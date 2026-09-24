"""Core knowledge entities parsed from OKF."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from codeknowledge.models.relationships import Relationship


class EntityType(str, Enum):
    PACKAGE = "package"
    MODULE = "module"
    CLASS = "class"
    INTERFACE = "interface"
    ENUM = "enum"
    METHOD = "method"
    FIELD = "field"
    DOCUMENT = "document"
    UNRESOLVED = "unresolved"


# Why an alias table: Java2OKF versions and hand-written OKF use different type
# spellings ("java_class", "Class", "constructor"); mapping them once here keeps
# every downstream component working with a single closed vocabulary.
_TYPE_ALIASES: dict[str, EntityType] = {
    "package": EntityType.PACKAGE,
    "java_package": EntityType.PACKAGE,
    "module": EntityType.MODULE,
    "java_module": EntityType.MODULE,
    "class": EntityType.CLASS,
    "java_class": EntityType.CLASS,
    "abstract_class": EntityType.CLASS,
    "record": EntityType.CLASS,
    "interface": EntityType.INTERFACE,
    "java_interface": EntityType.INTERFACE,
    "enum": EntityType.ENUM,
    "java_enum": EntityType.ENUM,
    "method": EntityType.METHOD,
    "java_method": EntityType.METHOD,
    "constructor": EntityType.METHOD,
    "function": EntityType.METHOD,
    "field": EntityType.FIELD,
    "java_field": EntityType.FIELD,
    "property": EntityType.FIELD,
}


def normalize_entity_type(raw: Any) -> EntityType:
    if raw is None:
        return EntityType.DOCUMENT
    key = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    return _TYPE_ALIASES.get(key, EntityType.DOCUMENT)


class OKFDocument(BaseModel):
    """One OKF Markdown document. OKF stays canonical; this is a parsed view of it."""

    id: str
    path: str  # posix path relative to the OKF root
    title: str
    type: EntityType
    raw_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    content: str = ""
    links: list[str] = Field(default_factory=list)  # resolved relative .md paths or raw wiki targets
    relationships: list[Relationship] = Field(default_factory=list)

    package: str | None = None
    class_name: str | None = None
    method_name: str | None = None
    source_file: str | None = None
    source_line: int | None = None
    summary: str | None = None
    signature: str | None = None

    def display_name(self) -> str:
        if self.type == EntityType.METHOD and self.class_name and self.method_name:
            return f"{self.class_name}.{self.method_name}"
        return self.title


class EntitySummary(BaseModel):
    """Lightweight entity view returned by APIs (no filesystem paths beyond the OKF-relative doc path)."""

    id: str
    title: str
    type: EntityType
    package: str | None = None
    class_name: str | None = None
    method_name: str | None = None
    document: str | None = None
    source_file: str | None = None
    source_line: int | None = None
    summary: str | None = None
    status: str = "resolved"

    @classmethod
    def from_document(cls, doc: OKFDocument) -> "EntitySummary":
        return cls(
            id=doc.id,
            title=doc.display_name(),
            type=doc.type,
            package=doc.package,
            class_name=doc.class_name,
            method_name=doc.method_name,
            document=doc.path,
            source_file=doc.source_file,
            source_line=doc.source_line,
            summary=doc.summary,
        )
