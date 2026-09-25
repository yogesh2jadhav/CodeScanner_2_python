"""Retrieval representation of an OKF document.

Why not embed raw Markdown: generated OKF bodies are dominated by boilerplate
(tables, link lists). A compact header of title/type/names/package/summary/
relationships puts the most discriminative signals first and within the
embedding model's context window.
"""
from __future__ import annotations

from codeknowledge.models.entities import OKFDocument
from codeknowledge.models.relationships import Relationship
from codeknowledge.utils.ids import short_name

# Kept short: the header already lists names, summary and relationships, and long
# inputs make CPU embedding slow (nomic-embed-text truncates beyond its context anyway).
MAX_CONTENT_CHARS = 800


MAX_COMMENT_CHARS = 1500


def build_retrieval_text(doc: OKFDocument, relationships: list[Relationship], comments: str | None = None) -> str:
    rel_lines: dict[str, list[str]] = {}
    for r in relationships:
        if r.source == doc.id:
            rel_lines.setdefault(r.type.value, []).append(short_name(r.target))
        elif r.target == doc.id and r.type.value == "CALLS":
            rel_lines.setdefault("CALLED_BY", []).append(short_name(r.source))
    parts = [
        f"Title: {doc.display_name()}",
        f"Type: {doc.type.value}",
    ]
    if doc.class_name:
        parts.append(f"Class: {doc.class_name}")
    if doc.method_name:
        parts.append(f"Method: {doc.method_name}")
    if doc.signature:
        parts.append(f"Signature: {doc.signature}")
    if doc.package:
        parts.append(f"Package: {doc.package}")
    if doc.summary:
        parts.append(f"Summary: {doc.summary}")
    for rtype, targets in sorted(rel_lines.items()):
        parts.append(f"{rtype}: {', '.join(sorted(set(targets))[:20])}")
    if comments:
        # Developer comments carry the business vocabulary ("discharge date", "casing")
        # that structure-only OKF lacks; they make the method findable by meaning.
        parts.append("Comments: " + comments[:MAX_COMMENT_CHARS])
    if doc.content:
        parts.append("Content: " + doc.content[:MAX_CONTENT_CHARS])
    return "\n".join(parts)


def build_metadata(doc: OKFDocument) -> dict[str, str | int]:
    meta = {
        "entity_id": doc.id,
        "entity_type": doc.type.value,
        "title": doc.display_name(),
        "class_name": doc.class_name,
        "method_name": doc.method_name,
        "package": doc.package,
        "source_file": doc.source_file,
        "source_line": doc.source_line,
        "document": doc.path,
    }
    # Chroma rejects None metadata values.
    return {k: v for k, v in meta.items() if v is not None}
