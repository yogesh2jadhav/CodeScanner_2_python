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
    OVERRIDES = "OVERRIDES"


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
    "overrides": (RelationType.OVERRIDES, False),
    "overridden_by": (RelationType.OVERRIDES, True),
}

# Markdown section headings -> relationship. Kept separate from frontmatter keys
# because the same word can mean different things: a "Fields" section in Java2OKF
# links to the *types* of fields (USES), while a `fields:` key lists members.
_SECTION_ALIASES: dict[str, tuple[RelationType, bool]] = {
    **_REL_ALIASES,
    # Java2OKF method documents
    "declared_by": (RelationType.CONTAINS, True),
    "parameters": (RelationType.USES, False),
    "returns": (RelationType.USES, False),
    "throws": (RelationType.USES, False),
    "instantiates": (RelationType.USES, False),
    "used_by": (RelationType.USES, True),
    "referenced_by": (RelationType.REFERENCES, True),
    "initializer_calls": (RelationType.CALLS, False),
    "initializer_instantiations": (RelationType.USES, False),
    # Java2OKF type documents
    "package": (RelationType.CONTAINS, True),
    "enclosing_type": (RelationType.CONTAINS, True),
    "inheritance": (RelationType.EXTENDS, False),
    "subtypes": (RelationType.EXTENDS, True),
    "extended_/_implemented_by": (RelationType.IMPLEMENTS, True),
    "fields": (RelationType.USES, False),
    "constructors": (RelationType.CONTAINS, False),
    "nested_types": (RelationType.CONTAINS, False),
    "annotations": (RelationType.USES, False),
    "imports": (RelationType.DEPENDS_ON, False),
    # Java2OKF package documents
    "classes": (RelationType.CONTAINS, False),
    "interfaces": (RelationType.CONTAINS, False),
    "enums": (RelationType.CONTAINS, False),
    "records": (RelationType.CONTAINS, False),
    "dependents": (RelationType.DEPENDS_ON, True),
}


def parse_relation_type(raw: str) -> tuple[RelationType, bool] | None:
    key = raw.strip().lower().replace("-", "_").replace(" ", "_")
    try:
        return RelationType(key.upper()), False
    except ValueError:
        return _REL_ALIASES.get(key)


def parse_section_type(heading: str) -> tuple[RelationType, bool] | None:
    key = heading.strip().lower().replace("-", "_").replace(" ", "_")
    return _SECTION_ALIASES.get(key) or parse_relation_type(heading)


class Relationship(BaseModel):
    source: str
    target: str
    type: RelationType
    origin: str = "frontmatter"  # frontmatter | body_section | body_link | derived
    status: str = "resolved"  # resolved | unresolved | external
    line: int | None = None  # source line of the call/use when the OKF records it
