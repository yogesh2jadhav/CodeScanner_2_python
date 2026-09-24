"""Settings: YAML file + environment-variable overrides.

Why YAML + env: YAML keeps a readable, versioned default configuration while env
variables let deployments/CI override single values without editing files.
Override rule: CODEKNOWLEDGE_<SECTION>_<KEY> (e.g. CODEKNOWLEDGE_LLM_MODEL).
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

ENV_PREFIX = "CODEKNOWLEDGE_"
DEFAULT_CONFIG_PATH = "./config/config.yaml"


class ApplicationSettings(BaseModel):
    name: str = "CodeKnowledgeAI"
    version: str = "0.1.0"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])


class OKFSettings(BaseModel):
    source_dir: str = "./data/okf"
    required_metadata: list[str] = Field(default_factory=lambda: ["id", "type"])


class VectorSettings(BaseModel):
    provider: str = "chroma"
    persist_directory: str = "./data/indexes/vector"
    collection_name: str = "codeknowledge"
    top_k: int = 10


class GraphSettings(BaseModel):
    provider: str = "networkx"
    persist_directory: str = "./data/indexes/graph"


class LLMSettings(BaseModel):
    provider: str = "ollama"
    base_url: str = "http://localhost:11434"
    model: str = "qwen3:8b"
    temperature: float = 0.1
    timeout_seconds: float = 120


class EmbeddingSettings(BaseModel):
    provider: str = "ollama"
    base_url: str = "http://localhost:11434"
    model: str = "nomic-embed-text"
    timeout_seconds: float = 300
    batch_size: int = 16


class RetrievalSettings(BaseModel):
    semantic_top_k: int = 10
    symbol_top_k: int = 10
    graph_max_depth: int = 3
    max_context_documents: int = 20
    max_context_tokens: int = 6000
    classifier_confidence_threshold: float = 0.6


class CacheSettings(BaseModel):
    enabled: bool = True
    directory: str = "./data/cache"
    ttl_seconds: int = 86400


class LoggingSettings(BaseModel):
    level: str = "INFO"
    file: str = "./logs/codeknowledge.log"
    config_file: str | None = "./config/logging.yaml"


class Settings(BaseModel):
    application: ApplicationSettings = Field(default_factory=ApplicationSettings)
    okf: OKFSettings = Field(default_factory=OKFSettings)
    vector: VectorSettings = Field(default_factory=VectorSettings)
    graph: GraphSettings = Field(default_factory=GraphSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


def _coerce(value: str, current: Any) -> Any:
    """Convert an env string to the type of the existing value."""
    if isinstance(current, bool):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(current, int):
        return int(value)
    if isinstance(current, float):
        return float(value)
    if isinstance(current, list):
        return [v.strip() for v in value.split(",") if v.strip()]
    return value


def _apply_env_overrides(data: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    defaults = Settings().model_dump()
    for section, fields in defaults.items():
        if not isinstance(fields, dict):
            continue
        for key, default in fields.items():
            env_key = f"{ENV_PREFIX}{section}_{key}".upper()
            if env_key in env:
                current = data.get(section, {}).get(key, default)
                data.setdefault(section, {})[key] = _coerce(env[env_key], current)
    return data


def load_settings(path: str | os.PathLike | None = None, env: dict[str, str] | None = None) -> Settings:
    env = dict(os.environ if env is None else env)
    config_path = Path(path or env.get(f"{ENV_PREFIX}CONFIG", DEFAULT_CONFIG_PATH))
    data: dict[str, Any] = {}
    if config_path.is_file():
        with config_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    return Settings.model_validate(_apply_env_overrides(data, env))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
