"""GitHub Pages site build: index of reports plus copies of each report."""

import os
import re
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
            self.assertIn("Not reviewed yet", page)  # the report's headline words, not the long label
        self.assertNotIn("Requirements met", page)

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


HEX = re.compile(r"#[0-9A-Fa-f]{3,8}\b|rgba?\(")


class DesignTokens(unittest.TestCase):
    def test_no_stray_colors_outside_tokens(self):
        for name, text in (("report template", open(render.TEMPLATE).read()), ("site index", site.index_html([]))):
            body = text.replace(render.tokens_style(), "")
            self.assertEqual(HEX.findall(body), [], name)

    def test_report_and_index_inline_the_same_tokens(self):
        tokens = render.tokens_style()
        self.assertIn("--fail-fg", tokens)
        self.assertIn(tokens, site.index_html([]))
        b = bundle()
        m = model.build(b, checks.run_all(b), triage(b), render.load_docs(), diffview.unavailable("x"))
        with tempfile.TemporaryDirectory() as d:
            page = open(render.write(m, os.path.join(d, "r.html"))).read()
        self.assertIn(tokens, page)
        self.assertNotIn(render.TOKENS_MARKER, page)


def row_for(verdict, mutate=None, number=5198):
    b = bundle()
    b["pr"]["number"] = number
    m = model.build(b, checks.run_all(b), triage(b), render.load_docs(), diffview.unavailable("x"))
    m.pop("view", None)
    if mutate:
        mutate(m)
    return site.summarize(m)


class IndexGroups(unittest.TestCase):
    def test_group_by_who_acts(self):
        self.assertEqual(site._group("draft", "contributor"), "draft")
        self.assertEqual(site._group("unknown", None), "unknown")
        self.assertEqual(site._group("ready", None), "ready")
        self.assertEqual(site._group("waiting", "committer"), "ready")
        self.assertEqual(site._group("blocked", "contributor"), "contributor")
        self.assertEqual(site._group("waiting", "contributor"), "contributor")
        self.assertEqual(site._group("waiting", "reviewer"), "reviewers")
        self.assertEqual(site._group("waiting", None), "reviewers")

    def test_mixed_site_has_a_heading_and_count_per_group(self):
        rows = []
        for n, group in ((1, "draft"), (2, "contributor"), (3, "contributor"), (4, "reviewers")):
            r = row_for(None, number=n)
            r.update(group=group, number=n)
            rows.append(r)
        page = site.index_html(rows)
        self.assertLess(page.index("Waiting on reviewers"), page.index("Waiting on the contributor"))
        self.assertLess(page.index("Waiting on the contributor"), page.index("Drafts"))
        for key, count in (("draft", 1), ("contributor", 2), ("reviewers", 1)):
            sec = page[page.index(f'id="g-{key}"'):]
            sec = sec[:sec.index("</section>")]
            self.assertEqual(sec.count('<li class="item"'), count, key)
            self.assertIn(f'<span class="count">{count}</span>', sec)
        self.assertNotIn('id="g-ready"', page)  # empty groups are left out

    def test_row_uses_the_reports_derived_view(self):
        r = row_for(None)
        self.assertEqual(r["label"], model.derive_view(model.build(bundle(), checks.run_all(bundle()), triage(bundle()), render.load_docs(),
                                                                  diffview.unavailable("x")))["verdict"]["headline"])
        self.assertIn(r["acts"], ("Contributor", "Committer", "Reviewers"))
        self.assertIn(r["effort"].split(" ")[0], ("Small", "Medium", "Large"))
        self.assertIn(" lines in ", r["effort"])

    def test_chips_only_when_review_or_build_ran(self):
        plain = row_for(None)
        self.assertIsNone(plain["review_chip"])
        self.assertIsNone(plain["build_chip"])
        self.assertNotIn("Code review:", site.index_html([plain]))

        def ran(m):
            m["review"] = {"status": "ran", "complete": True, "lenses": [], "counts": {}, "issue_counts": {"blocker": 1, "major": 2}}
            m["build"] = {**m["build"], "status": "tests-failed"}
        r = row_for(None, ran)
        self.assertEqual(r["review_chip"], ("fail", "Code review: 1 blocker, 2 major"))
        self.assertEqual(r["build_chip"], ("fail", "Tests failed"))
        page = site.index_html([r])
        self.assertIn("Code review: 1 blocker, 2 major", page)
        self.assertIn("Tests failed", page)

    def test_newest_first_within_a_group(self):
        a, b = row_for(None, number=10), row_for(None, number=11)
        a.update(group="contributor", generated_at="2026-10-01 10:00 UTC")
        b.update(group="contributor", generated_at="2026-10-02 10:00 UTC")
        page = site.index_html([a, b])
        self.assertLess(page.index('data-pr="11"'), page.index('data-pr="10"'))
        self.assertIn("Updated 2026-10-02", page)
        self.assertNotIn("10:00", page)  # date only


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
        self.assertIn("Code review: no issues", page)
        self.assertIn("Built, tests passed", page)
        self.assertIn("Updated ", page)

    def test_published_heads(self):
        self.put(head="d" * 40)
        self.assertEqual(site.published_heads(self.site), {5198: "d" * 40})


if __name__ == "__main__":
    unittest.main()
