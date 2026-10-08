"""Run checkstyle, PMD and CPD on a tree of extracted files and parse their XML.

Each runner returns a plain dict with a `problem` string (None when the tool ran) and `seconds`;
the parsers take XML text and a root directory so unit tests can use recorded output.
Exit codes: checkstyle exits with its error count, so any exit is fine when the XML parses;
PMD and CPD exit 0 (clean) or 4 (findings) when they ran.
"""

import os
import re
import signal
import subprocess
import time
import xml.etree.ElementTree as ET

from cpr.ingest.clone import show

CHECKSTYLE_FILES = (".build/checkstyle.xml", ".build/checkstyle_suppressions.xml", ".build/checkstyle_test.xml")
_QUOTED = re.compile(r"'([^']+)'")
_SCORE = re.compile(r"of (\d+)")
COMPLEXITY_RULES = ("CognitiveComplexity", "CyclomaticComplexity", "NPathComplexity")
MESSAGE_CAP = 200


def _tag(el):
    return el.tag.rsplit("}", 1)[-1]


def _rel(name, root):
    prefix = root.rstrip("/") + "/"
    return name[len(prefix):] if name.startswith(prefix) else name


def execute(cmd, env, timeout, cwd=None):
    """Run cmd in its own process group. Returns (returncode or None on timeout, stdout, stderr, seconds)."""
    start = time.monotonic()
    proc = subprocess.Popen(cmd, env=env, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
        rc = None
    return rc, out, err, round(time.monotonic() - start, 2)


def first_line(text):
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()[:300]
    return "no output"


def _write_list(path, root, rels):
    with open(path, "w") as f:
        f.write("".join(os.path.join(root, r) + "\n" for r in rels))


# ---- checkstyle ---------------------------------------------------------------------------------

def fetch_configs(clone, base_ref, dest):
    """Copy the base branch's checkstyle configs into dest. None when the branch has no checkstyle.xml."""
    texts = {n: show(clone, base_ref, n) for n in CHECKSTYLE_FILES}
    if texts[CHECKSTYLE_FILES[0]] is None or texts[CHECKSTYLE_FILES[1]] is None:
        return None
    os.makedirs(dest, exist_ok=True)
    cfgs = {}
    for name, text in texts.items():
        if text is not None:
            cfgs[os.path.basename(name)] = os.path.join(dest, os.path.basename(name))
            with open(cfgs[os.path.basename(name)], "w") as f:
                f.write(text)
    return cfgs


def checkstyle_scope(rel):
    """Which config applies: ant checks src/java with checkstyle.xml and test/ with checkstyle_test.xml."""
    return "main" if rel.startswith("src/java/") else "test" if rel.startswith("test/") else None


def parse_checkstyle(xml_text, root):
    """{rel: [{line, column, severity, message, rule, source}]} with one key per <file> element."""
    out = {}
    for f in ET.fromstring(xml_text).iter("file"):
        errs = out.setdefault(_rel(f.get("name"), root), [])
        for e in f.iter("error"):
            source = e.get("source") or ""
            rule = source.rsplit(".", 1)[-1]
            errs.append({"line": int(e.get("line") or 0), "column": int(e.get("column") or 0),
                         "severity": e.get("severity"), "message": e.get("message") or "",
                         "rule": rule[:-5] if rule.endswith("Check") else rule, "source": source})
    return out


def attach_text(errors, root, rel):
    """Add the trimmed source line text to each error (it disambiguates identical messages)."""
    try:
        with open(os.path.join(root, rel), errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        lines = []
    for e in errors:
        e["text"] = lines[e["line"] - 1].strip() if 0 < e["line"] <= len(lines) else ""


def run_checkstyle(java, jar, cfgs, root, rels, scratch, label, timeout):
    """Checkstyle over rels (relative to root). {files: {rel: [errors]}, missing: [rel], problem, seconds}."""
    files, seconds, problem = {}, 0.0, None
    for scope, cfg_name in (("main", "checkstyle.xml"), ("test", "checkstyle_test.xml")):
        group = [r for r in rels if checkstyle_scope(r) == scope]
        if not group:
            continue
        if cfg_name not in cfgs:
            problem = problem or f"no {cfg_name} on the base branch"
            continue
        tag = f"{label}-{scope}"
        logdir = os.path.join(scratch, f"{tag}-log")
        os.makedirs(logdir, exist_ok=True)
        props, out_xml = os.path.join(scratch, f"{tag}.properties"), os.path.join(scratch, f"{tag}.xml")
        with open(props, "w") as f:
            f.write(f"checkstyle.log.dir={logdir}\ncheckstyle.suppressions={cfgs['checkstyle_suppressions.xml']}\n")
        cmd = [java, "-jar", jar, "-c", cfgs[cfg_name], "-p", props, "-f", "xml", "-o", out_xml] + \
              [os.path.join(root, r) for r in group]
        rc, _, err, secs = execute(cmd, None, timeout)
        seconds += secs
        if rc is None:
            problem = problem or f"timed out after {timeout:.0f} s"
            continue
        try:
            with open(out_xml) as f:
                files.update(parse_checkstyle(f.read(), root))
        except (OSError, ET.ParseError):
            problem = problem or f"checkstyle failed: {first_line(err)}"
    for rel in files:
        attach_text(files[rel], root, rel)
    missing = [r for r in rels if checkstyle_scope(r) and r not in files]
    return {"files": files, "missing": missing, "problem": problem, "seconds": round(seconds, 2)}


# ---- PMD ----------------------------------------------------------------------------------------

def _category(ruleset):
    """PMD's report names a category 'Error Prone'; the slug is what the ruleset and docs use."""
    return (ruleset or "").lower().replace(" ", "")


def parse_pmd(xml_text, root):
    """-> ({rel: {bodies, m, v}}, [(rel, message)]).

    bodies: [[cls, meth, begin, end]]; m: method-level complexity rows [[cls, sig, rule, score, line]] (class-level
    cyclomatic violations have no `method` attribute); v: every other rule's violations
    [[rule, category slug, begin line, end line, message]].
    """
    top = ET.fromstring(xml_text)
    files, errors = {}, []
    for el in top:
        kind = _tag(el)
        if kind == "error":
            errors.append((_rel(el.get("filename") or "", root), (el.get("msg") or "").strip()[:200]))
        elif kind == "file":
            entry = files.setdefault(_rel(el.get("name"), root), {"bodies": [], "m": [], "v": []})
            for v in el:
                rule, cls, meth = v.get("rule"), v.get("class"), v.get("method")
                begin, end = int(v.get("beginline")), int(v.get("endline"))
                if rule == "MethodBody":
                    entry["bodies"].append([cls, meth, begin, end])
                elif rule in COMPLEXITY_RULES:
                    if meth is not None:
                        text = (v.text or "").strip()
                        sig, score = _QUOTED.search(text), _SCORE.search(text)
                        if sig and score:
                            entry["m"].append([cls, sig.group(1), rule, int(score.group(1)), begin])
                else:
                    entry["v"].append([rule, _category(v.get("ruleset")), begin, end,
                                       " ".join((v.text or "").split())[:MESSAGE_CAP]])
    return files, errors


def count_pmd_files(xml_path):
    """Stream a big PMD report -> ({rule: files with it}, files listed, [(file, message)] errors, {rule: violations}).

    Used for the baseline, where the report can run to hundreds of MB.
    """
    hits, listed, errors, counts = {}, 0, [], {}
    current = None
    for event, el in ET.iterparse(xml_path, events=("start", "end")):
        kind = _tag(el)
        if event == "start":
            if kind == "file":
                current = set()
            continue
        if kind == "violation" and current is not None:
            current.add(el.get("rule"))
            counts[el.get("rule")] = counts.get(el.get("rule"), 0) + 1
        elif kind == "file":
            for r in current or ():
                hits[r] = hits.get(r, 0) + 1
            listed += 1
            current = None
        elif kind == "error":
            errors.append((el.get("filename") or "", (el.get("msg") or "").strip()[:200]))
        if kind in ("violation", "file", "error"):
            el.clear()
    return hits, listed, errors, counts


def _jvm_tool(java_env_, cmd, timeout, scratch):
    rc, _, err, secs = execute(cmd, java_env_, timeout, cwd=scratch)
    if rc is None:
        return None, f"timed out after {timeout:.0f} s", secs
    if rc not in (0, 4):
        return None, f"exit {rc}: {first_line(err)}", secs
    return rc, None, secs


def pmd_command(pmd, ruleset, lst, out, aux=None, threads=None):
    cmd = [pmd, "check", "-R", ruleset, "--file-list", lst, "-f", "xml", "-r", out, "--no-progress", "--no-cache"]
    if aux:
        cmd += ["--aux-classpath", aux]
    if threads:
        cmd += ["-t", str(threads)]
    return cmd


def run_pmd(pmd, env, ruleset, root, rels, scratch, label, timeout, aux=None):
    """PMD check with the one-pass ruleset. {files, parse_errors, problem, seconds}.

    aux: a classpath string for type resolution (classes dirs and jars), or None to run without type info.
    """
    lst, out = os.path.join(scratch, f"{label}-pmd.list"), os.path.join(scratch, f"{label}-pmd.xml")
    _write_list(lst, root, rels)
    cmd = pmd_command(pmd, ruleset, lst, out, aux)
    rc, problem, secs = _jvm_tool(env, cmd, timeout, scratch)
    if problem:  # never publish local paths
        problem = problem.replace(root.rstrip("/") + "/", "").replace(scratch.rstrip("/") + "/", "")
    res = {"files": {}, "parse_errors": [], "problem": problem, "seconds": secs}
    if problem and not (rc is None and problem.startswith("exit ") and os.path.exists(out)):
        return res
    try:
        with open(out) as f:
            res["files"], res["parse_errors"] = parse_pmd(f.read(), root)
        if problem and not res["parse_errors"]:
            return res  # the run failed and the report does not say why per file: keep the failure
        res["problem"] = None
        failed = {p for p, _ in res["parse_errors"]}
        for rel in rels:  # PMD lists only files with violations; the rest have no methods
            if rel not in failed:
                res["files"].setdefault(rel, {"bodies": [], "m": [], "v": []})
    except (OSError, ET.ParseError) as e:
        res["problem"] = problem or f"unreadable PMD output: {e}"
    return res


# ---- CPD ----------------------------------------------------------------------------------------

def parse_cpd(xml_text, root):
    """-> ({tokens, lines, occurrences: [{file, line, endline}]} list, number of files CPD tokenized)."""
    top = ET.fromstring(xml_text)
    dups, analyzed = [], 0
    for el in top:
        if _tag(el) == "file":
            analyzed += 1
        elif _tag(el) == "duplication":
            dups.append({"tokens": int(el.get("tokens")), "lines": int(el.get("lines")),
                         "occurrences": [{"file": _rel(f.get("path"), root), "line": int(f.get("line")),
                                          "endline": int(f.get("endline"))} for f in el if _tag(f) == "file"]})
    return dups, analyzed


def run_cpd(pmd, env, min_tokens, root, rels, scratch, timeout):
    """CPD over rels. {duplicates, analyzed, problem, seconds}."""
    lst, out = os.path.join(scratch, "head-cpd.list"), os.path.join(scratch, "head-cpd.xml")
    _write_list(lst, root, rels)
    cmd = [pmd, "cpd", "--minimum-tokens", str(min_tokens), "--language", "java", "--file-list", lst,
           "--format", "xml", "-r", out]
    rc, problem, secs = _jvm_tool(env, cmd, timeout, scratch)
    res = {"duplicates": [], "analyzed": 0, "problem": problem, "seconds": secs}
    if problem:
        return res
    try:
        with open(out) as f:
            res["duplicates"], res["analyzed"] = parse_cpd(f.read(), root)
    except (OSError, ET.ParseError) as e:
        res["problem"] = f"unreadable CPD output: {e}"
    return res
