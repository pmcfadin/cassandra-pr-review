"""CI evidence from GitHub: the check-runs and workflow runs of a PR head, for projects whose CI is GitHub Actions.

apache/cassandra-sidecar and apache/cassandra-analytics run their CI on every PR. A first-time contributor's
workflow runs wait for a maintainer's approval (`conclusion: action_required`) and produce no check-runs until then.
"""

import urllib.parse

from cpr.net import NetError, gh_json

FAILED = ("failure", "timed_out", "startup_failure")


def _pages(data, key):
    """`gh api --paginate --slurp` gives one object per page; the list endpoint pages carry `key`."""
    pages = data if isinstance(data, list) else [data or {}]
    return [item for page in pages if isinstance(page, dict) for item in page.get(key) or []]


def fetch(repo, head_sha, recorder):
    """{status, error, head_sha, check_runs, workflow_runs}. status: ok | unavailable."""
    out = {"status": "ok", "error": None, "head_sha": head_sha, "check_runs": [], "workflow_runs": []}
    sha = urllib.parse.quote(head_sha)
    try:
        runs = _pages(gh_json(f"repos/{repo}/commits/{sha}/check-runs?per_page=100", recorder=recorder, paginate=True),
                      "check_runs")
        wfs = _pages(gh_json(f"repos/{repo}/actions/runs?head_sha={sha}&per_page=100", recorder=recorder, paginate=True),
                     "workflow_runs")
    except NetError as e:
        return {**out, "status": "unavailable", "error": str(e)}
    out["check_runs"] = [{"name": r.get("name"), "status": r.get("status"), "conclusion": r.get("conclusion"),
                          "app": (r.get("app") or {}).get("slug"), "url": r.get("html_url"),
                          "completed_at": r.get("completed_at")} for r in runs]
    out["workflow_runs"] = [{"name": w.get("name"), "status": w.get("status"), "conclusion": w.get("conclusion"),
                             "event": w.get("event"), "url": w.get("html_url")} for w in wfs
                            if w.get("head_sha") in (None, head_sha)]
    return out


def summary(gh):
    """Counts over the check-runs: {total, completed, passed, failed, skipped, cancelled, pending, awaiting_approval}."""
    runs = gh.get("check_runs") or []
    done = [r for r in runs if r.get("status") == "completed"]
    return {
        "total": len(runs),
        "completed": len(done),
        "passed": sum(1 for r in done if r.get("conclusion") in ("success", "neutral")),
        "failed": sum(1 for r in done if r.get("conclusion") in FAILED),
        "skipped": sum(1 for r in done if r.get("conclusion") == "skipped"),
        "cancelled": sum(1 for r in done if r.get("conclusion") == "cancelled"),
        "pending": len(runs) - len(done),
        "awaiting_approval": [w for w in gh.get("workflow_runs") or [] if w.get("conclusion") == "action_required"],
    }
