"""Trusted lens checklists: load them from apache/cassandra trunk, pick a tier, plan each lens's bundle.

Checklists are read only with `git show <sha>:<path>` for allow-listed paths, into a directory outside
the PR worktree. Nothing is ever read from the PR head, the PR worktree, or the base branch.
"""

import json
import os
import re
import shutil
import subprocess

from cpr import paths
from cpr.checks.compat import touched_surfaces
from cpr.ingest.clone import CloneError, _git

CONFIG = os.path.join(os.path.dirname(__file__), "config", "lenses.json")
TRIAGE = os.path.join(os.path.dirname(__file__), "config", "triage.json")
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


def extract(clone, sha, refdir, cfg):
    """Write each allow-listed file at `sha` under `refdir` and a manifest.json. Returns the manifest."""
    shutil.rmtree(refdir, ignore_errors=True)
    os.makedirs(refdir)
    files = {}
    for path in cfg["allow"]:
        if path.startswith("/") or ".." in path.split("/"):
            files[path] = {"ok": False, "error": "unsafe path"}
            continue
        text, err = _read(clone, sha, path, cfg["size_cap_bytes"])
        if err is None:
            dest = os.path.join(refdir, path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(text)
        files[path] = {"ok": err is None, "error": err}
    manifest = {"sha": sha, "ref": cfg.get("lens_ref") or DEFAULT_REF, "refdir": refdir, "files": files,
                "missing": sorted(p for p, v in files.items() if not v["ok"])}
    with open(os.path.join(refdir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    return manifest


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

def is_code(path):
    return not paths.is_doc(path) and not paths.is_generated(path) and (
        paths.is_prod(path) or path.endswith(CODE_EXTS))


def _changed_code(bundle):
    return [f for f in bundle.get("files", []) if paths.counted(f) and is_code(f["path"])]


def tier_of(bundle, cfg):
    """(tier, non-test changed lines). Tier is none for a PR that changes no code or test files."""
    files = [f for f in bundle.get("files", []) if paths.counted(f)]
    if not any(is_code(f["path"]) for f in files):
        return "none", 0
    lines = sum(f["additions"] + f["deletions"] for f in files if is_code(f["path"]) and not paths.is_test(f["path"]))
    t = cfg["tiers"]
    return ("small" if lines < t["small_under"] else "large" if lines > t["large_over"] else "medium"), lines


def diff_text(bundle):
    """Added and removed lines of non-test code files, joined."""
    out, keep = [], False
    for line in (bundle.get("diff") or "").split("\n"):
        if line.startswith("diff --git "):
            m = re.match(r"diff --git a/.* b/(.*)$", line)
            keep = bool(m) and is_code(m.group(1)) and not paths.is_test(m.group(1))
        elif keep and line[:1] in "+-" and not line.startswith(("+++", "---")):
            out.append(line[1:])
    return "\n".join(out)


def rank_files(bundle, cfg):
    """Production files by review risk, riskiest first: [{path, lines, risk, reasons}]."""
    with open(TRIAGE) as f:
        conc_paths = json.load(f)["concurrency_paths"]
    w = cfg["risk"]
    prod = [f for f in _changed_code(bundle) if not paths.is_test(f["path"])]
    surfaces = {p for ps in touched_surfaces([f["path"] for f in prod]).values() for p in ps}
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


def plan(bundle, manifest, cfg):
    """{tier, lines, lenses: {name: {status, files, categories, focus, not_reviewed, missing, error}}}."""
    tier, lines = tier_of(bundle, cfg)
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
        entry["missing"] = [p for p in want if not ok(p)]
        if entry["missing"]:
            entry["status"] = "missing"
            entry["error"] = "checklist missing at trunk: " + ", ".join(entry["missing"])
            continue
        entry.update(status="ok", files=[os.path.join(manifest["refdir"], p) for p in want], categories=cats)
        if tier == "large":
            entry.update(focus=top, not_reviewed=rest)
    return {"tier": tier, "lines": lines, "notes": notes, "lenses": lenses}
