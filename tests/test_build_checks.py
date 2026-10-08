"""build.* checks and the Build & coverage section, from saved `cpr build` results."""

import copy
import json
import os
import tempfile
import unittest

from cpr import buildresult, checks, cli, diffview, model, render
from cpr.triage import triage
from tests.helpers import SHA, SHA2, bundle, result

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "fixtures", "build", "5201-status.json")


def status_5201(**kw):
    with open(FIXTURE) as f:
        d = json.load(f)
    d["head"] = SHA
    d.update(kw)
    return d


def run_checks(run, **bundle_kw):
    b = bundle(**bundle_kw)
    if run is not None:
        b["build"] = run
    res = checks.run_all(b)
    return {c: result(res, c) for c in ("build.compiles", "build.tests-pass", "build.changed-line-coverage")}


def passing(**kw):
    d = status_5201(status="pass", failures=None)
    d["tests"] = {**d["tests"], "failed": 0, "errors": 0, "failures": []}
    d.update(kw)
    return d


class Registered(unittest.TestCase):
    def test_categories_and_blocking(self):
        r = run_checks(None)
        self.assertEqual({c["category"] for c in r.values()}, {"build"})
        self.assertTrue(r["build.compiles"]["blocking"] and r["build.tests-pass"]["blocking"])
        self.assertFalse(r["build.changed-line-coverage"]["blocking"])
        self.assertTrue(all(c["owner"] == "contributor" for c in r.values()))


class NotBuilt(unittest.TestCase):
    def assert_not_built(self, r):
        for c in r.values():
            self.assertEqual(c["status"], "not-applicable", c["id"])
            self.assertIn("not built", c["summary"])

    def test_no_result(self):
        self.assert_not_built(run_checks(None))

    def test_not_built_status_carries_the_reason(self):
        r = run_checks({"status": "not-built", "head": SHA, "reason": "author is not a committer"})
        self.assert_not_built(r)
        self.assertIn("author is not a committer", r["build.compiles"]["summary"])

    def test_stale_run_is_not_built(self):
        r = run_checks(passing(head=SHA2))
        self.assert_not_built(r)
        self.assertNotIn("328", r["build.tests-pass"]["summary"])


class Compiles(unittest.TestCase):
    def test_pass_when_built(self):
        for st in ("pass", "tests-failed"):
            self.assertEqual(run_checks(passing(status=st))["build.compiles"]["status"], "pass", st)

    def test_pass_on_the_real_5201_result(self):
        self.assertEqual(run_checks(status_5201())["build.compiles"]["status"], "pass")

    def test_fail_lists_compile_errors(self):
        errs = [{"file": "src/java/Foo.java", "line": 118, "message": "cannot find symbol"}]
        r = run_checks({"status": "build-failed", "head": SHA, "reason": "ant jar failed", "compile_errors": errs})
        c = r["build.compiles"]
        self.assertEqual(c["status"], "fail")
        self.assertTrue(c["blocking"] and c["action"])
        self.assertIn("src/java/Foo.java:118", c["evidence"][0]["text"])
        self.assertEqual(r["build.tests-pass"]["status"], "not-applicable")
        self.assertEqual(r["build.changed-line-coverage"]["status"], "not-applicable")

    def test_unknown_without_proof_never_blocks(self):
        c = run_checks({"status": "unknown", "head": SHA, "reason": "JDK 11 missing"})["build.compiles"]
        self.assertEqual(c["status"], "unknown")
        self.assertFalse(c["blocking"])
        self.assertIn("JDK 11 missing", c["summary"])

    def test_timeout_is_unknown(self):
        self.assertEqual(run_checks({"status": "timeout", "head": SHA})["build.compiles"]["status"], "unknown")


