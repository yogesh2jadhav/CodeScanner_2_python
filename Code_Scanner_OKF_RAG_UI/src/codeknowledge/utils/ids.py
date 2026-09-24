"""Identifier helpers.

Why normalise: OKF IDs may come from frontmatter, file names or links; comparing
them via one canonical form avoids duplicate graph nodes for the same entity.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import PurePosixPath

_METHOD_PARENS = re.compile(r"\(.*\)$")


def normalize_id(raw: str) -> str:
    """Canonical entity id: trimmed, no trailing "()", '#' treated as '.'."""
    value = raw.strip().replace("#", ".")
    value = _METHOD_PARENS.sub("", value)
    return value.strip(". ")


def id_from_path(rel_path: str) -> str:
    """Fallback id when frontmatter has none: the file stem path, dot-separated."""
    p = PurePosixPath(rel_path)
    return ".".join(p.with_suffix("").parts)


def short_name(entity_id: str) -> str:
    return entity_id.rsplit(".", 1)[-1]


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def stable_hash(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()
