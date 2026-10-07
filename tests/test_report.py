"""review-report: model validation, safe injection, findings slot, aspect docs, diff view, output, CLI."""

import base64
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from cpr import checks, cli, diffview, model, render
from cpr.triage import triage
from tests.helpers import bundle

FINDINGS = {"status": "ran", "lenses": [{"name": "correctness", "summary": "", "approve": False, "findings": [
    {"id": "c2", "severity": "minor", "location": "a.java:3", "rule": "r", "problem": "p", "fix": "f"},
    {"id": "c1", "severity": "blocker", "location": "a.java:1", "rule": "r", "problem": "p", "fix": "f"},
]}]}


def build(b=None, review=None, dv=None):
    b = b or bundle()
    res = checks.run_all(b)
    return model.build(b, res, triage(b), render.load_docs(),
                       dv or diffview.unavailable("not installed"), review=review)


class Model(unittest.TestCase):
    def test_valid_model(self):
        m = build()
        self.assertEqual(m["recommendation"]["verdict"], "requirements-met-unreviewed")
        self.assertEqual([s["id"] for s in m["sections"]][0], "summary")

    def test_invalid_model_writes_no_file(self):
        m = build()
        m["checks"][0]["status"] = "great"
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "r", "index.html")
            with self.assertRaises(model.ModelError) as cm:
                render.write(m, out)
            self.assertIn("checks[0].status", str(cm.exception))
            self.assertFalse(os.path.exists(out))

    def test_findings_present_grouped_by_lens(self):
        m = build(review=FINDINGS)
        self.assertEqual(m["review"]["lenses"][0]["name"], "correctness")
        self.assertEqual(m["recommendation"]["verdict"], "needs-work")
        self.assertEqual(next(s for s in m["sections"] if s["id"] == "review")["status"], "warn")

    def test_bad_finding_severity_rejected(self):
        bad = json.loads(json.dumps(FINDINGS))
        bad["lenses"][0]["findings"][0]["severity"] = "catastrophic"
        with self.assertRaises(model.ModelError):
            build(review=bad)

    def test_code_review_not_run(self):
        m = build()
        self.assertEqual(m["review"]["status"], "not-run")
        self.assertEqual(next(s for s in m["sections"] if s["id"] == "review")["status"], "unknown")

    def test_about_states_limits(self):
        m = build()
        self.assertTrue(any("ant check" in x for x in m["about"]["not_checked"]))
        self.assertTrue(any("design" in x for x in m["about"]["human_only"]))

    def test_files_carry_kind_and_suite(self):
        m = build()
        f = {x["path"]: x for x in m["files"]}
        self.assertEqual(f["test/unit/org/apache/cassandra/db/FooTest.java"]["suite"], "unit")
        self.assertEqual(f["src/java/org/apache/cassandra/db/Foo.java"]["kind"], "production")


class Injection(unittest.TestCase):
    def test_hostile_diff_content_cannot_open_or_close_script(self):
        b = bundle()
        b["pr"]["title"] = "<!--<script>window.PWNED=1</script>"
        b["diff"] += "+</script><script>alert(1)</script>\n"
        html = render.render_html(build(b))
        start = html.index('<script id="report-model">')
        end = html.index("</script>", start)
        payload = html[start:end]
        self.assertNotIn("<", payload[len('<script id="report-model">'):])
        self.assertTrue(payload.isascii())

    def test_template_needs_one_marker(self):
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
            f.write("<!doctype html><p>no marker</p>")
        try:
            with self.assertRaises(render.RenderError):
                render.render_html(build(), f.name)
        finally:
            os.unlink(f.name)


