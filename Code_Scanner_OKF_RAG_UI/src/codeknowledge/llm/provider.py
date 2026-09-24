"""LLM provider abstraction.

Why an ABC with a mock: the plan requires the LLM to be swappable and CI must not
depend on a live model. MockLLMProvider returns a deterministic answer built from
the prompt so tests can check the question -> context -> prompt -> answer chain.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod

from codeknowledge.config.settings import LLMSettings


class LLMUnavailableError(RuntimeError):
    pass


class LLMProvider(ABC):
    name: str = "base"
    model: str = ""

    @abstractmethod
    def generate(self, prompt: str, system: str | None = None) -> str: ...

    def is_available(self) -> bool:
        return True


class MockLLMProvider(LLMProvider):
    name = "mock"

    def __init__(self, model: str = "mock-model", response: str | None = None, fail: bool = False):
        self.model = model
        self.response = response
        self.fail = fail
        self.calls: list[tuple[str, str | None]] = []

    def generate(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        if self.fail:
            raise LLMUnavailableError("Mock LLM configured to fail")
        if self.response is not None:
            return self.response
        ids = re.findall(r'"id": "([^"]+)"', prompt)
        cited = ", ".join(f"`{i}`" for i in ids[:3]) or "the supplied evidence"
        return f"**Interpretation (mock):** Based on {cited}, the code appears to perform the described behaviour."


def create_llm_provider(cfg: LLMSettings) -> LLMProvider:
    if cfg.provider == "ollama":
        from codeknowledge.llm.ollama import OllamaProvider

        return OllamaProvider(cfg.base_url, cfg.model, cfg.temperature, cfg.timeout_seconds)
    if cfg.provider == "mock":
        return MockLLMProvider(cfg.model)
    raise ValueError(f"Unknown LLM provider: {cfg.provider}")
