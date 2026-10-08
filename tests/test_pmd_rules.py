"""PMD full catalog: ruleset, parsing, introduced classification, baseline, aux classpath, check, model."""

import json
import os
import shutil
import tempfile
import time
import unittest
import zipfile

from cpr import checks, model
from cpr.staticanalysis import auxpath, baseline, classify, rate, ruleset, run, typerules
from tests.helpers import bundle, result

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULESET = os.path.join(REPO, "cpr", "config", "pmd-pr.xml")

CATEGORY_XML = """<ruleset name="x" xmlns="http://pmd.sourceforge.net/ruleset/2.0.0">
 <rule name="Live" language="java" class="a.B"/>
 <rule name="Old" language="java" class="a.C" deprecated="true"/>
 <rule name="Renamed" ref="Live" deprecated="true"/>
 <rule name="LoosePackageCoupling" language="java" class="a.D"/>
 <rule name="CognitiveComplexity" language="java" class="a.E"/>
</ruleset>"""


class Ruleset(unittest.TestCase):
    def test_generate_skips_deprecated_renamed_misconfigured_and_complexity(self):
        with tempfile.TemporaryDirectory() as d:
            jar = os.path.join(d, "pmd-java.jar")
            with zipfile.ZipFile(jar, "w") as z:
                for cat in ruleset.CATEGORIES:
                    z.writestr(f"category/java/{cat}.xml", CATEGORY_XML.replace("Live", "Live" + cat))
            text = ruleset.generate(jar)
        cat = ruleset.catalog(text)
        self.assertEqual(set(cat.values()), set(ruleset.CATEGORIES))
        self.assertEqual(set(cat), {"Live" + c for c in ruleset.CATEGORIES})
        for bad in ("Old", "Renamed", "LoosePackageCoupling"):
            self.assertNotIn(f"/{bad}\"", text)

    def test_checked_in_ruleset_covers_eight_categories_and_keeps_the_complexity_rules(self):
        with open(RULESET) as f:
            text = f.read()
        cat = ruleset.catalog(text)
        self.assertEqual(set(cat.values()), set(ruleset.CATEGORIES))
        self.assertGreater(len(cat), 250)
        for r in ruleset.COMPLEXITY:
            self.assertIn(f"design.xml/{r}", text)
            self.assertNotIn(r, cat)
        self.assertIn("MethodBody", text)
        self.assertNotIn("LoosePackageCoupling", cat)
        self.assertIn("CloseResource", cat)

    def test_baseline_ruleset_drops_complexity_and_method_body(self):
        with open(RULESET) as f:
            text = baseline.baseline_ruleset(f.read())
        for r in ruleset.COMPLEXITY:
            self.assertNotIn(r, text)
        self.assertNotIn('name="MethodBody"', text)
        with open(RULESET) as f:
            self.assertEqual(ruleset.catalog(text), ruleset.catalog(f.read()))


XML = """<?xml version="1.0"?><pmd xmlns="http://pmd.sourceforge.net/report/2.0.0" version="7">
<file name="/r/src/java/A.java">
<violation beginline="5" endline="9" rule="CloseResource" ruleset="Error Prone" class="A" method="m">  Ensure that resources
 like this are closed </violation>
<violation beginline="12" endline="12" rule="CognitiveComplexity" ruleset="Design" class="A" method="m">The method 'm()' has a cognitive complexity of 20, current threshold is 15</violation>
<violation beginline="3" endline="30" rule="MethodBody" ruleset="x" class="A" method="m">body</violation>
<violation beginline="7" endline="7" rule="NullAssignment" ruleset="Error Prone" class="A">x</violation>
</file></pmd>"""


