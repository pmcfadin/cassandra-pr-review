"""build-and-coverage runner: config, gate, selection, changed-line coverage, status mapping (fake shell, no builds)."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from cpr import build as build_pkg, cli
from cpr.build import coverage, gate, runner, sandbox, select
from cpr.ingest import bundle as bundle_mod

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "build")
HEAD, HEAD2, MB = "a" * 40, "b" * 40, "c" * 40
SSTABLE = "src/java/org/apache/cassandra/io/sstable/SSTable.java"
GITENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x",
          "PATH": os.environ["PATH"], "HOME": tempfile.gettempdir()}


def bundle(author="nivykani", head=HEAD, committers=("mck",), clone="/nonexistent", base="cassandra-4.0"):
    return {"pr": {"number": 5201, "author": author, "head_sha": head, "base": base, "author_association": "NONE"},
            "voter_emails": {"mck": ["mck@apache.org"]},
            "roster": {"status": "ok", "roster": {"committers": {c: c for c in committers}}},
            "overrides": {"github": {}, "jira": {}}, "git": {"merge_base": MB, "clone": clone}}


def fixture(name):
    with open(os.path.join(FIX, name)) as f:
        return f.read()


# ---- config, profile --------------------------------------------------------------------------------

class ConfigTests(unittest.TestCase):
    def test_config_loads(self):
        cfg = build_pkg.load_config()
        self.assertEqual(cfg["branches"]["cassandra-4.0"]["jdk"], 11)
        self.assertEqual(cfg["branches"]["trunk"]["jdk"], 17)
        self.assertEqual(cfg["selection"]["cap"], 25)
        self.assertTrue(cfg["branches"]["cassandra-4.0"]["jna_swap"])

    def test_profile_has_the_deny_list(self):
        with open(sandbox.PROFILE) as f:
            text = f.read()
        self.assertIn("(deny network*)", text)
        for d in (".ssh", ".aws", ".gnupg", ".config/gh", "Library/Keychains", ".claude"):
            self.assertIn(d, text)
        self.assertIn('(deny file-read-data (subpath (param "ROOT")) (subpath (param "WORK")))', text)
        self.assertIn('(allow file-read-data (subpath (param "RUN")) (subpath (param "OBJECTS")))', text)

    def test_wrap(self):
        prm = sandbox.params("/r", "/w", "/w/run", "/w/run/wt", "/w/run/m2", "/w/c/.git/objects", "/h")
        cmd = sandbox.wrap(["ant", "jar"], prm)
        self.assertEqual(cmd[0], "sandbox-exec")
        self.assertEqual(cmd[-2:], ["ant", "jar"])
        self.assertIn("RUN=/w/run", cmd)
        self.assertEqual(cmd[cmd.index("-f") + 1], sandbox.PROFILE)

    def test_env_is_scrubbed(self):
        env = sandbox.scrubbed_env("/jdk", "/ant/bin", "/h", {"CASSANDRA_USE_JDK11": "true"})
        self.assertEqual(set(env), {"PATH", "JAVA_HOME", "HOME", "JAVA_TOOL_OPTIONS", "ANT_OPTS", "CASSANDRA_USE_JDK11"})


# ---- gate -------------------------------------------------------------------------------------------

class GateTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.work, True)

    def test_committer_allowed(self):
        d = gate.decide(bundle(author="mck"), self.work)
        self.assertTrue(d["allowed"] and d["author_is_committer"] and not d["approved"])

    def test_override_maps_login(self):
        b = bundle(author="somebody")
        b["overrides"]["github"]["somebody"] = "mck"
        self.assertTrue(gate.decide(b, self.work)["allowed"])

    def test_non_committer_not_built(self):
        d = gate.decide(bundle(), self.work)
        self.assertFalse(d["allowed"])
        self.assertIn("not a committer", d["reason"])
        path, st = runner.not_built(bundle(), self.work, d)
        self.assertEqual((st["status"], st["approved"], st["author_is_committer"]), ("not-built", False, False))
        self.assertEqual(json.load(open(path))["head"], HEAD)

    def test_approval_is_per_head(self):
        self.assertTrue(gate.decide(bundle(head=HEAD), self.work, approve=True)["allowed"])
        self.assertTrue(gate.decide(bundle(head=HEAD), self.work)["allowed"])
        d = gate.decide(bundle(head=HEAD2), self.work)
        self.assertFalse(d["allowed"])
        self.assertFalse(d["approved"])


# ---- selection and coverage on a synthetic tree ------------------------------------------------------

def git(wt, *args):
    return subprocess.run(["git", "-C", wt, *args], env=GITENV, capture_output=True, text=True, check=True).stdout.strip()


def write(wt, rel, text):
    p = os.path.join(wt, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text)


SSTABLE_BASE = """package org.apache.cassandra.io.sstable;

