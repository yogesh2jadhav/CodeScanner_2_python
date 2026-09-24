"""Embedding providers.

Why an abstraction: the plan requires a swappable embedding backend. Ollama is
the default; HashEmbeddingProvider is a deterministic, dependency-free provider
used by tests/CI (and usable offline), never silently substituted for Ollama.
"""
from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod

import httpx

from codeknowledge.config.settings import EmbeddingSettings
from codeknowledge.utils.logging import get_logger

logger = get_logger("Embeddings")


class EmbeddingUnavailableError(RuntimeError):
    pass


class EmbeddingProvider(ABC):
    name: str = "base"

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


class OllamaEmbeddingProvider(EmbeddingProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float, batch_size: int = 32):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.batch_size = batch_size

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        try:
            with httpx.Client(timeout=self.timeout) as client:
                for i in range(0, len(texts), self.batch_size):
                    batch = texts[i:i + self.batch_size]
                    resp = client.post(f"{self.base_url}/api/embed", json={"model": self.model, "input": batch})
                    resp.raise_for_status()
                    out.extend(resp.json()["embeddings"])
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise EmbeddingUnavailableError(f"Ollama embedding failed (model={self.model}): {exc}") from exc
        return out


_TOKEN_RE = re.compile(r"[A-Za-z][a-z0-9]*|[0-9]+")


def _tokens(text: str) -> list[str]:
    # Split camelCase / dotted identifiers so "processClaims" matches "process claims".
    return [t.lower() for t in _TOKEN_RE.findall(text)]


class HashEmbeddingProvider(EmbeddingProvider):
    """Feature-hashed bag of words + bigrams, L2-normalised."""

    name = "hash"

    def __init__(self, dim: int = 512):
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        toks = _tokens(text)
        feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
        for f in feats:
            h = int.from_bytes(hashlib.md5(f.encode()).digest()[:4], "little")
            v[h % self.dim] += 1.0 if (h >> 31) & 1 else -1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]


def create_embedding_provider(cfg: EmbeddingSettings) -> EmbeddingProvider:
    if cfg.provider == "ollama":
        return OllamaEmbeddingProvider(cfg.base_url, cfg.model, cfg.timeout_seconds, cfg.batch_size)
    if cfg.provider == "hash":
        return HashEmbeddingProvider()
    raise ValueError(f"Unknown embedding provider: {cfg.provider}")