class Parse(unittest.TestCase):
    def test_other_rules_go_to_v_with_category_and_collapsed_message(self):
        files, _ = run.parse_pmd(XML, "/r")
        f = files["src/java/A.java"]
        self.assertEqual(f["v"], [["CloseResource", "errorprone", 5, 9, "Ensure that resources like this are closed"],
                                  ["NullAssignment", "errorprone", 7, 7, "x"]])
        self.assertEqual(f["m"], [["A", "m()", "CognitiveComplexity", 20, 12]])  # a catalog rule's method never becomes a score
        self.assertEqual(f["bodies"], [["A", "m", 3, 30]])

    def test_streaming_counts_files_per_rule(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "r.xml")
            with open(p, "w") as f:
                f.write(XML.replace("</pmd>", '<file name="/r/B.java"><violation beginline="1" endline="1" rule="NullAssignment" '
                                    'ruleset="Error Prone">y</violation><violation beginline="2" endline="2" rule="NullAssignment" '
                                    'ruleset="Error Prone">y</violation></file><error filename="/r/C.java" msg="boom"/></pmd>'))
            hits, listed, errors, counts = run.count_pmd_files(p)
        self.assertEqual(hits["NullAssignment"], 2)  # two files, not three violations
        self.assertEqual(counts["NullAssignment"], 3)  # the rate test counts violations
        self.assertEqual(hits["CloseResource"], 1)
        self.assertEqual(listed, 2)
        self.assertEqual(errors, [("/r/C.java", "boom")])

    def test_command_adds_aux_classpath_and_threads_only_when_given(self):
        base = run.pmd_command("pmd", "r.xml", "l", "o")
        self.assertNotIn("--aux-classpath", base)
        self.assertNotIn("-t", base)
        cmd = run.pmd_command("pmd", "r.xml", "l", "o", aux="/c:/j.jar", threads=4)
        self.assertEqual(cmd[cmd.index("--aux-classpath") + 1], "/c:/j.jar")
        self.assertEqual(cmd[cmd.index("-t") + 1], "4")


def v(rule, line, cat="errorprone"):
    return [rule, cat, line, line, f"{rule} here"]


def entry(*vs):
    return {"bodies": [], "m": [], "v": list(vs)}


class Introduced(unittest.TestCase):
    def change(self, status="M", path="src/java/A.java"):
        return {"path": path, "base_path": None if status == "A" else path, "status": status, "test": path.startswith("test/")}

    def test_only_violations_on_added_lines_count(self):
        head = {"src/java/A.java": entry(v("CloseResource", 10), v("CloseResource", 50), v("NullAssignment", 51))}
        out = classify.classify_rules([self.change()], {"src/java/A.java": entry()}, head, {"src/java/A.java": [(48, 52)]})
        self.assertEqual(out["CloseResource"]["introduced"], 1)
        self.assertEqual(out["CloseResource"]["pre_existing"], 1)
        self.assertEqual(out["CloseResource"]["locations"], [["src/java/A.java", 50, "CloseResource here"]])
        self.assertEqual(out["NullAssignment"]["introduced"], 1)

    def test_firing_on_an_unchanged_line_that_also_fires_in_base_is_not_introduced(self):
        head = {"src/java/A.java": entry(v("CloseResource", 10))}
        out = classify.classify_rules([self.change()], {"src/java/A.java": entry(v("CloseResource", 10))}, head,
                                      {"src/java/A.java": [(40, 41)]})
        self.assertEqual(out["CloseResource"]["introduced"], 0)

    def test_new_file_counts_everything_and_tests_are_tallied(self):
        c = self.change("A", "test/unit/T.java")
        out = classify.classify_rules([c], {}, {"test/unit/T.java": entry(v("A", 1), v("A", 2))}, {})
        self.assertEqual((out["A"]["introduced"], out["A"]["in_tests"]), (2, 2))

    def test_no_line_map_falls_back_to_count_above_base(self):
        head = {"src/java/A.java": entry(v("R", 1), v("R", 2), v("R", 3), v("S", 4))}
        base = {"src/java/A.java": entry(v("R", 9), v("R", 8))}
        out = classify.classify_rules([self.change()], base, head, {})
        self.assertEqual(out["R"]["introduced"], 1)
        self.assertEqual(out["R"]["locations"][0][1], 3)  # the last one
        self.assertEqual(out["S"]["introduced"], 1)

    def test_locations_are_capped_but_counts_stay_exact(self):
        c = self.change("A")
        out = classify.classify_rules([c], {}, {"src/java/A.java": entry(*[v("R", i) for i in range(1, 31)])}, {}, cap=5)
        self.assertEqual((out["R"]["introduced"], len(out["R"]["locations"])), (30, 5))

    def test_deleted_files_are_ignored(self):
        self.assertEqual(classify.classify_rules([{**self.change(), "status": "D"}], {}, {}, {}), {})


