"""Gather the git history behind a PR's changes: blame of the changed base lines and per-file logs.

Everything here reads the local clone. The result is stored in the bundle as `history`; turning
it into tickets, experts, and suggestions is cpr.context, a pure function.
"""

import json
import os

from cpr import credits, diffparse, paths
from cpr.ingest import clone

CONFIG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "context.json")
_MAX_MESSAGE = 2000


def load_config(path=CONFIG):
    with open(path) as f:
        return json.load(f)


def _file_priority(files):
    """Changed-line counts by path, production code first, then largest first."""
    size = {f["path"]: f["additions"] + f["deletions"] for f in files}
    return lambda p: (0 if paths.is_prod(p) else 1, -size.get(p, 0), p)


def select_hunks(hunks, files, max_hunks):
    order = _file_priority(files)
    ranked = sorted(hunks, key=lambda h: (order(h["new_path"] or h["path"]), h["start"]))
    return ranked[:max_hunks], max(0, len(ranked) - max_hunks)


def select_files(files, max_files):
    existing = [f for f in files if f["status"] != "A" and not f.get("binary")]
    order = _file_priority(files)
    ranked = sorted(existing, key=lambda f: order(f["path"]))
    return ranked[:max_files], max(0, len(ranked) - max_files)


def _trim(commit):
    return {**commit, "message": commit["message"][:_MAX_MESSAGE]}


def history_ref(clone_path, merge_base, path):
    """Where to read a file's history: trunk when the file exists there, else the merge base.

    Backports target release branches whose own recent history is thin; the same code on trunk
    carries the project's recent work on it.
    """
    trunk = clone.base_ref("trunk")
    if clone.line_count(clone_path, trunk, path):
        return trunk, "trunk"
    return merge_base, "merge base"


def gather(clone_path, merge_base, diff_text, files, cfg=None):
    cfg = cfg or load_config()
    hunks = diffparse.old_side_hunks(diff_text, cfg["context_lines"])
    chosen, hunks_skipped = select_hunks(hunks, files, cfg["max_hunks"])

    by_path = {}
    for h in chosen:
        by_path.setdefault(h["path"], []).append(h)
    blame = []
    for path, hs in by_path.items():
        n = clone.line_count(clone_path, merge_base, path)
        ranges = [(h["start"], min(h["end"], n)) for h in hs if n and h["start"] <= n]
        for sha, lines in clone.blame(clone_path, merge_base, path, ranges).items():
            blame.append({"path": path, "sha": sha, "lines": lines})

    commits = {c["sha"]: _trim(c) for c in clone.show_commits(clone_path, sorted({b["sha"] for b in blame}))}

    logged, files_skipped = select_files(files, cfg["max_files"])
    file_logs, log_refs = {}, {}
    for f in logged:
        path = f.get("previous_path") or f["path"]
        ref, label = history_ref(clone_path, merge_base, path)
        log = clone.file_log(clone_path, ref, path, since=f"{cfg['window_years']}.years")
        file_logs[f["path"]] = [_trim(c) for c in log[:cfg["max_log_per_file"]]]
        log_refs[f["path"]] = label

    keys = sorted({k for c in commits.values() if not c["merge"] for k in [credits.primary_key(c["message"])] if k})
    return {
        "hunks_total": len(hunks), "hunks_blamed": len(chosen), "hunks_skipped": hunks_skipped,
        "files_total": len([f for f in files if f["status"] != "A"]), "files_logged": len(logged),
        "files_skipped": files_skipped, "new_files_only": bool(files) and all(f["status"] == "A" for f in files),
        "blame": blame, "commits": commits, "file_logs": file_logs, "log_refs": log_refs, "keys": keys, "tickets": {},
    }
