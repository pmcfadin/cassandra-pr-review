"""Project profiles: naming the project, per-project storage and migration, path classes and ticket keys."""

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from cpr import checks, cli, context, credits, diffview, layout, model, paths, project, render, site
from cpr.ingest import bundle as bundle_mod, keys
from cpr.triage import triage
from tests.helpers import SHA, bundle, result, sidecar_bundle


class Profiles(unittest.TestCase):
    def test_known_projects(self):
        self.assertEqual(project.slugs(), ["analytics", "cassandra", "sidecar"])
        self.assertEqual(project.load("sidecar").repo, "apache/cassandra-sidecar")
        self.assertEqual(project.by_repo("Apache/Cassandra-Analytics").slug, "analytics")
        self.assertEqual(project.load("analytics").clone_name, "cassandra-analytics")
        with self.assertRaises(project.ProjectError):
            project.load("../cassandra")
        with self.assertRaises(project.ProjectError):
            project.by_repo("apache/cassandra-dtest")

    def test_bundle_project(self):
        self.assertEqual(project.of(sidecar_bundle()).slug, "sidecar")
        self.assertEqual(project.of({"meta": {"repo": "apache/cassandra"}}).slug, "cassandra")  # saved before profiles
        self.assertEqual(project.of({"pr": {}}).slug, "cassandra")

    def test_pr_references(self):
        cases = {
            "5201": ("cassandra", 5201),
            "sidecar#397": ("sidecar", 397),
            "apache/cassandra-analytics#260": ("analytics", 260),
            "https://github.com/apache/cassandra-sidecar/pull/397": ("sidecar", 397),
            "https://github.com/apache/cassandra/pull/5201/": ("cassandra", 5201),
        }
        for text, want in cases.items():
            p, n = project.parse_ref(text)
            self.assertEqual((p.slug, n), want, text)
        self.assertEqual(project.parse_ref("397", "sidecar")[0].slug, "sidecar")
        self.assertEqual(project.parse_ref("sidecar#397", "sidecar")[0].slug, "sidecar")
        for bad, given in (("sidecar#397", "analytics"), ("#397", None), ("pull/397", None), ("nope#1", None)):
            with self.assertRaises(project.ProjectError, msg=bad):
                project.parse_ref(bad, given)


class Classifier(unittest.TestCase):
    def test_sidecar_layout(self):
        pc = project.load("sidecar").paths
        main = "server/src/main/java/org/apache/cassandra/sidecar/Foo.java"
        self.assertTrue(pc.is_prod(main))
        self.assertEqual(pc.subsystem(main), "server")
        self.assertEqual(pc.subsystem("adapters/adapters-base/src/main/java/A.java"), "adapters/adapters-base")
        self.assertEqual(pc.test_suite("server/src/test/java/org/apache/cassandra/sidecar/FooTest.java"), "unit")
        self.assertEqual(pc.test_suite("server/src/integrationTest/java/X.java"), "integration")
        self.assertEqual(pc.test_suite("server/src/containerTest/java/X.java"), "container")
        self.assertTrue(pc.is_test_resource("server/src/test/resources/config/sidecar_ssl.yaml"))
        self.assertTrue(pc.is_build("server/build.gradle"))
        self.assertTrue(pc.is_doc("CONTRIBUTING.md"))
        self.assertFalse(pc.is_prod("conf/sidecar.yaml"))
        self.assertIsNone(pc.test_suite(main))

    def test_analytics_layout(self):
        pc = project.load("analytics").paths
        self.assertTrue(pc.is_prod("cassandra-analytics-core/src/main/scala-2.13-spark-4/org/apache/Foo.java"))
        self.assertEqual(pc.test_suite("cassandra-analytics-core/src/test/spark3/org/FooTest.java"), "unit")
        self.assertEqual(pc.test_suite("cassandra-analytics-integration-tests/src/test/java/BulkIT.java"), "integration")
        self.assertTrue(pc.is_build("profiles/scala-2.13-spark-4-jdk-17.gradle"))
        self.assertEqual(pc.subsystem("cassandra-five-zero-bridge/src/main/java/B.java"), "cassandra-five-zero-bridge")

    def test_cassandra_rules_are_the_module_functions(self):
        pc = project.load("cassandra").paths
        for p in ("src/java/org/apache/cassandra/db/Foo.java", "test/unit/org/apache/cassandra/db/FooTest.java",
                  "test/distributed/org/apache/cassandra/distributed/test/X.java", "pylib/cqlshlib/test/t.py",
                  "doc/x.md", "src/README.md", "build.xml", "src/gen-java/A.java", "test/data/a.db"):
            for fn in ("is_prod", "is_test", "is_test_resource", "is_generated", "is_doc", "is_build", "test_suite",
                       "subsystem"):
                self.assertEqual(getattr(pc, fn)(p), getattr(paths, fn)(p), (fn, p))
        self.assertEqual(paths.subsystem("src/java/org/apache/cassandra/db/Foo.java"), "db")
        self.assertEqual(pc.suite_labels()["unit"], "Unit (test/unit)")
        self.assertEqual(list(pc.suite_labels())[-1], "other")


