"""Saved build results (`cpr build`) for the current head, and the committer gate's input.

`cpr review` never builds: it reads <work_dir>/build-runs/<N>/<head>/status.json. A file whose `head`
differs from the PR's current head is never shown as current.
"""

import json
import os

STATUSES = ("pass", "tests-failed", "build-failed", "timeout", "unknown", "not-built")
NOT_BUILT_REASON = ("No build result for this head. Only PRs by committers are built automatically "
                    "(`cpr build <N>`); for any other PR the owner approves one head with `cpr build <N> --approve`.")


def status_path(work_dir, number, head):
    return os.path.join(work_dir, "build-runs", str(number), head, "status.json")


def author_is_committer(bundle):
    """True when the PR author is on the committer roster (same rules as the vote check)."""
    from cpr.checks.votes import committer_id
    pr = bundle["pr"]
    return committer_id(bundle, "github", pr.get("author"), pr.get("author_association"))[0] is not None


def load(work_dir, number, head):
    """The saved result for exactly this head, or None (missing, unreadable, or for another head)."""
    try:
        with open(status_path(work_dir, number, head), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("head") != head or data.get("status") not in STATUSES:
        return None
    return data


def not_built(reason=None):
    return {"status": "not-built", "reason": reason or NOT_BUILT_REASON}
