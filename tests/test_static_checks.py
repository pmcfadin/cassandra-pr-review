"""static-analysis: checks over bundle["static_analysis"] and commit.perf-structure."""

import unittest

from cpr import checks
from tests.helpers import bundle, result, ticket, with_files


def tool(status="ran", **kw):
    t = {"status": status, "version": "10.26.1", "reason": None, "files_expected": 1, "files_analyzed": 1,
         "seconds": 1.0}
    t.update(kw)
    return t


def sa(**kw):
    d = {"status": "ran", "reason": None, "base_branch": "trunk",
         "tools": {"checkstyle": tool(), "pmd": tool(version="7.0"), "cpd": tool(version="7.0")},
         "changed_java": [], "checkstyle": [], "complexity": {"threshold": 15, "methods": [], "findings": []},
         "duplication": [], "commits": []}
    d.update(kw)
    return d


def finding(cls="introduced", **kw):
    f = {"tool": "checkstyle", "rule": "Rule", "file": "src/java/A.java", "base_file": None, "class": "A",
         "method_sig": "m()", "line": 10, "score": None, "message": "bad", "classification": cls}
    f.update(kw)
    return f


def run(b):
    return checks.run_all(b)


def get(b, cid):
    return result(run(b), cid)


def with_sa(**kw):
    return bundle(static_analysis=sa(**kw))


class Checkstyle(unittest.TestCase):
    def test_not_run_is_unknown(self):
        r = get(bundle(), "static.checkstyle")
        self.assertEqual(r["status"], "unknown")
        self.assertIn("did not run", r["summary"])

    def test_branch_without_config_is_unknown(self):
        b = with_sa(tools={"checkstyle": tool("unknown", reason="cassandra-4.0 has no checkstyle config"),
                           "pmd": tool(), "cpd": tool()})
        r = get(b, "static.checkstyle")
        self.assertEqual(r["status"], "unknown")
        self.assertIn("no checkstyle config", r["summary"])

    def test_introduced_error_warns_with_action(self):
        b = with_sa(checkstyle=[finding(), finding("pre-existing", line=3), finding("fixed", line=4)])
        r = get(b, "static.checkstyle")
        self.assertEqual(r["status"], "warn")
        self.assertTrue(r["action_required"])
        self.assertIn("src/java/A.java:10", r["evidence"][0]["text"])
        self.assertIn("1 pre-existing", r["evidence"][-1]["text"])
        self.assertIn("1 fixed", r["evidence"][-1]["text"])

    def test_clean_passes(self):
        b = with_sa(checkstyle=[finding("pre-existing")])
        self.assertEqual(get(b, "static.checkstyle")["status"], "pass")

    def test_file_missing_from_output_is_unknown(self):
        b = with_sa(tools={"checkstyle": tool(files_expected=3, files_analyzed=2), "pmd": tool(), "cpd": tool()})
        r = get(b, "static.checkstyle")
        self.assertEqual(r["status"], "unknown")
        self.assertIn("1 not analyzed", r["summary"])

    def test_not_applicable_tool_and_no_java(self):
        b = with_sa(tools={"checkstyle": tool("not-applicable", reason="no files"), "pmd": tool(), "cpd": tool()})
        self.assertEqual(get(b, "static.checkstyle")["status"], "not-applicable")
        b = bundle(static_analysis=sa(status="unavailable", reason="no changed Java files"))
        self.assertEqual(get(b, "static.checkstyle")["status"], "not-applicable")
        b = bundle(static_analysis=sa(status="unavailable", reason="no JDK"))
        self.assertEqual(get(b, "static.checkstyle")["status"], "unknown")


