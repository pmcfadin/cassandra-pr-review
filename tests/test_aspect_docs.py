"""Aspect docs and checks must not drift apart (spec: "Aspect documentation", design D10)."""

import os
import re
import unittest

from cpr.checks import registered_ids
from cpr.model import ASPECTS

DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "report")
REQUIRED_HEADINGS = ("What is checked", "Why", "How each status is decided", "How to fix", "Limits")


def doc_path(aspect):
    return os.path.join(DOCS_DIR, f"{aspect}.md")


def read_doc(aspect):
    with open(doc_path(aspect), encoding="utf-8") as f:
        return f.read()


def h2_headings(text):
    return [m.group(1).strip() for m in re.finditer(r"^## (.+)$", text, re.MULTILINE)]


class AspectDocsTest(unittest.TestCase):
    def test_every_aspect_has_a_doc(self):
        missing = [a for a in ASPECTS if not os.path.isfile(doc_path(a))]
        self.assertEqual(missing, [], f"aspects without a doc under {DOCS_DIR}")

    def test_every_check_aspect_is_a_known_aspect(self):
        unknown = sorted({a for _, a in registered_ids() if a not in ASPECTS})
        self.assertEqual(unknown, [], "checks name aspects that no report section embeds")

    def test_every_check_id_is_documented_in_its_aspect_doc(self):
        missing = []
        for check_id, aspect in registered_ids():
            if not os.path.isfile(doc_path(aspect)):
                missing.append(f"{check_id} (no {aspect}.md)")
                continue
            if f"### `{check_id}`" not in read_doc(aspect):
                missing.append(f"{check_id} (no '### `{check_id}`' entry in {aspect}.md)")
        self.assertEqual(missing, [])

    def test_every_doc_has_the_outline(self):
        problems = []
        for aspect in ASPECTS:
            if not os.path.isfile(doc_path(aspect)):
                continue
            text = read_doc(aspect)
            if not text.startswith("# "):
                problems.append(f"{aspect}.md: does not start with a '# ' title")
            headings = h2_headings(text)
            absent = [h for h in REQUIRED_HEADINGS if h not in headings]
            if absent:
                problems.append(f"{aspect}.md: missing ## {', ## '.join(absent)}")
            elif [h for h in headings if h in REQUIRED_HEADINGS] != list(REQUIRED_HEADINGS):
                problems.append(f"{aspect}.md: ## headings out of order: {headings}")
            if "TODO" in text:
                problems.append(f"{aspect}.md: still contains TODO")
        self.assertEqual(problems, [])


class ProjectDocsTest(unittest.TestCase):
    """A project's own docs (`docs_dir` in its profile) follow the same rules as the shared ones."""

    def test_project_docs(self):
        from cpr import project
        problems = []
        for d in sorted({project.load(s).docs_dir for s in project.slugs()} - {None}):
            directory = os.path.join(DOCS_DIR, d)
            self.assertTrue(os.path.isdir(directory), directory)
            for name in sorted(os.listdir(directory)):
                aspect = name[:-3]
                if not name.endswith(".md"):
                    continue
                if aspect not in ASPECTS:
                    problems.append(f"{d}/{name}: not a report aspect")
                    continue
                with open(os.path.join(directory, name), encoding="utf-8") as f:
                    text = f.read()
                headings = [h for h in h2_headings(text) if h in REQUIRED_HEADINGS]
                if not text.startswith("# ") or headings != list(REQUIRED_HEADINGS) or "TODO" in text:
                    problems.append(f"{d}/{name}: outline (title, {', '.join(REQUIRED_HEADINGS)}) or TODO")
                for check_id, a in registered_ids():
                    if a == aspect and f"### `{check_id}`" not in text:
                        problems.append(f"{d}/{name}: no '### `{check_id}`' entry")
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
