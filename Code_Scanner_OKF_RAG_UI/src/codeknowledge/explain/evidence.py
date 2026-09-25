"""MethodEvidenceBuilder: deterministic evidence for one method (no LLM, no network).

Same bundle + source + options => same evidence, in the same order, with the same ids.
"""
from __future__ import annotations

import re

from codeknowledge.config.settings import MethodExplanationSettings
from codeknowledge.explain.models import DeterministicFacts, EvidenceItem, EvidencePackage, ExplainOptions
from codeknowledge.models.entities import EntityType, OKFDocument
from codeknowledge.services.indexing_service import KnowledgeBase
from codeknowledge.source.reader import (SourceReader, SourceSnippet, _strip_code, extract_comments,
                                         extract_conditions)
from codeknowledge.utils.ids import short_name, strip_kind_prefix
from codeknowledge.utils.logging import get_logger

logger = get_logger("MethodEvidenceBuilder")

MAX_ID_LENGTH = 2000
MAX_CALLERS = 5
_ACCESSOR_RE = re.compile(r"^(get|set|is)[A-Z]")
_FIELD_RE = re.compile(
    r"^\s*((?:public|protected|private|static|final|transient|volatile)\s+)*"
    r"([\w.$<>\[\],? ]+?)\s+(\w+)\s*(=\s*(.+?))?;\s*$")
_SQL_RE = re.compile(r'"([^"]*\b(?:SELECT|INSERT|UPDATE|DELETE|MERGE|CALL)\b[^"]*)"', re.IGNORECASE)


class MethodNotFoundError(KeyError):
    pass


class InvalidMethodIdError(ValueError):
    pass


def validate_method_id(method_id: str) -> str:
    """Entity ids are opaque keys, never paths: reject control characters and absurd lengths."""
    if not method_id or len(method_id) > MAX_ID_LENGTH or any(ord(c) < 32 for c in method_id):
        raise InvalidMethodIdError("Invalid method id")
    return method_id


