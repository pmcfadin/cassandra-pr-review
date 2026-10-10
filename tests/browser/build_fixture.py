"""Render browser-test fixtures from the real 5201 report model.

Usage: PYTHONPATH=<repo root> python3 tests/browser/build_fixture.py <out_dir>

Writes <out_dir>/report.html (the 5201 model as-is) and <out_dir>/hostile.html (the same model with
script-shaped text in the PR title, a check's evidence, the PR body, and a JIRA comment).
"""

import copy
import json
import os
import sys

from cpr import model as model_mod, render

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


def with_about(model):
    """5201 as a review made after the run is recorded: model, time, size tier, and each lens's focus."""
    m = copy.deepcopy(model)
    rv = m["review"]
    rv["checklists"] = {"sha": "0123456789abcdef0123456789abcdef01234567"}
    rv["about"] = {"models": ["sonnet"], "ran_at": "2026-10-07 21:08 UTC", "tier": "small", "lines": 19}
    for lens in rv["lenses"]:
        lens["focus"] = f"what the {lens['name']} lens looks for"
    return m


def unreviewed(model):
    """5201 as the scheduled job publishes it: code review not run, the panel that would run listed."""
    from cpr import review
    m = copy.deepcopy(model)
    m["review"] = {"status": "not-run", "lenses": [], "panel": review.panel_summary()}
    return m


def no_plan(model):
    """5201 as if it were a docs-only PR: the Lab plan section explains why there is no plan."""
    m = copy.deepcopy(model)
    m["lab_plan"] = {"status": "none", "reason": "documentation-only change", "scenarios": [], "dropped": [],
                     "markdown": "", "filename": None}
    sec = next(s for s in m["sections"] if s["id"] == "labplan")
    sec.update(status="not-applicable", summary="No lab plan: documentation-only change")
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


def with_pmd_rules(model):
    """5201 with the PMD rules block filled from a trimmed real run (#4967: 157 files, 30 rules outside house style)."""
    m = copy.deepcopy(model)
    with open(os.path.join(REPO, "tests", "fixtures", "static", "pmd-rules-4967.json")) as f:
        rules = json.load(f)
    # Calibration: two rules the branch breaks at about this rate, and one that needs the compiled classes.
    usual = {"DoNotUseThreads": 58.4, "AvoidUsingVolatile": 30.1}
    for r in rules["rules"]:
        r.setdefault("in_tests", 0)
        r["production"] = r["introduced"] - r["in_tests"]
        r["needs_types"] = r["rule"] == "WrongTestAnnotation"
        r["usual"] = r["rule"] in usual
        r["expected"] = usual.get(r["rule"], 0)
        r["trunk"] = 107 if r["usual"] else 0
        r["p"] = 0.31 if r["usual"] else None
    rules.update({"usual_p": 0.01, "rate": {"loc": 640000, "added_loc": 21000, "available": True}})
    sa = {"status": "ran", "tools": {"pmd": {"status": "ran", "version": "7.28.0"}}, "pmd_rules": rules}
    m["pmd_rules"] = model_mod.pmd_rules_block({"static_analysis": sa})
    return m


def load_build_run():
    with open(os.path.join(REPO, "tests", "fixtures", "build", "5201-status.json")) as f:
        return json.load(f)


def bundle_model(name):
    """A model built from a recorded bundle (4967-huge is the long, many-table report)."""
    import gzip
    from cpr import checks as checks_mod, diffview
    from cpr.triage import triage
    with gzip.open(os.path.join(REPO, "tests", "fixtures", "bundles", name), "rt") as f:
        b = json.load(f)
    return model_mod.build(b, checks_mod.run_all(b), triage(b), render.load_docs(), diffview.unavailable("not built here"))


def build_site(out_dir, model):
    """An index over five different reports: contributor, draft, reviewers (siblings), unknown and ready-ish mixes."""
    from cpr import site
    reports = os.path.join(out_dir, "site-reports")
    for name in ("4967-huge.json.gz", "5201-backport-set.json.gz", "5212-no-jira.json.gz", "5228-stale-ci.json.gz", "5238-draft.json.gz"):
        m = bundle_model(name)
        render.write(m, os.path.join(reports, str(m["pr"]["number"]), "index.html"))
    # Two more reports so every kind of group exists: nothing left for the contributor, and a read failure.
    for number, verdict in ((6001, "awaiting-review"), (6002, "insufficient-evidence")):
        m = bundle_model("5212-no-jira.json.gz")
        m["pr"]["number"], m["pr"]["title"] = number, f"Variant {verdict}"
        for c in m["checks"]:
            c["status"], c["action_required"] = "pass", False
        m["recommendation"] = {**m["recommendation"], "verdict": verdict, "reasons": []}
        m.pop("view", None)
        render.write(m, os.path.join(reports, str(number), "index.html"))
    rows = site.build(reports, os.path.join(out_dir, "site"))
    return os.path.join(out_dir, "site", "index.html"), rows


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    model = load_model()
    render.write(model, os.path.join(out_dir, "report.html"))
    render.write(hostile(model), os.path.join(out_dir, "hostile.html"))
    render.write(lens_status(model), os.path.join(out_dir, "lens-status.html"))
    render.write(no_plan(model), os.path.join(out_dir, "labplan-none.html"))
    render.write(with_build(model, load_build_run()), os.path.join(out_dir, "build.html"))
    render.write(with_build(model, None), os.path.join(out_dir, "build-none.html"))
    render.write(with_pmd_rules(model), os.path.join(out_dir, "pmd-rules.html"))
    render.write(with_about(model), os.path.join(out_dir, "about.html"))
    render.write(unreviewed(model), os.path.join(out_dir, "unreviewed.html"))
    huge = bundle_model("4967-huge.json.gz")
    render.write(huge, os.path.join(out_dir, "huge.html"))
    index, rows = build_site(out_dir, model)
    print(json.dumps({"build": os.path.join(out_dir, "build.html"), "build_none": os.path.join(out_dir, "build-none.html"),
                      "report": os.path.join(out_dir, "report.html"), "hostile": os.path.join(out_dir, "hostile.html"),
                      "lens_status": os.path.join(out_dir, "lens-status.html"),
                      "labplan_none": os.path.join(out_dir, "labplan-none.html"),
                      "pmd_rules": os.path.join(out_dir, "pmd-rules.html"),
                      "about": os.path.join(out_dir, "about.html"), "unreviewed": os.path.join(out_dir, "unreviewed.html"),
                      "huge": os.path.join(out_dir, "huge.html"), "index": index,
                      "index_groups": {r["group"]: sum(1 for x in rows if x["group"] == r["group"]) for r in rows},
                      "hostile_title": HOSTILE_TITLE, "hostile_evidence": HOSTILE_EVIDENCE}))


if __name__ == "__main__":
    main(sys.argv[1])
