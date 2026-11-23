"""Pick open PRs (apache/cassandra and its subprojects) whose published report is missing or stale, and refresh them.

The polling run only does the cheap, deterministic parts of `cpr review` (no AI lenses, no builds, no
comments). The published state is the site directory (a gh-pages checkout) or the gh-pages branch.
"""

import calendar
import os
import subprocess
import tempfile
import time

from cpr import project as project_mod, site
from cpr.net import gh_json

DEFAULT_LIMIT = 25
STALE_DRAFT_DAYS = 30


def fetch_open(recorder=None, repo=None):
    """Open PRs as returned by the GitHub list endpoint (number, head.sha, draft, updated_at, ...)."""
    repo = repo or project_mod.load(project_mod.DEFAULT).repo
    return gh_json(f"repos/{repo}/pulls?state=open&per_page=100", recorder=recorder, paginate=True) or []


def _epoch(ts):
    return calendar.timegm(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")) if ts else 0


def select(open_prs, heads, now=None, limit=DEFAULT_LIMIT, stale_days=STALE_DRAFT_DAYS):
    """(picked, skipped): PRs with no published report or a different head, newest update first, capped.

    `heads` maps PR number to the published head sha, for the one project `open_prs` belong to. Drafts not
    updated in `stale_days` are skipped.
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


def heads_for(heads, slug):
    """{PR number: head sha} of one project from published_heads' {(slug, number): head sha}."""
    return {n: h for (s, n), h in heads.items() if s == slug}


def _site_path(name):
    """(slug, number) for `<slug>/pr/<N>/index.html` or a pre-project `pr/<N>/index.html`, else None."""
    parts = name.split("/")
    if len(parts) == 3 and parts[0] == "pr" and parts[2] == "index.html" and parts[1].isdigit():
        return project_mod.DEFAULT, int(parts[1])
    if len(parts) == 4 and parts[1] == "pr" and parts[3] == "index.html" and parts[2].isdigit() \
            and parts[0] in project_mod.slugs():
        return parts[0], int(parts[2])
    return None


def heads_from_git(repo_root, ref="origin/gh-pages"):
    """{(slug, PR number): head sha} read from a git ref (read-only; fetches gh-pages first). Empty when absent.

    A site from before projects existed keeps Cassandra reports at pr/<N>/; once migrated those are redirects,
    which carry no model and are skipped.
    """
    def run(*a):
        return subprocess.run(["git", "-C", repo_root, *a], capture_output=True, text=True)

    run("fetch", "--quiet", "origin", "gh-pages")
    tree = run("ls-tree", "-r", "--name-only", ref)
    if tree.returncode != 0:
        return {}
    heads = {}
    for name in tree.stdout.split("\n"):
        where = _site_path(name)
        if where:
            blob = run("show", f"{ref}:{name}")
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "index.html")
                with open(path, "w") as f:
                    f.write(blob.stdout)
                model = site.read_model(path)
            if model and site.model_slug(model) == where[0]:
                heads.setdefault(where, model["pr"].get("head_sha"))
    return heads


def refresh(picked, site_dir, review, log=print):
    """Review each picked PR into a scratch dir and merge it into the site; one failure never aborts.

    Each pick names its `project` slug. `review(slug, number, out_path)` returns an exit code (0 = report
    written). Returns {(slug, number): outcome}.
    """
    outcomes = {}
    for p in picked:
        slug, n = p["project"], p["number"]
        key = (slug, n)
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, str(n), "index.html")
            try:
                code = review(slug, n, out)
                if code != 0 or not os.path.exists(out):
                    outcomes[key] = f"failed (exit {code})"
                else:
                    outcomes[key] = site.merge_report(site_dir, out)[1]
            except Exception as e:  # noqa: BLE001 - polling must survive any single PR
                outcomes[key] = f"failed ({type(e).__name__}: {e})"
        log(f"{slug}#{n}: {outcomes[key]}")
    site.rebuild_index(site_dir)
    return outcomes


def format_picks(picked, skipped, project=None):
    """The dry-run listing; `project` (a Project) titles it when polling several projects."""
    lines = [f"{project.name + ': ' if project else ''}{len(picked)} PR(s) to refresh:"]
    lines += [f"  #{p['number']} {p['reason']} (updated {p['updated_at']}) {p['title'][:70]}" for p in picked]
    if skipped:
        by = {}
        for s in skipped:
            by[s["reason"]] = by.get(s["reason"], 0) + 1
        lines.append("skipped: " + "; ".join(f"{c} {r}" for r, c in sorted(by.items())))
    return "\n".join(lines)
