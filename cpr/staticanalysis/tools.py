"""Pinned static-analysis tools: download, verify sha256, unpack, and find a suitable JDK.

Tools live in `<work>/tools/<tool>-<version>/`. A `.verified` marker holds the sha256 that was
checked, so an installed tool is never downloaded or unpacked again. Nothing is unpacked unless the
digest matches.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile

from cpr import VERSION

CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "static.json")
MARKER = ".verified"
USER_AGENT = f"cassandra-pr-review/{VERSION} (read-only)"


class ToolError(Exception):
    pass


def load_config(path=CONFIG):
    with open(path) as f:
        return json.load(f)


def tools_dir(work_dir):
    return os.path.join(work_dir, "tools")


def tool_dir(work_dir, tool_id):
    return os.path.join(tools_dir(work_dir), tool_id)


def checkstyle_id(cfg, base_branch):
    """The pinned checkstyle tool id for a base branch family, or None (cassandra-4.0 and older have none)."""
    known = cfg["checkstyle_by_branch"]
    if base_branch in known:
        return known[base_branch]
    m = re.fullmatch(r"cassandra-(\d+)\.(\d+)", base_branch or "")
    if m and (int(m[1]), int(m[2])) > (5, 0):
        return known["trunk"]
    return None


def is_installed(work_dir, tool_id):
    return os.path.exists(os.path.join(tool_dir(work_dir, tool_id), MARKER))


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_url(url, dest):
    """Download `url` (GET only; file:// works for tests) into `dest`."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as out:
            shutil.copyfileobj(resp, out)
    except OSError as e:
        raise ToolError(f"download failed for {url}: {e}")


def _reusable(work_dir, filename, sha):
    """An earlier download of `filename` under <work>/tools whose digest matches, else None."""
    root = tools_dir(work_dir)
    if not os.path.isdir(root):
        return None
    for d in [root] + [os.path.join(root, n) for n in sorted(os.listdir(root))]:
        p = os.path.join(d, filename)
        if os.path.isfile(p) and sha256_of(p) == sha:
            return p
    return None


def _unzip(src, dest):
    real = os.path.realpath(dest)
    with zipfile.ZipFile(src) as z:
        for info in z.infolist():
            if not os.path.realpath(os.path.join(dest, info.filename)).startswith(real + os.sep):
                raise ToolError(f"unsafe path in archive: {info.filename}")
            z.extract(info, dest)
            mode = info.external_attr >> 16
            if mode:
                os.chmod(os.path.join(dest, info.filename), mode & 0o777)


def install(work_dir, tool_id, cfg=None, fetch=fetch_url, log=print):
    """Install one tool. Returns "present" when already installed, else "downloaded" or "reused"."""
    cfg = cfg or load_config()
    spec = cfg["tools"].get(tool_id)
    if not spec:
        raise ToolError(f"unknown tool {tool_id}")
    target = tool_dir(work_dir, tool_id)
    if is_installed(work_dir, tool_id):
        return "present"
    filename = os.path.basename(spec["url"].replace("%2F", "/"))
    src, how = _reusable(work_dir, filename, spec["sha256"]), "reused"
    scratch = tempfile.mkdtemp(prefix=f"{tool_id}-", dir=_ensure(tools_dir(work_dir)))
    try:
        if not src:
            log(f"downloading {spec['url']}")
            src, how = os.path.join(scratch, filename), "downloaded"
            fetch(spec["url"], src)
            got = sha256_of(src)
            if got != spec["sha256"]:
                raise ToolError(f"{tool_id}: sha256 mismatch (expected {spec['sha256']}, got {got}); nothing installed")
        staging = os.path.join(scratch, "unpacked")
        os.makedirs(staging)
        if spec["kind"] == "zip":
            _unzip(src, staging)
        else:
            shutil.copy(src, os.path.join(staging, filename))
        with open(os.path.join(staging, MARKER), "w") as f:
            f.write(spec["sha256"] + "\n")
        shutil.rmtree(target, ignore_errors=True)
        os.replace(staging, target)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return how


def _ensure(path):
    os.makedirs(path, exist_ok=True)
    return path


def jar_path(work_dir, tool_id):
    d = tool_dir(work_dir, tool_id)
    jars = [n for n in os.listdir(d) if n.endswith(".jar")] if os.path.isdir(d) else []
    return os.path.join(d, jars[0]) if jars else None


def pmd_path(work_dir, tool_id):
    d = tool_dir(work_dir, tool_id)
    if not os.path.isdir(d):
        return None
    for name in sorted(os.listdir(d)):
        p = os.path.join(d, name, "bin", "pmd")
        if os.path.exists(p):
            return p
    return None


def java_major(java):
    """Major version of a `java` executable, or None when it will not run."""
    try:
        proc = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r'version "(\d+)(?:\.(\d+))?', proc.stderr + proc.stdout)
    if not m:
        return None
    return int(m[2]) if m[1] == "1" and m[2] else int(m[1])


def java_candidates(cfg, env=None):
    env = os.environ if env is None else env
    homes = ([env["JAVA_HOME"]] if env.get("JAVA_HOME") else []) + list(cfg.get("java_homes", []))
    found = [os.path.join(h, "bin", "java") for h in homes]
    on_path = shutil.which("java", path=env.get("PATH"))
    return found + ([on_path] if on_path else [])


def find_java(min_major, cfg=None, env=None):
    """(java executable, major) for the first JDK of at least `min_major`; ToolError names what was found."""
    cfg = cfg or load_config()
    seen = []
    for java in java_candidates(cfg, env):
        if not os.path.exists(java):
            continue
        major = java_major(java)
        if major and major >= min_major:
            return java, major
        seen.append(f"{java} is {major or 'unusable'}")
    raise ToolError(f"needs JDK {min_major}+ ({'; '.join(seen) or 'no java found'})")


def java_env(java, env=None):
    """Environment that makes `java` the JVM for wrapper scripts such as pmd."""
    env = dict(os.environ if env is None else env)
    env["JAVA_HOME"] = os.path.dirname(os.path.dirname(os.path.realpath(java)))
    env["PATH"] = os.path.dirname(java) + os.pathsep + env.get("PATH", "")
    return env
