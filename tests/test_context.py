"""reviewer-context: hunk ranges, credit parsing, identity, related tickets, experts, suggestions."""

import datetime
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from cpr import checks, context, credits, diffparse, diffview, model, render
from cpr.ingest import history, jira
from cpr.triage import triage
from tests.helpers import bundle

TODAY = datetime.date(2026, 10, 7)
ROSTER = {"committers": {"alice": "Alice Smith", "bob": "Bob Jones", "carol": "Carol Díaz", "mck": "Michael Semb Wever",
                         "marcuse": "Marcus Eriksson", "dave": "Dave Lee"}}
CFG = history.load_config()


def commit(sha, date, message, name="Committer", email="c@example.com"):
    return {"sha": sha, "merge": False, "date": date, "author_name": name, "author_email": email, "message": message}


class HunkRanges(unittest.TestCase):
    DIFF = ("diff --git a/x b/x\n--- a/x\n+++ b/x\n"
            "@@ -10,4 +10,5 @@\n a\n-b\n+B\n+C\n c\n d\n"
            "@@ -40,0 +41,2 @@\n+n1\n+n2\n"
            "diff --git a/n b/n\n--- /dev/null\n+++ b/n\n@@ -0,0 +1,2 @@\n+x\n+y\n")

    def test_changed_lines_and_pure_addition(self):
        hunks = diffparse.old_side_hunks(self.DIFF)
        self.assertEqual([(h["start"], h["end"], h["kind"]) for h in hunks], [(11, 11, "changed"), (38, 43, "insertion")])

    def test_new_file_has_nothing_to_blame(self):
        self.assertEqual([h["path"] for h in diffparse.old_side_hunks(self.DIFF)], ["x", "x"])

    def test_rename_blames_old_path(self):
        d = "diff --git a/old b/new\n--- a/old\n+++ b/new\n@@ -5,1 +5,1 @@\n-x\n+y\n"
        h = diffparse.old_side_hunks(d)[0]
        self.assertEqual((h["path"], h["new_path"]), ("old", "new"))


class Credits(unittest.TestCase):
    def test_several_authors_and_reviewers(self):
        p = credits.parse("patch by Yaman Ziadeh, Bernardo Botella, Stefan Miklosovic; reviewed by Dmitry Konstantinov, "
                          "Jyothsna Konisa for CASSANDRA-20854")
        self.assertEqual(len(p["authors"]), 3)
        self.assertEqual(p["reviewers"], ["Dmitry Konstantinov", "Jyothsna Konisa"])
        self.assertEqual(p["key"], "CASSANDRA-20854")

    def test_wrapped_line(self):
        p = credits.parse("Block decommission\n\nPatch by Nivy Kani; reviewed by Sam Tunnicliffe and Caleb Rackliffe for\n"
                          "CASSANDRA-21539")
        self.assertEqual((p["authors"], p["reviewers"], p["key"]),
                         (["Nivy Kani"], ["Sam Tunnicliffe", "Caleb Rackliffe"], "CASSANDRA-21539"))

    def test_tbd_ignored_and_typo_verbs(self):
        self.assertEqual(credits.parse("patch by F; reviewed by TBD for CASSANDRA-3")["reviewers"], [])
        for verb in ("review by", "reviwed by", "reivewed by", "Reviewed by"):
            self.assertEqual(credits.parse(f"patch by A; {verb} B for CASSANDRA-1")["reviewers"], ["B"], verb)

    def test_primary_key_prefers_credit_line(self):
        msg = "Fix X, follow-up to CASSANDRA-100\n\npatch by A; reviewed by B for CASSANDRA-200"
        self.assertEqual(credits.primary_key(msg), "CASSANDRA-200")
        self.assertEqual(credits.primary_key("Fix (CASSANDRA-5)"), "CASSANDRA-5")
        self.assertIsNone(credits.primary_key("typo"))


