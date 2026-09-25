"""Render a validated explanation to Markdown (copy button, Ask answers)."""
from __future__ import annotations

from codeknowledge.explain.models import EvidencePackage, LLMExplanation, SourceRef


def _refs(refs: list[SourceRef], pkg: EvidencePackage) -> str:
    out = []
    for r in refs:
        item = pkg.get(r.evidence_id)
        name = (item.file or "").rsplit("/", 1)[-1] if item else r.evidence_id
        out.append(f"[{name}:{r.start_line}-{r.end_line}]" if r.end_line != r.start_line else f"[{name}:{r.start_line}]")
    return " " + " ".join(out) if out else ""


def _flag(grounded: bool) -> str:
    return "" if grounded else " _(unverified)_"


def to_markdown(exp: LLMExplanation, pkg: EvidencePackage, warnings: list[str]) -> str:
    md = [f"## {pkg.method_title}", "", exp.summary + (" _(purpose inferred from code)_" if exp.purpose_is_inferred else "")]
    if exp.inputs_outputs:
        md += ["", "### Inputs and outputs"]
        md += [f"- **{io.role}** `{io.name}`: {io.description}" for io in exp.inputs_outputs]
    if exp.execution_steps:
        md += ["", "### Execution flow"]
        for s in exp.execution_steps:
            md.append(f"{s.step_number}. **{s.title}** ({s.certainty}){_refs(s.source_refs, pkg)}{_flag(s.grounded)}  ")
            md.append(f"   {s.description}")
    if exp.branches:
        md += ["", "### Branches and conditions"]
        for b in exp.branches:
            line = f"- **IF** `{b.condition}` **THEN** {b.when_true}"
            if b.when_false:
                line += f" **ELSE** {b.when_false}"
            md.append(line + _refs(b.source_refs, pkg) + _flag(b.grounded))
    for title, group in (("Data transformations", exp.data_transformations), ("Side effects", exp.side_effects),
                         ("Exceptions and failure paths", exp.exceptions)):
        if group:
            md += ["", f"### {title}"] + [f"- {i.description}{_refs(i.source_refs, pkg)}{_flag(i.grounded)}" for i in group]
    if exp.calls:
        md += ["", "### Calls"]
        md += [f"- `{c.callee}` ({c.evidence_status.replace('_', ' ')}): {c.summary}{_refs(c.source_refs, pkg)}"
               for c in exp.calls]
    notes = list(exp.uncertainties) + list(warnings)
    if notes:
        md += ["", "### Uncertainties and warnings"] + [f"- {n}" for n in notes]
    return "\n".join(md)
