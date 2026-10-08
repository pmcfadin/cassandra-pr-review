"""Pick unit test classes for a PR: tests it changes, FooTest name matches, references to changed code.

Textual signals only (see docs/research/build-and-coverage.md section 3); JaCoCo is the real check.
`wt` is a checkout of the PR head; git runs with the base and head shas it is given.
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


def _changed_methods(wt, base, head):
    """Name of the nearest method declaration above each added line of src/java."""
    methods, cur, cache = set(), None, {}
    for ln in git(wt, "diff", "-U0", "--no-renames", base, head, "--", "src/java").splitlines():
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


def _subtypes(wt, classes):
    """One hop of subclasses and implementors in src (SSTable -> SSTableReader, SSTableWriter)."""
    subs = {}
    if not classes:
        return subs
    for dp, _, fs in os.walk(os.path.join(wt, "src", "java")):
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


def select(wt, base, head, cfg):
    """{selected: [{path, score, reasons}], skipped, changed_src_classes, ...}; paths are relative to test/unit."""
    sel_cfg = cfg["selection"]
    changed = [ln.split("\t") for ln in git(wt, "diff", "--name-status", "--no-renames", base, head).splitlines()]
    src = [p for s, p in changed if s != "D" and SRC_RE.match(p)]
    classes = sorted({os.path.basename(p)[:-5] for p in src})
    tests_touched = [p for s, p in changed if s != "D" and p.endswith(".java") and p.startswith("test/")]
    index = _unit_index(wt)
    cand = {}

    def add(rel, pts, why):
        c = cand.setdefault(rel, {"path": rel, "score": 0, "reasons": []})
        c["score"] += pts
        c["reasons"].append(why)

    skipped = {"non_unit": [], "not_a_test": []}
    pr_tests = 0
    for p in tests_touched:
        if p.startswith("test/unit/") and p.endswith("Test.java"):
            add(p[len("test/unit/"):], 1000, "changed by PR")
            pr_tests += 1
        else:
            skipped["non_unit"].append(p)
    for c in classes:
        for rel in index:
            b = os.path.basename(rel)[:-5]
            if b == c + "Test":
                add(rel, 500, f"FooTest name: {c}")
            elif re.fullmatch(re.escape(c) + r"[A-Z]\w*Test", b):
                add(rel, 15, f"name prefix: {c}")
    methods = _changed_methods(wt, base, head)
    subs = _subtypes(wt, classes)
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
                text = _read(os.path.join(wt, "test", "unit", rel))
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
    """org/apache/cassandra/Foo.java -> org.apache.cassandra.Foo"""
    return path[:-5].replace("/", ".")
