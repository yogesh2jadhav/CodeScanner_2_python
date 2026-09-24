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
                        # Package nodes are synthesised from class metadata; anything else
                        # missing is a placeholder for an unresolved reference.
                        is_pkg = rel.type.value == "CONTAINS" and end == rel.source and rel.status == "resolved"
                        self.store.add_node(
                            end,
                            label=end if is_pkg else short_name(end),
                            type=EntityType.PACKAGE.value if is_pkg else EntityType.UNRESOLVED.value,
                            package=end if is_pkg else None,
                            status="resolved" if is_pkg else "unresolved",
                        )
                self.store.add_edge(rel.source, rel.target, rel.type.value, origin=rel.origin, status=rel.status)
        stats = self.store.stats()
        logger.info("Created %d nodes", stats["nodes"])
        logger.info("Created %d relationships", stats["edges"])
        return self.store
