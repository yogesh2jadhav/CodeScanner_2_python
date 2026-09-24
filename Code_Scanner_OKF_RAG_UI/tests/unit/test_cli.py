import subprocess
import sys

from codeknowledge.cli import main
from tests.conftest import SAMPLE_OKF


def test_cli_validate_pass(capsys):
    assert main(["validate", "--input", str(SAMPLE_OKF)]) == 0
    assert "Status: PASS" in capsys.readouterr().out


def test_cli_validate_fail(tmp_path, capsys):
    (tmp_path / "a.md").write_text("no frontmatter")
    assert main(["validate", "--input", str(tmp_path)]) == 1
    assert "Status: FAIL" in capsys.readouterr().out


def test_cli_missing_dir(tmp_path, capsys):
    assert main(["validate", "--input", str(tmp_path / "nope")]) == 1
    assert "Configure okf.source_dir" in capsys.readouterr().err


def test_cli_ingest(capsys):
    assert main(["ingest", "--input", str(SAMPLE_OKF)]) == 0
    assert "Documents discovered: 24" in capsys.readouterr().out


def test_validate_script_exit_code():
    proc = subprocess.run([sys.executable, "scripts/validate_okf.py", "--input", str(SAMPLE_OKF)],
                          capture_output=True, text=True)
    assert proc.returncode == 0 and "Status: PASS" in proc.stdout


def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEKNOWLEDGE_OKF_SOURCE_DIR", str(SAMPLE_OKF))
    monkeypatch.setenv("CODEKNOWLEDGE_VECTOR_PERSIST_DIRECTORY", str(tmp_path / "vec"))
    monkeypatch.setenv("CODEKNOWLEDGE_GRAPH_PERSIST_DIRECTORY", str(tmp_path / "graph"))
    monkeypatch.setenv("CODEKNOWLEDGE_CACHE_DIRECTORY", str(tmp_path / "cache"))
    monkeypatch.setenv("CODEKNOWLEDGE_EMBEDDING_PROVIDER", "hash")
    monkeypatch.setenv("CODEKNOWLEDGE_LLM_PROVIDER", "mock")
    monkeypatch.setenv("CODEKNOWLEDGE_LOGGING_FILE", str(tmp_path / "log.log"))


def test_cli_rebuild_search_ask(tmp_path, monkeypatch, capsys):
    _env(tmp_path, monkeypatch)
    assert main(["rebuild"]) == 0
    out = capsys.readouterr().out
    assert "Documents: 24" in out and "Vector index: ok (24 documents)" in out
    assert main(["search", "ClaimService"]) == 0
    assert "com.example.claim.ClaimService" in capsys.readouterr().out.splitlines()[0]
    assert main(["ask", "Who calls processClaim?"]) == 0
    out = capsys.readouterr().out
    assert "Category: CALLERS" in out and "ClaimService.process" in out and "Evidence:" in out
    assert main(["ask", "What does ClaimService do?", "--json"]) == 0
    assert '"llm_used": true' in capsys.readouterr().out


def test_cli_rebuild_fails_on_empty_bundle(tmp_path, monkeypatch, capsys):
    _env(tmp_path, monkeypatch)
    empty = tmp_path / "okf"
    empty.mkdir()
    monkeypatch.setenv("CODEKNOWLEDGE_OKF_SOURCE_DIR", str(empty))
    assert main(["rebuild"]) == 1
    captured = capsys.readouterr()
    assert f"OKF source: {empty.resolve()}" in captured.out
    assert "No OKF documents found" in captured.err


def test_cli_validate_verbose_is_capped(tmp_path, capsys):
    for i in range(250):
        (tmp_path / f"d{i}.md").write_text(f"---\nid: d{i}\ntype: class\ncalls: [ghost.X]\n---\n")
    assert main(["validate", "--input", str(tmp_path), "-v"]) == 0
    out = capsys.readouterr().out
    assert "Issues (showing 200 of 250)" in out
    assert "Most frequent unresolved targets:" in out and "250  ghost.X" in out
