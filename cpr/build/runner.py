"""Run one PR build: throwaway clone, Maven cache copy, sandboxed ant, tests with JaCoCo, status.json.

Only dependency resolution at the merge-base (the base branch's build file) uses the network and runs
outside the sandbox. Everything that executes the PR's code goes through `sandbox.wrap`. All processes
start through a `Shell`, so unit tests pass a fake one and never build anything.

status values (research 5.1): pass, build-failed, tests-failed, timeout, unknown, not-built.
"""

import collections
import glob
import json
import os
import re
import shutil
import time
import xml.etree.ElementTree as ET

from cpr.build import coverage, run_dir, sandbox, select
from cpr.staticanalysis.run import execute

Proc = collections.namedtuple("Proc", "rc out err seconds timed_out")
JAVAC_ERROR = re.compile(r"^\s*(?:\[javac\]\s+)?(\S+\.java):(\d+): error: (.*)$", re.M)
HARNESS = re.compile(r"Unsupported JDK version|Unable to create javax script engine|must be set when building from java")
NETWORK = re.compile(r"UnknownHostException|Could not transfer|Unable to download|Connection refused|Failed to resolve|"
                     r"Unable to resolve|Operation not permitted|Network is unreachable")
ACCORD_MISSING = re.compile(r"cassandra-accord[^\n]*(?:not found|Could not find|Unable to resolve|missing|does not exist)|"
                            r"(?:Could not find|Unable to resolve|missing)[^\n]*cassandra-accord", re.I)
ACCORD_URL_NOTE = "unexpected accord submodule url"
SANDBOX_NOTE = "Failures matching a sandbox artifact (transferTo0 / Operation not permitted) are unknown, not failed."


class Shell:
    """The one place processes start."""

    def run(self, cmd, env=None, cwd=None, timeout=None):
        rc, out, err, seconds = execute(cmd, env, timeout, cwd=cwd)
        return Proc(rc, out, err, seconds, rc is None)

    def which(self, name, dirs=()):
        for d in [os.path.expanduser(x) for x in dirs] + os.environ.get("PATH", "").split(os.pathsep):
            p = os.path.join(d, name)
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return p
        return None


class Stop(Exception):
    """End the run now with this status."""

    def __init__(self, status, reason):
        super().__init__(reason)
        self.status, self.reason = status, reason


def expand(path):
    return os.path.expanduser(path)


def jdk_for(cfg, branch, exists=os.path.isdir):
    """{home, major, label, env} for the base branch, or Stop(unknown) naming the sdk command when missing."""
    b = cfg["branches"].get(branch)
    if b is None:
        raise Stop("unknown", f"no JDK mapping for base branch {branch}")
    major = str(b["jdk"])
    home = next((expand(h) for h in cfg["jdk_homes"].get(major, []) if exists(expand(h))), None)
    if home is None:
        cmd = cfg["sdk_install"].get(major, f"install a JDK {major}")
        raise Stop("unknown", f"JDK {major} is missing for {branch}: run `{cmd}`")
    name = os.path.basename(home)
    label = ("Temurin " + name[:-4]) if name.endswith("-tem") else name
    env = dict(b.get("env") or {})
    if env:
        label += " (" + " ".join(f"{k}={v}" for k, v in env.items()) + ")"
    return {"home": home, "major": int(major), "label": label, "env": env, "jna_swap": bool(b.get("jna_swap"))}


# ---- parsing ------------------------------------------------------------------------------------------

def parse_build_log(text):
    """Compile errors with file:line, newest first-error order kept; capped at 10."""
    return [{"file": m[1], "line": int(m[2]), "message": m[3].strip()[:300]} for m in JAVAC_ERROR.finditer(text or "")][:10]


def empty_junit():
    return {"classes_reported": 0, "run": 0, "failed": 0, "errors": 0, "skipped": 0, "failures": [], "sandbox": [],
            "timeouts": [], "flaky": []}


def apply_retry(tests, retry):
    """Fold a retry of the failing classes into `tests`: a failure that does not recur is flaky, not a failure."""
    still = {(f["class"], f["test"]) for f in retry["failures"] + retry["timeouts"] + retry["sandbox"]}
    persistent, flaky = [], []
    for f in tests["failures"]:
        (persistent if (f["class"], f["test"]) in still else flaky).append(f)
    tests["failures"], tests["flaky"] = persistent, tests.get("flaky", []) + flaky
    tests["failed"] = sum(1 for f in persistent if f.get("kind") != "error")
    tests["errors"] = len(persistent) - tests["failed"]
    return tests


