"""Static analysis of a PR's changed Java files: checkstyle, PMD complexity, CPD, base versus head.

`analyze` runs at ingest (online) and returns the `static_analysis` section of the evidence bundle;
`load_cached` replays a saved section and never runs a tool. A tool that is not installed is
`unknown` (run `cpr tools install`); nothing is downloaded during a review.
"""

import hashlib
import json
import os
import shutil
import time

from cpr.ingest import clone as clone_mod
from cpr.staticanalysis import auxpath, baseline, classify, inputs, ruleset as ruleset_mod, run, tools

SCHEMA = 3  # 2: partial PMD runs keep the files PMD read; 3: the full PMD catalog and the baseline
TOOLS = ("checkstyle", "pmd", "cpd")


def tool_result(status, reason=None, version=None, expected=0, analyzed=0, seconds=0.0):
    return {"status": status, "version": version, "reason": reason, "files_expected": expected,
            "files_analyzed": analyzed, "seconds": round(seconds, 2)}


def unavailable(reason, base_branch=None, status="unknown"):
    """The section when nothing could run: every tool gets the same status and reason."""
    return {"status": "unavailable", "reason": reason, "base_branch": base_branch,
            "tools": {t: tool_result(status, reason) for t in TOOLS}, "changed_java": [], "checkstyle": [],
            "complexity": {"threshold": 15, "methods": [], "findings": []}, "duplication": [], "commits": []}


def load_cached(bundle):
    """The saved section of a cached bundle. Never runs a tool."""
    return bundle.get("static_analysis") or unavailable("no static analysis in this cached ingest")


def sha_text(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode() if isinstance(p, str) else p)
    return h.hexdigest()


class Budget:
    """Per-PR and per-invocation time caps."""

    def __init__(self, caps):
        self.caps, self.start = caps, time.monotonic()

    def timeout(self):
        left = self.caps["pr_seconds"] - (time.monotonic() - self.start)
        return min(self.caps["tool_seconds"], left) if left > 1 else None


def _cached_side(cache_dir, shas, runner):
    """Base side per blob sha. runner(paths) -> ({path: result}, problem, seconds). Returns the same, cache-merged."""
    results, todo = {}, []
    os.makedirs(cache_dir, exist_ok=True)
    for path, sha in shas.items():
        p = os.path.join(cache_dir, sha + ".json")
        if os.path.exists(p):
            with open(p) as f:
                results[path] = json.load(f)
        else:
            todo.append(path)
    problem, seconds = None, 0.0
    if todo:
        fresh, problem, seconds = runner(todo)
        for path, res in fresh.items():
            results[path] = res
            with open(os.path.join(cache_dir, shas[path] + ".json"), "w") as f:
                json.dump(res, f)
    return results, problem, seconds


def _env(java_cache, need, cfg):
    """(java, env) or a ToolError message, memoised per minimum version."""
    if need not in java_cache:
        try:
            java, _ = tools.find_java(need, cfg)
            java_cache[need] = (java, tools.java_env(java), None)
        except tools.ToolError as e:
            java_cache[need] = (None, None, str(e))
    return java_cache[need]


def _read(path):
    with open(path, "rb") as f:
        return f.read()


def analyze(bundle, work_dir, log=print):
    """Run the tools on the PR's changed Java files and return the `static_analysis` section.

    A crash becomes an honest `unavailable` section instead of failing the ingest.
    """
    try:
        return _analyze(bundle, work_dir, log)
    except Exception as e:  # noqa: BLE001
        return unavailable(f"static analysis crashed: {type(e).__name__}: {e}", bundle["pr"].get("base"))