public abstract class SSTable
{
    public static boolean delete(Descriptor d)
    {
        return true;
    }
}
"""
SSTABLE_HEAD = SSTABLE_BASE.replace("        return true;\n", "        int x = 1;\n        int y = 2;\n        return x < y;\n")


class TreeTests(unittest.TestCase):
    def setUp(self):
        self.wt = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.wt, True)
        git(self.wt, "init", "-q")
        write(self.wt, SSTABLE, SSTABLE_BASE)
        write(self.wt, "src/java/org/apache/cassandra/io/sstable/format/SSTableReader.java",
              "package x;\npublic abstract class SSTableReader extends SSTable\n{\n}\n")
        write(self.wt, "test/unit/org/apache/cassandra/db/lifecycle/LogTransactionTest.java",
              "public class LogTransactionTest\n{\n    @Test\n    public void t() { SSTableReader r = null; SSTable.delete(null); SSTable.delete(null); SSTable.delete(null);\n        SSTable a = null; SSTable b = null; SSTable c = null; SSTable.delete(null); }\n}\n")
        write(self.wt, "test/unit/org/apache/cassandra/db/AbstractBaseTest.java", "public abstract class AbstractBaseTest { SSTableReader r; }\n")
        write(self.wt, "test/unit/org/apache/cassandra/io/UnrelatedTest.java", "public class UnrelatedTest\n{\n    @Test\n    public void t() { }\n}\n")
        for i in range(40):  # enough tests that SSTable is not a "hub" class
            write(self.wt, f"test/unit/org/apache/cassandra/filler/Filler{i}Test.java", "class FillerTest { @Test void t() {} }\n")
        git(self.wt, "add", "-A")
        git(self.wt, "commit", "-q", "-m", "base")
        self.base = git(self.wt, "rev-parse", "HEAD")
        write(self.wt, SSTABLE, SSTABLE_HEAD)
        write(self.wt, "test/distributed/org/apache/cassandra/distributed/test/FooDTest.java", "class FooDTest {}\n")
        git(self.wt, "add", "-A")
        git(self.wt, "commit", "-q", "-m", "head")
        self.head = git(self.wt, "rev-parse", "HEAD")

    def test_selects_log_transaction_test(self):
        out = select.select(self.wt, self.base, self.head, build_pkg.load_config())
        paths = [c["path"] for c in out["selected"]]
        self.assertEqual(paths, ["org/apache/cassandra/db/lifecycle/LogTransactionTest.java"])
        why = " ".join(out["selected"][0]["reasons"])
        self.assertIn("references SSTable", why)
        self.assertIn("calls changed method", why)
        self.assertIn("references subtype SSTableReader", why)
        self.assertEqual(out["changed_methods"], ["delete"])
        self.assertEqual(out["skipped"]["non_unit"], ["test/distributed/org/apache/cassandra/distributed/test/FooDTest.java"])
        self.assertEqual(select.class_name(paths[0]), "org.apache.cassandra.db.lifecycle.LogTransactionTest")

    def test_pr_changed_test_comes_first_and_name_match(self):
        write(self.wt, "test/unit/org/apache/cassandra/io/sstable/SSTableTest.java", "public class SSTableTest { @Test public void a(){} }\n")
        write(self.wt, "test/unit/org/apache/cassandra/io/UnrelatedTest.java", "public class UnrelatedTest\n{\n    @Test\n    public void t() { int z; }\n}\n")
        git(self.wt, "add", "-A")
        git(self.wt, "commit", "-q", "-m", "tests")
        out = select.select(self.wt, self.base, git(self.wt, "rev-parse", "HEAD"), build_pkg.load_config())
        self.assertEqual(out["selected"][0]["path"], "org/apache/cassandra/io/sstable/SSTableTest.java")
        self.assertEqual(out["selected"][0]["reasons"][:2], ["changed by PR", "FooTest name: SSTable"])
        self.assertEqual(out["selected"][1]["path"], "org/apache/cassandra/io/UnrelatedTest.java")

    def test_changed_line_coverage_matches_5201(self):
        added = coverage.added_lines(self.wt, self.base, self.head)
        self.assertEqual(added, {SSTABLE: [7, 8, 9]})
        with mock.patch.object(coverage, "added_lines", return_value={SSTABLE: list(range(112, 122))}):
            cov = coverage.changed_coverage(self.wt, self.base, self.head, os.path.join(FIX, "report-5201.xml"))
        f = cov["files"][SSTABLE]
        self.assertEqual(f["covered"], [114, 115, 116, 117, 118, 120, 121])
        self.assertEqual(f["nonexec"], [112, 113, 119])
        self.assertEqual(cov["total"]["executable"], 7)
        self.assertEqual(cov["total"]["pct_executed"], 100.0)

    def test_missed_partial_and_absent_file(self):
        report = os.path.join(self.wt, "r.xml")
        write(self.wt, "r.xml", '<report><package name="org/apache/cassandra/io/sstable"><sourcefile name="SSTable.java">'
              '<line nr="1" mi="0" ci="2" mb="0" cb="0"/><line nr="2" mi="3" ci="0" mb="0" cb="0"/>'
              '<line nr="3" mi="1" ci="2" mb="0" cb="0"/></sourcefile></package></report>')
        with mock.patch.object(coverage, "added_lines", return_value={SSTABLE: [1, 2, 3, 4], "src/java/x/Gone.java": [1]}):
            cov = coverage.changed_coverage(self.wt, self.base, self.head, report)
        f = cov["files"][SSTABLE]
        self.assertEqual((f["covered"], f["missed"], f["partial"], f["nonexec"]), ([1], [2], [3], [4]))
        self.assertFalse(cov["files"]["src/java/x/Gone.java"]["in_report"])
        self.assertEqual(cov["total"]["pct_executed"], 66.7)


# ---- runner with a fake shell -------------------------------------------------------------------------

JUNIT_OK = ('<testsuite name="org.x.FooTest" tests="3" failures="0" errors="0" skipped="1">'
            '<testcase classname="org.x.FooTest" name="a"/></testsuite>')
JUNIT_FAIL = ('<testsuite name="org.x.FooTest" tests="3" failures="1" errors="0" skipped="0">'
              '<testcase classname="org.x.FooTest" name="a"><failure message="expected 1 but was 2">AssertionError\n at x</failure></testcase>'
              '</testsuite>')
JUNIT_TIMEOUT = ('<testsuite name="org.x.FooTest" tests="1" failures="1" errors="0" skipped="0">'
                 '<testcase classname="org.x.FooTest" name="a"><failure message="Timeout occurred">x</failure></testcase></testsuite>')
JAVAC = "[javac] /w/src/java/org/apache/cassandra/Foo.java:118: error: cannot find symbol\nBUILD FAILED\n"
SEL = {"selected": [{"path": "org/x/FooTest.java", "score": 40, "reasons": ["references Foo"]}],
       "skipped": {"non_unit": ["test/distributed/Foo.java"], "not_a_test": []}}


class FakeShell:
    """Records every command; `script` maps a marker word to (rc, out, err, files-to-write relative to cwd)."""

    def __init__(self, script=None, which=True, timeout_on=None, tamper=None):
        self.calls, self.script, self._which, self.timeout_on, self.tamper = [], script or {}, which, timeout_on, tamper

    def which(self, name, dirs=()):
        return f"/bin/{name}" if self._which else None

    def run(self, cmd, env=None, cwd=None, timeout=None):
        self.calls.append({"cmd": cmd, "env": env, "cwd": cwd})
        text = " ".join(cmd)
        if cmd[0] == "git" and "clone" in cmd and "--shared" in cmd:
            os.makedirs(cmd[-1])
        if cmd[0] == "git" and "clone" in cmd and "--no-checkout" in cmd and "--shared" not in cmd:
            os.makedirs(cmd[-1])
            open(os.path.join(cmd[-1], "SRC"), "w").close()
        if cmd[0] == "cp" and cmd[1] == "-cR":
            shutil.copytree(cmd[-2], cmd[-1])
        rc, out, err = 0, "", ""
        for marker, (r, o, e, files) in self.script.items():
            if marker in text:
                rc, out, err = r, o, e
                for rel, content in files.items():
                    p = os.path.join(cwd, rel)
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                    with open(p, "w") as f:
                        f.write(content)
        if self.tamper and "jacoco-run" in text:
            self.tamper()
        return runner.Proc(rc, out, err, 1.0, self.timeout_on is not None and self.timeout_on in text)

    def markers(self):
        return [c for c in self.calls]


def ok(files=None):
    return (0, "", "", files or {})


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.work, True)
        self.jdk = os.path.join(self.work, "jdk", "11.0.32-tem")
        os.makedirs(self.jdk)
        self.fetch = os.path.join(self.work, "cassandra")
        os.makedirs(os.path.join(self.fetch, ".git", "hooks"))
        with open(os.path.join(self.fetch, ".git", "config"), "w") as f:
            f.write("[core]\n")
        self.cfg = build_pkg.load_config()
        self.cfg["jdk_homes"]["11"] = [self.jdk]
        self.cfg["maven_repository"] = os.path.join(self.work, "m2src")
        os.makedirs(os.path.join(self.cfg["maven_repository"], os.path.dirname(self.cfg["jna_swap"]["from"])))
        open(os.path.join(self.cfg["maven_repository"], self.cfg["jna_swap"]["from"]), "w").close()
        self.bundle = bundle(clone=self.fetch)
        self.decision = {"allowed": True, "approved": True, "author_is_committer": False, "reason": "owner approved"}

    def go(self, shell, select_fn=None, **kw):
        cov = lambda *a: {"files": {SSTABLE: {"covered": [1], "partial": [], "missed": [2], "nonexec": [3], "in_report": True}},  # noqa: E731
                          "total": {"covered": 1, "partial": 0, "missed": 1, "nonexec": 1, "executable": 2, "pct_executed": 50.0}}
        return runner.build(self.bundle, self.work, self.cfg, self.decision, shell=shell, root=self.work, home=self.work,
                            select_fn=select_fn or (lambda *a: SEL), cov_fn=cov, **kw)

    def happy_script(self, junit=JUNIT_OK):
        return {"jacoco-run": ok({"build/test/output/TEST-org.x.FooTest.xml": junit}),
                "jacoco-report": ok({"build/jacoco/report.xml": "<report/>"})}

    def test_pass_run_is_sandboxed_in_order(self):
        sh = FakeShell(self.happy_script())
        path, st = self.go(sh)
        self.assertEqual(st["status"], "pass")
        self.assertEqual((st["jdk"], st["approved"], st["author_is_committer"]), ("Temurin 11.0.32 (CASSANDRA_USE_JDK11=true)", True, False))
        self.assertEqual(st["tests"]["run"], 3)
        self.assertEqual(st["changed_total"]["pct_executed"], 50.0)
        self.assertEqual(st["changed_lines"][SSTABLE]["nonexec_count"], 1)
        self.assertEqual(st["not_run"][0]["path"], "test/distributed/Foo.java")
        self.assertEqual(st["selected"][0]["class"], "org.x.FooTest")
        self.assertEqual(json.load(open(path, encoding="utf-8"))["status"], "pass")
        ants = [c for c in sh.calls if any(x.endswith("/ant") for x in c["cmd"])]
        self.assertTrue(ants)
        for c in ants:
            if "resolver-dist-lib" in c["cmd"]:
                self.assertNotEqual(c["cmd"][0], "sandbox-exec")  # the only unsandboxed ant call
                self.assertIn("-Dlocal.repository=" + os.path.join(os.path.dirname(path), "m2"), c["cmd"])
            else:
                self.assertEqual(c["cmd"][0], "sandbox-exec", c["cmd"])
            self.assertEqual(set(c["env"]) - {"PATH", "JAVA_HOME", "HOME", "JAVA_TOOL_OPTIONS", "ANT_OPTS", "CASSANDRA_USE_JDK11"}, set())
        steps = [" ".join(c["cmd"]) for c in sh.calls]
        order = [next(i for i, s in enumerate(steps) if m in s) for m in
                 (f"checkout --quiet --detach {MB}", "resolver-dist-lib", f"checkout --quiet --detach {HEAD}", " jar",
                  "build-test", "jna-5.13.0", "jacoco-run", "jacoco-report")]
        self.assertEqual(order, sorted(order))
        self.assertTrue(any("-Dtest.classlistfile=" in s and "-Dno-build-test=true" in s for s in steps))
        rd = os.path.dirname(path)
        self.assertFalse(os.path.exists(os.path.join(rd, "buildclone")))
        self.assertFalse(os.path.exists(os.path.join(rd, "m2")))
        self.assertTrue(os.path.exists(os.path.join(rd, "report.xml")))
        self.assertTrue(os.path.exists(os.path.join(rd, "test-output", "TEST-org.x.FooTest.xml")))

    def accord_script(self, url="https://github.com/apache/cassandra-accord.git", **more):
        sha = "d" * 40
        s = self.happy_script()
        s.update({"ls-tree": (0, f"160000 commit {sha}\tmodules/accord\n", "", {}),
                  "config --blob": (0, url + "\n", "", {}),
                  "show " + HEAD + ":build.xml": (0, '  <property name="base.version" value="6.0-alpha2"/>\n', "", {})})
        s.update(more)
        return s

    def test_accord_gitlink_builds_accord_in_net_profile_first(self):
        os.makedirs(os.path.join(self.work, ".gradle", "wrapper"))
        sh = FakeShell(self.accord_script())
        path, st = self.go(sh)
        self.assertEqual(st["status"], "pass", st["reason"])
        steps = [" ".join(c["cmd"]) for c in sh.calls]
        order = [next(i for i, s in enumerate(steps) if m in s) for m in
                 (f"checkout --quiet --detach {HEAD}", "clone --no-checkout https://github.com/apache/cassandra-accord.git",
                  "fetch --quiet origin " + "d" * 40, "checkout --quiet --detach " + "d" * 40, "gradlew", " jar", "jacoco-run")]
        self.assertEqual(order, sorted(order))
        g = next(c for c in sh.calls if "gradlew" in " ".join(c["cmd"]))
        self.assertEqual(g["cmd"][0], "sandbox-exec")
        self.assertEqual(g["cmd"][g["cmd"].index("-f") + 1], sandbox.PROFILE_NET)
        rd = os.path.dirname(path)
        self.assertIn("GRADLE=" + os.path.realpath(os.path.join(rd, "gradle")), g["cmd"])
        self.assertEqual(g["env"]["GRADLE_USER_HOME"], os.path.join(rd, "gradle"))
        self.assertIn("-Paccord_version=6.0-alpha2-SNAPSHOT", g["cmd"])
        self.assertIn("-Dmaven.repo.local=" + os.path.join(rd, "m2"), g["cmd"])
        self.assertTrue(any("cp -cR" in s and ".gradle/wrapper" in s for s in steps))
        for c in sh.calls:  # the main ant calls skip accord and stay on the no-network profile
            text = " ".join(c["cmd"])
            if "/ant" in text and "resolver-dist-lib" not in text:
                self.assertIn("-Dno-build-accord=true", c["cmd"])
                self.assertEqual(c["cmd"][c["cmd"].index("-f") + 1], sandbox.PROFILE)
        self.assertIn("accord_build", st["timings_s"])

    def test_stale_accord_jars_are_removed_after_the_accord_build(self):
        seen = {}

        class Shell(FakeShell):
            def run(self, cmd, env=None, cwd=None, timeout=None):
                text = " ".join(cmd)
                if f"--detach {HEAD}" in text:  # the base resolve left an accord jar in the tree
                    jar = os.path.join(cmd[cmd.index("-C") + 1], "build", "lib", "jars", "cassandra-accord-1-SNAPSHOT.jar")
                    os.makedirs(os.path.dirname(jar))
                    open(jar, "w").close()
                    seen["jar"] = jar
                if text.endswith(" jar"):
                    seen["left"] = os.path.exists(seen["jar"])
                return super().run(cmd, env, cwd, timeout)

        self.go(Shell(self.accord_script()))
        self.assertIn("left", seen)
        self.assertFalse(seen["left"])

    def test_accord_url_must_be_apache(self):
        sh = FakeShell(self.accord_script(url="https://github.com/evil/cassandra-accord.git"))
        _, st = self.go(sh)
        self.assertEqual(st["status"], "unknown")
        self.assertIn("unexpected accord submodule url", st["reason"])
        self.assertFalse(any("gradlew" in " ".join(c["cmd"]) or "cassandra-accord.git" in " ".join(c["cmd"]) for c in sh.calls))

    def test_accord_failure_is_unknown_not_build_failed(self):
        sh = FakeShell(self.accord_script(gradlew=(1, "", "e: Foo.kt: error: boom\n", {})))
        _, st = self.go(sh)
        self.assertEqual(st["status"], "unknown")
        self.assertTrue(st["reason"].startswith("accord build failed: "), st["reason"])
        self.assertIn("boom", st["reason"])
        self.assertFalse(any("/ant" in " ".join(c["cmd"]) and " jar" in " ".join(c["cmd"]) for c in sh.calls))

    def test_no_gitlink_runs_no_accord_steps(self):
        sh = FakeShell(self.happy_script())
        _, st = self.go(sh)
        self.assertEqual(st["status"], "pass")
        text = "\n".join(" ".join(c["cmd"]) for c in sh.calls)
        self.assertNotIn("gradlew", text)
        self.assertNotIn("no-build-accord", text)

    def test_missing_accord_artifact_is_unknown(self):
        sh = FakeShell(self.accord_script(**{" jar": (1, "Could not find cassandra-accord-6.0-alpha2-SNAPSHOT.jar\n", "", {})}))
        _, st = self.go(sh)
        self.assertEqual(st["status"], "unknown")
        self.assertIn("accord artifact was not found", st["reason"])

    def test_net_profile_is_the_base_profile_minus_network_deny(self):
        with open(sandbox.PROFILE) as f:
            base = f.read().splitlines()
        with open(sandbox.PROFILE_NET) as f:
            net = [ln for ln in f.read().splitlines() if not ln.startswith(";; NET") and not ln.startswith(";; Used only")]
        self.assertNotIn("(deny network*)", net)
        self.assertEqual([ln for ln in base if ln != "(deny network*)"],
                         [ln for ln in net if ln != '  (subpath (param "GRADLE"))'])
        self.assertIn('  (subpath (param "GRADLE"))', net)

    def test_offline_skips_networked_resolve(self):
        sh = FakeShell(self.happy_script())
        self.go(sh, offline=True)
        self.assertFalse(any("resolver-dist-lib" in " ".join(c["cmd"]) for c in sh.calls))

    def test_compile_error(self):
        sh = FakeShell({" jar": (1, JAVAC, "", {})})
        _, st = self.go(sh)
        self.assertEqual(st["status"], "build-failed")
        self.assertEqual(st["compile_errors"][0], {"file": "/w/src/java/org/apache/cassandra/Foo.java", "line": 118, "message": "cannot find symbol"})
        self.assertIn("Foo.java:118", st["reason"])
        self.assertFalse(any("jacoco-run" in " ".join(c["cmd"]) for c in sh.calls))

    def test_test_failure(self):
        _, st = self.go(FakeShell(dict(self.happy_script(JUNIT_FAIL), **{"jacoco-run": (1, "", "", {"build/test/output/TEST-org.x.FooTest.xml": JUNIT_FAIL})})))
        self.assertEqual(st["status"], "tests-failed")
        self.assertEqual(st["tests"]["failed"], 1)
        self.assertEqual(st["tests"]["failures"][0], {"class": "org.x.FooTest", "test": "a", "message": "expected 1 but was 2"})
        self.assertEqual(st["changed_total"]["executable"], 2)  # report is still produced after failures

    def test_sandbox_artifact_is_unknown_with_entry(self):
        junit = fixture("TEST-StreamingTransferTest.xml")
        sh = FakeShell(dict(self.happy_script(), **{"jacoco-run": (1, "", "", {"build/test/output/TEST-s.xml": junit})}))
        _, st = self.go(sh)
        self.assertEqual(st["status"], "unknown")
        self.assertEqual(st["tests"]["failed"] + st["tests"]["errors"], 0)
        self.assertEqual([(u["class"], u["test"]) for u in st["sandbox_unknowns"]],
                         [("org.apache.cassandra.streaming.StreamingTransferTest", "testTransferRangeTombstones")])

    def test_class_timeout(self):
        _, st = self.go(FakeShell(dict(self.happy_script(), **{"jacoco-run": (1, "", "", {"build/test/output/TEST-t.xml": JUNIT_TIMEOUT})})))
        self.assertEqual(st["status"], "timeout")

    def test_wall_timeout(self):
        _, st = self.go(FakeShell(self.happy_script(), timeout_on="build-test"))
        self.assertEqual(st["status"], "timeout")

    def test_jdk_missing(self):
        self.cfg["jdk_homes"]["11"] = [os.path.join(self.work, "nope")]
        sh = FakeShell()
        _, st = self.go(sh)
        self.assertEqual(st["status"], "unknown")
        self.assertIn("sdk install java 11.0.32-tem", st["reason"])
        self.assertEqual(sh.calls, [])

    def test_network_failure_in_build(self):
        _, st = self.go(FakeShell({" jar": (1, "java.net.UnknownHostException: repo.maven.apache.org\nBUILD FAILED", "", {})}))
        self.assertEqual(st["status"], "unknown")
        self.assertIn("network", st["reason"])

    def test_harness_failure(self):
        _, st = self.go(FakeShell({" jar": (1, "Unsupported JDK version used: 26", "", {})}))
        self.assertEqual(st["status"], "unknown")
        self.assertIn("harness", st["reason"])

    def test_no_tests_selected(self):
        _, st = self.go(FakeShell(), select_fn=lambda *a: {"selected": [], "skipped": {"non_unit": [], "not_a_test": []}})
        self.assertEqual((st["status"], st["coverage"]), ("pass", "no-tests"))

    def test_missing_report_is_unknown(self):
        sh = FakeShell({"jacoco-run": ok({"build/test/output/TEST-org.x.FooTest.xml": JUNIT_OK})})
        _, st = self.go(sh)
        self.assertEqual((st["status"], st["coverage"]), ("unknown", "missing"))
        self.assertEqual(st["tests"]["run"], 3)

    def test_fetch_clone_tamper_is_detected(self):
        def tamper():
            with open(os.path.join(self.fetch, ".git", "hooks", "post-checkout"), "w") as f:
                f.write("#!/bin/sh\n")
        _, st = self.go(FakeShell(self.happy_script(), tamper=tamper))
        self.assertEqual(st["status"], "unknown")
        self.assertIn("hook added: post-checkout", st["reason"])

    def test_symlinked_results_are_not_copied(self):
        secret = os.path.join(self.work, "secret.xml")
        with open(secret, "w") as f:
            f.write(JUNIT_FAIL)

        def tamper():
            out = os.path.join(self.work, "build-runs", "5201", HEAD, "buildclone", "build", "test", "output")
            os.makedirs(out, exist_ok=True)
            os.symlink(secret, os.path.join(out, "TEST-evil.xml"))
        _, st = self.go(FakeShell(self.happy_script(), tamper=tamper))
        self.assertEqual(st["status"], "pass")
        self.assertFalse(os.path.exists(os.path.join(self.work, "build-runs", "5201", HEAD, "test-output", "TEST-evil.xml")))


# ---- cli ------------------------------------------------------------------------------------------

class CliTests(unittest.TestCase):
    def test_never_ingested(self):
        work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, work, True)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = cli.main(["build", "5201", "--work-dir", work])
        self.assertEqual(rc, 1)
        self.assertIn("never ingested", err.getvalue())

    def test_not_built_for_non_committer(self):
        work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, work, True)
        with mock.patch.object(bundle_mod, "load_cached", return_value=bundle()):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = cli.main(["build", "5201", "--work-dir", work])
        self.assertEqual(rc, 0)
        self.assertIn("not-built", out.getvalue())
        with open(os.path.join(work, "build-runs", "5201", HEAD, "status.json")) as f:
            self.assertEqual(json.load(f)["status"], "not-built")


if __name__ == "__main__":
    unittest.main()


class FlakyRetry(unittest.TestCase):
    """A failure that does not recur on one retry is flaky (unknown), not a PR failure."""

    def tests_with(self, *failures):
        t = runner.empty_junit()
        t["failures"] = [{"class": c, "test": m, "kind": "error", "message": "x"} for c, m in failures]
        t["errors"] = len(failures)
        return t

    def test_passes_on_retry_is_flaky(self):
        t = runner.apply_retry(self.tests_with(("a.StreamingTransferTest", "t1")), runner.empty_junit())
        self.assertEqual(t["failures"], [])
        self.assertEqual(len(t["flaky"]), 1)
        status, reason = runner.map_status({"rc": 0, "errors": [], "text": ""}, t, True, True, False, 1)
        self.assertEqual(status, "unknown")
        self.assertIn("flaky", reason)

    def test_fails_again_is_a_failure(self):
        retry = self.tests_with(("a.FooTest", "t1"))
        t = runner.apply_retry(self.tests_with(("a.FooTest", "t1"), ("a.BarTest", "t2")), retry)
        self.assertEqual([f["class"] for f in t["failures"]], ["a.FooTest"])
        self.assertEqual([f["class"] for f in t["flaky"]], ["a.BarTest"])
        status, _ = runner.map_status({"rc": 0, "errors": [], "text": ""}, t, True, True, False, 1)
        self.assertEqual(status, "tests-failed")
