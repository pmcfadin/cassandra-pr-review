"""Changed-line coverage: JaCoCo report.xml joined with the lines a PR adds under src/java."""

import re
import subprocess
import xml.etree.ElementTree as ET

HUNK = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
SRC = re.compile(r"src/(?:java|gen-java)/(.*)$")


def added_lines(wt, base, head):
    """{path: [new-file line numbers]} for added lines of src/java/*.java between base and head."""
    out = subprocess.run(["git", "-C", wt, "diff", "-U0", "--no-renames", base, head, "--", "src/java"],
                         capture_output=True, text=True, check=True).stdout
    res, cur = {}, None
    for ln in out.splitlines():
        if ln.startswith("+++ "):
            p = ln[4:]
            cur = p[2:] if p.startswith("b/") and p.endswith(".java") else None
        elif ln.startswith("@@") and cur:
            m = HUNK.match(ln)
            start, n = int(m[1]), int(m[2]) if m[2] is not None else 1
            res.setdefault(cur, []).extend(range(start, start + n))
    return res


def jacoco_lines(report, wanted):
    """{'pkg/path/File.java': {nr: (mi, ci, mb, cb)}} for the wanted source files."""
    got = {}
    for _, el in ET.iterparse(report):
        if el.tag == "package":
            pkg = el.get("name")
            for sf in el.findall("sourcefile"):
                key = f"{pkg}/{sf.get('name')}"
                if key in wanted:
                    got[key] = {int(ln.get("nr")): tuple(int(ln.get(a)) for a in ("mi", "ci", "mb", "cb"))
                                for ln in sf.findall("line")}
            el.clear()
    return got


def classify(added, cov):
    """Split added line numbers into covered, partial (some instructions or branches never ran), missed, nonexec."""
    r = {"covered": [], "partial": [], "missed": [], "nonexec": [], "in_report": cov is not None}
    for n in added:
        d = cov.get(n) if cov else None
        if d is None:
            r["nonexec"].append(n)
            continue
        mi, ci, mb, cb = d
        if ci == 0 and cb == 0:
            r["missed"].append(n)
        elif mi or mb:
            r["partial"].append(n)
        else:
            r["covered"].append(n)
    return r


def changed_coverage(wt, base, head, report):
    """{files: {path: {...lists, in_report}}, total: {covered, partial, missed, nonexec, executable, pct_executed}}."""
    byrel = {}
    for path, nrs in added_lines(wt, base, head).items():
        m = SRC.match(path)
        if m:
            byrel[m[1]] = (path, nrs)
    cov = jacoco_lines(report, set(byrel))
    files, tot = {}, {"covered": 0, "partial": 0, "missed": 0, "nonexec": 0}
    for rel, (path, nrs) in byrel.items():
        files[path] = classify(nrs, cov.get(rel))
        for k in tot:
            tot[k] += len(files[path][k])
    ex = tot["covered"] + tot["partial"] + tot["missed"]
    tot["executable"] = ex
    tot["pct_executed"] = round(100 * (tot["covered"] + tot["partial"]) / ex, 1) if ex else None
    return {"files": files, "total": tot}
