"""code-review-lenses: panel definition, merge rules, worktree, rendering of findings."""

import json
import os
import subprocess
import tempfile
import unittest

from cpr import diffview, review
from cpr.ingest import clone

PANEL = [{"name": "correctness", "agent": "spec-flow:code-reviewer"},
         {"name": "security", "agent": "spec-flow:security-reviewer"}]


def finding(sev="minor", loc="src/java/A.java:3", fid="f1"):
    return {"id": fid, "severity": sev, "location": loc, "rule": "r", "problem": "p", "fix": "f"}


def lens_out(approve=True, findings=None, summary="ok"):
    return {"summary": summary, "spec_conformance": "full", "tests_ran": "none",
            "tests_detail": "not run: review-only lens", "findings": findings or [], "approve": approve}


class Merge(unittest.TestCase):
    def write(self, d, name, data):
        with open(os.path.join(d, f"{name}.json"), "w") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))

    def test_all_approve(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, "correctness", lens_out())
            self.write(d, "security", lens_out())
            r = review.merge(d, PANEL)
        self.assertTrue(r["complete"] and r["approved"])

    def test_missing_lens(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, "correctness", lens_out())
            r = review.merge(d, PANEL)
        sec = r["lenses"][1]
        self.assertEqual((sec["name"], sec["status"]), ("security", "missing"))
        self.assertFalse(r["complete"])
        self.assertFalse(r["approved"])

    def test_unexplained_non_approval(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, "correctness", lens_out(approve=False, findings=[finding("nit")]))
            self.write(d, "security", lens_out())
            r = review.merge(d, PANEL)
        f = r["lenses"][0]["findings"][0]
        self.assertEqual((f["severity"], f["rule"]), ("major", "unexplained-non-approval"))
        self.assertFalse(r["approved"])

    def test_invalid_output(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, "correctness", "this is not json")
            self.write(d, "security", lens_out(findings=[finding("critical")]))
            r = review.merge(d, PANEL)
        self.assertEqual([l["status"] for l in r["lenses"]], ["invalid", "invalid"])
        self.assertIn("critical", r["lenses"][1]["error"])

    def test_fenced_json_is_accepted_and_findings_sorted(self):
        with tempfile.TemporaryDirectory() as d:
            data = lens_out(approve=False, findings=[finding("nit", fid="a"), finding("blocker", fid="b")])
            self.write(d, "correctness", "Here you go:\n```json\n" + json.dumps(data) + "\n```")
            self.write(d, "security", lens_out())
            r = review.merge(d, PANEL)
        self.assertEqual([f["id"] for f in r["lenses"][0]["findings"]], ["b", "a"])
        self.assertEqual(r["counts"]["blocker"], 1)

    def test_panel_is_data(self):
        self.assertEqual(review.load_panel()[0]["name"], "cassandra-standards")
        with tempfile.TemporaryDirectory() as d:
            panel = PANEL + [{"name": "performance", "agent": "perf-reviewer"}]
            for l in panel:
                self.write(d, l["name"], lens_out())
            r = review.merge(d, panel)
        self.assertEqual(r["lenses"][-1]["name"], "performance")
        self.assertTrue(r["approved"])


class FindingsInDiffView(unittest.TestCase):
    def test_locations_reach_explain_map(self):
        r = {"lenses": [{"name": "correctness", "findings": [
            finding("major", "src/java/org/apache/cassandra/io/sstable/SSTable.java:113"),
            finding("minor", "(correctness lens report)")]}]}
        notes = review.explain_notes(r)
        self.assertEqual(list(notes), ["src/java/org/apache/cassandra/io/sstable/SSTable.java"])
        emap = diffview.explain_map([], notes)
        self.assertIn("[major] correctness", emap["src/java/org/apache/cassandra/io/sstable/SSTable.java"])


class Worktree(unittest.TestCase):
    def test_first_prepare_then_head_moved(self):
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, "repo")
            os.makedirs(repo)

            def git(*a):
                return subprocess.run(["git", "-C", repo, *a], check=True, capture_output=True, text=True).stdout.strip()
            git("init", "-q", "-b", "trunk")
            git("config", "user.email", "t@t")
            git("config", "user.name", "t")
            with open(os.path.join(repo, "a.txt"), "w") as f:
                f.write("one\n")
            git("add", ".")
            git("commit", "-qm", "one")
            first = git("rev-parse", "HEAD")
            with open(os.path.join(repo, "a.txt"), "w") as f:
                f.write("two\n")
            git("commit", "-qam", "two")
            second = git("rev-parse", "HEAD")

            wt = os.path.join(d, "wt", "1")
            self.assertTrue(clone.worktree(repo, wt, 1, first))
            with open(os.path.join(wt, "a.txt")) as f:
                self.assertEqual(f.read(), "one\n")
            self.assertFalse(clone.worktree(repo, wt, 1, second))  # reused, moved
            with open(os.path.join(wt, "a.txt")) as f:
                self.assertEqual(f.read(), "two\n")


if __name__ == "__main__":
    unittest.main()
