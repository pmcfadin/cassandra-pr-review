"""pr-ingest: read-only network, key resolution, JIRA, siblings, CI parsing, clone, offline cache."""

import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from cpr import net
from cpr.ingest import bundle as bundle_mod, ci_summary, clone, github, jira, keys, roster

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


class ReadOnlyNetwork(unittest.TestCase):
    def test_http_get_only_issues_get(self):
        seen = []

        class Resp:
            status = 200

            def read(self, n):
                return b"ok"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout):
            seen.append(req.get_method())
            return Resp()

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            self.assertEqual(net.http_get("https://example.org/x"), "ok")
        self.assertEqual(seen, ["GET"])

    def test_gh_refuses_mutating_flags(self):
        for bad in (["-X", "POST"], ["--method=PATCH"], ["-f", "a=b"], ["-F", "a=b"], ["--input", "x"],
                    ["--raw-field", "a=b"], ["--field", "a=b"]):
            with self.assertRaises(ValueError, msg=bad):
                net.check_gh_args(bad)

    def test_gh_api_runs_only_gh_api(self):
        calls = []

        def fake_run(cmd, capture_output, text):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="{}", stderr="")

        with mock.patch("subprocess.run", fake_run):
            net.gh_api("repos/apache/cassandra/pulls/1")
            net.gh_json("repos/apache/cassandra/pulls/1/commits", paginate=True)
        for cmd in calls:
            self.assertEqual(cmd[:2], ["gh", "api"])
            self.assertFalse(set(cmd) & {"-X", "--method", "-f", "-F", "--field", "--raw-field", "--input"})

    def test_ingest_source_uses_no_mutating_calls(self):
        # Every network call in ingest goes through cpr.net; nothing else imports urllib or calls gh.
        root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cpr", "ingest")
        for name in os.listdir(root):
            if name.endswith(".py"):
                with open(os.path.join(root, name)) as f:
                    src = f.read()
                self.assertNotIn("urlopen", src, name)
                self.assertNotIn('"gh"', src, name)
                self.assertNotIn("method=", src, name)


class KeyResolution(unittest.TestCase):
    def test_key_in_title(self):
        r = keys.resolve("CASSANDRA-21649: Fix ...", "21649-5.0", "", [])
        self.assertEqual(r["key"], "CASSANDRA-21649")
        self.assertEqual(r["sources"], ["title", "branch"])
        self.assertEqual(r["conflicts"], [])

    def test_conflicting_keys(self):
        r = keys.resolve("CASSANDRA-21000 fix", "CASSANDRA-21001-trunk", "", [])
        self.assertEqual(r["key"], "CASSANDRA-21000")
        self.assertEqual([c["key"] for c in r["conflicts"]], ["CASSANDRA-21001"])

    def test_no_key_anywhere(self):
        r = keys.resolve("Fix typo", "patch-1", "no ticket", ["Fix typo"])
        self.assertIsNone(r["key"])
        self.assertEqual(r["sources"], [])

    def test_body_and_commit_fallback(self):
        self.assertEqual(keys.resolve("Fix", "x", "See CASSANDRA-123", [])["key"], "CASSANDRA-123")
        self.assertEqual(keys.resolve("Fix", "x", "", ["patch for CASSANDRA-9876"])["key"], "CASSANDRA-9876")

    def test_related_ticket_in_body_is_not_a_conflict(self):
        r = keys.resolve("CASSANDRA-21649: Fix", "21649-5.0", "Follows CASSANDRA-20000", [])
        self.assertEqual(r["conflicts"], [])


class CiSummaryParsing(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(FIX, "ci", name)) as f:
            return f.read()

    def test_classic_layout(self):
        r = ci_summary.parse(self.read("classic.html"))
        self.assertEqual(r["layout"], "classic")
        self.assertEqual(r["sha"], "1c9f391e00a10e3294a6fa3c5258effef8f2b4a3")
        self.assertEqual((r["passed"], r["failed"], r["total"]), (28804, 0, 30478))
        self.assertTrue(r["has_upgrade_tests"])
        self.assertEqual(ci_summary.guess_target_branch(r["ref"]), "cassandra-5.0")

    def test_totals_layout_with_placeholder_sha(self):
        r = ci_summary.parse(self.read("totals.html"))
        self.assertEqual(r["layout"], "totals")
        self.assertIsNone(r["sha"])
        self.assertIn("placeholder", r["sha_note"])
        self.assertEqual((r["passed"], r["failed"], r["skipped"]), (114106, 11, 2394))
        self.assertEqual(len(r["failures"]), 11)
        self.assertEqual(ci_summary.guess_target_branch(r["ref"]), "trunk")

    def test_unparseable(self):
        with self.assertRaises(ValueError):
            ci_summary.parse("<html><body>hello</body></html>")

    def test_attachment_names(self):
        self.assertTrue(ci_summary.is_ci_summary("4.0-ci_summary-1.html"))
        self.assertFalse(ci_summary.is_ci_summary("results.txt"))
        self.assertTrue(ci_summary.is_result_details("results_details_trunk.tar.xz"))
        self.assertTrue(ci_summary.is_result_details("result_details.tar.gz"))


