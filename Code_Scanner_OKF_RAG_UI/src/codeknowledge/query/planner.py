"""Turn a classification into an explicit, inspectable retrieval plan."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from codeknowledge.models.query import QueryCategory as C
from codeknowledge.query.classifier import Classification


class StepType(str, Enum):
    SYMBOL_LOOKUP = "SYMBOL_LOOKUP"
    SEMANTIC_SEARCH = "SEMANTIC_SEARCH"
    IDENTIFY_TARGET = "IDENTIFY_TARGET"
    GRAPH_REVERSE = "GRAPH_REVERSE"
    GRAPH_FORWARD = "GRAPH_FORWARD"
    GRAPH_EXPAND = "GRAPH_EXPAND"
    GRAPH_PATH = "GRAPH_PATH"
    INHERITANCE = "INHERITANCE"
    FLOW = "FLOW"
    RULES = "RULES"
    BUILD_CONTEXT = "BUILD_CONTEXT"
    LLM = "LLM"


class PlanStep(BaseModel):
    type: StepType
    description: str
    params: dict = Field(default_factory=dict)


class QueryPlan(BaseModel):
    category: C
    steps: list[PlanStep]
    requires_llm: bool
    graph_depth: int
    prompt_kind: str | None = None  # functional | technical | flow | business_rule | general

    def has(self, t: StepType) -> bool:
        return any(s.type == t for s in self.steps)

    def step(self, t: StepType) -> PlanStep | None:
        return next((s for s in self.steps if s.type == t), None)

    def describe(self) -> list[str]:
        return [f"{i}. {s.description}" for i, s in enumerate(self.steps, 1)]


# Categories answerable purely from the graph (LLM only when explanation is asked).
DETERMINISTIC = {C.CALLERS, C.CALLEES, C.DEPENDENCIES, C.IMPACT_ANALYSIS, C.PATH,
                 C.CLASS_LOOKUP, C.METHOD_LOOKUP, C.SEMANTIC_SEARCH}

REL_TYPES = {
    C.CALLERS: ["CALLS"],
    C.CALLEES: ["CALLS"],
    C.DEPENDENCIES: ["DEPENDS_ON", "USES", "CALLS", "EXTENDS", "IMPLEMENTS"],
    C.IMPACT_ANALYSIS: ["DEPENDS_ON", "USES", "CALLS", "EXTENDS", "IMPLEMENTS"],
}

PROMPT_KIND = {
    C.FUNCTIONAL_EXPLANATION: "functional",
    C.FLOW: "flow",
    C.BUSINESS_RULE: "business_rule",
    C.ARCHITECTURE: "architecture",
    C.GENERAL: "general",
}


class QueryPlanner:
    def __init__(self, max_depth: int):
        self.max_depth = max_depth

    def plan(self, cls: Classification, question: str) -> QueryPlan:
        cat = cls.category
        depth = self.max_depth if (cls.transitive or cat == C.IMPACT_ANALYSIS) else 1
        steps: list[PlanStep] = []

        if cls.symbols:
            steps.append(PlanStep(type=StepType.SYMBOL_LOOKUP, description="Exact symbol lookup",
                                  params={"symbols": cls.symbols}))
        else:
            steps.append(PlanStep(type=StepType.SEMANTIC_SEARCH, description=f"Semantic search for '{question}'"))
            steps.append(PlanStep(type=StepType.IDENTIFY_TARGET, description="Identify candidate entities from search hits"))

        if cat == C.CALLERS:
            steps.append(PlanStep(type=StepType.GRAPH_REVERSE, description=f"Graph reverse traversal over CALLS (depth {depth})",
                                  params={"rel_types": REL_TYPES[cat], "depth": depth}))
        elif cat == C.CALLEES:
            steps.append(PlanStep(type=StepType.GRAPH_FORWARD, description=f"Graph forward traversal over CALLS (depth {depth})",
                                  params={"rel_types": REL_TYPES[cat], "depth": depth}))
        elif cat in (C.DEPENDENCIES, C.IMPACT_ANALYSIS):
            reverse = cls.direction == "in"
            steps.append(PlanStep(
                type=StepType.GRAPH_REVERSE if reverse else StepType.GRAPH_FORWARD,
                description=f"Graph {'reverse' if reverse else 'forward'} traversal over dependency edges (depth {depth})",
                params={"rel_types": REL_TYPES[cat], "depth": depth}))
        elif cat == C.PATH:
            steps.append(PlanStep(type=StepType.GRAPH_PATH, description="Find shortest relationship path between the two entities"))
        elif cat in (C.CLASS_LOOKUP, C.METHOD_LOOKUP):
            steps.append(PlanStep(type=StepType.GRAPH_EXPAND, description="Expand direct relationships of the entity",
                                  params={"depth": 1}))
        elif cat == C.ARCHITECTURE:
            steps.append(PlanStep(type=StepType.GRAPH_EXPAND, description="Expand package/containment and inheritance structure",
                                  params={"depth": max(2, depth), "rel_types": ["CONTAINS", "EXTENDS", "IMPLEMENTS", "DEPENDS_ON"]}))
            steps.append(PlanStep(type=StepType.INHERITANCE, description="Collect inheritance/implementation relationships"))
        elif cat != C.SEMANTIC_SEARCH:
            steps.append(PlanStep(type=StepType.GRAPH_EXPAND, description="Expand graph around candidate entities",
                                  params={"depth": 1}))

        if cat in (C.FLOW, C.FUNCTIONAL_EXPLANATION, C.BUSINESS_RULE):
            steps.append(PlanStep(type=StepType.FLOW, description="Build execution flow for the target method(s)"))
        if cat == C.BUSINESS_RULE:
            steps.append(PlanStep(type=StepType.RULES, description="Extract IF/THEN/ELSE rule skeletons from flow"))

        requires_llm = cat not in DETERMINISTIC or cls.wants_explanation
        steps.append(PlanStep(type=StepType.BUILD_CONTEXT, description="Build evidence package (structured context)"))
        if requires_llm:
            steps.append(PlanStep(type=StepType.LLM, description="Send structured context to LLM for an evidence-based explanation"))
        return QueryPlan(category=cat, steps=steps, requires_llm=requires_llm, graph_depth=depth,
                         prompt_kind=PROMPT_KIND.get(cat, "technical" if cls.wants_explanation else None))
