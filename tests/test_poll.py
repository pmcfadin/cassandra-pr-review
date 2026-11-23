"""PR polling: selection from recorded GitHub JSON, refresh with a fake review, and the workflow file."""

import json
import os
import re
import tempfile
import time
import unittest
from unittest import mock

from cpr import cli, poll, site
from cpr.net import Recorder
from tests.test_site import make_report

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NOW = 1791417600  # 2026-10-08 00:00 UTC


def open_prs():
    with open(os.path.join(HERE, "fixtures", "poll", "open-prs.json")) as f:
        return json.load(f)


def head(prs, n):
    return next(p["head"]["sha"] for p in prs if p["number"] == n)


class Select(unittest.TestCase):
    def test_everything_new_newest_first(self):
        picked, skipped = poll.select(open_prs(), {}, now=NOW)
        self.assertEqual([p["number"] for p in picked], [5234, 5238, 5237, 5236, 5233, 5232, 5231, 5223])
        self.assertEqual(skipped, [])

    def test_unchanged_pr_not_picked(self):
        prs = open_prs()
        picked, skipped = poll.select(prs, {5234: head(prs, 5234)}, now=NOW)
        self.assertNotIn(5234, [p["number"] for p in picked])
        self.assertEqual([(s["number"], s["reason"]) for s in skipped],
                         [(5234, "published report is for the current head")])

    def test_new_head_picked(self):
        picked, _ = poll.select(open_prs(), {5234: "0" * 40}, now=NOW)
        self.assertEqual((picked[0]["number"], picked[0]["reason"]), (5234, "new head"))

    def test_stale_draft_skipped_but_fresh_draft_kept(self):
        _, skipped = poll.select(open_prs(), {}, now=NOW + 40 * 86400)
        stale = {s["number"] for s in skipped if s["reason"].startswith("draft")}
        self.assertEqual(stale, {5238, 5233, 5232})
        picked, _ = poll.select(open_prs(), {}, now=NOW)
        self.assertIn(5238, [p["number"] for p in picked])

    def test_cap(self):
        picked, skipped = poll.select(open_prs(), {}, now=NOW, limit=3)
        self.assertEqual([p["number"] for p in picked], [5234, 5238, 5237])
        self.assertEqual(len(skipped), 5)
        self.assertTrue(all("cap of 3" in s["reason"] for s in skipped))

    def test_fetch_open_replays_recorded_api(self):
        with tempfile.TemporaryDirectory() as d:
            rec = Recorder(d)
            key = "GH --paginate --slurp repos/apache/cassandra/pulls?state=open&per_page=100"
            rec.put(key, {"body": json.dumps([open_prs()]), "status": 200})
            rec.offline = True
            self.assertEqual(len(poll.fetch_open(rec)), 8)


class Refresh(unittest.TestCase):
    def test_refresh_merges_and_survives_failures(self):
        with tempfile.TemporaryDirectory() as d:
            make_report(site.report_path(d, "cassandra", 5000), number=5000)

            def review(slug, n, out):
                if n == 5201:
                    raise RuntimeError("boom")
                if n == 5202:
                    return 1
                make_report(out, number=n)
                return 0

            logs = []
            res = poll.refresh([{"project": "cassandra", "number": n} for n in (5198, 5201, 5202)], d, review,
                               log=logs.append)
            self.assertEqual(res[("cassandra", 5198)], "added")
            self.assertTrue(res[("cassandra", 5201)].startswith("failed (RuntimeError"))
            self.assertEqual(res[("cassandra", 5202)], "failed (exit 1)")
            self.assertEqual(sorted(site.published_heads(d)), [("cassandra", 5000), ("cassandra", 5198)])
            self.assertEqual(logs[0], "cassandra#5198: added")

    def test_refresh_keeps_richer_report_for_same_head(self):
        with tempfile.TemporaryDirectory() as d:
            make_report(site.report_path(d, "cassandra", 5198), review=True)

            def review(slug, n, out):
                make_report(out)
                return 0

            self.assertEqual(poll.refresh([{"project": "cassandra", "number": 5198}], d, review, log=lambda m: None),
                             {("cassandra", 5198): "kept"})


