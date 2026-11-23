"""The Gradle build of a subproject PR (apache/cassandra-sidecar, apache/cassandra-analytics).

The steps follow the Ant build in `runner.Build`, which this subclasses:

1. The PR may not change the Gradle wrapper (`gradlew`, `gradle/wrapper/*`): the wrapper picks and runs the Gradle
   distribution, so a PR that changes it would choose what runs. Such a PR is not built.
2. At the merge-base (trusted), in the networked profile, cpr's own init script resolves every configuration into
   the run's GRADLE_USER_HOME and an empty run-local Maven repository (never ~/.m2: a stale local SNAPSHOT there
   would decide what the build compiles against).
3. A project whose tests compile against an in-JVM dtest jar (sidecar) gets it built from the Cassandra sha the
   merge-base's own script pins, shaded by that script, in the networked profile; the jar is cached per pin.
4. At the head, offline and in the no-network profile: list the projects, compile, then run the selected unit
   test classes with JaCoCo. A dependency the merge-base did not resolve fails offline and reads unknown.
5. JUnit and JaCoCo XML are found by searching the build trees (projects move them), regular files only.
"""

import glob
import hashlib
import json
import os
import re
import shutil
import time

from cpr.build import coverage, runner, sandbox, select
from cpr.build.runner import Stop

INIT = os.path.join(sandbox.ASSETS, "cpr-init.gradle")
WRAPPER = ("gradlew", "gradlew.bat", "gradle/wrapper/")
DTEST_NAME = re.compile(r'"(dtest-(\d+\.\d+(?:\.\d+)?)\.jar)"')
PIN = re.compile(r'"([\w.-]+):([0-9a-f]{40})"')
BASE_VERSION = re.compile(r'<property\s+name="base\.version"\s+value="([0-9A-Za-z.+_-]+)"')
JACOCO_DOCTYPE = b"-//JACOCO//DTD Report"
NOT_UNIT = "integration, container or example module: needs Docker, dtest jars or a cluster"


def wrapper_changes(names):
    """The changed paths that belong to the Gradle wrapper."""
    return sorted(p for p in names if p in WRAPPER[:2] or p.startswith(WRAPPER[2]))


def dtest_jar_name(text):
    """('dtest-4.1.11.jar', '4.1.11') from the build file that declares the jar, or None."""
    m = DTEST_NAME.search(text or "")
    return (m[1], m[2]) if m else None


def pins(text):
    """[(branch, sha)] from the CANDIDATE_BRANCHES of a build-dtest-jars.sh."""
    return PIN.findall(text or "")


def parse_projects(text):
    """({Gradle path: project dir}, {Gradle paths of Java projects}) from cprProjects' projects.tsv."""
    dirs, java = {}, set()
    for line in (text or "").splitlines():
        parts = line.split("\t")
        if parts[0].startswith(":") and len(parts) >= 2:
            dirs[parts[0]] = parts[1].strip()
            if len(parts) > 2 and parts[2].strip() == "java":
                java.add(parts[0])
    return dirs, java


def _regular(path):
    return os.path.isfile(path) and not os.path.islink(path)


def find_results(wt, since):
    """(TEST-*.xml paths, JaCoCo XML paths) under any build/ directory of `wt`, written at or after `since`.

    A JaCoCo report is recognized by its DOCTYPE under a reports/ directory, whatever its name: a project may name
    the file without an extension (analytics writes build/reports/jacocoXml).
    """
    junit, jacoco = [], []
    for dp, dns, fns in os.walk(wt):
        dns[:] = [d for d in dns if d not in (".git", ".gradle", "src") and not os.path.islink(os.path.join(dp, d))]
        where = dp.replace(os.sep, "/") + "/"
        if "/build/" not in where:
            continue
        for fn in fns:
            p = os.path.join(dp, fn)
            if not _regular(p) or os.path.getmtime(p) < since:
                continue
            if fn.startswith("TEST-") and fn.endswith(".xml"):
                junit.append(p)
            elif "/reports/" in where and (fn.endswith(".xml") or "." not in fn):
                with open(p, "rb") as f:
                    if JACOCO_DOCTYPE in f.read(400):
                        jacoco.append(p)
    return sorted(junit), sorted(jacoco)


