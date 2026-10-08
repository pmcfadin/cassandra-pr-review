"""What the analysis reads from git: changed Java files, changed lines, blobs, and the commit list.

Everything comes from `git` plumbing against the clone, so no checkout is needed.
"""

import os
import re
import subprocess

from cpr.ingest.clone import CloneError, _git

_HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def is_excluded(path, exclude):
    return path.startswith(tuple(exclude))


def changed_java(clone, base, head, exclude=()):
    """[{path, base_path, status A|M|R|D, test}] for changed .java files (rename map from `git diff -M`)."""
    raw = _git(clone, "diff", "-M", "-z", "--name-status", base, head, "--", "*.java")
    parts, out, i = raw.split("\0"), [], 0
    while i < len(parts) and parts[i]:
        code = parts[i]
        if code[0] in "RC":
            old, new = parts[i + 1], parts[i + 2]
            i += 3
            status, base_path = ("R", old) if code[0] == "R" else ("A", None)
        else:
            new = parts[i + 1]
            i += 2
            status, base_path = code[0], (None if code[0] == "A" else new)
        if status not in "AMRD" or is_excluded(new, exclude):
            continue
        out.append({"path": new, "base_path": base_path, "status": status, "test": new.startswith("test/")})
    return sorted(out, key=lambda c: c["path"])


def parse_hunks(diff_text):
    """git diff -U0 text -> ({head path: [(start, end)]}, {base path: [(start, end)]}) changed-line ranges."""
    new, old, o, n = {}, {}, None, None
    for ln in diff_text.splitlines():
        if ln.startswith("--- "):
            o = ln[6:] if ln.startswith("--- a/") else None
        elif ln.startswith("+++ "):
            n = ln[6:] if ln.startswith("+++ b/") else None
        elif ln.startswith("@@"):
            m = _HUNK.match(ln)
            if not m:
                continue
            os_, oc, ns, nc = int(m[1]), int(m[2] or 1), int(m[3]), int(m[4] or 1)
            if o and oc:
                old.setdefault(o, []).append((os_, os_ + oc - 1))
            if n and nc:
                new.setdefault(n, []).append((ns, ns + nc - 1))
    return new, old


def changed_lines(clone, base, head):
    """(head-side, base-side) changed line ranges of the Java files, from `git diff -U0 -M`."""
    return parse_hunks(_git(clone, "diff", "-U0", "-M", "--no-color", base, head, "--", "*.java"))


def read_blobs(clone, ref, paths):
    """{path: (blob sha, bytes)} for each path that exists at ref, through one `git cat-file --batch`."""
    if not paths:
        return {}
    stdin = "".join(f"{ref}:{p}\n" for p in paths).encode()
    proc = subprocess.run(["git", "-C", clone, "cat-file", "--batch"], input=stdin, capture_output=True)
    if proc.returncode != 0:
        raise CloneError(f"git cat-file --batch: {proc.stderr.decode(errors='replace').strip()}")
    data, pos, out = proc.stdout, 0, {}
    for p in paths:
        eol = data.index(b"\n", pos)
        header = data[pos:eol].decode().split()
        pos = eol + 1
        if header[-1] == "missing":
            continue
        size = int(header[2])
        out[p] = (header[0], data[pos:pos + size])
        pos += size + 1
    return out


def extract(clone, changed, base, head, dest):
    """Write base and head blobs under dest/{base,head}/<path>. Returns {side: {path: blob sha}}."""
    shas = {"base": {}, "head": {}}
    want = {"base": [c["base_path"] for c in changed if c["base_path"]],
            "head": [c["path"] for c in changed if c["status"] != "D"]}
    for side, ref in (("base", base), ("head", head)):
        for path, (sha, content) in read_blobs(clone, ref, want[side]).items():
            target = os.path.join(dest, side, path)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as f:
                f.write(content)
            shas[side][path] = sha
    return shas


def commits(clone, base, head):
    """[{sha, subject, paths}] oldest first, no merges, for base..head."""
    raw = _git(clone, "-c", "core.quotepath=off", "log", "--reverse", "--no-merges", "--name-only",
               "--format=%x01%H%x00%s", f"{base}..{head}")
    out = []
    for rec in raw.split("\x01")[1:]:
        head_line, _, rest = rec.partition("\n")
        sha, _, subject = head_line.partition("\0")
        out.append({"sha": sha, "subject": subject, "paths": [p for p in rest.splitlines() if p]})
    return out
