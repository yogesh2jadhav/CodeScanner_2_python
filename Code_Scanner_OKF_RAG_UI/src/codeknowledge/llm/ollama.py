"""Ollama chat provider."""
from __future__ import annotations

import re

import httpx

from codeknowledge.llm.provider import LLMProvider, LLMUnavailableError
from codeknowledge.utils.logging import get_logger

logger = get_logger("OllamaProvider")

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, temperature: float, timeout: float, num_ctx: int | None = None):
        self.num_ctx = num_ctx
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.timeout = timeout

    def is_available(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=3)
            r.raise_for_status()
            names = {m.get("name") for m in r.json().get("models", [])}
            return self.model in names or f"{self.model}:latest" in names
        except (httpx.HTTPError, ValueError):
            return False

    def generate(self, prompt: str, system: str | None = None) -> str:
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            # Reasoning models (qwen3) would otherwise spend the budget "thinking";
            # we want a direct, evidence-bound answer.
            "think": False,
            "options": {"temperature": self.temperature, **({"num_ctx": self.num_ctx} if self.num_ctx else {})},
        }
        try:
            r = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
            r.raise_for_status()
            content = r.json()["message"]["content"]
        except httpx.TimeoutException as exc:
            raise LLMUnavailableError(
                f"Ollama did not answer within {self.timeout}s (model={self.model}). Increase llm.timeout_seconds "
                "or use a smaller/faster model.") from exc
        except httpx.ConnectError as exc:
            raise LLMUnavailableError(f"Cannot reach Ollama at {self.base_url}. Start Ollama.") from exc
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise LLMUnavailableError(f"Ollama request failed (model={self.model}): {exc}") from exc
        return _THINK_RE.sub("", content).strip()
