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


if __name__ == "__main__":
    unittest.main()
