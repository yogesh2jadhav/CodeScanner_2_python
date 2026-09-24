"""Query/search request and response models."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from codeknowledge.models.entities import EntitySummary


class QueryCategory(str, Enum):
    CLASS_LOOKUP = "CLASS_LOOKUP"
    METHOD_LOOKUP = "METHOD_LOOKUP"
    SEMANTIC_SEARCH = "SEMANTIC_SEARCH"
    CALLERS = "CALLERS"
    CALLEES = "CALLEES"
    DEPENDENCIES = "DEPENDENCIES"
    IMPACT_ANALYSIS = "IMPACT_ANALYSIS"
    FLOW = "FLOW"
    PATH = "PATH"
    FUNCTIONAL_EXPLANATION = "FUNCTIONAL_EXPLANATION"
    BUSINESS_RULE = "BUSINESS_RULE"
    ARCHITECTURE = "ARCHITECTURE"
    GENERAL = "GENERAL"


SearchMode = Literal["hybrid", "symbol", "semantic"]


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=100)
    mode: SearchMode = "hybrid"
    entity_type: str | None = None
    package: str | None = None
    expand_graph: bool = True


class SearchHit(BaseModel):
    entity: EntitySummary
    score: float
    match_types: list[str]  # symbol | semantic | graph
    matched_on: str | None = None  # e.g. method_name, fqn, via CALLS from X


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    hits: list[SearchHit]
    warnings: list[str] = Field(default_factory=list)
    timings_ms: dict[str, float] = Field(default_factory=dict)
