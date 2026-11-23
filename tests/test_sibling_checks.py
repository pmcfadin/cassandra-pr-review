"""Sidecar and Analytics: CI from GitHub checks, the project's own rules, checkstyle config, surfaces and docs."""

import os
import tempfile
import unittest
from unittest import mock

from cpr import checks, diffview, model, project, render
from cpr.ingest import gh_checks
from cpr.staticanalysis import run, tools
from cpr.triage import triage
from tests.helpers import SHA, bundle, github_ci, sidecar_bundle, with_files


def results(b):
    return {r["id"]: r for r in checks.run_all(b)}


def with_runs(b, runs, workflows=()):
    b["ci"]["github"] = {"status": "ok", "error": None, "head_sha": SHA, "check_runs": list(runs),
                         "workflow_runs": list(workflows)}
    return b


def run_(name, conclusion="success", status="completed"):
    return {"name": name, "status": status, "conclusion": conclusion if status == "completed" else None,
            "app": "github-actions", "url": f"https://github.com/x/{name}", "completed_at": None}


class GitHubChecksIngest(unittest.TestCase):
    def test_recorded_responses(self):
        gh = github_ci("sidecar-400", SHA)
        self.assertEqual(len(gh["check_runs"]), 21)
        self.assertEqual(gh_checks.summary(gh)["passed"], 21)
        waiting = github_ci("sidecar-401", SHA)
        self.assertEqual(waiting["check_runs"], [])
        self.assertEqual([w["conclusion"] for w in gh_checks.summary(waiting)["awaiting_approval"]], ["action_required"])

    def test_pages_are_flattened_and_other_heads_dropped(self):
        pages = {"check-runs": [{"check_runs": [{"name": "a"}]}, {"check_runs": [{"name": "b"}]}],
                 "workflow-runs": [{"workflow_runs": [{"name": "CI", "head_sha": SHA}, {"name": "old", "head_sha": "f" * 40}]}]}
        with mock.patch.object(gh_checks, "gh_json",
                               side_effect=lambda path, **k: pages["check-runs" if "/check-runs" in path else "workflow-runs"]):
            gh = gh_checks.fetch("apache/cassandra-sidecar", SHA, None)
        self.assertEqual([r["name"] for r in gh["check_runs"]], ["a", "b"])
        self.assertEqual([w["name"] for w in gh["workflow_runs"]], ["CI"])

    def test_unreachable(self):
        from cpr.net import NetError
        with mock.patch.object(gh_checks, "gh_json", side_effect=NetError("gh: HTTP 502")):
            gh = gh_checks.fetch("apache/cassandra-sidecar", SHA, None)
        self.assertEqual(gh["status"], "unavailable")
        b = sidecar_bundle()
        b["ci"]["github"] = gh
        self.assertEqual(results(b)["ci.evidence"]["status"], "unknown")


class GitHubCi(unittest.TestCase):
    def test_green_head(self):
        r = results(sidecar_bundle())
        self.assertEqual(r["ci.evidence"]["status"], "pass")
        self.assertIn("21 checks", r["ci.evidence"]["summary"])
        self.assertEqual(r["ci.freshness"]["status"], "pass")
        self.assertEqual(r["ci.failures"]["status"], "pass")

    def test_awaiting_approval_is_not_a_failure(self):
        b = sidecar_bundle()
        b["ci"]["github"] = github_ci("sidecar-401", SHA)
        r = results(b)
        self.assertEqual(r["ci.evidence"]["status"], "unknown")
        self.assertIn("approve", r["ci.evidence"]["summary"])
        self.assertEqual(r["ci.evidence"]["owner"], "committer")
        self.assertEqual(r["ci.freshness"]["status"], "not-applicable")

    def test_no_ci_at_all_fails(self):
        r = results(with_runs(sidecar_bundle(), []))
        self.assertEqual(r["ci.evidence"]["status"], "fail")

    def test_running_and_failed(self):
        r = results(with_runs(sidecar_bundle(), [run_("unit"), run_("it", status="in_progress")]))
        self.assertEqual(r["ci.evidence"]["status"], "unknown")
        self.assertIn("still running", r["ci.evidence"]["summary"])
        r = results(with_runs(sidecar_bundle(), [run_("unit"), run_("it", "failure"), run_("docs", "cancelled")]))
        self.assertEqual(r["ci.evidence"]["status"], "pass")
        self.assertEqual(r["ci.failures"]["status"], "warn")
        self.assertIn("it: failure", " ".join(e["text"] for e in r["ci.failures"]["evidence"]))

    def test_branch_row_shows_the_checks(self):
        b = with_runs(sidecar_bundle(), [run_("unit"), run_("it", "failure")],
                      [{"name": "CI", "status": "completed", "conclusion": "failure", "url": "https://github.com/x/run"}])
        m = model.build(b, checks.run_all(b), triage(b), render.load_docs(), diffview.unavailable("x"))
        ci = next(r for r in m["branches"] if r["is_self"])["ci"]
        self.assertEqual((ci["passed"], ci["failed"], ci["total"], ci["overall"]), (1, 1, 2, "failed"))
        self.assertEqual(ci["failures"], ["it"])
        self.assertEqual(m["project"]["ci_provider"], "github-checks")

    def test_cassandra_still_reads_jira(self):
        b = bundle()
        b["ci"]["github"] = {"status": "ok", "check_runs": [], "workflow_runs": []}  # ignored for Cassandra
        self.assertEqual(results(b)["ci.evidence"]["status"], "pass")


