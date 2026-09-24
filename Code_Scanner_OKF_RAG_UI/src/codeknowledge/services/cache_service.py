"""File-based answer cache keyed by question + knowledge-base version + model + retrieval config."""
from __future__ import annotations

import json
import time
from pathlib import Path

from codeknowledge.config.settings import Settings
from codeknowledge.utils.ids import stable_hash
from codeknowledge.utils.logging import get_logger

logger = get_logger("AnswerCache")


def cache_key(question: str, bundle_hash: str, model: str, retrieval_config: dict, use_llm: bool) -> str:
    # Normalising whitespace/case lets trivially different phrasings share an entry.
    q = " ".join(question.lower().split())
    return stable_hash(q, bundle_hash, model, json.dumps(retrieval_config, sort_keys=True), str(use_llm))


class AnswerCache:
    def __init__(self, settings: Settings):
        self.enabled = settings.cache.enabled
        self.dir = Path(settings.cache.directory)
        self.ttl = settings.cache.ttl_seconds

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(self, key: str, bundle_hash: str) -> dict | None:
        if not self.enabled:
            return None
        p = self._path(key)
        if not p.is_file():
            return None
        try:
            entry = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            p.unlink(missing_ok=True)
            return None
        # Why re-check version and TTL here: the key already includes the bundle hash,
        # but an explicit check makes invalidation robust to key-format changes.
        if entry.get("knowledge_base_version") != bundle_hash or time.time() - entry.get("timestamp", 0) > self.ttl:
            p.unlink(missing_ok=True)
            return None
        return entry

    def put(self, key: str, question: str, bundle_hash: str, response: dict) -> None:
        if not self.enabled:
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "question": question,
            "timestamp": time.time(),
            "knowledge_base_version": bundle_hash,
            "response": response,  # includes retrieval result, answer and evidence
        }
        tmp = self._path(key).with_suffix(".tmp")
        tmp.write_text(json.dumps(entry, default=str), encoding="utf-8")
        tmp.replace(self._path(key))

    def purge(self, keep_version: str | None = None) -> int:
        """Remove expired entries and entries for other knowledge-base versions."""
        if not self.dir.is_dir():
            return 0
        removed = 0
        now = time.time()
        for p in self.dir.glob("*.json"):
            try:
                entry = json.loads(p.read_text(encoding="utf-8"))
                stale = now - entry.get("timestamp", 0) > self.ttl or (
                    keep_version is not None and entry.get("knowledge_base_version") != keep_version)
            except (OSError, ValueError):
                stale = True
            if stale:
                p.unlink(missing_ok=True)
                removed += 1
        if removed:
            logger.info("Purged %d cache entries", removed)
        return removed