class TestsPass(unittest.TestCase):
    def test_pass(self):
        c = run_checks(passing())["build.tests-pass"]
        self.assertEqual(c["status"], "pass")
        self.assertIn("328 tests in 25 classes", c["summary"])

    def test_fail_names_the_failures(self):
        fl = [{"class": "a.FooTest", "test": "testBar", "message": "expected 1"}]
        d = passing(status="tests-failed")
        d["tests"] = {**d["tests"], "failed": 1, "failures": fl}
        c = run_checks(d)["build.tests-pass"]
        self.assertEqual(c["status"], "fail")
        self.assertTrue(c["blocking"] and c["action"])
        self.assertIn("a.FooTest.testBar", c["evidence"][0]["text"])

    def test_sandbox_failures_are_excluded(self):
        sb = [{"class": "a.StreamTest", "test": "testX", "message": "transferTo0"}]
        d = passing(status="tests-failed", sandbox_unknowns=sb)
        d["tests"] = {**d["tests"], "errors": 1, "failures": [{"class": "a.StreamTest", "test": "testX", "message": "m"}]}
        c = run_checks(d)["build.tests-pass"]
        self.assertEqual(c["status"], "unknown")
        self.assertFalse(c["blocking"])

    def test_real_failure_beside_a_sandbox_one_still_fails(self):
        sb = [{"class": "a.StreamTest", "test": "testX"}]
        d = passing(status="tests-failed", sandbox_unknowns=sb)
        d["tests"] = {**d["tests"], "failed": 1, "failures": [{"class": "a.StreamTest", "test": "testX"},
                                                              {"class": "a.FooTest", "test": "t", "message": "no"}]}
        c = run_checks(d)["build.tests-pass"]
        self.assertEqual(c["status"], "fail")
        self.assertEqual(len(c["evidence"]), 1)

    def test_the_real_5201_result_is_unknown_not_fail(self):
        c = run_checks(status_5201())["build.tests-pass"]
        self.assertEqual(c["status"], "unknown")
        self.assertFalse(c["blocking"])

    def test_timeout_is_unknown(self):
        self.assertEqual(run_checks(passing(status="timeout"))["build.tests-pass"]["status"], "unknown")

    def test_no_test_results_is_unknown(self):
        self.assertEqual(run_checks({"status": "pass", "head": SHA})["build.tests-pass"]["status"], "unknown")


class Coverage(unittest.TestCase):
    def test_all_covered_passes_with_per_file_evidence(self):
        c = run_checks(status_5201())["build.changed-line-coverage"]
        self.assertEqual(c["status"], "pass")
        self.assertIn("7 added executable", c["summary"])
        self.assertIn("covered 7/7", c["evidence"][0]["text"])

    def test_missed_lines_warn_as_a_note(self):
        d = status_5201()
        d["changed_lines"] = {"src/java/A.java": {"covered": [1, 2], "partial": [], "missed": [5, 9]},
                              "src/java/B.java": {"covered": [3], "partial": [4], "missed": []}}
        d["changed_total"] = {"covered": 3, "partial": 1, "missed": 2, "executable": 5}
        c = run_checks(d)["build.changed-line-coverage"]
        self.assertEqual(c["status"], "warn")
        self.assertFalse(c["blocking"])
        self.assertFalse(c["action_required"])
        self.assertEqual(c["evidence"][0]["text"], "`src/java/A.java`: covered 2/4, missed lines 5, 9")
        self.assertIn("1 only partly", c["evidence"][1]["text"])

    def test_missing_coverage_is_unknown(self):
        d = status_5201()
        del d["changed_lines"]
        self.assertEqual(run_checks(d)["build.changed-line-coverage"]["status"], "unknown")

    def test_no_executable_lines_not_applicable(self):
        d = status_5201(changed_lines={}, changed_total={"executable": 0})
        self.assertEqual(run_checks(d)["build.changed-line-coverage"]["status"], "not-applicable")

    def test_file_missing_from_report_is_unknown(self):
        d = status_5201()
        d["changed_lines"]["src/java/C.java"] = {"covered": [], "partial": [], "missed": [], "in_report": False}
        self.assertEqual(run_checks(d)["build.changed-line-coverage"]["status"], "unknown")


