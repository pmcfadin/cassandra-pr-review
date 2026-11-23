"""Where per-PR data lives. Every path names the project, because PR numbers repeat across repositories.

    <work>/<repo name>                         the project's clone (cassandra, cassandra-sidecar, ...)
    <work>/pr/<slug>/<N>/...                   ingest bundles, raw responses, lens outputs, static analysis
    <work>/wt/<slug>/<N>                       worktree of the PR head
    <work>/build-runs/<slug>/<N>/<head>        cpr build results
    <root>/reports/<slug>/<N>/index.html       rendered report

Before projects existed the same paths had no `<slug>/` level. `migrate` moves that apache/cassandra data in
place once (design D5 of openspec change project-profiles).
"""

import json
import os
import shutil
import subprocess

LEGACY_SLUG = "cassandra"


def clone_dir(work_dir, project):
    return os.path.join(work_dir, project.clone_name)


def pr_dir(work_dir, slug, number):
    return os.path.join(work_dir, "pr", slug, str(number))


def worktree(work_dir, slug, number):
    return os.path.join(work_dir, "wt", slug, str(number))


def build_runs(work_dir, slug, number):
    return os.path.join(work_dir, "build-runs", slug, str(number))


def reports_dir(root):
    return os.path.join(root, "reports")


def report(root, slug, number):
    return os.path.join(reports_dir(root), slug, str(number), "index.html")


def _numeric(parent):
    try:
        return sorted(n for n in os.listdir(parent) if n.isdigit() and os.path.isdir(os.path.join(parent, n)))
    except OSError:
        return []


def _rewrite_classpaths(run_root, old_prefix, new_prefix):
    """Point the kept build classpath of every status.json under run_root at its moved location."""
    for head in os.listdir(run_root):
        path = os.path.join(run_root, head, "status.json")
        try:
            with open(path) as f:
                st = json.load(f)
        except (OSError, ValueError):
            continue
        cp = st.get("classpath")
        if not isinstance(cp, dict):
            continue
        changed = False
        for k in ("classes", "jars"):
            items = cp.get(k)
            if isinstance(items, list):
                new = [new_prefix + p[len(old_prefix):] if isinstance(p, str) and p.startswith(old_prefix) else p
                       for p in items]
                changed = changed or new != items
                cp[k] = new
        if changed:
            with open(path, "w") as f:
                json.dump(st, f, indent=1)


def _remove_worktree(clone, wt):
    if os.path.isdir(os.path.join(clone, ".git")):
        subprocess.run(["git", "-C", clone, "worktree", "remove", "--force", wt], capture_output=True)
        subprocess.run(["git", "-C", clone, "worktree", "prune"], capture_output=True)
    if os.path.exists(wt):
        shutil.rmtree(wt, ignore_errors=True)


def migrate(work_dir, reports=None, log=print):
    """Move apache/cassandra data from the layout without projects. Returns the moves made; a no-op once done.

    `reports` is the reports directory to migrate too (None: leave reports alone). Never overwrites: when the
    target exists the source is left where it is and logged.
    """
    moves = []

    def move(parent, n, after_move=None):
        src, dest = os.path.join(parent, n), os.path.join(parent, LEGACY_SLUG, n)
        if os.path.exists(dest):
            log(f"layout: kept {src}: {dest} already exists")
            return
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        os.rename(src, dest)
        if after_move:
            after_move(src, dest)
        moves.append((src, dest))

    for n in _numeric(os.path.join(work_dir, "pr")):
        move(os.path.join(work_dir, "pr"), n)
    for n in _numeric(os.path.join(work_dir, "build-runs")):
        move(os.path.join(work_dir, "build-runs"), n,
             lambda src, dest: _rewrite_classpaths(dest, src + os.sep, dest + os.sep))
    for n in _numeric(reports) if reports else []:
        move(reports, n)
    clone = os.path.join(work_dir, "cassandra")
    for n in _numeric(os.path.join(work_dir, "wt")):
        wt = os.path.join(work_dir, "wt", n)
        _remove_worktree(clone, wt)  # a checkout of a sha; cpr prepare recreates it under wt/cassandra/
        moves.append((wt, None))
    if moves:
        log(f"layout: moved {sum(1 for _, d in moves if d)} apache/cassandra directories under cassandra/, "
            f"removed {sum(1 for _, d in moves if not d)} old worktrees")
    return moves