class CollectCi(unittest.TestCase):
    def ticket_with(self, *names):
        return {"attachments": [{"filename": n, "url": f"https://x/{n}", "created": "2026", "author": "a",
                                 "size": 1} for n in names]}

    def test_summary_attached_and_mapped_by_sha(self):
        with open(os.path.join(FIX, "ci", "classic.html")) as f:
            page = f.read()
        sibs = [{"base": "cassandra-5.0", "head_sha": "1c9f391e00a10e3294a6fa3c5258effef8f2b4a3"}]
        with mock.patch.object(bundle_mod, "http_get", return_value=page):
            ci = bundle_mod.collect_ci(self.ticket_with("ci_summary.html", "result_details.tar.gz"), sibs, None)
        s = ci["summaries"][0]
        self.assertEqual((s["target_branch"], s["mapped_by"], s["parse_status"]), ("cassandra-5.0", "sha", "ok"))
        self.assertEqual(len(ci["result_archives"]), 1)

    def test_unparseable_summary_is_recorded(self):
        with mock.patch.object(bundle_mod, "http_get", return_value="<p>nope</p>"):
            ci = bundle_mod.collect_ci(self.ticket_with("ci_summary.html"), [], None)
        self.assertEqual(ci["summaries"][0]["parse_status"], "unparsed")
        self.assertTrue(ci["summaries"][0]["error"])

    def test_no_ci_attached(self):
        ci = bundle_mod.collect_ci(self.ticket_with("patch.diff"), [], None)
        self.assertEqual(ci["summaries"], [])


class JiraFetch(unittest.TestCase):
    IDS = {"reviewers": "customfield_12313420", "authors": "customfield_12313920",
           "test_doc_plan": "customfield_12313823", "impacts": "customfield_12313922",
           "since_versions": None, "source_control_link": "customfield_12313924"}

    def test_ticket_exists(self):
        with open(os.path.join(FIX, "jira", "CASSANDRA-21520.json")) as f:
            issue = json.load(f)
        t = jira.normalize(issue, self.IDS, [{"object": {"title": "GitHub Pull Request #5227",
                                                          "url": "https://github.com/apache/cassandra/pull/5227"}}])
        self.assertEqual(t["key"], "CASSANDRA-21520")
        self.assertEqual(t["reviewers"][0]["name"], "maedhroz")
        self.assertTrue(t["attachments"])
        self.assertEqual(t["since_versions"], [])  # absent fields are empty, not missing
        for k in ("status", "fix_versions", "components", "comments", "remotelinks", "test_doc_plan"):
            self.assertIn(k, t)

    def test_ticket_not_found(self):
        with mock.patch.object(jira, "http_get", side_effect=net.NetError("HTTP 404", 404)):
            r = jira.fetch_ticket("CASSANDRA-1", None)
        self.assertEqual(r["status"], "not_found")

    def test_jira_unreachable(self):
        with mock.patch.object(jira, "http_get", side_effect=net.NetError("timed out", None)):
            r = jira.fetch_ticket("CASSANDRA-1", None)
        self.assertEqual(r["status"], "unavailable")


class Siblings(unittest.TestCase):
    def fake_pr(self, number, title, branch, base, body=""):
        return {"number": number, "url": f"u/{number}", "title": title, "body": body, "head_ref": branch,
                "base": base, "state": "open", "merged": False, "draft": False, "head_sha": str(number) * 4}

    def test_backport_set_and_unrelated_mention(self):
        me = self.fake_pr(5201, "CASSANDRA-21649 (4.0)", "21649-4.0", "cassandra-4.0")
        others = {
            5200: self.fake_pr(5200, "CASSANDRA-21649 (4.1)", "21649-4.1", "cassandra-4.1"),
            5198: self.fake_pr(5198, "CASSANDRA-21649 (5.0)", "21649-5.0", "cassandra-5.0"),
            # Mentions the key only as related work in its body; its own ticket is different.
            5300: self.fake_pr(5300, "CASSANDRA-21700: other", "21700", "trunk", body="related to CASSANDRA-21649"),
        }
        ticket = {"remotelinks": [{"url": "https://github.com/apache/cassandra/pull/5200"}]}
        with mock.patch.object(github, "search_pr_numbers", return_value=[5198, 5300, 5201]), \
                mock.patch.object(github, "fetch_pr", side_effect=lambda n, r: others[n]):
            sibs = bundle_mod.discover_siblings(me, "CASSANDRA-21649", ticket, None)
        self.assertEqual({s["number"]: s["base"] for s in sibs},
                         {5201: "cassandra-4.0", 5200: "cassandra-4.1", 5198: "cassandra-5.0"})
        self.assertTrue(next(s for s in sibs if s["number"] == 5201)["is_self"])


class PrNotFound(unittest.TestCase):
    def test_missing_pr_raises(self):
        with mock.patch.object(github, "gh_json", side_effect=net.NetError("gh: Not Found (HTTP 404)", 404)):
            with self.assertRaises(github.PRNotFound):
                github.fetch_pr(999999, None)


