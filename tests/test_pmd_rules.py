"""PMD full catalog: ruleset, parsing, introduced classification, baseline, aux classpath, check, model."""

import json
import os
import tempfile
import time
import unittest
import zipfile

from cpr import checks, model
from cpr.staticanalysis import auxpath, baseline, classify, ruleset, run
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
            hits, listed, errors = run.count_pmd_files(p)
        self.assertEqual(hits["NullAssignment"], 2)  # two files, not three violations
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
        return {"branch": "trunk", "tip": tip, "built_at": built_at, "files_scanned": n, "files_hit": hits or {"R": 30}}

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
            self.assertEqual(baseline.archive_sources(repo, "HEAD", dest), 1)
            self.assertEqual(os.listdir(os.path.join(dest, "src", "java", "a")), ["A.java"])
            self.assertEqual(baseline.archive_sources(repo, "HEAD", dest, exclude=("src/java/a/",)), 0)
            with self.assertRaises(Exception):
                baseline.archive_sources(repo, "no-such-ref", dest)

    def test_touched_file_density_fallback(self):
        data = baseline.from_touched({"a": entry(v("R", 1), v("R", 2)), "b": entry(v("R", 1), v("S", 1)), "c": entry()})
        self.assertEqual((data["files_scanned"], data["files_hit"]), (3, {"R": 2, "S": 1}))


class RulesSection(unittest.TestCase):
    """staticanalysis._rules: introduced violations joined with the baseline's shares."""

    def section(self, obtained):
        from unittest import mock
        from cpr import staticanalysis as sa_mod
        cfg = {"caps": {"baseline_seconds": 1, "pmd_threads": 1}, "exclude": [], "house_style_share": 0.25}
        changed = [{"path": "src/java/A.java", "base_path": "src/java/A.java", "status": "M", "test": False}]
        head = {"src/java/A.java": entry(v("CloseResource", 5), v("ShortVariable", 6, "codestyle"))}
        base = {"src/java/A.java": entry()}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sa_mod.baseline, "obtain", return_value=obtained), \
                mock.patch.object(sa_mod.clone_mod, "_git", return_value="a" * 40 + "\n"):
            return sa_mod._rules(cfg, d, "repo", "trunk", changed, base, head, {"src/java/A.java": [(1, 10)]},
                                 ("pmd-7", RULESET, "f" * 40, True, None, "no build; without type info: x"), {}, "pmd", lambda m: None)

    def test_house_flag_comes_from_the_baseline_share(self):
        data = {"tip": "a" * 40, "files_scanned": 100, "files_hit": {"ShortVariable": 45, "CloseResource": 1}, "seconds": 3}
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


if __name__ == "__main__":
    unittest.main()
