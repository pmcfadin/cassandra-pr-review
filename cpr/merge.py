"""Merge findings that several lenses report about the same issue (deterministic, no model call).

Two findings from different lenses are joined when their texts overlap enough (identifiers and words
of the problem, identifiers of the fix) and, secondarily, their locations are close. Joins are applied
strongest first, and a lens never contributes two findings to one issue. The constants live in
`config/merge.json`; the reasoning is in docs/research/lens-findings-merge-and-eval.md.
"""

import itertools
import json
import os
import re

CONFIG = os.path.join(os.path.dirname(__file__), "config", "merge.json")
SEVERITIES = ("blocker", "major", "minor", "nit")

_STOP = set("a an the and or of to in on is are was be it its this that for with as by at from not no but if "
            "then so than into out up we can may will would should could does do did has have had which what "
            "when where who how also only still any all each more most other such same too very just about "
            "after before over under again there their them they you your".split())
_ID_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
_LOC_RE = re.compile(r"^(.*\.\w+):(\d+)$")


def load_config(path=CONFIG):
    with open(path) as f:
        return json.load(f)


def _stem(w):
    for s in ("ations", "ation", "ings", "ing", "ed", "es", "s"):
        if w.endswith(s) and len(w) - len(s) >= 4:
            return w[:-len(s)]
    return w


def words(text):
    return {_stem(w) for w in re.findall(r"[a-z]+", text.lower()) if w not in _STOP and len(w) > 2}


def identifiers(text):
    """Tokens that look like code: camelCase, leading-capitals (SSTable), or dotted (FileUtils.delete)."""
    out = set()
    for m in _ID_RE.findall(text):
        if m.endswith("java"):
            continue
        parts = m.split(".")
        for p in ([m] + parts if len(parts) > 1 else [m]):
            if re.search(r"[a-z][A-Z]", p) or re.match(r"[A-Z]{2,}[a-z]", p) or (len(parts) > 1 and p == m):
                out.add(p)
    return out


def _jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 0.0


def parse_location(loc):
    m = _LOC_RE.match(loc or "")
    return (m.group(1), int(m.group(2))) if m else (None, None)


def score(a, b, cfg):
    """(text score, location bonus, total) for two findings."""
    w, lb = cfg["weights"], cfg["location_bonus"]
    text = (w["problem_identifiers"] * _jaccard(identifiers(a["problem"]), identifiers(b["problem"]))
            + w["problem_words"] * _jaccard(words(a["problem"]), words(b["problem"]))
            + w["fix_identifiers"] * _jaccard(identifiers(a["fix"]), identifiers(b["fix"])))
    (pa, la), (pb, lbn) = parse_location(a["location"]), parse_location(b["location"])
    if pa is None or pb is None:
        bonus = lb["non_file"]
    elif pa != pb:
        bonus = 0.0
    else:
        d = abs(la - lbn)
        bonus = lb["same_file_near"] if d <= cfg["near_lines"] else lb["same_file_mid"] if d <= cfg["mid_lines"] else 0.0
    return text, bonus, text + bonus


def clusters(findings, cfg=None):
    """Groups of finding indexes that are one issue. Each finding needs `lens`, `problem`, `fix`, `location`."""
    cfg = cfg or load_config()
    parent = list(range(len(findings)))
    lens_of = [{f["lens"]} for f in findings]

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x

    edges = []
    for i, j in itertools.combinations(range(len(findings)), 2):
        if findings[i]["lens"] == findings[j]["lens"]:
            continue
        text, _, total = score(findings[i], findings[j], cfg)
        if text >= cfg["text_floor"] and total >= cfg["merge_threshold"]:
            edges.append((-total, i, j))
    for _, i, j in sorted(edges):  # strongest first
        ri, rj = find(i), find(j)
        if ri != rj and not (lens_of[ri] & lens_of[rj]):
            parent[rj] = ri
            lens_of[ri] |= lens_of[rj]
    groups = {}
    for i in range(len(findings)):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def _rank(severity):
    return SEVERITIES.index(severity) if severity in SEVERITIES else len(SEVERITIES)  # invalid ones sort last


def _primary(members):
    """Highest severity, then the most identifiers (the most specific finding), then the earliest."""
    return min(members, key=lambda f: (_rank(f["severity"]),
                                       -len(identifiers(f["problem"] + " " + f["fix"])), f["_index"]))


def _issue(members):
    primary = _primary(members)
    ordered = [primary] + [m for m in members if m is not primary]
    seen_fixes = {primary["fix"].strip().lower()}
    also = []
    for m in ordered[1:]:
        key = m["fix"].strip().lower()
        if key not in seen_fixes:
            seen_fixes.add(key)
            also.append({"lens": m["lens"], "fix": m["fix"]})
    by_position = sorted(members, key=lambda f: f["_index"])
    lenses, locations = [], []
    for m in by_position:
        if m["lens"] not in lenses:
            lenses.append(m["lens"])
        if m["location"] not in locations:
            locations.append(m["location"])
    issue = {
        "id": None,
        "severity": primary["severity"],
        "severity_spread": sorted((m["severity"] for m in members), key=_rank),
        "lenses": lenses,
        "rule": primary["rule"], "problem": primary["problem"], "fix": primary["fix"],
        "location": primary["location"], "locations": locations,
        "also_fixes": also,
        "members": [{"lens": m["lens"], "id": m["id"]} for m in ordered],
        "impact": primary.get("impact"), "confidence": primary.get("confidence"),
    }
    if primary.get("severity_corrected"):
        issue["severity_corrected"] = primary["severity_corrected"]
    return issue, by_position[0]["_index"]


def merge_findings(findings, cfg=None):
    """Merged issues, most severe first, from findings that each carry a `lens` name."""
    cfg = cfg or load_config()
    indexed = [dict(f, _index=i) for i, f in enumerate(findings)]
    built = [_issue([indexed[i] for i in group]) for group in clusters(indexed, cfg)]
    built.sort(key=lambda t: (_rank(t[0]["severity"]), -len(t[0]["lenses"]), t[1]))
    issues = []
    for n, (issue, _) in enumerate(built, 1):
        issue["id"] = f"issue-{n}"
        issues.append(issue)
    return issues


def issues_of(review):
    """The merged issues of a review result; computed from its lens findings when it carries none."""
    if review.get("issues") is not None:
        return review["issues"]
    flat = [dict(f, lens=l["name"]) for l in review.get("lenses", []) for f in l.get("findings", [])]
    return merge_findings(flat)
