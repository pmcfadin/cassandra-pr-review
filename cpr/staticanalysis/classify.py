"""Classify findings as introduced or pre-existing by matching, never by line number alone.

Complexity key: (base path via the rename map, class, method signature, rule). Fallbacks: within the
matched base file, a unique same-signature method (the class was renamed); across the PR's base
files, a same-signature method (the method moved). Checkstyle: introduced when the head line was
changed or no equal (rule, message, line text) is left at base. CPD: introduced when an occurrence
overlaps a changed line or every occurrence is in a new file.

Inputs are the parsed tool output from `cpr.staticanalysis.run` and the `changed_java` list.
"""

import collections

COG = "CognitiveComplexity"


def overlaps(ranges, begin, end):
    return any(not (e < begin or s > end) for s, e in ranges)


def _index(files):
    """{rel: {bodies, m: {(cls, sig): {rule: (score, line)}}}} from the JSON-friendly parsed form."""
    out = {}
    for rel, f in files.items():
        m = collections.defaultdict(dict)
        for cls, sig, rule, score, line in f["m"]:
            m[(cls, sig)][rule] = (score, line)
        out[rel] = {"bodies": f["bodies"], "m": m}
    return out


def _body(f, cls, name, line):
    found = [b for b in f["bodies"] if b[0] == cls and b[1] == name and b[2] >= line]
    return min(found, key=lambda b: b[2]) if found else None


def _name(sig):
    return sig.split("(")[0]


def _count(f, cls, name):
    """Bodies named `name` in class `cls`; by name alone when the class does not match (renamed)."""
    n = sum(1 for b in f["bodies"] if b[0] == cls and b[1] == name)
    return n or sum(1 for b in f["bodies"] if b[1] == name)


def _match_base(bf, cls, sig):
    """The base file's (class, signature) key for a head method, or None."""
    if (cls, sig) in bf["m"]:
        return (cls, sig)
    alt = [k for k in bf["m"] if k[1] == sig]
    return alt[0] if len(alt) == 1 else None


def label(score, base, threshold, touched):
    """Classification of a head score against a base score (None = no such method at base)."""
    if score < base:
        return "pre-existing-improved"
    if score == base:
        return "pre-existing-touched" if touched else "pre-existing"
    if score >= threshold:
        return "introduced-worsened" if base >= threshold else "introduced-crossed"
    return "pre-existing-touched"


def _finding(tool, rule, c, base_file, cls, sig, line, score, message, classification):
    return {"tool": tool, "rule": rule, "file": c["path"], "base_file": base_file, "class": cls,
            "method_sig": sig, "line": line, "score": score, "message": message,
            "classification": classification}


def classify_complexity(changed, base_pmd, head_pmd, head_lines, thresholds):
    """-> (methods rows, findings). `thresholds` maps rule name to its reporting threshold."""
    B, H = _index(base_pmd), _index(head_pmd)
    th_cog = thresholds[COG]
    all_base = collections.defaultdict(list)
    for bp, f in B.items():
        for cls, sig in f["m"]:
            all_base[sig].append((bp, cls))
    methods, findings = [], []
    for c in changed:
        if c["status"] == "D" or c["path"] not in H:
            continue
        hp, bp, new_file = c["path"], c["base_path"], c["status"] == "A"
        hf, bf = H[hp], B.get(bp) if bp else None
        ranges = head_lines.get(hp, [])
        used = set()
        for (cls, sig), rules in hf["m"].items():
            cog_line = rules.get(COG, next(iter(rules.values())))[1]
            body = _body(hf, cls, _name(sig), cog_line)
            if body:
                used.add(tuple(body))
            touched = bool(body) and overlaps(ranges, body[2], body[3])
            bkey = _match_base(bf, cls, sig) if bf else None
            existed = bf is not None and bkey is None and _count(bf, cls, _name(sig)) >= \
                sum(1 for b in hf["bodies"] if b[0] == cls and b[1] == _name(sig))
            moved = bf is not None and bkey is None and not existed and \
                any(x != (bp, cls) for x in all_base.get(sig, []))

            def kind(rule, score, base_score=None):
                if new_file:
                    return "introduced-new-file"
                if bf is None or (bkey is None and not existed):
                    return "moved" if moved else "introduced-new-method"
                return label(score, base_score or 0, thresholds[rule], touched)

            base_of = lambda rule: bf["m"][bkey].get(rule, (0,))[0] if bkey else (0 if existed else None)  # noqa: E731
            for rule, (score, line) in rules.items():
                if score >= thresholds[rule]:
                    b = base_of(rule)
                    findings.append(_finding(
                        "pmd", rule, c, bp, cls, sig, line, score,
                        f"{rule} {score}" + (f" (base {b})" if b is not None else " (new)") + f", threshold {thresholds[rule]}",
                        kind(rule, score, b)))
            head_cog = rules.get(COG, (0,))[0]
            base_cog = base_of(COG)
            if touched or base_cog != head_cog or new_file:
                methods.append({"file": hp, "class": cls, "method_sig": sig, "base": base_cog, "head": head_cog,
                                "touched": touched, "classification": kind(COG, head_cog, base_cog)})
        if not new_file:
            for cls, meth, begin, end in hf["bodies"]:
                if tuple([cls, meth, begin, end]) in used or not overlaps(ranges, begin, end):
                    continue
                methods.append({"file": hp, "class": cls, "method_sig": f"{meth}(...)", "base": 0, "head": 0,
                                "touched": True, "classification": "pre-existing-touched"})
        findings += _fixed_complexity(c, bf, hf, H, hp, bp, thresholds, methods, th_cog)
    for c in changed:
        if c["status"] == "D" and c["base_path"] in B:
            findings += _fixed_complexity(c, B[c["base_path"]], None, H, c["path"], c["base_path"], thresholds, [], th_cog)
    return methods, findings


