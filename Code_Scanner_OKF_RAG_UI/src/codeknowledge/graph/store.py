"""GraphStore abstraction.

Why an abstract store: v1 runs on in-process NetworkX (zero infrastructure), but
large codebases may later need Neo4j. Services only talk to this interface, so a
Neo4jGraphStore can be added without touching retrieval, flow or API code.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal

Direction = Literal["out", "in", "both"]

# Nodes that are never expanded during traversal. Why: an external type such as
# java.lang.String is used by almost every class; walking *through* it would join
# unrelated code into one giant neighbourhood.
LEAF_STATUSES = frozenset({"external", "unresolved"})


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    type: str
    attrs: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "target": self.target, "type": self.type, **self.attrs}


@dataclass
class SubGraph:
    nodes: list[dict[str, Any]]
    edges: list[Edge]

    def to_dict(self) -> dict[str, Any]:
        return {"nodes": self.nodes, "edges": [e.to_dict() for e in self.edges]}


class GraphStore(ABC):
    @abstractmethod
    def clear(self) -> None: ...

    @abstractmethod
    def add_node(self, node_id: str, **attrs: Any) -> None: ...

    @abstractmethod
    def add_edge(self, source: str, target: str, rel_type: str, **attrs: Any) -> None: ...

    @abstractmethod
    def has_node(self, node_id: str) -> bool: ...

    @abstractmethod
    def get_node(self, node_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def nodes(self) -> Iterable[dict[str, Any]]: ...

    @abstractmethod
    def edges(self, node_id: str, direction: Direction = "both", rel_types: set[str] | None = None) -> list[Edge]: ...

    @abstractmethod
    def shortest_path(self, source: str, target: str, rel_types: set[str] | None = None,
                      directed: bool = True) -> list[str] | None: ...

    @abstractmethod
    def subgraph(self, node_id: str, depth: int, rel_types: set[str] | None = None,
                 direction: Direction = "both") -> SubGraph: ...

    @abstractmethod
    def stats(self) -> dict[str, int]: ...

    @abstractmethod
    def save(self, directory: str, meta: dict[str, Any]) -> None: ...

    @abstractmethod
    def load(self, directory: str) -> dict[str, Any] | None:
        """Load a persisted graph; returns its meta or None when nothing is persisted."""