class Baseline(unittest.TestCase):
    def data(self, tip, built_at, hits=None, n=100):
        return {"version": baseline.VERSION, "branch": "trunk", "tip": tip, "built_at": built_at, "files_scanned": n,
                "loc": 50000, "files_hit": hits or {"R": 30}, "violations": {"R": 40}}

    def save(self, d, data, rsha="abcdef12"):
        with open(os.path.join(d, baseline.file_name("trunk", data["tip"], "pmd-7", rsha)), "w") as f:
            json.dump(data, f)

    def test_house_style_is_a_share_of_the_branch_files(self):
        self.assertEqual(baseline.shares(self.data("t" * 40, 0, {"R": 30, "S": 24})), {"R": 0.30, "S": 0.24})

    def test_exact_baseline_is_reused_without_running_anything(self):
        with tempfile.TemporaryDirectory() as d:
            self.save(d, self.data("a" * 40, 1))
            got, source, note = baseline.obtain(d, "no-repo", "ref", "trunk", "a" * 40, "pmd-not-run", {}, "", "pmd-7", "abcdef12",
                                                1, 1, log=lambda m: None)
        self.assertEqual((got["tip"], source, note), ("a" * 40, "cached", None))

    def test_a_younger_baseline_is_reused_when_the_tip_moved_and_an_old_one_is_not(self):
        now = time.time()
        with tempfile.TemporaryDirectory() as d:
            self.save(d, self.data("a" * 40, now - 3 * 86400))
            self.save(d, self.data("b" * 40, now - 10 * 86400))
            self.assertEqual(baseline.newest_recent(d, "trunk", "pmd-7", "abcdef12", now)["tip"], "a" * 40)
            logs = []
            got, source, note = baseline.obtain(d, "no-repo", "ref", "trunk", "c" * 40, "x", {}, "", "pmd-7", "abcdef12", 1, 1,
                                                log=logs.append, now=now)
            self.assertEqual(source, "reused")
            self.assertIn("3.0 days", note)
            self.assertTrue(logs)
            self.assertIsNone(baseline.newest_recent(d, "trunk", "pmd-7", "abcdef12", now + 20 * 86400))
            self.assertIsNone(baseline.newest_recent(d, "trunk", "pmd-7", "other999", now))  # other ruleset: not reusable

    def test_a_failed_build_returns_the_reason(self):
        with tempfile.TemporaryDirectory() as d:
            got, source, note = baseline.obtain(d, os.path.join(d, "no-clone"), "ref", "trunk", "c" * 40, "x", {}, "", "pmd-7",
                                                "abcdef12", 1, 1, log=lambda m: None)
        self.assertIsNone(got)
        self.assertIsNone(source)
        self.assertTrue(note)

    def test_archive_writes_only_java_sources_under_src_java(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, "repo")
            for rel, text in (("src/java/a/A.java", "class A {}"), ("src/java/a/notes.txt", "x"), ("test/unit/T.java", "class T {}")):
                os.makedirs(os.path.dirname(os.path.join(repo, rel)), exist_ok=True)
                with open(os.path.join(repo, rel), "w") as f:
                    f.write(text)
            for args in (["init", "-q"], ["add", "."], ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
                                                        "commit", "-q", "-m", "x"]):
                subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True)
            dest = os.path.join(d, "out")
            self.assertEqual(baseline.archive_sources(repo, "HEAD", dest), (1, 1))  # one file, one non-blank line
            self.assertEqual(os.listdir(os.path.join(dest, "src", "java", "a")), ["A.java"])
            self.assertEqual(baseline.archive_sources(repo, "HEAD", dest, exclude=("src/java/a/",)), (0, 0))
            with self.assertRaises(Exception):
                baseline.archive_sources(repo, "no-such-ref", dest)

    def test_touched_file_density_fallback(self):
        data = baseline.from_touched({"a": entry(v("R", 1), v("R", 2)), "b": entry(v("R", 1), v("S", 1)), "c": entry()})
        self.assertEqual((data["files_scanned"], data["files_hit"]), (3, {"R": 2, "S": 1}))
        self.assertEqual(data["loc"], 0)  # a sample has no rate to judge against

    def test_a_baseline_without_violation_counts_is_rebuilt_not_loaded(self):
        old = {"branch": "trunk", "tip": "a" * 40, "built_at": time.time(), "files_scanned": 100, "files_hit": {"R": 30}}
        with tempfile.TemporaryDirectory() as d:
            self.save(d, old)
            self.assertIsNone(baseline.newest_recent(d, "trunk", "pmd-7", "abcdef12"))
            self.assertIsNone(baseline._load(os.path.join(d, baseline.file_name("trunk", "a" * 40, "pmd-7", "abcdef12"))))