def _analyze(bundle, work_dir, log):
    cfg = tools.load_config()
    pr = bundle["pr"]
    base_branch, number = pr["base"], pr["number"]
    git = bundle.get("git") or {}
    repo = git.get("clone")
    if not repo or not os.path.isdir(os.path.join(repo, ".git")) or not clone_mod.has_refs(repo, number, base_branch):
        return unavailable("no local clone or PR refs", base_branch)
    mb, head = git["merge_base"], clone_mod.pr_ref(number)
    changed = inputs.changed_java(repo, mb, head, cfg["exclude"])
    commits = inputs.commits(repo, mb, head)
    if not changed:
        out = unavailable("no changed Java files", base_branch, status="not-applicable")
        out["commits"] = commits
        return out
    sd = os.path.join(work_dir, "pr", str(number), pr["head_sha"], "static")
    base_ref = clone_mod.base_ref(base_branch)
    cs_id, pmd_id = tools.checkstyle_id(cfg, base_branch), cfg["pmd"]
    cfgs = run.fetch_configs(repo, base_ref, os.path.join(sd, "cfg"))
    ruleset = os.path.join(os.path.dirname(tools.CONFIG), "pmd-pr.xml")
    cs_sha = sha_text(*[_read(p) for _, p in sorted((cfgs or {}).items())])
    pmd_sha = sha_text(_read(ruleset), json.dumps(cfg["thresholds"], sort_keys=True))
    aux_cp, aux_note = auxpath.resolve(work_dir, number, pr["head_sha"])
    java_cache = {}
    cs_ok = cs_id and tools.is_installed(work_dir, cs_id) and cfgs
    pmd_ok = tools.is_installed(work_dir, pmd_id)
    key = {"schema": SCHEMA, "merge_base": mb, "checkstyle": [cs_id, cs_sha, bool(cs_ok),
                                                              _env(java_cache, cfg["tools"][cs_id]["min_java"] if cs_id else 8, cfg)[2]],
           "pmd": [pmd_id, pmd_sha, pmd_ok, _env(java_cache, 8, cfg)[2], sha_text(aux_cp or ""), cfg["house_style_share"]],
           "cpd": cfg["cpd_min_tokens"]}
    results = os.path.join(sd, "results.json")
    if os.path.exists(results):
        with open(results) as f:
            saved = json.load(f)
        if saved.get("key") == key:
            log("static analysis: cached for this head sha")
            return saved["result"]
    out = _run(cfg, work_dir, repo, base_branch, changed, mb, head, sd, (cs_id, cfgs, cs_sha, cs_ok),
               (pmd_id, ruleset, pmd_sha, pmd_ok, aux_cp, aux_note), java_cache, log)
    out["commits"] = commits
    os.makedirs(sd, exist_ok=True)
    with open(results, "w") as f:
        json.dump({"key": key, "result": out}, f)
    return out


def _run(cfg, work_dir, repo, base_branch, changed, mb, head, sd, cs, pmd, java_cache, log):
    for side in ("base", "head", "raw"):
        shutil.rmtree(os.path.join(sd, side), ignore_errors=True)
    shas = inputs.extract(repo, changed, mb, head, sd)
    head_lines, base_lines = inputs.changed_lines(repo, mb, head)
    raw = os.path.join(sd, "raw")
    os.makedirs(raw)
    budget = Budget(cfg["caps"])
    out = {"status": "ran", "reason": None, "base_branch": base_branch, "tools": {}, "changed_java": changed,
           "checkstyle": [], "complexity": {"threshold": cfg["thresholds"]["CognitiveComplexity"], "methods": [], "findings": []},
           "duplication": []}
    head_rels = [c["path"] for c in changed if c["status"] != "D"]
    log(f"static analysis: {len(changed)} changed Java files")
    out["tools"]["checkstyle"], out["checkstyle"] = _checkstyle(cfg, work_dir, changed, shas, head_lines, sd, raw, budget,
                                                                 cs, base_branch, java_cache)
    out["tools"]["pmd"], out["complexity"]["methods"], out["complexity"]["findings"], rules = _pmd(
        cfg, work_dir, repo, base_branch, changed, shas, head_lines, sd, raw, budget, pmd, java_cache, log)
    out["pmd_rules"] = rules or {"status": "unavailable", "reason": out["tools"]["pmd"]["reason"] or "PMD did not run"}
    out["tools"]["cpd"], out["duplication"] = _cpd(cfg, work_dir, changed, head_rels, head_lines, sd, raw, budget,
                                                   pmd, java_cache)
    for name, t in out["tools"].items():
        log(f"  {name}: {t['status']}" + (f" ({t['reason']})" if t["reason"] else "") + f" {t['seconds']} s")
    return out


