"""MethodEvidenceBuilder + EvidenceBudgetManager (no LLM)."""
import pytest

from codeknowledge.explain.budget import EvidenceBudgetManager
from codeknowledge.explain.evidence import InvalidMethodIdError, MethodEvidenceBuilder, MethodNotFoundError
from codeknowledge.explain.models import EvidenceItem, EvidencePackage, ExplainOptions
from tests.conftest import BUILD_VISITS, make_explain_kb

P = "com.acme.visits"
GROUP = f"java-method:{P}.VisitProcessor.groupByClaim(java.util.List)"
VALIDATE = f"java-method:{P}.VisitProcessor.validate(java.lang.String,java.util.List)"
SAVE_ALL = f"java-method:{P}.VisitRepository.saveAll(java.util.List)"
PING_A = f"java-method:{P}.VisitProcessor.pingA(int)"
PING_B = f"java-method:{P}.VisitProcessor.pingB(int)"


@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    return make_explain_kb(tmp_path_factory.mktemp("kb"))


@pytest.fixture(scope="module")
def builder(kb):
    return MethodEvidenceBuilder(kb, kb.settings.method_explanation)


def by_kind(pkg, kind):
    return [i for i in pkg.items if i.kind == kind]


def test_resolves_exact_method_and_source_range(builder):
    pkg, _ = builder.build(BUILD_VISITS, ExplainOptions())
    assert pkg.method_id == BUILD_VISITS and pkg.source_available
    [body] = by_kind(pkg, "method_source")
    assert (body.start_line, body.end_line) == (25, 73)  # Javadoc (25) through closing brace (73)
    lines = body.content.splitlines()
    assert lines[3].startswith("28|") and "buildVisits(List<ClaimLine> lines" in lines[3]
    assert [int(ln.split("|")[0]) for ln in lines] == list(range(25, 74))  # exact order, no gaps


def test_ids_are_stable_and_deterministic(builder):
    a, _ = builder.build(BUILD_VISITS, ExplainOptions())
    b, _ = builder.build(BUILD_VISITS, ExplainOptions())
    assert [(i.evidence_id, i.kind, i.entity_id, i.content) for i in a.items] == \
           [(i.evidence_id, i.kind, i.entity_id, i.content) for i in b.items]


def test_calls_preserve_status_and_lines(builder):
    pkg, facts = builder.build(BUILD_VISITS, ExplainOptions())
    calls = {i.title: (i.status, i.lines) for i in by_kind(pkg, "call")}
    assert calls["calls ClaimLine.setMissingEndFlag(int)"] == ("resolved", [50, 52])
    assert calls["calls audit.record(..)"] == ("unresolved", [66])
    assert calls["calls java.util.List.isEmpty"] == ("external", [30])
    assert [c["lines"][0] for c in facts.calls] == sorted(c["lines"][0] for c in facts.calls)


def test_callee_bodies_and_unavailable_body(builder):
    pkg, _ = builder.build(BUILD_VISITS, ExplainOptions(max_callee_depth=1))
    callee = {i.entity_id: i for i in pkg.items if i.kind in ("callee_source", "callee_signature")}
    assert callee[GROUP].kind == "callee_source" and "groupingBy" in callee[GROUP].content
    assert callee[VALIDATE].kind == "callee_source" and "new Visit(claimId)" in callee[VALIDATE].content
    # interface method: body is never inferred
    assert callee[SAVE_ALL].kind == "callee_signature" and callee[SAVE_ALL].status == "unavailable"
    assert "no implementation" in callee[SAVE_ALL].content
    # the unresolved call has no body evidence at all
    assert not any(i.kind.startswith("callee") and "audit" in i.title for i in pkg.items)


def test_non_accessor_callees_are_preferred(kb):
    cfg = kb.settings.method_explanation.model_copy(update={"max_callees_per_method": 3})
    pkg, _ = MethodEvidenceBuilder(kb, cfg).build(BUILD_VISITS, ExplainOptions(max_callee_depth=1))
    names = [i.title for i in pkg.items if i.kind in ("callee_source", "callee_signature")]
    assert not any("ClaimLine.get" in n or "ClaimLine.set" in n for n in names)
    assert any("not included" in w for w in pkg.warnings)


def test_depth_zero_means_selected_method_only(builder):
    pkg, _ = builder.build(BUILD_VISITS, ExplainOptions(max_callee_depth=0))
    assert not [i for i in pkg.items if i.kind.startswith("callee")]


def test_cycles_terminate(builder):
    pkg, _ = builder.build(PING_A, ExplainOptions(max_callee_depth=3))
    callee_ids = [i.entity_id for i in pkg.items if i.kind.startswith("callee")]
    assert callee_ids == [PING_B]  # pingB once; pingA (the selected method) never re-added


def test_fields_constants_and_sql(builder):
    pkg, _ = builder.build(f"java-method:{P}.VisitProcessor.loadBatch(java.lang.String)", ExplainOptions())
    fields = {i.title for i in by_kind(pkg, "field")}
    assert fields == {"field repository", "constant LOAD_SQL"}
    [sql] = by_kind(pkg, "sql_literal")
    assert sql.start_line == 14 and "SELECT claim_id" in sql.content
    pkg, _ = builder.build(f"java-method:{P}.VisitProcessor.loadBatch(java.lang.String)",
                           ExplainOptions(include_related_config=False, include_sql_evidence=False))
    assert {i.title for i in by_kind(pkg, "field")} == {"field repository"} and not by_kind(pkg, "sql_literal")


