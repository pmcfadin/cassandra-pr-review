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
            make_report(os.path.join(d, "pr", "5000", "index.html"), number=5000)

            def review(n, out):
                if n == 5201:
                    raise RuntimeError("boom")
                if n == 5202:
                    return 1
                make_report(out, number=n)
                return 0

            logs = []
            res = poll.refresh([{"number": n} for n in (5198, 5201, 5202)], d, review, log=logs.append)
            self.assertEqual(res[5198], "added")
            self.assertTrue(res[5201].startswith("failed (RuntimeError"))
            self.assertEqual(res[5202], "failed (exit 1)")
            self.assertEqual(sorted(site.published_heads(d)), [5000, 5198])
            self.assertEqual(len(logs), 3)

    def test_refresh_keeps_richer_report_for_same_head(self):
        with tempfile.TemporaryDirectory() as d:
            make_report(os.path.join(d, "pr", "5198", "index.html"), review=True)

            def review(n, out):
                make_report(out)
                return 0

            self.assertEqual(poll.refresh([{"number": 5198}], d, review, log=lambda m: None), {5198: "kept"})


class Cli(unittest.TestCase):
    def test_dry_run_and_run_with_fakes(self):
        real_main = cli.main

        def fake_main(argv):
            if argv[0] != "review":
                return real_main(argv)
            make_report(argv[argv.index("--out") + 1], number=int(argv[1]))
            return 0

        with tempfile.TemporaryDirectory() as d, mock.patch.object(poll, "fetch_open", return_value=open_prs()):
            s = os.path.join(d, "site")
            os.makedirs(s)
            self.assertEqual(real_main(["poll", "--site", s, "--limit", "2"]), 0)
            self.assertEqual(site.published_heads(s), {})  # a dry run writes nothing
            self.assertEqual(real_main(["poll", "--run"]), 2)  # --run needs --site
            with mock.patch.object(cli, "main", side_effect=fake_main):
                self.assertEqual(real_main(["poll", "--run", "--site", s, "--limit", "2", "--work-dir", d]), 0)
            self.assertEqual(sorted(site.published_heads(s)), [5234, 5238])
            self.assertTrue(os.path.exists(os.path.join(s, "index.html")))


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
        self.assertIn("path: .work/cassandra", self.text)
        self.assertIn("%G-W%V", self.text)
        self.assertIn("GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}", self.text)
        self.assertNotIn("secrets.", self.text.replace("secrets.GITHUB_TOKEN", ""))
        self.assertIn("github-actions[bot]", self.text)
        self.assertIn("git push origin HEAD:gh-pages", self.text)
        self.assertIn("bin/cpr poll --run --site site", self.text)
        self.assertNotIn("cpr build", self.text)


if __name__ == "__main__":
    unittest.main()
