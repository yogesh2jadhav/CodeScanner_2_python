"""Structured, bounded LLM context.

Why structured instead of "dump the retrieved Markdown": the LLM must only
explain facts that the analyzer found. Giving it explicit entity, relationship
and flow sections (plus trimmed excerpts) keeps prompts small, makes every
statement traceable to an entity id, and lets us enforce hard budgets.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from codeknowledge.flow.path import Flow
from codeknowledge.models.answers import Evidence, RelationshipView
from codeknowledge.okf.repository import OKFRepository

CHARS_PER_TOKEN = 4  # rough heuristic; avoids a tokenizer dependency
EXCERPT_CHARS = 1200

# Lower = higher priority when the budget is tight.
PRIORITY = {"target": 0, "path": 1, "graph": 2, "flow": 2, "semantic": 3, "symbol": 3}


class ContextEntity(BaseModel):
    id: str
    title: str
    type: str
    package: str | None = None
    signature: str | None = None
    summary: str | None = None
    source: str | None = None
    source_line: int | None = None


class SourceDocument(BaseModel):
    entity_id: str
    document: str
    excerpt: str


class StructuredContext(BaseModel):
    target: str | None
    question: str
    category: str
    entities: list[ContextEntity] = Field(default_factory=list)
    relationships: list[RelationshipView] = Field(default_factory=list)
    flow: list[str] = Field(default_factory=list)
    rules: list[dict] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    source_documents: list[SourceDocument] = Field(default_factory=list)
    truncated: bool = False

    def to_prompt_json(self) -> str:
        data = self.model_dump(exclude={"evidence", "question"})
        return json.dumps(data, indent=1, default=str)

    def estimated_tokens(self) -> int:
        return len(self.to_prompt_json()) // CHARS_PER_TOKEN


@dataclass
class _Candidate:
    entity_id: str
    score: float
    origin: str
    reason: str


@dataclass
class ContextBuilder:
    repo: OKFRepository
    max_documents: int
    max_tokens: int
    candidates: dict[str, _Candidate] = field(default_factory=dict)
    relationships: list[RelationshipView] = field(default_factory=list)
    flows: list[Flow] = field(default_factory=list)
    rules: list[dict] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)

    def add_entity(self, entity_id: str, score: float, origin: str, reason: str) -> None:
        """Duplicate removal: keep the best (priority, score) occurrence of each entity."""
        cur = self.candidates.get(entity_id)
        new = _Candidate(entity_id, score, origin, reason)
        if cur is None or (PRIORITY.get(origin, 9), -score) < (PRIORITY.get(cur.origin, 9), -cur.score):
            self.candidates[entity_id] = new

    def add_relationship(self, source: str, target: str, rel_type: str, status: str = "resolved") -> None:
        rv = RelationshipView(source=source, target=target, type=rel_type, status=status)
        if rv not in self.relationships:
            self.relationships.append(rv)

    def add_flow(self, flow: Flow) -> None:
        self.flows.append(flow)
        for n in flow.nodes:
            if n.entity_id:
                self.add_entity(n.entity_id, 0.7, "flow", f"step in flow of {flow.title}")

    def ranked(self) -> list[_Candidate]:
        return sorted(self.candidates.values(), key=lambda c: (PRIORITY.get(c.origin, 9), -c.score, c.entity_id))

    def build(self, question: str, category: str, target: str | None) -> StructuredContext:
        ctx = StructuredContext(target=target, question=question, category=category,
                                relationships=list(self.relationships), rules=list(self.rules), facts=list(self.facts))
        for f in self.flows:
            head = f"Flow of {f.title} (availability: {f.availability})"
            body = f.render_text() if f.nodes else "; ".join(f.notes)
            ctx.flow.append(head + "\n" + body)
            if f.call_chains:
                ctx.flow.append("Call chains: " + " | ".join(" -> ".join(c) for c in f.call_chains[:10]))

        budget_chars = self.max_tokens * CHARS_PER_TOKEN
        for cand in self.ranked():
            if len(ctx.entities) >= self.max_documents:
                ctx.truncated = True
                break
            doc = self.repo.get(cand.entity_id)
            if doc is None:
                ctx.entities.append(ContextEntity(id=cand.entity_id, title=cand.entity_id, type="unresolved"))
                continue
            ctx.entities.append(ContextEntity(
                id=doc.id, title=doc.display_name(), type=doc.type.value, package=doc.package,
                signature=doc.signature, summary=doc.summary, source=doc.source_file, source_line=doc.source_line))
            ctx.evidence.append(Evidence(entity_id=doc.id, title=doc.display_name(), type=doc.type.value,
                                         document=doc.path, source=doc.source_file, source_line=doc.source_line,
                                         reason=cand.reason))
            excerpt = doc.content[:EXCERPT_CHARS]
            if excerpt and len(ctx.to_prompt_json()) + len(excerpt) < budget_chars:
                ctx.source_documents.append(SourceDocument(entity_id=doc.id, document=doc.path, excerpt=excerpt))
            elif excerpt:
                ctx.truncated = True

        # Hard token cap: drop excerpts, then trailing relationships, until we fit.
        while ctx.estimated_tokens() > self.max_tokens and ctx.source_documents:
            ctx.source_documents.pop()
            ctx.truncated = True
        while ctx.estimated_tokens() > self.max_tokens and len(ctx.relationships) > 1:
            ctx.relationships.pop()
            ctx.truncated = True
        return ctx
