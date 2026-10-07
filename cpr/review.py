"""Merge code review lens outputs with the rustyrazorblade spec-flow panel rules.

* A lens with no valid output is `missing` (or `invalid`) and never counts as approval.
* A lens that declines without a blocker/major finding gets a synthesized `major` finding,
  rule `unexplained-non-approval`: declining is a verdict and has to be justified.
* The panel approves only when every lens ran, every lens approved, and nothing must be fixed.
"""

import json
import os

PANEL = os.path.join(os.path.dirname(__file__), "config", "panel.json")
SEVERITIES = ("blocker", "major", "minor", "nit")
MUST_FIX = ("blocker", "major")
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
    return None


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
        findings = sorted(data["findings"], key=lambda f: SEVERITIES.index(f["severity"]))
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

    complete = all(l["status"] == "ran" for l in lenses)
    must_fix = [f for l in lenses for f in l["findings"] if f["severity"] in MUST_FIX]
    approved = complete and all(l["approve"] for l in lenses) and not must_fix
    counts = {s: sum(1 for l in lenses for f in l["findings"] if f["severity"] == s) for s in SEVERITIES}
    return {"status": "ran", "complete": complete, "approved": approved, "counts": counts, "lenses": lenses}


def explain_notes(review):
    """{path: [markdown lines]} for findings whose location names a file, for the diff view."""
    notes = {}
    for lens in (review or {}).get("lenses", []):
        for f in lens["findings"]:
            loc = f["location"]
            if loc.startswith("(") or "/" not in loc:
                continue
            path = loc.split(":", 1)[0].strip()
            notes.setdefault(path, []).append(f"- **[{f['severity']}] {lens['name']}: {f['rule']}** "
                                              f"({loc}): {f['problem']} Fix: {f['fix']}")
    return notes
