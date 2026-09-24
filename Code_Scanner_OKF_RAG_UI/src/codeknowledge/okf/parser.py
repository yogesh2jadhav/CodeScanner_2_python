"""Parse a single OKF Markdown document (YAML frontmatter + Markdown body).

The parser is deliberately tolerant: Java2OKF output and hand-written OKF may
differ in key names, so we accept several aliases and fall back to the body
(headings, links) when frontmatter is incomplete. Anything we cannot interpret
becomes a warning, never an exception, so one bad file never stops ingestion.
"""
from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

import yaml

from codeknowledge.models.entities import EntityType, OKFDocument, is_navigation_type, normalize_entity_type
from codeknowledge.models.relationships import Relationship, RelationType, parse_relation_type, parse_section_type
from codeknowledge.utils.ids import id_from_path, normalize_id, simplify_params, strip_kind_prefix

# libyaml's C loader parses frontmatter ~7x faster than the pure-Python one, which
# dominates load time on large bundles; fall back when PyYAML was built without it.
_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

PATH_TARGET_PREFIX = "@path:"  # marks a relationship target that must be resolved via document path
WIKI_LINK_PREFIX = "wiki:"  # marks a [[wiki]] link (target is an id, not a path)

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
MD_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_WIKI_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")

_ID_KEYS = ("id", "identifier", "fqn", "qualified_name", "fully_qualified_name")
_SOURCE_KEYS = ("source_file", "source", "source_path", "file", "path", "resource")
_LINE_KEYS = ("source_line", "line", "start_line", "line_start")
_SUMMARY_KEYS = ("summary", "description")
# Frontmatter keys that are never relationship lists even if they look like aliases.
_NON_REL_KEYS = set(_ID_KEYS) | set(_SOURCE_KEYS) | set(_LINE_KEYS) | {
    "title", "type", "kind", "flow", "relationships", "java", "tags", "generated"}

# Java2OKF bullet markers (see java2okf docs/okf-output.md "Rendering relationship targets").
_EXTERNAL_MARKER_RE = re.compile(r"\((external|implicit)\)")
_UNRESOLVED_MARKER_RE = re.compile(r"\b(UNRESOLVED|AMBIGUOUS)\b|\(no document\)")
_LINE_NO_RE = re.compile(r"\bline (\d+)\b")
_LINES_RANGE_RE = re.compile(r"^\s*(\d+)\s*(?:[-–]\s*(\d+))?\s*$")


@dataclass
class ParseResult:
    document: OKFDocument | None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    has_frontmatter: bool = False


def split_frontmatter(text: str) -> tuple[str | None, str]:
    text = text.lstrip("﻿")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    return m.group(1), text[m.end():]


def _first(meta: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for k in keys:
        if meta.get(k) not in (None, ""):
            return meta[k]
    return None


def _is_external(href: str) -> bool:
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", href)) or href.startswith("#")


def resolve_link(doc_path: str, href: str) -> str | None:
    """Resolve a relative Markdown link to an OKF-relative posix path; None for external/anchor links."""
    if _is_external(href):
        return None
    href = href.split("#", 1)[0].split("?", 1)[0]
    if not href:
        return None
    base = posixpath.dirname(doc_path)
    joined = href.lstrip("/") if href.startswith("/") else posixpath.join(base, href)
    return posixpath.normpath(joined)


def _iter_body_lines(body: str):
    """Yield (line, in_code_block); links inside fenced code are not links."""
    in_code = False
    for line in body.splitlines():
        if _FENCE_RE.match(line):
            in_code = not in_code
            continue
        yield line, in_code


def _targets_from_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        t = value.get("id") or value.get("target") or value.get("name") or value.get("type")
        return [str(t)] if t else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_targets_from_value(item))
        return out
    return [str(value)]


