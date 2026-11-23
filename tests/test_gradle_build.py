"""gradle-build: the Gradle strategy for subproject PRs (fake shell, no builds), selection and coverage on a real repo."""

import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest import mock

from cpr import build as build_pkg
from cpr.build import coverage, gradle, runner, sandbox, select  # noqa: F401 (runner is the entry point)
from tests.test_build import GITENV, FakeShell, ok

HEAD, MB = "a" * 40, "c" * 40
JUNIT = ('<testsuite name="org.x.FooTest" tests="3" failures="0" errors="0" skipped="0">'
         '<testcase classname="org.x.FooTest" name="a"/></testsuite>')
JUNIT_FAIL = ('<testsuite name="org.x.FooTest" tests="1" failures="1" errors="0" skipped="0"><testcase classname="org.x.FooTest" '
              'name="a"><failure message="boom">x</failure></testcase></testsuite>')
JACOCO = '<?xml version="1.0"?><!DOCTYPE report PUBLIC "-//JACOCO//DTD Report 1.1//EN" "report.dtd"><report name="core"/>'
TSV = ":\t\t-\n:core\tcore\tjava\n:docs\tdocs\t-\n:it\tintegration\tjava\n"
SEL = {"selected": [{"path": "core/src/test/java/org/x/FooTest.java", "module": ":core", "score": 500,
                     "reasons": ["FooTest name: Foo"]}],
       "skipped": {"non_unit": ["integration/src/test/java/org/x/FooIT.java"], "not_a_test": []}}


class Helpers(unittest.TestCase):
    def test_wrapper_changes(self):
        self.assertEqual(gradle.wrapper_changes(["gradlew", "core/src/main/java/A.java", "gradle/wrapper/gradle-wrapper.jar",
                                                 "gradle/libs.versions.toml", "gradle.properties"]),
                         ["gradle/wrapper/gradle-wrapper.jar", "gradlew"])

    def test_dtest_jar_name_and_pins(self):
        self.assertEqual(gradle.dtest_jar_name('ext.dtestJar = System.getenv("DTEST_JAR") ?: "dtest-4.1.11.jar" // x'),
                         ("dtest-4.1.11.jar", "4.1.11"))
        self.assertIsNone(gradle.dtest_jar_name("nothing here"))
        script = 'CANDIDATE_BRANCHES=(\n  "cassandra-4.0:' + "e" * 40 + '"\n  "cassandra-4.1:' + "f" * 40 + '"\n)'
        self.assertEqual(gradle.pins(script), [("cassandra-4.0", "e" * 40), ("cassandra-4.1", "f" * 40)])

    def test_parse_projects(self):
        dirs, java = gradle.parse_projects(TSV)
        self.assertEqual(dirs, {":": "", ":core": "core", ":docs": "docs", ":it": "integration"})
        self.assertEqual(java, {":core", ":it"})

    def test_find_results_by_content_and_time(self):
        with tempfile.TemporaryDirectory() as d:
            def put(rel, text, age=0):
                p = os.path.join(d, rel)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w") as f:
                    f.write(text)
                if age:
                    os.utime(p, (time.time() - age, time.time() - age))
            put("core/build/test-results/test/TEST-org.x.FooTest.xml", JUNIT)
            put("build/test-results/core/test/TEST-org.x.BarTest.xml", JUNIT)  # a project that moves them to the root
            put("core/build/reports/jacocoXml", JACOCO)  # no extension
            put("core/build/reports/jacoco/test/jacocoTestReport.xml", JACOCO)
            put("core/build/reports/other.xml", "<report/>")
            put("core/src/test/resources/TEST-fixture.xml", JUNIT)  # not under build/
            put("core/build/test-results/test/TEST-old.xml", JUNIT, age=3600)
            junit, jacoco = gradle.find_results(d, time.time() - 60)
        self.assertEqual([os.path.basename(p) for p in junit], ["TEST-org.x.BarTest.xml", "TEST-org.x.FooTest.xml"])
        self.assertEqual([os.path.relpath(p, d) for p in jacoco],
                         ["core/build/reports/jacoco/test/jacocoTestReport.xml", "core/build/reports/jacocoXml"])


def git(wt, *args):
    return subprocess.run(["git", "-C", wt, *args], check=True, capture_output=True, text=True, env=GITENV).stdout.strip()


def write(wt, rel, text):
    p = os.path.join(wt, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text)


FOO = "package org.x;\n\npublic class Foo\n{\n    public int size()\n    {\n        return 1;\n    }\n}\n"


