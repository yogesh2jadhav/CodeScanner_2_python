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


class LLMTimeoutError(LLMUnavailableError):
    pass


class LLMModelMissingError(LLMUnavailableError):
    pass


class LLMProvider(ABC):
    name: str = "base"
    model: str = ""

    @abstractmethod
    def generate(self, prompt: str, system: str | None = None) -> str: ...

    def generate_json(self, prompt: str, system: str | None, schema: dict) -> str:
        """Structured output. Providers without native support fall back to plain generation."""
        return self.generate(prompt, system)

    def is_available(self) -> bool:
        return True


class MockLLMProvider(LLMProvider):
    name = "mock"

    def __init__(self, model: str = "mock-model", response: str | None = None, fail: bool = False,
                 json_responses: list[str] | None = None, error: Exception | None = None):
        self.model = model
        self.response = response
        self.fail = fail
        self.error = error
        # Consumed in order by generate_json; the last one repeats.
        self.json_responses = list(json_responses or [])
        self.calls: list[tuple[str, str | None]] = []
        self.json_calls: list[tuple[str, str | None, dict]] = []

    def generate_json(self, prompt: str, system: str | None, schema: dict) -> str:
        self.json_calls.append((prompt, system, schema))
        if self.error:
            raise self.error
        if self.fail:
            raise LLMUnavailableError("Mock LLM configured to fail")
        if self.json_responses:
            return self.json_responses.pop(0) if len(self.json_responses) > 1 else self.json_responses[0]
        return '{"summary": "Mock summary.", "execution_steps": []}'

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

        return OllamaProvider(cfg.base_url, cfg.model, cfg.temperature, cfg.timeout_seconds, cfg.num_ctx)
    if cfg.provider == "mock":
        return MockLLMProvider(cfg.model)
    raise ValueError(f"Unknown LLM provider: {cfg.provider}")
