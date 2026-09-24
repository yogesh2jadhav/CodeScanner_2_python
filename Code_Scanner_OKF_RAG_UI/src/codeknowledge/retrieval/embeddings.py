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
    model: str = ""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


class OllamaEmbeddingProvider(EmbeddingProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float, batch_size: int = 16):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.batch_size = max(1, batch_size)

    def _post(self, client: httpx.Client, batch: list[str]) -> list[list[float]]:
        """Embed one batch; on a timeout, split it in half and retry.

        Why: on CPU-only machines a batch of long documents can exceed the timeout.
        Aborting would throw away a long indexing run, so the work is subdivided
        until it fits; only a single document that still times out is an error.
        """
        try:
            resp = client.post(f"{self.base_url}/api/embed",
                               json={"model": self.model, "input": batch, "truncate": True})
            resp.raise_for_status()
            return resp.json()["embeddings"]
        except httpx.TimeoutException:
            if len(batch) == 1:
                raise
            mid = len(batch) // 2
            logger.warning("Embedding batch of %d timed out after %ss; retrying as two halves",
                           len(batch), self.timeout)
            return self._post(client, batch[:mid]) + self._post(client, batch[mid:])

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        try:
            with httpx.Client(timeout=httpx.Timeout(self.timeout, connect=10)) as client:
                for i in range(0, len(texts), self.batch_size):
                    out.extend(self._post(client, texts[i:i + self.batch_size]))
        except httpx.ConnectError as exc:
            raise EmbeddingUnavailableError(
                f"Cannot reach Ollama at {self.base_url} ({exc}). Start Ollama (`ollama serve` or the Ollama app) "
                f"and run `ollama pull {self.model}`, or rebuild with --skip-vectors.") from exc
        except httpx.TimeoutException as exc:
            raise EmbeddingUnavailableError(
                f"Ollama embedding timed out after {self.timeout}s even for a single document (model={self.model}). "
                "Increase embedding.timeout_seconds in config/config.yaml. Documents embedded so far are saved; "
                "rerun the rebuild to continue.") from exc
        except httpx.HTTPStatusError as exc:
            hint = f" Run `ollama pull {self.model}`." if exc.response.status_code == 404 else ""
            raise EmbeddingUnavailableError(
                f"Ollama embedding failed (model={self.model}): HTTP {exc.response.status_code}.{hint}") from exc
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
        self.model = f"hash-{dim}"

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
