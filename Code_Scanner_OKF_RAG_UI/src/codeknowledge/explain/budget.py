"""EvidenceBudgetManager: priority-based selection that never silently truncates the selected body."""
from __future__ import annotations

from codeknowledge.explain.models import EvidenceItem, EvidencePackage

ITEM_OVERHEAD_TOKENS = 40  # delimiters + metadata line per evidence block
PROMPT_OVERHEAD_TOKENS = 900  # system prompt + instructions + schema


class EvidenceBudgetManager:
    def __init__(self, budget_tokens: int, chars_per_token: float, max_items: int):
        self.budget = budget_tokens
        self.cpt = chars_per_token
        self.max_items = max_items

    def tokens(self, item: EvidenceItem) -> int:
        return int((len(item.content) + len(item.title)) / self.cpt) + ITEM_OVERHEAD_TOKENS

    def _segment(self, body: EvidenceItem, max_tokens: int) -> list[EvidenceItem]:
        """Split a numbered body into ordered segments at blank lines / statement ends."""
        lines = body.content.splitlines()
        max_chars = max(400, int(max_tokens * self.cpt))
        segments: list[list[str]] = [[]]
        size = 0
        for i, line in enumerate(lines):
            segments[-1].append(line)
            size += len(line) + 1
            code = line.partition("| ")[2].strip()
            boundary = code == "" or code.endswith((";", "{", "}"))
            nxt = len(lines[i + 1]) if i + 1 < len(lines) else 0
            if size + nxt > max_chars and boundary:
                segments.append([])
                size = 0
        if not segments[-1]:
            segments.pop()
        out = []
        for n, seg in enumerate(segments, 1):
            first = int(seg[0].partition("|")[0])
            last = int(seg[-1].partition("|")[0])
            out.append(body.model_copy(update={
                "evidence_id": f"{body.evidence_id}.{n}", "kind": "source_segment",
                "title": f"{body.title} — part {n} of {len(segments)}", "start_line": first,
                "end_line": last, "content": "\n".join(seg)}))
        return out

    def apply(self, pkg: EvidencePackage) -> EvidencePackage:
        """Keep evidence in priority order (stable) within the budget; record what was omitted."""
        available = self.budget - PROMPT_OVERHEAD_TOKENS
        ordered = sorted(pkg.items, key=lambda i: (i.priority, int(i.evidence_id.strip("E").split(".")[0])))
        body = next((i for i in ordered if i.kind == "method_source"), None)
        kept: list[EvidenceItem] = []
        used = 0
        warnings = list(pkg.warnings)
        omitted: list[str] = []

        if body is not None and self.tokens(body) > available * 0.7:
            # The body alone would crowd out everything: explain it in ordered parts.
            segments = self._segment(body, int(available * 0.6))
            metadata = [i for i in ordered if i.kind in ("method_metadata", "class_metadata")]
            calls = [i for i in ordered if i.kind == "call"]
            kept = metadata + segments + calls
            dropped = [i for i in ordered if i not in metadata and i is not body and i not in calls]
            for i in dropped:
                omitted.append(f"{i.evidence_id} {i.title}: omitted (selected method explained in segments)")
            warnings.append(f"The method body is large (~{self.tokens(body)} tokens); it is explained in "
                            f"{len(segments)} ordered parts. Callee bodies and fields were omitted.")
            est = sum(self.tokens(i) for i in metadata + calls) + max(self.tokens(s) for s in segments)
            return pkg.model_copy(update={"items": kept, "warnings": warnings, "omitted": omitted,
                                          "segments": len(segments), "estimated_tokens": est + PROMPT_OVERHEAD_TOKENS})

        for item in ordered:
            t = self.tokens(item)
            mandatory = item.kind in ("method_source", "method_metadata")
            if mandatory or (used + t <= available and len(kept) < self.max_items):
                kept.append(item)
                used += t
            else:
                reason = "budget" if used + t > available else "max_evidence_documents"
                omitted.append(f"{item.evidence_id} {item.title}: omitted ({reason})")
        if omitted:
            warnings.append(f"{len(omitted)} evidence item(s) omitted to fit the context budget "
                            f"(~{self.budget} tokens).")
        # Present kept evidence in the original (build) order: metadata, body, class, calls, callees...
        kept.sort(key=lambda i: int(i.evidence_id.strip("E").split(".")[0]))
        return pkg.model_copy(update={"items": kept, "warnings": warnings, "omitted": omitted,
                                      "estimated_tokens": used + PROMPT_OVERHEAD_TOKENS})
