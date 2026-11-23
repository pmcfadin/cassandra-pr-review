"""Trusted lens checklists: load them from apache/cassandra trunk, pick a tier, plan each lens's bundle.

Checklists are read only with `git show <sha>:<path>` for allow-listed paths, into a directory outside
the PR worktree. Nothing is ever read from the PR head, the PR worktree, or the base branch. The checklists
always come from apache/cassandra, whichever project the PR is in; a subproject's own guides
(`lenses.guides` in its profile) come from that project's trunk, the same way, into `<refdir>/<slug>/`.
"""

import json
import os
import re
import shutil
import subprocess

from cpr import layout, paths, project as project_mod
from cpr.ingest import clone as clone_mod
from cpr.checks.compat import touched_surfaces
from cpr.ingest.clone import CloneError, _git

CONFIG = os.path.join(os.path.dirname(__file__), "config", "lenses.json")
TRIAGE = os.path.join(os.path.dirname(__file__), "config", "triage.json")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_REF = "origin/trunk"
CODE_EXTS = (".java", ".py", ".g", ".jj", ".kt", ".sh")


def load_config(path=CONFIG):
    with open(path) as f:
        return json.load(f)


# ---- trusted extraction -------------------------------------------------------------------------

def resolve(clone, ref=None):
    """Commit sha for `ref` (default origin/trunk) in the clone."""
    out = _git(clone, "rev-parse", "--verify", "--quiet", f"{ref or DEFAULT_REF}^{{commit}}", check=False).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", out):
        raise CloneError(f"cannot resolve {ref or DEFAULT_REF} in {clone}")
    return out


def _read(clone, sha, path, cap):
    """(text, error) for `path` at `sha`."""
    proc = subprocess.run(["git", "-C", clone, "show", f"{sha}:{path}"], capture_output=True)
    if proc.returncode != 0:
        return None, f"not found at {sha[:12]}"
    if len(proc.stdout) > cap:
        return None, f"{len(proc.stdout)} bytes exceeds the {cap} byte cap"
    try:
        return proc.stdout.decode("utf-8"), None
    except UnicodeDecodeError:
        return None, "not valid UTF-8"


