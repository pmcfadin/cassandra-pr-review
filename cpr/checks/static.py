"""Advisory static checks over added lines. `ant check` (not run here) stays authoritative."""

import re
import xml.etree.ElementTree as ET

from cpr.checks import Result, check, ev

_LICENSE_MARKER = "Licensed to the Apache Software Foundation"
_PERMIT_RE = re.compile(r"checkstyle:\s*permit", re.IGNORECASE)
_DEPRECATED_RE = re.compile(r"@Deprecated\b(?!\s*\([^)]*\bsince\b)")
_LICENSED_EXT = (".java", ".py", ".sh", ".xml", ".g", ".yaml", ".yml", ".properties")


def banned_rules(checkstyle_xml):
    """Rules from .build/checkstyle.xml: [{id, kind, regex, message}]."""
    if not checkstyle_xml:
        return []
    try:
        root = ET.fromstring(checkstyle_xml)
    except ET.ParseError:
        return []
    rules = []
    for module in root.iter("module"):
        props = {p.get("name"): p.get("value") for p in module.findall("property")}
        name = module.get("name")
        if name == "RegexpSinglelineJava" and props.get("format"):
            try:
                rx = re.compile(props["format"])
            except re.error:
                continue
            rules.append({"id": props.get("id") or "regexp", "kind": "regexp", "regex": rx,
                          "message": props.get("message") or props["format"]})
        elif name == "IllegalImport":
            for cls in filter(None, (props.get("illegalClasses") or "").split(",")):
                rules.append({"id": "IllegalImport", "kind": "import",
                              "regex": re.compile(rf"^\s*import\s+(static\s+)?{re.escape(cls.strip())}\s*;"),
                              "message": f"illegal import {cls.strip()}"})
            for pkg in filter(None, (props.get("illegalPkgs") or "").split(",")):
                rules.append({"id": "IllegalImport", "kind": "import",
                              "regex": re.compile(rf"^\s*import\s+(static\s+)?{re.escape(pkg.strip())}\."),
                              "message": f"illegal import from {pkg.strip()}"})
        elif name == "IllegalInstantiation":
            for cls in filter(None, (props.get("classes") or "").split(",")):
                simple = cls.strip().rsplit(".", 1)[-1]
                rules.append({"id": "IllegalInstantiation", "kind": "new",
                              "regex": re.compile(rf"\bnew\s+(?:{re.escape(cls.strip())}|{re.escape(simple)})\s*[(<]"),
                              "message": f"do not instantiate {cls.strip()}"})
    return rules


def _sa(bundle):
    return bundle.get("static_analysis")


def _checkstyle_ran(bundle):
    sa = _sa(bundle)
    return bool(sa) and ((sa.get("tools") or {}).get("checkstyle") or {}).get("status") == "ran"


def _approx(r):
    """Label a regex-scan result as an approximation of checkstyle (no real checkstyle ran)."""
    if r.status != "not-applicable":
        r.summary += " (approximation of checkstyle from the diff; real checkstyle did not run)"
    return r


def _gate(bundle, tool, allow_partial=False):
    """(analysis, tool_info, early Result or None). Never lets a check pass without proof.

    With allow_partial, a run that analyzed only some files returns no early result; the caller reports
    what it found and must not pass (see _partial).
    """
    sa = _sa(bundle)
    if not sa:
        return None, None, Result("unknown", "static analysis did not run")
    if sa.get("status") != "ran":
        reason = sa.get("reason") or "static analysis unavailable"
        if reason == "no changed Java files":
            return sa, None, Result("not-applicable", "No changed Java files")
        return sa, None, Result("unknown", reason)
    t = (sa.get("tools") or {}).get(tool) or {}
    st = t.get("status")
    ver = f" ({tool} {t['version']})" if t.get("version") else ""
    if st == "not-applicable":
        return sa, t, Result("not-applicable", t.get("reason") or f"{tool} does not apply to this PR")
    if st != "ran":
        return sa, t, Result("unknown", (t.get("reason") or f"{tool} did not run (status {st})") + ver)
    exp, got = t.get("files_expected"), t.get("files_analyzed")
    if exp is not None and got is not None and got < exp and not (allow_partial and got > 0):
        return sa, t, Result("unknown", f"{tool} analyzed {got} of {exp} changed files; {exp - got} not analyzed")
    return sa, t, None


