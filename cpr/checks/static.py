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


def _is_comment(text):
    s = text.strip()
    return s.startswith(("//", "*", "/*"))


@check("static.banned-api", "No checkstyle-banned APIs in added code", "static", "static", blocking=False)
def banned_api(bundle, ctx):
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
