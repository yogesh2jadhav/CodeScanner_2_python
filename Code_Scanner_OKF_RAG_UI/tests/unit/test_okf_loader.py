import pytest

from codeknowledge.okf.loader import OKFLoader, OKFSourceMissingError
from codeknowledge.okf.repository import OKFRepository
from codeknowledge.models.relationships import RelationType
from tests.conftest import SAMPLE_OKF


def test_missing_directory(tmp_path):
    with pytest.raises(OKFSourceMissingError) as exc:
        OKFLoader(tmp_path / "missing").load()
    assert "OKF source directory does not exist." in str(exc.value)
    assert "Configure okf.source_dir." in str(exc.value)


def test_load_sample_bundle():
    res = OKFLoader(SAMPLE_OKF).load()
    r = res.report
    assert r.discovered == 24
    assert r.errors == 0 and r.valid == 24
    assert r.links > 20
    assert "Documents discovered: 24" in r.render()


def test_nested_dirs_and_bad_documents_do_not_stop_ingestion(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "ok.md").write_text("---\nid: x.Ok\ntype: class\n---\n# Ok\n")
    (tmp_path / "bad.md").write_text("---\nid: [oops\n---\n")
    (tmp_path / "nofm.md").write_text("# Loose note\n")
    (tmp_path / "bin.md").write_bytes(b"\xff\xfe\x00bad")
    res = OKFLoader(tmp_path).load()
    assert res.report.discovered == 4
    assert res.report.valid == 1 and res.report.warnings == 1 and res.report.errors == 2
    assert {d.id for d in res.documents} == {"x.Ok", "nofm"}


def test_bundle_hash_changes_with_content(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("---\nid: a\n---\n")
    h1 = OKFLoader(tmp_path).load().bundle_hash
    f.write_text("---\nid: a\n---\nchanged")
    assert OKFLoader(tmp_path).load().bundle_hash != h1


def test_repository_resolution():
    repo = OKFRepository.from_directory(SAMPLE_OKF)
    P = "com.example.claim"
    # unqualified target resolved within source's class
    assert repo.resolve("getClaimData", f"{P}.CasingService.processClaims") == f"{P}.CasingService.getClaimData"
    assert repo.resolve("@path:classes/ClaimService.md") == f"{P}.ClaimService"
    assert repo.resolve("CasingService") == f"{P}.CasingService"  # unique suffix
    assert repo.resolve("nope.Nothing") is None
    assert repo.lookup("casingservice.processclaims") == [f"{P}.CasingService.processClaims"]


def test_repository_relationships_include_derived_and_resolved():
    repo = OKFRepository.from_directory(SAMPLE_OKF)
    P = "com.example.claim"
    rels = {(r.source, r.target, r.type) for r in repo.relationships()}
    assert (f"{P}.ClaimService", f"{P}.BaseService", RelationType.EXTENDS) in rels
    assert (f"{P}.ClaimService", f"{P}.ClaimProcessor", RelationType.IMPLEMENTS) in rels
    assert (f"{P}.JdbcClaimRepository", f"{P}.ClaimRepository", RelationType.IMPLEMENTS) in rels
    assert (f"{P}.CasingService", f"{P}.CasingService.processClaims", RelationType.CONTAINS) in rels
    assert (P, f"{P}.ClaimService", RelationType.CONTAINS) in rels
    assert (f"{P}.CasingService.processClaims", f"{P}.CasingService.getClaimData", RelationType.CALLS) in rels
    assert all(r.status == "resolved" for r in repo.relationships())


def test_unresolved_relationship_is_kept(tmp_path):
    (tmp_path / "A.md").write_text("---\nid: p.A\ntype: class\ncalls: [p.Missing]\n---\n")
    repo = OKFRepository.from_directory(tmp_path)
    [rel] = repo.relationships()
    assert rel.status == "unresolved" and rel.target == "p.Missing"


def test_duplicate_ids_first_wins(tmp_path):
    (tmp_path / "a.md").write_text("---\nid: dup\n---\n")
    (tmp_path / "b.md").write_text("---\nid: dup\n---\n")
    repo = OKFRepository.from_directory(tmp_path)
    assert repo.get("dup").path == "a.md" and repo.duplicates["dup"] == ["b.md"]