class Complexity(unittest.TestCase):
    def method(self, base, head, cls="introduced-new-method", name="m()"):
        return {"file": "src/java/A.java", "class": "A", "method_sig": name, "base": base, "head": head,
                "touched": True, "classification": cls}

    def test_simplified_method_passes_with_delta(self):
        m = self.method(6, 2, "pre-existing-improved", "delete(Descriptor, Set<Component>)")
        r = get(with_sa(complexity={"threshold": 15, "methods": [m], "findings": []}), "static.complexity")
        self.assertEqual(r["status"], "pass")
        self.assertIn("A.delete(Descriptor, Set<Component>)`: 6 → 2", r["evidence"][0]["text"])

    def test_introduced_over_threshold_is_a_note(self):
        m1 = self.method(None, 20, name="big()")
        m2 = self.method(3, 4, "pre-existing-touched", "small()")
        f = finding(tool="pmd", score=20, method_sig="big()", rule="CognitiveComplexity")
        r = get(with_sa(complexity={"threshold": 15, "methods": [m2, m1], "findings": [f]}), "static.complexity")
        self.assertEqual(r["status"], "warn")
        self.assertFalse(r["action_required"])
        self.assertIn("new → 20", r["evidence"][0]["text"])
        self.assertIn("3 → 4", r["evidence"][1]["text"])

    def test_other_rules_do_not_count_as_cognitive(self):
        m1 = self.method(None, 20, name="big()")
        f = finding(tool="pmd", score=20, method_sig="big()", rule="CyclomaticComplexity")
        r = get(with_sa(complexity={"threshold": 15, "methods": [m1], "findings": [f]}), "static.complexity")
        self.assertEqual(r["status"], "pass")
        self.assertIn("1 CyclomaticComplexity", r["evidence"][0]["text"])

    def test_removed_method_and_pre_existing_finding(self):
        m = self.method(9, None, "fixed")
        f = finding("pre-existing-touched", tool="pmd", score=30)
        r = get(with_sa(complexity={"threshold": 15, "methods": [m], "findings": [f]}), "static.complexity")
        self.assertEqual(r["status"], "pass")
        self.assertIn("9 → removed", r["evidence"][0]["text"])

    def test_pmd_missing_is_unknown(self):
        b = with_sa(tools={"checkstyle": tool(), "pmd": tool("unknown", reason="PMD not installed"), "cpd": tool()})
        self.assertEqual(get(b, "static.complexity")["status"], "unknown")


class Duplication(unittest.TestCase):
    def test_introduced_is_a_note(self):
        d = {"tokens": 120, "lines": 15, "introduced": True,
             "occurrences": [{"file": "a.java", "line": 1, "endline": 15}, {"file": "b.java", "line": 5, "endline": 20}]}
        r = get(with_sa(duplication=[d]), "static.duplication")
        self.assertEqual(r["status"], "warn")
        self.assertFalse(r["action_required"])
        self.assertIn("b.java:5-20", r["evidence"][0]["text"])

    def test_pre_existing_passes_and_missing_tool_unknown(self):
        d = {"tokens": 120, "lines": 15, "introduced": False, "occurrences": []}
        self.assertEqual(get(with_sa(duplication=[d]), "static.duplication")["status"], "pass")
        b = with_sa(tools={"checkstyle": tool(), "pmd": tool(), "cpd": tool("unknown", reason="no cpd")})
        self.assertEqual(get(b, "static.duplication")["status"], "unknown")


class Superseded(unittest.TestCase):
    def test_superseded_when_checkstyle_ran(self):
        b = with_sa()
        for cid in ("static.banned-api", "static.deprecated-since"):
            r = get(b, cid)
            self.assertEqual(r["status"], "not-applicable")
            self.assertIn("static.checkstyle", r["summary"])

    def test_approximation_label_otherwise(self):
        b = with_files(bundle(), [("src/java/A.java", ["long t = System.currentTimeMillis();",
                                                       "@Deprecated"], False)])
        for cid in ("static.banned-api", "static.deprecated-since"):
            r = get(b, cid)
            self.assertEqual(r["status"], "warn")
            self.assertIn("approximation of checkstyle", r["summary"])
        b["static_analysis"] = sa(tools={"checkstyle": tool("unknown"), "pmd": tool(), "cpd": tool()})
        self.assertEqual(get(b, "static.banned-api")["status"], "warn")