class RulesSection(unittest.TestCase):
    """staticanalysis._rules: introduced violations joined with the baseline's shares."""

    extra = ()

    def section(self, obtained):
        from unittest import mock
        from cpr import staticanalysis as sa_mod
        cfg = {"caps": {"baseline_seconds": 1, "pmd_threads": 1}, "exclude": [], "house_style_share": 0.25, "usual_p": 0.01}
        changed = [{"path": "src/java/A.java", "base_path": "src/java/A.java", "status": "M", "test": False}]
        head = {"src/java/A.java": entry(v("CloseResource", 5), v("ShortVariable", 6, "codestyle"), *self.extra)}
        base = {"src/java/A.java": entry()}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sa_mod.baseline, "obtain", return_value=obtained), \
                mock.patch.object(sa_mod.clone_mod, "_git", return_value="a" * 40 + "\n"):
            return sa_mod._rules(cfg, d, "repo", "trunk", changed, base, head, {"src/java/A.java": [(1, 10)]},
                                 ("pmd-7", RULESET, "f" * 40, True, None, "no build; without type info: x"), {}, "pmd", lambda m: None,
                                 self.root)

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        os.makedirs(os.path.join(self.root, "src", "java"))
        with open(os.path.join(self.root, "src", "java", "A.java"), "w") as f:
            f.write("class A {\n" * 10)

    def test_house_flag_comes_from_the_baseline_share(self):
        data = {"tip": "a" * 40, "files_scanned": 100, "files_hit": {"ShortVariable": 45, "CloseResource": 1}, "seconds": 3,
                "loc": 0, "violations": {}}
        out = self.section((data, "cached", None))
        by = {r["rule"]: r for r in out["rules"]}
        self.assertFalse(by["CloseResource"]["house"])
        self.assertTrue(by["ShortVariable"]["house"])
        self.assertEqual(out["house_style"], [{"rule": "ShortVariable", "category": "codestyle", "share": 0.45}])
        self.assertEqual((out["rules_run"], out["type_info"], out["baseline"]["source"]), (296, False, "cached"))

    def test_an_unbuildable_baseline_falls_back_to_the_touched_files_and_says_so(self):
        out = self.section((None, None, "timed out after 900 s"))
        self.assertEqual(out["baseline"]["source"], "touched-files")
        self.assertIn("timed out", out["baseline"]["note"])
        self.assertEqual(out["status"], "ran")


class Aux(unittest.TestCase):
    def status(self, d, number, head, **kw):
        p = os.path.join(d, "build-runs", str(number), head)
        os.makedirs(p)
        with open(os.path.join(p, "status.json"), "w") as f:
            json.dump({"head": head, "status": "pass", **kw}, f)

    def test_without_a_build_there_is_no_classpath_and_the_note_says_why(self):
        with tempfile.TemporaryDirectory() as d:
            cp, note = auxpath.resolve(d, 1, "h" * 40)
        self.assertIsNone(cp)
        self.assertIn("without type info", note)

    def test_a_build_that_did_not_keep_its_classes_gives_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.status(d, 1, "h" * 40)
            cp, note = auxpath.resolve(d, 1, "h" * 40)
        self.assertIsNone(cp)
        self.assertIn("did not keep", note)

    def test_existing_classes_and_jars_form_the_classpath_and_missing_ones_are_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            classes, jar = os.path.join(d, "classes"), os.path.join(d, "a.jar")
            os.makedirs(classes)
            open(jar, "w").close()
            self.status(d, 1, "h" * 40, classpath={"classes": [classes, os.path.join(d, "gone")], "jars": [jar, os.path.join(d, "x.jar")]})
            cp, note = auxpath.resolve(d, 1, "h" * 40)
        self.assertEqual(cp, os.pathsep.join([classes, jar]))
        self.assertIn("with type info", note)

    def test_a_status_for_another_head_is_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            self.status(d, 1, "a" * 40, classpath={"classes": [d], "jars": []})
            self.assertIsNone(auxpath.resolve(d, 1, "b" * 40)[0])


