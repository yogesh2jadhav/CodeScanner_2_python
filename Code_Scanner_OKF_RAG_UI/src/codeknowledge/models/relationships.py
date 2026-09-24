"""Relationship vocabulary."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class RelationType(str, Enum):
    CALLS = "CALLS"
    DEPENDS_ON = "DEPENDS_ON"
    EXTENDS = "EXTENDS"
    IMPLEMENTS = "IMPLEMENTS"
    USES = "USES"
    CONTAINS = "CONTAINS"
    BELONGS_TO = "BELONGS_TO"
    REFERENCES = "REFERENCES"


_REL_ALIASES: dict[str, tuple[RelationType, bool]] = {
    # alias -> (type, reversed). "called_by: X" means X CALLS this entity.
    "calls": (RelationType.CALLS, False),
    "call": (RelationType.CALLS, False),
    "invokes": (RelationType.CALLS, False),
    "callees": (RelationType.CALLS, False),
    "called_by": (RelationType.CALLS, True),
    "callers": (RelationType.CALLS, True),
    "depends_on": (RelationType.DEPENDS_ON, False),
    "dependencies": (RelationType.DEPENDS_ON, False),
    "imports": (RelationType.DEPENDS_ON, False),
    "extends": (RelationType.EXTENDS, False),
    "superclass": (RelationType.EXTENDS, False),
    "inherits": (RelationType.EXTENDS, False),
    "implements": (RelationType.IMPLEMENTS, False),
    "implemented_by": (RelationType.IMPLEMENTS, True),
    "uses": (RelationType.USES, False),
    "uses_types": (RelationType.USES, False),
    "fields": (RelationType.CONTAINS, False),
    "contains": (RelationType.CONTAINS, False),
    "methods": (RelationType.CONTAINS, False),
    "members": (RelationType.CONTAINS, False),
    "belongs_to": (RelationType.BELONGS_TO, False),
    "references": (RelationType.REFERENCES, False),
    "see_also": (RelationType.REFERENCES, False),
    "related": (RelationType.REFERENCES, False),
}


def parse_relation_type(raw: str) -> tuple[RelationType, bool] | None:
    key = raw.strip().lower().replace("-", "_").replace(" ", "_")
    try:
        return RelationType(key.upper()), False
    except ValueError:
        return _REL_ALIASES.get(key)


class Relationship(BaseModel):
    source: str
    target: str
    type: RelationType
    origin: str = "frontmatter"  # frontmatter | body_section | body_link | derived
    status: str = "resolved"  # resolved | unresolved
