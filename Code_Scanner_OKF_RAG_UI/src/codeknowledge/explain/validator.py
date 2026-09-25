"""ExplanationResponseValidator: schema + evidence-grounding checks on the model output.

Policy (deterministic, documented in README):
- Output that is not valid JSON for LLMExplanation is rejected (the service may run one repair).
- A source_ref must name an evidence block and a line range inside it; otherwise it is removed.
- An item left without any valid source_ref is kept but marked grounded=False ("unverified" in the UI).
- Line mentions in prose (L120, lines 120-130) outside all evidence are replaced by "[unverified line]".
- calls[].evidence_status is overwritten with the status derived from evidence (a call can never be
  "body_inspected" unless that callee's body was supplied); calls to targets absent from evidence are removed.
- A call without a citation gets its call-site lines from the OKF call evidence (deterministic, not inferred).
"""
from __future__ import annotations

import json
import re

from pydantic import ValidationError

from codeknowledge.explain.models import (CallExplanation, EvidenceItem, EvidencePackage, LLMExplanation,
                                          SourceRef, ValidationReport)
from codeknowledge.utils.ids import base_name

_LINE_MENTION = re.compile(r"\b(?:L|lines?\s+)(\d{1,6})(?:\s*[-–]\s*L?(\d{1,6}))?", re.IGNORECASE)
_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse(raw: str) -> tuple[LLMExplanation | None, list[str]]:
    text = raw.strip()
    if not text.startswith("{"):
        m = _JSON_BLOCK.search(text)  # tolerate a model wrapping JSON in prose/fences
        text = m.group(0) if m else text
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, [f"Invalid JSON: {exc.msg} at position {exc.pos}"]
    try:
        return LLMExplanation.model_validate(data), []
    except ValidationError as exc:
        return None, [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:20]]


class ExplanationResponseValidator:
    def __init__(self, pkg: EvidencePackage, validate_citations: bool = True):
        self.pkg = pkg
        self.enabled = validate_citations
        self.items = {i.evidence_id: i for i in pkg.items}
        self.ranges = [(i.start_line, i.end_line, i.file) for i in pkg.items
                       if i.start_line is not None and i.end_line is not None and i.kind in
                       ("method_source", "source_segment", "callee_source", "field", "sql_literal")]
        self.call_lines = {ln for i in pkg.items if i.kind == "call" for ln in i.lines}

    # ------------------------------------------------------------- refs
    def _ref_ok(self, ref: SourceRef) -> bool:
        item = self.items.get(ref.evidence_id)
        if item is None or ref.start_line > ref.end_line:
            return False
        return item.covers(ref.start_line, ref.end_line)

    def _clean_refs(self, refs: list[SourceRef], report: ValidationReport) -> list[SourceRef]:
        kept = [r for r in refs if self._ref_ok(r)]
        report.invalid_refs_removed += len(refs) - len(kept)
        return kept

    def _line_known(self, a: int, b: int | None) -> bool:
        b = b or a
        return any(s <= a <= b <= e for s, e, _ in self.ranges) or (a == b and a in self.call_lines)

    def _clean_text(self, text: str, report: ValidationReport) -> str:
        def repl(m: re.Match) -> str:
            a, b = int(m.group(1)), int(m.group(2)) if m.group(2) else None
            if self._line_known(a, b):
                return m.group(0)
            report.invalid_refs_removed += 1
            return "[unverified line]"
        return _LINE_MENTION.sub(repl, text)

    # ------------------------------------------------------------ calls
    @staticmethod
    def _names(item: EvidenceItem) -> set[str]:
        """Comparable names for an evidence item: id, qualified base name, and title name (no params)."""
        names = set()
        if item.entity_id:
            names |= {item.entity_id, base_name(item.entity_id)}
        title = item.title.removeprefix("calls ").split(" (")[0].strip()
        names |= {title, base_name(title)}
        return {n for n in names if n}

    def _matches(self, item: EvidenceItem, callee: str) -> bool:
        key = callee.strip()
        base = base_name(key)
        for n in self._names(item):
            if key == n or base == n or n.endswith("." + base) or base.endswith("." + n):
                return True
        return False

    def _call_item(self, call: CallExplanation):
        return next((i for i in self.pkg.items if i.kind == "call" and i.lines and self._matches(i, call.callee)), None)

    def _call_status(self, call: CallExplanation) -> str | None:
        call_items = [i for i in self.pkg.items if i.kind == "call" and self._matches(i, call.callee)]
        body_items = [i for i in self.pkg.items if i.kind in ("callee_source", "callee_signature")
                      and self._matches(i, call.callee)]
        if body_items:
            return "body_inspected" if body_items[0].kind == "callee_source" else "signature_only"
        if not call_items:
            return None
        status = call_items[0].status
        return {"external": "external", "unresolved": "unresolved", "ambiguous": "unresolved"}.get(status, "signature_only")

    def validate(self, exp: LLMExplanation) -> tuple[LLMExplanation, ValidationReport, list[str]]:
        report = ValidationReport(valid=True)
        warnings: list[str] = []
        if not self.enabled:
            return exp, report, warnings

        exp.summary = self._clean_text(exp.summary, report)
        for step in exp.execution_steps:
            step.source_refs = self._clean_refs(step.source_refs, report)
            step.description = self._clean_text(step.description, report)
            step.grounded = bool(step.source_refs) or step.certainty == "unknown"
        for group in (exp.branches, exp.data_transformations, exp.side_effects, exp.exceptions):
            for it in group:
                it.source_refs = self._clean_refs(it.source_refs, report)
                it.grounded = bool(it.source_refs)
                for attr in ("description", "condition", "when_true", "when_false"):
                    if isinstance(getattr(it, attr, None), str):
                        setattr(it, attr, self._clean_text(getattr(it, attr), report))
        kept_calls = []
        for call in exp.calls:
            status = self._call_status(call)
            if status is None:
                warnings.append(f"Removed a call the model mentioned that is not in the evidence: {call.callee}")
                continue
            if status != call.evidence_status:
                report.corrected_call_statuses += 1
                call.evidence_status = status  # type: ignore[assignment]
            call.source_refs = self._clean_refs(call.source_refs, report)
            if not call.source_refs and (ci := self._call_item(call)) is not None:
                call.source_refs = [SourceRef(evidence_id=ci.evidence_id, start_line=ln, end_line=ln) for ln in ci.lines]
            call.summary = self._clean_text(call.summary, report)
            call.grounded = bool(call.source_refs)
            kept_calls.append(call)
        exp.calls = kept_calls
        exp.uncertainties = [self._clean_text(u, report) for u in exp.uncertainties]

        items = exp.execution_steps + exp.branches + exp.data_transformations + exp.side_effects + exp.exceptions + exp.calls
        report.ungrounded_items = sum(1 for i in items if not i.grounded)
        if report.invalid_refs_removed:
            warnings.append(f"{report.invalid_refs_removed} source reference(s) not found in the evidence were removed.")
        if report.ungrounded_items:
            warnings.append(f"{report.ungrounded_items} statement(s) have no verified source reference (marked unverified).")
        if report.corrected_call_statuses:
            warnings.append(f"{report.corrected_call_statuses} call status(es) corrected to match the evidence.")
        return exp, report, warnings