def _frontmatter_relationships(doc_id: str, meta: dict[str, Any], warnings: list[str]) -> list[Relationship]:
    rels: list[Relationship] = []

    def add(rel_key: str, value: Any) -> None:
        parsed = parse_relation_type(rel_key)
        if parsed is None:
            warnings.append(f"Unknown relationship type '{rel_key}'")
            return
        rtype, reverse = parsed
        for target in _targets_from_value(value):
            target = normalize_id(target)
            if not target:
                continue
            src, dst = (target, doc_id) if reverse else (doc_id, target)
            rels.append(Relationship(source=src, target=dst, type=rtype, origin="frontmatter"))

    block = meta.get("relationships")
    if isinstance(block, dict):
        for k, v in block.items():
            add(str(k), v)
    elif isinstance(block, list):
        for item in block:
            if isinstance(item, dict) and item.get("type") and (item.get("target") or item.get("id")):
                add(str(item["type"]), item.get("target") or item.get("id"))
            elif isinstance(item, str) and ":" in item:
                k, v = item.split(":", 1)
                add(k, v.strip())
            else:
                warnings.append(f"Unrecognised relationship entry: {item!r}")
    elif block is not None:
        warnings.append("'relationships' must be a mapping or a list")

    for key, value in meta.items():
        if key in _NON_REL_KEYS or parse_relation_type(str(key)) is None:
            continue
        # Only treat top-level keys as relationships when values look like references.
        if key in {"methods", "fields", "members"} and not _looks_like_refs(value):
            continue
        add(str(key), value)
    return rels


def _looks_like_refs(value: Any) -> bool:
    items = value if isinstance(value, list) else [value]
    return all(isinstance(i, str) or (isinstance(i, dict) and ("id" in i or "target" in i)) for i in items)


def _body_relationships(doc_id: str, doc_path: str, body: str, strict_markers: bool = False,
                        skip_sections: frozenset[str] = frozenset()) -> tuple[list[Relationship], list[str]]:
    """Relationships from Markdown sections and links.

    strict_markers: in Java2OKF bundles a link-less bullet is only a relationship
    target when it carries a marker ((external), UNRESOLVED, ...); otherwise it is
    plain text such as a primitive field type. Hand-written OKF may name symbols
    in backticks without markers, so the generic mode accepts them.
    """
    rels: list[Relationship] = []
    links: list[str] = []
    section: tuple[RelationType, bool] | None = None

    for line, in_code in _iter_body_lines(body):
        if in_code:
            continue
        h = _HEADING_RE.match(line)
        if h:
            key = h.group(2).strip().lower().replace(" ", "_")
            section = parse_section_type(h.group(2)) if len(h.group(1)) > 1 and key not in skip_sections else None
            continue

        # (target, status) pairs found on this line
        line_targets: list[tuple[str, str]] = []
        for _text, href in MD_LINK_RE.findall(line):
            resolved = resolve_link(doc_path, href)
            if resolved is None:
                continue
            links.append(resolved)
            if resolved.endswith(".md"):
                line_targets.append((PATH_TARGET_PREFIX + resolved, "resolved"))
        for wiki in _WIKI_LINK_RE.findall(line):
            links.append(WIKI_LINK_PREFIX + wiki.strip())
            line_targets.append((normalize_id(wiki), "resolved"))

        # Inside a relationship section, list items without links may still name
        # a symbol (e.g. "- `CasingService.processClaims`" or a Java2OKF marker item).
        if section and not line_targets and line.lstrip().startswith(("- ", "* ")):
            code = _BACKTICK_RE.findall(line)
            if code:
                if _EXTERNAL_MARKER_RE.search(line):
                    line_targets.append((normalize_id(code[0]), "external"))
                elif _UNRESOLVED_MARKER_RE.search(line):
                    line_targets.append((normalize_id(code[0]), "unresolved"))
                elif not strict_markers:
                    line_targets.append((normalize_id(code[0]), "resolved"))

        m_line = _LINE_NO_RE.search(line)
        line_no = int(m_line.group(1)) if m_line else None
        for target, status in line_targets:
            if section:
                rtype, reverse = section
                origin = "body_section"
            else:
                rtype, reverse, origin = RelationType.REFERENCES, False, "body_link"
            src, dst = (target, doc_id) if reverse else (doc_id, target)
            rels.append(Relationship(source=src, target=dst, type=rtype, origin=origin,
                                     status=status, line=line_no))
    return rels, links


