"""The sandbox-exec wrapper, the scrubbed environment, and the shared-clone integrity check.

Every command that executes PR code goes through `wrap`; nothing here runs a process.
"""

import hashlib
import os
import re

ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
PROFILE = os.path.join(ASSETS, "sandbox.sb")
PROFILE_NET = os.path.join(ASSETS, "sandbox-net.sb")
BASE_PATH = ("/usr/bin", "/bin", "/usr/sbin", "/sbin")


def norm(path):
    return os.path.realpath(os.path.abspath(os.path.expanduser(path)))


def params(root, work_dir, run, wt, m2, objects, home, gradle=None):
    """The -D parameters the profile needs, as an ordered dict. Paths must be absolute and normalized."""
    prm = {
        "WT": norm(wt), "M2": norm(m2), "GIT": norm(os.path.join(wt, ".git")), "HOME": norm(home),
        "ROOT": norm(root), "WORK": norm(work_dir), "RUN": norm(run), "OBJECTS": norm(objects),
    }
    if gradle:  # only the net profile uses it
        prm["GRADLE"] = norm(gradle)
    return prm


def wrap(argv, prm, profile=PROFILE):
    """`sandbox-exec -D K=V ... -f profile argv`."""
    cmd = ["sandbox-exec"]
    for k, v in prm.items():
        cmd += ["-D", f"{k}={v}"]
    return cmd + ["-f", profile, *argv]


def scrubbed_env(java_home, ant_dir, home, extra=None, ant_heap="1g"):
    """Only what the build needs: no tokens, no inherited variables."""
    path = list(BASE_PATH) + ([ant_dir] if ant_dir else []) + [os.path.join(java_home, "bin")]
    env = {"PATH": os.pathsep.join(path), "JAVA_HOME": java_home, "HOME": home,
           "JAVA_TOOL_OPTIONS": "-Djava.net.preferIPv4Stack=true", "ANT_OPTS": f"-Xmx{ant_heap}"}
    env.update(extra or {})
    return env


def artifact_pattern(cfg):
    return re.compile("|".join(re.escape(p) for p in cfg["sandbox_artifact_patterns"]))


def clone_state(clone):
    """Config text and per-file hashes of the hooks of the shared fetch clone."""
    gitdir = os.path.join(clone, ".git")
    try:
        with open(os.path.join(gitdir, "config"), errors="replace") as f:
            config = f.read()
    except OSError:
        config = None
    hooks = {}
    hdir = os.path.join(gitdir, "hooks")
    for dp, _, fs in os.walk(hdir):
        for name in fs:
            p = os.path.join(dp, name)
            try:
                with open(p, "rb") as f:
                    hooks[os.path.relpath(p, hdir)] = hashlib.sha256(f.read()).hexdigest()
            except OSError:
                hooks[os.path.relpath(p, hdir)] = None
    return {"config": config, "hooks": hooks}


def clone_changes(before, after):
    """Human-readable differences between two clone_state results (empty when unchanged)."""
    out = []
    if before["config"] != after["config"]:
        out.append("config changed")
    for name in sorted(set(before["hooks"]) | set(after["hooks"])):
        if name not in before["hooks"]:
            out.append(f"hook added: {name}")
        elif name not in after["hooks"]:
            out.append(f"hook removed: {name}")
        elif before["hooks"][name] != after["hooks"][name]:
            out.append(f"hook modified: {name}")
    return out
