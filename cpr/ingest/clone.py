"""A full clone of apache/cassandra, used for diffs, blame context, and base-branch files.

A blobless partial clone is far smaller, but `git blame` then fetches historical blobs one at a
time over the network: one blame of DatabaseDescriptor.java took over 8 minutes. A full clone
(about 480 MB, about 3 minutes once) runs the same blame in under a second.
"""

import os
import subprocess

from cpr import REPO

REMOTE = f"https://github.com/{REPO}.git"


class CloneError(Exception):
    pass


def _git(path, *args, check=True):
    proc = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise CloneError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def pr_ref(number):
    return f"refs/cpr/pr/{number}"


def base_ref(branch):
    return f"refs/remotes/origin/{branch}"


def ensure(path, runner=subprocess.run):
    """Create the clone on first use. Returns True when a new clone was made."""
    if os.path.isdir(os.path.join(path, ".git")):
        return False
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    proc = runner(
        ["git", "clone", "--no-checkout", REMOTE, path],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise CloneError(f"git clone failed: {proc.stderr.strip()}")
    return True


def fetch(path, number, base):
    """Fetch only the PR head and its base branch."""
    _git(path, "fetch", "--no-tags", "--quiet", "origin",
         f"+refs/pull/{number}/head:{pr_ref(number)}",
         f"+refs/heads/{base}:{base_ref(base)}")


def has_refs(path, number, base):
    for ref in (pr_ref(number), base_ref(base)):
        if subprocess.run(["git", "-C", path, "rev-parse", "--verify", "--quiet", ref],
                          capture_output=True).returncode != 0:
            return False
    return True


def merge_base(path, number, base):
    return _git(path, "merge-base", base_ref(base), pr_ref(number)).strip()


def diff(path, merge_base_sha, number):
    return _git(path, "diff", "-M", "--no-color", merge_base_sha, pr_ref(number))


def changed_files(path, merge_base_sha, number):
    """[{path, previous_path, status, additions, deletions, binary}] for the PR's changes."""
    status_raw = _git(path, "diff", "-M", "-z", "--name-status", merge_base_sha, pr_ref(number))
    numstat_raw = _git(path, "diff", "-M", "-z", "--numstat", merge_base_sha, pr_ref(number))

    files = {}
    parts = status_raw.split("\0")
    i = 0
    while i < len(parts) and parts[i]:
        code = parts[i]
        if code[0] in "RC":
            files[parts[i + 2]] = {"path": parts[i + 2], "previous_path": parts[i + 1], "status": code[0]}
            i += 3
        else:
            files[parts[i + 1]] = {"path": parts[i + 1], "previous_path": None, "status": code[0]}
            i += 2

    parts = numstat_raw.split("\0")
    i = 0
    while i < len(parts) and parts[i]:
        adds, dels, name = parts[i].split("\t", 2)
        if name == "":  # rename: old and new paths follow
            name = parts[i + 2]
            i += 3
        else:
            i += 1
        entry = files.setdefault(name, {"path": name, "previous_path": None, "status": "M"})
        entry["binary"] = adds == "-"
        entry["additions"] = 0 if adds == "-" else int(adds)
        entry["deletions"] = 0 if dels == "-" else int(dels)
    for entry in files.values():
        entry.setdefault("additions", 0)
        entry.setdefault("deletions", 0)
        entry.setdefault("binary", False)
    return sorted(files.values(), key=lambda f: f["path"])


def show(path, ref, file_path):
    """File content at ref, or None when it does not exist there."""
    proc = subprocess.run(["git", "-C", path, "show", f"{ref}:{file_path}"], capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else None



def release_branches(path):
    out = _git(path, "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin/", check=False)
    names = [line.split("/", 1)[1] for line in out.splitlines() if "/" in line]
    return sorted(n for n in names if n.startswith("cassandra-") or n == "trunk")


def worktree(path, wt_path, number, head_sha):
    """Check the PR head out into `wt_path` (detached). Reuses and moves an existing worktree."""
    if os.path.exists(os.path.join(wt_path, ".git")):
        _git(wt_path, "checkout", "--quiet", "--detach", "--force", head_sha)
        _git(wt_path, "clean", "-fdq")
        return False
    _git(path, "worktree", "prune")
    _git(path, "worktree", "add", "--quiet", "--detach", "--force", os.path.abspath(wt_path), head_sha)
    return True
