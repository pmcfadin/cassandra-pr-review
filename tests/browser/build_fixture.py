"""Render browser-test fixtures from the real 5201 report model.

Usage: PYTHONPATH=<repo root> python3 tests/browser/build_fixture.py <out_dir>

Writes <out_dir>/report.html (the 5201 model as-is) and <out_dir>/hostile.html (the same model with
script-shaped text in the PR title, a check's evidence, the PR body, and a JIRA comment).
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


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    model = load_model()
    render.write(model, os.path.join(out_dir, "report.html"))
    render.write(hostile(model), os.path.join(out_dir, "hostile.html"))
    render.write(lens_status(model), os.path.join(out_dir, "lens-status.html"))
    print(json.dumps({"report": os.path.join(out_dir, "report.html"), "hostile": os.path.join(out_dir, "hostile.html"),
                      "lens_status": os.path.join(out_dir, "lens-status.html"),
                      "hostile_title": HOSTILE_TITLE, "hostile_evidence": HOSTILE_EVIDENCE}))


if __name__ == "__main__":
    main(sys.argv[1])
