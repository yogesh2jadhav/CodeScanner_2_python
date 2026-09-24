"""Derive business-rule candidates (IF/THEN/ELSE) from explicit flow metadata."""
from __future__ import annotations

from pydantic import BaseModel

from codeknowledge.flow.path import Flow


class RuleCandidate(BaseModel):
    entity_id: str
    condition: str
    then: list[str]
    otherwise: list[str]


def _branch_labels(flow: Flow, start: str, stop_kinds=("merge", "end")) -> list[str]:
    by_id = {n.id: n for n in flow.nodes}
    nexts: dict[str, list[str]] = {}
    for e in flow.edges:
        nexts.setdefault(e.source, []).append(e.target)
    out: list[str] = []
    cur, seen = start, set()
    while cur and cur not in seen:
        seen.add(cur)
        n = by_id[cur]
        if n.kind in stop_kinds:
            break
        out.append(n.label)
        nxt = nexts.get(cur, [])
        cur = nxt[0] if len(nxt) == 1 else None
    return out


def extract_rules(flow: Flow) -> list[RuleCandidate]:
    """Deterministic rule skeletons; the LLM may phrase them but must not invent new ones."""
    rules: list[RuleCandidate] = []
    for n in flow.nodes:
        if n.kind != "condition":
            continue
        yes = [e.target for e in flow.edges if e.source == n.id and e.label == "yes"]
        no = [e.target for e in flow.edges if e.source == n.id and e.label == "no"]
        rules.append(RuleCandidate(
            entity_id=flow.root,
            condition=n.label,
            then=_branch_labels(flow, yes[0]) if yes else [],
            otherwise=_branch_labels(flow, no[0]) if no else [],
        ))
    return rules
