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
    "overrides": {"OVERRIDES"},
}
MAX_SUBGRAPH_DEPTH = 6
MAX_SUBGRAPH_NODES = 300


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

    def _visible(self, nid: str, include_external: bool) -> bool:
        return include_external or (self.kb.graph.get_node(nid) or {}).get("status") != "external"

    def neighbors(self, nid: str, direction: str = "both", types: str | None = None,
                  include_external: bool = False) -> dict:
        self.kb.require_ready()
        if not self.kb.graph.has_node(nid):
            raise EntityNotFoundError(nid)
        edges = [e for e in self.kb.graph.edges(nid, direction, parse_types(types))
                 if self._visible(e.source, include_external) and self._visible(e.target, include_external)]
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

    def subgraph(self, nid: str, depth: int = 2, types: str | None = None, direction: str = "both",
                 include_external: bool = False, max_nodes: int = MAX_SUBGRAPH_NODES) -> dict:
        self.kb.require_ready()
        if not self.kb.graph.has_node(nid):
            raise EntityNotFoundError(nid)
        depth = max(0, min(depth, MAX_SUBGRAPH_DEPTH))  # bound work for huge graphs
        sg = self.kb.graph.subgraph(nid, depth, parse_types(types), direction)
        # External (JDK/library) leaves are hidden by default: on a real bundle they
        # outnumber project classes and bury the structure the user is looking for.
        nodes = [n for n in sg.nodes if n["id"] == nid or self._visible(n["id"], include_external)]
        hidden_external = len(sg.nodes) - len(nodes)
        # Cap the node count (closest first) so the browser can render the result.
        nodes.sort(key=lambda n: (n.get("depth", 0), n["id"]))
        truncated = len(nodes) > max_nodes
        nodes = nodes[:max_nodes]
        keep = {n["id"] for n in nodes}
        edges = [e.to_dict() for e in sg.edges if e.source in keep and e.target in keep]
        return {"root": nid, "depth": depth, "nodes": nodes, "edges": edges,
                "hidden_external": hidden_external, "truncated": truncated}