def _first_heading(body: str) -> str | None:
    for line, in_code in _iter_body_lines(body):
        if not in_code:
            h = _HEADING_RE.match(line)
            if h and len(h.group(1)) == 1:
                return h.group(2).strip()
    return None


def _first_paragraph(body: str) -> str | None:
    para: list[str] = []
    for line, in_code in _iter_body_lines(body):
        if in_code:
            continue
        s = line.strip()
        if not s:
            if para:
                break
            continue
        if s.startswith(("#", "-", "*", "|", ">")):
            if para:
                break
            continue
        para.append(s)
    return " ".join(para)[:500] if para else None


def _compose_id(meta: dict[str, Any]) -> str | None:
    pkg, cls, mth = meta.get("package"), meta.get("class_name") or meta.get("class"), meta.get("method_name") or meta.get("method")
    if cls and mth:
        return ".".join(p for p in (pkg, cls, mth) if p)
    if cls:
        return ".".join(p for p in (pkg, cls) if p)
    return None


def _is_java2okf(meta: dict[str, Any]) -> bool:
    gen = meta.get("generated")
    by = gen.get("by") if isinstance(gen, dict) else None
    return (isinstance(by, str) and by.lower().startswith("java2okf")) or str(meta.get("id", "")).startswith("java-")


def _parse_lines(value: Any) -> tuple[int | None, int | None]:
    if value is None:
        return None, None
    if isinstance(value, int):
        return value, None
    m = _LINES_RANGE_RE.match(str(value))
    if not m:
        return None, None
    return int(m.group(1)), (int(m.group(2)) if m.group(2) else None)


def _section_code(body: str, heading: str) -> str | None:
    """First fenced code block under '## <heading>' (Java2OKF Signature/Declaration)."""
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$\s*```[a-zA-Z]*\n(.*?)```", body, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else None


def _java2okf_fields(meta: dict[str, Any], body: str, doc_type: EntityType, title: str) -> dict[str, Any]:
    """Map Java2OKF frontmatter (`java:` block, `resource`, tags) onto document fields."""
    java = meta.get("java") if isinstance(meta.get("java"), dict) else {}
    tags = [str(t) for t in meta.get("tags") or []]
    out: dict[str, Any] = {}
    declaring = java.get("declaringClass")
    qualified = java.get("qualifiedName") or declaring
    pkg = java.get("package")
    if not pkg and qualified:
        # Methods carry no package key; the package is the tag that prefixes the class name.
        cands = [t for t in tags if qualified.startswith(t + ".")]
        pkg = max(cands, key=len) if cands else None
    out["package"] = pkg or (java.get("package") if doc_type == EntityType.PACKAGE else None) or (
        title if doc_type == EntityType.PACKAGE else None)
    if qualified:
        cls = qualified[len(pkg) + 1:] if pkg and qualified.startswith(pkg + ".") else qualified.rsplit(".", 1)[-1]
        out["class_name"] = cls
    start, end = _parse_lines(java.get("lines"))
    out["source_line"], out["end_line"] = start, end
    if doc_type == EntityType.METHOD:
        out["method_name"] = title
        sig = str(java.get("signature") or title)
        owner = (out.get("class_name") or "").rsplit(".", 1)[-1]
        is_ctor = str(meta.get("type", "")).lower() == "javaconstructor"
        # Constructors read as "Order(String, double)" rather than "Order.Order(...)".
        out["display"] = simplify_params(sig) if is_ctor else f"{owner}.{simplify_params(sig)}".lstrip(".")
        code_sig = _section_code(body, "Signature")
        out["signature"] = code_sig or sig
        ret = java.get("returnType")
        out["summary"] = (f"{'Constructor' if str(meta.get('type')).lower() == 'javaconstructor' else 'Method'} "
                          f"{out['display']}" + (f" returns {ret}" if ret else "") +
                          (f"; declared in {declaring}" if declaring else "") + ".")
    elif doc_type in (EntityType.CLASS, EntityType.INTERFACE, EntityType.ENUM):
        decl = _section_code(body, "Declaration")
        out["signature"] = decl
        out["display"] = out.get("class_name") or title
        out["summary"] = f"{decl or java.get('kind', 'type')} in package {pkg}." if pkg else decl
    elif doc_type == EntityType.PACKAGE:
        out["summary"] = f"Package {title}" + (f" with {java.get('types')} types." if java.get("types") else ".")
    return out


