"""Render browser-test fixtures from the real 5201 report model.

Usage: PYTHONPATH=<repo root> python3 tests/browser/build_fixture.py <out_dir>

Writes <out_dir>/report.html (the 5201 model as-is), <out_dir>/hostile.html (the same model with
script-shaped text in the PR title, a check's evidence, the PR body, and a JIRA comment), and variants
of 5201 for lens status, lab plan, build, and an unreviewed PR with nothing to do.
"""

import copy
import json
import os
import sys

from cpr import render

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL = os.path.join(REPO, "tests", "fixtures", "models", "5201.json")

HOSTILE_TITLE = '<!--<script>window.PWNED=1</script>'
HOSTILE_EVIDENCE = '</script><img src=x onerror="window.PWNED=1">'


def load_model():
    with open(MODEL) as f:
        return json.load(f)


def hostile(model):
    m = copy.deepcopy(model)
    m["pr"]["title"] = HOSTILE_TITLE
    m["pr"]["body"] = HOSTILE_EVIDENCE + "\n" + HOSTILE_TITLE
    m["checks"][0]["evidence"] = [{"text": HOSTILE_EVIDENCE}, {"text": "[click](javascript:window.PWNED=1)"},
                                  {"text": "link", "url": "javascript:window.PWNED=1"}]
    m["checks"][0]["summary"] = HOSTILE_TITLE
    ticket = (m.get("jira") or {}).get("ticket")
    if ticket and ticket.get("comments"):
        ticket["comments"][0]["body"] = HOSTILE_EVIDENCE
    return m


def lens_status(model):
    """5201 with one lens missing, one approved with no findings, and a pinned checklist sha."""
    m = copy.deepcopy(model)
    rv = m["review"]
    rv["checklists"] = {"sha": "0123456789abcdef0123456789abcdef01234567"}
    by_name = {l["name"]: l for l in rv["lenses"]}
    by_name["observability"].update(status="missing", approve=False, findings=[], error="the lens produced no output",
                                    summary="")
    by_name["security"].update(status="ran", approve=True, findings=[])
    rv["complete"] = False
    return m


def no_plan(model):
    """5201 as if it were a docs-only PR: the Lab plan section explains why there is no plan."""
    m = copy.deepcopy(model)
    m["lab_plan"] = {"status": "none", "reason": "documentation-only change", "scenarios": [], "dropped": [],
                     "markdown": "", "filename": None}
    sec = next(s for s in m["sections"] if s["id"] == "labplan")
    sec.update(status="not-applicable", summary="No lab plan: documentation-only change")
    return m


def unreviewed(model):
    """5201 with every requirement met and code review not run: nothing to do, review still pending."""
    m = copy.deepcopy(model)
    for c in m["checks"]:
        if c["status"] in ("warn", "fail", "unknown"):
            c.update(status="pass", action=None, action_required=False)
    m["recommendation"] = {"verdict": "requirements-met-unreviewed", "label": "Requirements met — code not yet reviewed",
                           "reasons": [], "waiting_on": []}
    for sec in m["sections"]:
        if sec["status"] in ("warn", "fail", "unknown"):
            sec["status"] = "pass"
    return m


def with_build(model, run):
    """5201 with the Build & coverage section filled from a saved `cpr build` result (or not built when None)."""
    from cpr import buildresult, checks as checks_mod, model as model_mod
    from cpr.checks import build as _build  # noqa: F401  (registers the build.* checks)
    m = copy.deepcopy(model)
    head = m["pr"]["head_sha"]
    run = {**run, "head": head} if run else buildresult.not_built()
    bundle = {"pr": {"head_sha": head}, "build": run}
    for spec in [c for c in checks_mod.REGISTRY if c["id"].startswith("build.")]:
        r = spec["fn"](bundle, None)
        m["checks"].append({"id": spec["id"], "title": spec["title"], "category": spec["category"], "aspect": spec["aspect"],
                            "blocking": spec["blocking"] if r.blocking is None else r.blocking, "owner": spec["owner"],
                            "status": r.status, "summary": r.summary, "evidence": r.evidence,
                            "action": r.action if r.status not in ("pass", "not-applicable") else None,
                            "action_required": r.status in ("fail", "warn") if r.action_required is None else r.action_required})
    mine = [c for c in m["checks"] if c["id"].startswith("build.")]
    live = [c["status"] for c in mine if c["status"] != "not-applicable"]
    status = "not-applicable" if run["status"] == "not-built" else (
        min(live, key=lambda x: model_mod._RANK[x]) if live else "info")
    sec = {"id": "build", "title": "Build & coverage", "status": status, "docs": ["build"], "checks": [c["id"] for c in mine]}
    ids = [x["id"] for x in m["sections"]]
    m["sections"].insert(ids.index("testing") + 1, sec)
    m["build"] = {**run, "author_is_committer": False}
    with open(os.path.join(REPO, "docs", "report", "build.md")) as f:
        m["docs"]["build"] = f.read()
    return m


def load_build_run():
    with open(os.path.join(REPO, "tests", "fixtures", "build", "5201-status.json")) as f:
        return json.load(f)


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    model = load_model()
    render.write(model, os.path.join(out_dir, "report.html"))
    render.write(hostile(model), os.path.join(out_dir, "hostile.html"))
    render.write(lens_status(model), os.path.join(out_dir, "lens-status.html"))
    render.write(no_plan(model), os.path.join(out_dir, "labplan-none.html"))
    render.write(with_build(model, load_build_run()), os.path.join(out_dir, "build.html"))
    render.write(with_build(model, None), os.path.join(out_dir, "build-none.html"))
    render.write(unreviewed(model), os.path.join(out_dir, "unreviewed.html"))
    print(json.dumps({"build": os.path.join(out_dir, "build.html"), "build_none": os.path.join(out_dir, "build-none.html"),
                      "report": os.path.join(out_dir, "report.html"), "hostile": os.path.join(out_dir, "hostile.html"),
                      "lens_status": os.path.join(out_dir, "lens-status.html"),
                      "labplan_none": os.path.join(out_dir, "labplan-none.html"),
                      "unreviewed": os.path.join(out_dir, "unreviewed.html"),
                      "hostile_title": HOSTILE_TITLE, "hostile_evidence": HOSTILE_EVIDENCE}))


if __name__ == "__main__":
    main(sys.argv[1])
