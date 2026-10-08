"""Pick open apache/cassandra PRs whose published report is missing or stale, and refresh them.

The polling run only does the cheap, deterministic parts of `cpr review` (no AI lenses, no builds, no
comments). The published state is the site directory (a gh-pages checkout) or the gh-pages branch.
"""

import calendar
import os
import subprocess
import tempfile
import time

from cpr import REPO, site
from cpr.net import gh_json

DEFAULT_LIMIT = 25
STALE_DRAFT_DAYS = 30


def fetch_open(recorder=None):
    """Open PRs as returned by the GitHub list endpoint (number, head.sha, draft, updated_at, ...)."""
    return gh_json(f"repos/{REPO}/pulls?state=open&per_page=100", recorder=recorder, paginate=True) or []


def _epoch(ts):
    return calendar.timegm(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")) if ts else 0


def select(open_prs, heads, now=None, limit=DEFAULT_LIMIT, stale_days=STALE_DRAFT_DAYS):
    """(picked, skipped): PRs with no published report or a different head, newest update first, capped.

    `heads` maps PR number to the published head sha. Drafts not updated in `stale_days` are skipped.
    Each entry is {number, head, updated_at, title, reason}.
    """
    now = time.time() if now is None else now
    picked, skipped = [], []
    for pr in sorted(open_prs, key=lambda p: p.get("updated_at") or "", reverse=True):
        number, head = pr["number"], (pr.get("head") or {}).get("sha")
        row = {"number": number, "head": head, "updated_at": pr.get("updated_at"), "title": pr.get("title") or ""}
        if pr.get("draft") and now - _epoch(pr.get("updated_at")) > stale_days * 86400:
            skipped.append({**row, "reason": f"draft not updated in {stale_days} days"})
        elif number in heads and heads[number] == head:
            skipped.append({**row, "reason": "published report is for the current head"})
        elif len(picked) >= limit:
            skipped.append({**row, "reason": f"over the cap of {limit} per run"})
        else:
            picked.append({**row, "reason": "no published report" if number not in heads else "new head"})
    return picked, skipped


def heads_from_git(repo_root, ref="origin/gh-pages"):
    """{PR number: head sha} read from a git ref (read-only; fetches gh-pages first). Empty when absent."""
    def run(*a):
        return subprocess.run(["git", "-C", repo_root, *a], capture_output=True, text=True)

    run("fetch", "--quiet", "origin", "gh-pages")
    tree = run("ls-tree", "-r", "--name-only", ref)
    if tree.returncode != 0:
        return {}
    heads = {}
    for name in tree.stdout.split("\n"):
        if name.startswith("pr/") and name.endswith("/index.html"):
            blob = run("show", f"{ref}:{name}")
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "index.html")
                with open(path, "w") as f:
                    f.write(blob.stdout)
                model = site.read_model(path)
            if model:
                heads[model["pr"]["number"]] = model["pr"].get("head_sha")
    return heads


def refresh(picked, site_dir, review, log=print):
    """Review each picked PR into a scratch dir and merge it into the site; one failure never aborts.

    `review(number, out_path)` returns an exit code (0 = report written). Returns {number: outcome}.
    """
    outcomes = {}
    for p in picked:
        n = p["number"]
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, str(n), "index.html")
            try:
                code = review(n, out)
                if code != 0 or not os.path.exists(out):
                    outcomes[n] = f"failed (exit {code})"
                else:
                    outcomes[n] = site.merge_report(site_dir, out)[1]
            except Exception as e:  # noqa: BLE001 - polling must survive any single PR
                outcomes[n] = f"failed ({type(e).__name__}: {e})"
        log(f"#{n}: {outcomes[n]}")
    site.rebuild_index(site_dir)
    return outcomes


def format_picks(picked, skipped):
    lines = [f"{len(picked)} PR(s) to refresh:"]
    lines += [f"  #{p['number']} {p['reason']} (updated {p['updated_at']}) {p['title'][:70]}" for p in picked]
    if skipped:
        by = {}
        for s in skipped:
            by[s["reason"]] = by.get(s["reason"], 0) + 1
        lines.append("skipped: " + "; ".join(f"{c} {r}" for r, c in sorted(by.items())))
    return "\n".join(lines)
