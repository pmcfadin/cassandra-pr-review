"""GitHub Pages site build: index of reports plus copies of each report."""

import os
import tempfile
import unittest

from cpr import checks, diffview, model, render, site
from cpr.triage import triage
from tests.helpers import bundle


class Site(unittest.TestCase):
    def test_build_index_and_copies(self):
        with tempfile.TemporaryDirectory() as d:
            b = bundle()
            b["pr"]["title"] = "<script>alert(1)</script> Fix things"
            m = model.build(b, checks.run_all(b), triage(b), render.load_docs(), diffview.unavailable("x"))
            render.write(m, os.path.join(d, "reports", "5198", "index.html"))
            os.makedirs(os.path.join(d, "reports", "junk"))
            with open(os.path.join(d, "reports", "junk", "index.html"), "w") as f:
                f.write("not a report")
            out = os.path.join(d, "site")
            os.makedirs(out)
            rows = site.build(os.path.join(d, "reports"), out)
            self.assertEqual([r["number"] for r in rows], [5198])
            self.assertTrue(os.path.exists(os.path.join(out, "pr", "5198", "index.html")))
            self.assertTrue(os.path.exists(os.path.join(out, ".nojekyll")))
            with open(os.path.join(out, "index.html")) as f:
                page = f.read()
            self.assertTrue(page.startswith("<!doctype html>"))
            self.assertIn('href="pr/5198/"', page)
            self.assertNotIn("<script>alert(1)", page)
            self.assertIn("Requirements met", page)

    def test_read_model_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            b = bundle()
            m = model.build(b, checks.run_all(b), triage(b), render.load_docs(), diffview.unavailable("x"))
            path = render.write(m, os.path.join(d, "r.html"))
            self.assertEqual(site.read_model(path)["pr"]["number"], 5198)


def make_report(path, head=None, review=False, build=False, number=5198):
    b = bundle()
    b["pr"]["number"] = number
    if head:
        b["pr"]["head_sha"] = head
    m = model.build(b, checks.run_all(b), triage(b), render.load_docs(), diffview.unavailable("x"))
    if review:
        m["review"] = {"status": "ran", "complete": True, "lenses": [], "counts": {}}
    if build:
        m["build"] = {**m["build"], "status": "pass"}
    return render.write(m, path)


class Merge(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.addCleanup(self._d.cleanup)
        self.d = self._d.name
        self.site = os.path.join(self.d, "site")
        os.makedirs(self.site)

    def local(self, number=5198, **kw):
        path = make_report(os.path.join(self.d, "reports", str(number), "index.html"), number=number, **kw)
        return os.path.dirname(os.path.dirname(path))

    def put(self, number=5198, **kw):
        make_report(os.path.join(self.site, "pr", str(number), "index.html"), number=number, **kw)

    def published(self, number=5198):
        return site.read_model(os.path.join(self.site, "pr", str(number), "index.html"))

    def test_never_deletes_published_reports_not_local(self):
        self.put(5000)
        rows, actions = site.merge(self.local(5198), self.site)
        self.assertEqual(actions, {5198: "added"})
        self.assertEqual([r["number"] for r in rows], [5198, 5000])
        self.assertTrue(os.path.exists(os.path.join(self.site, "pr", "5000", "index.html")))
        with open(os.path.join(self.site, "index.html")) as f:
            self.assertIn('href="pr/5000/"', f.read())

    def test_richer_published_report_kept_for_same_head(self):
        self.put(review=True)
        _, actions = site.merge(self.local(), self.site)
        self.assertEqual(actions, {5198: "kept"})
        self.assertEqual(self.published()["review"]["status"], "ran")

    def test_published_build_result_counts_as_richer(self):
        self.put(build=True)
        self.assertEqual(site.merge(self.local(), self.site)[1], {5198: "kept"})

    def test_new_head_replaces_richer_report(self):
        self.put(review=True)
        _, actions = site.merge(self.local(head="c" * 40), self.site)
        self.assertEqual(actions, {5198: "replaced"})
        self.assertEqual(self.published()["pr"]["head_sha"], "c" * 40)
        self.assertEqual(self.published()["review"]["status"], "not-run")

    def test_same_head_local_at_least_as_rich_replaces(self):
        self.put(review=True)
        self.assertEqual(site.merge(self.local(review=True), self.site)[1], {5198: "replaced"})

    def test_local_with_build_replaces_plain_published(self):
        self.put()
        self.assertEqual(site.merge(self.local(build=True), self.site)[1], {5198: "replaced"})
        self.assertEqual(self.published()["build"]["status"], "pass")

    def test_same_head_plain_replaces_plain(self):
        self.put()
        self.assertEqual(site.merge(self.local(), self.site)[1], {5198: "replaced"})

    def test_index_shows_review_and_build(self):
        self.put(review=True, build=True)
        site.rebuild_index(self.site)
        with open(os.path.join(self.site, "index.html")) as f:
            page = f.read()
        self.assertIn("code review: 0 blocker", page)
        self.assertIn("build: pass", page)
        self.assertIn("generated ", page)

    def test_published_heads(self):
        self.put(head="d" * 40)
        self.assertEqual(site.published_heads(self.site), {5198: "d" * 40})


if __name__ == "__main__":
    unittest.main()