def _fixed_complexity(c, bf, hf, H, hp, bp, thresholds, methods, th_cog):
    """Base breaches with no breach left at head: fixed. Removed scored methods also get a methods row."""
    out = []
    if bf is None:
        return out
    for (cls, sig), rules in bf["m"].items():
        hkey = (cls, sig) if hf and (cls, sig) in hf["m"] else None
        if hf and hkey is None:
            alt = [k for k in hf["m"] if k[1] == sig]
            hkey = alt[0] if len(alt) == 1 else None
        for rule, (score, line) in rules.items():
            head = hf["m"][hkey].get(rule, (0,))[0] if hkey else None
            if score < thresholds[rule] or (head or 0) >= thresholds[rule]:
                continue
            if hkey is None and any(sig == k[1] and any(r in thresholds and s >= thresholds[r] for r, (s, _) in rs.items())
                                    for p, f in H.items() if p != hp for k, rs in f["m"].items()):
                continue  # moved to another file; the head side carries the finding
            out.append(_finding("pmd", rule, c, bp, cls, sig, line, head, f"{rule} {score} -> "
                                + (str(head) if head is not None else "removed"), "fixed"))
        if hf is not None and hkey is None and rules.get(COG, (0,))[0] > 0:
            base_cog = rules[COG][0]
            methods.append({"file": hp, "class": cls, "method_sig": sig, "base": base_cog, "head": None,
                            "touched": False, "classification": "fixed" if base_cog >= th_cog else "pre-existing-improved"})
    return out


def classify_checkstyle(changed, base_cs, head_cs, head_lines):
    """Head errors as introduced or pre-existing, plus base-only errors as fixed."""
    out = []
    for c in changed:
        hp, bp = c["path"], c["base_path"]
        pool = collections.defaultdict(list)
        for e in (base_cs.get(bp) or []) if bp else []:
            pool[(e["rule"], e["message"], e.get("text", ""))].append(e)
        if c["status"] != "D":
            ranges = head_lines.get(hp, [])
            for e in sorted(head_cs.get(hp) or [], key=lambda e: e["line"]):
                key = (e["rule"], e["message"], e.get("text", ""))
                equal = pool[key].pop(0) if pool.get(key) else None
                introduced = c["status"] == "A" or equal is None or overlaps(ranges, e["line"], e["line"])
                out.append(_finding("checkstyle", e["rule"], c, bp, None, None, e["line"], None, e["message"],
                                    "introduced" if introduced else "pre-existing"))
        for errs in pool.values():
            for e in errs:
                out.append(_finding("checkstyle", e["rule"], c, bp, None, None, e["line"], None, e["message"], "fixed"))
    return out


def classify_duplication(dups, changed, head_lines):
    """Add `introduced` to each CPD duplicate (head side)."""
    new_files = {c["path"] for c in changed if c["status"] == "A"}
    out = []
    for d in dups:
        occ = d["occurrences"]
        touched = any(overlaps(head_lines.get(o["file"], []), o["line"], o["endline"]) for o in occ)
        out.append({**d, "introduced": touched or all(o["file"] in new_files for o in occ)})
    return out


# ---- PMD rule catalog ---------------------------------------------------------------------------

LOCATION_CAP = 200  # kept per rule in the bundle; the report model keeps fewer


def _counts(file_entry):
    c = collections.Counter()
    for v in (file_entry or {}).get("v") or []:
        c[v[0]] += 1
    return c


def classify_rules(changed, base_files, head_files, head_lines, cap=LOCATION_CAP):
    """Violations of PMD's catalog rules the patch introduces.

    A violation is introduced when its begin line is an added line of the head file, or the file is new.
    A modified file with no line map falls back to head count minus base count per rule (floored at 0),
    taking the last occurrences. Returns {rule: {category, introduced, in_tests, pre_existing, locations}} for every
    rule that fires in a changed head file; locations are the introduced ones, [file, line, message], capped.
    """
    out = {}
    for c in changed:
        hp = c["path"]
        if c["status"] == "D" or hp not in head_files:
            continue
        vs = head_files[hp].get("v") or []
        if not vs:
            continue
        new_file = c["status"] == "A"
        mapped = new_file or hp in head_lines
        extra = {}  # fallback: how many of each rule to call introduced
        total = collections.Counter(v[0] for v in vs)
        if not mapped:
            base_n = _counts(base_files.get(c["base_path"])) if c["base_path"] else collections.Counter()
            extra = {r: max(0, n - base_n[r]) for r, n in total.items()}
        ranges = head_lines.get(hp, [])
        seen = collections.Counter()
        for rule, cat, begin, _end, msg in sorted(vs, key=lambda v: v[2]):
            seen[rule] += 1
            intro = (new_file or overlaps(ranges, begin, begin)) if mapped else seen[rule] > total[rule] - extra[rule]
            e = out.setdefault(rule, {"category": cat, "introduced": 0, "in_tests": 0, "pre_existing": 0,
                                                     "locations": []})
            if intro:
                e["introduced"] += 1
                e["in_tests"] += hp.startswith("test/")
                if len(e["locations"]) < cap:
                    e["locations"].append([hp, begin, msg])
            else:
                e["pre_existing"] += 1
    return out