class Tree(unittest.TestCase):
    def setUp(self):
        self.wt = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.wt, True)
        git(self.wt, "init", "-q")
        write(self.wt, "core/src/main/java/org/x/Foo.java", FOO)
        write(self.wt, "core/src/test/java/org/x/FooTest.java", "class FooTest { @Test void t() { new Foo().size(); } }")
        write(self.wt, "core/src/test/java/org/x/OtherTest.java", "class OtherTest { @Test void t() {} }")
        write(self.wt, "lib/nested/src/test/java/org/y/FooTest.java", "class FooTest { @Test void t() {} }")
        write(self.wt, "integration/src/test/java/org/x/FooIntegrationTest.java", "class FooIntegrationTest { @Test void t() { Foo f; } }")
        git(self.wt, "add", ".")
        git(self.wt, "commit", "-qm", "base")
        self.base = git(self.wt, "rev-parse", "HEAD")
        write(self.wt, "core/src/main/java/org/x/Foo.java", FOO.replace("return 1;", "int n = 2;\n        return n;"))
        write(self.wt, "integration/src/test/java/org/x/FooIntegrationTest.java", "class FooIntegrationTest { @Test void u() {} }")
        git(self.wt, "commit", "-qam", "head")
        self.head = git(self.wt, "rev-parse", "HEAD")
        self.projects = {":": "", ":core": "core", ":lib": "lib", ":lib:nested": "lib/nested", ":it": "integration"}

    def test_select_gradle(self):
        sel = select.select_gradle(self.wt, self.base, self.head, build_pkg.load_config(), self.projects, ["integration"])
        picked = {c["path"]: c for c in sel["selected"]}
        self.assertEqual(picked["core/src/test/java/org/x/FooTest.java"]["module"], ":core")
        self.assertIn("FooTest name: Foo", picked["core/src/test/java/org/x/FooTest.java"]["reasons"])
        self.assertEqual(picked["lib/nested/src/test/java/org/y/FooTest.java"]["module"], ":lib:nested")  # deepest dir wins
        self.assertNotIn("core/src/test/java/org/x/OtherTest.java", picked)
        self.assertFalse(any(p.startswith("integration/") for p in picked))
        self.assertEqual(sel["skipped"]["non_unit"], ["integration/src/test/java/org/x/FooIntegrationTest.java"])
        self.assertEqual(sel["changed_src_classes"], ["Foo"])
        self.assertEqual(sel["changed_methods"], ["size"])
        self.assertEqual(select.class_name("core/src/test/java/org/x/FooTest.java"), "org.x.FooTest")
        self.assertEqual(select.class_name("org/x/FooTest.java"), "org.x.FooTest")  # Cassandra's test/unit paths

    def test_coverage_merges_module_reports(self):
        rep = os.path.join(self.wt, "r1.xml")
        with open(rep, "w") as f:
            f.write('<report name="x"><package name="org/x"><sourcefile name="Foo.java">'
                    '<line nr="7" mi="0" ci="3" mb="0" cb="0"/><line nr="8" mi="2" ci="0" mb="0" cb="0"/>'
                    '</sourcefile></package></report>')
        empty = os.path.join(self.wt, "r0.xml")
        with open(empty, "w") as f:
            f.write('<report name="y"/>')
        cov = coverage.changed_coverage(self.wt, self.base, self.head, [empty, rep], coverage.GRADLE_PATHSPEC,
                                        coverage.GRADLE_SRC)
        f = cov["files"]["core/src/main/java/org/x/Foo.java"]
        self.assertEqual((f["covered"], f["missed"]), ([7], [8]))
        self.assertEqual(cov["total"]["pct_executed"], 50.0)


class RunnerBase(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.work, True)
        self.jdk = os.path.join(self.work, "jdk17")
        os.makedirs(self.jdk)
        self.fetch = os.path.join(self.work, "cassandra-analytics")
        os.makedirs(os.path.join(self.fetch, ".git", "hooks"))
        with open(os.path.join(self.fetch, ".git", "config"), "w") as f:
            f.write("[core]\n")
        self.cfg = build_pkg.load_config()
        self.cfg["jdk_homes"]["17"] = [self.jdk]
        self.bundle = {"meta": {"project": "analytics"},
                       "pr": {"number": 260, "author": "sarankk", "head_sha": HEAD, "base": "trunk"},
                       "git": {"merge_base": MB, "clone": self.fetch}}
        self.decision = {"allowed": True, "approved": False, "author_is_committer": True, "reason": "committer"}

    def go(self, script, sel=SEL, **kw):
        cov = lambda *a: {"files": {"core/src/main/java/org/x/Foo.java": {"covered": [7], "partial": [], "missed": [8],  # noqa: E731
                                                                         "nonexec": [], "in_report": True}},
                          "total": {"covered": 1, "partial": 0, "missed": 1, "nonexec": 0, "executable": 2, "pct_executed": 50.0}}
        self.seen = []

        def pick(*a):
            self.seen.append(a)
            return sel
        sh = FakeShell(script)
        _, st = runner.build(self.bundle, self.work, self.cfg, self.decision, shell=sh, root=self.work, home=self.work,
                             select_fn=pick, cov_fn=cov, **kw)
        return sh, st

    def happy(self, junit=JUNIT):
        return {"cprProjects": ok({"build/cpr/projects.tsv": TSV}),
                "cprClasspath": ok({"core/build/test-results/test/TEST-org.x.FooTest.xml": junit,
                                    "core/build/reports/jacocoXml": JACOCO})}

    def gradle_calls(self, sh):
        return [c for c in sh.calls if "./gradlew" in c["cmd"]]


