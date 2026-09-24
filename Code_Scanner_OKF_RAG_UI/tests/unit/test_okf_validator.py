from codeknowledge.okf.validator import OKFValidator
from tests.conftest import ABC_OKF, SAMPLE_OKF


def rules(report):
    return {i.rule for i in report.issues}


def write(tmp_path, name, text):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_sample_bundle_passes():
    report = OKFValidator(SAMPLE_OKF).validate()
    assert report.passed, report.render(verbose=True)
    assert report.documents == 24 and report.valid == 24
    assert report.broken_links == 0 and report.duplicate_ids == 0
    assert "Status: PASS" in report.render()


def test_abc_bundle_passes():
    assert OKFValidator(ABC_OKF).validate().passed


def test_frontmatter_missing(tmp_path):
    write(tmp_path, "a.md", "# no frontmatter\n")
    r = OKFValidator(tmp_path).validate()
    assert "frontmatter_missing" in rules(r) and not r.passed


def test_required_metadata(tmp_path):
    write(tmp_path, "a.md", "---\nid: a\n---\n")
    r = OKFValidator(tmp_path, required_metadata=["id", "type"]).validate()
    assert "required_metadata" in rules(r)
    assert "type" in r.errors[0].message


def test_malformed_yaml(tmp_path):
    write(tmp_path, "a.md", "---\nid: [x\n---\n")
    r = OKFValidator(tmp_path).validate()
    assert "malformed_yaml" in rules(r) and not r.passed


def test_duplicate_ids(tmp_path):
    write(tmp_path, "a.md", "---\nid: same\ntype: class\n---\n[b](b.md)")
    write(tmp_path, "b.md", "---\nid: same\ntype: class\n---\n[a](a.md)")
    r = OKFValidator(tmp_path).validate()
    assert r.duplicate_ids == 1 and "duplicate_id" in rules(r) and not r.passed


def test_broken_links_and_missing_referenced_file(tmp_path):
    write(tmp_path, "a.md", "---\nid: a\ntype: class\n---\n[x](missing.md) [img](diagram.png) [[no.such.Id]]")
    r = OKFValidator(tmp_path).validate()
    assert r.broken_links == 3
    assert {"broken_link", "missing_referenced_file"} <= rules(r)


def test_link_outside_root(tmp_path):
    write(tmp_path, "a.md", "---\nid: a\ntype: class\n---\n[x](../../etc/passwd.md)")
    assert "broken_link" in rules(OKFValidator(tmp_path).validate())


def test_links_resolve_ok(tmp_path):
    write(tmp_path, "x/a.md", "---\nid: a\ntype: class\n---\n[b](../y/b.md)")
    write(tmp_path, "y/b.md", "---\nid: b\ntype: class\n---\n")
    r = OKFValidator(tmp_path).validate()
    assert r.passed and r.broken_links == 0 and r.orphans == 0


def test_orphan_documents_are_warnings(tmp_path):
    write(tmp_path, "a.md", "---\nid: a\ntype: class\n---\nalone")
    r = OKFValidator(tmp_path).validate()
    assert r.orphans == 1 and r.passed and "orphan_document" in rules(r)


def test_unresolved_relationship_warning(tmp_path):
    write(tmp_path, "a.md", "---\nid: a\ntype: class\ncalls: [ghost.X]\n---\n")
    r = OKFValidator(tmp_path).validate()
    assert r.unresolved_relationships == 1 and r.passed
    assert "ghost.X" in r.warnings[0].message
