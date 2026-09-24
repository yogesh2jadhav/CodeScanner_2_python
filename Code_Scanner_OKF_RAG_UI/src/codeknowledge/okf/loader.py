"""Discover and load an OKF bundle directory."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from codeknowledge.models.entities import OKFDocument
from codeknowledge.okf.parser import parse_document
from codeknowledge.utils.ids import stable_hash
from codeknowledge.utils.logging import get_logger
from codeknowledge.utils.timing import timed

logger = get_logger("OKFLoader")

MISSING_DIR_MESSAGE = "OKF source directory does not exist.\nConfigure okf.source_dir."


class OKFSourceMissingError(FileNotFoundError):
    def __init__(self, path: str):
        super().__init__(f"{MISSING_DIR_MESSAGE} (path: {path})")
        self.path = path


@dataclass
class DocumentIssue:
    path: str
    level: str  # warning | error
    message: str


@dataclass
class IngestionReport:
    discovered: int = 0
    valid: int = 0
    warnings: int = 0
    errors: int = 0
    links: int = 0
    issues: list[DocumentIssue] = field(default_factory=list)

    def render(self) -> str:
        return (
            f"Documents discovered: {self.discovered}\n"
            f"Valid: {self.valid}\n"
            f"Warnings: {self.warnings}\n"
            f"Errors: {self.errors}\n"
            f"Links discovered: {self.links}"
        )


@dataclass
class LoadResult:
    documents: list[OKFDocument]
    report: IngestionReport
    bundle_hash: str
    frontmatter_present: dict[str, bool] = field(default_factory=dict)


class OKFLoader:
    def __init__(self, source_dir: str | Path):
        self.source_dir = Path(source_dir)

    def discover(self) -> list[Path]:
        if not self.source_dir.is_dir():
            raise OKFSourceMissingError(str(self.source_dir))
        return sorted(p for p in self.source_dir.rglob("*.md") if p.is_file())

    def load(self) -> LoadResult:
        logger.info("Loading OKF bundle")
        report = IngestionReport()
        docs: list[OKFDocument] = []
        fm_present: dict[str, bool] = {}
        hash_parts: list[str] = []
        with timed(logger, "okf_load"):
            files = self.discover()
            report.discovered = len(files)
            for path in files:
                rel = path.relative_to(self.source_dir).as_posix()
                try:
                    text = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as exc:
                    report.errors += 1
                    report.issues.append(DocumentIssue(rel, "error", f"Unreadable file: {exc}"))
                    logger.warning("Skipping unreadable document %s: %s", rel, exc)
                    continue
                hash_parts.extend([rel, text])
                result = parse_document(text, rel)
                fm_present[rel] = result.has_frontmatter
                for w in result.warnings:
                    report.issues.append(DocumentIssue(rel, "warning", w))
                for e in result.errors:
                    report.issues.append(DocumentIssue(rel, "error", e))
                if result.errors or result.document is None:
                    report.errors += 1
                    logger.warning("Skipping invalid document %s: %s", rel, "; ".join(result.errors))
                    continue
                if result.warnings:
                    report.warnings += 1
                else:
                    report.valid += 1
                report.links += len(result.document.links)
                docs.append(result.document)
        logger.info("Loaded %d documents (valid=%d warnings=%d errors=%d links=%d)",
                    len(docs), report.valid, report.warnings, report.errors, report.links)
        # Why hash content: the bundle hash is the knowledge-base version used to
        # invalidate indexes and the answer cache whenever any OKF file changes.
        return LoadResult(docs, report, stable_hash(*hash_parts), fm_present)