def _checkstyle(cfg, work_dir, changed, shas, head_lines, sd, raw, budget, cs, base_branch, java_cache):
    cs_id, cfgs, cs_sha, ok = cs
    version = cfg["tools"][cs_id]["version"] if cs_id else None
    head_rels = [c["path"] for c in changed if c["status"] != "D" and run.checkstyle_scope(c["path"])]
    n = len(head_rels)
    if not n:
        return tool_result("not-applicable", "no changed files under src/java or test", version), []
    if not cs_id or not cfgs:
        return tool_result("unknown", f"no checkstyle config on {base_branch}", version, n), []
    if not ok:
        return tool_result("unknown", "checkstyle not installed: run `cpr tools install`", version, n), []
    java, _, err = _env(java_cache, cfg["tools"][cs_id]["min_java"], cfg)
    if err:
        return tool_result("unknown", err, version, n), []
    jar = tools.jar_path(work_dir, cs_id)
    root_h, root_b = os.path.join(sd, "head"), os.path.join(sd, "base")

    def side(root, rels, label):
        t = budget.timeout()
        if t is None:
            return {"files": {}, "missing": rels, "problem": "PR time budget exhausted", "seconds": 0}
        return run.run_checkstyle(java, jar, cfgs, root, rels, raw, label, t)

    head = side(root_h, head_rels, "head")
    base_paths = {c["base_path"]: shas["base"][c["base_path"]] for c in changed
                  if c["base_path"] and run.checkstyle_scope(c["base_path"]) and c["base_path"] in shas["base"]}

    def base_runner(paths):
        r = side(root_b, paths, "base")
        return r["files"], r["problem"] or (f"{len(r['missing'])} base files not analyzed" if r["missing"] else None), r["seconds"]

    cache = os.path.join(work_dir, "static-cache", f"{cs_id}-{cs_sha[:12]}")
    base_files, base_problem, base_secs = _cached_side(cache, base_paths, base_runner)
    secs = head["seconds"] + base_secs
    done = n - len(head["missing"])
    if head["problem"] or head["missing"]:
        reason = head["problem"] or f"{len(head['missing'])} of {n} files not analyzed"
        return tool_result("unknown", reason, version, n, done, secs), []
    if base_problem:
        return tool_result("unknown", f"base side: {base_problem}", version, n, done, secs), []
    return (tool_result("ran", None, version, n, done, secs),
            classify.classify_checkstyle(changed, base_files, head["files"], head_lines))


def _pmd(cfg, work_dir, repo, base_branch, changed, shas, head_lines, sd, raw, budget, pmd, java_cache, log):
    pmd_id, ruleset, pmd_sha, ok, aux_cp, aux_note = pmd
    version = cfg["tools"][pmd_id]["version"]
    head_rels = [c["path"] for c in changed if c["status"] != "D"]
    n = len(head_rels)
    limit = cfg["caps"]["pmd_max_files"]
    if len(changed) > limit:
        return tool_result("skipped", f"too large: {len(changed)} changed Java files (limit {limit})", version, n), [], [], None
    if not ok:
        return tool_result("unknown", "PMD not installed: run `cpr tools install`", version, n), [], [], None
    java, env, err = _env(java_cache, cfg["tools"][pmd_id]["min_java"], cfg)
    if err:
        return tool_result("unknown", err, version, n), [], [], None
    pmd_bin = tools.pmd_path(work_dir, pmd_id)

    def side(root, rels, label):
        t = budget.timeout()
        if t is None:
            return {"files": {}, "parse_errors": [], "problem": "PR time budget exhausted", "seconds": 0}
        return run.run_pmd(pmd_bin, env, ruleset, root, rels, raw, label, t, aux_cp if label == "head" else None)

    head = side(os.path.join(sd, "head"), head_rels, "head")
    base_paths = {c["base_path"]: shas["base"][c["base_path"]] for c in changed if c["base_path"] in shas["base"]}
    bad_base = []

    def base_runner(paths):
        r = side(os.path.join(sd, "base"), paths, "base")
        bad = {p for p, _ in r["parse_errors"]}
        bad_base.extend(sorted(bad))
        return {p: f for p, f in r["files"].items() if p not in bad}, r["problem"], r["seconds"]

    cache = os.path.join(work_dir, "static-cache", f"{pmd_id}-{pmd_sha[:12]}")
    base_files, base_problem, base_secs = _cached_side(cache, base_paths, base_runner)
    secs = head["seconds"] + base_secs
    if head["problem"]:
        return tool_result("unknown", head["problem"], version, n, 0, secs), [], [], None
    if base_problem:
        return tool_result("unknown", f"base side: {base_problem}", version, n, 0, secs), [], [], None
    bad = sorted({p for p, _ in head["parse_errors"]} | set(bad_base))
    if bad and len(bad) >= n:
        status, reason = "unknown", f"{len(bad)} file(s) failed to parse: {', '.join(bad[:5])}"
    else:  # report on the files PMD read; the check names the skipped ones and will not pass
        status, reason = "ran", (f"{len(bad)} file(s) failed to parse: {', '.join(bad[:5])}" if bad else None)
    ok_changed = [c for c in changed if c["path"] not in bad and c["base_path"] not in bad]
    head_ok = {p: f for p, f in head["files"].items() if p not in bad}
    methods, findings = classify.classify_complexity(ok_changed, base_files, head_ok, head_lines, cfg["thresholds"])
    tool = tool_result(status, reason, version, n, n - len(bad), secs)
    rules = _rules(cfg, work_dir, repo, base_branch, ok_changed, base_files, head_ok, head_lines, pmd, env, pmd_bin, log)
    return tool, methods, findings, rules


