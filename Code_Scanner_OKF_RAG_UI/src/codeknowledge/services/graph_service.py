"""Graph API service (node, neighbours, path, subgraph) with UI-friendly filters."""
from __future__ import annotations

from codeknowledge.retrieval.hybrid import entity_summary
from codeknowledge.services.explorer_service import EntityNotFoundError
from codeknowledge.services.indexing_service import KnowledgeBase

# UI filter names -> relationship types
FILTERS = {
    "calls": {"CALLS"},
    "dependencies": {"DEPENDS_ON"},
    "inheritance": {"EXTENDS"},
    "implements": {"IMPLEMENTS"},
    "uses": {"USES"},
    "contains": {"CONTAINS", "BELONGS_TO"},
    "references": {"REFERENCES"},
}
MAX_SUBGRAPH_DEPTH = 6


def parse_types(types: str | None) -> set[str] | None:
    """Accept UI filter names (calls, inheritance…) or raw types (CALLS, EXTENDS…), comma-separated."""
    if not types:
        return None
    out: set[str] = set()
    for t in (x.strip() for x in types.split(",") if x.strip()):
        out |= FILTERS.get(t.lower(), {t.upper()})
    return out


class GraphService:
    def __init__(self, kb: KnowledgeBase):
        self.kb = kb

    def _node(self, nid: str) -> dict:
        n = self.kb.graph.get_node(nid) or {"id": nid}
        return {**n, "label": n.get("label", nid)}

    def node(self, nid: str) -> dict:
        self.kb.require_ready()
        if not self.kb.graph.has_node(nid):
            raise EntityNotFoundError(nid)
        return {"node": self._node(nid), "entity": entity_summary(self.kb.repo, self.kb.graph, nid).model_dump(mode="json"),
                "degree": {"in": len(self.kb.graph.edges(nid, "in")), "out": len(self.kb.graph.edges(nid, "out"))}}

    def neighbors(self, nid: str, direction: str = "both", types: str | None = None) -> dict:
        self.kb.require_ready()
        if not self.kb.graph.has_node(nid):
            raise EntityNotFoundError(nid)
        edges = self.kb.graph.edges(nid, direction, parse_types(types))
        ids = {nid} | {e.source for e in edges} | {e.target for e in edges}
        return {"nodes": [self._node(i) for i in sorted(ids)], "edges": [e.to_dict() for e in edges]}

    def path(self, source: str, target: str, types: str | None = None, directed: bool = True) -> dict:
        self.kb.require_ready()
        for n in (source, target):
            if not self.kb.graph.has_node(n):
                raise EntityNotFoundError(n)
        path = self.kb.graph.shortest_path(source, target, parse_types(types), directed)
        if not path:
            return {"found": False, "path": [], "nodes": [], "edges": []}
        edges = []
        for a, b in zip(path, path[1:]):
            es = [e for e in self.kb.graph.edges(a, "both") if {e.source, e.target} == {a, b}]
            edges.extend(e.to_dict() for e in es[:1])
        return {"found": True, "path": path, "nodes": [self._node(n) for n in path], "edges": edges}

    def subgraph(self, nid: str, depth: int = 2, types: str | None = None, direction: str = "both") -> dict:
        self.kb.require_ready()
        if not self.kb.graph.has_node(nid):
            raise EntityNotFoundError(nid)
        depth = max(0, min(depth, MAX_SUBGRAPH_DEPTH))  # bound work for huge graphs
        sg = self.kb.graph.subgraph(nid, depth, parse_types(types), direction)
        return {"root": nid, "depth": depth, **sg.to_dict()}
