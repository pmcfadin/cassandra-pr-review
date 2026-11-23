"""Pick unit test classes for a PR: tests it changes, FooTest name matches, references to changed code.

Textual signals only (see docs/research/build-and-coverage.md section 3); JaCoCo is the real check.
`wt` is a checkout of the PR head; git runs with the base and head shas it is given. `select` is apache/cassandra's
layout (src/java, test/unit); `select_gradle` is a Gradle multi-module layout (<module>/src/{main,test}/java).
"""

import os
import re
import subprocess

SRC_RE = re.compile(r"src/(java|gen-java)/.*\.java$")
DECL = re.compile(r"^\s{4}(?:@\w+\s+)*(?:(?:public|protected|private|static|final|synchronized|abstract|default)\s+)*"
                  r"(?:<[^>]+>\s+)?[\w<>\[\],.? ]+?\s+(\w+)\s*\(")
NOT_METHODS = ("if", "for", "while", "switch", "catch", "return", "new", "synchronized")
EXTENDS = re.compile(r"\b(?:class|interface|enum)\s+(\w+)[^{;]*?\b(?:extends|implements)\s+([^{]+)\{", re.S)
HUNK = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
GRADLE_MAIN = re.compile(r"^(?:(.+)/)?src/main/java/(.+\.java)$")
GRADLE_TEST = re.compile(r"^(?:(.+)/)?src/test/java/(.+\.java)$")
GRADLE_PATHSPEC = (":(glob)**/src/main/java/**", ":(glob)src/main/java/**")


def git(wt, *args):
    return subprocess.run(["git", "-C", wt, *args], capture_output=True, text=True, check=True).stdout


def _read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def _is_test(text):
    return "@Test" in text or "extends CQLTester" in text or "@RunWith" in text  # skips abstract bases


def _unit_index(wt):
    root = os.path.join(wt, "test", "unit")
    index = {}
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith("Test.java"):
                p = os.path.join(dp, f)
                index[os.path.relpath(p, root)] = _read(p)
    return index


def _changed_methods(wt, base, head, pathspec=("src/java",)):
    """Name of the nearest method declaration above each added line of the production sources."""
    methods, cur, cache = set(), None, {}
    for ln in git(wt, "diff", "-U0", "--no-renames", base, head, "--", *pathspec).splitlines():
        if ln.startswith("+++ "):
            cur = ln[6:] if ln.endswith(".java") else None
        m = HUNK.match(ln)
        if m and cur and (m[2] is None or int(m[2]) > 0):
            if cur not in cache:
                cache[cur] = git(wt, "show", f"{head}:{cur}").splitlines()
            lines = cache[cur]
            for i in range(int(m[1]) - 1, -1, -1):
                d = DECL.match(lines[i]) if i < len(lines) else None
                if d and d[1] not in NOT_METHODS:
                    methods.add(d[1])
                    break
    return methods


def _subtypes(wt, classes, roots=(os.path.join("src", "java"),)):
    """One hop of subclasses and implementors in the production roots (SSTable -> SSTableReader, SSTableWriter)."""
    subs = {}
    if not classes:
        return subs
    for dp, _, fs in (w for r in roots for w in os.walk(os.path.join(wt, r))):
        for f in fs:
            if not f.endswith(".java"):
                continue
            with open(os.path.join(dp, f), encoding="utf-8", errors="replace") as fh:
                text = fh.read(60000)
            for m in EXTENDS.finditer(text):
                for name in re.findall(r"\w+", re.sub(r"<[^>]*>", "", m[2])):
                    if name in classes and m[1] not in classes:
                        subs.setdefault(m[1], set()).add(name)
    return subs


def _changed(wt, base, head):
    return [ln.split("\t") for ln in git(wt, "diff", "--name-status", "--no-renames", base, head).splitlines()]


def select(wt, base, head, cfg):
    """{selected: [{path, score, reasons}], skipped, changed_src_classes, ...}; paths are relative to test/unit."""
    changed = _changed(wt, base, head)
    src = [p for s, p in changed if s != "D" and SRC_RE.match(p)]
    classes = sorted({os.path.basename(p)[:-5] for p in src})
    tests_touched = [p for s, p in changed if s != "D" and p.endswith(".java") and p.startswith("test/")]
    unit = [p[len("test/unit/"):] for p in tests_touched if p.startswith("test/unit/") and p.endswith("Test.java")]
    non_unit = [p for p in tests_touched if not (p.startswith("test/unit/") and p.endswith("Test.java"))]

    def read(rel):
        return _read(os.path.join(wt, "test", "unit", rel))

    return _rank(cfg["selection"], _unit_index(wt), classes, unit, non_unit, _changed_methods(wt, base, head),
                 _subtypes(wt, classes), read)


def gradle_modules(wt, projects):
    """[(module dir, Gradle path)] from cprProjects' {path: dir}, deepest dir first so nested modules win."""
    return sorted(((d, p) for p, d in projects.items() if d not in ("", ".")), key=lambda dp: -len(dp[0]))


def module_of(path, modules):
    """The Gradle project path owning a repository path, or ":" for the root project."""
    for d, p in modules:
        if path.startswith(d.rstrip("/") + "/"):
            return p
    return ":"