def _rules(cfg, work_dir, repo, base_branch, changed, base_files, head_files, head_lines, pmd, env, pmd_bin, log):
    """The `pmd_rules` section: introduced violations per catalog rule, and which rules are house style."""
    pmd_id, ruleset, pmd_sha, _, aux_cp, aux_note = pmd
    with open(ruleset) as f:
        text = f.read()
    cats = ruleset_mod.catalog(text)
    found = classify.classify_rules(changed, base_files, head_files, head_lines)
    base_ref = clone_mod.base_ref(base_branch)
    tip = clone_mod._git(repo, "rev-parse", base_ref).strip()
    caps = cfg["caps"]
    data, source, note = baseline.obtain(os.path.join(work_dir, "static-cache"), repo, base_ref, base_branch, tip, pmd_bin,
                                         env, text, pmd_id, pmd_sha, caps["baseline_seconds"], caps["pmd_threads"],
                                         cfg["exclude"], log)
    if data is None:
        data, source = baseline.from_touched(base_files), "touched-files"
        note = (f"The branch baseline could not be built ({note}); house style is the density of each rule in the "
                f"base versions of the {len(base_files)} touched file(s), a small sample.")
    shares = baseline.shares(data)
    limit = cfg["house_style_share"]
    rules = []
    for rule, e in found.items():
        share = shares.get(rule, 0.0)
        rules.append({"rule": rule, "category": e["category"] or cats.get(rule), "introduced": e["introduced"],
                      "in_tests": e["in_tests"], "pre_existing": e["pre_existing"], "share": round(share, 3), "house": share >= limit,
                      "locations": e["locations"]})
    rules.sort(key=lambda r: (-r["introduced"], r["rule"]))
    house = sorted(({"rule": r, "category": cats.get(r), "share": round(s, 3)} for r, s in shares.items() if s >= limit),
                   key=lambda h: (-h["share"], h["rule"]))
    return {"status": "ran", "reason": None, "rules_run": len(cats), "type_info": aux_cp is not None,
            "type_note": aux_note, "threshold": limit,
            "baseline": {"source": source, "branch": base_branch, "tip": data.get("tip", tip), "files": data["files_scanned"],
                         "seconds": data.get("seconds"), "built_at": data.get("built_at"), "note": note},
            "house_style": house, "rules": rules}


def _cpd(cfg, work_dir, changed, head_rels, head_lines, sd, raw, budget, pmd, java_cache):
    pmd_id, ok = pmd[0], pmd[3]
    version = cfg["tools"][pmd_id]["version"]
    n = len(head_rels)
    if not ok:
        return tool_result("unknown", "PMD not installed: run `cpr tools install`", version, n), []
    _, env, err = _env(java_cache, cfg["tools"][pmd_id]["min_java"], cfg)
    t = budget.timeout()
    if err or t is None:
        return tool_result("unknown", err or "PR time budget exhausted", version, n), []
    res = run.run_cpd(tools.pmd_path(work_dir, pmd_id), env, cfg["cpd_min_tokens"], os.path.join(sd, "head"),
                      head_rels, raw, t)
    if res["problem"]:
        return tool_result("unknown", res["problem"], version, n, 0, res["seconds"]), []
    status, reason = ("ran", None) if res["analyzed"] >= n else ("unknown", f"{n - res['analyzed']} of {n} files not analyzed")
    return (tool_result(status, reason, version, n, min(res["analyzed"], n), res["seconds"]),
            classify.classify_duplication(res["duplicates"], changed, head_lines))
