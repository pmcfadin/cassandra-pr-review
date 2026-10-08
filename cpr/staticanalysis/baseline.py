"""The branch baseline: how many of a base branch's source files each PMD rule fires in.

A rule that fires in at least `house_style_share` of the branch's files is "house style differs": the code
itself does not follow it, so a PR that breaks it is not news. The baseline scores the base branch's whole
`src/java` once and is cached under `<work>/static-cache/` by branch, tip sha, PMD id and ruleset hash.

Order of use: the exact cached baseline; else a baseline for the same branch built less than seven days ago
(the tip moved; logged); else build one within its own time cap; else the density in the base versions of the
files the PR touches, which the report says is a weaker answer.
"""

import json
import os
import re
import shutil
import subprocess
import tarfile
import time

from cpr.staticanalysis import run

VERSION = 2  # 2: per-rule violation counts and the lines of code scanned (the usual-for-Cassandra rate test)
MAX_AGE_DAYS = 7
_METHOD_BODY = re.compile(r'\s*<rule name="MethodBody".*?</rule>', re.S)
_COMPLEXITY = re.compile(r'^.*(CognitiveComplexity|CyclomaticComplexity|NPathComplexity).*\n?', re.M)


def baseline_ruleset(text):
    """The PR ruleset without the complexity rules and the method-body rule: the baseline counts files per rule only."""
    return _COMPLEXITY.sub("", _METHOD_BODY.sub("", text))


def file_name(branch, tip, pmd_id, ruleset_sha):
    return f"pmd-baseline-{branch.replace('/', '_')}-{tip[:12]}-{pmd_id}-{ruleset_sha[:8]}.json"


def _load(path):
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("files_scanned") and data.get("version") == VERSION else None


def newest_recent(cache_dir, branch, pmd_id, ruleset_sha, now=None, max_age_days=MAX_AGE_DAYS):
    """The newest baseline for this branch, PMD and ruleset that is younger than max_age_days, else None."""
    now = time.time() if now is None else now
    prefix, suffix = f"pmd-baseline-{branch.replace('/', '_')}-", f"-{pmd_id}-{ruleset_sha[:8]}.json"
    best = None
    try:
        names = os.listdir(cache_dir)
    except OSError:
        return None
    for n in names:
        if not (n.startswith(prefix) and n.endswith(suffix)):
            continue
        data = _load(os.path.join(cache_dir, n))
        if data and now - data.get("built_at", 0) <= max_age_days * 86400:
            if best is None or data["built_at"] > best["built_at"]:
                best = data
    return best


def archive_sources(repo, ref, dest, exclude=()):
    """Write the *.java files under src/java at `ref` into dest. Returns (file count, non-blank lines). No checkout needed."""
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    proc = subprocess.Popen(["git", "-C", repo, "archive", "--format=tar", ref, "src/java"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        n, loc = _extract(proc, dest, exclude)
    except BaseException:
        proc.kill()
        raise
    finally:
        err = proc.stderr.read().decode(errors="replace").strip() if proc.poll() is not None else ""
        rc = proc.wait()
        proc.stdout.close()
        proc.stderr.close()
    if rc != 0:
        raise RuntimeError(f"git archive failed: {err[:200]}")
    return n, loc


def _extract(proc, dest, exclude):
    n = loc = 0
    with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
        for m in tar:
            name = m.name
            if not m.isfile() or not name.endswith(".java") or name.startswith(tuple(exclude)) or ".." in name.split("/"):
                continue
            target = os.path.join(dest, name)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            data = tar.extractfile(m).read()
            with open(target, "wb") as f:
                f.write(data)
            n += 1
            loc += sum(1 for ln in data.splitlines() if ln.strip())
    return n, loc


def build(repo, ref, branch, tip, pmd_bin, env, ruleset_text, pmd_id, ruleset_sha, scratch, timeout, threads, exclude=()):
    """Score the whole branch. (baseline dict, None) or (None, problem). Removes its scratch files."""
    start = time.monotonic()
    root = os.path.join(scratch, "tree")
    try:
        n, loc = archive_sources(repo, ref, root, exclude)
        if not n:
            return None, f"no Java sources under src/java at {branch}"
        rules = os.path.join(scratch, "ruleset.xml")
        with open(rules, "w") as f:
            f.write(baseline_ruleset(ruleset_text))
        files = sorted(os.path.join(dp, x) for dp, _, fs in os.walk(root) for x in fs if x.endswith(".java"))
        lst, out = os.path.join(scratch, "files.list"), os.path.join(scratch, "report.xml")
        with open(lst, "w") as f:
            f.write("".join(p + "\n" for p in files))
        rc, problem, secs = run._jvm_tool(env, run.pmd_command(pmd_bin, rules, lst, out, threads=threads), timeout, scratch)
        if problem and not (rc is None and problem.startswith("exit ") and os.path.exists(out)):
            return None, problem.replace(scratch.rstrip("/") + "/", "")
        hits, listed, errors, counts = run.count_pmd_files(out)
        return {"version": VERSION, "branch": branch, "tip": tip, "pmd": pmd_id, "ruleset_sha": ruleset_sha, "built_at": int(time.time()),
                "files_scanned": len(files), "loc": loc, "files_hit": hits, "violations": counts, "parse_errors": len(errors),
                "seconds": round(time.monotonic() - start, 1)}, None
    except (OSError, RuntimeError, tarfile.TarError, ValueError) as e:
        return None, f"baseline failed: {type(e).__name__}: {e}"[:300]
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def from_touched(base_files):
    """Fallback: density of each rule in the base versions of the touched files (a weaker, smaller sample)."""
    hits = {}
    for entry in base_files.values():
        for rule in {v[0] for v in entry.get("v") or []}:
            hits[rule] = hits.get(rule, 0) + 1
    return {"files_scanned": len(base_files), "files_hit": hits, "loc": 0, "violations": {}}  # a sample has no rate


def shares(data):
    """{rule: share of files}, for rules that fire at all."""
    n = data["files_scanned"]
    return {r: h / n for r, h in data["files_hit"].items()} if n else {}


def obtain(cache_dir, repo, ref, branch, tip, pmd_bin, env, ruleset_text, pmd_id, ruleset_sha, timeout, threads,
           exclude=(), log=print, now=None):
    """(baseline dict, source, note). source: cached | reused | built | None with the reason in note."""
    os.makedirs(cache_dir, exist_ok=True)
    exact = _load(os.path.join(cache_dir, file_name(branch, tip, pmd_id, ruleset_sha)))
    if exact:
        return exact, "cached", None
    recent = newest_recent(cache_dir, branch, pmd_id, ruleset_sha, now)
    if recent:
        days = ((time.time() if now is None else now) - recent["built_at"]) / 86400
        log(f"  pmd baseline: {branch} moved to {tip[:12]}; reusing the one for {recent['tip'][:12]} ({days:.1f} days old)")
        return recent, "reused", f"baseline of {recent['tip'][:12]}, built {days:.1f} days ago; {branch} has moved since"
    log(f"  pmd baseline: scoring all of {branch} at {tip[:12]} (cap {timeout:.0f} s)")
    scratch = os.path.join(cache_dir, f"pmd-baseline-scratch-{os.getpid()}")
    data, problem = build(repo, ref, branch, tip, pmd_bin, env, ruleset_text, pmd_id, ruleset_sha, scratch, timeout,
                          threads, exclude)
    if not data:
        return None, None, problem
    with open(os.path.join(cache_dir, file_name(branch, tip, pmd_id, ruleset_sha)), "w") as f:
        json.dump(data, f)
    return data, "built", None
