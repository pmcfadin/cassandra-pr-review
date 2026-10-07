"""bench: known-issue cases load and are self-describing; the cut-off context leaks nothing later."""

import copy
import json
import os
import tempfile
import unittest
from unittest import mock

from cpr import bench
from tests.helpers import bundle, ticket

CUTOFF = "2026-02-04"
FIX_KEY = "CASSANDRA-21671"


def link(key, relation="relates to"):
    return {"relation": relation, "key": key, "summary": f"summary of {key}", "status": "Resolved",
            "url": f"https://issues.apache.org/jira/browse/{key}"}


def comment(cid, created, body):
    return {"id": cid, "author": "bob", "display": "Bob", "created": created, "body": body, "url": f"u{cid}"}


def case(**kw):
    c = {"id": "BX-1", "title": "t", "repo": "apache/cassandra", "pr": 1, "base_sha": "a" * 40, "head_sha": "b" * 40,
         "ticket": "CASSANDRA-19987", "cutoff": CUTOFF, "notes": "n",
         "known_issues": [{"id": "K1", "source": "https://issues.apache.org/jira/browse/CASSANDRA-1", "severity": "major",
                           "hard": True, "files": ["a.java"], "lines": [1, 5], "match_terms": ["leak"]}]}
    c.update(kw)
    return c


def history(created, to_string, from_string=None):
    return {"created": created, "items": [{"field": "Link", "fromString": from_string, "toString": to_string}]}


def late_ticket():
    return ticket(
        key="CASSANDRA-19987", summary="Direct IO", status="Resolved", resolution="Fixed", fix_versions=["6.0"],
        since_versions=["6.0"], source_control_link="https://github.com/apache/cassandra/commit/6f5fe8c",
        comments=[comment("1", "2026-01-10T10:00:00.000+0000", "early comment"),
                  comment("2", "2026-02-04T23:59:00.000+0000", "same day comment"),
                  comment("3", "2026-09-09T10:00:00.000+0000", f"see {FIX_KEY}, the leak")],
        issuelinks=[link("CASSANDRA-14466", "is a child of"), link(FIX_KEY)],
        remotelinks=[{"url": "https://github.com/apache/cassandra/pull/5168", "title": "fix"}],
        attachments=[{"id": "1", "filename": "early.patch", "created": "2026-01-01T00:00:00.000+0000"},
                     {"id": "2", "filename": "late.patch", "created": "2026-09-10T00:00:00.000+0000"}])


class CaseFiles(unittest.TestCase):
    def test_all_six_research_cases_load(self):
        cases = bench.load_cases()
        self.assertEqual([c["id"].split("-")[0] for c in cases], ["B1", "B2", "B3", "B4", "B5", "B6"])
        for c in cases:
            self.assertEqual(c["repo"], "apache/cassandra")
            for issue in c["known_issues"]:
                self.assertTrue(issue["source"].startswith("https://"), (c["id"], issue["id"]))
                self.assertTrue(issue["match_terms"], (c["id"], issue["id"]))

    def test_filename_matches_id(self):
        for name in os.listdir(bench.CASES_DIR):
            self.assertEqual(bench.load_case(os.path.join(bench.CASES_DIR, name))["id"] + ".json", name)

    def test_quick_loop_cases_have_their_real_inputs(self):
        b3, b6 = bench.find_cases("B3")[0], bench.find_cases("B6")[0]
        self.assertEqual((b3["pr"], b3["ticket"]), (4887, "CASSANDRA-21113"))
        self.assertIn("$$", b3["known_issues"][0]["match_terms"])
        self.assertEqual((b6["pr"], b6["head_sha"]), (5201, "d1095cbdca4173277488e6e93abeb06a35ea0bb8"))

    def test_shas_are_full_or_null(self):
        for c in bench.load_cases():
            for k in ("base_sha", "head_sha"):
                self.assertTrue(c[k] is None or len(c[k]) == 40, (c["id"], k))

    def test_find_cases_by_short_id_and_all(self):
        self.assertEqual(len(bench.find_cases("all")), 6)
        self.assertEqual(bench.find_cases("B1")[0]["id"], "B1-19987")
        with self.assertRaises(bench.CaseError):
            bench.find_cases("B9")

    def _load(self, c):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.json")
            with open(p, "w") as f:
                json.dump(c, f)
            return bench.load_case(p)

    def test_issue_without_source_names_case_and_issue(self):
        c = case()
        c["known_issues"][0]["source"] = ""
        with self.assertRaises(ValueError) as cm:
            self._load(c)
        self.assertIn("BX-1", str(cm.exception))
        self.assertIn("K1", str(cm.exception))
        self.assertIn("source", str(cm.exception))

    def test_issue_without_match_terms_names_the_issue(self):
        c = case()
        c["known_issues"].append({**copy.deepcopy(c["known_issues"][0]), "id": "K2", "match_terms": []})
        with self.assertRaises(ValueError) as cm:
            self._load(c)
        self.assertIn("K2", str(cm.exception))
        self.assertIn("match_terms", str(cm.exception))

    def test_valid_case_loads(self):
        self.assertEqual(self._load(case())["id"], "BX-1")

    def test_bad_cutoff_and_missing_field(self):
        with self.assertRaises(ValueError):
            self._load(case(cutoff="June 2026"))
        c = case()
        del c["ticket"]
        with self.assertRaises(ValueError) as cm:
            self._load(c)
        self.assertIn("ticket", str(cm.exception))


