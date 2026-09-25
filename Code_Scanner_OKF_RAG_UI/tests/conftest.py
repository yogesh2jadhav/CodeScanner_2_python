from __future__ import annotations

from pathlib import Path

import pytest

from codeknowledge.config.settings import Settings

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_OKF = FIXTURES / "sample-okf"
ABC_OKF = FIXTURES / "abc-okf"


def make_settings(tmp_path: Path, okf_dir: Path | None = None) -> Settings:
    return Settings.model_validate(
        {
            "okf": {"source_dir": str(okf_dir or SAMPLE_OKF)},
            "vector": {"persist_directory": str(tmp_path / "vector")},
            "graph": {"persist_directory": str(tmp_path / "graph")},
            "embedding": {"provider": "hash"},
            "llm": {"provider": "mock"},
            "cache": {"directory": str(tmp_path / "cache")},
            "logging": {"file": str(tmp_path / "logs" / "test.log"), "config_file": None},
        }
    )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


def make_kb(tmp_path: Path, okf_dir: Path | None = None):
    from codeknowledge.services.indexing_service import KnowledgeBase

    kb = KnowledgeBase(make_settings(tmp_path, okf_dir))
    kb.load(rebuild=True, rebuild_vectors=True)
    return kb


@pytest.fixture
def kb(tmp_path: Path):
    return make_kb(tmp_path)


EXPLAIN_OKF = FIXTURES / "explain-okf"
EXPLAIN_JAVA = FIXTURES / "explain-java"
BUILD_VISITS = "java-method:com.acme.visits.VisitProcessor.buildVisits(java.util.List,boolean)"


def make_explain_kb(tmp_path: Path, with_source: bool = True):
    from codeknowledge.services.indexing_service import KnowledgeBase

    s = make_settings(tmp_path, EXPLAIN_OKF)
    if with_source:
        s.source.root_dir = str(EXPLAIN_JAVA)
    kb = KnowledgeBase(s)
    kb.load(rebuild=True, rebuild_vectors=True)
    return kb
