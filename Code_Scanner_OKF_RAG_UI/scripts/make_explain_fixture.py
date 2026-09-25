"""Hand-build a Java2OKF-format bundle for tests/fixtures/explain-java.

Used where no JVM is available; follows java2okf docs/okf-output.md. Method line ranges are
computed from the Java files; call-site lines below were verified against the source.
Prefer scripts/regen_explain_fixture.sh (real Java2OKF) when Java is installed.
Run from the project root: python scripts/make_explain_fixture.py
"""
import hashlib, os, re, shutil
SRC = "tests/fixtures/explain-java"
OUT = "tests/fixtures/explain-okf"
P = "com.acme.visits"
JDIR = f"src/main/java/com/acme/visits"
shutil.rmtree(OUT, ignore_errors=True)
for d in ("methods", "classes", "interfaces", "packages"):
    os.makedirs(f"{OUT}/{d}", exist_ok=True)

def lines_of(cls):
    return open(f"{SRC}/{JDIR}/{cls}.java").read().splitlines()

def span(cls, pattern):
    ls = lines_of(cls)
    start = next(i for i, l in enumerate(ls) if re.search(pattern, l))
    depth, opened = 0, False
    for j in range(start, len(ls)):
        code = re.sub(r'"[^"]*"', "", ls[j])
        if not opened and ";" in code and "{" not in code:
            return start + 1, j + 1
        for ch in code:
            if ch == "{": depth, opened = depth + 1, True
            elif ch == "}":
                depth -= 1
                if opened and depth == 0:
                    return start + 1, j + 1
    raise ValueError(pattern)

def h(eid): return hashlib.sha256(eid.encode()).hexdigest()[:6]
def mfile(cls, name, eid): return f"{P}.{cls}.{name}-{h(eid)}.md"
def cdir(kind): return {"class": "classes", "interface": "interfaces"}[kind]

TYPES = {"VisitProcessor": "class", "VisitRepository": "interface", "ClaimLine": "class", "Visit": "class",
         "VisitException": "class"}
METHODS = {}  # key -> dict

def method(cls, name, sig, ret, vis, pattern, ctor=False):
    eid = f"java-{'constructor' if ctor else 'method'}:{P}.{cls}{'' if ctor else '.' + name}({sig})"
    a, b = span(cls, pattern)
    key = f"{cls}.{name}({sig})"
    METHODS[key] = dict(cls=cls, name=name, sig=sig, ret=ret, vis=vis, id=eid, lines=(a, b), ctor=ctor,
                        file=mfile(cls, name, eid), calls=[], called_by=[], decl=lines_of(cls)[a - 1].strip().rstrip("{").strip())
    return key

L, S, LD = "java.util.List", "java.lang.String", "java.time.LocalDate"
k_ctor = method("VisitProcessor", "VisitProcessor", f"{P}.VisitRepository,{P}.AuditClient", None, "public", r"public VisitProcessor\(", ctor=True)
k_build = method("VisitProcessor", "buildVisits", f"{L},boolean", "List<Visit>", "public", r"buildVisits\(")
k_group = method("VisitProcessor", "groupByClaim", L, "Map<String,List<ClaimLine>>", "private", r"groupByClaim\(List")
k_val = method("VisitProcessor", "validate", f"{S},{L}", "Visit", "private", r"private Visit validate\(")
k_load = method("VisitProcessor", "loadBatch", S, "int", "package-private", r"int loadBatch\(")
k_a = method("VisitProcessor", "pingA", "int", "void", "package-private", r"void pingA\(")
k_b = method("VisitProcessor", "pingB", "int", "void", "package-private", r"void pingB\(")
k_save = method("VisitRepository", "saveAll", L, "void", "public", r"void saveAll\(")
k_count = method("VisitRepository", "count", f"{S},{S}", "int", "public", r"int count\(")
getters = {}
for nm, sig, ret, pat in [("getClaimId", "", "String", r"getClaimId\("), ("getFromDate", "", "LocalDate", r"getFromDate\("),
                          ("getToDate", "", "LocalDate", r"getToDate\("), ("getStartDate", "", "LocalDate", r"getStartDate\("),
                          ("setStartDate", LD, "void", r"void setStartDate\("), ("getEndDate", "", "LocalDate", r"getEndDate\("),
                          ("setEndDate", LD, "void", r"void setEndDate\("), ("setMissingEndFlag", "int", "void", r"setMissingEndFlag\(")]:
    getters[nm] = method("ClaimLine", nm, sig, ret, "public", pat)
