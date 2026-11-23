"""PR comment: body, find/create/edit, guards. No test touches GitHub or the network."""

import json
import os
import tempfile
import unittest
from unittest import mock

from cpr import checks, comment, diffview, model, net, render
from cpr.triage import triage
from tests.helpers import SHA, SHA2, bundle

LOGIN = "pmcfadin"
ORIGIN = "git@github.com:pmcfadin/cassandra-pr-review.git"


def setUpModule():
    # The Pages link follows the checkout's origin; pin it so the tests do not depend on where they run.
    for p in (mock.patch.object(comment, "origin_url", lambda: ORIGIN), mock.patch.dict(os.environ)):
        p.start()
        unittest.addModuleCleanup(p.stop)
    os.environ.pop("CPR_PAGES_BASE", None)


def make_model(head=SHA):
    b = bundle()
    b["pr"]["head_sha"] = head
    m = model.build(b, checks.run_all(b), triage(b), render.load_docs(), diffview.unavailable("x"))
    m["pr"]["number"] = 5201
    return m


def page_for(m):
    return f'<script id="report-model">window.REPORT_MODEL = {json.dumps(m)};</script>'


class FakeGh:
    """Stands in for run_gh. Records every call; writes are the ones with -X."""

    def __init__(self, head=SHA, comments=None):
        self.head, self.comments, self.calls = head, comments or [], []

    def __call__(self, args, input=None):
        self.calls.append(list(args))
        if args[:2] == ["api", "user"]:
            return LOGIN + "\n"
        if args[:2] == ["pr", "view"]:
            return json.dumps({"headRefOid": self.head})
        if "-X" in args:
            return json.dumps({"id": 99, "html_url": "https://github.com/apache/cassandra/pull/5201#issuecomment-99"})
        if args[0] == "api" and args[1].endswith("/comments"):
            return json.dumps([self.comments])
        raise AssertionError(f"unexpected gh call {args}")

    def writes(self):
        return [c for c in self.calls if "-X" in c]


class Base(unittest.TestCase):
    def setUp(self):
        self.model = make_model()
        self.gh = FakeGh()
        self.page = page_for(self.model)
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        for target, repl in (("run_gh", lambda *a, **k: self.gh(*a, **k)),
                             ("fetch_page", lambda url: self.page_or_raise(url))):
            p = mock.patch.object(comment, target, repl)
            p.start()
            self.addCleanup(p.stop)

    def page_or_raise(self, url):
        if isinstance(self.page, Exception):
            raise self.page
        return self.page

    def plan(self):
        return comment.plan(5201, self.model)


class Body(unittest.TestCase):
    def test_content(self):
        m = make_model()
        body = comment.build_body(m)
        self.assertTrue(body.startswith(f"<!-- cassandra-pr-review:report pr=5201 head={SHA} -->"))
        self.assertIn(m["recommendation"]["label"], body)
        self.assertIn("triage " + m["triage"]["rating"], body)
        self.assertIn("no code review run", body)
        self.assertIn("https://pmcfadin.github.io/cassandra-pr-review/cassandra/pr/5201/", body)
        self.assertIn("Advisory", body)

    def test_must_fix_count(self):
        m = make_model()
        m["review"] = {"status": "ran", "must_fix": 4, "issue_counts": {"blocker": 0, "major": 4}}
        self.assertIn("4 must-fix issues from the code review panel", comment.build_body(m))

    def test_reasons_capped_at_five_in_order_and_length_capped(self):
        m = make_model()
        m["recommendation"]["reasons"] = [
            {"title": f"Reason {i}", "summary": "x" * 900} for i in range(8)]
        body = comment.build_body(m)
        self.assertLessEqual(len(body), 1500)
        self.assertIn("Reason 4", body)
        self.assertNotIn("Reason 5", body)
        self.assertLess(body.index("Reason 0"), body.index("Reason 1"))
        self.assertIn("…", body)


class PagesBase(unittest.TestCase):
    def base_for(self, origin):
        with mock.patch.object(comment, "origin_url", lambda: origin):
            return comment.pages_base()

    def test_follows_origin(self):
        for origin in ("git@github.com:pmcfadin/cassandra-pr-review.git",
                       "https://github.com/pmcfadin/cassandra-pr-review.git",
                       "https://github.com/pmcfadin/cassandra-pr-review",
                       "ssh://git@github.com/pmcfadin/cassandra-pr-review.git"):
            self.assertEqual(self.base_for(origin), "https://pmcfadin.github.io/cassandra-pr-review", origin)

    def test_fork_links_to_its_own_site(self):
        self.assertEqual(self.base_for("git@github.com:BBotella/cassandra-pr-review.git"),
                         "https://bbotella.github.io/cassandra-pr-review")
        with mock.patch.object(comment, "origin_url", lambda: "git@github.com:bbotella/cassandra-pr-review.git"):
            self.assertIn("https://bbotella.github.io/cassandra-pr-review/cassandra/pr/5201/", comment.build_body(make_model()))

    def test_user_site_repo_is_the_root(self):
        self.assertEqual(self.base_for("git@github.com:someone/someone.github.io.git"), "https://someone.github.io")

    def test_env_overrides(self):
        with mock.patch.dict(os.environ, {"CPR_PAGES_BASE": "https://reviews.example.org/"}):
            self.assertEqual(self.base_for(None), "https://reviews.example.org")

    def test_unknown_origin_refuses(self):
        for origin in (None, "git@gitlab.com:someone/cassandra-pr-review.git"):
            with self.assertRaises(comment.CommentError):
                self.base_for(origin)