def _intro(f):
    return str(f.get("classification") or "").startswith("introduced")


def _where(f):
    return f"{f.get('file')}:{f.get('line')}" if f.get("line") else str(f.get("file"))


@check("static.checkstyle", "Checkstyle passes on changed files", "static", "static", blocking=False)
def checkstyle(bundle, ctx):
    sa, t, early = _gate(bundle, "checkstyle")
    if early:
        return early
    fs = sa.get("checkstyle") or []
    intro = [f for f in fs if _intro(f)]
    fixed = [f for f in fs if f.get("classification") == "fixed"]
    pre = [f for f in fs if not _intro(f) and f.get("classification") != "fixed"]
    ver = f"checkstyle {t.get('version')}" if t.get("version") else "checkstyle"
    counts = [ev(f"{len(pre)} pre-existing error(s) in touched files, {len(fixed)} fixed")]
    if intro:
        rows = [ev(f"`{_where(f)}` {f.get('rule')}: {f.get('message')}", location=_where(f)) for f in intro[:50]]
        return Result("warn", f"{len(intro)} checkstyle error(s) introduced ({ver}); `ant check` would fail",
                      rows + counts, action_required=True,
                      action="Fix each error, or add a suppression comment that explains why; run `ant checkstyle` "
                             "and `ant checkstyle-test` to confirm.")
    return Result("pass", f"No checkstyle errors introduced ({ver})", counts)




def _partial(t):
    """'N of M changed files could not be analyzed: a, b' when a tool skipped files, else None."""
    exp, got = (t or {}).get("files_expected"), (t or {}).get("files_analyzed")
    if exp is None or got is None or got >= exp:
        return None
    names = (t.get("reason") or "").split(": ", 1)[-1]
    return f"{exp - got} of {exp} changed files could not be analyzed" + (f": {names}" if names else "")


def _sig(m):
    return f"{m.get('class')}.{m.get('method_sig')}"


@check("static.complexity", "Cognitive complexity of changed methods", "static", "static", blocking=False)
def complexity(bundle, ctx):
    sa, t, early = _gate(bundle, "pmd", allow_partial=True)
    if early:
        return early
    partial = _partial(t)
    cx = sa.get("complexity") or {}
    thr = cx.get("threshold", 15)
    methods = sorted(cx.get("methods") or [],
                     key=lambda m: (not str(m.get("classification", "")).startswith("introduced"),
                                    str(m.get("file")), _sig(m)))
    rows = []  # per-method scores are in the report's Method complexity table (model["complexity"])
    intro = [f for f in cx.get("findings") or [] if _intro(f)]
    over = sorted((f for f in intro if f.get("rule") == "CognitiveComplexity" and (f.get("score") or 0) >= thr),
                  key=lambda f: -(f.get("score") or 0))
    bad = [f for f in over if not str(f.get("file", "")).startswith("test/")]
    in_tests = len(over) - len(bad)
    if in_tests:
        rows.insert(0, ev(f"{in_tests} test method(s) introduced at or above {thr} (not counted in the headline)"))
    other = {}
    for f in intro:
        if f.get("rule") != "CognitiveComplexity":
            other[f.get("rule")] = other.get(f.get("rule"), 0) + 1
    if other:
        rows.insert(0, ev("Also introduced above PMD's thresholds: "
                          + ", ".join(f"{n} {r}" for r, n in sorted(other.items()))))
    if partial:
        rows.insert(0, ev(f"PMD skipped some files ({partial}); they are not scored"))
    if bad:
        top = "; ".join(f"`{f.get('class')}.{f.get('method_sig')}` {f.get('score')}" for f in bad[:5])
        return Result("warn", f"{len(bad)} production method(s) introduced at or above cognitive complexity {thr}: {top}",
                      rows, action_required=False,
                      action=f"Consider splitting the method(s) to keep cognitive complexity under {thr}.")
    if partial:
        return Result("unknown", f"No production method introduced at or above cognitive complexity {thr} in the "
                                 f"files PMD could read; {partial}", rows,
                      action="PMD reads source without the compile classpath and could not resolve some types; "
                             "check the skipped files by hand or run PMD with the classpath.")
    return Result("pass", f"No production method introduced at or above cognitive complexity {thr} "
                          f"({len(methods)} changed method(s) listed)", rows)