def test_callers_optional(builder):
    pkg, _ = builder.build(GROUP, ExplainOptions())
    assert not by_kind(pkg, "caller")
    pkg, _ = builder.build(GROUP, ExplainOptions(include_caller_context=True))
    assert [i.entity_id for i in by_kind(pkg, "caller")] == [BUILD_VISITS]


def test_deterministic_facts(builder):
    _, facts = builder.build(BUILD_VISITS, ExplainOptions())
    conds = {(c["line"], c["kind"]) for c in facts.conditions}
    assert {(30, "if"), (36, "filter"), (46, "loop"), (47, "if"), (49, "if"), (67, "catch")} <= conds
    assert any(c["text"].startswith("Stage 1") for c in facts.comments)


def test_unknown_and_invalid_ids(builder):
    with pytest.raises(MethodNotFoundError):
        builder.build("java-method:nope.X.y()", ExplainOptions())
    with pytest.raises(MethodNotFoundError):
        builder.build(f"java-class:{P}.VisitProcessor", ExplainOptions())  # not a method
    for bad in ["", "a\nb", "x" * 3000]:
        with pytest.raises(InvalidMethodIdError):
            builder.build(bad, ExplainOptions())


def test_missing_source_is_a_warning_not_content(tmp_path):
    kb = make_explain_kb(tmp_path, with_source=False)
    pkg, facts = MethodEvidenceBuilder(kb, kb.settings.method_explanation).build(BUILD_VISITS, ExplainOptions())
    assert not pkg.source_available and not by_kind(pkg, "method_source")
    assert "Insufficient evidence" in pkg.warnings[0] and not facts.comments
    assert by_kind(pkg, "method_metadata") and by_kind(pkg, "call")  # OKF facts still present


def test_stale_line_range_warns(tmp_path, kb):
    import shutil

    from codeknowledge.services.indexing_service import KnowledgeBase
    from tests.conftest import EXPLAIN_JAVA, EXPLAIN_OKF, make_settings

    src = tmp_path / "java"
    shutil.copytree(EXPLAIN_JAVA, src)
    f = src / "src/main/java/com/acme/visits/VisitProcessor.java"
    f.write_text(f.read_text().replace("public class VisitProcessor {", "public class VisitProcessor {\n\n\n\n\n", 1))
    s = make_settings(tmp_path / "idx", EXPLAIN_OKF)
    s.source.root_dir = str(src)
    kb2 = KnowledgeBase(s)
    kb2.load(rebuild=True, rebuild_vectors=False)
    pkg, _ = MethodEvidenceBuilder(kb2, s.method_explanation).build(BUILD_VISITS, ExplainOptions())
    [body] = by_kind(pkg, "method_source")
    assert body.content.splitlines()[3].startswith("33|")  # re-located, not fabricated
    assert any("changed since OKF generation" in w for w in pkg.warnings)


def test_path_traversal_in_resource_is_refused(tmp_path):
    from codeknowledge.models.entities import EntityType, OKFDocument
    from codeknowledge.source.reader import SourceReader

    doc = OKFDocument(id="m", path="m.md", title="m", type=EntityType.METHOD, method_name="m",
                      source_file="../../../etc/passwd", source_line=1)
    assert SourceReader(tmp_path).snippet(doc) is None


# ------------------------------------------------------------------ budget

def item(eid, kind, n_chars, priority):
    return EvidenceItem(evidence_id=eid, kind=kind, title=kind, priority=priority, content="x" * n_chars)


def test_budget_prioritises_selected_body_and_reports_omissions():
    pkg = EvidencePackage(method_id="m", method_signature="m()", method_title="m", source_available=True, items=[
        item("E1", "method_metadata", 100, 1), item("E2", "method_source", 3000, 0),
        item("E3", "callee_source", 3000, 5), item("E4", "call", 50, 3)])
    out = EvidenceBudgetManager(budget_tokens=2500, chars_per_token=3.5, max_items=30).apply(pkg)
    assert [i.evidence_id for i in out.items] == ["E1", "E2", "E4"]  # body kept, callee dropped
    assert out.omitted and "E3" in out.omitted[0] and any("omitted" in w for w in out.warnings)
    assert out.estimated_tokens <= 2500


def test_oversized_body_is_segmented_in_order_not_truncated(builder):
    pkg, _ = builder.build(BUILD_VISITS, ExplainOptions())
    body = next(i for i in pkg.items if i.kind == "method_source")
    out = EvidenceBudgetManager(budget_tokens=1400, chars_per_token=3.5, max_items=30).apply(pkg)
    segs = [i for i in out.items if i.kind == "source_segment"]
    assert out.segments == len(segs) > 1
    joined = "\n".join(s.content for s in segs)
    assert joined == body.content  # every line kept, in order
    assert [s.evidence_id for s in segs] == [f"E2.{n}" for n in range(1, len(segs) + 1)]
    assert segs[0].start_line == 25 and segs[-1].end_line == 73
    assert any("ordered parts" in w for w in out.warnings)


def test_budget_is_deterministic(builder):
    pkg, _ = builder.build(BUILD_VISITS, ExplainOptions())
    mgr = EvidenceBudgetManager(budget_tokens=3000, chars_per_token=3.5, max_items=10)
    assert [i.evidence_id for i in mgr.apply(pkg).items] == [i.evidence_id for i in mgr.apply(pkg).items]
