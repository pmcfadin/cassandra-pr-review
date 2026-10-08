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
        cls.model = model
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
        # Search the markup outside the model payload. The payload is JSON data (docs may mention
        # `@import` as text, which is harmless) and the embedded diff view inside it is base64.
        start = self.html.index('<script id="report-model">')
        end = self.html.index("</script>", start)
        lowered = (self.html[:start] + self.html[end:]).lower()
        for ref in NETWORK_REFS:
            self.assertNotIn(ref, lowered, ref)

    def test_code_review_leads_with_issues_then_lens_detail(self):
        with open(render.TEMPLATE) as f:
            tpl = f.read()
        body = tpl[tpl.index("function renderReview()"):]
        self.assertLess(body.index('block("Issues"'), body.index("Per-lens detail"))
        # Data-driven: lenses, chips and statuses come from the model, not from names in the template.
        for name in ("cassandra-standards", "cass-logic-boundary", "cass-test-regime"):
            self.assertNotIn(name, tpl)

    def test_template_names_the_checklist_version_and_headline(self):
        with open(render.TEMPLATE) as f:
            tpl = f.read()
        self.assertIn("checklists: apache/cassandra trunk @ ", tpl)
        self.assertIn('plural(findings, "finding")', tpl)

    def test_model_with_issues_validates_and_a_bad_issue_does_not(self):
        from cpr import model as model_mod
        m = json.loads(json.dumps(self.model))
        self.assertEqual(len(m["review"]["issues"]), 5)
        model_mod.validate(m)
        m["review"]["issues"][0]["severity"] = "huge"
        with self.assertRaises(model_mod.ModelError):
            model_mod.validate(m)

    def test_fonts_are_embedded(self):
        for family in ("Red Hat Text", "Red Hat Mono"):
            self.assertIn(f'@font-face{{font-family:"{family}"', self.html)
        self.assertEqual(self.html.count("src:url(data:font/woff2;base64,"), len(render.FONTS))
        self.assertNotIn(render.FONT_MARKER, self.html)

    def test_missing_font_files_fall_back_to_system_fonts(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(render.font_faces(d), "")

    def test_template_has_one_marker(self):
        with open(render.TEMPLATE) as f:
            self.assertEqual(f.read().count(render.MARKER), 1)


if __name__ == "__main__":
    unittest.main()