def rule(name, cat, n, tests=0, house=False, locs=None):
    return {"rule": name, "category": cat, "introduced": n, "in_tests": tests, "pre_existing": 3, "share": 0.5 if house else 0.01,
            "house": house, "locations": locs if locs is not None else [["src/java/A.java", i + 1, "m"] for i in range(min(n, 200))]}


def sa(rules, **kw):
    pr = {"status": "ran", "reason": None, "rules_run": 296, "type_info": False, "type_note": "no build; without type info: x",
          "threshold": 0.25, "baseline": {"source": "cached", "branch": "trunk", "tip": "a" * 40, "files": 3000},
          "house_style": [{"rule": "LocalVariableCouldBeFinal", "category": "codestyle", "share": 0.6}], "rules": rules}
    pr.update(kw)
    t = {"status": "ran", "version": "7.28.0", "reason": None, "files_expected": 1, "files_analyzed": 1, "seconds": 1}
    return {"status": "ran", "reason": None, "base_branch": "trunk",
            "tools": {"checkstyle": t, "pmd": t, "cpd": t}, "changed_java": [], "checkstyle": [],
            "complexity": {"threshold": 15, "methods": [], "findings": []}, "duplication": [], "commits": [], "pmd_rules": pr}


def run_check(s):
    return result(checks.run_all({**bundle(), "static_analysis": s}), "static.pmd-rules")


class Check(unittest.TestCase):
    def test_red_category_outside_house_style_warns_and_is_advisory(self):
        r = run_check(sa([rule("CloseResource", "errorprone", 2), rule("ShortVariable", "codestyle", 40)]))
        self.assertEqual(r["status"], "warn")
        self.assertIn("CloseResource 2", r["summary"])
        self.assertFalse(r["blocking"])

    def test_house_style_red_rule_does_not_warn(self):
        r = run_check(sa([rule("CloseResource", "errorprone", 5, house=True)]))
        self.assertEqual(r["status"], "pass")

    def test_only_tests_do_not_warn(self):
        self.assertEqual(run_check(sa([rule("CloseResource", "errorprone", 2, tests=2)]))["status"], "pass")

    def test_yellow_and_green_pass_with_counts(self):
        r = run_check(sa([rule("TooManyMethods", "design", 4)]))
        self.assertEqual(r["status"], "pass")
        self.assertIn("4 lower-severity", r["summary"])

    def test_without_the_catalog_or_pmd_it_is_unknown_never_pass(self):
        s = sa([])
        s["pmd_rules"] = {"status": "unavailable", "reason": "PMD not installed"}
        self.assertEqual(run_check(s)["status"], "unknown")
        s = sa([])
        del s["pmd_rules"]
        self.assertEqual(run_check(s)["status"], "unknown")
        s = sa([])
        s["tools"]["pmd"]["status"] = "unknown"
        self.assertEqual(run_check(s)["status"], "unknown")

    def test_a_partial_run_with_nothing_red_is_unknown(self):
        s = sa([rule("TooManyMethods", "design", 4)])
        s["tools"]["pmd"].update(files_expected=3, files_analyzed=2, reason="1 file(s) failed to parse: A.java")
        self.assertEqual(run_check(s)["status"], "unknown")

    def test_partial_run_with_red_still_warns_and_names_the_skip(self):
        s = sa([rule("CloseResource", "errorprone", 1)])
        s["tools"]["pmd"].update(files_expected=3, files_analyzed=2, reason="1 file(s) failed to parse: A.java")
        r = run_check(s)
        self.assertEqual(r["status"], "warn")
        self.assertTrue(any("skipped" in e["text"] for e in r["evidence"]))

    def test_type_info_missing_is_stated(self):
        r = run_check(sa([rule("TooManyMethods", "design", 4)]))
        self.assertTrue(any("without type info" in e["text"] for e in r["evidence"]))


