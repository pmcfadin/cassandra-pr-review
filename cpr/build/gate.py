"""Who may be built: committers, or a PR head the owner approved."""

import json
import os
import time

from cpr.build import runs_dir


def author_is_committer(bundle):
    """Same rule as the votes check: roster, GitHub-to-ASF overrides, apache.org commit emails, org membership."""
    from cpr.checks import votes
    pr = bundle.get("pr") or {}
    cid, _ = votes.committer_id(bundle, "github", pr.get("author"), pr.get("author_association"))
    return bool(cid)


def approvals_path(work_dir, number):
    return os.path.join(runs_dir(work_dir, number), "approved.json")


def read_approval(work_dir, number):
    try:
        with open(approvals_path(work_dir, number)) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def record_approval(work_dir, number, head, now=None):
    """Remember the owner's approval of this exact head sha (a new push needs a new approval)."""
    path = approvals_path(work_dir, number)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rec = {"head": head, "approved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now or time.time()))}
    with open(path, "w") as f:
        json.dump(rec, f, indent=1)
    return rec


def decide(bundle, work_dir, approve=False, now=None):
    """{allowed, approved, author_is_committer, reason}. `approve` records approval for the bundle's head."""
    pr = bundle["pr"]
    number, head = pr["number"], pr["head_sha"]
    committer = author_is_committer(bundle)
    if approve:
        record_approval(work_dir, number, head, now)
    saved = read_approval(work_dir, number)
    approved = bool(saved and saved.get("head") == head)
    if committer:
        reason = f"author {pr['author']} is a committer"
    elif approved:
        reason = f"owner approved head {head[:8]}"
    else:
        roster = (bundle.get("roster") or {}).get("status")
        why = "author is not a committer" if roster in ("ok", "stale") else "committer roster unavailable"
        reason = (f"{why} ({pr['author']}) and the owner has not approved head {head[:8]}; "
                  f"run: cpr build {number} --approve")
    return {"allowed": committer or approved, "approved": approved, "author_is_committer": committer, "reason": reason}
