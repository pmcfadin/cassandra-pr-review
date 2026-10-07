"""Rate how hard a PR is to review (easy / moderate / hard) from deterministic signals."""

import json
import os

from cpr import paths
from cpr.checks import Context
from cpr.checks.ci import upgrade_sensitive_files
from cpr.checks.compat import touched_surfaces

CONFIG = os.path.join(os.path.dirname(__file__), "config", "triage.json")


def load_config(path=CONFIG):
    with open(path) as f:
        return json.load(f)


def _band(value, bands):
    for b in bands:
        if value > b["over"]:
            return b
    return None


def triage(bundle, config=None):
    cfg = config or load_config()
    files = [f for f in bundle.get("files", []) if paths.counted(f)]
    lines = sum(f["additions"] + f["deletions"] for f in files)
    src_files = [f for f in files if paths.is_prod(f["path"])]
    src_lines = sum(f["additions"] + f["deletions"] for f in src_files)
    signals, points, forced = [], 0, None

    def add(name, value, pts, why=None):
        nonlocal points
        points += pts
        signals.append({"signal": name, "value": value, "points": pts, "why": why})

    b = _band(lines, cfg["size_lines"])
    add("changed lines", f"{lines:,} (excluding generated and test data)", b["points"] if b else 0, b and b["label"])
    b = _band(len(files), cfg["files"])
    add("changed files", len(files), b["points"] if b else 0)

    subs = sorted({s for s in (paths.subsystem(f["path"]) for f in src_files) if s})
    b = _band(len(subs), cfg["subsystems"])
    add("subsystems touched", ", ".join(subs) if subs else "none", b["points"] if b else 0)

    surfaces = touched_surfaces([f["path"] for f in bundle.get("files", [])])
    add("compatibility surfaces", ", ".join(surfaces) if surfaces else "none",
        len(surfaces) * cfg["points_per_compat_surface"])
    hard = [s for s in surfaces if s in cfg["hard_surfaces"]]
    if hard:
        add("high-risk surfaces", ", ".join(hard), len(hard) * cfg["points_hard_surface_extra"])
    serializers = upgrade_sensitive_files(Context(bundle))
    if serializers:
        forced = f"changes serialization or on-disk format code ({', '.join(serializers[:3])})"

    conc = sorted({p for f in src_files for p in cfg["concurrency_paths"] if f["path"].startswith(p)})
    add("concurrency-sensitive paths", ", ".join(conc) if conc else "none", cfg["points_concurrency"] if conc else 0)

    targets = {s["base"] for s in bundle.get("siblings", []) if s.get("is_self") or s.get("state") == "open"}
    b = _band(len(targets), cfg["branches"])
    add("target branches", len(targets), b["points"] if b else 0)

    has_tests = any(paths.test_suite(f["path"]) for f in bundle.get("files", []))
    no_tests = bool(src_files) and not has_tests
    add("production code without tests", "yes" if no_tests else "no", cfg["points_no_tests"] if no_tests else 0)

    r = cfg["rating"]
    rating = "hard" if points >= r["hard_at"] else "moderate" if points >= r["moderate_at"] else "easy"
    capped = None
    if rating == "hard" and lines < cfg["small_change_lines"]:
        rating, capped = "moderate", f"fewer than {cfg['small_change_lines']} changed lines: capped at moderate"
    if forced:
        rating, capped = "hard", None
    split = None
    if src_lines > cfg["split_threshold_src_lines"]:
        largest = sorted(files, key=lambda f: f["additions"] + f["deletions"], reverse=True)[:5]
        split = {"src_lines": src_lines, "threshold": cfg["split_threshold_src_lines"],
                 "largest": [{"path": f["path"], "lines": f["additions"] + f["deletions"]} for f in largest]}
    return {"rating": rating, "points": points, "forced_by": forced, "capped_by": capped, "signals": signals,
            "split_suggestion": split, "lines": lines, "files": len(files)}
