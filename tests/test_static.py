"""static-analysis: tool install, git inputs, runners and parsers (recorded XML), classifier, analyze, offline replay."""

import contextlib
import hashlib
import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
import zipfile
from unittest import mock

from cpr import cli, staticanalysis as sa
from cpr.ingest import bundle as bundle_mod, clone as clone_mod
from cpr.staticanalysis import classify, inputs, run, tools

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "static")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SSTABLE = "src/java/org/apache/cassandra/io/sstable/SSTable.java"


def fixture(name):
    with open(os.path.join(FIX, name)) as f:
        return f.read()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def tool_cfg(d, files):
    """A tools config whose URLs are local files; files = {tool id: (filename, bytes, kind)}."""
    cfg = {"tools": {}}
    for tid, (name, data, kind) in files.items():
        p = os.path.join(d, "dl-" + name)
        with open(p, "wb") as f:
            f.write(data)
        cfg["tools"][tid] = {"name": tid, "version": "1", "kind": kind, "min_java": 8, "url": "file://" + p,
                             "sha256": sha(data)}
    return cfg


def make_zip(path, member):
    with zipfile.ZipFile(path, "w") as z:
        info = zipfile.ZipInfo(member)
        info.external_attr = 0o755 << 16
        z.writestr(info, "#!/bin/sh\n")