def select_gradle(wt, base, head, cfg, projects, skip_modules=()):
    """Like `select` for a Gradle layout; paths are relative to the repository root and each pick names its `module`.

    `projects` is {Gradle path: project dir}; `skip_modules` are project dirs whose tests are not unit tests.
    """
    modules = gradle_modules(wt, projects)
    skipped_dirs = tuple(d.rstrip("/") + "/" for d in skip_modules)
    is_skipped = lambda p: p.startswith(skipped_dirs)  # noqa: E731
    changed = _changed(wt, base, head)
    src = [p for s, p in changed if s != "D" and GRADLE_MAIN.match(p) and not is_skipped(p)]
    classes = sorted({os.path.basename(p)[:-5] for p in src})
    tests_touched = [p for s, p in changed if s != "D" and p.endswith(".java") and "/src/" in "/" + p
                     and not GRADLE_MAIN.match(p)]
    unit = [p for p in tests_touched if GRADLE_TEST.match(p) and p.endswith("Test.java") and not is_skipped(p)]
    non_unit = [p for p in tests_touched if p not in unit]
    dirs = [d for d, _ in modules if not is_skipped(d + "/")] + [""]
    index = {}
    for d in dirs:  # a module's src/test/java never holds a nested module's sources
        for dp, _, fs in os.walk(os.path.join(wt, d, "src", "test", "java")):
            for f in fs:
                if f.endswith("Test.java"):
                    index[os.path.relpath(os.path.join(dp, f), wt)] = _read(os.path.join(dp, f))
    roots = [os.path.join(d, "src", "main", "java") for d in dirs]
    res = _rank(cfg["selection"], index, classes, unit, non_unit, _changed_methods(wt, base, head, GRADLE_PATHSPEC),
                _subtypes(wt, classes, roots), lambda rel: _read(os.path.join(wt, rel)))
    for c in res["selected"]:
        c["module"] = module_of(c["path"], modules)
    return res


def _rank(sel_cfg, index, classes, unit_touched, non_unit, methods, subs, read):
    """Score candidate test classes; `index` is {test path: text}, `read(path)` reads one not in the index."""
    cand = {}

    def add(rel, pts, why):
        c = cand.setdefault(rel, {"path": rel, "score": 0, "reasons": []})
        c["score"] += pts
        c["reasons"].append(why)

    skipped = {"non_unit": list(non_unit), "not_a_test": []}
    for p in unit_touched:
        add(p, 1000, "changed by PR")
    pr_tests = len(unit_touched)
    for c in classes:
        for rel in index:
            b = os.path.basename(rel)[:-5]
            if b == c + "Test":
                add(rel, 500, f"FooTest name: {c}")
            elif re.fullmatch(re.escape(c) + r"[A-Z]\w*Test", b):
                add(rel, 15, f"name prefix: {c}")
    pat = lambda n: re.compile(r"\b" + re.escape(n) + r"\b")  # noqa: E731
    cpat = {c: pat(c) for c in classes if len(c) > 3}
    spat = {c: pat(c) for c in subs}
    mpat = [re.compile(r"[.\s]" + re.escape(m) + r"\s*\(") for m in sorted(methods)] if len(methods) < 60 else []
    # hub classes (referenced by more than 8% of all tests) say nothing about relevance
    hubs = sorted(c for c, p in cpat.items() if sum(1 for t in index.values() if p.search(t)) > 0.08 * max(1, len(index)))
    cpat = {c: p for c, p in cpat.items() if c not in hubs}
    for rel, txt in index.items():
        hits = {c: len(p.findall(txt)) for c, p in cpat.items()}
        hits = {c: n for c, n in hits.items() if n}
        if hits:
            add(rel, min(30, 2 * sum(hits.values())), "references " + ",".join(sorted(hits, key=hits.get, reverse=True)[:3]))
            mh = sum(len(p.findall(txt)) for p in mpat)
            if mh:
                add(rel, min(30, 5 * mh), f"calls changed method(s) ({mh} hits)")
        sh = {c: len(p.findall(txt)) for c, p in spat.items()}
        sh = {c: n for c, n in sh.items() if n}
        if sh:
            add(rel, min(15, sum(sh.values())), "references subtype " + ",".join(sorted(sh, key=sh.get, reverse=True)[:3]))
    for rel in list(cand):
        text = index.get(rel)
        if text is None:
            try:
                text = read(rel)
            except OSError:
                text = ""
        if not _is_test(text):
            skipped["not_a_test"].append(rel)
            del cand[rel]
    ranked = sorted(cand.values(), key=lambda c: (-c["score"], c["path"]))
    cap = sel_cfg["cap_with_pr_tests"] if pr_tests else sel_cfg["cap"]
    chosen = [c for c in ranked if c["score"] >= sel_cfg["min_score"]][:cap]
    return {"changed_src_classes": classes, "hub_classes_ignored": hubs, "changed_methods": sorted(methods),
            "subtypes": {k: sorted(v) for k, v in subs.items()}, "total_candidates": len(cand),
            "selected": chosen, "dropped": len(ranked) - len(chosen), "unit_test_files": len(index),
            "skipped": skipped}


def class_name(path):
    """org/apache/cassandra/Foo.java or server/src/test/java/org/apache/Foo.java -> org.apache.cassandra.Foo"""
    m = GRADLE_TEST.match(path)
    return (m[2] if m else path)[:-5].replace("/", ".")