def parse_junit(directory, artifact):
    """Read TEST-*.xml: counts, real failures, sandbox artifacts, class timeouts. Symlinks are ignored."""
    res = empty_junit()
    if not os.path.isdir(directory):
        return res
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if not (name.startswith("TEST-") and name.endswith(".xml")) or os.path.islink(path):
            continue
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            continue
        for suite in [root] if root.tag == "testsuite" else root.iter("testsuite"):
            res["classes_reported"] += 1
            res["run"] += int(suite.get("tests") or 0)
            res["skipped"] += int(suite.get("skipped") or 0)
            # The artifact's stack trace lands in the suite's console output, not in the <error>: judge per suite.
            console = "".join((suite.findtext(t) or "") for t in ("system-out", "system-err"))
            suite_artifact = bool(artifact.search(console))
            for tc in suite.iter("testcase"):
                for kind in ("failure", "error"):
                    for el in tc.findall(kind):
                        body = (el.get("message") or "") + "\n" + (el.text or "")
                        item = {"class": tc.get("classname") or suite.get("name"), "test": tc.get("name"), "kind": kind,
                                "message": next((ln.strip() for ln in body.splitlines() if ln.strip()), "")[:300]}
                        if suite_artifact or artifact.search(body):
                            res["sandbox"].append(item)
                        elif "Timeout occurred" in body:
                            res["timeouts"].append(item)
                        else:
                            res["failures"].append(item)
                            res["failed" if kind == "failure" else "errors"] += 1
    return res


def map_status(build, tests, ran_tests, cov_ok, wall_timeout, test_rc):
    """(status, reason). `build` is None or {rc, errors, text}; tests is parse_junit's dict."""
    if build and build["rc"] != 0:
        if build["errors"]:
            e = build["errors"][0]
            return "build-failed", f"compile error: {e['file']}:{e['line']}: {e['message']}"
        if ACCORD_MISSING.search(build["text"]):
            return "unknown", "the accord artifact was not found in the run's Maven repo after the accord pre-step; see build.log"
        if HARNESS.search(build["text"]):
            return "unknown", "harness: the build refused this JDK or flag; see build.log"
        if NETWORK.search(build["text"]):
            return "unknown", "network or sandbox: a build step could not reach a resource; see build.log"
        return "unknown", "the build failed without a compile error; see build.log"
    if tests["failures"]:
        f = tests["failures"][0]
        return "tests-failed", f"{len(tests['failures'])} failing test(s), first {f['class']}.{f['test']}"
    if wall_timeout or tests["timeouts"]:
        return "timeout", ("the run hit the wall-clock cap" if wall_timeout
                           else f"{len(tests['timeouts'])} test class(es) timed out")
    if tests["sandbox"]:
        return "unknown", f"{len(tests['sandbox'])} failure(s) look like sandbox artifacts, not PR defects"
    if tests.get("flaky"):
        f = tests["flaky"][0]
        return "unknown", (f"{len(tests['flaky'])} test(s) failed once and passed on retry (flaky), "
                           f"first {f['class']}.{f['test']}")
    if ran_tests and test_rc not in (0, None) and not tests["run"]:
        return "unknown", "ant failed before any test result was written; see jacoco-run.log"
    if ran_tests and test_rc not in (0, None):
        return "unknown", "ant exited non-zero but no failing test was found; see jacoco-run.log"
    if ran_tests and not cov_ok:
        return "unknown", "tests ran but no JaCoCo report was produced; coverage unknown"
    return "pass", f"build ok, {tests['run']} tests passed" if ran_tests else "build ok; no unit tests were selected"


# ---- status files -------------------------------------------------------------------------------------

def base_status(bundle, decision, jdk=None):
    pr = bundle["pr"]
    return {"status": "unknown", "reason": None, "pr": pr["number"], "head": pr["head_sha"], "base_branch": pr["base"],
            "merge_base": bundle["git"]["merge_base"], "jdk": jdk, "approved": decision["approved"],
            "author_is_committer": decision["author_is_committer"], "gate": decision["reason"],
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "timings_s": {}, "tests": None, "selected": [], "not_run": [], "changed_lines": {},
            "changed_total": None, "coverage": "none", "compile_errors": [], "sandbox_unknowns": [], "notes": []}


