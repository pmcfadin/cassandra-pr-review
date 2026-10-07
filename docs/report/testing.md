# Testing

## What is checked

One automated check runs in this version: when a PR changes production code, does it also change test code? It looks only at which files changed. It does not build, run, or read the tests, and it cannot tell a good test from a weak one.

The rest of this page explains what the Cassandra project expects from tests, so you can meet the standard that reviewers apply by hand.

### The test suites

Every suite below lives in `apache/cassandra` except the Python dtests. Run any of them with `.build/run-tests.sh -a <type>`.

| Suite | Where | `-a` type | Use it for |
|---|---|---|---|
| Unit and single-node integration (JUnit, `CQLTester`) | `test/unit` | `test` (variants: `test-latest`, `test-cdc`, `test-compression`, `test-oa`, `test-tries`, `test-system-keyspace-directory`) | Almost every change. Logic, state transitions, CQL behaviour on one node. |
| In-JVM distributed tests | `test/distributed` (`org.apache.cassandra.distributed.test`) | `jvm-dtest`, `jvm-dtest-novnode` | Behaviour that needs more than one node: messaging, repair, streaming, gossip, cluster metadata, consistency. |
| In-JVM upgrade tests | `test/distributed` (`org.apache.cassandra.distributed.upgrade`) | `jvm-dtest-upgrade` | Mixed-version clusters and upgrading with data written by an older version. Needs `ant dtest-jar` built for each version. |
| Python dtests | separate repo [apache/cassandra-dtest](https://github.com/apache/cassandra-dtest), driven by ccm | `dtest`, `dtest-novnode`, `dtest-offheap`, `dtest-large`, `dtest-upgrade` | Black-box cluster and client contracts, tools, and upgrade paths that are awkward to reach from the in-JVM framework. |
| Fuzz and Harry | `test/distributed/org/apache/cassandra/fuzz`, `test/harry` | (run with the in-JVM dtests) | Property-based and model-based checking of reads and writes against a reference model. |
| Simulator | `test/simulator` | `simulator-dtest` | Deterministic simulation of concurrent and distributed protocols (Accord, cluster metadata). |
| Burn | `test/burn` | `test-burn` | Sustained randomised load on one component. |
| Long | `test/long` | `long-test` | Tests too slow for pre-commit. They run post-commit only. |
| Microbenchmarks (JMH) | `test/microbench` | `microbench-test` (compile and smoke run); full run with `ant microbench -Dbenchmark.name=<Name>` | Performance claims and hot-path changes. |
| cqlsh | `pylib/cqlshlib/test` | `cqlsh-test` | Changes to cqlsh (`pylib/`). |
| Tools | `tools/stress`, fqltool, sstableloader | `stress-test`, `fqltool-test`, `sstableloader-test` | Changes to those tools. |

Sources: [testing page](https://cassandra.apache.org/_/development/testing.html), [.build/README.md](https://github.com/apache/cassandra/blob/trunk/.build/README.md), `TARGET_TYPES` in `.build/run-tests.sh`.

### Which suite fits which change

- **A bug fix**: a regression test that fails without the fix and passes with it. Put it in the lowest suite that can reproduce the bug, usually `test/unit`.
- **Single-node logic or CQL behaviour**: a unit test, using `CQLTester` for anything that goes through CQL.
- **Behaviour across nodes** (messaging, repair, streaming, bootstrap, consistency levels, schema or cluster metadata): an in-JVM dtest in `test/distributed`. Add a Python dtest only when the in-JVM framework cannot reach the behaviour, and still add the granular Java tests.
- **Serialization, messaging versions, SSTable, commit log, hints, or system tables**: an upgrade test (in-JVM `upgrade` package or a Python upgrade dtest), serialization tests such as `*SerializationsTest`, and CI with the `pre-commit w/ upgrades` profile (see the CI aspect).
- **Concurrency or distributed protocols** (Paxos, Accord, cluster metadata): consider the simulator or a fuzz test in addition to targeted tests.
- **Long-running behaviour** (compaction over time, resource leaks): a long or burn test.
- **Read or write path performance**: a JMH benchmark in `test/microbench` or `cassandra-stress` numbers, before and after.
- **Config**: `ConfigCompatibilityTest` and `LoadOldYAMLBackwardCompatibilityTest` already guard yaml compatibility. Add a test for the new setting's behaviour.
- **nodetool**: update the help fixtures under `test/resources/nodetool/help/` that `NodetoolHelpCommandsOutputTest` checks.

## Why

- "When fixing a bug, write the regression test first" and "provide test coverage for all new or modified code." Source: [AGENTS.md](https://github.com/apache/cassandra/blob/trunk/AGENTS.md), section Testing.
- Reviewers check that "tests exist, are comprehensive, and actually exercise the behaviour", that tests reuse `CQLTester`, dtest, and ccm helpers, that multi-node behaviour has in-JVM or Python dtests, and that long-running behaviour has long or fuzz tests. Source: [How to review](https://cassandra.apache.org/_/development/how_to_review.html), section Testing.
- Python dtests "are not a replacement for proper functional java tests". Systems that dtests cover also need granular Java tests. Distributed components should be testable in JUnit with injected dependencies, and global state "is not an excuse to not test something". Source: [TESTING.md](https://github.com/apache/cassandra/blob/trunk/TESTING.md).
- Unit tests should cover every state transition, illegal transitions (which must throw), all conditional branches, range boundaries, and exception handling, without testing implementation details. Integration tests should cover messages sent and received, side effects, restart after clean and unclean shutdown, and upgrade with data from a previous version. Structure each test as setup, precondition assert, action, postcondition assert. Source: [TESTING.md](https://github.com/apache/cassandra/blob/trunk/TESTING.md).
- Test debt should be paid down in proportion to the change. Refactor-heavy, test-light patches "are not likely to get committed". Source: [TESTING.md](https://github.com/apache/cassandra/blob/trunk/TESTING.md).
- How much testing a change needs depends on its stability risk: tooling needs less than the storage engine. Source: [Contributing code changes](https://cassandra.apache.org/_/development/patches.html).
- Performance claims "must be measurable" (JMH, cassandra-stress, NoSQLBench), and read or write path changes should be tested for regressions under several workloads. Sources: [testing page](https://cassandra.apache.org/_/development/testing.html), section Performance Testing; [How to review](https://cassandra.apache.org/_/development/how_to_review.html).
- Repeated runs: new or changed tests that depend on timing (dtests, tests with timeouts, sleeps, or races) are often flaky. Reviewers commonly ask for evidence that such tests pass many times in a row. The legacy CircleCI config repeated changed tests automatically; the current Jenkins pre-commit profiles do not, so you run the repeats yourself. This is project convention; no current page makes it a written rule. Sources: [.build/README.md](https://github.com/apache/cassandra/blob/trunk/.build/README.md), section "Repeating tests"; `.circleci/readme.md`.

## How each status is decided

### `tests.present`

**Blocking.** Owner: contributor.

The check sorts changed files into production and test code by path:

- **Production code** is any path under `src/java/` or `pylib/` that is not a test path.
- **Test code** is any path under `test/`, any path containing `/test/`, and `pylib/cqlshlib/test/`. Each test file is assigned a suite from its directory (`unit`, `distributed`, `burn`, `long`, `microbench`, `simulator`, `harry`, `memory`, `anttasks`, `cqlsh`), or `other` for any other test path.

Then:

- **not-applicable**: no production lines changed (additions plus deletions in production files is zero). Docs-only, build-only, and test-only PRs land here.
- **fail**: production code changed and no test file of any suite changed.
- **pass**: production code changed and at least one test file changed. The summary names the suites touched and the ratio of test lines to production lines. Lines under `test/resources/`, `test/data/`, and `test/conf/` do not count toward the ratio, but they do count as a test change.
- The check never returns warn or unknown. If it crashes, it reports unknown, which as a blocking check makes the recommendation "insufficient evidence".

A fail makes the recommendation **blocked**. The triage rating also adds one point for production code without tests.

## How to fix

**Write the test before the fix.** For a bug, reproduce it in a test first, watch it fail, then apply the fix and watch it pass. Say in the PR or on the ticket that the test fails without the fix.

**Pick the suite** from the table above. Start with the lowest level that can show the behaviour.

**Run it locally.** For one class:

```
ant testsome -Dtest.name=org.apache.cassandra.db.SomeTest
.build/run-tests.sh -a test -t SomeTest
.build/run-tests.sh -a jvm-dtest -t SomeDistributedTest
```

**Repeat timing-sensitive tests.** For a new or changed test that uses timeouts, sleeps, several nodes, or background threads, run it many times and post the result on the ticket:

```
.build/run-tests.sh -a test-repeat -t SomeTest -e REPEATED_TESTS_COUNT=500
.build/run-tests.sh -a jvm-dtest-repeat -t SomeDistributedTest -e REPEATED_TESTS_COUNT=100
```

**Then:**

- **Python dtests**: open a PR against [apache/cassandra-dtest](https://github.com/apache/cassandra-dtest) on the same ticket, link it from the JIRA ticket and the PR description, and point CI at your dtest fork and branch.
- **Upgrade-sensitive changes**: add an in-JVM upgrade test or a Python upgrade dtest, and run CI with the `pre-commit w/ upgrades` profile.
- **Performance changes**: attach JMH or `cassandra-stress` results, before and after, to the ticket.
- **If no test is possible**, explain why on the ticket and in the PR description. The check will still fail; a reviewer decides whether the explanation is enough.
- Fill in the ticket's **Test and Documentation Plan** field with what you tested and how.

The Cassandra repo ships agent skills for this work in `.claude/skills/`: `write-reproducer` and `cassandra-injvm-dtest`.

## Limits

- **Presence only.** The check sees that a test file changed. It does not know whether that test covers the change, fails without the fix, or passes at all. A one-line edit to an unrelated test satisfies it.
- **Deleting or touching test data counts.** A PR that only deletes a test, or only edits a file under `test/resources/`, passes.
- **Python dtests are invisible.** Tests in `cassandra-dtest` live in another repo, so a PR whose only test is a dtest PR fails this check. A reviewer can accept the linked dtest PR.
- **Narrow definition of production code.** Only `src/java/` and `pylib/` count. Changes under `tools/` (for example `tools/stress`), `conf/`, `src/resources/`, or `src/antlr/` alone make this check not-applicable, even when they change behaviour.
- **Tests are not run.** This version runs no tests. Test results come only from CI summaries attached to JIRA (see the CI aspect), and repeated runs are not detected at all.
- **No judgement of fit.** The check does not ask whether multi-node behaviour has a dtest, whether an on-disk format change has an upgrade test, or whether a performance claim has numbers. Reviewers judge these. Review lenses that do this are planned, not built.