class ReviewFindings(unittest.TestCase):
    """Gaps found while writing the subproject docs."""

    def test_feature_branch_without_ci_is_not_a_failure(self):
        b = with_runs(sidecar_bundle(), [])
        b["pr"]["base"] = "mutation-tracking-support"
        self.assertEqual(results(b)["ci.evidence"]["status"], "not-applicable")
        b["pr"]["base"] = "trunk"
        self.assertEqual(results(b)["ci.evidence"]["status"], "fail")

    def test_test_methods_follow_the_projects_layout(self):
        b = sidecar_bundle()
        f = {"rule": "CognitiveComplexity", "score": 30, "classification": "introduced", "class": "T", "method_sig": "t()",
             "file": "server/src/test/java/org/apache/cassandra/sidecar/T.java"}
        b["static_analysis"] = {"status": "ran", "tools": {"pmd": {"status": "ran", "files_expected": 1, "files_analyzed": 1}},
                                "complexity": {"threshold": 15, "methods": [], "findings": [f]}}
        r = results(b)["static.complexity"]
        self.assertEqual(r["status"], "pass")
        self.assertIn("1 test method(s)", r["evidence"][0]["text"])

    def test_missing_tests_advice_names_the_projects_layout(self):
        b = with_files(sidecar_bundle(), [("server/src/main/java/org/apache/cassandra/sidecar/X.java", ["int x;"], False)])
        self.assertIn("src/integrationTest", results(b)["tests.present"]["action"])

    def test_build_runs_the_gradle_strategy_for_a_committer(self):
        import contextlib
        import io
        from cpr import cli
        from cpr.ingest import bundle as bundle_mod
        with tempfile.TemporaryDirectory() as d:
            b = sidecar_bundle()
            b["pr"]["author"], b["pr"]["author_association"] = "bob", "MEMBER"  # a committer: builds
            bundle_mod.save(b, d)
            out = io.StringIO()
            with mock.patch("cpr.build.runner.build", return_value=("/x/status.json", {"status": "pass", "reason": "ok"})) as run, \
                    contextlib.redirect_stdout(out):
                self.assertEqual(cli.main(["build", "sidecar#397", "--work-dir", d]), 0)
            self.assertEqual(run.call_count, 1)
            self.assertIn("sidecar#397: pass", out.getvalue())

    def test_build_refuses_a_project_with_no_build(self):
        import contextlib
        import io
        from cpr import cli, project
        from cpr.ingest import bundle as bundle_mod
        with tempfile.TemporaryDirectory() as d:
            b = sidecar_bundle()
            b["pr"]["author"], b["pr"]["author_association"] = "bob", "MEMBER"
            bundle_mod.save(b, d)
            out = io.StringIO()
            with mock.patch.object(project.load("sidecar"), "build", {}), \
                    mock.patch("cpr.build.runner.build", side_effect=AssertionError("built")), contextlib.redirect_stdout(out):
                self.assertEqual(cli.main(["build", "sidecar#397", "--work-dir", d]), 0)
            self.assertIn("not-built", out.getvalue())
            self.assertIn("no build set up for Cassandra Sidecar", out.getvalue())