k_visit = method("Visit", "Visit", S, None, "public", r"public Visit\(", ctor=True)
k_vstart = method("Visit", "setStartDate", LD, "void", "public", r"void setStartDate\(")
k_vend = method("Visit", "setEndDate", LD, "void", "public", r"void setEndDate\(")
k_exc = method("VisitException", "VisitException", S, None, "public", r"public VisitException\(", ctor=True)

def call(src, dst, *lines):
    METHODS[src]["calls"].append((dst, lines))
    if not dst.startswith("`"):
        METHODS[dst]["called_by"].append((src, lines))

ext = lambda t: f"`{t}` (external)"
call(k_build, ext("java.util.List.isEmpty()"), 30)
call(k_build, k_exc, 31, 68)
call(k_build, ext("java.util.Collection.stream()"), 35, 39)
call(k_build, getters["getStartDate"], 36)
call(k_build, ext("java.util.stream.Collectors.groupingBy(java.util.function.Function)"), 37)
call(k_build, getters["setStartDate"], 43)
call(k_build, getters["getEndDate"], 47)
call(k_build, getters["getToDate"], 48)
call(k_build, getters["setEndDate"], 48)
call(k_build, getters["setMissingEndFlag"], 50, 52)
call(k_build, k_group, 61)
call(k_build, k_val, 63)
call(k_build, ext("java.util.List.add(java.lang.Object)"), 63)
call(k_build, k_save, 65)
call(k_build, "`audit.record(..)` — UNRESOLVED", 66)
call(k_build, ext("java.util.List.size()"), 66, 71)
call(k_group, ext("java.util.Collection.stream()"), 76)
call(k_group, ext("java.util.stream.Collectors.groupingBy(java.util.function.Function)"), 76)
call(k_val, k_visit, 81)
call(k_val, k_vstart, 82)
call(k_val, getters["getStartDate"], 82)
call(k_val, k_vend, 83)
call(k_val, getters["getEndDate"], 83)
call(k_load, k_count, 88)
call(k_a, k_b, 93)
call(k_b, k_a, 98)

def link(key, from_dir="methods"):
    m = METHODS[key]
    label = (m["cls"] if m["ctor"] else f"{m['cls']}.{m['name']}") + "(" + ", ".join(
        p.rsplit(".", 1)[-1] for p in m["sig"].split(",") if p) + ")"
    return f"[{label}](./{m['file']})"

def lines_suffix(ls, at=False):
    word = "at line" if at else "line"
    return f" — {word} {ls[0]}" if len(ls) == 1 else f" — {'at lines' if at else 'lines'} {', '.join(map(str, ls))}"