class Runner(RunnerBase):
    def test_pass_resolve_networked_then_offline_sandboxed(self):
        sh, st = self.go(self.happy())
        self.assertEqual((st["status"], st["reason"]), ("pass", "build ok, 3 tests passed"))
        self.assertEqual(st["jdk"], "jdk17")
        self.assertEqual(st["selected"][0], {"class": "org.x.FooTest", "module": ":core", "reasons": ["FooTest name: Foo"],
                                             "score": 500})
        self.assertEqual(st["not_run"], [{"path": "integration/src/test/java/org/x/FooIT.java", "why": gradle.NOT_UNIT}])
        self.assertEqual(st["changed_total"]["pct_executed"], 50.0)
        calls = self.gradle_calls(sh)
        rd = os.path.join(self.work, "build-runs", "analytics", "260", HEAD)
        for c in calls:
            self.assertEqual(c["cmd"][0], "sandbox-exec")
            self.assertIn(f"-Dmaven.repo.local={os.path.join(rd, 'm2')}", c["cmd"])
            self.assertEqual(c["cmd"][c["cmd"].index("-I") + 1], os.path.join(rd, "cpr-init.gradle"))
            self.assertEqual(c["env"]["GRADLE_USER_HOME"], os.path.join(rd, "gradle"))
            self.assertIn("GRADLE=" + sandbox.norm(os.path.join(rd, "gradle")), c["cmd"])
        resolve, *head = calls
        self.assertIn("cprResolve", resolve["cmd"])
        self.assertEqual(resolve["cmd"][resolve["cmd"].index("-f") + 1], sandbox.PROFILE_NET)
        self.assertNotIn("--offline", resolve["cmd"])
        for c in head:
            self.assertEqual(c["cmd"][c["cmd"].index("-f") + 1], sandbox.PROFILE)
            self.assertIn("--offline", c["cmd"])
        compile_ = next(c["cmd"] for c in head if ":core:testClasses" in c["cmd"])
        self.assertIn(":it:testClasses", compile_)  # compiled, but its tests are not run
        self.assertNotIn(":docs:testClasses", compile_)  # not a Java project
        tests = next(c["cmd"] for c in head if "cprClasspath" in c["cmd"])
        self.assertEqual(tests[tests.index(":core:test"):tests.index(":core:test") + 3], [":core:test", "--tests", "org.x.FooTest"])
        steps = [" ".join(c["cmd"]) for c in sh.calls]
        order = [next(i for i, s in enumerate(steps) if m in s) for m in
                 (f"checkout --quiet --detach {MB}", "cprResolve", f"checkout --quiet --detach {HEAD}", "cprProjects",
                  ":core:testClasses", "cprClasspath")]
        self.assertEqual(order, sorted(order))
        self.assertTrue(os.path.isfile(os.path.join(rd, "jacoco", "00-jacocoXml")))
        self.assertFalse(os.path.exists(os.path.join(rd, "buildclone")))

    def test_wrapper_change_is_not_built(self):
        sh, st = self.go({"diff --name-only": ok(), **self.happy(),
                          f"diff --name-only --no-renames {MB} {HEAD}": (0, "gradle/wrapper/gradle-wrapper.properties\n", "", {})})
        self.assertEqual(st["status"], "unknown")
        self.assertIn("changes the Gradle wrapper (gradle/wrapper/gradle-wrapper.properties)", st["reason"])
        self.assertEqual(self.gradle_calls(sh), [])

    def test_dependency_not_resolved_offline_is_unknown(self):
        msg = "Could not resolve all files for configuration ':core:compileClasspath'.\n   > No cached version of org.x:new:1.0 available for offline mode.\n"
        sh, st = self.go({**self.happy(), "testClasses": (1, msg, "", {})})
        self.assertEqual(st["status"], "unknown")
        self.assertIn("not among those resolved at the merge-base", st["reason"])

    def test_compile_error_path_is_relative(self):
        rd = os.path.join(self.work, "build-runs", "analytics", "260", HEAD)
        err = f"{rd}/buildclone/core/src/main/java/org/x/Foo.java:9: error: cannot find symbol\n"
        sh, st = self.go({**self.happy(), "testClasses": (1, err, "", {})})
        self.assertEqual(st["status"], "build-failed")
        self.assertEqual(st["compile_errors"][0], {"file": "core/src/main/java/org/x/Foo.java", "line": 9,
                                                   "message": "cannot find symbol"})
        self.assertFalse(any("cprClasspath" in c["cmd"] for c in sh.calls))

    def test_failure_retried_with_rerun(self):
        script = {**self.happy(JUNIT_FAIL), "--rerun": ok({"core/build/test-results/test/TEST-org.x.FooTest.xml": JUNIT})}
        sh, st = self.go(script)
        self.assertEqual(st["status"], "unknown")
        self.assertIn("flaky", st["reason"])
        rerun = next(c["cmd"] for c in sh.calls if "--rerun" in c["cmd"])
        self.assertEqual(rerun[rerun.index(":core:test"):rerun.index(":core:test") + 4],
                         [":core:test", "--tests", "org.x.FooTest", "--rerun"])

    def test_offline_skips_the_networked_resolve(self):
        sh, st = self.go(self.happy(), offline=True)
        self.assertEqual(st["status"], "pass")
        self.assertFalse(any("cprResolve" in c["cmd"] for c in sh.calls))

    def test_no_selected_tests(self):
        _, st = self.go(self.happy(), sel={"selected": [], "skipped": {"non_unit": [], "not_a_test": []}})
        self.assertEqual((st["status"], st["coverage"]), ("pass", "no-tests"))


