"""Exact symbol search.

Why a dedicated index: embeddings are poor at exact identifiers
("ClaimService.processClaim" vs "ClaimService.processClaims"); a dictionary
lookup is exact, instant and independent of the vector store's availability.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath

from codeknowledge.models.entities import EntityType
from codeknowledge.okf.repository import OKFRepository
from codeknowledge.utils.ids import base_name, normalize_id, strip_kind_prefix

# kind -> base score for an exact match on that kind
KIND_SCORES = {
    "fqn": 1.0,
    "qualified_name": 0.95,
    "class_name": 0.9,
    "method_name": 0.88,
    "field": 0.8,
    "package": 0.9,
    "source_file": 0.85,
    "in_package": 0.6,
}

_CODE_TOKEN_RE = re.compile(r"`([^`]+)`|([A-Za-z_$][\w$]*(?:[.#][A-Za-z_$][\w$]*)*(?:\(\))?)")
_STOPWORDS = {
    "what", "which", "where", "when", "does", "that", "this", "with", "from", "have", "calls", "call",
    "called", "classes", "class", "method", "methods", "explain", "describe", "show", "about", "there",
    "their", "they", "them", "into", "flow", "path", "code", "used", "uses", "work", "works", "happens",
    "depend", "depends", "dependencies", "who", "how", "the", "and", "for", "why", "between", "eventually",
    "impact", "change", "changes", "affected", "rules", "rule", "business", "logic", "architecture",
    "is", "are", "can", "list", "find", "give", "tell", "i", "if", "in", "of", "to", "on", "an",
}


@dataclass
class SymbolHit:
    entity_id: str
    score: float
    kind: str
    key: str


def _looks_like_code(token: str) -> bool:
    core = token.rstrip("()")
    return (
        token.endswith("()")
        or "." in core or "#" in core or "_" in core
        or any(c.isupper() for c in core[1:])  # camelCase / PascalCase
        or core[:1].isupper()  # PascalCase class names, incl. one-letter ones like "A"
    )


def extract_symbols(text: str) -> list[str]:
    """Code-like tokens in a natural-language question (backticked, camelCase, dotted, foo())."""
    out: list[str] = []
    for tick, tok in _CODE_TOKEN_RE.findall(text):
        cand = tick or tok
        if tick or (_looks_like_code(cand) and cand.lower() not in _STOPWORDS):
            norm = normalize_id(cand)
            if norm and norm not in out:
                out.append(norm)
    return out


def candidate_words(text: str) -> list[str]:
    return [w for w in re.findall(r"[A-Za-z_][\w$]{3,}", text) if w.lower() not in _STOPWORDS]


class SymbolIndex:
    def __init__(self, repo: OKFRepository):
        self.repo = repo
        self.entries: dict[str, list[tuple[str, str]]] = defaultdict(list)  # key -> [(entity_id, kind)]
        for doc in repo.content_documents:
            self._add(doc.id, doc.id, "fqn")
            qualified = strip_kind_prefix(doc.id)
            self._add(qualified, doc.id, "fqn")
            self._add(base_name(doc.id), doc.id, "fqn")
            display = doc.display_name()
            if display != doc.id:
                self._add(display, doc.id, "qualified_name")
                self._add(display.split("(", 1)[0], doc.id, "qualified_name")
            if doc.type == EntityType.METHOD and doc.method_name:
                self._add(doc.method_name, doc.id, "method_name")
            elif doc.type in (EntityType.CLASS, EntityType.INTERFACE, EntityType.ENUM):
                self._add(doc.class_name or doc.title, doc.id, "class_name")
                for f in doc.metadata.get("fields") or []:
                    name = f.get("name") if isinstance(f, dict) else str(f)
                    if name:
                        self._add(name, doc.id, "field")
                        self._add(f"{doc.class_name or doc.title}.{name}", doc.id, "field")
            elif doc.type == EntityType.FIELD:
                self._add(doc.title, doc.id, "field")
            elif doc.type == EntityType.PACKAGE:
                self._add(doc.title, doc.id, "package")
            if doc.package and doc.type != EntityType.PACKAGE:
                self._add(doc.package, doc.id, "in_package")
            if doc.source_file and doc.type in (EntityType.CLASS, EntityType.INTERFACE, EntityType.ENUM):
                p = PurePosixPath(doc.source_file.replace("\\", "/"))
                for key in {doc.source_file, p.name, p.stem}:
                    self._add(key, doc.id, "source_file")
        self._keys = sorted(self.entries)

    def _add(self, key: str, entity_id: str, kind: str) -> None:
        k = key.strip().lower()
        if k and (entity_id, kind) not in self.entries[k]:
            self.entries[k].append((entity_id, kind))

    def search(self, query: str, top_k: int = 10, fuzzy: bool = True) -> list[SymbolHit]:
        q = normalize_id(query).lower()
        if not q:
            return []
        best: dict[str, SymbolHit] = {}

        def offer(eid: str, score: float, kind: str, key: str) -> None:
            if eid not in best or best[eid].score < score:
                best[eid] = SymbolHit(eid, round(score, 4), kind, key)

        for eid, kind in self.entries.get(q, []):
            offer(eid, KIND_SCORES[kind], kind, q)
        if fuzzy and len(best) < top_k and len(q) >= 3:
            # Fuzzy tiers are scaled down so an exact hit always ranks first.
            for key in self._keys:
                if key == q:
                    continue
                if key.startswith(q) or key.endswith("." + q):
                    factor = 0.7
                elif q in key:
                    factor = 0.5
                else:
                    continue
                for eid, kind in self.entries[key]:
                    if kind != "in_package":
                        offer(eid, KIND_SCORES[kind] * factor, kind, key)
        hits = sorted(best.values(), key=lambda h: (-h.score, h.entity_id))
        return hits[:top_k]

    def resolve_question(self, question: str) -> list[SymbolHit]:
        """Exact entities mentioned in a question (no fuzzy matching, to avoid false targets)."""
        hits: list[SymbolHit] = []
        seen: set[str] = set()
        # Code-looking tokens first; plain words only if none of those resolve.
        for tokens in (extract_symbols(question), candidate_words(question)):
            for tok in tokens:
                for h in self.search(tok, top_k=5, fuzzy=False):
                    if h.kind == "in_package":
                        continue
                    if h.entity_id not in seen:
                        seen.add(h.entity_id)
                        hits.append(h)
            if hits:
                break
        # "processCasingData in CasingService" names both a class and one of its methods;
        # the method is the more specific target, so its class is dropped.
        method_bases = {base_name(h.entity_id) for h in hits
                        if (d := self.repo.get(h.entity_id)) is not None and d.type == EntityType.METHOD}
        hits = [h for h in hits
                if not any(mb.startswith(base_name(h.entity_id) + ".") for mb in method_bases)]
        return sorted(hits, key=lambda h: -h.score)

    def close_matches(self, question: str, limit: int = 5) -> list[SymbolHit]:
        """Fuzzy candidates for code-like tokens that matched nothing exactly (typos, partial names)."""
        out: dict[str, SymbolHit] = {}
        for tok in extract_symbols(question):
            for h in self.search(tok, top_k=limit, fuzzy=True):
                if h.kind != "in_package" and h.entity_id not in out:
                    out[h.entity_id] = h
        return sorted(out.values(), key=lambda h: -h.score)[:limit]