class MethodEvidenceBuilder:
    def __init__(self, kb: KnowledgeBase, cfg: MethodExplanationSettings):
        self.kb = kb
        self.cfg = cfg
        # A dedicated reader: the selected body must never be cut at the generic 800-line view limit.
        self.source = SourceReader(kb.source.root if kb.source.enabled else None,
                                   max_lines=cfg.max_source_lines_per_method + 1)

    # ----------------------------------------------------------- helpers
    def _label(self, entity_id: str) -> str:
        doc = self.kb.repo.get(entity_id)
        return doc.display_name() if doc else short_name(entity_id)

    def _snippet(self, doc: OKFDocument) -> SourceSnippet | None:
        try:
            return self.source.snippet(doc)
        except OSError as exc:
            logger.warning("Source read failed for %s: %s", doc.id, exc)
            return None

    @staticmethod
    def _has_body(snippet: SourceSnippet) -> bool:
        code = "\n".join(snippet.lines[snippet.decl_line - snippet.start_line:])
        return "{" in code

    def _calls(self, entity_id: str) -> list:
        rels = [r for r in self.kb.repo.relationships() if r.source == entity_id and r.type.value == "CALLS"]
        return sorted(rels, key=lambda r: ((r.lines or [r.line or 10 ** 9])[0], r.target))

    def _is_accessor(self, entity_id: str) -> bool:
        doc = self.kb.repo.get(entity_id)
        return bool(doc and doc.method_name and _ACCESSOR_RE.match(doc.method_name))

    def _fields(self, cls_doc: OKFDocument, body: str, include_constants: bool) -> list[tuple[int, str, str, bool]]:
        """(line, name, declaration, is_constant) for class-level fields used in `body`."""
        sn = self._snippet(cls_doc)
        if sn is None:
            return []
        out, depth, in_block = [], 0, False
        for i, raw in enumerate(sn.lines):
            code, in_block = _strip_code(raw, in_block)
            if depth == 1:
                m = _FIELD_RE.match(code)
                if m and "(" not in (m.group(2) or "") and m.group(3):
                    name = m.group(3)
                    is_const = "static" in (m.group(1) or "") + code.split(name)[0] and "final" in code.split(name)[0]
                    if re.search(rf"\b{re.escape(name)}\b", body) and (include_constants or not is_const):
                        out.append((sn.start_line + i, name, raw.strip(), is_const))
            depth += code.count("{") - code.count("}")
        return out

    # ------------------------------------------------------------- build
    def build(self, method_id: str, opts: ExplainOptions) -> tuple[EvidencePackage, DeterministicFacts]:
        validate_method_id(method_id)
        self.kb.require_ready()
        doc = self.kb.repo.get(method_id)
        if doc is None or doc.type != EntityType.METHOD:
            raise MethodNotFoundError(method_id)

        depth_limit = self.cfg.max_callee_depth if opts.max_callee_depth is None else opts.max_callee_depth
        include_callers = self.cfg.include_caller_context if opts.include_caller_context is None else opts.include_caller_context
        include_config = self.cfg.include_related_config if opts.include_related_config is None else opts.include_related_config
        include_sql = self.cfg.include_sql_evidence if opts.include_sql_evidence is None else opts.include_sql_evidence

        items: list[EvidenceItem] = []
        warnings: list[str] = []

        def add(**kw) -> EvidenceItem:
            item = EvidenceItem(evidence_id=f"E{len(items) + 1}", **kw)
            items.append(item)
            return item

        # 1. method metadata (always available from OKF)
        meta_lines = [f"Method: {doc.display_name()}", f"Id: {doc.id}"]
        if doc.signature:
            meta_lines.append(f"Declaration: {doc.signature}")
        java = doc.metadata.get("java") if isinstance(doc.metadata.get("java"), dict) else {}
        if java.get("returnType"):
            meta_lines.append(f"Returns: {java['returnType']}")
        if java.get("visibility"):
            meta_lines.append(f"Visibility: {java['visibility']}")
        if doc.source_file:
            meta_lines.append(f"Location: {doc.source_file}:{doc.source_line}-{doc.end_line or doc.source_line}")
        add(kind="method_metadata", title=f"{doc.display_name()} (metadata)", entity_id=doc.id,
            file=doc.source_file, start_line=doc.source_line, end_line=doc.end_line or doc.source_line,
            priority=1, content="\n".join(meta_lines))

        # 2. selected method body (never truncated: too large => refused with a warning)
        facts = DeterministicFacts()
        snippet = self._snippet(doc)
        body_text = ""
        source_available = False
        if snippet is None:
            reason = ("source.root_dir is not configured" if not self.source.enabled
                      else f"source file not found under source.root_dir: {doc.source_file}")
            warnings.append(f"Insufficient evidence: the method body is not available ({reason}). "
                            "Only OKF metadata can be explained.")
        elif snippet.truncated or len(snippet.lines) > self.cfg.max_source_lines_per_method:
            warnings.append(f"Size limit: the method has more than {self.cfg.max_source_lines_per_method} lines "
                            "(method_explanation.max_source_lines_per_method); the body was not sent to the model.")
        else:
            source_available = True
            body_text = snippet.text
            warnings.extend(snippet.notes)
            add(kind="method_source", title=f"{doc.display_name()} source", entity_id=doc.id, file=snippet.file,
                start_line=snippet.start_line, end_line=snippet.end_line, priority=0, content=snippet.numbered())
            facts.comments = [c.__dict__ for c in extract_comments(snippet)]
            facts.conditions = [c.__dict__ for c in extract_conditions(snippet)]

        # 3. declaring class + referenced fields/constants
        cls_doc = None
        cls_ids = [r.source for r in self.kb.repo.relationships()
                   if r.target == doc.id and r.type.value == "CONTAINS" and self.kb.repo.get(r.source)
                   and self.kb.repo.get(r.source).type in (EntityType.CLASS, EntityType.INTERFACE, EntityType.ENUM)]
        if cls_ids:
            cls_doc = self.kb.repo.get(sorted(cls_ids)[0])
            add(kind="class_metadata", title=f"{cls_doc.display_name()} (declaring type)", entity_id=cls_doc.id,
                file=cls_doc.source_file, start_line=cls_doc.source_line, end_line=cls_doc.end_line,
                priority=2, content="\n".join(filter(None, [cls_doc.signature, cls_doc.summary])))
            if source_available:
                for line, name, decl, is_const in self._fields(cls_doc, body_text, include_config):
                    add(kind="field", title=f"{'constant' if is_const else 'field'} {name}", entity_id=cls_doc.id,
                        file=cls_doc.source_file, start_line=line, end_line=line, priority=4,
                        content=f"{line}| {decl}")

        # 4. calls made by the method (status + call-site lines from OKF)
        for rel in self._calls(doc.id):
            target_doc = self.kb.repo.get(rel.target)
            label = target_doc.display_name() if target_doc else rel.target
            where = ", ".join(map(str, rel.lines or ([rel.line] if rel.line else []))) or "?"
            status = rel.status if rel.status in ("resolved", "unresolved", "ambiguous", "external") else "resolved"
            add(kind="call", title=f"calls {label}", entity_id=rel.target if target_doc else None,
                file=doc.source_file, lines=list(rel.lines or ([rel.line] if rel.line else [])),
                status=status, priority=3, content=f"line {where}: calls {label} [{status}]")
            facts.calls.append({"target": label, "entity_id": rel.target if target_doc else None,
                                "status": status, "lines": rel.lines or ([rel.line] if rel.line else [])})

        # 5. callee bodies within depth (cycle-safe, non-accessors first, capped per method)
        visited = {doc.id}
        frontier = [doc.id]
        for depth in range(1, depth_limit + 1):
            nxt: list[str] = []
            for caller_id in frontier:
                targets = [r.target for r in self._calls(caller_id)
                           if r.status == "resolved" and self.kb.repo.get(r.target)
                           and self.kb.repo.get(r.target).type == EntityType.METHOD]
                targets = list(dict.fromkeys(targets))
                ranked = [t for t in targets if not self._is_accessor(t)] + [t for t in targets if self._is_accessor(t)]
                for tid in ranked[: self.cfg.max_callees_per_method]:
                    if tid in visited:
                        continue
                    visited.add(tid)
                    tdoc = self.kb.repo.get(tid)
                    sn = self._snippet(tdoc)
                    if sn is not None and self._has_body(sn) and not sn.truncated:
                        add(kind="callee_source", title=f"{tdoc.display_name()} source (callee, depth {depth})",
                            entity_id=tid, file=sn.file, start_line=sn.start_line, end_line=sn.end_line,
                            depth=depth, priority=4 + depth + (1 if self._is_accessor(tid) else 0),
                            content=sn.numbered())
                        nxt.append(tid)
                    else:
                        why = "no implementation (interface/abstract method)" if sn is not None else "source not available"
                        add(kind="callee_signature", title=f"{tdoc.display_name()} (callee, body unavailable)",
                            entity_id=tid, file=tdoc.source_file, start_line=tdoc.source_line,
                            end_line=tdoc.end_line or tdoc.source_line, status="unavailable", depth=depth,
                            priority=5 + depth, content=f"{tdoc.signature or tdoc.display_name()} — {why}")
                skipped = len([t for t in ranked if t not in visited])
                if skipped:
                    warnings.append(f"{skipped} callee bodies of {self._label(caller_id)} not included "
                                    f"(max_callees_per_method={self.cfg.max_callees_per_method} or already included).")
            frontier = nxt

        # 6. callers (optional)
        if include_callers:
            callers = sorted({r.source for r in self.kb.repo.relationships()
                              if r.target == doc.id and r.type.value == "CALLS" and self.kb.repo.get(r.source)})
            for cid in callers[:MAX_CALLERS]:
                cdoc = self.kb.repo.get(cid)
                add(kind="caller", title=f"called by {cdoc.display_name()}", entity_id=cid, file=cdoc.source_file,
                    start_line=cdoc.source_line, end_line=cdoc.end_line or cdoc.source_line, priority=7,
                    content=f"{cdoc.signature or cdoc.display_name()}")

        # 7. SQL-looking literals in the selected body, callee bodies and referenced constants
        if include_sql:
            for it in [i for i in items if i.kind in ("method_source", "callee_source", "field")]:
                for raw in it.content.splitlines():
                    num, _, code = raw.partition("| ")
                    for sql in _SQL_RE.findall(code):
                        ln = int(num.strip()) if num.strip().isdigit() else it.start_line
                        add(kind="sql_literal", title=f"SQL literal ({it.title})", entity_id=it.entity_id,
                            file=it.file, start_line=ln, end_line=ln, priority=4, content=f'{ln}| "{sql}"')

        pkg = EvidencePackage(method_id=doc.id, method_signature=doc.signature or doc.display_name(),
                              method_title=doc.display_name(), source_available=source_available,
                              items=items, warnings=warnings)
        logger.info("Evidence built method=%s items=%d source=%s callees=%d warnings=%d", strip_kind_prefix(doc.id),
                    len(items), source_available, len(visited) - 1, len(warnings))
        return pkg, facts
