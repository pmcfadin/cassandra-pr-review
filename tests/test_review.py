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


class SeverityFromImpact(unittest.TestCase):
    def merged(self, **extra):
        with tempfile.TemporaryDirectory() as d:
            for name in ("correctness", "security"):
                data = lens_out(approve=name != "correctness",
                                findings=[dict(finding("blocker"), **extra)] if name == "correctness" else [])
                with open(os.path.join(d, f"{name}.json"), "w") as fh:
                    json.dump(data, fh)
            return review.merge(d, PANEL)

    def test_severity_follows_the_table(self):
        r = self.merged(impact="data-loss", confidence="medium")
        f = r["lenses"][0]["findings"][0]
        self.assertEqual(f["severity"], "major")
        self.assertEqual(f["severity_corrected"], {"from": "blocker", "to": "major"})

    def test_whole_table(self):
        expect = {"data-loss": "blocker major minor", "crash": "blocker major minor", "hang": "blocker major minor",
                  "mixed-version-break": "blocker major minor", "silent-wrong-result": "major major minor",
                  "performance": "minor minor nit", "cosmetic": "nit nit nit"}
        for impact, sevs in expect.items():
            for conf, sev in zip(("high", "medium", "low"), sevs.split()):
                got = review.derive_severity(dict(finding("major"), impact=impact, confidence=conf))
                self.assertEqual(got["severity"], sev, (impact, conf))

    def test_agreeing_severity_is_not_marked_and_no_impact_keeps_severity(self):
        f = review.derive_severity(dict(finding("blocker"), impact="crash", confidence="high"))
        self.assertNotIn("severity_corrected", f)
        self.assertEqual(review.derive_severity(finding("nit"))["severity"], "nit")

    def test_invalid_impact_or_confidence_rejected(self):
        self.assertIn("impact", review.validate_output(lens_out(findings=[dict(finding(), impact="meh")])))
        self.assertIn("confidence", review.validate_output(lens_out(findings=[dict(finding(), confidence="sure")])))
        self.assertIsNone(review.validate_output(lens_out(findings=[dict(finding(), impact="crash", confidence="low")])))


class Issues(unittest.TestCase):
    def test_merge_adds_issues_counts_and_checklists(self):
        with tempfile.TemporaryDirectory() as d:
            lens_dir = os.path.join(d, "lenses")
            os.makedirs(lens_dir)
            same = dict(problem="FileUtils.delete swallows failedDeletions silently", fix="Use deleteWithConfirm")
            for name, sev in (("correctness", "major"), ("security", "blocker")):
                with open(os.path.join(lens_dir, f"{name}.json"), "w") as fh:
                    json.dump(lens_out(approve=False, findings=[dict(finding(sev, "src/java/A.java:5", name), **same)]), fh)
            self.assertIsNone(review.merge(lens_dir, PANEL)["checklists"])
            with open(os.path.join(d, "lens-plan.json"), "w") as fh:
                json.dump({"checklists": {"sha": "0123456789abcdef"}}, fh)
            r = review.merge(lens_dir, PANEL)
        self.assertEqual(r["counts"]["blocker"] + r["counts"]["major"], 2)  # per finding
        self.assertEqual(len(r["issues"]), 1)
        self.assertEqual((r["must_fix"], r["issue_counts"]["blocker"]), (1, 1))
        self.assertEqual(r["checklists"], {"sha": "0123456789abcdef"})
        self.assertFalse(r["approved"])


class FindingsInDiffView(unittest.TestCase):
    def test_issue_reported_by_two_lenses_appears_once(self):
        loc = "src/java/org/apache/cassandra/io/sstable/SSTable.java:121"
        same = dict(problem="FileUtils.delete swallows failedDeletions silently", fix="Use deleteWithConfirm")
        r = {"lenses": [
            {"name": "cass-logic-boundary", "findings": [dict(finding("major", loc, "a"), **same)]},
            {"name": "cass-persistence-compat", "findings": [dict(finding("major", loc, "b"), **same)]}]}
        notes = review.explain_notes(r)
        lines = notes["src/java/org/apache/cassandra/io/sstable/SSTable.java"]
        self.assertEqual(len(lines), 1)
        self.assertIn("cass-logic-boundary, cass-persistence-compat", lines[0])
        self.assertIn(loc, lines[0])
        self.assertTrue(lines[0].startswith("- **[major] cass-logic-boundary, cass-persistence-compat: r**"))

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


class PlanMissing(unittest.TestCase):
    def test_missing_checklist_named(self):
        with tempfile.TemporaryDirectory() as d:
            lens_dir = os.path.join(d, "lenses")
            os.makedirs(lens_dir)
            with open(os.path.join(d, "lens-plan.json"), "w") as f:
                json.dump({"checklists": {"sha": "abc123"}, "lenses": {"security": {
                    "status": "missing", "error": "checklist missing at trunk: x/logic.md"}}}, f)
            with open(os.path.join(lens_dir, "correctness.json"), "w") as f:
                json.dump(lens_out(), f)
            r = review.merge(lens_dir, PANEL)
        sec = r["lenses"][1]
        self.assertEqual(sec["status"], "missing")
        self.assertIn("x/logic.md", sec["error"])
        self.assertFalse(r["approved"])
        self.assertEqual(r["checklists"], {"sha": "abc123"})
