from codeknowledge.models.entities import EntityType, OKFDocument
from codeknowledge.source.reader import SourceReader, extract_comments, extract_conditions

JAVA = '''package p;

public class Casing {

    /**
     * Processes casing data for a partition.
     */
    @SuppressWarnings("unchecked")
    private Map<String, List<Row>> processCasingData(
            List<ClaimDataDBO> claims,
            boolean isNDDEnabled) throws BICException {

        /*
         * This is data manipulation based on Metadata Configuration
         * only for Stage = Pre.
         */
        List<Pre> pre = load.populate(claims);

        dtos.stream()
                .filter(dto -> Objects.isNull(dto.getDischargeDate()))
                .forEach((id, list) -> {
                    // nddFlag = 1 when actual discharge date is missing,
                    // otherwise 0.
                    if (isNDDEnabled) {
                        dto.setNddFlag(1);
                    } else if (x > 2 && y.equals("A")) {
                        dto.setNddFlag(0);
                    }
                });
        // dto.setFoo(bar);
        String s = "not // a comment { }";
        try {
            return visit.generate(pre);
        } catch (BICException e) {
            throw new BICException("failed");
        }
    }

    void other() {}
}
'''


def make(tmp_path, line=9, end=None, name="processCasingData"):
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "Casing.java").write_text(JAVA)
    doc = OKFDocument(id="m", path="m.md", title=name, type=EntityType.METHOD, method_name=name,
                      source_file="src/Casing.java", source_line=line, end_line=end)
    return SourceReader(tmp_path).snippet(doc)


def test_snippet_includes_javadoc_and_full_body(tmp_path):
    sn = make(tmp_path)
    assert sn.start_line == 5 and sn.decl_line == 9 and not sn.drifted
    assert sn.lines[0].strip() == "/**" and sn.lines[-1].strip() == "}"
    assert "void other()" not in sn.text  # stops at the method's closing brace, braces in strings ignored
    assert sn.numbered().splitlines()[0].startswith(" 5| ")


def test_drift_detection(tmp_path):
    sn = make(tmp_path, line=30)  # file changed since OKF generation
    assert sn.decl_line == 9 and sn.drifted and "changed since OKF generation" in sn.notes[0]


def test_comments_verbatim_and_code_like_comments_skipped(tmp_path):
    comments = extract_comments(make(tmp_path))
    texts = [c.text for c in comments]
    assert texts[0] == "Processes casing data for a partition." and comments[0].kind == "javadoc"
    assert texts[1].startswith("This is data manipulation") and (comments[1].start_line, comments[1].end_line) == (13, 16)
    assert texts[2] == "nddFlag = 1 when actual discharge date is missing,\notherwise 0."
    assert (comments[2].start_line, comments[2].end_line) == (22, 23)
    assert not any("setFoo" in t for t in texts)  # commented-out code
    assert not any("not" in t and "comment {" in t for t in texts)  # // inside a string


def test_conditions(tmp_path):
    conds = [(c.line, c.kind, c.expression) for c in extract_conditions(make(tmp_path))]
    assert (20, "filter", "dto -> Objects.isNull(dto.getDischargeDate())") in conds
    assert (24, "if", "isNDDEnabled") in conds
    assert (26, "else if", 'x > 2 && y.equals("A")') in conds
    assert (34, "catch", "BICException e") in conds


def test_refuses_paths_outside_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "secret.java").write_text("class S { void m() {} }")
    doc = OKFDocument(id="m", path="m.md", title="m", type=EntityType.METHOD, method_name="m",
                      source_file="../secret.java", source_line=1)
    assert SourceReader(root).snippet(doc) is None


def test_disabled_without_root(tmp_path):
    assert not SourceReader(None).enabled
    assert not SourceReader(tmp_path / "missing").enabled
