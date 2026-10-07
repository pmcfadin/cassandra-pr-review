"""review-triage scenarios."""

import copy
import unittest

from cpr.triage import load_config, triage
from tests.helpers import bundle, with_files


class Triage(unittest.TestCase):
    def test_small_test_only_change_is_easy(self):
        b = with_files(bundle(), [("test/unit/org/apache/cassandra/db/FooTest.java", ["x"] * 40, False)])
        b["siblings"] = b["siblings"][:1]
        t = triage(b)
        self.assertEqual(t["rating"], "easy")

    def test_serialization_change_is_hard_regardless_of_size(self):
        b = with_files(bundle(), [("src/java/org/apache/cassandra/db/FooSerializer.java", ["x"], False),
                                  ("test/unit/FooTest.java", ["y"], False)])
        t = triage(b)
        self.assertEqual(t["rating"], "hard")
        self.assertIn("serialization", t["forced_by"])

    def test_signals_are_shown(self):
        t = triage(bundle())
        names = [s["signal"] for s in t["signals"]]
        for n in ("changed lines", "changed files", "subsystems touched", "compatibility surfaces",
                  "concurrency-sensitive paths", "target branches", "production code without tests"):
            self.assertIn(n, names)
        for s in t["signals"]:
            self.assertIn("points", s)
            self.assertIn("value", s)

    def test_thresholds_are_configurable(self):
        b = with_files(bundle(), [("src/java/org/apache/cassandra/db/Foo.java", ["x"] * 150, False),
                                  ("test/unit/FooTest.java", ["y"] * 10, False)])
        cfg = load_config()
        base = triage(b, cfg)
        strict = copy.deepcopy(cfg)
        strict["rating"]["moderate_at"] = 0
        strict["rating"]["hard_at"] = 1
        self.assertEqual(triage(b, strict)["rating"], "hard")
        self.assertNotEqual(base["rating"], "hard")

    def test_huge_pr_flags_split_and_lists_largest(self):
        files = [(f"src/java/org/apache/cassandra/db/F{i}.java", ["x"] * (3000 + i * 100), False) for i in range(7)]
        b = with_files(bundle(), files)
        t = triage(b)
        self.assertIsNotNone(t["split_suggestion"])
        self.assertEqual(len(t["split_suggestion"]["largest"]), 5)
        self.assertEqual(t["split_suggestion"]["largest"][0]["path"], "src/java/org/apache/cassandra/db/F6.java")

    def test_tiny_broad_change_is_capped_at_moderate(self):
        files = [(f"src/java/org/apache/cassandra/{pkg}/C.java", ["x"], False)
                 for pkg in ("net", "hints", "concurrent", "db/compaction", "service", "gms")]
        t = triage(with_files(bundle(), files))
        self.assertEqual(t["rating"], "moderate")
        self.assertIn("capped", t["capped_by"])

    def test_generated_files_do_not_count(self):
        b = with_files(bundle(), [("src/gen-java/Big.java", ["x"] * 5000, False),
                                  ("test/unit/FooTest.java", ["y"], False)])
        self.assertEqual(triage(b)["lines"], 1)


if __name__ == "__main__":
    unittest.main()