def _write(clone, sha, root, paths, cap):
    """{path: {ok, error}} after writing each of `paths` at `sha` under `root`."""
    files = {}
    for path in paths:
        if path.startswith("/") or ".." in path.split("/"):
            files[path] = {"ok": False, "error": "unsafe path"}
            continue
        text, err = _read(clone, sha, path, cap)
        if err is None:
            dest = os.path.join(root, path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(text)
        files[path] = {"ok": err is None, "error": err}
    return files


def extract(clone, sha, refdir, cfg):
    """Write each allow-listed file at `sha` under `refdir` and a manifest.json. Returns the manifest."""
    shutil.rmtree(refdir, ignore_errors=True)
    os.makedirs(refdir)
    files = _write(clone, sha, refdir, cfg["allow"], cfg["size_cap_bytes"])
    manifest = {"sha": sha, "ref": cfg.get("lens_ref") or DEFAULT_REF, "refdir": refdir, "files": files,
                "missing": sorted(p for p, v in files.items() if not v["ok"])}
    with open(os.path.join(refdir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    return manifest


def extract_guides(clone, sha, refdir, proj, cfg):
    """Write the project's own guides at `sha` (its trunk) under `<refdir>/<slug>/`; record them in the manifest.

    Returns {sha, root, files, missing}. Call after `extract`, which empties the refdir.
    """
    root = os.path.join(refdir, proj.slug)
    files = _write(clone, sha, root, sorted(proj.lens_guides), cfg["size_cap_bytes"])
    guides = {"sha": sha, "root": root, "files": files, "missing": sorted(p for p, v in files.items() if not v["ok"])}
    path = os.path.join(refdir, "manifest.json")
    with open(path) as f:
        manifest = json.load(f)
    manifest["guides"] = guides
    with open(path, "w") as f:
        json.dump(manifest, f, indent=1)
    return guides


# ---- INDEX diff signals -------------------------------------------------------------------------

_TICK = re.compile(r"`([^`]+)`")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _signal_regex(token):
    """A regex source for one backticked token of an INDEX bullet, or None when it is too generic."""
    token = token.strip().rstrip("()").rstrip(".")
    if not token:
        return None
    if re.fullmatch(r"[A-Za-z_][\w.]*\*?", token):  # identifier, dotted name, or prefix wildcard (VERSION_*)
        if len(token) < 4:
            return None
        return r"\b" + re.escape(token.rstrip("*")) + (r"\w*" if token.endswith("*") else r"\b")
    idents = [i for i in _IDENT.findall(token) if len(i) >= 5]  # `if (version >= ...)` -> version
    return r"\b(?:" + "|".join(re.escape(i) for i in idents) + r")\b" if len(idents) == 1 else None


def parse_index(text):
    """{category: [regex source, ...]} from "## <category>" sections with a "Diff signals" bullet list."""
    cats, cur, in_signals = {}, None, False
    for line in text.splitlines():
        if line.startswith("## "):
            cur, in_signals = line[3:].strip(), False
            cats[cur] = []
        elif cur and line.lower().startswith("**diff signals"):
            in_signals = True
        elif cur and in_signals and line.startswith("- "):
            for token in _TICK.findall(line):
                rx = _signal_regex(token)
                if rx and rx not in cats[cur]:
                    cats[cur].append(rx)
        elif in_signals and line.strip() and not line.startswith(("-", " ")):
            in_signals = False
    return {c: s for c, s in cats.items() if s}


def match_categories(signals, diff_text, extra=None, min_signals=2):
    """[(category, score)] strongest first. Score = distinct signals matched, with extra signals counting 3."""
    scored = []
    for cat, rxs in signals.items():
        score = sum(1 for rx in rxs if re.search(rx, diff_text))
        score += sum(3 for w in (extra or {}).get(cat, []) if re.search(r"\b" + re.escape(w), diff_text))
        if score >= min_signals:
            scored.append((cat, score))
    return sorted(scored, key=lambda cs: (-cs[1], cs[0]))


# ---- tiers --------------------------------------------------------------------------------------

def is_code(path, classify=paths):
    return not classify.is_doc(path) and not classify.is_generated(path) and (
        classify.is_prod(path) or path.endswith(CODE_EXTS))


def _changed_code(bundle):
    pc = paths.of(bundle)
    return [f for f in bundle.get("files", []) if pc.counted(f) and is_code(f["path"], pc)]


def tier_of(bundle, cfg):
    """(tier, non-test changed lines). Tier is none for a PR that changes no code or test files."""
    pc = paths.of(bundle)
    files = [f for f in bundle.get("files", []) if pc.counted(f)]
    if not any(is_code(f["path"], pc) for f in files):
        return "none", 0
    lines = sum(f["additions"] + f["deletions"] for f in files if is_code(f["path"], pc) and not pc.is_test(f["path"]))
    t = cfg["tiers"]
    return ("small" if lines < t["small_under"] else "large" if lines > t["large_over"] else "medium"), lines


def diff_text(bundle):
    """Added and removed lines of non-test code files, joined."""
    pc = paths.of(bundle)
    out, keep = [], False
    for line in (bundle.get("diff") or "").split("\n"):
        if line.startswith("diff --git "):
            m = re.match(r"diff --git a/.* b/(.*)$", line)
            keep = bool(m) and is_code(m.group(1), pc) and not pc.is_test(m.group(1))
        elif keep and line[:1] in "+-" and not line.startswith(("+++", "---")):
            out.append(line[1:])
    return "\n".join(out)


def rank_files(bundle, cfg):
    """Production files by review risk, riskiest first: [{path, lines, risk, reasons}]."""
    proj = project_mod.of(bundle)
    with open(TRIAGE) as f:
        conc_paths = {**json.load(f), **proj.triage}["concurrency_paths"]
    w = cfg["risk"]
    prod = [f for f in _changed_code(bundle) if not proj.paths.is_test(f["path"])]
    surfaces = {p for ps in touched_surfaces([f["path"] for f in prod], proj).values() for p in ps}
    ranked = []
    for f in prod:
        lines, mult, why = f["additions"] + f["deletions"], 1.0, []
        if f["path"] in surfaces:
            mult += w["compat_surface"]
            why.append("compatibility surface")
        if any(f["path"].startswith(p) for p in conc_paths):
            mult += w["concurrency_path"]
            why.append("concurrency-sensitive path")
        if re.search(r"Serializer|Serialization|/io/sstable/format/", f["path"]):
            mult += w["serializer"]
            why.append("serialization / on-disk format")
        ranked.append({"path": f["path"], "lines": lines, "risk": round(lines * mult, 1), "reasons": why})
    return sorted(ranked, key=lambda r: (-r["risk"], r["path"]))


# ---- plan ---------------------------------------------------------------------------------------

def _read_index(manifest, cfg):
    ent = manifest["files"].get(cfg["index"], {})
    if not ent.get("ok"):
        return None
    with open(os.path.join(manifest["refdir"], cfg["index"]), encoding="utf-8") as f:
        return f.read()


def plan(bundle, manifest, cfg, proj=None):
    """{tier, lines, lenses: {name: {status, files, categories, focus, not_reviewed, missing, error}}}.

    The project's `lenses.drop` paths leave every bundle, and each guide in `manifest["guides"]` joins the
    bundles of the lenses its profile names. A guide missing at the project's trunk is a note, not a missing lens.
    """
    proj = proj or project_mod.of(bundle)
    tier, lines = tier_of(bundle, cfg)
    guides = manifest.get("guides") or {"files": {}, "root": None}
    ok = lambda p: manifest["files"].get(p, {}).get("ok", False)  # noqa: E731
    chosen, notes = {}, []
    if tier == "medium":
        index = _read_index(manifest, cfg)
        signals = parse_index(index) if index else {}
        owner = {c: n for n, l in cfg["lenses"].items() for c in l["categories"]}
        scored = [(c, s) for c, s in match_categories(signals, diff_text(bundle), cfg.get("extra_signals"))
                  if c in owner]
        for cat, _ in scored[:cfg["max_categories"]]:
            chosen.setdefault(owner[cat], []).append(cat)
        if index is None:
            notes.append(f"{cfg['index']} is unavailable: targeted categories could not be chosen")
    notes += [f"{proj.name} guide {p} is unavailable at its trunk: {v['error']}"
              for p, v in sorted(guides["files"].items()) if not v["ok"]]
    ranked = rank_files(bundle, cfg) if tier == "large" else []
    top = ranked[:cfg["focus_files"]]
    rest = [r["path"] for r in ranked[cfg["focus_files"]:]]
    lenses = {}
    for name, l in cfg["lenses"].items():
        entry = {"status": "skipped", "files": [], "categories": [], "focus": [], "not_reviewed": [],
                 "missing": [], "error": None}
        lenses[name] = entry
        if tier == "none":
            continue
        cats = chosen.get(name, [])
        want = l["large"] if tier == "large" else list(l["small"])
        if tier == "medium":
            want += [l["categories"][c] for c in cats]
            if l["categories"] and not ok(cfg["index"]):
                want.append(cfg["index"])
        want = [p for p in want if p not in proj.lens_drop]
        entry["missing"] = [p for p in want if not ok(p)]
        if entry["missing"]:
            entry["status"] = "missing"
            entry["error"] = "checklist missing at trunk: " + ", ".join(entry["missing"])
            continue
        files = [os.path.join(manifest["refdir"], p) for p in want]
        files += [os.path.join(guides["root"], p) for p, v in sorted(guides["files"].items())
                  if v["ok"] and name in proj.lens_guides.get(p, ())]
        entry.update(status="ok", files=files, categories=cats)
        if tier == "large":
            entry.update(focus=top, not_reviewed=rest)
    return {"tier": tier, "lines": lines, "notes": notes, "lenses": lenses}


# ---- prepare ------------------------------------------------------------------------------------

def inputs(proj):
    """The per-project lens inputs of the prepare JSON: the project name and the standards and testing docs."""
    return {"project_name": proj.name, "standards": os.path.join(ROOT, proj.lens_standards),
            "testing_doc": os.path.join(ROOT, proj.lens_testing_doc)}


def checklist_clone(work_dir, target_clone, proj, offline=False):
    """The apache/cassandra clone the checklists come from: the PR's own clone for a Cassandra PR."""
    if proj.slug == project_mod.DEFAULT:
        return target_clone
    path = layout.clone_dir(work_dir, project_mod.load(project_mod.DEFAULT))
    if offline and not os.path.isdir(os.path.join(path, ".git")):
        raise CloneError(f"no apache/cassandra clone at {path} for the checklists; run once without --offline")
    clone_mod.ensure(path)
    return path


def prepare(proj, bundle, d, checklists_from, target_clone, offline=False, log=lambda m: None):
    """Extract the checklists and the project's guides into `<d>/refdir`, plan every lens, write lens-plan.json.

    `checklists_from` is the apache/cassandra clone and `target_clone` the PR project's clone; each one's
    origin/trunk is fetched first unless `offline`.
    """
    cfg = load_config()
    if not offline:
        clone_mod.fetch_trunk(checklists_from)
    sha = resolve(checklists_from, cfg.get("lens_ref"))
    refdir = os.path.join(d, "refdir")
    manifest = extract(checklists_from, sha, refdir, cfg)
    log(f"checklists: apache/cassandra trunk @ {sha[:12]} ({len(manifest['missing'])} missing)")
    checklists = {"sha": sha, "refdir": refdir, "missing": manifest["missing"]}
    if proj.lens_guides:
        if not offline:
            clone_mod.fetch_trunk(target_clone)
        gsha = resolve(target_clone)
        manifest["guides"] = extract_guides(target_clone, gsha, refdir, proj, cfg)
        checklists["guides"] = {"repo": proj.repo, "sha": gsha, "missing": manifest["guides"]["missing"]}
        log(f"guides: {proj.repo} trunk @ {gsha[:12]} ({len(manifest['guides']['missing'])} missing)")
    result = plan(bundle, manifest, cfg, proj)
    result["checklists"] = checklists
    with open(os.path.join(d, "lens-plan.json"), "w") as f:
        json.dump(result, f, indent=1)
    return result
