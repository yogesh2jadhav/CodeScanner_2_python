"""Semantic (vector) index over OKF documents backed by ChromaDB."""
from __future__ import annotations

from dataclasses import dataclass
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


class SemanticIndex:
    def __init__(self, cfg: VectorSettings, embedder: EmbeddingProvider):
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

    def indexed_bundle_hash(self) -> str | None:
        try:
            meta = self._get_collection().metadata or {}
        except SemanticUnavailableError:
            return None
        return meta.get("bundle_hash")

    def count(self) -> int:
        try:
            return self._get_collection().count()
        except SemanticUnavailableError:
            return 0

    def rebuild(self, repo: OKFRepository) -> int:
        """Drop and re-create the collection so deleted OKF docs never linger in the index."""
        import chromadb  # noqa: F401  (ensures a clear error if chroma is missing)

        with timed(logger, "vector_index"):
            self._get_collection()
            try:
                self._client.delete_collection(self.cfg.collection_name)
            except Exception:
                pass
            self._collection = self._client.create_collection(
                self.cfg.collection_name,
                metadata={"hnsw:space": "cosine", "bundle_hash": repo.bundle_hash,
                          "embedding_provider": self.embedder.name},
            )
            rels = repo.relationships()
            by_doc: dict[str, list] = {}
            for r in rels:
                by_doc.setdefault(r.source, []).append(r)
                by_doc.setdefault(r.target, []).append(r)
            docs = repo.documents
            texts = [build_retrieval_text(d, by_doc.get(d.id, [])) for d in docs]
            if docs:
                embeddings = self.embedder.embed(texts)
                batch = 256
                for i in range(0, len(docs), batch):
                    self._collection.upsert(
                        ids=[d.id for d in docs[i:i + batch]],
                        embeddings=embeddings[i:i + batch],
                        documents=texts[i:i + batch],
                        metadatas=[build_metadata(d) for d in docs[i:i + batch]],
                    )
        logger.info("Indexed %d documents", len(docs))
        return len(docs)

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
