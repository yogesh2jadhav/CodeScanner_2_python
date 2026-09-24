"""Score fusion for hybrid retrieval.

Why a simple weighted max instead of a learned reranker: it is deterministic,
explainable (each hit reports which signal matched) and needs no extra model.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SYMBOL_WEIGHT = 1.0
SEMANTIC_WEIGHT = 0.8
AGREEMENT_BONUS = 0.1  # found by both symbol and semantic search
GRAPH_DECAY = 0.5


@dataclass
class Candidate:
    entity_id: str
    score: float = 0.0
    match_types: list[str] = field(default_factory=list)
    matched_on: str | None = None


class Reranker:
    def __init__(self) -> None:
        self.cands: dict[str, Candidate] = {}

    def _get(self, eid: str) -> Candidate:
        return self.cands.setdefault(eid, Candidate(eid))

    def add(self, eid: str, raw_score: float, match_type: str, matched_on: str | None = None) -> None:
        weight = {"symbol": SYMBOL_WEIGHT, "semantic": SEMANTIC_WEIGHT, "graph": 1.0}[match_type]
        c = self._get(eid)
        score = raw_score * weight
        if match_type not in c.match_types:
            c.match_types.append(match_type)
            if {"symbol", "semantic"} <= set(c.match_types) and match_type in ("symbol", "semantic"):
                score += AGREEMENT_BONUS
        if score > c.score:
            c.score = round(score, 4)
            c.matched_on = matched_on or c.matched_on
        elif c.matched_on is None:
            c.matched_on = matched_on

    def ranked(self) -> list[Candidate]:
        return sorted(self.cands.values(), key=lambda c: (-c.score, c.entity_id))
