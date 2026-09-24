"""Explorer: package/class/method tree and entity details."""
from __future__ import annotations

from codeknowledge.models.entities import EntitySummary, EntityType
from codeknowledge.okf.parser import MD_LINK_RE, resolve_link
from codeknowledge.retrieval.hybrid import entity_summary
from codeknowledge.services.indexing_service import KnowledgeBase

TYPE_ORDER = {EntityType.INTERFACE: 0, EntityType.CLASS: 1, EntityType.ENUM: 2}
DEFAULT_PACKAGE = "(default package)"


class EntityNotFoundError(KeyError):
    pass


class ExplorerService:
    def __init__(self, kb: KnowledgeBase):
        self.kb = kb

    def tree(self) -> list[dict]:
        self.kb.require_ready()
        repo, g = self.kb.repo, self.kb.graph
        packages: dict[str, dict] = {}
        types = [d for d in repo.documents if d.type in TYPE_ORDER]
        for d in sorted(types, key=lambda d: (TYPE_ORDER[d.type], d.display_name())):
            pkg = d.package or DEFAULT_PACKAGE
            node = packages.setdefault(pkg, {"id": pkg, "title": pkg, "type": "package",
                                             "has_document": pkg in repo.by_id, "children": []})
            methods = []
            for e in g.edges(d.id, "out", {"CONTAINS"}):
                m = repo.get(e.target)
                if m and m.type in (EntityType.METHOD, EntityType.FIELD):
                    methods.append({"id": m.id, "title": m.method_name or m.title, "type": m.type.value})
            node["children"].append({"id": d.id, "title": d.display_name(), "type": d.type.value,
                                     "children": sorted(methods, key=lambda m: m["title"])})
        others = [d for d in repo.documents
                  if d.type in (EntityType.DOCUMENT, EntityType.MODULE)]
        tree = [packages[k] for k in sorted(packages)]
        if others:
            tree.append({"id": "(documents)", "title": "Other documents", "type": "group", "has_document": False,
                         "children": [{"id": d.id, "title": d.title, "type": d.type.value, "children": []}
                                      for d in sorted(others, key=lambda d: d.title)]})
        return tree

    def entity(self, entity_id: str) -> dict:
        self.kb.require_ready()
        repo, g = self.kb.repo, self.kb.graph
        doc = repo.get(entity_id)
        if doc is None and not g.has_node(entity_id):
            raise EntityNotFoundError(entity_id)
        summary: EntitySummary = entity_summary(repo, g, entity_id)
        data = {"entity": summary.model_dump(mode="json"), "content": None, "signature": None,
                "metadata": {}, "flow_available": False, "owner": None, "members": [], "link_targets": {}}
        if doc:
            meta = {k: v for k, v in doc.metadata.items() if k not in ("flow",)}
            data.update(content=doc.content, signature=doc.signature, metadata=meta,
                        flow_available=bool(doc.metadata.get("flow")) or bool(g.edges(entity_id, "out", {"CALLS"})),
                        link_targets=self._link_targets(doc))
        for e in g.edges(entity_id, "in", {"CONTAINS"}):
            data["owner"] = entity_summary(repo, g, e.source).model_dump(mode="json")
        data["members"] = [entity_summary(repo, g, e.target).model_dump(mode="json")
                           for e in g.edges(entity_id, "out", {"CONTAINS"})]
        return data

    def _link_targets(self, doc) -> dict[str, str]:
        """Map relative Markdown hrefs in the document to entity ids, so the UI can make
        OKF cross-links navigable without exposing or fetching file paths."""
        out: dict[str, str] = {}
        for _text, href in MD_LINK_RE.findall(doc.content):
            resolved = resolve_link(doc.path, href)
            target = self.kb.repo.by_path.get(resolved) if resolved else None
            if target:
                out[href] = target.id
        return out

    def relationships(self, entity_id: str) -> dict:
        self.kb.require_ready()
        g = self.kb.graph
        if not g.has_node(entity_id):
            raise EntityNotFoundError(entity_id)
        out = [{**e.to_dict(), "other": entity_summary(self.kb.repo, g, e.target).model_dump(mode="json")}
               for e in g.edges(entity_id, "out")]
        inc = [{**e.to_dict(), "other": entity_summary(self.kb.repo, g, e.source).model_dump(mode="json")}
               for e in g.edges(entity_id, "in")]
        return {"entity_id": entity_id, "outgoing": out, "incoming": inc}
