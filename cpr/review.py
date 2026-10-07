"""Merge code review lens outputs with the rustyrazorblade spec-flow panel rules.

* A lens with no valid output is `missing` (or `invalid`) and never counts as approval.
* A lens that declines without a blocker/major finding gets a synthesized `major` finding,
  rule `unexplained-non-approval`: declining is a verdict and has to be justified.
* A finding that names an impact (and confidence) gets its severity from a fixed table.
* The panel approves only when every lens ran, every lens approved, and nothing must be fixed.
* Findings that several lenses report about one problem are merged into issues (cpr/merge.py);
  approval is unaffected, must-fix counts count issues.
"""

import json
import os

from cpr import merge as merge_mod

PANEL = os.path.join(os.path.dirname(__file__), "config", "panel.json")
SEVERITIES = ("blocker", "major", "minor", "nit")
MUST_FIX = ("blocker", "major")
IMPACTS = ("data-loss", "crash", "hang", "mixed-version-break", "silent-wrong-result", "performance", "cosmetic")
CONFIDENCES = ("high", "medium", "low")
# Severity follows impact and confidence, not the lens's mood. Values are for (high, medium, low).
SEVERITY_TABLE = {
    "data-loss": ("blocker", "major", "minor"),
    "crash": ("blocker", "major", "minor"),
    "hang": ("blocker", "major", "minor"),
    "mixed-version-break": ("blocker", "major", "minor"),
    "silent-wrong-result": ("major", "major", "minor"),
    "performance": ("minor", "minor", "nit"),
    "cosmetic": ("nit", "nit", "nit"),
}
_FINDING_KEYS = ("id", "severity", "location", "rule", "problem", "fix")


def load_panel(path=PANEL):
    with open(path) as f:
        return json.load(f)["lenses"]


def _extract_json(text):
    """Lenses are told to output JSON only; tolerate a fenced block or surrounding prose."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def validate_output(data):
    """Return an error string, or None when `data` matches the review schema."""
    if not isinstance(data, dict):
        return "output is not a JSON object"
    if not isinstance(data.get("approve"), bool):
        return "missing boolean `approve`"
    if not isinstance(data.get("findings"), list):
        return "missing `findings` list"
    for i, f in enumerate(data["findings"]):
        if not isinstance(f, dict):
            return f"findings[{i}] is not an object"
        for k in _FINDING_KEYS:
            if not isinstance(f.get(k), str):
                return f"findings[{i}].{k} missing or not a string"
        if f["severity"] not in SEVERITIES:
            return f"findings[{i}].severity '{f['severity']}' is not one of {', '.join(SEVERITIES)}"
        for key, allowed in (("impact", IMPACTS), ("confidence", CONFIDENCES)):
            if f.get(key) is not None and f[key] not in allowed:
                return f"findings[{i}].{key} '{f[key]}' is not one of {', '.join(allowed)}"
    return None


def derive_severity(f):
    """Return `f` with its severity taken from the impact/confidence table when it names an impact.

    When the lens's severity differs, the table value wins and `severity_corrected: {from, to}` records
    the change. A finding without an impact, or with an impact that needs a confidence it lacks, keeps
    the lens's severity.
    """
    impact, confidence = f.get("impact"), f.get("confidence")
    if impact is None or (impact != "cosmetic" and confidence is None):
        return f
    to = SEVERITY_TABLE[impact][CONFIDENCES.index(confidence) if confidence else 0]
    if to == f["severity"]:
        return f
    return dict(f, severity=to, severity_corrected={"from": f["severity"], "to": to})


def read_checklists(lens_dir):
    """{sha} from `<lens_dir>/../lens-plan.json` (written by `cpr prepare`), or None."""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(lens_dir)), "lens-plan.json")) as f:
            sha = json.load(f)["checklists"]["sha"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return {"sha": sha} if isinstance(sha, str) and sha else None


def merge(lens_dir, panel=None):
    """Read `<lens_dir>/<name>.json` for every lens in the panel and merge them."""
    panel = panel or load_panel()
    lenses = []
    for spec in panel:
        name, agent = spec["name"], spec["agent"]
        entry = {"name": name, "agent": agent, "status": "missing", "approve": False, "summary": "",
                 "spec_conformance": None, "tests_ran": None, "tests_detail": None, "findings": [], "error": None}
        path = os.path.join(lens_dir, f"{name}.json")
        if not os.path.exists(path):
            entry["error"] = "the lens produced no output"
            lenses.append(entry)
            continue
        try:
            with open(path) as f:
                data = _extract_json(f.read())
        except (json.JSONDecodeError, ValueError) as e:
            entry.update(status="invalid", error=f"not JSON: {e}")
            lenses.append(entry)
            continue
        err = validate_output(data)
        if err:
            entry.update(status="invalid", error=err)
            lenses.append(entry)
            continue
        findings = sorted((derive_severity(f) for f in data["findings"]), key=lambda f: SEVERITIES.index(f["severity"]))
        if not data["approve"] and not any(f["severity"] in MUST_FIX for f in findings):
            findings.insert(0, {
                "id": f"unexplained-{name}", "severity": "major", "location": f"({name} lens report)",
                "rule": "unexplained-non-approval",
                "problem": f"{name} lens returned approve=false with no blocker or major finding "
                           f"(summary: {data.get('summary') or 'none given'})",
                "fix": "Re-review and either approve, or report a specific blocking finding.",
            })
        entry.update(status="ran", approve=data["approve"], summary=data.get("summary") or "",
                     spec_conformance=data.get("spec_conformance"), tests_ran=data.get("tests_ran"),
                     tests_detail=data.get("tests_detail"), findings=findings)
        lenses.append(entry)

    flat = [dict(f, lens=l["name"]) for l in lenses for f in l["findings"]]
    complete = all(l["status"] == "ran" for l in lenses)
    approved = complete and all(l["approve"] for l in lenses) and not any(f["severity"] in MUST_FIX for f in flat)
    counts = {s: sum(1 for f in flat if f["severity"] == s) for s in SEVERITIES}
    issues = merge_mod.merge_findings(flat)
    issue_counts = {s: sum(1 for i in issues if i["severity"] == s) for s in SEVERITIES}
    return {"status": "ran", "complete": complete, "approved": approved, "counts": counts,
            "issues": issues, "issue_counts": issue_counts,
            "must_fix": sum(1 for i in issues if i["severity"] in MUST_FIX),
            "checklists": read_checklists(lens_dir), "lenses": lenses}


def explain_notes(review):
    """{path: [markdown lines]} for merged issues whose location names a file, for the diff view.

    One line per issue per file, naming every lens that reported it.
    """
    notes = {}
    if not review:
        return notes
    for issue in merge_mod.issues_of(review):
        by_path = {}
        for loc in issue["locations"]:
            if loc.startswith("(") or "/" not in loc:
                continue
            by_path.setdefault(loc.split(":", 1)[0].strip(), []).append(loc)
        for path, locs in by_path.items():
            notes.setdefault(path, []).append(
                f"- **[{issue['severity']}] {', '.join(issue['lenses'])}: {issue['rule']}** "
                f"({', '.join(locs)}): {issue['problem']} Fix: {issue['fix']}")
    return notes