class Model(unittest.TestCase):
    def block(self, rules, **kw):
        return model.pmd_rules_block({"static_analysis": sa(rules, **kw)})

    def test_rows_sort_by_band_then_count_and_house_rules_are_apart_and_unlisted(self):
        b = self.block([rule("ShortVariable", "codestyle", 90, house=True), rule("TooManyMethods", "design", 9),
                        rule("CloseResource", "errorprone", 2), rule("DoNotUseThreads", "multithreading", 7),
                        rule("UnusedPrivateMethod", "bestpractices", 12)])
        self.assertEqual([r["rule"] for r in b["rows"]], ["DoNotUseThreads", "CloseResource", "UnusedPrivateMethod", "TooManyMethods"])
        self.assertEqual([r["band"] for r in b["rows"]], ["red", "red", "yellow", "yellow"])
        self.assertEqual([r["rule"] for r in b["house"]], ["ShortVariable"])
        self.assertEqual(b["house"][0]["locations"], [])
        self.assertEqual((b["introduced"], b["introduced_house"]), (30, 90))
        self.assertEqual(len(b["categories"]), 8)
        by = {c["id"]: c for c in b["categories"]}
        self.assertEqual((by["errorprone"]["band"], by["errorprone"]["introduced"]), ("red", 2))
        self.assertEqual(by["codestyle"]["house"], 90)

    def test_rule_links_to_its_pmd_page(self):
        b = self.block([rule("CloseResource", "errorprone", 1)])
        self.assertEqual(b["rows"][0]["url"], "https://docs.pmd-code.org/pmd-doc-7.28.0/pmd_rules_java_errorprone.html#closeresource")

    def test_locations_capped_per_rule_and_in_total_with_exact_counts(self):
        rules = [rule(f"R{i}", "errorprone", 120) for i in range(50)]
        b = self.block(rules)
        self.assertTrue(all(len(r["locations"]) == 50 for r in b["rows"] if r["locations"]))
        self.assertEqual(sum(len(r["locations"]) for r in b["rows"]), model.PMD_LOCATIONS_TOTAL)
        self.assertEqual([r["introduced"] for r in b["rows"]], [120] * 50)
        self.assertEqual(b["rows"][0]["more"], 70)
        self.assertEqual(b["rows"][-1]["locations"], [])

    def test_test_locations_are_marked(self):
        b = self.block([rule("R", "design", 1, tests=1, locs=[["test/unit/T.java", 4, "m"]])])
        self.assertTrue(b["rows"][0]["locations"][0]["test"])

    def test_unavailable_when_pmd_or_the_catalog_did_not_run(self):
        self.assertEqual(model.pmd_rules_block({})["status"], "unavailable")
        s = sa([])
        s["pmd_rules"] = {"status": "unavailable", "reason": "why"}
        self.assertEqual(model.pmd_rules_block({"static_analysis": s})["reason"], "why")


class Rate(unittest.TestCase):
    def test_poisson_tail_matches_known_values(self):
        self.assertAlmostEqual(rate.poisson_tail(4, 3.0), 0.352768, places=5)
        self.assertEqual(rate.poisson_tail(0, 3.0), 1.0)
        self.assertEqual(rate.poisson_tail(1, 0.0), 0.0)
        self.assertGreater(rate.poisson_tail(60, 1.0), 0.0)
        self.assertLess(rate.poisson_tail(60, 1.0), 1e-60)

    def test_threads_in_a_database_are_usual(self):
        # 4 observed over 2,000 added lines; trunk: 150 in 100,000 lines predicts 3
        usual, mu, p = rate.judge(4, 150, 100_000, 2_000)
        self.assertTrue(usual)
        self.assertAlmostEqual(mu, 3.0)
        self.assertGreater(p, 0.01)

    def test_well_above_the_rate_is_not_usual(self):
        usual, mu, p = rate.judge(12, 150, 100_000, 2_000)
        self.assertFalse(usual)
        self.assertLess(p, 0.01)

    def test_a_rule_trunk_never_breaks_is_never_usual(self):
        self.assertEqual(rate.judge(1, 0, 100_000, 2_000)[0], False)

    def test_no_production_violations_or_no_baseline_lines_judge_nothing(self):
        self.assertEqual(rate.judge(0, 150, 100_000, 2_000), (False, 3.0, None))
        self.assertFalse(rate.judge(2, 150, 0, 2_000)[0])
        self.assertFalse(rate.judge(2, 150, 100_000, 0)[0])

    def test_added_production_lines_skip_blank_lines_tests_and_deleted_files(self):
        with tempfile.TemporaryDirectory() as d:
            for rel, text in (("src/java/A.java", "a\n\nb\n  \nc\nd\n"), ("src/java/N.java", "x\ny\n\nz\n"),
                              ("test/unit/T.java", "t\nt\n")):
                os.makedirs(os.path.dirname(os.path.join(d, rel)), exist_ok=True)
                with open(os.path.join(d, rel), "w") as f:
                    f.write(text)
            changed = [{"path": "src/java/A.java", "status": "M"}, {"path": "src/java/N.java", "status": "A"},
                       {"path": "test/unit/T.java", "status": "A"}, {"path": "src/java/Gone.java", "status": "D"}]
            # A: lines 2-5 added = "", b, "  ", c -> two non-blank; N: whole file, three non-blank
            self.assertEqual(rate.added_production_loc(changed, {"src/java/A.java": [(2, 5)]}, d), 5)


