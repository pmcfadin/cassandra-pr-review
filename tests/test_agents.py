"""Lens agent prompts must be well formed and stay independent of spec-flow (spec: code-review-lenses)."""

import glob
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS = os.path.join(ROOT, ".claude", "agents")
STANDARDS = os.path.join(AGENTS, "cassandra-standards-reviewer.md")
IMPACTS = ("data-loss", "crash", "hang", "mixed-version-break", "silent-wrong-result", "performance", "cosmetic")


def cass_lenses():
    return sorted(glob.glob(os.path.join(AGENTS, "cass-*.md")))


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def front_matter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return None
    fields = {}
    for line in m.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


class AgentPromptsTest(unittest.TestCase):
    def all_paths(self):
        return cass_lenses() + [STANDARDS]

    def test_five_cass_lenses_exist(self):
        names = {os.path.basename(p)[:-3] for p in cass_lenses()}
        self.assertEqual(names, {"cass-logic-boundary", "cass-concurrency-lifecycle", "cass-persistence-compat",
                                 "cass-completeness-symmetry", "cass-test-regime"})

    def test_front_matter_valid(self):
        for path in self.all_paths():
            with self.subTest(path=path):
                fm = front_matter(read(path))
                self.assertIsNotNone(fm, "missing front matter")
                self.assertEqual(fm.get("name"), os.path.basename(path)[:-3])
                self.assertTrue(fm.get("description"))
                self.assertEqual(fm.get("tools"), "Read, Bash, Grep, Glob")

    def test_severity_table_and_fields(self):
        for path in self.all_paths():
            text = read(path)
            with self.subTest(path=path):
                for impact in IMPACTS:
                    self.assertIn(impact, text)
                self.assertIn('"impact"', text)
                self.assertIn('"confidence"', text)
                self.assertIn("blocker", text)

    def test_cass_lenses_use_refdir(self):
        for path in cass_lenses():
            with self.subTest(path=path):
                text = read(path)
                self.assertIn("refdir", text)
                self.assertIn("bundle", text)
                self.assertIn("review-steering", text)

    def test_no_spec_flow_references(self):
        for path in self.all_paths():
            with self.subTest(path=path):
                text = read(path).lower()
                self.assertNotIn("spec-flow", text)
                self.assertNotIn("spec_flow", text)
                self.assertNotIn("specflow", text)

    def test_standards_reviewer_security_and_config_edit(self):
        text = read(STANDARDS)
        self.assertIn("system_views", text)
        self.assertIn("virtual table", text)
        self.assertIn("review-config-edit", text)
        self.assertIn("security-", text)


if __name__ == "__main__":
    unittest.main()


class Panel(unittest.TestCase):
    """The default panel is data and needs no spec-flow plugin (spec: code-review-lenses, Lens panel)."""

    def setUp(self):
        from cpr import review
        self.panel = review.load_panel()

    def test_six_cassandra_lenses(self):
        self.assertEqual([l["name"] for l in self.panel],
                         ["cassandra-standards", "cass-logic-boundary", "cass-concurrency-lifecycle",
                          "cass-persistence-compat", "cass-completeness-symmetry", "cass-test-regime"])

    def test_no_spec_flow_dependency(self):
        for lens in self.panel:
            self.assertNotIn(":", lens["agent"], f"{lens['name']} uses a plugin agent")
            self.assertTrue(os.path.exists(os.path.join(AGENTS, lens["agent"] + ".md")),
                            f"no project agent file for {lens['agent']}")
        skill = read(os.path.join(ROOT, ".claude", "skills", "review-pr", "SKILL.md"))
        self.assertNotIn("spec-flow:", skill)

    def test_panel_is_data(self):
        skill = read(os.path.join(ROOT, ".claude", "skills", "review-pr", "SKILL.md"))
        for key in ("refdir", "bundle", "tier", "panel.json"):
            self.assertIn(key, skill)
        from cpr import lenses
        configured = set(lenses.load_config()["lenses"])
        for lens in self.panel:
            self.assertIn(lens["name"], configured, f"{lens['name']} has no checklist bundle in lenses.json")


class PanelModel(unittest.TestCase):
    """Owner decision 2026-10-07: every panel lens runs on Sonnet (see benchmark.md, Haiku 5.5 quick loop)."""

    def test_lenses_pinned_to_sonnet(self):
        from cpr import review
        for lens in review.load_panel():
            fm = front_matter(read(os.path.join(AGENTS, lens["agent"] + ".md")))
            self.assertEqual(fm.get("model"), "sonnet", lens["agent"])