class Keys(unittest.TestCase):
    def test_sidecar_keys(self):
        sc = project.load("sidecar")
        r = keys.resolve("CASSSIDECAR-12: Fix", "fix-thing", "Follows CASSANDRA-20000", [], sc)
        self.assertEqual(r["key"], "CASSSIDECAR-12")
        self.assertEqual(r["mentioned"], ["CASSSIDECAR-12"])  # another project's key is not a ticket here
        self.assertEqual(keys.resolve("Fix", "cassandrasc-7/x", "", [], sc)["key"], "CASSANDRASC-7")  # legacy key

    def test_bare_branch_number_is_cassandra_only(self):
        self.assertEqual(keys.resolve("Fix", "mck/21649/trunk", "", [])["key"], "CASSANDRA-21649")
        self.assertIsNone(keys.resolve("Fix", "mck/21649/trunk", "", [], project.load("sidecar"))["key"])

    def test_credit_line_with_markdown_link(self):
        msg = ("CASSSIDECAR-378: Fix (#397)\n\nPatch by Alice; Reviewed by Bob, Carol for "
               "[CASSSIDECAR-378](https://issues.apache.org/jira/browse/CASSSIDECAR-378)")
        p = credits.parse(msg, project.load("sidecar").jira_keys)
        self.assertEqual((p["authors"], p["reviewers"], p["key"]), (["Alice"], ["Bob", "Carol"], "CASSSIDECAR-378"))
        self.assertIsNone(credits.parse(msg)["key"])  # not a CASSANDRA key
        self.assertEqual(credits.primary_key("x\n\npatch by A; reviewed by B for CASSANALYTICS-37",
                                             ("CASSANALYTICS",)), "CASSANALYTICS-37")