class RateInRulesSection(RulesSection):
    def data(self, **kw):
        return {"tip": "a" * 40, "files_scanned": 100, "files_hit": {"ShortVariable": 45}, "seconds": 3, "loc": 1000,
                "violations": {"CloseResource": 100, "NullAssignment": 0, "ShortVariable": 900, "DoNotUseThreads": 100}, **kw}

    def test_usual_flag_expected_and_p_per_rule(self):
        self.extra = (v("NullAssignment", 7), v("DoNotUseThreads", 8, "multithreading"), v("DoNotUseThreads", 9, "multithreading"))
        out = self.section((self.data(), "cached", None))
        by = {r["rule"]: r for r in out["rules"]}
        self.assertEqual(out["rate"], {"loc": 1000, "added_loc": 10, "available": True})
        self.assertTrue(by["CloseResource"]["usual"])           # 1 observed, 1.0 expected
        self.assertEqual((by["CloseResource"]["production"], by["CloseResource"]["expected"], by["CloseResource"]["trunk"]), (1, 1.0, 100))
        self.assertTrue(by["DoNotUseThreads"]["usual"])         # 2 observed, 1.0 expected: p = 0.26
        self.assertFalse(by["NullAssignment"]["usual"])         # trunk never breaks it
        self.assertFalse(by["ShortVariable"]["usual"])          # house style comes first, not judged by rate
        self.assertTrue(by["ShortVariable"]["house"])

    def test_without_a_baseline_line_count_nothing_is_usual(self):
        out = self.section((self.data(loc=0, violations={}), "cached", None))
        self.assertFalse(out["rate"]["available"])
        self.assertFalse(any(r["usual"] for r in out["rules"]))

    def test_needs_types_comes_from_the_type_rule_list(self):
        out = self.section((self.data(), "cached", None))
        by = {r["rule"]: r for r in out["rules"]}
        self.assertTrue(by["CloseResource"]["needs_types"])
        self.assertFalse(by["ShortVariable"]["needs_types"])


class TypeRules(unittest.TestCase):
    def test_checked_in_list_names_real_catalog_rules_with_a_source(self):
        with open(RULESET) as f:
            cat = ruleset.catalog(f.read())
        rules = typerules.load()
        self.assertGreater(len(rules), 3)
        self.assertEqual({r for r in rules if r not in cat}, set())
        self.assertLessEqual(set(rules.values()), {"docs", "measured"})
        self.assertIn("CloseResource", rules)

    def test_measured_diff_names_rules_whose_count_changes(self):
        self.assertEqual(typerules.measured_diff({"A": 5, "B": 2, "C": 1}, {"A": 5, "B": 0, "D": 3}),
                         {"B": [2, 0], "C": [1, 0], "D": [0, 3]})


def rate_rule(name, cat, n, prod=None, usual=False, expected=1.0, needs=False, tests=0, locs=None):
    r = rule(name, cat, n, tests=tests, locs=locs)
    r.update({"production": n - tests if prod is None else prod, "usual": usual, "expected": expected, "trunk": 10, "p": 0.3,
              "needs_types": needs})
    return r