class CutoffTicket(unittest.TestCase):
    def test_comments_after_cutoff_removed_and_input_untouched(self):
        t = late_ticket()
        before = copy.deepcopy(t)
        out = bench.cutoff_ticket(t, CUTOFF)
        self.assertEqual([c["id"] for c in out["comments"]], ["1", "2"])  # cut-off day is inclusive
        self.assertEqual(t, before)

    def test_undated_comment_is_dropped(self):
        t = ticket(comments=[comment("1", "", "x")])
        self.assertEqual(bench.cutoff_ticket(t, CUTOFF)["comments"], [])

    def test_outcome_fields_stripped(self):
        out = bench.cutoff_ticket(late_ticket(), CUTOFF)
        self.assertEqual((out["resolution"], out["status"], out["fix_versions"], out["since_versions"],
                          out["source_control_link"]), (None, None, [], [], ""))
        self.assertEqual(out["remotelinks"], [])
        self.assertEqual([a["id"] for a in out["attachments"]], ["1"])

    def test_link_added_after_cutoff_removed_using_changelog(self):
        hist = [history("2025-06-16T10:00:00.000+0000", "This issue is a child of CASSANDRA-14466"),
                history("2026-09-09T10:00:00.000+0000", f"This issue is related to {FIX_KEY}")]
        out = bench.cutoff_ticket(late_ticket(), CUTOFF, changelog=hist)
        self.assertEqual([k["key"] for k in out["issuelinks"]], ["CASSANDRA-14466"])

    def test_link_removal_entry_is_not_an_add(self):
        hist = [history("2025-06-16T10:00:00.000+0000", f"This issue relates to {FIX_KEY}"),
                history("2026-02-07T10:00:00.000+0000", None, from_string=f"This issue relates to {FIX_KEY}")]
        out = bench.cutoff_ticket(ticket(issuelinks=[link(FIX_KEY)]), CUTOFF, changelog=hist)
        self.assertEqual([k["key"] for k in out["issuelinks"]], [FIX_KEY])

    def test_without_changelog_links_to_tickets_created_later_are_dropped(self):
        created = {"CASSANDRA-14466": "2022-01-01", FIX_KEY: "2026-09-09"}
        out = bench.cutoff_ticket(late_ticket(), CUTOFF, link_created=created)
        self.assertEqual([k["key"] for k in out["issuelinks"]], ["CASSANDRA-14466"])

    def test_changelog_gap_falls_back_to_creation_date(self):
        hist = [history("2025-06-16T10:00:00.000+0000", "This issue is a child of CASSANDRA-14466")]
        created = {FIX_KEY: "2026-09-09"}
        out = bench.cutoff_ticket(late_ticket(), CUTOFF, changelog=hist, link_created=created)
        self.assertEqual([k["key"] for k in out["issuelinks"]], ["CASSANDRA-14466"])

    def test_link_with_no_evidence_is_dropped(self):
        self.assertEqual(bench.cutoff_ticket(late_ticket(), CUTOFF)["issuelinks"], [])

    def test_fetch_changelog_reads_histories(self):
        body = json.dumps({"changelog": {"histories": [history("2026-09-09T00:00:00.000+0000", "x CASSANDRA-1")]}})
        with mock.patch("cpr.bench.http_get", return_value=body) as g:
            out = bench.fetch_changelog("CASSANDRA-19987")
        self.assertIn("expand=changelog", g.call_args[0][0])
        self.assertEqual(len(out), 1)