def parse_document(text: str, rel_path: str) -> ParseResult:
    rel_path = PurePosixPath(rel_path).as_posix()
    result = ParseResult(document=None)
    fm_text, body = split_frontmatter(text)
    meta: dict[str, Any] = {}

    if fm_text is None:
        result.warnings.append("Missing YAML frontmatter")
    else:
        result.has_frontmatter = True
        try:
            loaded = yaml.load(fm_text, Loader=_YAML_LOADER)  # noqa: S506 - safe loader
        except yaml.YAMLError as exc:
            result.errors.append(f"Malformed YAML frontmatter: {str(exc).splitlines()[0]}")
            return result
        if loaded is None:
            loaded = {}
        if not isinstance(loaded, dict):
            result.errors.append("YAML frontmatter must be a mapping")
            return result
        meta = loaded

    raw_type = meta.get("type") or meta.get("kind")
    navigation = is_navigation_type(raw_type)
    raw_id = _first(meta, _ID_KEYS)
    doc_id = normalize_id(str(raw_id)) if raw_id else (_compose_id(meta) or id_from_path(rel_path))
    if not raw_id and result.has_frontmatter and not navigation:
        result.warnings.append(f"No id in frontmatter; derived id '{doc_id}'")
    title = str(meta.get("title") or _first_heading(body) or PurePosixPath(rel_path).stem)

    line_val = _first(meta, _LINE_KEYS)
    try:
        source_line = int(line_val) if line_val is not None else None
    except (TypeError, ValueError):
        result.warnings.append(f"Invalid source line '{line_val}'")
        source_line = None

    java2okf = _is_java2okf(meta)
    doc_type = normalize_entity_type(raw_type)
    # Java2OKF type documents aggregate "Called By" over all members; the method
    # documents already carry those calls precisely, so the aggregate is skipped
    # rather than turned into vague class-level CALLS edges.
    skip = frozenset({"called_by"}) if java2okf and doc_type in (
        EntityType.CLASS, EntityType.INTERFACE, EntityType.ENUM) else frozenset()
    rels = _frontmatter_relationships(doc_id, meta, result.warnings)
    body_rels, links = _body_relationships(doc_id, rel_path, body, strict_markers=java2okf, skip_sections=skip)
    if navigation:
        # Index/Log pages link to everything; as graph edges they would be pure noise.
        rels, body_rels = [], []

    # De-duplicate identical edges that appear both in frontmatter and body.
    seen: set[tuple[str, str, str]] = set()
    unique: list[Relationship] = []
    for r in rels + body_rels:
        key = (r.source, r.target, r.type.value)
        if key not in seen:
            seen.add(key)
            unique.append(r)

    extra: dict[str, Any] = _java2okf_fields(meta, body, doc_type, title) if java2okf else {}
    summary = _first(meta, _SUMMARY_KEYS) or extra.get("summary") or _first_paragraph(body)
    source_file = _first(meta, _SOURCE_KEYS)
    if extra.get("source_line") is not None:
        source_line = extra["source_line"]
    result.document = OKFDocument(
        id=doc_id,
        path=rel_path,
        title=title,
        type=doc_type,
        raw_type=str(raw_type) if raw_type is not None else None,
        metadata=meta,
        content=body.strip(),
        links=list(dict.fromkeys(links)),
        relationships=unique,
        package=meta.get("package") or extra.get("package"),
        class_name=meta.get("class_name") or meta.get("class") or extra.get("class_name"),
        method_name=meta.get("method_name") or meta.get("method") or extra.get("method_name"),
        source_file=str(source_file) if source_file else None,
        source_line=source_line,
        end_line=extra.get("end_line"),
        summary=str(summary) if summary else None,
        signature=meta.get("signature") or extra.get("signature"),
        navigation=navigation,
        qualified_name=strip_kind_prefix(doc_id),
        display=extra.get("display"),
    )
    return result
