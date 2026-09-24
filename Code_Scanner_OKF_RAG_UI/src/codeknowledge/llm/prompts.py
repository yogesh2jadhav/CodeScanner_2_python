"""Prompt templates.

Every template tells the model to use only the supplied context, to separate
verified facts from interpretation and to cite entity ids. The LLM is never asked
to discover relationships: those come from the graph/flow sections.
"""
from __future__ import annotations

from codeknowledge.models.query import QueryCategory
from codeknowledge.query.context_builder import StructuredContext

SYSTEM_PROMPT = """You are CodeKnowledgeAI, an assistant that explains a Java codebase.
Rules:
- Use ONLY the supplied context (entities, relationships, flow, rules, facts, source_documents).
- Never invent classes, methods, relationships, calls or business requirements that are not in the context.
- Reference entities by their id or title in backticks, e.g. `CasingService.processClaims`.
- Structure the answer with two sections:
  "### Verified facts" (statements directly supported by relationships/flow/facts) and
  "### Interpretation" (your inferred meaning, phrased as 'appears to' / 'likely').
- If the context is insufficient, say what is missing instead of guessing.
- Be concise."""

TASKS = {
    "functional": """Explain what the target accomplishes functionally.
Use only supplied evidence. Separate verified facts from inferred interpretation.
Do not invent business requirements.""",
    "technical": """Explain the implementation step-by-step.
Mention important calls, conditions and dependencies.""",
    "flow": """Explain the execution flow.
Describe branches explicitly (condition, yes-branch, no-branch). Reference the relevant methods.
If the flow availability is 'call_sequence' or 'unavailable', state that ordering/conditions are unknown.""",
    "business_rule": """Identify conditional rules expressed by the code.
For each rule provide:
IF condition
THEN outcome
ELSE outcome
Evidence (entity ids)
Use the 'rules' section as the authoritative list; do not add rules that are not present.""",
    "architecture": """Describe the architecture: packages, main classes, their responsibilities and how they relate
(containment, inheritance, dependencies). Use only the supplied relationships.""",
    "general": """Answer the question using only the supplied context.""",
}


def build_prompt(question: str, ctx: StructuredContext, kind: str | None) -> str:
    task = TASKS.get(kind or "general", TASKS["general"])
    return (
        f"Task:\n{task}\n\n"
        f"Question:\n{question}\n\n"
        f"Context (JSON):\n{ctx.to_prompt_json()}\n\n"
        "Answer:"
    )


def classification_prompt(question: str) -> str:
    cats = ", ".join(c.value for c in QueryCategory)
    return (
        "Classify the developer question about a Java codebase into exactly one category.\n"
        f"Categories: {cats}\n"
        f"Question: {question}\n"
        "Reply with the category name only."
    )
