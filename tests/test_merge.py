"""code-review-lenses: merging duplicate findings across lenses (cpr/merge.py)."""

import json
import os
import unittest

from cpr import merge, review

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LENSES_5201 = os.path.join(REPO, "tests", "fixtures", "lenses", "5201")
OLD_PANEL = [{"name": n, "agent": n} for n in
             ("cassandra-standards", "correctness", "test-rigor", "observability", "security")]


def f(lens, fid, loc, problem, fix, severity="major", **extra):
    return dict({"lens": lens, "id": fid, "severity": severity, "location": loc, "rule": "r",
                 "problem": problem, "fix": fix}, **extra)


class Pr5201Regression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = review.merge(LENSES_5201, OLD_PANEL)

    def test_eleven_findings_become_five_issues_three_must_fix(self):
        self.assertEqual(sum(self.result["counts"].values()), 11)
        self.assertEqual(len(self.result["issues"]), 5)
        self.assertEqual(self.result["must_fix"], 3)
        self.assertEqual(self.result["issue_counts"], {"blocker": 1, "major": 2, "minor": 2, "nit": 0})

    def test_silent_delete_issue_names_all_four_lenses(self):
        issue = self.result["issues"][0]
        self.assertEqual(issue["severity"], "blocker")  # highest member severity
        self.assertEqual(sorted(issue["lenses"]),
                         ["cassandra-standards", "correctness", "observability", "test-rigor"])
        self.assertEqual(sorted(m["id"] for m in issue["members"]), ["C2", "OBS-1", "TR-3", "cs-1"])
        self.assertEqual(issue["location"], "src/java/org/apache/cassandra/io/sstable/SSTable.java:121")
        self.assertEqual(issue["severity_spread"], ["blocker", "major", "major", "major"])

    def test_membership_matches_hand_clustering(self):
        groups = sorted(sorted(m["id"] for m in i["members"]) for i in self.result["issues"])
        self.assertEqual(groups, sorted([["C2", "OBS-1", "TR-3", "cs-1"], ["C1", "TR-2", "cs-2"],
                                         ["TR-1", "cs-3"], ["cs-4"], ["cs-5"]]))

    def test_same_line_comment_nit_and_missing_test_stay_apart(self):
        by_member = {m["id"]: i["id"] for i in self.result["issues"] for m in i["members"]}
        self.assertNotEqual(by_member["cs-4"], by_member["TR-1"])

    def test_issue_keeps_every_location_and_differing_fixes(self):
        test_gap = next(i for i in self.result["issues"] if {"cs-3", "TR-1"} == {m["id"] for m in i["members"]})
        self.assertEqual(sorted(test_gap["locations"]),
                         ["src/java/org/apache/cassandra/io/sstable/SSTable.java:113", "ticket"])
        self.assertEqual(len(test_gap["also_fixes"]), 1)
        self.assertNotEqual(test_gap["also_fixes"][0]["fix"], test_gap["fix"])


class Rules(unittest.TestCase):
    def test_same_line_different_issue_stays_separate(self):
        a = f("logic", "a", "src/A.java:10", "Iterator leaks when close() is skipped on the error path",
              "Wrap the iterator in try-with-resources")
        b = f("compat", "b", "src/A.java:10", "Serialization format version missing for new column",
              "Bump MessagingService version constant")
        self.assertEqual(len(merge.merge_findings([a, b])), 2)

    def test_same_lens_findings_never_merge(self):
        text = dict(problem="FileUtils.delete swallows failedDeletions silently", fix="Use deleteWithConfirm")
        a = f("logic", "a", "src/A.java:10", **text)
        b = f("logic", "b", "src/A.java:10", **text)
        self.assertEqual(len(merge.merge_findings([a, b])), 2)
        c = f("compat", "c", "src/A.java:11", **text)
        issues = merge.merge_findings([a, b, c])
        self.assertEqual(len(issues), 2)  # c joins one of them, never both
        self.assertTrue(all(len(set(i["lenses"])) == len(i["members"]) for i in issues))

    def test_primary_is_highest_severity_and_impact_comes_from_it(self):
        text = dict(problem="FileUtils.delete swallows failedDeletions silently", fix="Use deleteWithConfirm")
        a = f("logic", "a", "src/A.java:10", severity="major", impact="silent-wrong-result", confidence="high", **text)
        b = f("compat", "b", "src/A.java:10", severity="blocker", impact="data-loss", confidence="high",
              problem=text["problem"], fix="Restore the retry in SSTableTidier")
        (issue,) = merge.merge_findings([a, b])
        self.assertEqual((issue["severity"], issue["impact"], issue["members"][0]["id"]), ("blocker", "data-loss", "b"))
        self.assertEqual(issue["also_fixes"], [{"lens": "logic", "fix": "Use deleteWithConfirm"}])

    def test_issue_keeps_the_primary_findings_title(self):
        a = f("correctness", "c1", "src/A.java:10", "FileUtils.deleteWithConfirm swallows the error", "call FileUtils.deleteWithConfirm",
              severity="major", title="Keep deleteWithConfirm in SSTable")
        b = f("observability", "o1", "src/A.java:11", "FileUtils.deleteWithConfirm swallows the error", "call FileUtils.deleteWithConfirm",
              severity="minor", title="Other title")
        issues = merge.merge_findings([a, b])
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["title"], "Keep deleteWithConfirm in SSTable")

    def test_issue_without_a_title_has_no_title_key(self):
        issues = merge.merge_findings([f("correctness", "c1", "src/A.java:10", "p one", "fix one")])
        self.assertNotIn("title", issues[0])

    def test_constants_live_in_config(self):
        with open(merge.CONFIG) as fh:
            cfg = json.load(fh)
        self.assertEqual((cfg["text_floor"], cfg["merge_threshold"]), (0.18, 0.40))


if __name__ == "__main__":
    unittest.main()
