"""Derived view fields (report-redesign): status words, steps to merge, to-do by role, verdict card."""

import json
import os
import unittest

from cpr import model

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load():
    with open(os.path.join(REPO, "tests", "fixtures", "models", "5201.json")) as f:
        return json.load(f)


class StatusWords(unittest.TestCase):
    def test_words(self):
        self.assertEqual(model.status_word("fail"), "Must fix")
        self.assertEqual(model.status_word("warn", True), "Should fix")
        self.assertEqual(model.status_word("warn", False), "Note")
        self.assertEqual(model.status_word("unknown"), "Unknown")
        self.assertEqual(model.status_word("pass"), "Passed")
        self.assertEqual(model.status_word("not-applicable"), "Not needed")
        self.assertEqual(model.status_word("something-new"), "Unknown")

    def test_first_sentence(self):
        self.assertEqual(model.first_sentence("Add a test. Then run it."), "Add a test")
        self.assertEqual(model.first_sentence(None), "")
        self.assertEqual(model.first_sentence("Put the key in the title, e.g. CASSANDRA-1 Fix it. Then push."), "Put the key in the title, e.g. CASSANDRA-1 Fix it")
        long = "word " * 80
        cut = model.first_sentence(long, 50)
        self.assertTrue(cut.endswith("…") and len(cut) <= 51)
        self.assertEqual(model.first_sentence("Run `a b c d e f g h` now please", 14).count("`") % 2, 0)