class Identity(unittest.TestCase):
    def setUp(self):
        self.r = credits.Resolver(ROSTER, credits.load_aliases())

    def test_alias(self):
        self.assertEqual(self.r.resolve("Mick Semb Wever")[2], "mck")
        self.assertEqual(self.r.resolve("Michael Semb Wever")[2], "mck")

    def test_asf_id_written_as_a_name(self):
        self.assertEqual(self.r.resolve("marcuse")[2], "marcuse")

    def test_accents_and_case(self):
        self.assertEqual(self.r.resolve("carol diaz")[2], "carol")

    def test_apache_email(self):
        self.assertEqual(self.r.resolve("Whoever", "BOB@apache.org")[2], "bob")

    def test_unresolved(self):
        key, display, asf = self.r.resolve("Zed Unknown")
        self.assertEqual((display, asf), ("Zed Unknown", None))
        self.assertTrue(key.startswith("name:"))


def ctx_bundle(**history_kw):
    b = bundle()
    b["meta"]["fetched_at"] = "2026-10-07T00:00:00Z"
    b["roster"] = {"status": "ok", "roster": ROSTER}
    b["jira"]["ticket"]["comments"] = []
    b["pr"]["author"] = "pat-author"  # not on the test roster
    b["commits"][0].update(login="pat-author", author_name="Pat Author", author_email="pat@example.com")
    h = {"hunks_total": 2, "hunks_blamed": 2, "hunks_skipped": 0, "files_total": 1, "files_logged": 1,
         "files_skipped": 0, "new_files_only": False, "blame": [], "commits": {}, "file_logs": {}, "log_refs": {},
         "keys": [], "tickets": {}}
    h.update(history_kw)
    b["history"] = h
    return b


class RelatedTickets(unittest.TestCase):
    def test_modified_lines_lead_to_their_tickets(self):
        a = commit("a" * 40, "2024-01-01", "Fix A\n\npatch by Alice; reviewed by Bob for CASSANDRA-100")
        b = commit("b" * 40, "2025-01-01", "Fix B (CASSANDRA-200)")
        c = context.build(ctx_bundle(
            blame=[{"path": "F.java", "sha": a["sha"], "lines": 10}, {"path": "F.java", "sha": b["sha"], "lines": 2}],
            commits={a["sha"]: a, b["sha"]: b},
            tickets={"CASSANDRA-100": {"summary": "Old fix", "status": "Resolved", "url": "u"}}))
        self.assertEqual([(t["key"], t["lines"]) for t in c["related_tickets"]], [("CASSANDRA-100", 10), ("CASSANDRA-200", 2)])
        self.assertEqual(c["related_tickets"][0]["summary"], "Old fix")

    def test_commit_without_a_ticket(self):
        a = commit("a" * 40, "2024-01-01", "Reformat everything")
        c = context.build(ctx_bundle(blame=[{"path": "F.java", "sha": a["sha"], "lines": 4}], commits={a["sha"]: a}))
        self.assertEqual(c["related_tickets"], [])
        self.assertEqual(c["untracked_commits"][0]["subject"], "Reformat everything")

    def test_own_ticket_is_not_related(self):
        a = commit("a" * 40, "2024-01-01", "Fix (CASSANDRA-21649)")
        c = context.build(ctx_bundle(blame=[{"path": "F.java", "sha": a["sha"], "lines": 4}], commits={a["sha"]: a}))
        self.assertEqual(c["related_tickets"], [])

    def test_new_files_only(self):
        c = context.build(ctx_bundle(new_files_only=True))
        self.assertTrue(c["new_files_only"])

    def test_bundle_without_history(self):
        b = bundle()
        b.pop("history", None)
        self.assertEqual(context.build(b)["status"], "unavailable")