class Plan(Base):
    def test_dry_run_makes_no_write(self):
        p = self.plan()
        self.assertEqual(p["action"], "create")
        self.assertEqual(p["problems"], [])
        self.assertIn("Would create", comment.describe(p))
        self.assertEqual(self.gh.writes(), [])

    def test_finds_own_comment_only(self):
        mk = comment.marker(5201, SHA2)
        self.gh.comments = [
            {"id": 1, "user": {"login": "someone"}, "body": mk + "\nspoof"},
            {"id": 2, "user": {"login": LOGIN}, "body": "unrelated"},
            {"id": 3, "user": {"login": LOGIN}, "body": mk + "\nold"},
        ]
        p = self.plan()
        self.assertEqual((p["action"], p["existing"]["id"]), ("edit", 3))

    def test_unchanged_does_not_write(self):
        self.gh.comments = [{"id": 3, "user": {"login": LOGIN}, "body": comment.build_body(self.model)}]
        p = self.plan()
        self.assertEqual(p["action"], "unchanged")
        res = comment.post(p, self.work.name, yes=True, is_tty=False)
        self.assertEqual(res["action"], "unchanged")
        self.assertEqual(self.gh.writes(), [])

    def test_stale_local_report(self):
        self.gh.head = SHA2
        p = self.plan()
        self.assertTrue(any("re-run cpr review" in x for x in p["problems"]))
        with self.assertRaises(comment.CommentError):
            comment.post(p, self.work.name, yes=True)
        self.assertEqual(self.gh.writes(), [])

    def test_pages_behind(self):
        self.page = page_for(make_model(SHA2))
        p = self.plan()
        self.assertTrue(any("publish first: run bin/publish-pages" in x for x in p["problems"]))
        with self.assertRaises(comment.CommentError):
            comment.post(p, self.work.name, yes=True)

    def test_pages_missing(self):
        self.page = net.NetError("HTTP 404", status=404)
        self.assertTrue(any("publish first" in x for x in self.plan()["problems"]))

    def test_no_reasons(self):
        self.model["recommendation"]["reasons"] = []
        self.assertTrue(any("no reasons" in x for x in self.plan()["problems"]))

    def test_sidecar_links_and_posts_to_its_own_repo(self):
        from tests.helpers import sidecar_bundle
        b = sidecar_bundle()
        b["pr"]["head_sha"] = SHA
        m = model.build(b, checks.run_all(b), triage(b), render.load_docs(), diffview.unavailable("x"))
        self.page = page_for(m)
        urls = []
        with mock.patch.object(comment, "fetch_page", lambda url: urls.append(url) or self.page):
            p = comment.plan(397, m)
        self.assertEqual((p["repo"], p["slug"]), ("apache/cassandra-sidecar", "sidecar"))
        self.assertIn("https://pmcfadin.github.io/cassandra-pr-review/sidecar/pr/397/", p["body"])
        self.assertEqual(urls, ["https://pmcfadin.github.io/cassandra-pr-review/sidecar/pr/397/"])
        self.assertIn(["pr", "view", "397", "-R", "apache/cassandra-sidecar", "--json", "headRefOid"], self.gh.calls)
        self.assertTrue(any(c[:2] == ["api", "repos/apache/cassandra-sidecar/issues/397/comments"] for c in self.gh.calls))


class Post(Base):
    def test_first_post_creates_and_records(self):
        p = self.plan()
        res = comment.post(p, self.work.name, yes=True, is_tty=False)
        w = self.gh.writes()
        self.assertEqual(len(w), 1)
        self.assertEqual(w[0][:3], ["api", "-X", "POST"])
        self.assertEqual(res["comment_id"], 99)
        with open(comment.comment_json_path(self.work.name, "cassandra", 5201)) as f:
            rec = json.load(f)
        self.assertEqual((rec["comment_id"], rec["head"]), (99, SHA))
        self.assertIn("posted_at", rec)

    def test_edit_on_new_head(self):
        self.gh.comments = [{"id": 3, "user": {"login": LOGIN}, "body": comment.marker(5201, SHA2) + "\nold"}]
        comment.post(self.plan(), self.work.name, yes=True, is_tty=False)
        w = self.gh.writes()
        self.assertEqual(len(w), 1)
        self.assertEqual(w[0][:3], ["api", "-X", "PATCH"])
        self.assertTrue(w[0][3].endswith("/issues/comments/3"))

    def test_no_tty_without_yes_refused(self):
        with self.assertRaisesRegex(comment.CommentError, "--yes"):
            comment.post(self.plan(), self.work.name, yes=False, is_tty=False)
        self.assertEqual(self.gh.writes(), [])

    def test_tty_prompt(self):
        asked = []

        def no(prompt):
            asked.append(prompt)
            return "n"

        with self.assertRaises(comment.CommentError):
            comment.post(self.plan(), self.work.name, is_tty=True, ask=no)
        self.assertEqual(asked, ["Post to apache/cassandra #5201 as pmcfadin? [y/N] "])
        self.assertEqual(self.gh.writes(), [])
        comment.post(self.plan(), self.work.name, is_tty=True, ask=lambda _: "y")
        self.assertEqual(len(self.gh.writes()), 1)


class Paginate(unittest.TestCase):
    def test_concatenated_and_slurped_pages(self):
        a, b = [{"id": 1}], [{"id": 2}]
        flat = lambda t: [c for v in comment._json_values(t) for c in comment._flatten(v)]  # noqa: E731
        self.assertEqual(flat(json.dumps(a) + json.dumps(b)), a + b)
        self.assertEqual(flat(json.dumps([a, b])), a + b)


if __name__ == "__main__":
    unittest.main()
