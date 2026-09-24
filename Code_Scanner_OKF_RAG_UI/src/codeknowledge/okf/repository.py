"""In-memory repository over a loaded OKF bundle with relationship resolution."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from codeknowledge.models.entities import EntityType, OKFDocument
from codeknowledge.models.relationships import Relationship, RelationType
from codeknowledge.okf.loader import LoadResult, OKFLoader
from codeknowledge.okf.parser import PATH_TARGET_PREFIX
from codeknowledge.utils.ids import base_name, strip_kind_prefix
from codeknowledge.utils.logging import get_logger

logger = get_logger("OKFRepository")


class OKFRepository:
    def __init__(self, load_result: LoadResult):
        self.load_result = load_result
        self.bundle_hash = load_result.bundle_hash
        self.report = load_result.report
        self.by_id: dict[str, OKFDocument] = {}
        self.by_path: dict[str, OKFDocument] = {}
        self.duplicates: dict[str, list[str]] = defaultdict(list)
        for doc in load_result.documents:
            self.by_path[doc.path] = doc
            if doc.id in self.by_id:
                # Why keep the first: deterministic across runs (files are sorted) and the
                # validator surfaces the conflict so the OKF author can fix the source.
                self.duplicates[doc.id].append(doc.path)
                continue
            self.by_id[doc.id] = doc
        # Lookup indexes are keyed on ids without kind prefix / parameter list so that
        # "OrderService.placeOrder" finds "java-method:com.x.OrderService.placeOrder(int)".
        self._suffix_index: dict[str, set[str]] = defaultdict(set)
        self._name_index: dict[str, set[str]] = defaultdict(set)
        self._qualified: dict[str, str] = {}
        self._by_base: dict[str, set[str]] = defaultdict(set)
        for doc_id, doc in self.by_id.items():
            if doc.navigation:
                continue
            qualified = strip_kind_prefix(doc_id)
            self._qualified.setdefault(qualified.lower(), doc_id)
            base = base_name(doc_id)
            self._by_base[base].add(doc_id)
            parts = base.split(".")
            for i in range(len(parts)):
                self._suffix_index[".".join(parts[i:]).lower()].add(doc_id)
            display = doc.display_name()
            for name in (doc.title, display, display.split("(", 1)[0]):
                self._name_index[name.lower()].add(doc_id)
        self._relationships: list[Relationship] | None = None

    @classmethod
    def from_directory(cls, source_dir: str | Path) -> "OKFRepository":
        return cls(OKFLoader(source_dir).load())

    @property
    def documents(self) -> list[OKFDocument]:
        return list(self.by_id.values())

    @property
    def content_documents(self) -> list[OKFDocument]:
        """Documents describing code entities (navigation Index/Log pages excluded)."""
        return [d for d in self.by_id.values() if not d.navigation]

    def get(self, entity_id: str) -> OKFDocument | None:
        return self.by_id.get(entity_id)

    def lookup(self, symbol: str) -> list[str]:
        """Ids matching a symbol by exact id, dotted suffix or name (case-insensitive)."""
        if symbol in self.by_id:
            return [symbol]
        key = symbol.strip().lower()
        if key in self._qualified:
            return [self._qualified[key]]
        hits = self._suffix_index.get(key, set()) | self._name_index.get(key, set())
        return sorted(hits)

    def resolve(self, target: str, source_id: str | None = None) -> str | None:
        if target.startswith(PATH_TARGET_PREFIX):
            doc = self.by_path.get(target[len(PATH_TARGET_PREFIX):])
            return doc.id if doc else None
        if target in self.by_id:
            return target
        qualified = self._qualified.get(strip_kind_prefix(target).lower())
        if qualified:
            return qualified
        # Why try the source's own prefixes first: an unqualified "getClaimData"
        # written inside CasingService most likely means CasingService.getClaimData.
        if source_id:
            parts = source_id.split(".")
            for i in range(len(parts), 0, -1):
                candidate = ".".join(parts[:i]) + "." + target
                if candidate in self.by_id:
                    return candidate
        hits = self._suffix_index.get(base_name(target).lower(), set())
        if len(hits) == 1:
            return next(iter(hits))
        return None

    def _type_id(self, qualified: str) -> str | None:
        for cand in self._by_base.get(qualified, ()):
            if self.by_id[cand].type in (EntityType.CLASS, EntityType.INTERFACE, EntityType.ENUM):
                return cand
        return None

    def _package_id(self, package: str) -> str:
        for cand in self._by_base.get(package, ()):
            if self.by_id[cand].type == EntityType.PACKAGE:
                return cand
        return package

    def _derived_containment(self) -> list[Relationship]:
        rels: list[Relationship] = []
        for doc in self.by_id.values():
            if doc.navigation:
                continue
            if doc.type == EntityType.METHOD or doc.type == EntityType.FIELD:
                owner = None
                if doc.class_name:
                    owner = self._type_id(".".join(p for p in (doc.package, doc.class_name) if p))
                if not owner and "." in base_name(doc.id):
                    owner = self._type_id(base_name(doc.id).rsplit(".", 1)[0])
                if owner:
                    rels.append(Relationship(source=owner, target=doc.id, type=RelationType.CONTAINS, origin="derived"))
            elif doc.type in (EntityType.CLASS, EntityType.INTERFACE, EntityType.ENUM) and doc.package:
                rels.append(Relationship(source=self._package_id(doc.package), target=doc.id,
                                         type=RelationType.CONTAINS, origin="derived"))
        return rels

    def relationships(self) -> list[Relationship]:
        """All relationships with targets resolved to entity ids.

        Unresolvable targets are kept with status 'unresolved' instead of being
        dropped, so broken references stay visible to users and the validator.
        """
        if self._relationships is not None:
            return self._relationships
        out: list[Relationship] = []
        seen: set[tuple[str, str, str]] = set()
        for doc in self.by_id.values():
            for rel in doc.relationships:
                external = rel.status == "external"
                # Targets marked external by the generator are never resolved against the
                # bundle: e.g. `java.util.List` must not match an analysed class named List.
                src = rel.source if (rel.source == doc.id or external) else (self.resolve(rel.source, doc.id) or rel.source)
                dst = rel.target if (rel.target == doc.id or external) else (self.resolve(rel.target, doc.id) or rel.target)
                if external:
                    status = "external"
                else:
                    status = "resolved" if (src in self.by_id and dst in self.by_id) else "unresolved"
                if src.startswith(PATH_TARGET_PREFIX):
                    src = src[len(PATH_TARGET_PREFIX):]
                if dst.startswith(PATH_TARGET_PREFIX):
                    dst = dst[len(PATH_TARGET_PREFIX):]
                if src == dst:
                    continue
                key = (src, dst, rel.type.value)
                if key in seen:
                    continue
                seen.add(key)
                out.append(Relationship(source=src, target=dst, type=rel.type, origin=rel.origin, status=status,
                                        line=rel.line))
        for rel in self._derived_containment():
            key = (rel.source, rel.target, rel.type.value)
            if key not in seen:
                seen.add(key)
                if rel.source not in self.by_id:
                    rel.status = "resolved"  # synthetic package node; not a broken reference
                out.append(rel)
        # A body link to a doc that is already a typed neighbour (CALLS, USES...) adds
        # no information; dropping it keeps graph views readable.
        typed = {(r.source, r.target) for r in out if r.type != RelationType.REFERENCES}
        out = [r for r in out if r.type != RelationType.REFERENCES or (r.source, r.target) not in typed]
        self._relationships = out
        unresolved = sum(1 for r in out if r.status == "unresolved")
        external = sum(1 for r in out if r.status == "external")
        logger.info("Resolved %d relationships (%d unresolved, %d external)", len(out), unresolved, external)
        return out