class Loading(unittest.TestCase):
    def write(self, work, data, head=SHA):
        p = buildresult.status_path(work, 5198, head)
        os.makedirs(os.path.dirname(p))
        with open(p, "w") as f:
            json.dump(data, f)

    def test_loads_only_the_current_head(self):
        with tempfile.TemporaryDirectory() as w:
            self.write(w, passing())
            self.assertEqual(buildresult.load(w, 5198, SHA)["status"], "pass")
            self.assertIsNone(buildresult.load(w, 5198, SHA2))

    def test_file_for_another_head_inside_the_dir_is_ignored(self):
        with tempfile.TemporaryDirectory() as w:
            self.write(w, passing(head=SHA2))
            self.assertIsNone(buildresult.load(w, 5198, SHA))

    def test_garbage_is_not_built(self):
        with tempfile.TemporaryDirectory() as w:
            p = buildresult.status_path(w, 5198, SHA)
            os.makedirs(os.path.dirname(p))
            with open(p, "w") as f:
                f.write("{not json")
            self.assertIsNone(buildresult.load(w, 5198, SHA))

    def test_build_report_reads_the_saved_run(self):
        with tempfile.TemporaryDirectory() as w:
            self.write(w, passing())
            b = bundle()
            m = cli.build_report(b, w, offline=True, log=lambda *a: None)
            self.assertEqual(m["build"]["status"], "pass")
            self.assertEqual(result(m["checks"], "build.tests-pass")["status"], "pass")
            self.assertNotIn("build", b)
        with tempfile.TemporaryDirectory() as w:
            m = cli.build_report(bundle(), w, offline=True, log=lambda *a: None)
            self.assertEqual(m["build"]["status"], "not-built")


class Section(unittest.TestCase):
    def build(self, run):
        b = bundle()
        if run is not None:
            b["build"] = run
        return model.build(b, checks.run_all(b), triage(b), render.load_docs(), diffview.unavailable("x"))

    def test_kept_classpath_is_never_published(self):
        m = self.build(passing(classpath={"classes": ["/home/me/.work/build-runs/1/classes"], "jars": []}))
        self.assertNotIn("classpath", m["build"])
        self.assertNotIn("/home/me", json.dumps(m))

    def sec(self, m):
        ids = [s["id"] for s in m["sections"]]
        self.assertEqual(ids[ids.index("testing") + 1], "build")
        return m["sections"][ids.index("build")]

    def test_not_built(self):
        m = self.build(None)
        self.assertEqual(self.sec(m)["status"], "not-applicable")
        self.assertEqual(m["build"]["status"], "not-built")
        self.assertIn("committer", m["build"]["reason"])
        self.assertIn("--approve", m["build"]["reason"])
        self.assertEqual(self.sec(m)["docs"], ["build"])

    def test_stale_run_shows_no_old_numbers(self):
        m = self.build(passing(head=SHA2))
        self.assertEqual(m["build"]["status"], "not-built")
        self.assertNotIn("tests", m["build"])

    def test_pass_and_fail_status(self):
        self.assertEqual(self.sec(self.build(passing()))["status"], "pass")
        d = passing(status="build-failed", compile_errors=["x"])
        self.assertEqual(self.sec(self.build(d))["status"], "fail")

    def test_summary_verdict_not_moved_by_unknown(self):
        base = self.build(None)["recommendation"]["verdict"]
        self.assertEqual(self.build(status_5201())["recommendation"]["verdict"], base)

    def test_blocking_failure_blocks(self):
        d = {"status": "build-failed", "head": SHA, "compile_errors": ["boom"]}
        self.assertEqual(self.build(d)["recommendation"]["verdict"], "needs-contributor-work")


class Prepare(unittest.TestCase):
    def test_author_is_committer(self):
        b = bundle()
        self.assertFalse(buildresult.author_is_committer(b))
        b["pr"]["author"] = "bob"
        b["roster"] = {"status": "ok", "roster": {"committers": {"bob": "Bob"}}}
        b["overrides"] = {"github": {"bob": "bob"}}
        self.assertTrue(buildresult.author_is_committer(b))


if __name__ == "__main__":
    unittest.main()