class AspectDocs(unittest.TestCase):
    def test_doc_missing_fails_render(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(render.RenderError) as cm:
                render.load_docs(d)
            self.assertIn("missing aspect document", str(cm.exception))

    def test_docs_are_embedded(self):
        m = build()
        with open(os.path.join(render.DOCS_DIR, "testing.md")) as f:
            self.assertEqual(m["docs"]["testing"], f.read())
        testing = next(s for s in m["sections"] if s["id"] == "testing")
        self.assertEqual(testing["docs"], ["testing"])


class DiffView(unittest.TestCase):
    def test_unavailable_when_plugin_missing(self):
        dv = diffview.render(bundle(), [], env={"CPR_IDE_EXPLAIN": "/does/not/exist"})
        self.assertEqual(dv["status"], "unavailable")
        self.assertIn("not installed", dv["reason"])

    def test_generator_failure_is_unavailable(self):
        with tempfile.NamedTemporaryFile(suffix=".py") as gen:
            def runner(cmd, cwd, capture_output, text):
                return subprocess.CompletedProcess(cmd, 1, "", "boom")
            dv = diffview.render(bundle(), [], runner=runner, env={"CPR_IDE_EXPLAIN": gen.name})
        self.assertEqual(dv["status"], "unavailable")
        self.assertIn("boom", dv["reason"])

    def test_generator_output_embedded_and_command_shape(self):
        seen = {}
        with tempfile.NamedTemporaryFile(suffix=".py") as gen:
            def runner(cmd, cwd, capture_output, text):
                seen["cmd"], seen["cwd"] = cmd, cwd
                with open(cmd[cmd.index("--out") + 1], "w") as f:
                    f.write("<title>x</title><p>diff</p>")
                with open(cmd[cmd.index("--explain-map") + 1]) as f:
                    seen["map"] = json.load(f)
                return subprocess.CompletedProcess(cmd, 0, "", "")
            res = [{"status": "warn", "title": "Banned", "evidence": [{"text": "t", "location": "src/A.java:3"}]}]
            dv = diffview.render(bundle(), res, runner=runner, env={"CPR_IDE_EXPLAIN": gen.name})
        self.assertEqual(dv["status"], "ok")
        self.assertEqual(base64.b64decode(dv["html_b64"]).decode(), "<title>x</title><p>diff</p>")
        self.assertIn("--pr", seen["cmd"])
        self.assertEqual(seen["cwd"], "/nonexistent")
        self.assertIn("src/A.java", seen["map"])

    def test_network_references_are_refused(self):
        with tempfile.NamedTemporaryFile(suffix=".py") as gen:
            def runner(cmd, cwd, capture_output, text):
                with open(cmd[cmd.index("--out") + 1], "w") as f:
                    f.write('<script src="https://cdn.example/x.js"></script>')
                return subprocess.CompletedProcess(cmd, 0, "", "")
            dv = diffview.render(bundle(), [], runner=runner, env={"CPR_IDE_EXPLAIN": gen.name})
        self.assertEqual(dv["status"], "unavailable")

    def test_finds_newest_installed_version(self):
        with mock.patch.object(diffview.glob, "glob", return_value=[
                "/h/.claude/plugins/cache/rustyrazorblade-plugins/dev-skills/0.4.1/skills/ide-explain/scripts/g.py",
                "/h/.claude/plugins/cache/rustyrazorblade-plugins/dev-skills/0.10.0/skills/ide-explain/scripts/g.py"]):
            path, version = diffview.find_generator(env={})
        self.assertEqual(version, "0.10.0")


class Cli(unittest.TestCase):
    def test_default_output_and_offline(self):
        from cpr.ingest import bundle as bundle_mod
        with tempfile.TemporaryDirectory() as d:
            b = bundle()
            bundle_mod.save(b, d)
            out = os.path.join(d, "reports", "5198", "index.html")
            with mock.patch.object(cli, "ROOT", d):
                rc = cli.main(["review", "5198", "--offline", "--work-dir", d, "--quiet"])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(out))
            with open(out) as f:
                self.assertTrue(f.read().startswith("<!doctype html>"))

    def test_offline_without_cache_fails(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(cli.main(["review", "4242", "--offline", "--work-dir", d, "--quiet"]), 1)

    def test_pr_not_found_writes_no_report(self):
        from cpr.ingest import bundle as bundle_mod
        from cpr.ingest.github import PRNotFound
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(cli, "ROOT", d), \
                    mock.patch.object(bundle_mod, "ingest", side_effect=PRNotFound("#999999 is not a pull request")):
                rc = cli.main(["review", "999999", "--work-dir", d, "--quiet"])
            self.assertEqual(rc, 2)
            self.assertFalse(os.path.exists(os.path.join(d, "reports", "999999")))


if __name__ == "__main__":
    unittest.main()