class Heads(unittest.TestCase):
    def test_site_paths(self):
        self.assertEqual(poll._site_path("pr/5198/index.html"), ("cassandra", 5198))
        self.assertEqual(poll._site_path("sidecar/pr/397/index.html"), ("sidecar", 397))
        self.assertEqual(poll._site_path("cassandra/pr/5198/index.html"), ("cassandra", 5198))
        for name in ("index.html", "nope/pr/1/index.html", "sidecar/pr/x/index.html", "pr/1/other.html"):
            self.assertIsNone(poll._site_path(name), name)

    def test_heads_for(self):
        heads = {("cassandra", 1): "a", ("sidecar", 1): "b", ("sidecar", 2): "c"}
        self.assertEqual(poll.heads_for(heads, "sidecar"), {1: "b", 2: "c"})

    def test_heads_from_git_reads_both_layouts(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            up, repo = os.path.join(d, "up"), os.path.join(d, "repo")
            os.makedirs(up)
            g = lambda c, *a: subprocess.run(["git", "-C", c, *a], check=True, capture_output=True)  # noqa: E731
            g(up, "init", "-q", "-b", "gh-pages")
            make_report(os.path.join(up, "pr", "5000", "index.html"), number=5000, head="a" * 40)
            make_report(site.report_path(up, "cassandra", 5198), head="b" * 40)
            os.makedirs(os.path.join(up, "pr", "5198"))
            with open(os.path.join(up, "pr", "5198", "index.html"), "w") as f:  # a migrated redirect
                f.write(site.redirect_html("../../cassandra/pr/5198/"))
            g(up, "add", ".")
            g(up, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "site")
            subprocess.run(["git", "clone", "-q", up, repo], check=True, capture_output=True)
            self.assertEqual(poll.heads_from_git(repo), {("cassandra", 5000): "a" * 40, ("cassandra", 5198): "b" * 40})


class Cli(unittest.TestCase):
    def test_dry_run_and_run_with_fakes(self):
        real_main = cli.main

        def fake_main(argv):
            if argv[0] != "review":
                return real_main(argv)
            make_report(argv[argv.index("--out") + 1], number=int(argv[1]))
            return 0

        def fetch_open(recorder=None, repo=None):
            return open_prs() if repo == "apache/cassandra" else []

        with tempfile.TemporaryDirectory() as d, mock.patch.object(poll, "fetch_open", side_effect=fetch_open), \
                mock.patch.object(poll.time, "time", return_value=NOW):
            s = os.path.join(d, "site")
            os.makedirs(s)
            make_report(os.path.join(s, "pr", "5000", "index.html"), number=5000)  # pre-project layout
            self.assertEqual(real_main(["poll", "--site", s, "--limit", "2"]), 0)
            self.assertEqual(site.published_heads(s), {})  # a dry run writes nothing, not even the migration
            self.assertEqual(real_main(["poll", "--run"]), 2)  # --run needs --site
            seen = []
            with mock.patch.object(cli, "main", side_effect=lambda argv: seen.append(argv) or fake_main(argv)):
                self.assertEqual(real_main(["poll", "--run", "--site", s, "--limit", "2", "--work-dir", d]), 0)
            self.assertEqual(sorted(site.published_heads(s)), [("cassandra", 5000), ("cassandra", 5234), ("cassandra", 5238)])
            self.assertEqual([a[1:4] for a in seen], [["5234", "--project", "cassandra"], ["5238", "--project", "cassandra"]])
            self.assertTrue(os.path.exists(os.path.join(s, "index.html")))

    def test_project_option_and_per_project_picks(self):
        calls = []

        def fetch_open(recorder=None, repo=None):
            calls.append(repo)
            return open_prs()

        with tempfile.TemporaryDirectory() as d, mock.patch.object(poll, "fetch_open", side_effect=fetch_open), \
                mock.patch.object(poll.time, "time", return_value=NOW), mock.patch("sys.stdout") as out:
            s = os.path.join(d, "site")
            os.makedirs(s)
            self.assertEqual(cli.main(["poll", "--site", s, "--project", "sidecar"]), 0)
            self.assertEqual(calls, ["apache/cassandra-sidecar"])
            calls.clear()
            self.assertEqual(cli.main(["poll", "--site", s, "--limit", "1"]), 0)
            self.assertEqual(calls, ["apache/cassandra", "apache/cassandra-analytics", "apache/cassandra-sidecar"])
            printed = "".join(c.args[0] for c in out.write.call_args_list)
            for name in ("Cassandra: 1 PR(s)", "Cassandra Sidecar: 1 PR(s)", "Cassandra Analytics: 1 PR(s)"):
                self.assertIn(name, printed)


class Workflow(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, ".github", "workflows", "poll.yml")) as f:
            self.text = f.read()

    def test_triggers(self):
        self.assertIn('cron: "17 */6 * * *"', self.text)
        self.assertIn("workflow_dispatch:", self.text)
        self.assertIn("limit:", self.text)

    def test_only_contents_write(self):
        m = re.search(r"^permissions:\n((?:[ ]+\S.*\n)+)", self.text, re.M)
        self.assertEqual([l.strip() for l in m.group(1).splitlines()], ["contents: write"])
        self.assertEqual(len(re.findall(r"^\s*permissions:", self.text, re.M)), 1)

    def test_concurrency_never_cancels(self):
        self.assertRegex(self.text, r"concurrency:\n  group: pr-polling\n  cancel-in-progress: false")

    def test_actions_and_java(self):
        self.assertEqual(set(re.findall(r"uses: (\S+)", self.text)),
                         {"actions/checkout@v4", "actions/setup-java@v4", "actions/cache@v4"})
        self.assertIn("distribution: temurin", self.text)
        self.assertIn('java-version: "21"', self.text)

    def test_cache_token_and_publish(self):
        self.assertIn("path: .work/cassandra\n", self.text)
        self.assertIn("path: .work/cassandra-sidecar\n", self.text)
        self.assertIn("path: .work/cassandra-analytics\n", self.text)
        self.assertIn("%G-W%V", self.text)
        self.assertIn("GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}", self.text)
        self.assertNotIn("secrets.", self.text.replace("secrets.GITHUB_TOKEN", ""))
        self.assertIn("github-actions[bot]", self.text)
        self.assertIn("git push origin HEAD:gh-pages", self.text)
        self.assertIn("bin/cpr poll --run --site site", self.text)
        self.assertNotIn("cpr build", self.text)


if __name__ == "__main__":
    unittest.main()