class Clone(unittest.TestCase):
    def test_first_run_clones(self):
        with tempfile.TemporaryDirectory() as d:
            calls = []

            def runner(cmd, capture_output, text):
                calls.append(cmd)
                os.makedirs(os.path.join(cmd[-1], ".git"))
                return subprocess.CompletedProcess(cmd, 0, "", "")

            self.assertTrue(clone.ensure(os.path.join(d, "c"), runner=runner))
            self.assertEqual(calls[0][:2], ["git", "clone"])
            self.assertNotIn("--filter=blob:none", calls[0])  # blame needs local history
            # Subsequent run: no clone.
            self.assertFalse(clone.ensure(os.path.join(d, "c"), runner=runner))
            self.assertEqual(len(calls), 1)

    def test_fetch_only_pr_head_and_base(self):
        with mock.patch.object(clone, "_git") as g:
            clone.fetch("/c", 5201, "cassandra-4.0")
        args = g.call_args[0]
        self.assertIn("+refs/pull/5201/head:refs/cpr/pr/5201", args)
        self.assertIn("+refs/heads/cassandra-4.0:refs/remotes/origin/cassandra-4.0", args)
        self.assertIn("+refs/heads/trunk:refs/remotes/origin/trunk", args)  # expert history reads trunk
        self.assertEqual(len([a for a in args if a.startswith("+refs/")]), 3)
        with mock.patch.object(clone, "_git") as g:
            clone.fetch("/c", 5202, "trunk")
        self.assertEqual(len([a for a in g.call_args[0] if a.startswith("+refs/")]), 2)

    def test_changed_files_in_real_repo(self):
        with tempfile.TemporaryDirectory() as d:
            def git(*a):
                subprocess.run(["git", "-C", d, *a], check=True, capture_output=True)
            git("init", "-q", "-b", "trunk")
            git("config", "user.email", "t@t")
            git("config", "user.name", "t")
            with open(os.path.join(d, "a.txt"), "w") as f:
                f.write("one\n")
            git("add", ".")
            git("commit", "-qm", "base")
            base = subprocess.run(["git", "-C", d, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
            git("mv", "a.txt", "b.txt")
            with open(os.path.join(d, "c.txt"), "w") as f:
                f.write("x\ny\n")
            git("add", ".")
            git("commit", "-qm", "change")
            git("update-ref", "refs/cpr/pr/1", "HEAD")
            files = {f["path"]: f for f in clone.changed_files(d, base, 1)}
        self.assertEqual(files["b.txt"]["status"], "R")
        self.assertEqual(files["b.txt"]["previous_path"], "a.txt")
        self.assertEqual((files["c.txt"]["status"], files["c.txt"]["additions"]), ("A", 2))


class OfflineCache(unittest.TestCase):
    def test_offline_rerender_uses_saved_bundle(self):
        from tests.helpers import bundle
        with tempfile.TemporaryDirectory() as d:
            b = bundle()
            bundle_mod.save(b, d)
            with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network used")), \
                    mock.patch("subprocess.run", side_effect=AssertionError("subprocess used")):
                again = bundle_mod.load_cached(d, b["pr"]["number"])
        self.assertEqual(again["pr"]["head_sha"], b["pr"]["head_sha"])

    def test_offline_with_no_cache(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(bundle_mod.IngestError):
                bundle_mod.load_cached(d, 1234)

    def test_recorder_replays_offline(self):
        with tempfile.TemporaryDirectory() as d:
            online = net.Recorder(d)
            with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, '{"a": 1}', "")):
                net.gh_json("repos/apache/cassandra/pulls/1", recorder=online)
            offline = net.Recorder(d, offline=True)
            with mock.patch("subprocess.run", side_effect=AssertionError("network used")):
                self.assertEqual(net.gh_json("repos/apache/cassandra/pulls/1", recorder=offline), {"a": 1})
                with self.assertRaises(net.OfflineMiss):
                    net.gh_json("repos/apache/cassandra/pulls/2", recorder=offline)


class Roster(unittest.TestCase):
    def test_cache_fresh_stale_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "roster.json")
            fresh = {"fetched_at": 1000, "committers": {"bob": "Bob"}, "pmc": []}
            r = roster.load(path, now=1000, fetch=lambda: fresh)
            self.assertEqual(r["status"], "ok")
            # Within 24h: no refetch.
            r = roster.load(path, now=1000 + 3600, fetch=lambda: (_ for _ in ()).throw(AssertionError()))
            self.assertEqual(r["status"], "ok")
            # Expired and fetch fails: stale cache is used.
            r = roster.load(path, now=1000 + 90000, fetch=lambda: (_ for _ in ()).throw(net.NetError("down")))
            self.assertEqual(r["status"], "stale")
        with tempfile.TemporaryDirectory() as d:
            r = roster.load(os.path.join(d, "r.json"), fetch=lambda: (_ for _ in ()).throw(net.NetError("down")))
            self.assertEqual(r["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