class Experts(unittest.TestCase):
    def test_recent_work_outranks_old_work(self):
        log = [commit("1" * 40, "2026-03-01", "x\n\npatch by Alice Smith; reviewed by Dave Lee for CASSANDRA-1"),
               commit("2" * 40, "2026-05-01", "y\n\npatch by Alice Smith; reviewed by Dave Lee for CASSANDRA-2")]
        log += [commit(str(i) * 40, "2020-01-01", f"old\n\npatch by Bob Jones; reviewed by Dave Lee for CASSANDRA-{i}")
                for i in range(3, 6)]
        c = context.build(ctx_bundle(file_logs={"F.java": log}))
        names = [p["name"] for p in c["experts"]["F.java"]]
        self.assertEqual(names[0], "Alice Smith")
        self.assertNotIn("Bob Jones", names)  # all of Bob's work is outside the 5-year window

    def test_git_author_counts_without_credit_line(self):
        log = [commit("1" * 40, "2026-01-01", "Fix it", name="Carol Díaz", email="carol@apache.org")]
        c = context.build(ctx_bundle(file_logs={"F.java": log}))
        self.assertEqual(c["experts"]["F.java"][0]["asf_id"], "carol")


class Suggestions(unittest.TestCase):
    def log(self):
        return [commit(str(i) * 40, "2026-06-01", f"x\n\npatch by {a}; reviewed by {r} for CASSANDRA-{i}")
                for i, (a, r) in enumerate([("Alice Smith", "Bob Jones"), ("Alice Smith", "Bob Jones"),
                                             ("Dave Lee", "Zed Unknown")], 1)]

    def test_author_excluded(self):
        b = ctx_bundle(file_logs={"F.java": self.log()})
        b["commits"][0].update(author_name="Alice Smith", author_email="alice@example.com")
        names = [p["name"] for p in context.build(b)["suggested_reviewers"]]
        self.assertNotIn("Alice Smith", names)
        self.assertNotIn("Zed Unknown", names)  # not a committer
        self.assertEqual(names[0], "Bob Jones")

    def test_committer_who_opened_someone_elses_patch_is_excluded(self):
        b = ctx_bundle(file_logs={"F.java": self.log()})
        b["pr"]["author"] = "bob"  # GitHub login equal to an ASF id; the commits are someone else's
        self.assertNotIn("Bob Jones", [p["name"] for p in context.build(b)["suggested_reviewers"]])

    def test_already_involved_via_reviewers_field(self):
        b = ctx_bundle(file_logs={"F.java": self.log()})
        b["jira"]["ticket"]["reviewers"] = [{"name": "alice", "display": "Alice Smith"}]
        c = context.build(b)
        self.assertEqual([p["name"] for p in c["already_reviewing"]], ["Alice Smith"])
        self.assertNotIn("Alice Smith", [p["name"] for p in c["suggested_reviewers"]])

    def test_commented_on_the_ticket(self):
        b = ctx_bundle(file_logs={"F.java": self.log()})
        b["jira"]["ticket"]["comments"] = [{"id": "1", "author": "alice", "display": "Alice Smith", "created": "",
                                            "body": "Looks close", "url": "u"}]
        c = context.build(b)
        self.assertEqual([p["name"] for p in c["already_reviewing"]], ["Alice Smith"])

    def test_suggestion_names_its_files(self):
        c = context.build(ctx_bundle(file_logs={"F.java": self.log(), "G.java": self.log()[:1]}))
        alice = next(p for p in c["suggested_reviewers"] if p["name"] == "Alice Smith")
        self.assertEqual(sorted(alice["files"]), ["F.java", "G.java"])


class Budget(unittest.TestCase):
    def test_huge_pr(self):
        hunks = [{"path": f"src/java/F{i % 7}.java", "new_path": f"src/java/F{i % 7}.java", "start": i, "end": i,
                  "kind": "changed", "lines": 1} for i in range(1200)]
        files = [{"path": f"src/java/F{i}.java", "additions": i * 10, "deletions": 0, "status": "M"} for i in range(7)]
        chosen, skipped = history.select_hunks(hunks, files, 300)
        self.assertEqual((len(chosen), skipped), (300, 900))
        self.assertEqual(chosen[0]["path"], "src/java/F6.java")  # largest production file first

    def test_files_budget_skips_new_files(self):
        files = [{"path": f"src/java/F{i}.java", "additions": 1, "deletions": 0, "status": "M"} for i in range(30)]
        files.append({"path": "src/java/New.java", "additions": 99, "deletions": 0, "status": "A"})
        chosen, skipped = history.select_files(files, 25)
        self.assertEqual((len(chosen), skipped), (25, 5))
        self.assertNotIn("src/java/New.java", [f["path"] for f in chosen])


