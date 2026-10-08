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
        self.assertEqual(v["sentence"], "6 must-fix items. 3 people need to act.")

    def test_steps_to_merge(self):
        steps = {s["label"].split(" (")[0]: s["state"] for s in self.v["steps"]}
        self.assertEqual(steps, {"Ticket": "ok", "Tests": "bad", "Code review": "bad", "CI": "bad", "+1 votes": "bad"})
        self.assertIn("+1 votes (0 of 2)", [s["label"] for s in self.v["steps"]])

    def test_todo_roles_must_first(self):
        roles = self.v["todo"]["roles"]
        self.assertEqual([r["role"] for r in roles], ["Contributor", "Committer", "Reviewers"])
        items = roles[0]["items"]
        flags = [i["must"] for i in items]
        self.assertEqual(flags, sorted(flags, reverse=True))
        self.assertEqual(roles[0]["must_count"], 4)
        self.assertEqual(self.v["todo"]["must_count"], 6)
        self.assertTrue(self.v["todo"]["optional_count"] >= 3)
        self.assertEqual(roles[1]["who"], "Any Cassandra committer")

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
