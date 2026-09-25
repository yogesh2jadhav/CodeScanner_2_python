"""Typed contracts for method explanation: options, evidence, LLM output, API response."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EvidenceKind = Literal[
    "method_metadata",   # signature, parameters, return, throws, location (from OKF)
    "method_source",     # selected method body with line numbers (from source.root_dir)
    "source_segment",    # ordered part of an oversized selected method body
    "class_metadata",    # declaring type (from OKF)
    "field",             # class field/constant referenced by the method (from source)
    "call",              # a call made by the method: target, status, call-site lines (from OKF)
    "callee_source",     # a called method's body (from source), within depth
    "callee_signature",  # a called method whose body is not available (interface, abstract, missing source)
    "caller",            # a method that calls the selected one (optional)
    "sql_literal",       # string literal that looks like SQL (from source)
]
EvidenceStatus = Literal["resolved", "unresolved", "ambiguous", "external", "unavailable"]
Certainty = Literal["observed", "derived", "unknown"]
CallEvidenceStatus = Literal["body_inspected", "signature_only", "unresolved", "external"]


class ExplainOptions(BaseModel):
    """Request options; None means "use the configured default"."""

    detail: Literal["detailed", "summary"] = "detailed"
    max_callee_depth: int | None = Field(default=None, ge=0, le=3)
    include_caller_context: bool | None = None
    include_related_config: bool | None = None
    include_sql_evidence: bool | None = None
    force_refresh: bool = False


class EvidenceItem(BaseModel):
    evidence_id: str  # "E1", "E2", ... stable for a given bundle/source/options
    kind: EvidenceKind
    title: str
    entity_id: str | None = None
    file: str | None = None  # project-relative (OKF `resource`), never absolute
    start_line: int | None = None
    end_line: int | None = None
    status: EvidenceStatus = "resolved"
    depth: int = 0  # 0 = selected method, 1 = direct callee, ...
    priority: int = 9  # lower is kept first when the budget is tight
    content: str = ""  # numbered code or short text
    lines: list[int] = Field(default_factory=list)  # call-site lines for kind=call

    def covers(self, start: int, end: int) -> bool:
        if self.start_line is None or self.end_line is None:
            return bool(self.lines) and all(ln in self.lines for ln in range(start, end + 1))
        return self.start_line <= start <= end <= self.end_line


class EvidencePackage(BaseModel):
    method_id: str
    method_signature: str
    method_title: str
    source_available: bool
    items: list[EvidenceItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    omitted: list[str] = Field(default_factory=list)  # evidence dropped by the budget, with reason
    segments: int = 1  # >1 when the selected body is explained in ordered parts
    estimated_tokens: int = 0

    def get(self, evidence_id: str) -> EvidenceItem | None:
        return next((i for i in self.items if i.evidence_id == evidence_id), None)


# ------------------------------------------------------------- LLM output

class SourceRef(BaseModel):
    evidence_id: str
    start_line: int
    end_line: int


class ExplanationStep(BaseModel):
    step_number: int
    title: str
    description: str
    source_refs: list[SourceRef] = Field(default_factory=list)
    certainty: Certainty = "observed"
    grounded: bool = True  # set by the validator; False = no verified source reference


class Branch(BaseModel):
    condition: str
    when_true: str
    when_false: str | None = None
    source_refs: list[SourceRef] = Field(default_factory=list)
    grounded: bool = True


class DescribedItem(BaseModel):
    description: str
    source_refs: list[SourceRef] = Field(default_factory=list)
    grounded: bool = True


class InputOutput(BaseModel):
    name: str
    role: Literal["input", "output", "exception", "side_effect"]
    description: str


class CallExplanation(BaseModel):
    callee: str  # entity id or the call text from evidence
    evidence_status: CallEvidenceStatus
    summary: str
    source_refs: list[SourceRef] = Field(default_factory=list)
    grounded: bool = True


class LLMExplanation(BaseModel):
    """The structure the model must return (also sent to Ollama as the JSON schema)."""

    summary: str
    purpose_is_inferred: bool = True
    inputs_outputs: list[InputOutput] = Field(default_factory=list)
    execution_steps: list[ExplanationStep] = Field(default_factory=list)
    branches: list[Branch] = Field(default_factory=list)
    data_transformations: list[DescribedItem] = Field(default_factory=list)
    calls: list[CallExplanation] = Field(default_factory=list)
    side_effects: list[DescribedItem] = Field(default_factory=list)
    exceptions: list[DescribedItem] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


# ------------------------------------------------------------ API response

class ValidationReport(BaseModel):
    valid: bool
    repair_attempts: int = 0
    invalid_refs_removed: int = 0
    ungrounded_items: int = 0
    corrected_call_statuses: int = 0
    errors: list[str] = Field(default_factory=list)


class ModelMetadata(BaseModel):
    provider: str
    model: str
    prompt_version: str
    num_ctx: int | None = None


class DeterministicFacts(BaseModel):
    """Facts computed without the LLM, shown even when generation fails."""

    comments: list[dict] = Field(default_factory=list)
    conditions: list[dict] = Field(default_factory=list)
    calls: list[dict] = Field(default_factory=list)


class MethodExplanationResponse(BaseModel):
    request_id: str
    method_id: str
    method_signature: str
    method_title: str
    explanation: LLMExplanation | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    facts: DeterministicFacts = Field(default_factory=DeterministicFacts)
    warnings: list[str] = Field(default_factory=list)
    validation: ValidationReport | None = None
    model: ModelMetadata | None = None
    cached: bool = False
    timings_ms: dict[str, float] = Field(default_factory=dict)
    estimated_prompt_tokens: int = 0
    markdown: str = ""  # rendered from the validated explanation (for copy/Ask)
