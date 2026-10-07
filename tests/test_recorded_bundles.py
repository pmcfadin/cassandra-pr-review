"""Regression tests over bundles recorded from real apache/cassandra PRs (2026-10-07)."""

import gzip
import json
import os
import unittest

from cpr import checks, diffview, model, render
from cpr.recommend import recommend
from cpr.triage import triage

DIR = os.path.join(os.path.dirname(__file__), "fixtures", "bundles")


def load(name):
    with gzip.open(os.path.join(DIR, name), "rt") as f:
        return json.load(f)


def status(results, check_id):
    return next(r["status"] for r in results if r["id"] == check_id)


class RecordedBundles(unittest.TestCase):
    def test_backport_set(self):
        b = load("5201-backport-set.json.gz")
        res = checks.run_all(b)
        self.assertEqual({s["base"] for s in b["siblings"]},
                         {"cassandra-4.0", "cassandra-4.1", "cassandra-5.0", "cassandra-6.0", "trunk"})
        self.assertEqual(status(res, "ci.evidence"), "fail")  # only 5.0 has CI attached
        self.assertEqual(status(res, "static.banned-api"), "not-applicable")  # 4.0 has no checkstyle.xml
        self.assertEqual(recommend(b["pr"], res)["verdict"], "needs-contributor-work")  # no tests

    def test_no_jira(self):
        b = load("5212-no-jira.json.gz")
        res = checks.run_all(b)
        self.assertIsNone(b["jira_key"]["key"])
        self.assertEqual(status(res, "jira.key-present"), "fail")
        self.assertEqual(status(res, "ci.evidence"), "unknown")
        self.assertEqual(triage(b)["rating"], "moderate")  # 12 lines across 9 files

    def test_draft(self):
        b = load("5238-draft.json.gz")
        self.assertEqual(recommend(b["pr"], checks.run_all(b))["verdict"], "draft")

    def test_huge(self):
        b = load("4967-huge.json.gz")
        t = triage(b)
        self.assertEqual(t["rating"], "hard")
        self.assertIsNotNone(t["split_suggestion"])

    def test_stale_ci(self):
        b = load("5228-stale-ci.json.gz")
        res = checks.run_all(b)
        self.assertEqual(status(res, "ci.freshness"), "warn")
        self.assertEqual(status(res, "jira.not-resolved"), "warn")

    def test_every_bundle_renders(self):
        for name in sorted(os.listdir(DIR)):
            with self.subTest(name):
                b = load(name)
                res = checks.run_all(b)
                m = model.build(b, res, triage(b), render.load_docs(), diffview.unavailable("fixture"))
                self.assertTrue(render.render_html(m).startswith("<!doctype html>"))


if __name__ == "__main__":
    unittest.main()


class RecordedContext(unittest.TestCase):
    """reviewer-context on real history recorded 2026-10-07."""

    def test_backport_tickets_and_trunk_experts(self):
        from cpr import context
        c = context.build(load("5201-backport-set.json.gz"))
        self.assertEqual(c["related_tickets"][0]["key"], "CASSANDRA-2468")  # "Clean up after failed compaction"
        self.assertEqual(set(c["experts_from"].values()), {"trunk"})
        self.assertIn("Caleb Rackliffe", [p["name"] for p in c["already_reviewing"]])  # commented on the ticket

    def test_huge_pr_is_bounded(self):
        from cpr import context
        b = context.build(load("4967-huge.json.gz"))["budget"]
        self.assertEqual((b["hunks_blamed"], b["files_logged"]), (300, 25))
        self.assertGreater(b["hunks_skipped"], 0)

    def test_pr_opener_is_never_suggested(self):
        from cpr import context
        c = context.build(load("5228-stale-ci.json.gz"))  # opened by maedhroz for another author's patch
        names = [p["name"] for p in c["suggested_reviewers"] + c["already_reviewing"]]
        self.assertNotIn("Caleb Rackliffe", names)