for key, m in METHODS.items():
    t = TYPES[m["cls"]]
    cls_file = f"../{cdir(t)}/{P}.{m['cls']}.md"
    fm = [
        "---",
        f"type: {'JavaConstructor' if m['ctor'] else 'JavaMethod'}",
        f'id: "{m["id"]}"',
        f"title: {m['name']}",
        f"resource: {JDIR}/{m['cls']}.java",
        "tags:", "- java", f"- {'constructor' if m['ctor'] else 'method'}", f"- {P}",
        "generated:", "  by: java2okf/1.0.0",
        "java:",
        f"  declaringClass: {P}.{m['cls']}",
        f'  signature: "{m["name"] if not m["ctor"] else m["cls"]}({m["sig"]})"',
    ]
    if m["ret"]:
        fm.append(f"  returnType: {m['ret']}")
    fm += [f"  visibility: {m['vis']}", f"  lines: {m['lines'][0]}-{m['lines'][1]}", "---", ""]
    body = [f"# {m['name']}", "", "## Declared By", "", f"[{m['cls']}]({cls_file})", "", "## Signature", "", "```java",
            m["decl"], "```", "", "## Source", "", f"`{m['cls']}.java:{m['lines'][0]}-{m['lines'][1]}`", ""]
    if m["calls"]:
        body += ["## Calls", ""]
        for dst, ls in sorted(m["calls"], key=lambda c: c[1][0]):
            body.append("- " + (dst if dst.startswith("`") else link(dst)) + lines_suffix(ls))
        body.append("")
    if m["called_by"]:
        body += ["## Called By", ""]
        for src, ls in m["called_by"]:
            body.append("- " + link(src) + lines_suffix(ls, at=True))
        body.append("")
    body += ["## Resolution Status", "", "Statically resolvable relationships are recorded."]
    open(f"{OUT}/methods/{m['file']}", "w").write("\n".join(fm + body) + "\n")

for cls, kind in TYPES.items():
    a, b = span(cls, rf"(class|interface) {cls}\b")
    members = [k for k, m in METHODS.items() if m["cls"] == cls]
    fm = ["---", f"type: Java{kind.capitalize()}", f"id: java-{kind}:{P}.{cls}", f"title: {cls}",
          f"resource: {JDIR}/{cls}.java", "tags:", "- java", f"- {kind}", f"- {P}", "generated:", "  by: java2okf/1.0.0",
          "java:", f"  qualifiedName: {P}.{cls}", f"  package: {P}", f"  kind: {kind}", "  visibility: public",
          f"  lines: {a}-{b}", "---", ""]
    body = [f"# {cls}", "", "## Source", "", f"`{JDIR}/{cls}.java` (lines {a}–{b})", "", "## Package", "",
            f"[{P}](../packages/{P}.md)", ""]
    ctors = [k for k in members if METHODS[k]["ctor"]]
    meths = [k for k in members if not METHODS[k]["ctor"]]
    if ctors:
        body += ["## Constructors", ""] + [f"- [{METHODS[k]['cls']}(...)](../methods/{METHODS[k]['file']})" for k in ctors] + [""]
    if meths:
        body += ["## Methods", ""] + [f"- [{METHODS[k]['name']}(...)](../methods/{METHODS[k]['file']})" for k in meths] + [""]
    if cls == "VisitProcessor":
        body += ["## Fields", "", f"- `repository` — [VisitRepository](../interfaces/{P}.VisitRepository.md) · private final",
                 "- `audit` — `AuditClient` — UNRESOLVED · private final", "- `processedCount` — `int` · private", ""]
    open(f"{OUT}/{cdir(kind)}/{P}.{cls}.md", "w").write("\n".join(fm + body) + "\n")

pkg = ["---", "type: JavaPackage", f"id: java-package:{P}", f"title: {P}", "generated:", "  by: java2okf/1.0.0",
       "java:", f"  package: {P}", f'  types: "{len(TYPES)}"', "---", "", f"# {P}", "", "## Classes", ""]
pkg += [f"- [{c}](../classes/{P}.{c}.md)" for c, k in TYPES.items() if k == "class"] + ["", "## Interfaces", ""]
pkg += [f"- [{c}](../interfaces/{P}.{c}.md)" for c, k in TYPES.items() if k == "interface"]
open(f"{OUT}/packages/{P}.md", "w").write("\n".join(pkg) + "\n")
open(f"{OUT}/index.md", "w").write("---\ntype: Index\ntitle: Java Project Knowledge\ngenerated:\n  by: java2okf/1.0.0\n---\n\n# Java Project Knowledge\n\n- [Packages](packages/com.acme.visits.md)\n")
print(len(METHODS), "methods;", {k: v["lines"] for k, v in METHODS.items() if v["cls"] == "VisitProcessor"})
