"""Static checks on the rendered report: one self-contained file with no network references."""

import json
import os
import tempfile
import unittest

from cpr import render

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(REPO, "tests", "fixtures", "models", "5201.json")
NETWORK_REFS = ("<script src", "<link href", "@import", "url(http", "fetch(")


class TemplateStaticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(MODEL) as f:
            model = json.load(f)
        with tempfile.TemporaryDirectory() as d:
            path = render.write(model, os.path.join(d, "index.html"))
            with open(path) as f:
                cls.html = f.read()

    def test_starts_with_doctype(self):
        self.assertTrue(self.html.startswith("<!doctype html>"))

    def test_exactly_one_model_script(self):
        self.assertEqual(self.html.count('<script id="report-model">'), 1)
        self.assertEqual(self.html.count("window.REPORT_MODEL = "), 1)
        self.assertNotIn(render.MARKER, self.html)

    def test_no_network_references(self):
        # The embedded diff view is base64, so a plain substring search over the whole file is exact.
        lowered = self.html.lower()
        for ref in NETWORK_REFS:
            self.assertNotIn(ref, lowered, ref)

    def test_template_has_one_marker(self):
        with open(render.TEMPLATE) as f:
            self.assertEqual(f.read().count(render.MARKER), 1)


if __name__ == "__main__":
    unittest.main()
