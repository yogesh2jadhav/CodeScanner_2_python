"""NetworkX implementation of GraphStore."""
from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any, Iterable

import networkx as nx

from codeknowledge.graph.store import LEAF_STATUSES, Direction, Edge, GraphStore, SubGraph

GRAPH_FILE = "graph.json"


class NetworkXGraphStore(GraphStore):
    def __init__(self) -> None:
        # MultiDiGraph: two entities can be linked by several relationship types
        # (e.g. CALLS and USES); a plain DiGraph would silently overwrite one.
        self.g = nx.MultiDiGraph()
        self._path_ends: set[str] = set()

    def clear(self) -> None:
        self.g.clear()

    def add_node(self, node_id: str, **attrs: Any) -> None:
        if node_id in self.g:
            self.g.nodes[node_id].update(attrs)
        else:
            self.g.add_node(node_id, id=node_id, **attrs)

    def add_edge(self, source: str, target: str, rel_type: str, **attrs: Any) -> None:
        for n in (source, target):
            if n not in self.g:
                self.g.add_node(n, id=n)
        self.g.add_edge(source, target, key=rel_type, type=rel_type, **attrs)

    def has_node(self, node_id: str) -> bool:
        return node_id in self.g

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        return dict(self.g.nodes[node_id]) if node_id in self.g else None

    def nodes(self) -> Iterable[dict[str, Any]]:
        return (dict(d) for _, d in self.g.nodes(data=True))

    def _edge(self, u: str, v: str, data: dict[str, Any]) -> Edge:
        attrs = {k: val for k, val in data.items() if k != "type"}
        return Edge(u, v, data["type"], attrs)

    def edges(self, node_id: str, direction: Direction = "both", rel_types: set[str] | None = None) -> list[Edge]:
        if node_id not in self.g:
            return []
        out: list[Edge] = []
        if direction in ("out", "both"):
            out += [self._edge(u, v, d) for u, v, d in self.g.out_edges(node_id, data=True)]
        if direction in ("in", "both"):
            out += [self._edge(u, v, d) for u, v, d in self.g.in_edges(node_id, data=True)]
        if rel_types:
            out = [e for e in out if e.type in rel_types]
        return sorted(out, key=lambda e: (e.type, e.source, e.target))

    def _view(self, rel_types: set[str] | None) -> nx.MultiDiGraph:
        # Paths may end at, but never pass through, external/unresolved nodes.
        def node_ok(n: str) -> bool:
            return self.g.nodes[n].get("status") not in LEAF_STATUSES or n in self._path_ends

        def edge_ok(u: str, v: str, k: str) -> bool:
            return not rel_types or k in rel_types

        return nx.subgraph_view(self.g, filter_node=node_ok, filter_edge=edge_ok)

    def shortest_path(self, source: str, target: str, rel_types: set[str] | None = None,
                      directed: bool = True) -> list[str] | None:
        if source not in self.g or target not in self.g:
            return None
        self._path_ends = {source, target}
        view = self._view(rel_types)
        if not directed:
            view = view.to_undirected(as_view=True)
        try:
            return nx.shortest_path(view, source, target)
        except nx.NetworkXNoPath:
            return None

    def subgraph(self, node_id: str, depth: int, rel_types: set[str] | None = None,
                 direction: Direction = "both") -> SubGraph:
        if node_id not in self.g:
            return SubGraph([], [])
        seen = {node_id: 0}
        edges: set[Edge] = set()
        queue = deque([node_id])
        while queue:
            current = queue.popleft()
            if seen[current] >= depth:
                continue
            if current != node_id and self.g.nodes[current].get("status") in LEAF_STATUSES:
                continue
            for e in self.edges(current, direction, rel_types):
                edges.add(e)
                nxt = e.target if e.source == current else e.source
                if nxt not in seen:
                    seen[nxt] = seen[current] + 1
                    queue.append(nxt)
        nodes = [{**self.g.nodes[n], "depth": d} for n, d in seen.items()]
        # Keep edges between visited nodes only, sorted for deterministic output.
        edge_list = sorted((e for e in edges if e.source in seen and e.target in seen),
                           key=lambda e: (e.source, e.target, e.type))
        return SubGraph(nodes, edge_list)

    def stats(self) -> dict[str, int]:
        return {"nodes": self.g.number_of_nodes(), "edges": self.g.number_of_edges()}

    def save(self, directory: str, meta: dict[str, Any]) -> None:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        data = {
            "meta": meta,
            "nodes": [dict(d) for _, d in self.g.nodes(data=True)],
            "edges": [{"source": u, "target": v, **d} for u, v, d in self.g.edges(data=True)],
        }
        tmp = path / (GRAPH_FILE + ".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(path / GRAPH_FILE)  # atomic swap so readers never see a half-written file

    def load(self, directory: str) -> dict[str, Any] | None:
        file = Path(directory) / GRAPH_FILE
        if not file.is_file():
            return None
        data = json.loads(file.read_text(encoding="utf-8"))
        self.clear()
        for n in data["nodes"]:
            self.g.add_node(n["id"], **n)
        for e in data["edges"]:
            e = dict(e)
            u, v = e.pop("source"), e.pop("target")
            self.g.add_edge(u, v, key=e["type"], **e)
        return data.get("meta", {})