class View5201(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load()
        cls.v = model.derive_view(cls.m)

    def test_verdict_card(self):
        v = self.v["verdict"]
        self.assertEqual((v["kind"], v["headline"]), ("blocked", "Not ready to merge"))
        self.assertEqual(v["sentence"], "The contributor has 3 fixes to make. Then a committer runs CI and two committers vote.")
        self.assertEqual(v["note"], "")
        self.assertEqual(v["must_count"], 3)

    def test_steps_to_merge(self):
        steps = {s["label"].split(" (")[0]: s["state"] for s in self.v["steps"]}
        self.assertEqual(steps, {"Ticket": "ok", "Tests": "bad", "Code review": "bad", "CI": "bad", "+1 votes": "bad"})
        self.assertIn("+1 votes (0 of 2)", [s["label"] for s in self.v["steps"]])

    def test_now_is_the_contributors_fixes_then_is_steps(self):
        todo = self.v["todo"]
        self.assertEqual([r["role"] for r in todo["roles"]], ["Contributor"])
        now = todo["roles"][0]["items"]
        flags = [i["must"] for i in now]
        self.assertEqual(flags, sorted(flags, reverse=True))
        self.assertEqual(sum(1 for i in now if i["must"]), 3)
        self.assertEqual(todo["must_count"], 3)
        self.assertTrue(todo["optional_count"] >= 3)
        self.assertTrue(all(i["kind"] == "step" for i in todo["then"]))
        must_steps = [i["title"] for i in todo["then"] if i["must"]]
        self.assertEqual(must_steps, ["Ask for review on the JIRA ticket or the dev@ list", "Run pre-commit CI on each target branch",
                                      "Collect two committer +1 votes"])
        self.assertEqual(todo["then"][0]["owner"], "contributor")
        self.assertEqual(todo["then"][1]["who"], "Any Cassandra committer")

    def test_test_request_is_one_item_that_also_satisfies_the_check(self):
        now = self.v["todo"]["roles"][0]["items"]
        self.assertNotIn("tests.present", [i["check"] for i in now])
        tests = [i for i in now if i["also"]]
        self.assertEqual(len(tests), 1)
        self.assertEqual(tests[0]["also"], "Tests accompany production changes")
        self.assertEqual(tests[0]["also_check"], "tests.present")
        self.assertEqual(tests[0]["source"], "Code review")
        self.assertEqual(self.v["words"]["tests.present"], "Must fix")  # the check itself is unchanged

    def test_titles_stand_alone_with_location_and_source(self):
        now = [i for i in self.v["todo"]["roles"][0]["items"] if i["must"]]
        self.assertEqual([i["title"] for i in now], ["Observability \u2014 SSTable.java:121", "Correctness \u2014 LogTransaction.java:396",
                                                    "Test rigor \u2014 SSTable.java:113"])
        self.assertEqual([i["location"] for i in now], ["SSTable.java:121", "LogTransaction.java:396", "SSTable.java:113"])
        self.assertEqual({i["source"] for i in now}, {"Code review"})
        self.assertTrue(all(i["issue"] for i in now))
        self.assertTrue(all("\u2026" not in i["title"] for i in self.v["todo"]["roles"][0]["items"]))

    def test_lens_title_wins_over_the_fallback(self):
        m = load()
        m["review"]["issues"][1]["title"] = "Delete SSTable components in mtime order in SSTableTidier"
        now = model.derive_view(m)["todo"]["roles"][0]["items"]
        self.assertIn("Delete SSTable components in mtime order in SSTableTidier", [i["title"] for i in now])

    def test_reviewers_row_shows_three_names_and_the_vote_count(self):
        votes = next(i for i in self.v["todo"]["then"] if i["check"] == "votes.committer-plus-ones" and i["owner"] == "reviewer")
        self.assertEqual(votes["who"], "Suggested: Stefan Miklosovic, Michael Semb Wever, Maxim Muzafarov and 2 more \u00b7 +1 votes: 0 of 2")

    def test_no_fixes_means_only_steps_remain(self):
        m = load()
        m["recommendation"]["reasons"] = [r for r in m["recommendation"]["reasons"] if r["owner"] != "contributor"]
        m["recommendation"]["verdict"] = "awaiting-review"
        m["checks"] = [dict(c, status="pass") if c["owner"] == "contributor" else c for c in m["checks"]]
        v = model.derive_view(m)
        self.assertEqual(v["todo"]["fix_count"], 0)
        self.assertEqual(v["todo"]["now_role"], "contributor")  # asking for review comes first
        self.assertEqual(v["verdict"]["sentence"],
                         "The contributor asks for review. Then a committer runs CI and two committers vote.")


    def test_groups_sorted_problems_first_with_plain_words(self):
        groups = self.v["groups"]
        order = [g["status"] for g in groups]
        rank = {"fail": 0, "warn": 1, "unknown": 2, "pass": 3, "not-applicable": 4}
        self.assertEqual(order, sorted(order, key=rank.get))
        by = {g["id"]: g for g in groups}
        self.assertEqual(by["ci"]["word"], "Must fix")
        self.assertEqual(by["ticket"]["word"], "Should fix")
        self.assertEqual(by["compatibility"]["word"], "Note")
        self.assertEqual(by["static"]["word"], "Passed")
        self.assertTrue(by["review"]["is_review"])
        self.assertNotIn("triage", by)

    def test_header_effort_and_headlines(self):
        self.assertTrue(self.v["header"]["first_time_contributor"])
        self.assertEqual(self.v["effort"]["level"], 2)
        self.assertEqual(set(self.v["headlines"]), {i["id"] for i in self.m["review"]["issues"]})
        self.assertEqual(self.v["words"]["tests.present"], "Must fix")


class Titles(unittest.TestCase):
    def test_fallback_is_rule_and_short_location(self):
        self.assertEqual(model.finding_title({"rule": "test-rigor", "location": "src/java/A/Foo.java:12 (new file)"}), "Test rigor \u2014 Foo.java:12")
        self.assertEqual(model.finding_title({"rule": "x", "location": "ticket"}), "X \u2014 ticket")

    def test_long_rule_is_shortened_at_a_colon_not_mid_word(self):
        rule = "Commit hygiene: CHANGES.txt entry and 'patch by ... ; reviewed by ... for CASSANDRA-N' commit message"
        self.assertEqual(model.humanize_rule(rule), "Commit hygiene")
        self.assertEqual(model.humanize_rule("word " * 30).count("\u2026"), 1)

    def test_a_rule_written_as_a_sentence_is_kept_whole(self):
        rule = "Resource cleanup: failures on the delete path must not be swallowed"
        self.assertEqual(model.humanize_rule(rule), rule)
        self.assertEqual(model.humanize_rule("Bug fix needs a regression test that fails without the fix (ticket plan: additions to LogTransactionTest)"),
                         "Bug fix needs a regression test that fails without the fix")

    def test_title_over_80_is_not_used(self):
        self.assertEqual(model.finding_title({"title": "x" * 81, "rule": "r", "location": "A.java:1"}), "R \u2014 A.java:1")


class Verdict(unittest.TestCase):
    def test_only_fixes_are_counted_and_nothing_restates(self):
        v = model.derive_view(load())
        self.assertEqual(v["verdict"]["must_count"], 3)
        self.assertNotIn("must-fix", v["verdict"]["sentence"])
        self.assertNotIn("Overall", json.dumps(v["verdict"]))

    def test_needs_work_counts_requested_changes_and_asking_for_review_is_a_step(self):
        m = load()
        m["recommendation"]["verdict"] = "needs-work"
        m["recommendation"]["reasons"] = [{"check": "jira.fix-version", "finding": None, "title": "Fix versions", "status": "warn", "summary": "none set",
                                           "action": "Set Fix Version(s) on the ticket.", "owner": "contributor", "blocking": False}]
        for c in m["checks"]:
            if c["id"] == "jira.fix-version":
                c["status"], c["action_required"] = "warn", True
        v = model.derive_view(m)
        self.assertEqual(v["verdict"]["headline"], "Needs changes")
        self.assertTrue(v["verdict"]["sentence"].startswith("The contributor has 1 change to make."))
        self.assertNotIn("asks for review", v["verdict"]["sentence"])
        self.assertEqual(v["todo"]["must_count"], 0)

    def test_one_fix_is_singular(self):
        m = load()
        m["review"]["issues"] = m["review"]["issues"][:1]
        m["recommendation"]["reasons"] = [r for r in m["recommendation"]["reasons"]
                                          if r["finding"] in (None, "OBS-1") and r["check"] != "tests.present"]
        self.assertTrue(model.derive_view(m)["verdict"]["sentence"].startswith("The contributor has 1 fix to make."))


class VerdictKinds(unittest.TestCase):
    def kind(self, verdict):
        m = load()
        m["recommendation"] = {"verdict": verdict, "label": verdict, "reasons": [], "waiting_on": []}
        return model.derive_view(m)["verdict"]

    def test_each_verdict_has_a_card(self):
        expect = {"ready": ("ready", "Ready to merge"), "draft": ("draft", "Draft"),
                  "insufficient-evidence": ("unknown", "Cannot tell yet"),
                  "awaiting-review": ("waiting", "Waiting for review"),
                  "requirements-met-unreviewed": ("waiting", "Not reviewed yet")}
        for verdict, (kind, headline) in expect.items():
            v = self.kind(verdict)
            self.assertEqual((v["kind"], v["headline"]), (kind, headline))

    def test_validate_rejects_bad_view(self):
        m = load()
        m["view"] = model.derive_view(m)
        model.validate(m)
        m["view"]["verdict"]["kind"] = "purple"
        with self.assertRaises(model.ModelError):
            model.validate(m)


if __name__ == "__main__":
    unittest.main()