SRC = "src/java/org/apache/cassandra/db/Mutation.java"
BENCH = "test/microbench/org/apache/cassandra/test/microbench/MutationBench.java"


def perf_bundle(commits, files=(SRC, BENCH), **kw):
    b = bundle(static_analysis=sa(commits=commits), **kw)
    return with_files(b, [(p, ["x"], False) for p in files])


def c(sha, subject, *paths):
    return {"sha": sha * 40, "subject": subject, "paths": list(paths)}


class PerfStructure(unittest.TestCase):
    def test_bench_after_change_asks_for_action(self):
        r = get(perf_bundle([c("1", "Change", SRC), c("2", "Add bench", BENCH)]), "commit.perf-structure")
        self.assertEqual(r["status"], "warn")
        self.assertTrue(r["action_required"])
        texts = " ".join(e["text"] for e in r["evidence"])
        self.assertIn("test/microbench", texts)
        self.assertIn("Add bench", texts)

    def test_bench_first_passes(self):
        r = get(perf_bundle([c("1", "Add bench", BENCH), c("2", "Change", SRC)]), "commit.perf-structure")
        self.assertEqual(r["status"], "pass")

    def test_fixup_commit_ignored_for_ordering(self):
        commits = [c("1", "Add bench", BENCH), c("2", "fixup! x", SRC), c("3", "Change", SRC)]
        self.assertEqual(get(perf_bundle(commits), "commit.perf-structure")["status"], "pass")

    def test_combined_is_a_note(self):
        r = get(perf_bundle([c("1", "Change and bench", SRC, BENCH)]), "commit.perf-structure")
        self.assertEqual(r["status"], "warn")
        self.assertFalse(r["action_required"])

    def test_no_benchmark_is_a_note(self):
        t = ticket(labels=["performance"])
        b = perf_bundle([c("1", "Change", SRC)], files=(SRC,), jira={"status": "ok", "error": None, "ticket": t})
        r = get(b, "commit.perf-structure")
        self.assertEqual(r["status"], "warn")
        self.assertFalse(r["action_required"])
        self.assertIn("JIRA label", " ".join(e["text"] for e in r["evidence"]))

    def test_not_a_perf_pr(self):
        r = get(bundle(static_analysis=sa(commits=[c("1", "Fix", SRC)])), "commit.perf-structure")
        self.assertEqual(r["status"], "not-applicable")

    def test_one_medium_signal_is_not_enough_two_are(self):
        b = bundle(static_analysis=sa(commits=[c("1", "Change", SRC)]))
        b["pr"]["title"] = "CASSANDRA-1: Reduce allocation in reads (trunk)"
        self.assertEqual(get(b, "commit.perf-structure")["status"], "not-applicable")
        b["pr"]["body"] = "Includes a JMH benchmark."
        self.assertEqual(get(b, "commit.perf-structure")["status"], "warn")

    def test_commits_unavailable_is_unknown(self):
        b = with_files(bundle(), [(BENCH, ["x"], False), (SRC, ["x"], False)])
        self.assertEqual(get(b, "commit.perf-structure")["status"], "unknown")

    def test_component_signal(self):
        t = ticket(components=["Test/benchmark"])
        b = bundle(static_analysis=sa(commits=[c("1", "b", BENCH), c("2", "c", SRC)]),
                   jira={"status": "ok", "error": None, "ticket": t})
        self.assertEqual(get(b, "commit.perf-structure")["status"], "pass")


if __name__ == "__main__":
    unittest.main()


class ComplexityTests(unittest.TestCase):
    def test_test_methods_not_in_headline(self):
        f = finding(tool="pmd", score=40, method_sig="t()", rule="CognitiveComplexity", file="test/unit/ATest.java")
        r = get(with_sa(complexity={"threshold": 15, "methods": [], "findings": [f]}), "static.complexity")
        self.assertEqual(r["status"], "pass")
        self.assertIn("1 test method(s)", r["evidence"][0]["text"])
