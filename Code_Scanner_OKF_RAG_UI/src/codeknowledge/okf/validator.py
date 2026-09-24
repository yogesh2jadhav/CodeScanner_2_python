"""OKF bundle validation rules."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from codeknowledge.okf.loader import OKFLoader
from codeknowledge.okf.parser import PATH_TARGET_PREFIX, WIKI_LINK_PREFIX
from codeknowledge.okf.repository import OKFRepository
from codeknowledge.utils.ids import normalize_id
from codeknowledge.utils.logging import get_logger

logger = get_logger("OKFValidator")


@dataclass
class ValidationIssue:
    rule: str
    level: str  # error | warning
    path: str
    message: str


@dataclass
class ValidationReport:
    documents: int = 0
    valid: int = 0
    broken_links: int = 0
    duplicate_ids: int = 0
    unresolved_relationships: int = 0
    external_references: int = 0
    orphans: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def passed(self) -> bool:
        return not self.errors

    def render(self, verbose: bool = False, max_issues: int = 200) -> str:
        lines = [
            "OKF Validation",
            "-------------",
            f"Documents: {self.documents}",
            f"Valid: {self.valid}",
            f"Broken links: {self.broken_links}",
            f"Duplicate IDs: {self.duplicate_ids}",
            f"Unresolved relationships: {self.unresolved_relationships}",
            f"External references (JDK/libraries): {self.external_references}",
            f"Orphan documents: {self.orphans}",
            f"Errors: {len(self.errors)}",
            f"Warnings: {len(self.warnings)}",
            f"Status: {'PASS' if self.passed else 'FAIL'}",
        ]
        if self.unresolved_relationships:
            top = Counter(i.message.split("'")[1] for i in self.issues
                          if i.rule == "unresolved_relationship" and "'" in i.message).most_common(10)
            lines.append("")
            lines.append("Most frequent unresolved targets:")
            lines.extend(f"  {count:6}  {target}" for target, count in top)
        if verbose and self.issues:
            # Errors first, and a cap: a large bundle can produce tens of thousands of warnings.
            ordered = self.errors + self.warnings
            lines.append("")
            lines.append(f"Issues (showing {min(len(ordered), max_issues)} of {len(ordered)}):")
            for i in ordered[:max_issues]:
                lines.append(f"  [{i.level.upper()}] {i.rule} {i.path}: {i.message}")
        return "\n".join(lines)


class OKFValidator:
    """Rules: frontmatter exists, required metadata, malformed YAML, unique IDs,
    links resolve, referenced files exist, orphan documents, unresolved relationships.
    """

    def __init__(self, source_dir: str | Path, required_metadata: list[str] | None = None):
        self.source_dir = Path(source_dir)
        self.required_metadata = required_metadata or ["id", "type"]

    def validate(self) -> ValidationReport:
        load = OKFLoader(self.source_dir).load()
        repo = OKFRepository(load)
        report = ValidationReport(documents=load.report.discovered)
        bad_paths: set[str] = set()

        def add(rule: str, level: str, path: str, msg: str) -> None:
            report.issues.append(ValidationIssue(rule, level, path, msg))
            if level == "error":
                bad_paths.add(path)

        for issue in load.report.issues:
            if issue.level == "error":
                rule = "malformed_yaml" if "YAML" in issue.message else "invalid_document"
                add(rule, "error", issue.path, issue.message)

        for path, present in load.frontmatter_present.items():
            if not present:
                add("frontmatter_missing", "error", path, "Document has no YAML frontmatter")

        for doc in load.documents:
            if not load.frontmatter_present.get(doc.path, True) or doc.navigation:
                continue
            missing = [k for k in self.required_metadata if doc.metadata.get(k) in (None, "")]
            if missing:
                add("required_metadata", "error", doc.path, f"Missing required metadata: {', '.join(missing)}")

        for dup_id, paths in repo.duplicates.items():
            report.duplicate_ids += 1
            first = repo.by_id[dup_id].path
            for p in paths:
                add("duplicate_id", "error", p, f"Duplicate id '{dup_id}' (first defined in {first})")

        linked_paths: set[str] = set()
        for doc in load.documents:
            for link in doc.links:
                if link.startswith(WIKI_LINK_PREFIX):
                    if repo.resolve(normalize_id(link[len(WIKI_LINK_PREFIX):]), doc.id) is None:
                        report.broken_links += 1
                        add("broken_link", "error", doc.path, f"Wiki link target not found: {link[len(WIKI_LINK_PREFIX):]}")
                    continue
                if link.startswith(".."):
                    report.broken_links += 1
                    add("broken_link", "error", doc.path, f"Link escapes OKF root: {link}")
                    continue
                target = self.source_dir / link
                if not target.exists():
                    report.broken_links += 1
                    rule = "broken_link" if link.endswith(".md") else "missing_referenced_file"
                    add(rule, "error", doc.path, f"Link target does not exist: {link}")
                else:
                    linked_paths.add(link)

        rels = repo.relationships()
        connected: set[str] = set()
        for rel in rels:
            connected.update((rel.source, rel.target))
            if rel.status == "external":
                report.external_references += 1
                continue
            if rel.status == "unresolved" and rel.origin != "body_link":
                report.unresolved_relationships += 1
                src_doc = repo.get(rel.source)
                path = src_doc.path if src_doc else (repo.get(rel.target).path if repo.get(rel.target) else "?")
                missing = rel.target if rel.target not in repo.by_id else rel.source
                add("unresolved_relationship", "warning", path,
                    f"{rel.type.value} target '{missing.removeprefix(PATH_TARGET_PREFIX)}' not found (kept as unresolved)")

        # Why orphans are warnings: an isolated doc is suspicious (e.g. a missed link)
        # but not invalid — a leaf utility class may legitimately have no edges.
        for doc in repo.content_documents:
            if doc.id not in connected and doc.path not in linked_paths and not doc.links:
                report.orphans += 1
                add("orphan_document", "warning", doc.path, "Document has no relationships or links")

        report.valid = sum(1 for p in load.frontmatter_present if p not in bad_paths)
        log = logger.info if report.passed else logger.warning
        log("Validation finished documents=%d errors=%d warnings=%d status=%s",
            report.documents, len(report.errors), len(report.warnings), "PASS" if report.passed else "FAIL")
        return report