class SidecarReport(unittest.TestCase):
    def setUp(self):
        self.b = sidecar_bundle()
        self.results = checks.run_all(self.b)

    def test_checks_see_module_layout(self):
        self.assertEqual(result(self.results, "tests.present")["status"], "pass")
        self.assertIn("unit", result(self.results, "tests.present")["summary"])
        self.assertEqual(result(self.results, "changelog.entry")["status"], "pass")
        fmt = result(self.results, "commits.message-format")
        self.assertNotIn("no `patch by", " ".join(e["text"] for e in fmt["evidence"]))

    def test_model_carries_the_project(self):
        m = model.build(self.b, self.results, triage(self.b), render.load_docs(), diffview.unavailable("x"),
                        context=context.build(self.b))
        self.assertEqual(m["project"]["repo"], "apache/cassandra-sidecar")
        self.assertEqual(m["project"]["suite_labels"]["unit"], "Unit (src/test)")
        kinds = {f["path"].split("/")[-1]: (f["kind"], f["suite"]) for f in m["files"]}
        self.assertEqual(kinds["FooHandler.java"], ("production", None))
        self.assertEqual(kinds["FooHandlerTest.java"], ("test", "unit"))
        model.validate({**m, "project": None})  # older models have no project
        with self.assertRaises(model.ModelError):
            model.validate({**m, "project": {"slug": "sidecar"}})

    def test_triage_counts_modules(self):
        t = triage(self.b)
        sig = {s["signal"]: s["value"] for s in t["signals"]}
        self.assertEqual(sig["subsystems touched"], "server")
        self.assertEqual(sig["production code without tests"], "no")


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class Layout(unittest.TestCase):
    def test_same_number_two_projects(self):
        with tempfile.TemporaryDirectory() as d:
            c, s = bundle(), sidecar_bundle()
            c["pr"]["number"] = s["pr"]["number"] = 397
            bundle_mod.save(c, d)
            bundle_mod.save(s, d)
            self.assertEqual(bundle_mod.load_cached(d, "cassandra", 397)["meta"]["repo"], "apache/cassandra")
            self.assertEqual(bundle_mod.load_cached(d, "sidecar", 397)["meta"]["repo"], "apache/cassandra-sidecar")
            self.assertNotEqual(layout.build_runs(d, "cassandra", 397), layout.build_runs(d, "sidecar", 397))

    def test_cached_bundle_of_another_project_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            s = sidecar_bundle()
            bundle_mod.save(s, d)
            os.makedirs(os.path.join(d, "pr", "cassandra"))
            os.rename(os.path.join(d, "pr", "sidecar", "397"), os.path.join(d, "pr", "cassandra", "397"))
            with self.assertRaises(bundle_mod.IngestError):
                bundle_mod.load_cached(d, "cassandra", 397)

    def legacy(self, work, reports):
        """The layout before projects: .work/pr/5201, .work/build-runs/5201 with a kept classpath, reports/5201."""
        os.makedirs(os.path.join(work, "pr", "5201", SHA, "lenses"))
        with open(os.path.join(work, "pr", "5201", SHA, "lenses", "x.json"), "w") as f:
            f.write("{}")
        rd = os.path.join(work, "build-runs", "5201", SHA)
        os.makedirs(os.path.join(rd, "classpath", "classes", "main"))
        jar = os.path.join(rd, "classpath", "jars", "a.jar")
        os.makedirs(os.path.dirname(jar))
        open(jar, "w").close()
        with open(os.path.join(rd, "status.json"), "w") as f:
            json.dump({"head": SHA, "status": "pass", "classpath": {
                "classes": [os.path.join(rd, "classpath", "classes", "main")], "jars": [jar, "/elsewhere/b.jar"]}}, f)
        with open(os.path.join(work, "build-runs", "5201", "approved.json"), "w") as f:
            f.write("{}")
        os.makedirs(os.path.join(reports, "5201"))
        open(os.path.join(reports, "5201", "index.html"), "w").close()

    def test_migrate_moves_once_and_rewrites_the_classpath(self):
        with tempfile.TemporaryDirectory() as d:
            work, reports = os.path.join(d, ".work"), os.path.join(d, "reports")
            self.legacy(work, reports)
            moves = layout.migrate(work, reports, log=lambda m: None)
            self.assertEqual(len(moves), 3)
            self.assertTrue(os.path.exists(os.path.join(work, "pr", "cassandra", "5201", SHA, "lenses", "x.json")))
            self.assertTrue(os.path.exists(os.path.join(reports, "cassandra", "5201", "index.html")))
            self.assertTrue(os.path.exists(os.path.join(work, "build-runs", "cassandra", "5201", "approved.json")))
            from cpr.staticanalysis import auxpath
            cp, note = auxpath.resolve(work, "cassandra", 5201, SHA)
            self.assertIn("with type info", note)
            self.assertTrue(all(p.startswith(os.path.join(work, "build-runs", "cassandra")) for p in cp.split(os.pathsep)))
            with open(os.path.join(work, "build-runs", "cassandra", "5201", SHA, "status.json")) as f:
                self.assertIn("/elsewhere/b.jar", json.load(f)["classpath"]["jars"])  # outside the run: untouched
            self.assertEqual(layout.migrate(work, reports, log=lambda m: None), [])

    def test_migrate_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            work, reports = os.path.join(d, ".work"), os.path.join(d, "reports")
            self.legacy(work, reports)
            os.makedirs(os.path.join(reports, "cassandra", "5201"))
            logs = []
            layout.migrate(work, reports, log=logs.append)
            self.assertTrue(os.path.exists(os.path.join(reports, "5201", "index.html")))
            self.assertTrue(any("already exists" in m for m in logs))

    def test_migrate_leaves_reports_alone_without_a_reports_dir(self):
        with tempfile.TemporaryDirectory() as d:
            work, reports = os.path.join(d, ".work"), os.path.join(d, "reports")
            self.legacy(work, reports)
            layout.migrate(work, None, log=lambda m: None)
            self.assertTrue(os.path.exists(os.path.join(reports, "5201", "index.html")))

    def test_migrate_removes_old_worktrees(self):
        with tempfile.TemporaryDirectory() as d:
            work = os.path.join(d, ".work")
            clone = os.path.join(work, "cassandra")
            os.makedirs(clone)
            git("init", "-q", cwd=clone)
            git("-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q", "--allow-empty", "-m", "x", cwd=clone)
            wt = os.path.join(work, "wt", "5201")
            os.makedirs(os.path.dirname(wt))
            git("worktree", "add", "-q", "--detach", wt, cwd=clone)
            layout.migrate(work, None, log=lambda m: None)
            self.assertFalse(os.path.exists(wt))
            out = subprocess.run(["git", "worktree", "list"], cwd=clone, capture_output=True, text=True).stdout
            self.assertNotIn(wt, out)


class Cli(unittest.TestCase):
    def test_sidecar_review_writes_its_own_report(self):
        with tempfile.TemporaryDirectory() as d:
            bundle_mod.save(sidecar_bundle(), d)
            out = io.StringIO()
            with mock.patch.object(cli, "ROOT", d), contextlib.redirect_stdout(out):
                rc = cli.main(["review", "sidecar#397", "--offline", "--work-dir", d, "--quiet"])
            self.assertEqual(rc, 0)
            self.assertIn("sidecar#397:", out.getvalue())
            m = site.read_model(os.path.join(d, "reports", "sidecar", "397", "index.html"))
            self.assertEqual(m["project"]["repo"], "apache/cassandra-sidecar")

    def test_conflicting_project_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = cli.main(["review", "sidecar#397", "--project", "analytics", "--offline", "--work-dir", d])
            self.assertEqual(rc, 1)
            self.assertIn("--project is analytics", err.getvalue())

    def test_comment_links_to_the_projects_page(self):
        from cpr import comment
        with mock.patch.dict(os.environ, {"CPR_PAGES_BASE": "https://example.org/site"}):
            self.assertEqual(comment.pages_url(project.load("sidecar"), 397), "https://example.org/site/sidecar/pr/397/")


if __name__ == "__main__":
    unittest.main()