def wall_clock():
    """Now, as file mtimes count it, less a second of slack for coarse filesystems."""
    return time.time() - 1


class GradleBuild(runner.Build):
    def __init__(self, bundle, work_dir, cfg, shell, decision, root, offline, log, select_fn, cov_fn, home, clock, proj):
        super().__init__(bundle, work_dir, cfg, shell, decision, root, offline, log, select_fn, cov_fn, home, clock)
        self.proj, self.bcfg = proj, proj.build
        self.projects, self.java, self.modules, self.selected = {}, set(), [], []
        self.dtest, self.tests_started, self.init = None, 0, INIT
        self.dtest_cache = os.path.join(work_dir, "build-cache", proj.slug, "dtest-jars")

    # plumbing
    def gradlew(self, *args, offline=True):
        return ["nice", "-n", str(self.cfg["caps"]["nice"]), "./gradlew", "--no-daemon", "--console=plain",
                *(["--offline"] if offline else []), f"-Dmaven.repo.local={self.m2}", "-I", self.init, *args]

    @staticmethod
    def first_error(text):
        """Gradle's "What went wrong" line when there is one, else the first error-looking line."""
        lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        for i, ln in enumerate(lines):
            if ln.startswith("* What went wrong") and i + 1 < len(lines):
                return " ".join(lines[i + 1:i + 3])[:200]
        return runner.Build.first_error(text)

    def gradle_env(self):
        return dict(self.env, GRADLE_USER_HOME=self.gradle)

    def sandboxed(self, name, argv, check=True, net=False, wt=None, m2=None, gradle=None, env=None, timeout=None,
                  objects=None):
        wt = wt or self.wt
        prm = sandbox.params(self.root, self.work_dir, self.rd, wt, m2 or self.m2,
                             objects or os.path.join(self.fetch_clone, ".git", "objects"), self.home,
                             gradle=gradle or self.gradle)
        return self.sh(name, sandbox.wrap(argv, prm, profile=sandbox.PROFILE_NET if net else sandbox.PROFILE),
                       env=env or self.gradle_env(), cwd=wt, check=check, timeout=timeout)

    def show(self, rev, path):
        p = self.git("inspect", "-C", self.wt, "show", f"{rev}:{path}", check=False)
        return p.out if p.rc == 0 else None

    # steps
    def prepare(self):
        os.makedirs(self.rd, exist_ok=True)
        for name in os.listdir(self.rd):
            if name.endswith(".log"):
                os.remove(os.path.join(self.rd, name))
        home, label = runner.jdk_home(self.cfg, self.bcfg["jdk"], self.proj.name)
        self.jdk = {"home": home, "major": int(self.bcfg["jdk"]), "label": label, "env": {}, "jna_swap": False}
        self.status["jdk"] = label
        self.env = sandbox.scrubbed_env(home, None, self.home, None, self.cfg["caps"]["ant_heap"])
        self.env.pop("ANT_OPTS", None)
        if not self.shell.which("sandbox-exec", ["/usr/bin"]):
            raise Stop("unknown", "sandbox-exec not found; the build needs it")
        for d in (self.wt, self.m2, self.gradle, os.path.join(self.rd, "dtest")):
            shutil.rmtree(d, ignore_errors=True)
        # The sandbox cannot read this tool's checkout, so the init script runs from the run directory.
        self.init = os.path.join(self.rd, "cpr-init.gradle")
        shutil.copyfile(INIT, self.init)
        have = self.git("clone", "-C", self.fetch_clone, "cat-file", "-e", f"{self.head}^{{commit}}", check=False)
        if have.rc != 0:
            raise Stop("unknown", f"head {self.head[:8]} is not in the fetch clone; run cpr review first")

    def make_clone(self):
        self.git("clone", "clone", "--shared", "--no-checkout", self.fetch_clone, self.wt)
        self.git("clone", "-C", self.wt, "remote", "remove", "origin")
        os.makedirs(self.m2)  # empty on purpose: see the module docstring
        names = self.git("clone", "-C", self.wt, "diff", "--name-only", "--no-renames", self.mb, self.head).out.split()
        changed = wrapper_changes(names)
        if changed:
            raise Stop("unknown", "the PR changes the Gradle wrapper (" + ", ".join(changed) + "); cpr does not run a "
                       "Gradle distribution the PR chose, so it was not built")

    def resolve_at_base(self):
        """Trusted, networked: the merge-base's own build resolves every configuration."""
        self.git("clone", "-C", self.wt, "checkout", "--quiet", "--detach", self.mb)
        self.seed_gradle("gradle_seed", "gradle")
        if self.offline:
            self.dtest_jar(build=False)
            return
        cap = min(self.left(), self.cfg["gradle"]["resolve_seconds"])
        p = self.sandboxed("resolve", self.gradlew("cprResolve", offline=False), net=True, check=False, timeout=cap)
        self.timings["resolve_trusted"] = self.timings.pop("resolve")
        if p.rc != 0:
            raise Stop("timeout" if p.timed_out and cap >= self.left() else "unknown",
                       "resolving dependencies at the merge-base failed: " + self.first_error(p.err + "\n" + p.out))
        self.dtest_jar()

    def dtest_jar(self, build=True):
        """Build (or reuse) the in-JVM dtest jar the merge-base's test fixtures compile against."""
        dcfg = self.bcfg.get("dtest_jar")
        if not dcfg:
            return
        want = dtest_jar_name(self.show(self.mb, dcfg["declared_in"]))
        script = self.show(self.mb, dcfg["pins"])
        if not want or script is None:
            raise Stop("unknown", f"could not read the dtest jar the merge-base wants from {dcfg['declared_in']}")
        name, version = want
        shade = self.show(self.mb, dcfg["shade"]) or ""
        key = hashlib.sha256((script + shade).encode()).hexdigest()[:12]
        cached = os.path.join(self.dtest_cache, key, name)
        if not os.path.isfile(cached):
            if not build:
                raise Stop("unknown", f"{name} is not cached and --offline cannot build it; run once without --offline")
            self.build_dtest_jar(dcfg, name, version, script, cached)
        self.dtest = cached
        self.status["notes"].append(f"Compiled against {name}, built from the Cassandra sha the merge-base's "
                                    f"{dcfg['pins']} pins and shaded by its {dcfg['shade']}.")

    def build_dtest_jar(self, dcfg, name, version, script, dest):
        from cpr import layout, project as project_mod
        from cpr.ingest import clone
        cass = layout.clone_dir(self.work_dir, project_mod.load(project_mod.DEFAULT))
        clone.ensure(cass)
        found = None
        for branch, sha in pins(script):
            try:
                clone.ensure_commit(cass, sha)
            except clone.CloneError:
                continue
            m = BASE_VERSION.search(self.git("dtest", "-C", cass, "show", f"{sha}:build.xml", check=False).out or "")
            if m and m[1] == version:
                found = (branch, sha)
                break
        if not found:
            raise Stop("unknown", f"none of the Cassandra shas pinned in {dcfg['pins']} builds version {version} for {name}")
        branch, sha = found
        d = os.path.join(self.rd, "dtest")
        # Everything the step writes sits in the sandbox's writable dirs: the Cassandra checkout (WT, which also gets a
        # copy of the merge-base's scripts, since Maven writes target/ beside its pom), the Maven repo and Maven home.
        src, m2, mvn = (os.path.join(d, x) for x in ("cassandra", "m2", "maven"))
        out, scripts = os.path.join(src, ".cpr-dtest-out"), os.path.join(src, ".cpr-scripts")
        self.git("dtest", "clone", "--shared", "--no-checkout", cass, src)
        self.git("dtest", "-C", src, "checkout", "--quiet", "--detach", sha)
        shutil.copytree(os.path.join(self.wt, os.path.dirname(dcfg["shade"])), scripts, symlinks=True)
        for x in (m2, mvn, out):
            os.makedirs(x, exist_ok=True)
        home, _ = runner.jdk_home(self.cfg, dcfg["jdk"], f"the dtest jar ({branch})")
        ant = self.shell.which("ant", self.cfg["ant_dirs"])
        if not ant:
            raise Stop("unknown", "ant not found; the dtest jar is built with it")
        env = sandbox.scrubbed_env(home, os.path.dirname(ant), self.home, {
            "CASSANDRA_USE_JDK11": "true", "ANT_ARGS": f"-Dlocal.repository={m2} -Dmaven.repo.local={m2}",
            "M2_HOME": m2, "MAVEN_USER_HOME": mvn, "MAVEN_OPTS": f"-Dmaven.repo.local={m2}", "CASSANDRA_DEP_DIR": out}, "2g")
        cap = min(self.left(), self.cfg["gradle"]["dtest_seconds"])
        p = self.sandboxed("dtest", ["sh", os.path.join(scripts, os.path.basename(dcfg["shade"]))], net=True, check=False,
                           wt=src, m2=m2,
                           gradle=mvn, env=env, timeout=cap, objects=os.path.join(cass, ".git", "objects"))
        built = os.path.join(out, name)
        if p.rc != 0 or not _regular(built):
            raise Stop("timeout" if p.timed_out and cap >= self.left() else "unknown",
                       f"building {name} failed: " + self.first_error(p.err + "\n" + p.out))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(built, dest + ".part")
        os.replace(dest + ".part", dest)
        shutil.rmtree(d, ignore_errors=True)

    def build_head(self):
        self.git("clone", "-C", self.wt, "checkout", "--quiet", "--detach", self.head)
        dcfg = self.bcfg.get("dtest_jar")
        if dcfg and self.dtest:
            into = os.path.join(self.wt, dcfg["into"])
            os.makedirs(into, exist_ok=True)
            shutil.copyfile(self.dtest, os.path.join(into, os.path.basename(self.dtest)))
        p = self.sandboxed("build", self.gradlew("cprProjects"), check=False)
        text = p.out + p.err
        if p.timed_out:
            raise Stop("timeout", "the build hit the wall-clock cap")
        if p.rc == 0:
            tsv = os.path.join(self.wt, "build", "cpr", "projects.tsv")
            with open(tsv) if _regular(tsv) else open(os.devnull) as f:
                self.projects, self.java = parse_projects(f.read())
            self.modules = select.gradle_modules(self.wt, self.projects)
            skip = set(self.bcfg.get("skip_modules", ()))
            tasks = [f"{path}:testClasses" for path, d in sorted(self.projects.items())
                     if path in self.java and path != ":" and d not in skip]
            if ":" in self.java:
                tasks.append(":testClasses")
            p = self.sandboxed("build", self.gradlew("--continue", *tasks), check=False)
            text += p.out + p.err
            if p.timed_out:
                raise Stop("timeout", "the build hit the wall-clock cap")
        self.timings["build_compile"] = self.timings.pop("build")
        errors = [dict(e, file=os.path.relpath(e["file"], self.wt) if e["file"].startswith(self.wt) else e["file"])
                  for e in runner.parse_build_log(text)]
        self.status["compile_errors"] = errors
        return {"rc": p.rc if p.rc is not None else 1, "errors": errors, "text": text}

    def pick_tests(self):
        t = self.clock()
        sel = (self.select_fn or select.select_gradle)(self.wt, self.mb, self.head, self.cfg, self.projects,
                                                         self.bcfg.get("skip_modules", ()))
        self.timings["select"] = round(self.clock() - t)
        self.selected = sel["selected"]
        self.status["selected"] = [{"class": select.class_name(c["path"]), "module": c["module"], "reasons": c["reasons"],
                                    "score": c["score"]} for c in sel["selected"]]
        self.status["not_run"] = [{"path": p, "why": NOT_UNIT} for p in sel["skipped"]["non_unit"]]
        with open(os.path.join(self.rd, "selected.json"), "w") as f:
            json.dump(sel, f, indent=1)
        return None

    def test_args(self, picks, *extra):
        by = {}
        for c in picks:
            by.setdefault(c["module"], []).append(select.class_name(c["path"]))
        args = []
        for module, classes in sorted(by.items()):
            args.append(f"{module}:{self.bcfg.get('test_task', 'test')}" if module != ":" else self.bcfg.get("test_task", "test"))
            for c in sorted(classes):
                args += ["--tests", c]
            args += extra
        return args

    def run_tests(self, listing):
        """One Gradle run of every selected class, with JaCoCo; `--continue` so one module's failure runs the rest."""
        self.tests_started = wall_clock()
        p = self.sandboxed("tests", self.gradlew("--continue", *self.test_args(self.selected), "cprClasspath"), check=False)
        return p.rc, p.timed_out

    def collect(self):
        junit, jacoco = find_results(self.wt, self.tests_started)
        out = os.path.join(self.rd, "test-output")
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(out)
        for p in junit:
            shutil.copyfile(p, os.path.join(out, os.path.basename(p)))
        dest = os.path.join(self.rd, "jacoco")
        shutil.rmtree(dest, ignore_errors=True)
        kept = []
        for i, p in enumerate(jacoco):
            os.makedirs(dest, exist_ok=True)
            kept.append(os.path.join(dest, f"{i:02d}-{os.path.basename(p)}"))
            shutil.copyfile(p, kept[-1])
        return kept or None

    def retry_failures(self, tests):
        """Re-run the classes with failures once (`--rerun`), in the sandbox."""
        failing = {f["class"] for f in tests["failures"]}
        picks = [c for c in self.selected if select.class_name(c["path"]) in failing]
        if not picks:
            return tests
        since = wall_clock()
        self.sandboxed("retry", self.gradlew("--continue", *self.test_args(picks, "--rerun")), check=False)
        retry_dir = os.path.join(self.rd, "test-output-retry")
        shutil.rmtree(retry_dir, ignore_errors=True)
        os.makedirs(retry_dir)
        for p in find_results(self.wt, since)[0]:
            shutil.copyfile(p, os.path.join(retry_dir, os.path.basename(p)))
        retry = runner.parse_junit(retry_dir, sandbox.artifact_pattern(self.cfg))
        seen = {os.path.basename(p)[5:-4] for p in glob.glob(os.path.join(retry_dir, "TEST-*.xml"))}
        retry["failures"] += [f for f in tests["failures"] if f["class"] not in seen]
        return runner.apply_retry(tests, retry)

    def changed_coverage(self, reports):
        cov = self.cov_fn(self.wt, self.mb, self.head, reports, coverage.GRADLE_PATHSPEC, coverage.GRADLE_SRC)
        self.status["changed_lines"] = {p: {"covered": r["covered"], "partial": r["partial"], "missed": r["missed"],
                                            "nonexec_count": len(r["nonexec"]), "in_report": r["in_report"]}
                                        for p, r in cov["files"].items()}
        self.status["changed_total"] = cov["total"]
        self.status["coverage"] = "ok"

    def keep_classpath(self):
        """Compiled classes of every module and the jars cprClasspath listed from the run's caches, for PMD."""
        root = os.path.join(self.rd, "classpath")
        shutil.rmtree(root, ignore_errors=True)
        classes, jars, size = [], [], 0
        for path, d in sorted(self.projects.items()):
            for kind in ("main", "test"):
                src = os.path.join(self.wt, d, "build", "classes", "java", kind)
                if os.path.isdir(src) and not os.path.islink(src):
                    dest = os.path.join(root, "classes", (path.strip(":").replace(":", ".") or "root") + "-" + kind)
                    n, b = runner._keep_tree(src, dest)
                    if n:
                        classes.append(dest)
                        size += b
        if not classes:
            shutil.rmtree(root, ignore_errors=True)
            return None
        trusted = tuple(sandbox.norm(x) + os.sep for x in (self.gradle, self.m2))
        seen = set()
        for listing in sorted(glob.glob(os.path.join(self.wt, "build", "cpr", "classpath", "*.txt"))):
            if not _regular(listing):
                continue
            with open(listing) as f:
                lines = f.read().splitlines()
            for line in lines:
                p = sandbox.norm(line.strip()) if line.strip() else ""
                if not p.endswith(".jar") or not p.startswith(trusted) or os.path.basename(p) in seen:
                    continue
                seen.add(os.path.basename(p))
                got = runner._link_or_copy(p, os.path.join(root, "jars", os.path.basename(p)))
                if got is not None:
                    jars.append(os.path.join(root, "jars", os.path.basename(p)))
                    size += got
        return {"classes": classes, "jars": jars, "bytes": size}