class Install(unittest.TestCase):
    def test_digest_mismatch_installs_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = tool_cfg(d, {"cs-1": ("cs-1-all.jar", b"jar bytes", "jar")})
            cfg["tools"]["cs-1"]["sha256"] = "0" * 64
            work = os.path.join(d, "work")
            with self.assertRaises(tools.ToolError) as cm:
                tools.install(work, "cs-1", cfg, log=lambda m: None)
            self.assertIn("sha256 mismatch", str(cm.exception))
            self.assertFalse(tools.is_installed(work, "cs-1"))
            self.assertFalse(os.path.exists(tools.tool_dir(work, "cs-1")))
            self.assertEqual(os.listdir(tools.tools_dir(work)), [])  # scratch cleaned up too

    def test_jar_installs_once(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = tool_cfg(d, {"cs-1": ("cs-1-all.jar", b"jar bytes", "jar")})
            work = os.path.join(d, "work")
            self.assertEqual(tools.install(work, "cs-1", cfg, log=lambda m: None), "downloaded")
            self.assertTrue(tools.jar_path(work, "cs-1").endswith("cs-1-all.jar"))
            boom = mock.Mock(side_effect=AssertionError("fetched again"))
            self.assertEqual(tools.install(work, "cs-1", cfg, fetch=boom), "present")

    def test_reuses_an_earlier_download_with_matching_digest(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = tool_cfg(d, {"cs-1": ("cs-1-all.jar", b"jar bytes", "jar")})
            work = os.path.join(d, "work")
            os.makedirs(os.path.join(work, "tools", "old"))
            with open(os.path.join(work, "tools", "old", "dl-cs-1-all.jar"), "wb") as f:
                f.write(b"jar bytes")
            boom = mock.Mock(side_effect=AssertionError("downloaded"))
            self.assertEqual(tools.install(work, "cs-1", cfg, fetch=boom), "reused")

    def test_zip_keeps_executable_bit(self):
        with tempfile.TemporaryDirectory() as d:
            z = os.path.join(d, "pmd.zip")
            make_zip(z, "pmd-bin-1/bin/pmd")
            with open(z, "rb") as f:
                cfg = tool_cfg(d, {"pmd-1": ("pmd.zip", f.read(), "zip")})
            work = os.path.join(d, "work")
            tools.install(work, "pmd-1", cfg, log=lambda m: None)
            self.assertTrue(os.stat(tools.pmd_path(work, "pmd-1")).st_mode & stat.S_IXUSR)

    def test_checkstyle_by_branch_family(self):
        cfg = tools.load_config()
        self.assertEqual(tools.checkstyle_id(cfg, "trunk"), "checkstyle-10.26.1")
        self.assertEqual(tools.checkstyle_id(cfg, "cassandra-5.0"), "checkstyle-10.26.1")
        self.assertEqual(tools.checkstyle_id(cfg, "cassandra-5.1"), "checkstyle-10.26.1")
        self.assertEqual(tools.checkstyle_id(cfg, "cassandra-4.1"), "checkstyle-8.40")
        self.assertIsNone(tools.checkstyle_id(cfg, "cassandra-4.0"))
        self.assertIsNone(tools.checkstyle_id(cfg, "cassandra-3.11"))

    def test_pinned_digests_are_sha256(self):
        for spec in tools.load_config()["tools"].values():
            self.assertRegex(spec["sha256"], r"^[0-9a-f]{64}$")

    def test_java_too_old(self):
        with tempfile.TemporaryDirectory() as d:
            bindir = os.path.join(d, "bin")
            os.makedirs(bindir)
            java = os.path.join(bindir, "java")
            with open(java, "w") as f:
                f.write('#!/bin/sh\necho \'openjdk version "1.8.0_402"\' >&2\n')
            os.chmod(java, 0o755)
            cfg = {"java_homes": []}
            env = {"JAVA_HOME": d, "PATH": ""}
            self.assertEqual(tools.find_java(8, cfg, env), (java, 8))
            with self.assertRaises(tools.ToolError) as cm:
                tools.find_java(17, cfg, env)
            self.assertIn("needs JDK 17+", str(cm.exception))

    def test_cli_install_twice_is_a_noop(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = tool_cfg(d, {"cs-1": ("cs-1-all.jar", b"jar bytes", "jar")})
            cfg["java_homes"] = []
            work = os.path.join(d, "work")
            outs = []
            with mock.patch.object(tools, "load_config", return_value=cfg):
                for _ in range(2):
                    buf = io.StringIO()
                    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(cli.main(["tools", "install", "--work-dir", work]), 0)
                    outs.append(buf.getvalue())
            self.assertIn("cs-1: installed (downloaded)", outs[0])
            self.assertIn("cs-1: already installed", outs[1])

    def test_cli_digest_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = tool_cfg(d, {"cs-1": ("cs-1-all.jar", b"jar bytes", "jar")})
            cfg["tools"]["cs-1"]["sha256"] = "1" * 64
            cfg["java_homes"] = []
            with mock.patch.object(tools, "load_config", return_value=cfg), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(["tools", "install", "--work-dir", os.path.join(d, "w")]), 1)


def git(repo, *a):
    return subprocess.run(["git", "-C", repo, "-c", "user.name=T", "-c", "user.email=t@example.org",
                           "-c", "commit.gpgsign=false", *a], check=True, capture_output=True, text=True).stdout.strip()


def write(repo, path, text):
    p = os.path.join(repo, path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text)


BODY = "".join(f"    int f{i}() {{ return {i}; }}\n" for i in range(30))
MAIN_A, MAIN_B = "src/java/A.java", "src/java/B.java"


def make_repo(d):
    """base: A, B, test/T, Gone, gen. head: A edited at line 5, B renamed to C and edited, N added, Gone deleted."""
    git(d, "init", "-q", "-b", "main")
    write(d, MAIN_A, "class A {\n" + BODY + "}\n")
    write(d, MAIN_B, "class B {\n" + BODY + "}\n")
    write(d, "test/T.java", "class T {}\n")
    write(d, "src/java/Gone.java", "class Gone {}\n")
    write(d, "src/gen-java/G.java", "class G {}\n")
    write(d, "README.md", "x\n")
    git(d, "add", "-A")
    git(d, "commit", "-qm", "base")
    base = git(d, "rev-parse", "HEAD")
    lines = ("class A {\n" + BODY + "}\n").splitlines()
    lines[4] = "    int changed() { return 1; }"
    write(d, MAIN_A, "\n".join(lines) + "\n")
    git(d, "mv", MAIN_B, "src/java/C.java")
    write(d, "src/java/C.java", "class C {\n" + BODY + "}\n")
    git(d, "add", "-A")
    git(d, "commit", "-qm", "edit A, rename B to C")
    git(d, "rm", "-q", "src/java/Gone.java")
    write(d, "src/java/N.java", "class N {\n}\n")
    write(d, "src/gen-java/G.java", "class G { int x; }\n")
    write(d, "README.md", "y\n")
    git(d, "add", "-A")
    git(d, "commit", "-qm", "add N, delete Gone")
    return base, git(d, "rev-parse", "HEAD")


class Inputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.repo = cls.tmp.name
        cls.base, cls.head = make_repo(cls.repo)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_rename_map_statuses_and_exclusions(self):
        got = {c["path"]: c for c in inputs.changed_java(self.repo, self.base, self.head, ["src/gen-java/"])}
        self.assertEqual(set(got), {MAIN_A, "src/java/C.java", "src/java/N.java", "src/java/Gone.java"})
        self.assertEqual((got["src/java/C.java"]["status"], got["src/java/C.java"]["base_path"]), ("R", MAIN_B))
        self.assertEqual((got["src/java/N.java"]["status"], got["src/java/N.java"]["base_path"]), ("A", None))
        self.assertEqual((got["src/java/Gone.java"]["status"], got["src/java/Gone.java"]["base_path"]),
                         ("D", "src/java/Gone.java"))
        self.assertEqual((got[MAIN_A]["status"], got[MAIN_A]["base_path"]), ("M", MAIN_A))
        self.assertFalse(got[MAIN_A]["test"])

    def test_changed_line_ranges(self):
        new, old = inputs.changed_lines(self.repo, self.base, self.head)
        self.assertEqual(new[MAIN_A], [(5, 5)])
        self.assertEqual(old[MAIN_A], [(5, 5)])
        self.assertEqual(new["src/java/N.java"], [(1, 2)])
        self.assertNotIn("src/java/Gone.java", new)
        self.assertEqual(old["src/java/Gone.java"], [(1, 1)])

    def test_parse_hunks_counts_default_to_one(self):
        new, old = inputs.parse_hunks("--- a/X.java\n+++ b/X.java\n@@ -3 +3,2 @@\n-a\n+b\n+c\n@@ -9,2 +10,0 @@\n-d\n-e\n")
        self.assertEqual(new["X.java"], [(3, 4)])
        self.assertEqual(old["X.java"], [(3, 3), (9, 10)])

    def test_extract_writes_both_sides_without_checkout(self):
        changed = inputs.changed_java(self.repo, self.base, self.head, ["src/gen-java/"])
        with tempfile.TemporaryDirectory() as dest:
            shas = inputs.extract(self.repo, changed, self.base, self.head, dest)
            self.assertTrue(os.path.exists(os.path.join(dest, "base", MAIN_B)))
            self.assertTrue(os.path.exists(os.path.join(dest, "head", "src/java/C.java")))
            self.assertFalse(os.path.exists(os.path.join(dest, "head", "src/java/Gone.java")))
            self.assertFalse(os.path.exists(os.path.join(dest, "base", "src/java/N.java")))
            self.assertEqual(shas["base"][MAIN_B], git(self.repo, "rev-parse", f"{self.base}:{MAIN_B}"))
            with open(os.path.join(dest, "head", MAIN_A)) as f:
                self.assertIn("int changed()", f.read())

    def test_commits_oldest_first_with_paths(self):
        got = inputs.commits(self.repo, self.base, self.head)
        self.assertEqual([c["subject"] for c in got], ["edit A, rename B to C", "add N, delete Gone"])
        self.assertIn(MAIN_A, got[0]["paths"])
        self.assertIn("src/java/N.java", got[1]["paths"])
        self.assertEqual(len(got[0]["sha"]), 40)


class Parsers(unittest.TestCase):
    def test_checkstyle_xml(self):
        got = run.parse_checkstyle(fixture("checkstyle-5201-head.xml"), "/work/head")
        errs = got[SSTABLE]
        self.assertEqual([e["line"] for e in errs], [117, 258, 287, 316, 322, 335])
        self.assertEqual(errs[0]["rule"], "IllegalInstantiation")
        self.assertEqual(errs[0]["severity"], "error")

    def test_pmd_xml_methods_and_bodies(self):
        files, errors = run.parse_pmd(fixture("pmd-5201-head.xml"), "/work/head")
        self.assertEqual(errors, [])
        f = files[SSTABLE]
        self.assertIn(["SSTable", "delete(Descriptor, Set<Component>)", "CognitiveComplexity", 2, 109], f["m"])
        self.assertIn(["SSTable", "delete", 110, 124], f["bodies"])
        base, _ = run.parse_pmd(fixture("pmd-5201-base.xml"), "/work/base")
        self.assertIn(["SSTable", "delete(Descriptor, Set<Component>)", "CognitiveComplexity", 6, 109], base[SSTABLE]["m"])

    def test_pmd_processing_errors(self):
        xml = ('<pmd xmlns="http://pmd.sourceforge.net/report/2.0.0"><file name="/r/A.java"></file>'
               '<error filename="/r/B.java" msg="ParseException: boom"/></pmd>')
        files, errors = run.parse_pmd(xml, "/r")
        self.assertEqual(list(files), ["A.java"])
        self.assertEqual(errors, [("B.java", "ParseException: boom")])

    def test_cpd_xml(self):
        dups, analyzed = run.parse_cpd(fixture("cpd-sample.xml"), "/work/head")
        self.assertEqual((analyzed, len(dups)), (3, 2))
        self.assertEqual((dups[0]["tokens"], dups[0]["lines"]), (396, 47))
        self.assertTrue(all(o["file"].startswith("test/unit/") for o in dups[0]["occurrences"]))


def fake_execute(write_xml=None, rc=0, err=""):
    """A stand-in for run.execute that writes `write_xml` to the -o / -r output path."""
    def execute(cmd, env, timeout, cwd=None):
        out = cmd[cmd.index("-o") + 1] if "-o" in cmd else cmd[cmd.index("-r") + 1] if "-r" in cmd else None
        if write_xml is not None and out:
            with open(out, "w") as f:
                f.write(write_xml)
        return rc, "", err, 0.5
    return execute


class Runners(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.d.name, "head")
        for rel in (SSTABLE, "src/java/Other.java"):
            write(self.root, rel, "class X {}\n")
        self.cfgs = {"checkstyle.xml": "c", "checkstyle_suppressions.xml": "s"}

    def tearDown(self):
        self.d.cleanup()

    def cs(self, execute, rels):
        with mock.patch.object(run, "execute", execute):
            return run.run_checkstyle("java", "cs.jar", self.cfgs, self.root, rels, self.d.name, "head", 10)

    def test_file_missing_from_output(self):
        xml = f'<checkstyle><file name="{self.root}/{SSTABLE}"></file></checkstyle>'
        r = self.cs(fake_execute(xml, rc=0), [SSTABLE, "src/java/Other.java"])
        self.assertEqual(r["missing"], ["src/java/Other.java"])
        self.assertIsNone(r["problem"])

    def test_every_file_present_with_errors_is_ran(self):
        xml = (f'<checkstyle><file name="{self.root}/{SSTABLE}"><error line="1" column="1" severity="error" '
               f'message="m" source="a.b.XCheck"/></file><file name="{self.root}/src/java/Other.java"></file></checkstyle>')
        r = self.cs(fake_execute(xml, rc=1), [SSTABLE, "src/java/Other.java"])  # exit code = error count
        self.assertEqual(r["missing"], [])
        self.assertEqual(r["files"][SSTABLE][0]["text"], "class X {}")

    def test_crash_has_no_xml(self):
        r = self.cs(fake_execute(None, rc=1, err="\nCheckstyle failed: Unable to find: x\n  at ..."), [SSTABLE])
        self.assertEqual(r["problem"], "checkstyle failed: Checkstyle failed: Unable to find: x")
        self.assertEqual(r["missing"], [SSTABLE])

    def test_timeout(self):
        r = self.cs(lambda *a, **k: (None, "", "", 10.0), [SSTABLE])
        self.assertIn("timed out after 10 s", r["problem"])

    def test_per_run_props_file_and_log_dir(self):
        seen = []

        def execute(cmd, env, timeout, cwd=None):
            seen.append(cmd)
            return fake_execute("<checkstyle/>")(cmd, env, timeout)
        self.cs(execute, [SSTABLE])
        props = seen[0][seen[0].index("-p") + 1]
        with open(props) as f:
            text = f.read()
        self.assertIn("checkstyle.log.dir=" + os.path.join(self.d.name, "head-main-log"), text)
        self.assertIn("checkstyle.suppressions=s", text)
        self.assertIn("-f", seen[0])

    def test_pmd_exit_codes(self):
        xml = fixture("pmd-5201-head.xml").replace("/work/head", self.root)
        with mock.patch.object(run, "execute", fake_execute(xml, rc=4)):
            ok = run.run_pmd("pmd", {}, "r.xml", self.root, [SSTABLE, "src/java/Other.java"], self.d.name, "head", 10)
        self.assertIsNone(ok["problem"])
        self.assertEqual(ok["files"]["src/java/Other.java"], {"bodies": [], "m": [], "v": []})  # clean files have no rows
        with mock.patch.object(run, "execute", fake_execute(xml, rc=1, err="usage: boom")):
            bad = run.run_pmd("pmd", {}, "r.xml", self.root, [SSTABLE], self.d.name, "head", 10)
        self.assertEqual(bad["problem"], "exit 1: usage: boom")

    def test_pmd_failure_with_per_file_errors_keeps_the_other_files(self):
        bad_file = os.path.join(self.root, "src/java/Other.java")
        xml = fixture("pmd-5201-head.xml").replace("/work/head", self.root).replace(
            "</pmd>", f'<error filename="{bad_file}" msg="SemanticException: unresolved type"/></pmd>')
        with mock.patch.object(run, "execute", fake_execute(xml, rc=1, err=f"[ERROR] at {bad_file}:1:1: boom")):
            r = run.run_pmd("pmd", {}, "r.xml", self.root, [SSTABLE, "src/java/Other.java"], self.d.name, "head", 10)
        self.assertIsNone(r["problem"])
        self.assertEqual([p for p, _ in r["parse_errors"]], ["src/java/Other.java"])
        self.assertIn(SSTABLE, r["files"])

    def test_pmd_failure_message_has_no_local_paths(self):
        with mock.patch.object(run, "execute", fake_execute("not xml", rc=1, err=f"[ERROR] at {self.root}/src/A.java")):
            r = run.run_pmd("pmd", {}, "r.xml", self.root, [SSTABLE], self.d.name, "head", 10)
        self.assertEqual(r["problem"], "exit 1: [ERROR] at src/A.java")

    def test_cpd_counts_files(self):
        xml = fixture("cpd-sample.xml").replace("/work/head", self.root)
        with mock.patch.object(run, "execute", fake_execute(xml, rc=4)):
            r = run.run_cpd("pmd", {}, 100, self.root, [SSTABLE], self.d.name, 10)
        self.assertEqual((r["problem"], r["analyzed"], len(r["duplicates"])), (None, 3, 2))


def pm(bodies=(), methods=()):
    """Parsed PMD for one file: bodies [(cls, meth, b, e)], methods [(cls, sig, rule, score, line)]."""
    return {"bodies": [list(b) for b in bodies], "m": [list(m) for m in methods]}


CHANGE = {"path": "A.java", "base_path": "A.java", "status": "M", "test": False}
TH = {"CognitiveComplexity": 15, "CyclomaticComplexity": 10, "NPathComplexity": 200}
COG = "CognitiveComplexity"


def classes(findings):
    return {(f["method_sig"], f["classification"]) for f in findings}


class Classify(unittest.TestCase):
    def test_pr_5201_delete_goes_from_6_to_2_with_nothing_introduced(self):
        base, _ = run.parse_pmd(fixture("pmd-5201-base.xml"), "/work/base")
        head, _ = run.parse_pmd(fixture("pmd-5201-head.xml"), "/work/head")
        change = {"path": SSTABLE, "base_path": SSTABLE, "status": "M", "test": False}
        methods, findings = classify.classify_complexity([change], base, head, {SSTABLE: [(112, 120)]}, TH)
        self.assertEqual(findings, [])
        self.assertEqual(methods, [{"file": SSTABLE, "class": "SSTable", "method_sig": "delete(Descriptor, Set<Component>)",
                                    "base": 6, "head": 2, "touched": True, "classification": "pre-existing-improved"}])

    def test_new_file(self):
        head = {"A.java": pm([("A", "m", 2, 9)], [("A", "m()", COG, 20, 2)])}
        change = {**CHANGE, "status": "A", "base_path": None}
        methods, findings = classify.classify_complexity([change], {}, head, {"A.java": [(1, 10)]}, TH)
        self.assertEqual(classes(findings), {("m()", "introduced-new-file")})
        self.assertEqual(methods[0]["base"], None)

    def test_new_method_in_existing_file(self):
        base = {"A.java": pm([("A", "old", 2, 5)], [("A", "old()", COG, 3, 2)])}
        head = {"A.java": pm([("A", "old", 2, 5), ("A", "m", 7, 20)], [("A", "old()", COG, 3, 2), ("A", "m()", COG, 18, 7)])}
        methods, findings = classify.classify_complexity([CHANGE], base, head, {"A.java": [(7, 20)]}, TH)
        self.assertEqual(classes(findings), {("m()", "introduced-new-method")})
        self.assertEqual([m["method_sig"] for m in methods], ["m()"])

    def test_worsened_crossed_and_improved(self):
        base = {"A.java": pm([("A", "w", 2, 5), ("A", "c", 6, 9), ("A", "i", 10, 14)],
                             [("A", "w()", COG, 16, 2), ("A", "c()", COG, 10, 6), ("A", "i()", COG, 30, 10)])}
        head = {"A.java": pm([("A", "w", 2, 5), ("A", "c", 6, 9), ("A", "i", 10, 14)],
                             [("A", "w()", COG, 20, 2), ("A", "c()", COG, 15, 6), ("A", "i()", COG, 16, 10)])}
        _, findings = classify.classify_complexity([CHANGE], base, head, {"A.java": [(1, 3)]}, TH)
        self.assertEqual(classes(findings), {("w()", "introduced-worsened"), ("c()", "introduced-crossed"),
                                             ("i()", "pre-existing-improved")})

    def test_untouched_breach_is_pre_existing(self):
        both = {"A.java": pm([("A", "m", 2, 5)], [("A", "m()", COG, 22, 2)])}
        change = {"A.java": [(50, 51)]}
        _, findings = classify.classify_complexity([CHANGE], both, both, change, TH)
        self.assertEqual(classes(findings), {("m()", "pre-existing")})
        _, findings = classify.classify_complexity([CHANGE], both, both, {"A.java": [(3, 3)]}, TH)
        self.assertEqual(classes(findings), {("m()", "pre-existing-touched")})

    def test_renamed_file_and_class_matches_by_signature(self):
        base = {"Old.java": pm([("Old", "m", 2, 5)], [("Old", "m(int)", COG, 20, 2)])}
        head = {"New.java": pm([("New", "m", 2, 5)], [("New", "m(int)", COG, 20, 2)])}
        change = {"path": "New.java", "base_path": "Old.java", "status": "R", "test": False}
        methods, findings = classify.classify_complexity([change], base, head, {}, TH)
        self.assertEqual(classes(findings), {("m(int)", "pre-existing")})
        self.assertEqual(methods, [])  # unchanged score, untouched: not listed

    def test_moved_method_is_labelled_not_introduced(self):
        base = {"A.java": pm([("A", "m", 2, 9)], [("A", "m()", COG, 20, 2)]), "B.java": pm()}
        head = {"A.java": pm(), "B.java": pm([("B", "m", 2, 9)], [("B", "m()", COG, 20, 2)])}
        changes = [CHANGE, {"path": "B.java", "base_path": "B.java", "status": "M", "test": False}]
        _, findings = classify.classify_complexity(changes, base, head, {"B.java": [(2, 9)]}, TH)
        self.assertEqual(classes(findings), {("m()", "moved")})  # and no "fixed" for the A.java side

    def test_zero_score_base_method_is_not_new(self):
        base = {"A.java": pm([("A", "m", 2, 5)])}
        head = {"A.java": pm([("A", "m", 2, 5)], [("A", "m()", COG, 16, 2)])}
        _, findings = classify.classify_complexity([CHANGE], base, head, {"A.java": [(3, 4)]}, TH)
        self.assertEqual(classes(findings), {("m()", "introduced-crossed")})

    def test_new_overload_is_new(self):
        base = {"A.java": pm([("A", "m", 2, 5)])}
        head = {"A.java": pm([("A", "m", 2, 5), ("A", "m", 6, 20)], [("A", "m(int)", COG, 17, 6)])}
        _, findings = classify.classify_complexity([CHANGE], base, head, {"A.java": [(6, 20)]}, TH)
        self.assertEqual(classes(findings), {("m(int)", "introduced-new-method")})

    def test_fixed_when_method_removed_or_reduced(self):
        base = {"A.java": pm([("A", "gone", 2, 9), ("A", "less", 10, 19)],
                             [("A", "gone()", COG, 30, 2), ("A", "less()", COG, 30, 10)])}
        head = {"A.java": pm([("A", "less", 2, 11)], [("A", "less()", COG, 4, 2)])}
        methods, findings = classify.classify_complexity([CHANGE], base, head, {"A.java": [(2, 11)]}, TH)
        self.assertEqual(classes([f for f in findings if f["classification"] == "fixed"]),
                         {("gone()", "fixed"), ("less()", "fixed")})
        self.assertIn(("gone()", None, "fixed"), {(m["method_sig"], m["head"], m["classification"]) for m in methods})

    def test_deleted_file_breaches_are_fixed(self):
        base = {"A.java": pm([("A", "m", 2, 5)], [("A", "m()", COG, 20, 2)])}
        _, findings = classify.classify_complexity([{**CHANGE, "status": "D"}], base, {}, {}, TH)
        self.assertEqual(classes(findings), {("m()", "fixed")})

    def test_checkstyle_introduced_pre_existing_fixed(self):
        def e(line, rule, text, msg="bad"):
            return {"line": line, "rule": rule, "message": msg, "text": text}
        base = {"A.java": [e(10, "R", "x = 1;"), e(20, "R", "y = 2;"), e(30, "Q", "gone")]}
        head = {"A.java": [e(12, "R", "x = 1;"), e(25, "R", "y = 2;"), e(40, "R", "z = 3;")]}
        got = classify.classify_checkstyle([CHANGE], base, head, {"A.java": [(25, 25)]})
        by_line = {(f["line"], f["classification"]) for f in got}
        self.assertEqual(by_line, {(12, "pre-existing"), (25, "introduced"), (40, "introduced"), (30, "fixed")})

    def test_checkstyle_identical_lines_are_counted_not_merged(self):
        e = lambda line: {"line": line, "rule": "R", "message": "m", "text": "same"}  # noqa: E731
        got = classify.classify_checkstyle([CHANGE], {"A.java": [e(1)]}, {"A.java": [e(5), e(9)]}, {})
        self.assertEqual(sorted(f["classification"] for f in got), ["introduced", "pre-existing"])

    def test_checkstyle_new_file_is_all_introduced(self):
        change = {**CHANGE, "status": "A", "base_path": None}
        got = classify.classify_checkstyle([change], {}, {"A.java": [{"line": 1, "rule": "R", "message": "m", "text": ""}]}, {})
        self.assertEqual([f["classification"] for f in got], ["introduced"])

    def test_checkstyle_on_pr_5201_fixture(self):
        head = run.parse_checkstyle(fixture("checkstyle-5201-head.xml"), "/work/head")
        change = {"path": SSTABLE, "base_path": SSTABLE, "status": "M", "test": False}
        got = classify.classify_checkstyle([change], {SSTABLE: []}, head, {SSTABLE: [(316, 316)]})
        self.assertEqual({f["line"] for f in got if f["classification"] == "introduced"}, {117, 258, 287, 316, 322, 335})
        self.assertEqual(got[0]["tool"], "checkstyle")

    def test_cpd_introduced_rules(self):
        dups, _ = run.parse_cpd(fixture("cpd-sample.xml"), "/work/head")
        first = dups[0]["occurrences"]
        changed = [{"path": o["file"], "base_path": o["file"], "status": "M", "test": True} for o in first]
        untouched = classify.classify_duplication(dups[:1], changed, {})
        self.assertFalse(untouched[0]["introduced"])
        touched = classify.classify_duplication(dups[:1], changed, {first[0]["file"]: [(first[0]["line"], first[0]["line"])]})
        self.assertTrue(touched[0]["introduced"])
        all_new = classify.classify_duplication(dups[:1], [{**c, "status": "A"} for c in changed], {})
        self.assertTrue(all_new[0]["introduced"])
        some_new = classify.classify_duplication(dups[:1], [{**changed[0], "status": "A"}] + changed[1:], {})
        self.assertFalse(some_new[0]["introduced"])


def pr_bundle(repo, base, number=7, base_branch="cassandra-4.0"):
    return {"pr": {"number": number, "base": base_branch, "head_sha": "h" * 40},
            "git": {"merge_base": base, "head_ref": clone_mod.pr_ref(number), "clone": repo}}


class Analyze(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.repo = cls.tmp.name
        cls.base, cls.head = make_repo(cls.repo)
        git(cls.repo, "update-ref", clone_mod.pr_ref(7), cls.head)
        git(cls.repo, "update-ref", clone_mod.base_ref("cassandra-4.0"), cls.base)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_no_clone_is_unavailable(self):
        out = sa.analyze({"pr": {"number": 1, "base": "trunk", "head_sha": "x"}}, "/nonexistent", log=lambda m: None)
        self.assertEqual(out["status"], "unavailable")
        self.assertEqual({t["status"] for t in out["tools"].values()}, {"unknown"})
        self.assertEqual(out["commits"], [])

    def test_no_java_files_is_unavailable_with_commits(self):
        out = sa.analyze(pr_bundle(self.repo, self.head), "/nonexistent", log=lambda m: None)  # merge base == head
        self.assertEqual(out["status"], "unavailable")
        self.assertEqual(out["reason"], "no changed Java files")
        self.assertEqual(out["tools"]["pmd"]["status"], "not-applicable")

    def test_tools_not_installed_are_unknown_not_pass(self):
        with tempfile.TemporaryDirectory() as work:
            out = sa.analyze(pr_bundle(self.repo, self.base), work, log=lambda m: None)
            self.assertEqual(out["status"], "ran")
            self.assertEqual(out["tools"]["checkstyle"]["reason"], "no checkstyle config on cassandra-4.0")
            for t in ("pmd", "cpd"):
                self.assertEqual(out["tools"][t]["status"], "unknown")
                self.assertIn("cpr tools install", out["tools"][t]["reason"])
            self.assertEqual(out["tools"]["pmd"]["files_expected"], 3)
            self.assertEqual(len(out["changed_java"]), 4)
            self.assertEqual([c["subject"] for c in out["commits"]], ["edit A, rename B to C", "add N, delete Gone"])
            self.assertEqual(out["complexity"], {"threshold": 15, "methods": [], "findings": []})

    def test_checkstyle_config_present_but_tool_missing(self):
        wt = tempfile.mkdtemp()
        try:
            repo = os.path.join(wt, "r")
            subprocess.run(["git", "clone", "-q", self.repo, repo], check=True)
            git(repo, "checkout", "-q", "-b", "tmpb", self.base)
            write(repo, ".build/checkstyle.xml", "<module name='Checker'/>")
            write(repo, ".build/checkstyle_suppressions.xml", "<suppressions/>")
            git(repo, "add", "-A")
            git(repo, "commit", "-qm", "cfg")
            git(repo, "update-ref", clone_mod.base_ref("trunk"), "tmpb")
            git(repo, "update-ref", clone_mod.pr_ref(7), self.head)
            mb = git(repo, "rev-parse", "tmpb")
            with tempfile.TemporaryDirectory() as work:
                out = sa.analyze(pr_bundle(repo, mb, base_branch="trunk"), work, log=lambda m: None)
            self.assertEqual(out["tools"]["checkstyle"]["status"], "unknown")
            self.assertIn("cpr tools install", out["tools"]["checkstyle"]["reason"])
            self.assertEqual(out["checkstyle"], [])
        finally:
            import shutil
            shutil.rmtree(wt, ignore_errors=True)

    def test_second_analysis_of_the_same_head_uses_the_cache(self):
        with tempfile.TemporaryDirectory() as work:
            first = sa.analyze(pr_bundle(self.repo, self.base), work, log=lambda m: None)
            with mock.patch.object(inputs, "extract", side_effect=AssertionError("re-ran")):
                second = sa.analyze(pr_bundle(self.repo, self.base), work, log=lambda m: None)
            self.assertEqual(first, second)
            self.assertTrue(os.path.exists(os.path.join(work, "pr", "7", "h" * 40, "static", "results.json")))

    def test_base_side_results_are_cached_per_blob(self):
        with tempfile.TemporaryDirectory() as d:
            calls = []

            def runner(paths):
                calls.append(list(paths))
                return {p: {"bodies": [], "m": []} for p in paths}, None, 1.0
            shas = {"a": "1" * 40, "b": "2" * 40}
            sa._cached_side(d, shas, runner)
            sa._cached_side(d, {**shas, "c": "3" * 40}, runner)
            self.assertEqual(calls, [["a", "b"], ["c"]])

    def test_offline_replay_runs_no_tool(self):
        saved = {"status": "ran", "reason": None, "base_branch": "trunk", "tools": {}, "changed_java": [],
                 "checkstyle": [], "complexity": {"threshold": 15, "methods": [], "findings": []},
                 "duplication": [], "commits": []}
        with tempfile.TemporaryDirectory() as work:
            b = {"pr": {"number": 9, "head_sha": "e" * 40}, "static_analysis": saved}
            bundle_mod.save(b, work)
            boom = AssertionError("a tool ran during an offline replay")
            with mock.patch.object(run, "execute", side_effect=boom), mock.patch.object(sa, "analyze", side_effect=boom), \
                    mock.patch.object(tools, "install", side_effect=boom):
                self.assertEqual(bundle_mod.load_cached(work, 9)["static_analysis"], saved)
            old = {"pr": {"number": 10, "head_sha": "d" * 40}}
            bundle_mod.save(old, work)
            replay = bundle_mod.load_cached(work, 10)["static_analysis"]
            self.assertEqual(replay["status"], "unavailable")


def _smoke_env():
    work = os.environ.get("CPR_WORK_DIR") or os.path.join(ROOT, ".work")
    try:
        cfg = tools.load_config()
        for tid in ("pmd-7.28.0",):
            if not tools.is_installed(work, tid):
                return None
        tools.find_java(8, cfg)
    except tools.ToolError:
        return None
    if not os.path.exists(bundle_mod.latest_bundle_path(work, 5201)):
        return None
    return work


@unittest.skipUnless(_smoke_env(), "needs installed tools, a JDK, the cassandra clone and the cached PR 5201 ingest")
class RealPr5201(unittest.TestCase):
    def test_delete_is_simpler_and_nothing_is_introduced(self):
        work = _smoke_env()
        b = bundle_mod.load_cached(work, 5201)
        if not os.path.isdir(os.path.join(b["git"]["clone"], ".git")):
            self.skipTest("no clone")
        out = sa.analyze(b, work, log=lambda m: None)
        self.assertEqual(out["status"], "ran")
        self.assertEqual(out["tools"]["pmd"]["status"], "ran")
        self.assertEqual(out["tools"]["cpd"]["status"], "ran")
        self.assertEqual(out["tools"]["checkstyle"]["status"], "unknown")  # cassandra-4.0 has no config
        self.assertIn("cassandra-4.0", out["tools"]["checkstyle"]["reason"])
        delete = [m for m in out["complexity"]["methods"] if m["method_sig"].startswith("delete(")]
        self.assertEqual([(m["base"], m["head"]) for m in delete], [(6, 2)])
        introduced = [f for f in out["complexity"]["findings"] if f["classification"].startswith("introduced")]
        self.assertEqual(introduced, [])
        self.assertEqual(out["duplication"], [])


if __name__ == "__main__":
    unittest.main()
