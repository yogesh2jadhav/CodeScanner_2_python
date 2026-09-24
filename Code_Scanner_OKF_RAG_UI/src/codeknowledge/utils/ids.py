"""Identifier helpers.

Why normalise: OKF IDs may come from frontmatter, file names or links; comparing
them via one canonical form avoids duplicate graph nodes for the same entity.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import PurePosixPath

_EMPTY_PARENS = re.compile(r"\(\s*\)$")
_PARAMS = re.compile(r"\(.*\)$")
_KIND_PREFIX = re.compile(r"^[a-z][a-z0-9-]*:(?!//)")  # e.g. "java-method:" (Java2OKF)


def normalize_id(raw: str) -> str:
    """Canonical entity id: trimmed, '#' treated as '.', trailing empty "()" removed.

    Why parameter lists are kept: Java2OKF ids include the signature
    ("…placeOrder(com.example.Customer,double)") and that is the only thing that
    keeps overloaded methods apart. Only a bare "()" is dropped (user shorthand).
    """
    value = raw.strip().replace("#", ".")
    value = _EMPTY_PARENS.sub("", value)
    return value.strip(". ")


def strip_kind_prefix(entity_id: str) -> str:
    """"java-method:com.x.A.m(int)" -> "com.x.A.m(int)"."""
    return _KIND_PREFIX.sub("", entity_id)


def base_name(entity_id: str) -> str:
    """Id without kind prefix and parameter list: "java-method:com.x.A.m(int)" -> "com.x.A.m"."""
    return _PARAMS.sub("", strip_kind_prefix(entity_id))


def simplify_params(signature: str) -> str:
    """"m(com.example.Customer,double)" -> "m(Customer, double)" for display."""
    m = re.match(r"^(.*?)\((.*)\)$", signature)
    if not m:
        return signature
    params = [p.strip().rsplit(".", 1)[-1] for p in m.group(2).split(",") if p.strip()]
    return f"{m.group(1)}({', '.join(params)})"


def id_from_path(rel_path: str) -> str:
    """Fallback id when frontmatter has none: the file stem path, dot-separated."""
    p = PurePosixPath(rel_path)
    return ".".join(p.with_suffix("").parts)


def short_name(entity_id: str) -> str:
    base = base_name(entity_id)
    name = base.rsplit(".", 1)[-1]
    return name + "()" if base != strip_kind_prefix(entity_id) else name


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def stable_hash(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()
