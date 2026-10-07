"""Render the PR's diff with the installed rustyrazorblade dev-skills ide-explain generator.

The generator's page is embedded in our report inside a sandboxed iframe (see design D5).
"""

import base64
import glob
import os
import re
import subprocess
import tempfile

PLUGIN_GLOB = os.path.expanduser(
    "~/.claude/plugins/cache/rustyrazorblade-plugins/dev-skills/*/skills/ide-explain/scripts/generate-explain.py")
SIZE_BUDGET = 8 * 1024 * 1024
_NETWORK_RE = re.compile(r"<script[^>]+src=|<link[^>]+href=\s*[\"']https?:|@import|fetch\(", re.IGNORECASE)


def _version_key(path):
    m = re.search(r"/dev-skills/([^/]+)/", path)
    parts = re.findall(r"\d+", m.group(1)) if m else []
    return [int(p) for p in parts]


def find_generator(env=os.environ):
    """(path, version) of the newest installed generator, or (None, None)."""
    override = env.get("CPR_IDE_EXPLAIN")
    if override:
        return (override, "override") if os.path.exists(override) else (None, None)
    candidates = sorted(glob.glob(PLUGIN_GLOB), key=_version_key)
    if not candidates:
        return None, None
    path = candidates[-1]
    m = re.search(r"/dev-skills/([^/]+)/", path)
    return path, (m.group(1) if m else "unknown")


def unavailable(reason, version=None):
    return {"status": "unavailable", "reason": reason, "version": version, "html_b64": None, "omitted": []}


def explain_map(checks):
    """Per-file notes for the explanation pane, built from check evidence that names a file."""
    notes = {}
    for c in checks:
        if c["status"] not in ("fail", "warn"):
            continue
        for e in c.get("evidence", []):
            loc = e.get("location")
            if not loc:
                continue
            path = loc.split(":", 1)[0]
            notes.setdefault(path, []).append(f"- **{c['title']}** ({c['status']}): {e['text']}")
    return {p: "Flagged by cassandra-pr-review:\n\n" + "\n".join(lines) for p, lines in notes.items()}


def render(bundle, checks, runner=subprocess.run, env=os.environ, scope_paths=None):
    gen, version = find_generator(env)
    if not gen:
        return unavailable("The rustyrazorblade dev-skills plugin (ide-explain) is not installed.")
    pr = bundle["pr"]
    clone = bundle["git"]["clone"]
    with tempfile.TemporaryDirectory(prefix="cpr-explain-") as tmp:
        out = os.path.join(tmp, "explain.html")
        emap = os.path.join(tmp, "explain-map.json")
        import json
        with open(emap, "w") as f:
            json.dump(explain_map(checks), f)
        cmd = ["python3", gen, "--diff", "--base", bundle["git"]["merge_base"], "--head", bundle["git"]["head_ref"],
               "--pr", str(pr["number"]), "--explain-map", emap,
               "--title", f"#{pr['number']} {pr['title']}"[:200], "--subtitle", f"{pr['head_ref']} → {pr['base']}",
               "--out", out]
        for p in scope_paths or []:
            cmd += ["--path", p]
        proc = runner(cmd, cwd=clone, capture_output=True, text=True)
        if proc.returncode != 0 or not os.path.exists(out):
            return unavailable(f"ide-explain failed: {(proc.stderr or proc.stdout or '').strip()[-500:]}", version)
        with open(out, "rb") as f:
            data = f.read()
    if len(data) > SIZE_BUDGET and not scope_paths:
        scoped = render(bundle, checks, runner, env, scope_paths=["src/"])
        if scoped["status"] == "ok":
            scoped["omitted"] = ["Diff view limited to src/ because the full view exceeded "
                                 f"{SIZE_BUDGET // (1024 * 1024)} MB; tests and other files are listed in the file table."]
        return scoped
    if len(data) > SIZE_BUDGET:
        return unavailable(f"Diff view is {len(data) // (1024 * 1024)} MB even when limited to src/; too large to embed.",
                           version)
    if _NETWORK_RE.search(data.decode("utf-8", "replace")):
        return unavailable("ide-explain output referenced network resources; not embedded.", version)
    return {"status": "ok", "reason": None, "version": version,
            "html_b64": base64.b64encode(data).decode("ascii"), "omitted": []}