class OwnRules(unittest.TestCase):
    def test_cassandra_only_checks_are_not_applicable(self):
        r = results(sidecar_bundle())
        for cid in project.load("sidecar").disabled_checks:
            self.assertEqual(r[cid]["status"], "not-applicable", cid)
            self.assertEqual(r[cid]["summary"], "Not part of Cassandra Sidecar's process")
        self.assertEqual(r["jira.key-present"]["title"], "PR references a CASSSIDECAR ticket")
        self.assertEqual(results(bundle())["jira.key-present"]["title"], "PR references a CASSANDRA ticket")

    def test_key_in_the_subject_is_the_subprojects_convention(self):
        self.assertEqual(results(sidecar_bundle())["commits.message-format"]["status"], "pass")
        b = bundle()
        b["commits"][0]["message"] = "CASSANDRA-21649: Fix things\n\npatch by Alice; reviewed by Bob for CASSANDRA-21649"
        self.assertEqual(results(b)["commits.message-format"]["status"], "warn")

    def test_missing_key_names_the_project(self):
        b = sidecar_bundle(jira_key={"key": None, "sources": [], "conflicts": [], "mentioned": []})
        r = results(b)["jira.key-present"]
        self.assertEqual(r["status"], "fail")
        self.assertIn("CASSSIDECAR-N", r["summary"])
        self.assertIn("CASSSIDECAR-12345", r["action"])

    def test_about_lists_the_projects_gaps(self):
        b = sidecar_bundle()
        m = model.build(b, checks.run_all(b), triage(b), render.load_docs(project=project.of(b)), diffview.unavailable("x"))
        self.assertTrue(any("in-JVM dtest suites are not run" in x for x in m["about"]["not_checked"]))
        self.assertEqual(m["lab_plan"]["status"], "none")
        self.assertIn("no lab plan for Cassandra Sidecar", m["lab_plan"]["reason"])


class Surfaces(unittest.TestCase):
    def test_sidecar(self):
        b = with_files(sidecar_bundle(), [
            ("client-common/src/main/java/org/apache/cassandra/sidecar/common/response/NodeSettings.java", ["int x;"], False),
            ("conf/sidecar.yaml", ["x: 1"], False),
            ("server/src/main/java/org/apache/cassandra/sidecar/db/schema/RestoreJobsSchema.java", ["int x;"], False)])
        r = results(b)["compat.surfaces"]
        self.assertEqual(r["status"], "warn")
        for name in ("REST API", "configuration", "sidecar schema"):
            self.assertIn(name, r["summary"])
        t = {s["signal"]: s for s in triage(b)["signals"]}
        self.assertIn("REST API", t["high-risk surfaces"]["value"])

    def test_analytics(self):
        b = with_files(sidecar_bundle(), [
            ("cassandra-analytics-cdc-codec/src/main/resources/cdc_bytes.avsc", ["{}"], False),
            ("cassandra-five-zero-bridge/src/main/java/org/apache/cassandra/bridge/X.java", ["int x;"], False),
            ("cassandra-analytics-core/src/main/java/org/apache/cassandra/spark/bulkwriter/RecordWriter.java", ["int x;"], False)])
        b["meta"] = {**b["meta"], "project": "analytics", "repo": "apache/cassandra-analytics"}
        r = results(b)["compat.surfaces"]
        self.assertIn("CDC Avro schemas", r["summary"])
        self.assertIn("Cassandra version bridges", r["summary"])
        t = {s["signal"]: s["value"] for s in triage(b)["signals"]}
        self.assertIn("spark/bulkwriter/", t["concurrency-sensitive paths"])

    def test_cassandra_surfaces_do_not_apply(self):
        b = with_files(sidecar_bundle(), [("src/java/org/apache/cassandra/net/Verb.java", ["int x;"], False)])
        self.assertEqual(results(b)["compat.surfaces"]["status"], "pass")


