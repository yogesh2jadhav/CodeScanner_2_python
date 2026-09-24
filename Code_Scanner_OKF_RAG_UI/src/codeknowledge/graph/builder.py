"""Build the relationship graph from the OKF repository."""
from __future__ import annotations

from codeknowledge.graph.store import GraphStore
from codeknowledge.models.entities import EntityType, OKFDocument
from codeknowledge.okf.repository import OKFRepository
from codeknowledge.utils.ids import short_name
from codeknowledge.utils.logging import get_logger
from codeknowledge.utils.timing import timed

logger = get_logger("GraphBuilder")


def node_attrs(doc: OKFDocument) -> dict:
    return {
        "label": doc.display_name(),
        "type": doc.type.value,
        "package": doc.package,
        "class_name": doc.class_name,
        "method_name": doc.method_name,
        "document": doc.path,
        "source_file": doc.source_file,
        "source_line": doc.source_line,
        "status": "resolved",
    }


class GraphBuilder:
    def __init__(self, store: GraphStore):
        self.store = store

    def build(self, repo: OKFRepository) -> GraphStore:
        with timed(logger, "graph_build"):
            self.store.clear()
            for doc in repo.documents:
                self.store.add_node(doc.id, **node_attrs(doc))
            for rel in repo.relationships():
                for end in (rel.source, rel.target):
                    if not self.store.has_node(end):
                        # Package nodes are synthesised from class metadata; external targets
                        # (JDK/libraries) are leaves; anything else is an unresolved placeholder.
                        is_pkg = rel.type.value == "CONTAINS" and end == rel.source and rel.status == "resolved"
                        if is_pkg:
                            kind, status, label = EntityType.PACKAGE.value, "resolved", end
                        elif rel.status == "external":
                            kind, status, label = EntityType.EXTERNAL.value, "external", short_name(end)
                        else:
                            kind, status, label = EntityType.UNRESOLVED.value, "unresolved", short_name(end)
                        self.store.add_node(end, label=label, type=kind, package=end if is_pkg else None, status=status)
                attrs = {"origin": rel.origin, "status": rel.status}
                if rel.line is not None:
                    attrs["line"] = rel.line
                self.store.add_edge(rel.source, rel.target, rel.type.value, **attrs)
        external = sum(1 for n in self.store.nodes() if n.get("status") == "external")
        if external:
            logger.info("External (JDK/library) nodes: %d", external)
        stats = self.store.stats()
        logger.info("Created %d nodes", stats["nodes"])
        logger.info("Created %d relationships", stats["edges"])
        return self.store
