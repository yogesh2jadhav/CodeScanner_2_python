"""Semantic (vector) index over OKF documents backed by ChromaDB."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from codeknowledge.config.settings import VectorSettings
from codeknowledge.okf.repository import OKFRepository
from codeknowledge.retrieval.embeddings import EmbeddingProvider
from codeknowledge.retrieval.representation import build_metadata, build_retrieval_text
from codeknowledge.utils.logging import get_logger
from codeknowledge.utils.timing import timed

logger = get_logger("VectorIndexer")


class SemanticUnavailableError(RuntimeError):
    pass


@dataclass
class SemanticHit:
    entity_id: str
    score: float
    metadata: dict[str, Any]


@dataclass
class IndexRunStats:
    total: int = 0
    embedded: int = 0
    unchanged: int = 0
    removed: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


STATE_FILE = "index_state.json"
TEXT_HASH_KEY = "text_hash"
GET_PAGE = 5000


def _comments_for(source, doc) -> str | None:
    """Developer comments of a method, read from source.root_dir (None when unavailable)."""
    if source is None or not source.enabled or doc.type.value != "method":
        return None
    try:
        from codeknowledge.source.reader import extract_comments

        snippet = source.snippet(doc)
        return " ".join(" ".join(c.text.split()) for c in extract_comments(snippet)) if snippet else None
    except OSError:
        return None


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class SemanticIndex:
    def __init__(self, cfg: VectorSettings, embedder: EmbeddingProvider, chunk_size: int = 128):
        self.chunk_size = chunk_size  # documents embedded + saved per step (resume granularity)
        self.cfg = cfg
        self.embedder = embedder
        self._collection = None
        self._client = None
        self.error: str | None = None

    def _get_collection(self):
        if self._collection is not None:
            return self._collection
        try:
            import chromadb

            self._client = chromadb.PersistentClient(
                path=self.cfg.persist_directory,
                settings=chromadb.Settings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                self.cfg.collection_name, metadata={"hnsw:space": "cosine"}
            )
        except Exception as exc:  # chroma import/sqlite/disk errors
            self.error = str(exc)
            logger.exception("Vector store unavailable")
            raise SemanticUnavailableError(f"Vector store unavailable: {exc}") from exc
        return self._collection

    # Index state lives in a small sidecar file rather than collection metadata: it is
    # written only after a run completes, so an interrupted run is visibly "stale".
    def _state_path(self) -> Path:
        return Path(self.cfg.persist_directory) / STATE_FILE

    def _read_state(self) -> dict[str, Any]:
        try:
            return json.loads(self._state_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _write_state(self, state: dict[str, Any]) -> None:
        self._state_path().parent.mkdir(parents=True, exist_ok=True)
        self._state_path().write_text(json.dumps(state, indent=1), encoding="utf-8")

    def indexed_bundle_hash(self) -> str | None:
        return self._read_state().get("bundle_hash")

    def count(self) -> int:
        try:
            return self._get_collection().count()
        except SemanticUnavailableError:
            return 0

    def _existing_hashes(self) -> dict[str, str]:
        col = self._get_collection()
        out: dict[str, str] = {}
        offset = 0
        while True:
            page = col.get(include=["metadatas"], limit=GET_PAGE, offset=offset)
            ids = page.get("ids") or []
            for eid, meta in zip(ids, page.get("metadatas") or []):
                out[eid] = (meta or {}).get(TEXT_HASH_KEY, "")
            if len(ids) < GET_PAGE:
                return out
            offset += GET_PAGE

    def rebuild(self, repo: OKFRepository, progress=None, full: bool = False, source=None) -> IndexRunStats:
        """Bring the vector index in line with the bundle, incrementally.

        Why incremental: embedding a 10k+ document bundle on CPU takes a long time.
        Each chunk is stored as soon as it is embedded and every entry records a hash
        of its retrieval text, so an interrupted run resumes where it stopped and a
        changed bundle only re-embeds changed documents. Documents that disappeared
        from the bundle are deleted. `full=True` (or a different embedding model)
        starts from an empty collection.
        """
        stats = IndexRunStats()
        with timed(logger, "vector_index"):
            self._get_collection()
            state = self._read_state()
            model_id = f"{self.embedder.name}:{self.embedder.model}"
            if full or (state and state.get("embedding") != model_id) or (not state and self._collection.count()):
                # Vectors from another model are incomparable; unknown provenance is not trusted either.
                try:
                    self._client.delete_collection(self.cfg.collection_name)
                except Exception:
                    pass
                self._collection = self._client.create_collection(
                    self.cfg.collection_name, metadata={"hnsw:space": "cosine"})
            self._write_state({**state, "embedding": model_id, "bundle_hash": None})

            rels = repo.relationships()
            by_doc: dict[str, list] = {}
            for r in rels:
                by_doc.setdefault(r.source, []).append(r)
                by_doc.setdefault(r.target, []).append(r)
            docs = repo.content_documents
            texts = {d.id: build_retrieval_text(d, by_doc.get(d.id, []), _comments_for(source, d)) for d in docs}
            hashes = {eid: _text_hash(t) for eid, t in texts.items()}

            existing = self._existing_hashes()
            gone = [eid for eid in existing if eid not in hashes]
            for i in range(0, len(gone), GET_PAGE):
                self._collection.delete(ids=gone[i:i + GET_PAGE])
            todo = [d for d in docs if existing.get(d.id) != hashes[d.id]]
            stats.total, stats.removed = len(docs), len(gone)
            stats.unchanged = len(docs) - len(todo)
            if stats.unchanged:
                logger.info("Vector index: %d unchanged documents kept, %d to embed", stats.unchanged, len(todo))

            chunk = self.chunk_size
            for i in range(0, len(todo), chunk):
                part = todo[i:i + chunk]
                embeddings = self.embedder.embed([texts[d.id] for d in part])
                self._collection.upsert(
                    ids=[d.id for d in part],
                    embeddings=embeddings,
                    documents=[texts[d.id] for d in part],
                    metadatas=[{**build_metadata(d), TEXT_HASH_KEY: hashes[d.id]} for d in part],
                )
                stats.embedded += len(part)
                if progress:
                    progress(stats.unchanged + stats.embedded, stats.total)
            self._write_state({"embedding": model_id, "bundle_hash": repo.bundle_hash, "documents": len(docs)})
        logger.info("Indexed %d documents (embedded %d, unchanged %d, removed %d)",
                    stats.total, stats.embedded, stats.unchanged, stats.removed)
        return stats

    def search(self, query: str, top_k: int, entity_type: str | None = None,
               package: str | None = None) -> list[SemanticHit]:
        col = self._get_collection()
        if col.count() == 0:
            return []
        where: dict[str, Any] | None = None
        conds = [{"entity_type": entity_type}] if entity_type else []
        if package:
            conds.append({"package": package})
        if len(conds) == 1:
            where = conds[0]
        elif conds:
            where = {"$and": conds}
        vec = self.embedder.embed_one(query)
        res = col.query(query_embeddings=[vec], n_results=min(top_k, col.count()), where=where)
        hits: list[SemanticHit] = []
        for eid, dist, meta in zip(res["ids"][0], res["distances"][0], res["metadatas"][0]):
            # cosine distance in [0, 2] -> similarity in [-1, 1]
            hits.append(SemanticHit(eid, round(1.0 - float(dist), 4), dict(meta or {})))
        return hits