class CaseContext(unittest.TestCase):
    def _write(self, **jira_extra):
        b = bundle()
        b["jira"] = {"status": "ok", "error": None, "ticket": late_ticket(), **jira_extra}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "context.md")
            t = bench.write_case_context(case(), b, path)
            with open(path) as f:
                return f.read(), t

    def test_later_link_removed(self):
        hist = [history("2025-06-16T10:00:00.000+0000", "This issue is a child of CASSANDRA-14466"),
                history("2026-09-09T10:00:00.000+0000", f"This issue is related to {FIX_KEY}")]
        text, t = self._write(changelog=hist)
        self.assertNotIn(FIX_KEY, text)
        self.assertIn("CASSANDRA-14466", text)
        self.assertEqual([k["key"] for k in t["issuelinks"]], ["CASSANDRA-14466"])

    def test_later_comment_and_outcome_absent(self):
        text, _ = self._write(changelog=[])
        self.assertIn("early comment", text)
        self.assertIn("same day comment", text)
        self.assertNotIn("the leak", text)
        for leaked in ("Resolved", "Fixed", "6.0", "pull/5168", "commit/6f5fe8c"):
            self.assertNotIn(leaked, text)

    def test_uses_case_head_and_base(self):
        text, _ = self._write()
        self.assertIn("b" * 40, text)

    def test_no_ticket(self):
        b = bundle()
        b["jira"] = {"status": "unavailable", "error": "x", "ticket": None}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "c.md")
            self.assertIsNone(bench.write_case_context(case(), b, path))
            with open(path) as f:
                self.assertIn("No ticket", f.read())

    def test_checks_are_optional_and_filtered(self):
        b = bundle()
        text, _ = bench.render_case_context(case(), b, checks=[
            {"status": "fail", "title": "T1", "summary": "bad"}, {"status": "pass", "title": "T2", "summary": "ok"}])
        self.assertIn("[fail] T1", text)
        self.assertNotIn("T2", text)


if __name__ == "__main__":
    unittest.main()


class Score(unittest.TestCase):
    """cpr bench score on recorded lens outputs (spec: lens-benchmark, Run and score)."""

    FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "lenses", "5201")
    OLD = {"lenses": [{"name": n, "agent": n} for n in
                      ("cassandra-standards", "correctness", "test-rigor", "observability", "security")]}

    def setUp(self):
        import shutil
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.case = bench.find_cases("B6")[0]
        self.runs = os.path.join(self.tmp, "runs")

    def panel(self, name, drop=()):
        import shutil
        path = os.path.join(self.tmp, f"{name}.json")
        with open(path, "w") as f:
            json.dump(self.OLD, f)
        lens_dir = os.path.join(bench.run_dir(name, self.case["id"], 1, self.runs), "lenses")
        os.makedirs(lens_dir)
        for fn in os.listdir(self.FIXTURE):
            src = os.path.join(self.FIXTURE, fn)
            if fn[:-5] in drop:
                with open(src) as f:
                    data = json.load(f)
                data.update(findings=[], approve=True)
                with open(os.path.join(lens_dir, fn), "w") as f:
                    json.dump(data, f)
            else:
                shutil.copy(src, lens_dir)
        return path

    def test_recorded_5201_finds_known_issues(self):
        s = bench.score_panel(self.panel("old"), [self.case], runs_dir=self.runs, labels={})
        c = s["cases"][0]
        self.assertEqual((c["raw"], c["issues"], c["must_fix"]), ([11], [5], [3]))
        self.assertEqual(c["found"], {"K1": 1, "K2": 1, "K3": 1})
        self.assertEqual(s["recall_soft"][0], 1.0)
        self.assertAlmostEqual(s["duplicate_rate"], 1 - 5 / 11)
        self.assertTrue(os.path.exists(os.path.join(bench.run_dir("old", self.case["id"], 1, self.runs), "merged.json")))

    def test_comparing_panels(self):
        old = bench.score_panel(self.panel("old"), [self.case], runs_dir=self.runs, labels={})
        new = bench.score_panel(self.panel("new", drop=("cassandra-standards", "correctness", "test-rigor")),
                                [self.case], runs_dir=self.runs, labels={})
        diff = bench.compare(new, old)
        self.assertIn((self.case["id"], "K2"), diff["b_only"])
        self.assertEqual(diff["a_only"], [])
        table = bench.format_scores([new, old], diff)
        self.assertIn("| hard recall | ", table)
        self.assertIn("Found only by old: B6-21649 K2", table)

    def test_labels_cached(self):
        s = bench.score_panel(self.panel("old"), [self.case], runs_dir=self.runs, labels={})
        keys = {u["key"] for u in s["unlabelled"]}
        labels = {k: "real" for k in keys}
        again = bench.score_panel(os.path.join(self.tmp, "old.json"), [self.case], runs_dir=self.runs, labels=labels)
        self.assertEqual(again["unlabelled"], [])
