"""Relationship queries on top of GraphStore (callers, callees, impact, inheritance)."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from codeknowledge.graph.store import LEAF_STATUSES, Direction, Edge, GraphStore

CALLS = {"CALLS"}
DEPENDENCY_TYPES = {"DEPENDS_ON", "USES", "CALLS", "EXTENDS", "IMPLEMENTS"}
INHERITANCE = {"EXTENDS", "IMPLEMENTS"}


@dataclass
class TraversalResult:
    root: str
    nodes: dict[str, int] = field(default_factory=dict)  # id -> depth
    edges: list[Edge] = field(default_factory=list)
    starts: set[str] = field(default_factory=set)  # root plus, for types, its members

    def ids(self, include_root: bool = False) -> list[str]:
        """Result entities; a class's own members are search seeds, not results."""
        return sorted((n for n in self.nodes if include_root or n not in (self.starts or {self.root})),
                      key=lambda n: (self.nodes[n], n))


class GraphTraversal:
    def __init__(self, store: GraphStore):
        self.store = store

    def _is_leaf(self, node_id: str) -> bool:
        return (self.store.get_node(node_id) or {}).get("status") in LEAF_STATUSES

    def _members(self, node_id: str) -> list[str]:
        """Methods of a class; class-level questions ("who calls ClaimService?") also
        need callers of the class's methods, not only edges on the class node."""
        return [e.target for e in self.store.edges(node_id, "out", {"CONTAINS"})
                if (self.store.get_node(e.target) or {}).get("type") == "method"]

    def walk(self, node_id: str, rel_types: set[str], direction: Direction, max_depth: int,
             include_members: bool = True) -> TraversalResult:
        result = TraversalResult(root=node_id)
        if not self.store.has_node(node_id):
            return result
        starts = [node_id] + (self._members(node_id) if include_members else [])
        result.nodes = {s: 0 for s in starts}
        result.starts = set(starts)
        queue = deque(starts)
        seen_edges: set[Edge] = set()
        while queue:
            cur = queue.popleft()
            if result.nodes[cur] >= max_depth or (cur != node_id and self._is_leaf(cur)):
                continue
            for e in self.store.edges(cur, direction, rel_types):
                if e in seen_edges:
                    continue
                seen_edges.add(e)
                result.edges.append(e)
                nxt = e.target if e.source == cur else e.source
                if nxt not in result.nodes:
                    result.nodes[nxt] = result.nodes[cur] + 1
                    queue.append(nxt)
        return result

    def callers(self, node_id: str, depth: int = 1) -> TraversalResult:
        return self.walk(node_id, CALLS, "in", depth)

    def callees(self, node_id: str, depth: int = 1) -> TraversalResult:
        return self.walk(node_id, CALLS, "out", depth)

    def dependencies(self, node_id: str, depth: int = 1) -> TraversalResult:
        return self.walk(node_id, DEPENDENCY_TYPES, "out", depth)

    def dependents(self, node_id: str, depth: int = 1) -> TraversalResult:
        return self.walk(node_id, DEPENDENCY_TYPES, "in", depth)

    def impact(self, node_id: str, depth: int) -> TraversalResult:
        """Everything that could break if node_id changes: transitive reverse dependencies."""
        return self.dependents(node_id, depth)

    def supertypes(self, node_id: str, depth: int = 5) -> TraversalResult:
        return self.walk(node_id, INHERITANCE, "out", depth, include_members=False)

    def subtypes(self, node_id: str, depth: int = 5) -> TraversalResult:
        return self.walk(node_id, INHERITANCE, "in", depth, include_members=False)

    def call_paths(self, source: str, target: str) -> list[str] | None:
        path = self.store.shortest_path(source, target, CALLS, directed=True)
        if path is None:
            path = self.store.shortest_path(source, target, None, directed=True)
        return path

    def reachable_call_chains(self, node_id: str, max_depth: int, include_external: bool = False) -> list[list[str]]:
        """All maximal call chains from node_id (DFS, cycle-safe), e.g. [[A, B, C]]."""
        chains: list[list[str]] = []

        def dfs(path: list[str]) -> None:
            nexts = [] if (len(path) > 1 and self._is_leaf(path[-1])) else [
                e.target for e in self.store.edges(path[-1], "out", CALLS)
                if e.target not in path and (include_external or not self._is_leaf(e.target))]
            if not nexts or len(path) > max_depth:
                chains.append(path)
                return
            for n in nexts:
                dfs(path + [n])

        if self.store.has_node(node_id):
            dfs([node_id])
        return chains