def write_status(rd, status):
    os.makedirs(rd, exist_ok=True)
    with open(os.path.join(rd, "status.json"), "w") as f:
        json.dump(status, f, indent=1)
    return os.path.join(rd, "status.json")


def not_built(bundle, work_dir, decision):
    st = base_status(bundle, decision)
    st["status"], st["reason"] = "not-built", decision["reason"]
    return write_status(run_dir(work_dir, bundle["pr"]["number"], bundle["pr"]["head_sha"]), st), st


def load_status(work_dir, number, head):
    try:
        with open(os.path.join(run_dir(work_dir, number, head), "status.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ---- the run ------------------------------------------------------------------------------------------

class Build:
    def __init__(self, bundle, work_dir, cfg, shell, decision, root, offline, log, select_fn, cov_fn, home, clock):
        self.bundle, self.work_dir, self.cfg, self.shell, self.log = bundle, work_dir, cfg, shell, log
        self.pr, self.decision, self.root, self.offline = bundle["pr"], decision, root, offline
        self.select_fn, self.cov_fn, self.home, self.clock = select_fn, cov_fn, home, clock
        self.head, self.mb = self.pr["head_sha"], bundle["git"]["merge_base"]
        self.fetch_clone = bundle["git"]["clone"]
        self.rd = run_dir(work_dir, self.pr["number"], self.head)
        self.wt, self.m2 = os.path.join(self.rd, "buildclone"), os.path.join(self.rd, "m2")
        self.start = clock()
        self.deadline = self.start + cfg["caps"]["wall_seconds"]
        self.gradle, self.accord_dir = os.path.join(self.rd, "gradle"), os.path.join(self.rd, "accord")
        self.accord_ready = False
        self.timings, self.jdk, self.env, self.ant = {}, None, None, None
        self.status = base_status(bundle, decision)

    # plumbing
    def left(self):
        left = self.deadline - self.clock()
        if left < 1:
            raise Stop("timeout", "the run hit the wall-clock cap")
        return left

    def sh(self, name, cmd, env=None, cwd=None, timeout=None, check=True):
        """Run, append output to <run>/<name>.log, and time it. Stop(unknown) when check and the command fails."""
        p = self.shell.run(cmd, env=env, cwd=cwd, timeout=timeout or self.left())
        with open(os.path.join(self.rd, name + ".log"), "a") as f:
            f.write(f"$ {' '.join(cmd)}\n{p.out}{p.err}\n")
        self.timings[name] = round(self.timings.get(name, 0) + p.seconds)
        if check and p.rc != 0:
            raise Stop("timeout" if p.timed_out else "unknown",
                       f"{name} failed: " + next((ln.strip() for ln in (p.err or p.out).splitlines() if ln.strip()), "no output")[:200])
        return p

    def sandboxed(self, name, argv, check=True):
        prm = sandbox.params(self.root, self.work_dir, self.rd, self.wt, self.m2,
                             os.path.join(self.fetch_clone, ".git", "objects"), self.home)
        return self.sh(name, sandbox.wrap(argv, prm), env=self.env, cwd=self.wt, check=check)

    def ant_argv(self, *targets, extra=()):
        accord = ["-Dno-build-accord=true"] if self.accord_ready else []
        return ["nice", "-n", str(self.cfg["caps"]["nice"]), self.ant, f"-Dlocal.repository={self.m2}",
                f"-Dmaven.repo.local={self.m2}", *accord, *extra, *targets]

    def git(self, name, *args, **kw):
        return self.sh(name, ["git", *args], env=self.git_env(), **kw)

    def git_env(self):
        return {"PATH": os.pathsep.join(sandbox.BASE_PATH), "HOME": self.home, "GIT_TERMINAL_PROMPT": "0"}

    # steps
    def prepare(self):
        os.makedirs(self.rd, exist_ok=True)
        for name in os.listdir(self.rd):
            if name.endswith(".log"):
                os.remove(os.path.join(self.rd, name))
        self.jdk = jdk_for(self.cfg, self.pr["base"])
        self.status["jdk"] = self.jdk["label"]
        self.env = sandbox.scrubbed_env(self.jdk["home"], None, self.home, self.jdk["env"], self.cfg["caps"]["ant_heap"])
        ant = self.shell.which("ant", self.cfg["ant_dirs"])
        if not ant or not self.shell.which("sandbox-exec", ["/usr/bin"]):
            raise Stop("unknown", "ant or sandbox-exec not found; the build needs both")
        self.ant = ant
        self.env["PATH"] += os.pathsep + os.path.dirname(ant)
        for d in (self.wt, self.m2, self.accord_dir, self.gradle):
            shutil.rmtree(d, ignore_errors=True)
        have = self.git("clone", "-C", self.fetch_clone, "cat-file", "-e", f"{self.head}^{{commit}}", check=False)
        if have.rc != 0:
            raise Stop("unknown", f"head {self.head[:8]} is not in the fetch clone; run cpr review {self.pr['number']} first")

    def make_clone(self):
        self.git("clone", "clone", "--shared", "--no-checkout", self.fetch_clone, self.wt)
        self.git("clone", "-C", self.wt, "remote", "remove", "origin")
        repo = expand(self.cfg["maven_repository"])
        if os.path.isdir(repo):
            p = self.sh("m2", ["cp", "-cR", repo, self.m2], check=False)
            if p.rc != 0:
                self.sh("m2", ["cp", "-R", repo, self.m2])
        else:
            os.makedirs(self.m2)

    def resolve_at_base(self):
        """Trusted, networked: the base commit's own build file downloads dependencies into the m2 copy."""
        self.git("clone", "-C", self.wt, "checkout", "--quiet", "--detach", self.mb)
        if self.offline:
            return
        # On trunk this ant run builds the base's accord with gradle, which would publish to ~/.m2 and write ~/.gradle:
        # point both at the run directory instead.
        self.seed_gradle()
        env = dict(self.env, GRADLE_USER_HOME=self.gradle,
                   JAVA_TOOL_OPTIONS=f"{self.env['JAVA_TOOL_OPTIONS']} -Dmaven.repo.local={self.m2}")
        self.sh("resolve", ["nice", "-n", str(self.cfg["caps"]["nice"]), self.ant, f"-Dlocal.repository={self.m2}",
                            f"-Dmaven.repo.local={self.m2}", "resolver-dist-lib"], env=env, cwd=self.wt, timeout=min(self.left(), self.cfg["caps"]["resolve_seconds"]))
        self.timings["resolve_trusted"] = self.timings.pop("resolve")

    def seed_gradle(self):
        """<run>/gradle as GRADLE_USER_HOME, seeded with an APFS clone of the wrapper distributions (once)."""
        if os.path.isdir(self.gradle):
            return
        os.makedirs(self.gradle)
        seed = os.path.join(self.home, ".gradle", "wrapper")
        if os.path.isdir(seed):  # ~/.gradle itself is never written
            p = self.sh("accord_fetch", ["cp", "-cR", seed, os.path.join(self.gradle, "wrapper")], check=False)
            if p.rc != 0:
                self.status["notes"].append("accord: the Gradle wrapper seed could not be copied; the run downloads it")

    def accord_pin(self):
        """The sha the head tree pins for the accord submodule, or None when there is no gitlink there."""
        out = self.git("accord_ls", "-C", self.wt, "ls-tree", self.head, self.cfg["accord"]["path"]).out
        m = re.match(r"160000 commit ([0-9a-f]{40})\t", out or "")
        return m.group(1) if m else None

    def accord_version(self):
        """`${version}` the way build.xml computes it for a non-release build: base.version + -SNAPSHOT."""
        out = self.git("accord_ls", "-C", self.wt, "show", f"{self.head}:build.xml").out
        m = re.search(r'<property\s+name="base\.version"\s+value="([0-9A-Za-z.+_-]+)"', out or "")
        if not m:
            raise Stop("unknown", "accord build failed: could not read base.version from build.xml")
        return m.group(1) + "-SNAPSHOT"

    def accord_fetch(self, sha):
        """Trusted, networked, source only: clone the base's accord URL and check out the pinned sha."""
        acfg = self.cfg["accord"]
        url = self.git("accord_ls", "-C", self.wt, "config", "--blob", f"{self.mb}:.gitmodules", "--get",
                       f"submodule.{acfg['path']}.url", check=False).out.strip()
        if url != acfg["url"]:
            raise Stop("unknown", f"{ACCORD_URL_NOTE}: {url or 'none'} (the base commit's .gitmodules must name {acfg['url']})")
        cap = min(self.left(), acfg["fetch_seconds"])
        self.git("accord_fetch", "clone", "--no-checkout", url, self.accord_dir, timeout=cap)
        self.git("accord_fetch", "-C", self.accord_dir, "fetch", "--quiet", "origin", sha, timeout=cap)
        self.git("accord_fetch", "-C", self.accord_dir, "checkout", "--quiet", "--detach", sha, timeout=cap)
        dest = os.path.join(self.wt, acfg["path"])
        shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        p = self.sh("accord_fetch", ["cp", "-cR", self.accord_dir, dest], check=False)
        if p.rc != 0:
            self.sh("accord_fetch", ["cp", "-R", self.accord_dir, dest])

    @staticmethod
    def first_error(text):
        lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        return next((ln for ln in lines if re.search(r"error|exception|FAILED|went wrong|not permitted", ln, re.I)),
                    lines[-1] if lines else "no output")[:200]

    def build_accord(self):
        """Gradle build of the accord submodule in the net profile (network, same write limits and read denies)."""
        acfg = self.cfg["accord"]
        sha = self.accord_pin()
        if sha is None:
            return
        version = self.accord_version()
        self.accord_fetch(sha)
        self.seed_gradle()
        args = [a.replace("{version}", version).replace("{m2}", self.m2) for a in acfg["gradle_args"]]
        wt_accord = os.path.join(self.wt, acfg["path"])
        prm = sandbox.params(self.root, self.work_dir, self.rd, self.wt, self.m2,
                             os.path.join(self.fetch_clone, ".git", "objects"), self.home, gradle=self.gradle)
        cap = min(self.left(), acfg["build_seconds"])
        env = dict(self.env, GRADLE_USER_HOME=self.gradle)
        cmd = sandbox.wrap(["nice", "-n", str(self.cfg["caps"]["nice"]), os.path.join(wt_accord, "gradlew"), *args],
                           prm, profile=sandbox.PROFILE_NET)
        p = self.sh("accord_build", cmd, env=env, cwd=wt_accord, timeout=cap, check=False)
        note = ("Accord is built from the sha the PR head pins (base pin may differ): a compile error there can be the "
                "PR's own accord change, otherwise it is not a PR defect.")
        if p.timed_out:
            self.status["notes"].append(note)
            raise Stop("timeout" if cap >= self.left() else "unknown", "accord build failed: timed out")
        if p.rc != 0:
            self.status["notes"].append(note)
            raise Stop("unknown", "accord build failed: " + self.first_error(p.err + "\n" + p.out))
        # What build-accord.xml does after gradle: drop accord jars the base-commit resolve left in the build tree, so
        # the head build copies the freshly published one from the run's Maven repo.
        for pattern in ("build/lib/jars/cassandra-accord-*.jar", "build/test/lib/jars/cassandra-accord-*.jar"):
            for stale in glob.glob(os.path.join(self.wt, pattern)):
                os.remove(stale)
        self.accord_ready = True

    def build_head(self):
        self.git("clone", "-C", self.wt, "checkout", "--quiet", "--detach", self.head)
        self.build_accord()
        text, rc = "", 0
        for target in ("jar", "build-test"):
            p = self.sandboxed("build", self.ant_argv(target), check=False)
            text += p.out + p.err
            if p.timed_out:
                raise Stop("timeout", "the build hit the wall-clock cap")
            if p.rc != 0:
                rc = p.rc if p.rc is not None else 1
                break
        self.timings["build_jar_and_build_test"] = self.timings.pop("build")
        errors = parse_build_log(text)
        self.status["compile_errors"] = errors
        return {"rc": rc, "errors": errors, "text": text}

    def swap_jna(self):
        swap = self.cfg["jna_swap"]
        src = os.path.join(self.m2, swap["from"])
        if not os.path.exists(src):
            self.status["notes"].append(f"JNA swap skipped: {swap['from']} is not in the Maven cache")
            return
        for dest in (swap["to"], swap["also"]):
            self.sandboxed("jna", ["cp", src, os.path.join(self.wt, dest)])
        self.status["notes"].append("JNA 5.6.0 swapped for 5.13.0 (arm64).")

    def pick_tests(self):
        t = self.clock()
        sel = self.select_fn(self.wt, self.mb, self.head, self.cfg)
        self.timings["select"] = round(self.clock() - t)
        self.status["selected"] = [{"class": select.class_name(c["path"]), "reasons": c["reasons"], "score": c["score"]}
                                   for c in sel["selected"]]
        self.status["not_run"] = [{"path": p, "why": "needs the dtest, long, burn or simulator suites"}
                                  for p in sel["skipped"]["non_unit"]]
        with open(os.path.join(self.rd, "selected.json"), "w") as f:
            json.dump(sel, f, indent=1)
        listing = os.path.join(self.rd, "tests.txt")
        with open(listing, "w") as f:
            f.write("".join(c["path"] + "\n" for c in sel["selected"]))
        return listing

    def run_tests(self, listing):
        """jacoco-run then jacoco-report (the report reads partial results after failures). (test rc, timed out)."""
        extra = ["-Dno-build-test=true"]
        p = self.sandboxed("jacoco-run", self.ant_argv(
            "jacoco-run", extra=extra + ["-Dtaskname=testclasslist", f"-Dtest.classlistfile={listing}",
                                         f"-Dtest.timeout={self.cfg['caps']['test_timeout_ms']}"]), check=False)
        self.timings["jacoco_run"] = self.timings.pop("jacoco-run")
        timed_out = p.timed_out
        if not timed_out:
            r = self.sandboxed("jacoco-report", self.ant_argv("jacoco-report", extra=extra), check=False)
            self.timings["jacoco_report"] = self.timings.pop("jacoco-report")
            timed_out = r.timed_out
        return p.rc, timed_out

    def retry_failures(self, tests):
        """Re-run the classes with failures once, without coverage, in the sandbox."""
        classes = sorted({f["class"] for f in tests["failures"]})
        with open(os.path.join(self.rd, "selected.json")) as f:
            by_name = {select.class_name(c["path"]): c["path"] for c in json.load(f)["selected"]}
        paths = [by_name[c] for c in classes if c in by_name]
        if not paths:
            return tests
        listing = os.path.join(self.rd, "retry.txt")
        with open(listing, "w") as f:
            f.write("".join(p + "\n" for p in paths))
        out = os.path.join(self.wt, "build", "test", "output")
        for c in classes:
            stale = os.path.join(out, f"TEST-{c}.xml")
            if os.path.isfile(stale):
                os.remove(stale)
        self.sandboxed("retry", self.ant_argv("testclasslist", extra=[
            "-Dno-build-test=true", f"-Dtest.classlistfile={listing}",
            f"-Dtest.timeout={self.cfg['caps']['test_timeout_ms']}"]), check=False)
        retry_dir = os.path.join(self.rd, "test-output-retry")
        shutil.rmtree(retry_dir, ignore_errors=True)
        os.makedirs(retry_dir)
        for c in classes:
            p = os.path.join(out, f"TEST-{c}.xml")
            if os.path.isfile(p) and not os.path.islink(p):
                shutil.copyfile(p, os.path.join(retry_dir, f"TEST-{c}.xml"))
        retry = parse_junit(retry_dir, sandbox.artifact_pattern(self.cfg))
        missing = [c for c in classes if not os.path.exists(os.path.join(retry_dir, f"TEST-{c}.xml"))]
        if missing:  # no retry result: keep those failures as they were
            retry["failures"] += [f for f in tests["failures"] if f["class"] in missing]
        return apply_retry(tests, retry)

    def collect(self):
        """Copy results out of the build clone (regular files only: the PR controls that tree)."""
        out = os.path.join(self.rd, "test-output")
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(out)
        src = os.path.join(self.wt, "build", "test", "output")
        if os.path.isdir(src):
            for name in os.listdir(src):
                p = os.path.join(src, name)
                if name.startswith("TEST-") and name.endswith(".xml") and os.path.isfile(p) and not os.path.islink(p):
                    shutil.copyfile(p, os.path.join(out, name))
        report, dest = os.path.join(self.wt, "build", "jacoco", "report.xml"), os.path.join(self.rd, "report.xml")
        if os.path.exists(dest):
            os.remove(dest)
        if os.path.isfile(report) and not os.path.islink(report):
            shutil.copyfile(report, dest)
            return dest
        return None

    def changed_coverage(self, report):
        cov = self.cov_fn(self.wt, self.mb, self.head, report)
        self.status["changed_lines"] = {p: {"covered": r["covered"], "partial": r["partial"], "missed": r["missed"],
                                            "nonexec_count": len(r["nonexec"]), "in_report": r["in_report"]}
                                        for p, r in cov["files"].items()}
        self.status["changed_total"] = cov["total"]
        self.status["coverage"] = "ok"

    # the whole run
    def execute(self):
        st, build, ran, rc, wall_timeout, report = self.status, None, False, None, False, None
        before = sandbox.clone_state(self.fetch_clone)
        tests = empty_junit()
        try:
            self.prepare()
            self.make_clone()
            self.resolve_at_base()
            build = self.build_head()
            if build["rc"] == 0:
                if self.jdk["jna_swap"]:
                    self.swap_jna()
                listing = self.pick_tests()
                if self.status["selected"]:
                    ran = True
                    rc, wall_timeout = self.run_tests(listing)
                    report = self.collect()
                    tests = parse_junit(os.path.join(self.rd, "test-output"), sandbox.artifact_pattern(self.cfg))
                    if tests["failures"] and not wall_timeout:
                        tests = self.retry_failures(tests)
                    if report:
                        self.changed_coverage(report)
                    else:
                        st["coverage"] = "missing"
                else:
                    st["coverage"] = "no-tests"
                    st["notes"].append("No unit test class matched the changed code, so coverage was not measured.")
            st["status"], st["reason"] = map_status(build, tests, ran, report is not None, wall_timeout, rc)
        except Stop as e:
            st["status"], st["reason"] = e.status, e.reason
        finally:
            self.finish(before, tests, ran)
        return st

    def finish(self, before, tests, ran):
        st = self.status
        changes = sandbox.clone_changes(before, sandbox.clone_state(self.fetch_clone))
        if changes:
            st["status"] = "unknown"
            st["reason"] = "WARNING: the build changed the shared fetch clone: " + "; ".join(changes)
            st["notes"].append(st["reason"])
        for d in (self.wt, self.m2, self.accord_dir, self.gradle):
            shutil.rmtree(d, ignore_errors=True)
        st["tests"] = {"classes": len(st["selected"]), "run": tests["run"], "failed": tests["failed"],
                       "errors": tests["errors"], "skipped": tests["skipped"],
                       "failures": [{k: f[k] for k in ("class", "test", "message")}
                                    for f in tests["failures"] + tests["timeouts"]]} if ran or tests["run"] else None
        st["flaky"] = [{"class": t["class"], "test": t["test"], "message": t["message"]} for t in tests.get("flaky", [])]
        st["sandbox_unknowns"] = [{"class": t["class"], "test": t["test"], "message": t["message"]} for t in tests["sandbox"]]
        if tests["sandbox"]:
            st["notes"].append(SANDBOX_NOTE)
        if ran and tests["classes_reported"] < len(st["selected"]):
            st["notes"].append(f"{len(st['selected']) - tests['classes_reported']} selected class(es) wrote no result.")
        if st["selected"]:
            st["notes"].append(f"Coverage is from the {len(st['selected'])} auto-selected classes only.")
        st["timings_s"] = dict(self.timings, total_wall=round(self.clock() - self.start))
        st["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        write_status(self.rd, st)


def build(bundle, work_dir, cfg, decision, shell=None, root=None, offline=False, log=print,
          select_fn=select.select, cov_fn=coverage.changed_coverage, home=None, clock=time.monotonic):
    """Run the build for an allowed PR. Returns (status.json path, status dict)."""
    root = root or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    b = Build(bundle, work_dir, cfg, shell or Shell(), decision, root, offline, log, select_fn, cov_fn,
              home or os.path.expanduser("~"), clock)
    st = b.execute()
    return os.path.join(b.rd, "status.json"), st