class Checkstyle(unittest.TestCase):
    def test_scopes(self):
        sc, an, ca = project.load("sidecar"), project.load("analytics"), project.load("cassandra")
        self.assertEqual(sc.static_kind("server/src/main/java/org/apache/cassandra/sidecar/X.java"), "main")
        self.assertEqual(sc.static_kind("server/src/integrationTest/java/X.java"), "test")
        self.assertIsNone(sc.static_kind("src/java/org/apache/cassandra/X.java"))
        self.assertEqual(an.static_kind("cassandra-analytics-core/src/main/scala-2.13-spark-4/org/X.java"), "main")
        self.assertEqual(ca.static_kind("tools/stress/src/org/apache/cassandra/stress/test/X.java"), None)  # as before
        self.assertEqual(run.checkstyle_scope("test/unit/X.java"), "test")

    def test_tool_per_project(self):
        cfg = tools.load_config()
        self.assertEqual(tools.checkstyle_id(cfg, "trunk", project.load("sidecar").static["checkstyle"]["tool"]), "checkstyle-7.8.1")
        self.assertEqual(tools.checkstyle_id(cfg, "trunk", project.load("analytics").static["checkstyle"]["tool"]), "checkstyle-9.3")
        self.assertEqual(tools.checkstyle_id(cfg, "cassandra-4.1", project.load("cassandra").static["checkstyle"]["tool"]),
                         "checkstyle-8.40")
        for tid in ("checkstyle-7.8.1", "checkstyle-9.3"):
            self.assertRegex(cfg["tools"][tid]["sha256"], r"^[0-9a-f]{64}$")

    def fetch(self, slug, files):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(run, "show", side_effect=lambda c, r, n: files.get(n)):
            cfgs = run.fetch_configs("clone", "ref", os.path.join(d, "cfg"), project.load(slug).static["checkstyle"])
            texts = {k: open(v).read() for k, v in (cfgs or {}).items()}
            dirs = {os.path.dirname(v) for v in (cfgs or {}).values()}
        return cfgs, texts, dirs

    def test_configs_are_copied_side_by_side(self):
        cfgs, texts, dirs = self.fetch("analytics", {"config/checkstyle/checkstyle.xml": "c", "config/checkstyle/suppressions.xml": "s"})
        self.assertEqual(texts, {"config/checkstyle/checkstyle.xml": "c", "config/checkstyle/suppressions.xml": "s"})
        self.assertEqual(len(dirs), 1)
        self.assertIsNone(self.fetch("sidecar", {})[0])  # required file missing on the branch

    def test_properties(self):
        seen = {}

        def execute(cmd, env, timeout, cwd=None):
            with open(cmd[cmd.index("-p") + 1]) as f:
                seen[cmd[cmd.index("-c") + 1]] = f.read()
            with open(cmd[cmd.index("-o") + 1], "w") as f:
                f.write("<checkstyle/>")
            return 0, "", "", 0.1
        with tempfile.TemporaryDirectory() as d, mock.patch.object(run, "execute", execute):
            an = project.load("analytics")
            cfg = os.path.join(d, "cfg", "checkstyle.xml")
            rel = "cassandra-analytics-core/src/main/java/X.java"
            run.run_checkstyle("java", "cs.jar", {"config/checkstyle/checkstyle.xml": cfg}, d, [rel, "README.md"], d, "head", 10,
                               an.static["checkstyle"], an.static_kind)
            self.assertEqual(seen[cfg], f"config_loc={os.path.join(d, 'cfg')}\n")
            sc = project.load("sidecar")
            cfg2 = os.path.join(d, "cfg2", "checkstyle.xml")
            r = run.run_checkstyle("java", "cs.jar", {"checkstyle.xml": cfg2}, d, ["server/src/test/java/T.java"], d, "x", 10,
                                   sc.static["checkstyle"], sc.static_kind)
            self.assertEqual(seen[cfg2], "")  # sidecar's config needs no property
            self.assertEqual(r["missing"], ["server/src/test/java/T.java"])  # no <file> in the output

    def test_banned_api_reads_the_projects_main_sources(self):
        xml = ('<module name="Checker"><module name="TreeWalker"><module name="IllegalImport">'
               '<property name="illegalPkgs" value="junit.framework"/></module></module></module>')
        b = with_files(sidecar_bundle(), [("server/src/main/java/org/apache/cassandra/sidecar/X.java",
                                           ["import junit.framework.Assert;"], False)])
        b["base_files"]["checkstyle_xml"] = xml
        self.assertEqual(results(b)["static.banned-api"]["status"], "warn")
        b["base_files"]["checkstyle_xml"] = None
        self.assertIn("`checkstyle.xml`", results(b)["static.banned-api"]["summary"])


class Docs(unittest.TestCase):
    def test_project_docs_override_shared_ones(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("jira", "ci"):
                with open(os.path.join(d, f"{name}.md"), "w") as f:
                    f.write(f"shared {name}")
            os.makedirs(os.path.join(d, "subprojects"))
            with open(os.path.join(d, "subprojects", "ci.md"), "w") as f:
                f.write("subproject ci")
            docs = render.load_docs(d, ["jira", "ci"], project.load("sidecar"))
            self.assertEqual(docs, {"jira": "shared jira", "ci": "subproject ci"})
            self.assertEqual(render.load_docs(d, ["ci"], project.load("cassandra"))["ci"], "shared ci")


if __name__ == "__main__":
    unittest.main()
