"""Ask request/answer and evidence models."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from codeknowledge.flow.path import Flow
from codeknowledge.models.entities import EntitySummary


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    use_llm: bool = True
    use_cache: bool = True


class Evidence(BaseModel):
    entity_id: str
    title: str
    type: str
    document: str | None = None
    source: str | None = None
    source_line: int | None = None
    reason: str | None = None  # why it is evidence: target | CALLS <- X | semantic match ...
    cited: bool = False  # mentioned in the generated answer


class Fact(BaseModel):
    """A deterministic statement derived from the graph/OKF (never from the LLM)."""

    claim: str
    kind: Literal["fact"] = "fact"
    evidence: list[str] = Field(default_factory=list)  # entity ids


class RelationshipView(BaseModel):
    source: str
    target: str
    type: str
    status: str = "resolved"


class AskResponse(BaseModel):
    request_id: str
    question: str
    category: str
    confidence: float
    classification_method: str
    plan: list[str]
    target: str | None = None
    answer: str  # deterministic answer text (always present)
    facts: list[Fact] = Field(default_factory=list)
    interpretation: str | None = None  # LLM output, labelled as AI interpretation
    evidence: list[Evidence] = Field(default_factory=list)
    related_entities: list[EntitySummary] = Field(default_factory=list)
    relationships: list[RelationshipView] = Field(default_factory=list)
    paths: list[list[str]] = Field(default_factory=list)
    flow: Flow | None = None
    llm_used: bool = False
    llm_model: str | None = None
    llm_error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    timings_ms: dict[str, float] = Field(default_factory=dict)
    cached: bool = False
    knowledge_base_version: str | None = None