class GatherFromGit(unittest.TestCase):
    def test_blame_and_log_in_real_repo(self):
        with tempfile.TemporaryDirectory() as d:
            env = {**os.environ, "GIT_AUTHOR_DATE": "2026-01-01T00:00:00", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00"}

            def git(*a):
                return subprocess.run(["git", "-C", d, *a], check=True, capture_output=True, text=True, env=env).stdout.strip()
            git("init", "-q", "-b", "trunk")
            git("config", "user.email", "t@example.com")
            git("config", "user.name", "T")
            with open(os.path.join(d, "F.java"), "w") as f:
                f.write("".join(f"line{i}\n" for i in range(1, 21)))
            git("add", ".")
            git("commit", "-qm", "Add F\n\npatch by Alice Smith; reviewed by Bob Jones for CASSANDRA-100")
            base = git("rev-parse", "HEAD")
            git("update-ref", "refs/remotes/origin/trunk", base)
            diff = ("diff --git a/F.java b/F.java\n--- a/F.java\n+++ b/F.java\n"
                    "@@ -5,1 +5,1 @@\n-line5\n+LINE5\n")
            files = [{"path": "F.java", "previous_path": None, "status": "M", "additions": 1, "deletions": 1}]
            h = history.gather(d, base, diff, files, CFG)
        self.assertEqual(h["blame"], [{"path": "F.java", "sha": base, "lines": 1}])
        self.assertEqual(h["keys"], ["CASSANDRA-100"])
        self.assertEqual(h["log_refs"], {"F.java": "trunk"})
        self.assertEqual(len(h["file_logs"]["F.java"]), 1)


class Jira(unittest.TestCase):
    def test_batch_lookup_uses_validate_warn(self):
        seen = []

        def fake(url, recorder=None):
            seen.append(url)
            return '{"issues": [{"key": "CASSANDRA-1", "fields": {"summary": "S", "status": {"name": "Open"}}}]}'
        with mock.patch.object(jira, "http_get", fake):
            out = jira.lookup_keys(["CASSANDRA-1", "CASSANDRA-99999999"], None)
        self.assertEqual(list(out), ["CASSANDRA-1"])
        self.assertIn("validateQuery=warn", seen[0])

    def test_ticket_has_links(self):
        issue = {"key": "CASSANDRA-5", "fields": {"issuelinks": [
            {"type": {"name": "Causality", "inward": "is caused by", "outward": "causes"},
             "inwardIssue": {"key": "CASSANDRA-300", "fields": {"summary": "Root", "status": {"name": "Resolved"}}}}]}}
        t = jira.normalize(issue, {}, [])
        self.assertEqual(t["issuelinks"][0]["relation"], "is caused by")
        self.assertEqual(t["issuelinks"][0]["key"], "CASSANDRA-300")


class ReportModel(unittest.TestCase):
    def test_context_in_model_and_section(self):
        b = ctx_bundle()
        m = model.build(b, checks.run_all(b), triage(b), render.load_docs(), diffview.unavailable("x"),
                        context=context.build(b))
        ids = [s["id"] for s in m["sections"]]
        self.assertEqual(ids[ids.index("triage") + 1], "context")
        self.assertEqual(m["context"]["status"], "ok")

    def test_invalid_context_rejected(self):
        b = ctx_bundle()
        bad = context.build(b)
        bad["related_tickets"] = "nope"
        with self.assertRaises(model.ModelError):
            model.build(b, checks.run_all(b), triage(b), render.load_docs(), diffview.unavailable("x"), context=bad)


if __name__ == "__main__":
    unittest.main()
