from __future__ import annotations

from codeknowledge.flow.analyzer import extract_rules
from codeknowledge.services.explorer_service import EntityNotFoundError
from codeknowledge.services.indexing_service import KnowledgeBase


class FlowService:
    def __init__(self, kb: KnowledgeBase):
        self.kb = kb

    def flow(self, entity_id: str, depth: int | None = None) -> dict:
        self.kb.require_ready()
        flow = self.kb.flows.build(entity_id, depth or self.kb.settings.retrieval.graph_max_depth)
        if flow is None:
            raise EntityNotFoundError(entity_id)
        return {**flow.model_dump(mode="json"), "text": flow.render_text(),
                "rules": [r.model_dump() for r in extract_rules(flow)]}