class UsualAndTypes(unittest.TestCase):
    def block(self, rules, typed=False):
        return model.pmd_rules_block({"static_analysis": sa(rules, type_info=typed, rate={"loc": 1000, "added_loc": 10, "available": True},
                                                            usual_p=0.01)})

    def test_usual_rules_leave_the_table_and_show_observed_vs_expected(self):
        b = self.block([rate_rule("DoNotUseThreads", "multithreading", 4, usual=True, expected=3.2),
                        rate_rule("NullAssignment", "errorprone", 2)])
        self.assertEqual([r["rule"] for r in b["rows"]], ["NullAssignment"])
        self.assertEqual([(r["rule"], r["production"], r["expected"]) for r in b["usual"]], [("DoNotUseThreads", 4, 3.2)])
        self.assertEqual((b["introduced"], b["introduced_usual"]), (2, 4))
        by = {c["id"]: c for c in b["categories"]}
        self.assertEqual((by["multithreading"]["introduced"], by["multithreading"]["usual"]), (0, 4))

    def test_a_usual_rules_test_file_violations_stay_in_the_table(self):
        locs = [["src/java/A.java", 1, "m"], ["test/unit/T.java", 2, "m"], ["test/unit/T.java", 3, "m"]]
        b = self.block([rate_rule("DoNotUseThreads", "multithreading", 3, tests=2, usual=True, locs=locs)])
        self.assertEqual(b["usual"][0]["production"], 1)
        self.assertEqual((b["rows"][0]["introduced"], len(b["rows"][0]["locations"])), (2, 2))
        self.assertTrue(all(x["test"] for x in b["rows"][0]["locations"]))

    def test_type_rules_without_classes_are_marked_last_and_left_out_of_the_tallies(self):
        b = self.block([rate_rule("WrongTestAnnotation", "errorprone", 48, needs=True), rate_rule("TooManyMethods", "design", 2)])
        self.assertEqual([(r["rule"], r["untyped"]) for r in b["rows"]], [("TooManyMethods", False), ("WrongTestAnnotation", True)])
        self.assertEqual((b["introduced"], b["introduced_untyped"], b["untyped_rules"]), (2, 48, 1))

    def test_type_rules_count_normally_with_a_classpath(self):
        b = self.block([rate_rule("WrongTestAnnotation", "errorprone", 48, needs=True)], typed=True)
        self.assertEqual((b["rows"][0]["untyped"], b["introduced"], b["introduced_untyped"]), (False, 48, 0))


class UsualAndTypesCheck(unittest.TestCase):
    def run_(self, rules, typed=False):
        return run_check(sa(rules, type_info=typed))

    def test_a_usual_red_rule_does_not_warn_and_is_named_in_the_evidence(self):
        r = self.run_([rate_rule("DoNotUseThreads", "multithreading", 4, usual=True, expected=3.2)])
        self.assertEqual(r["status"], "pass")
        self.assertTrue(any("DoNotUseThreads 4 vs 3.2 expected" in e["text"] for e in r["evidence"]))

    def test_an_unusual_red_rule_still_warns_beside_a_usual_one(self):
        r = self.run_([rate_rule("DoNotUseThreads", "multithreading", 4, usual=True), rate_rule("NullAssignment", "errorprone", 3)])
        self.assertEqual(r["status"], "warn")
        self.assertIn("NullAssignment 3", r["summary"])
        self.assertNotIn("DoNotUseThreads", r["summary"])

    def test_a_type_rule_without_classes_is_ignored_and_with_classes_counts(self):
        rules = [rate_rule("WrongTestAnnotation", "errorprone", 48, needs=True)]
        r = self.run_(rules)
        self.assertEqual(r["status"], "pass")
        self.assertTrue(any("need compiled classes" in e["text"] for e in r["evidence"]))
        r = self.run_(rules, typed=True)
        self.assertEqual(r["status"], "warn")
        self.assertIn("WrongTestAnnotation 48", r["summary"])

    def test_test_only_violations_of_a_usual_rule_never_warn(self):
        self.assertEqual(self.run_([rate_rule("DoNotUseThreads", "multithreading", 2, tests=2, usual=True)])["status"], "pass")


if __name__ == "__main__":
    unittest.main()