RED_CATEGORIES = ("errorprone", "multithreading", "security")


def pmd_rules_rows(sa):
    """Introduced PMD catalog violations outside house style: [(rule, category, production count, test count)]."""
    out = []
    for r in (sa.get("pmd_rules") or {}).get("rules") or []:
        if r.get("house") or not r.get("introduced"):
            continue
        prod = r["introduced"] - r.get("in_tests", 0)
        out.append((r["rule"], r.get("category"), prod, r.get("in_tests", 0)))
    return out


@check("static.pmd-rules", "No bug-finding PMD rule violations introduced", "static", "static", blocking=False)
def pmd_rules(bundle, ctx):
    sa, t, early = _gate(bundle, "pmd", allow_partial=True)
    if early:
        return early
    pr = sa.get("pmd_rules") or {}
    if pr.get("status") != "ran":
        return Result("unknown", pr.get("reason") or "PMD's rule catalog did not run on this head")
    partial = _partial(t)
    rows = [ev(pr.get("type_note") or "PMD ran without type info")] if not pr.get("type_info") else []
    base = pr.get("baseline") or {}
    if base.get("source") == "touched-files":
        rows.append(ev("House style was judged from the touched files only: " + (base.get("note") or "no branch baseline")))
    if partial:
        rows.insert(0, ev(f"PMD skipped some files ({partial}); they are not scored"))
    rest = pmd_rules_rows(sa)
    red = sorted((r for r in rest if r[1] in RED_CATEGORIES and r[2] > 0), key=lambda r: (-r[2], r[0]))
    other = sum(r[2] for r in rest if r[1] not in RED_CATEGORIES)
    if red:
        n = sum(r[2] for r in red)
        top = ", ".join(f"{r[0]} {r[2]}" for r in red[:5])
        rows.append(ev(f"{other} more introduced in Performance, Best Practices, Design, Code Style and Documentation"))
        return Result("warn", f"{n} bug-finding PMD violation(s) introduced in production code ({len(red)} rule(s)): {top}",
                      rows, action_required=False,
                      action="Open the PMD rules block in Code style for each rule's file and line, and fix or justify each.")
    if partial:
        return Result("unknown", f"No bug-finding PMD violation introduced in the files PMD could read; {partial}", rows,
                      action="Check the skipped files by hand.")
    return Result("pass", f"No Error Prone, Multithreading or Security PMD violation introduced in production code "
                          f"({other} lower-severity violation(s) introduced, see the PMD rules block)", rows)


@check("static.duplication", "No duplicated code introduced", "static", "static", blocking=False)
def duplication(bundle, ctx):
    sa, t, early = _gate(bundle, "cpd")
    if early:
        return early
    intro = [d for d in sa.get("duplication") or [] if d.get("introduced")]
    if not intro:
        return Result("pass", "No introduced duplicate blocks (CPD)")
    rows = []
    for d in intro:
        occ = ", ".join(f"`{o.get('file')}:{o.get('line')}-{o.get('endline')}`" for o in d.get("occurrences") or [])
        rows.append(ev(f"{d.get('tokens')} tokens, {d.get('lines')} lines: {occ}"))
    return Result("warn", f"{len(intro)} duplicate block(s) introduced (CPD)", rows, action_required=False,
                  action="Extract the shared code if the duplication is not deliberate.")


def _is_comment(text):
    s = text.strip()
    return s.startswith(("//", "*", "/*"))