class Dtest(RunnerBase):
    def setUp(self):
        super().setUp()
        self.fetch = os.path.join(self.work, "cassandra-sidecar")
        os.makedirs(os.path.join(self.fetch, ".git", "hooks"))
        self.cfg["jdk_homes"]["11"] = [self.jdk]
        self.bundle = {**self.bundle, "meta": {"project": "sidecar"}, "git": {"merge_base": MB, "clone": self.fetch}}
        self.script_text = 'CANDIDATE_BRANCHES=(\n  "cassandra-4.1:' + "f" * 40 + '"\n)\n'

    def shows_script(self):
        return {f"show {MB}:test-common/build.gradle": (0, 'ext.dtestJar = "dtest-4.1.11.jar"\n', "", {}),
                f"show {MB}:scripts/build-dtest-jars.sh": (0, self.script_text, "", {}),
                f"show {MB}:scripts/build-shaded-dtest-jar-local.sh": (0, "ant dtest-jar\n", "", {})}

    def test_cached_dtest_jar_is_copied_into_the_head(self):
        import hashlib
        key = hashlib.sha256((self.script_text + "ant dtest-jar\n").encode()).hexdigest()[:12]
        cached = os.path.join(self.work, "build-cache", "sidecar", "dtest-jars", key, "dtest-4.1.11.jar")
        os.makedirs(os.path.dirname(cached))
        with open(cached, "w") as f:
            f.write("jar")
        seen = {}
        script = {**self.shows_script(), **self.happy()}
        real_copy = shutil.copyfile

        def spy(src, dst, **k):
            if dst.endswith(os.path.join("dtest-jars", "dtest-4.1.11.jar")) and "buildclone" in dst:
                seen["dst"] = dst
            return real_copy(src, dst, **k)
        with mock.patch.object(gradle.shutil, "copyfile", side_effect=spy):
            sh, st = self.go(script)
        self.assertEqual(st["status"], "pass")
        self.assertTrue(seen.get("dst"))
        self.assertTrue(any("Compiled against dtest-4.1.11.jar" in n for n in st["notes"]))
        self.assertFalse(any("sh" in c["cmd"] and c["cmd"][-1].endswith("build-shaded-dtest-jar-local.sh") for c in sh.calls))

    def test_offline_without_a_cached_jar_is_unknown(self):
        sh, st = self.go({**self.shows_script(), **self.happy()}, offline=True)
        self.assertEqual(st["status"], "unknown")
        self.assertIn("dtest-4.1.11.jar is not cached", st["reason"])


if __name__ == "__main__":
    unittest.main()
