"""Read a code entity's source (with comments) from the analysed project.

Why read source at all: Java2OKF records structure (who calls what, on which
line) but not method bodies or comments. Explaining *what a method does* needs
the code and the developers' own comments, so we read them from the project the
bundle was generated from (`source.root_dir`), using the bundle's `resource` and
line range. Source is only read, never executed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from codeknowledge.models.entities import EntityType, OKFDocument
from codeknowledge.utils.logging import get_logger

logger = get_logger("SourceReader")

MAX_DRIFT_LINES = 300  # how far to look when the file changed after OKF generation


@dataclass
class SourceComment:
    start_line: int
    end_line: int
    text: str
    kind: str  # javadoc | block | line


@dataclass
class SourceCondition:
    line: int
    kind: str  # if | else if | filter | loop | switch | catch | ternary
    expression: str


@dataclass
class SourceSnippet:
    entity_id: str
    file: str  # OKF `resource`, relative to the project root
    start_line: int  # first line shown (includes Javadoc/annotations above the declaration)
    decl_line: int  # declaration line
    end_line: int
    lines: list[str]
    truncated: bool = False
    drifted: bool = False  # declaration found away from the OKF line (file changed since generation)
    notes: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def numbered(self) -> str:
        width = len(str(self.start_line + len(self.lines)))
        return "\n".join(f"{self.start_line + i:>{width}}| {line}" for i, line in enumerate(self.lines))


# ----------------------------------------------------------------- helpers

def _strip_code(line: str, in_block: bool) -> tuple[str, bool]:
    """Remove string/char literals and comments from a line (for brace counting)."""
    out = []
    i = 0
    while i < len(line):
        if in_block:
            end = line.find("*/", i)
            if end < 0:
                return "".join(out), True
            i, in_block = end + 2, False
            continue
        ch = line[i]
        if line.startswith("//", i):
            break
        if line.startswith("/*", i):
            in_block, i = True, i + 2
            continue
        if ch in "\"'":
            j = i + 1
            while j < len(line) and line[j] != ch:
                j += 2 if line[j] == "\\" else 1
            i = j + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out), in_block


def _find_body_end(lines: list[str], decl_idx: int) -> int:
    """Index of the line with the closing brace of the member declared at decl_idx."""
    depth, opened, in_block = 0, False, False
    for idx in range(decl_idx, len(lines)):
        code, in_block = _strip_code(lines[idx], in_block)
        if not opened and ";" in code and "{" not in code:
            return idx  # abstract / interface method
        for ch in code:
            if ch == "{":
                depth, opened = depth + 1, True
            elif ch == "}":
                depth -= 1
                if opened and depth == 0:
                    return idx
    return len(lines) - 1


def _leading_doc_start(lines: list[str], decl_idx: int) -> int:
    """Include Javadoc / annotations / comments directly above the declaration."""
    idx = decl_idx - 1
    start = decl_idx
    in_comment = False
    while idx >= 0:
        s = lines[idx].strip()
        if in_comment:
            start = idx
            if s.startswith("/*"):
                in_comment = False
            idx -= 1
            continue
        if s.endswith("*/"):
            in_comment = not s.startswith("/*") or s == "*/"
            start = idx
        elif s.startswith("@") or s.startswith("//"):
            start = idx
        else:
            break
        idx -= 1
    return start


def _locate_declaration(lines: list[str], hint_idx: int, name: str) -> tuple[int, bool]:
    """Find the declaration line of `name` nearest the OKF hint; (index, drifted)."""
    pattern = re.compile(rf"\b{re.escape(name)}\s*\(")
    if 0 <= hint_idx < len(lines) and pattern.search(lines[hint_idx]):
        return hint_idx, False
    # Annotations/modifiers may wrap: accept the declaration within a few lines after the hint.
    for off in range(1, 4):
        j = hint_idx + off
        if 0 <= j < len(lines) and pattern.search(lines[j]):
            return j, False
    for off in range(1, MAX_DRIFT_LINES):
        for j in (hint_idx - off, hint_idx + off):
            if 0 <= j < len(lines) and pattern.search(lines[j]) and not lines[j].strip().startswith(("//", "*")) \
                    and ";" not in lines[j].split("(")[0]:
                return j, True
    return hint_idx, False


# ------------------------------------------------------------------ reader

class SourceReader:
    def __init__(self, root_dir: str | Path | None, max_lines: int = 800):
        self.root = Path(root_dir).expanduser().resolve() if root_dir else None
        self.max_lines = max_lines

    @property
    def enabled(self) -> bool:
        return self.root is not None and self.root.is_dir()

    def _resolve(self, resource: str) -> Path | None:
        if not self.enabled or not resource:
            return None
        path = (self.root / resource.replace("\\", "/")).resolve()
        # Never read outside the configured project root (resource comes from untrusted OKF).
        if self.root not in path.parents and path != self.root:
            logger.warning("Refusing to read source outside root: %s", resource)
            return None
        return path if path.is_file() else None

    @staticmethod
    @lru_cache(maxsize=256)
    def _read_lines(path: str, mtime: float) -> tuple[str, ...]:
        return tuple(Path(path).read_text(encoding="utf-8", errors="replace").splitlines())

    def snippet(self, doc: OKFDocument, max_lines: int | None = None) -> SourceSnippet | None:
        path = self._resolve(doc.source_file or "")
        if path is None or doc.source_line is None:
            return None
        lines = list(self._read_lines(str(path), path.stat().st_mtime))
        hint = doc.source_line - 1
        notes: list[str] = []
        if doc.type == EntityType.METHOD and doc.method_name:
            decl, drifted = _locate_declaration(lines, hint, doc.method_name)
            end = _find_body_end(lines, decl)
        else:
            decl, drifted = hint, False
            end = (doc.end_line - 1) if doc.end_line else _find_body_end(lines, decl)
        if drifted:
            notes.append(f"Source changed since OKF generation: declaration found at line {decl + 1} "
                         f"(OKF says {doc.source_line}).")
        start = _leading_doc_start(lines, decl)
        end = min(end, len(lines) - 1)
        shown = lines[start:end + 1]
        limit = max_lines or self.max_lines
        truncated = len(shown) > limit
        if truncated:
            notes.append(f"Source truncated to the first {limit} lines.")
            shown = shown[:limit]
        return SourceSnippet(entity_id=doc.id, file=doc.source_file or "", start_line=start + 1,
                             decl_line=decl + 1, end_line=start + len(shown), lines=shown,
                             truncated=truncated, drifted=drifted, notes=notes)


# ------------------------------------------------------- comments & conditions

_CODE_LIKE = re.compile(r"[;{}]\s*$|^\s*(return|if|for|while|else)\b.*[;{)]\s*$")


def extract_comments(snippet: SourceSnippet) -> list[SourceComment]:
    """Developer comments in source order; commented-out code is skipped."""
    out: list[SourceComment] = []
    block: list[str] | None = None
    block_start = 0
    kind = "block"
    pending_line: SourceComment | None = None

    def flush_line() -> None:
        nonlocal pending_line
        if pending_line and pending_line.text.strip():
            out.append(pending_line)
        pending_line = None

    for i, raw in enumerate(snippet.lines):
        ln = snippet.start_line + i
        s = raw.strip()
        if block is not None:
            end = s.find("*/")
            body = s[:end] if end >= 0 else s
            block.append(body.lstrip("*").strip())
            if end >= 0:
                text = "\n".join(t for t in block if t).strip()
                if text and not all(_CODE_LIKE.search(t) for t in block if t):
                    out.append(SourceComment(block_start, ln, text, kind))
                block = None
            continue
        idx = _comment_start(raw)
        if idx is None:
            flush_line()
            continue
        rest = raw[idx:]
        if rest.startswith("/*"):
            flush_line()
            kind = "javadoc" if rest.startswith("/**") else "block"
            inner = rest[3 if kind == "javadoc" else 2:]
            end = inner.find("*/")
            if end >= 0:
                text = inner[:end].strip().lstrip("*").strip()
                if text and not _CODE_LIKE.search(text):
                    out.append(SourceComment(ln, ln, text, kind))
            else:
                block, block_start = [inner.lstrip("*").strip()], ln
            continue
        text = rest[2:].strip()
        if not text or _CODE_LIKE.search(text):
            flush_line()
            continue
        # Merge consecutive // lines into one comment.
        if pending_line and pending_line.end_line == ln - 1:
            pending_line.text += "\n" + text
            pending_line.end_line = ln
        else:
            flush_line()
            pending_line = SourceComment(ln, ln, text, "line")
    flush_line()
    return out


def _comment_start(line: str) -> int | None:
    """Column where a comment starts on this line, ignoring comment markers inside strings."""
    i = 0
    while i < len(line):
        ch = line[i]
        if ch in "\"'":
            j = i + 1
            while j < len(line) and line[j] != ch:
                j += 2 if line[j] == "\\" else 1
            i = j + 1
            continue
        if line.startswith("//", i) or line.startswith("/*", i):
            return i
        i += 1
    return None


_COND_START = re.compile(
    r"\belse\s+if\s*\(|\bif\s*\(|\.filter\s*\(|\bwhile\s*\(|\bfor\s*\(|\bswitch\s*\(|\bcatch\s*\(|\.anyMatch\s*\(|"
    r"\.allMatch\s*\(|\.noneMatch\s*\(")


def _balanced(text: str, open_idx: int) -> str | None:
    depth = 0
    for j in range(open_idx, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1:j]
    return None


def extract_conditions(snippet: SourceSnippet) -> list[SourceCondition]:
    """Conditions/branches in the code (if, filter predicates, loops, catch) with line numbers."""
    code_lines: list[str] = []
    in_block = False
    for raw in snippet.lines:
        code, in_block = _strip_code_keep_strings(raw, in_block)
        code_lines.append(code)
    joined = "\n".join(code_lines)
    starts = [0]
    for line in code_lines:
        starts.append(starts[-1] + len(line) + 1)

    out: list[SourceCondition] = []
    for m in _COND_START.finditer(joined):
        token = m.group(0)
        kind = ("else if" if token.startswith("else") else token.strip(".( \t").split("(")[0].strip())
        kind = {"for": "loop", "while": "loop"}.get(kind, kind)
        expr = _balanced(joined, m.end() - 1)
        if expr is None:
            continue
        line_no = snippet.start_line + next(i for i in range(len(starts)) if starts[i + 1] > m.start())
        expr = " ".join(expr.split())
        out.append(SourceCondition(line_no, kind, expr))
    return out


def _strip_code_keep_strings(line: str, in_block: bool) -> tuple[str, bool]:
    """Remove comments only (keep string literals, they matter in conditions)."""
    out = []
    i = 0
    while i < len(line):
        if in_block:
            end = line.find("*/", i)
            if end < 0:
                return "".join(out), True
            i, in_block = end + 2, False
            continue
        ch = line[i]
        if ch in "\"'":
            j = i + 1
            while j < len(line) and line[j] != ch:
                j += 2 if line[j] == "\\" else 1
            out.append(line[i:j + 1])
            i = j + 1
            continue
        if line.startswith("//", i):
            break
        if line.startswith("/*", i):
            in_block, i = True, i + 2
            continue
        out.append(ch)
        i += 1
    return "".join(out), in_block