@check("static.banned-api", "No checkstyle-banned APIs in added code", "static", "static", blocking=False)
def banned_api(bundle, ctx):
    if _checkstyle_ran(bundle):
        return Result("not-applicable", "superseded by static.checkstyle")
    return _approx(_banned_api(bundle, ctx))


def _banned_api(bundle, ctx):
    xml = bundle["base_files"].get("checkstyle_xml")
    if xml is None:
        return Result("not-applicable", f"The base branch `{ctx.pr['base']}` has no `.build/checkstyle.xml`")
    rules = banned_rules(xml)
    if not rules:
        return Result("unknown", "Could not parse `.build/checkstyle.xml` from the base branch")
    hits = []
    for path, info in ctx.added.items():
        if not (path.startswith("src/java/") and path.endswith(".java")):
            continue
        lines = info["added"]
        for idx, (n, text) in enumerate(lines):
            if _is_comment(text) or _PERMIT_RE.search(text):
                continue
            if idx > 0 and _PERMIT_RE.search(lines[idx - 1][1]):
                continue
            for r in rules:
                if r["regex"].search(text):
                    hits.append(ev(f"`{path}:{n}` {r['id']}: {r['message']}", location=f"{path}:{n}"))
                    break
    if hits:
        return Result("warn", f"{len(hits)} added line(s) match checkstyle bans", hits[:50],
                      action="Use the project alternative named in each message, or run `ant checkstyle` to confirm.")
    return Result("pass", f"No added line matches the {len(rules)} checkstyle ban rules")


@check("static.license-header", "New files carry the Apache licence header", "static", "static", blocking=False)
def license_header(bundle, ctx):
    missing = []
    for path, info in ctx.added.items():
        if not info["new_file"] or not path.endswith(_LICENSED_EXT) or path.startswith("test/resources/"):
            continue
        head = "\n".join(t for _, t in info["added"][:30])
        if _LICENSE_MARKER not in head:
            missing.append(ev(f"`{path}`", location=path))
    if missing:
        return Result("warn", f"{len(missing)} new file(s) lack the Apache licence header", missing,
                      action="Copy the ASF licence header from any existing source file; `ant check` runs the RAT licence check.")
    return Result("pass", "Every new source file has the licence header")


@check("static.protected-paths", "No edits to generated code or bundled jars", "static", "static", blocking=False)
def protected_paths(bundle, ctx):
    hits = [ev(f"`{p}`", location=p) for p in ctx.paths if p.startswith(("src/gen-java/", "lib/"))]
    grammar = [ev(f"`{p}` (CQL grammar: discuss on dev@ first)", location=p) for p in ctx.paths if p.startswith("src/antlr/")]
    if hits:
        return Result("warn", "Edits under `src/gen-java/` or `lib/`", hits + grammar,
                      action="Generated code is rebuilt by the build; dependencies change through the build POM "
                             "templates with a dev@ discussion.")
    if grammar:
        return Result("warn", "CQL grammar changed", grammar, action_required=False,
                      action="Grammar changes need a dev@ discussion and a CQL docs update.")
    return Result("pass", "No generated, bundled, or grammar files touched")


@check("static.deprecated-since", "@Deprecated has since=", "static", "static", blocking=False)
def deprecated_since(bundle, ctx):
    if _checkstyle_ran(bundle):
        return Result("not-applicable", "superseded by static.checkstyle")
    return _approx(_deprecated_since(bundle, ctx))


def _deprecated_since(bundle, ctx):
    hits = []
    for path, info in ctx.added.items():
        if path.endswith(".java"):
            for n, text in info["added"]:
                if _DEPRECATED_RE.search(text) and not _is_comment(text):
                    hits.append(ev(f"`{path}:{n}`", location=f"{path}:{n}"))
    if hits:
        return Result("warn", f"{len(hits)} @Deprecated without `since`", hits,
                      action='Write `@Deprecated(since = "X.Y")`; checkstyle requires it.')
    return Result("pass", "No new @Deprecated without since")
