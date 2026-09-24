from codeknowledge.models.entities import EntityType, normalize_entity_type
from codeknowledge.models.relationships import RelationType
from codeknowledge.okf.parser import PATH_TARGET_PREFIX, WIKI_LINK_PREFIX, parse_document, resolve_link, split_frontmatter
from codeknowledge.utils.ids import id_from_path, normalize_id, stable_hash


def test_split_frontmatter():
    fm, body = split_frontmatter("---\nid: x\n---\n# Title\nbody")
    assert fm == "id: x" and body.startswith("# Title")
    assert split_frontmatter("# no fm")[0] is None


def test_yaml_parsing_and_fields():
    text = """---
id: com.x.Foo
type: java_class
package: com.x
class_name: Foo
source_file: Foo.java
line: 12
summary: Does foo.
---
# Foo
"""
    r = parse_document(text, "classes/Foo.md")
    d = r.document
    assert not r.errors and not r.warnings
    assert d.id == "com.x.Foo" and d.type == EntityType.CLASS and d.raw_type == "java_class"
    assert d.source_file == "Foo.java" and d.source_line == 12 and d.summary == "Does foo."
    assert d.title == "Foo"  # from heading


def test_malformed_yaml_is_error_not_exception():
    r = parse_document("---\nid: [unclosed\n---\nbody", "bad.md")
    assert r.document is None and r.errors and "Malformed YAML" in r.errors[0]


def test_non_mapping_frontmatter():
    r = parse_document("---\n- a\n- b\n---\n", "list.md")
    assert r.document is None and "mapping" in r.errors[0]


def test_missing_frontmatter_is_warning_with_derived_id():
    r = parse_document("# Hello\n\nSome text.", "notes/hello.md")
    assert r.document.id == "notes.hello"
    assert r.document.type == EntityType.DOCUMENT
    assert r.warnings == ["Missing YAML frontmatter"]
    assert r.document.summary == "Some text."


def test_missing_optional_fields():
    r = parse_document("---\nid: a.B\n---\n", "B.md")
    d = r.document
    assert d.source_file is None and d.source_line is None and d.package is None and d.title == "B"


def test_id_composed_from_package_class_method():
    r = parse_document("---\ntype: method\npackage: p\nclass_name: C\nmethod_name: m\n---\n", "m.md")
    assert r.document.id == "p.C.m"
    assert any("derived id" in w for w in r.warnings)


def test_markdown_links_relative_resolution_and_code_blocks():
    body = """---
id: a.A
---
See [B](../other/B.md#sec) and [ext](https://example.com) and [anchor](#x).

```
[not a link](C.md)
```
[[a.D]]
"""
    d = parse_document(body, "dir/A.md").document
    assert d.links == ["other/B.md", WIKI_LINK_PREFIX + "a.D"]
    types = {(r.target, r.type) for r in d.relationships}
    assert (PATH_TARGET_PREFIX + "other/B.md", RelationType.REFERENCES) in types
    assert ("a.D", RelationType.REFERENCES) in types


def test_resolve_link():
    assert resolve_link("a/b/c.md", "../d.md") == "a/d.md"
    assert resolve_link("a/c.md", "http://x") is None
    assert resolve_link("a/c.md", "#top") is None
    assert resolve_link("a/c.md", "/root.md") == "root.md"


def test_frontmatter_relationship_forms():
    text = """---
id: p.A
extends: p.Base
implements: [p.I1, {id: p.I2}]
relationships:
  calls: [p.B.m]
  called_by: p.Z
  unknown_kind: p.Q
---
"""
    r = parse_document(text, "A.md")
    rels = {(x.source, x.target, x.type) for x in r.document.relationships}
    assert ("p.A", "p.Base", RelationType.EXTENDS) in rels
    assert ("p.A", "p.I1", RelationType.IMPLEMENTS) in rels
    assert ("p.A", "p.I2", RelationType.IMPLEMENTS) in rels
    assert ("p.A", "p.B.m", RelationType.CALLS) in rels
    assert ("p.Z", "p.A", RelationType.CALLS) in rels  # reversed
    assert any("unknown_kind" in w for w in r.warnings)


def test_relationships_as_list():
    text = "---\nid: p.A\nrelationships:\n  - {type: USES, target: p.X}\n  - 'DEPENDS_ON: p.Y'\n---\n"
    rels = {(x.target, x.type) for x in parse_document(text, "A.md").document.relationships}
    assert rels == {("p.X", RelationType.USES), ("p.Y", RelationType.DEPENDS_ON)}


def test_body_sections_become_typed_relationships():
    text = """---
id: p.A
---
## Calls
- [B](B.md)
- `p.C.run()`

## Called By
- [Z](Z.md)
"""
    rels = {(x.source, x.target, x.type, x.origin) for x in parse_document(text, "A.md").document.relationships}
    assert ("p.A", PATH_TARGET_PREFIX + "B.md", RelationType.CALLS, "body_section") in rels
    assert ("p.A", "p.C.run", RelationType.CALLS, "body_section") in rels
    assert (PATH_TARGET_PREFIX + "Z.md", "p.A", RelationType.CALLS, "body_section") in rels


def test_type_normalization():
    assert normalize_entity_type("Java_Class") == EntityType.CLASS
    assert normalize_entity_type("constructor") == EntityType.METHOD
    assert normalize_entity_type("weird") == EntityType.DOCUMENT
    assert normalize_entity_type(None) == EntityType.DOCUMENT


def test_id_helpers():
    assert normalize_id(" a.B#run() ") == "a.B.run"
    assert id_from_path("x/y/Z.md") == "x.y.Z"
    assert stable_hash("a", "b") != stable_hash("ab")
    assert stable_hash("a") == stable_hash("a")
