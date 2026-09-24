"""Flow data structures (serialisable for the API/UI)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

StepKind = Literal["start", "call", "condition", "loop", "statement", "return", "throw", "merge", "end"]


class FlowNode(BaseModel):
    id: str
    kind: StepKind
    label: str
    entity_id: str | None = None  # set for call steps that resolve to a known entity
    status: str = "resolved"  # resolved | unresolved


class FlowEdge(BaseModel):
    source: str
    target: str
    label: str | None = None  # "yes" / "no" / "loop" / "next"


class Flow(BaseModel):
    root: str
    title: str
    # explicit: control flow described in OKF metadata; call_sequence: only CALLS
    # edges are known (order/conditions unknown); unavailable: nothing to show.
    availability: Literal["explicit", "call_sequence", "unavailable"]
    nodes: list[FlowNode] = Field(default_factory=list)
    edges: list[FlowEdge] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    call_chains: list[list[str]] = Field(default_factory=list)
    outline: list[str] = Field(default_factory=list)  # indented text built from the step structure

    def render_text(self) -> str:
        """Indented plain-text rendering for CLI and LLM context."""
        if self.outline:
            return "\n".join(self.outline)
        children: dict[str, list[FlowEdge]] = {}
        for e in self.edges:
            children.setdefault(e.source, []).append(e)
        by_id = {n.id: n for n in self.nodes}
        lines: list[str] = []
        visited: set[str] = set()

        def walk(nid: str, depth: int, label: str | None) -> None:
            n = by_id[nid]
            prefix = "  " * depth + (f"[{label}] " if label and label not in ("next",) else "")
            if nid in visited:
                if n.kind not in ("merge", "end"):
                    lines.append(prefix + f"(back to {n.label})")
                return
            visited.add(nid)
            if n.kind not in ("merge",):
                lines.append(prefix + f"{n.kind.upper()}: {n.label}")
            for e in children.get(nid, []):
                walk(e.target, depth + (1 if n.kind in ("condition", "loop") and e.label in ("yes", "no", "loop") else 0), e.label)

        start = next((n.id for n in self.nodes if n.kind == "start"), None)
        if start:
            walk(start, 0, None)
        return "\n".join(lines)
