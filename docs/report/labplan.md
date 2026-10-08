# Lab plan

## What is checked

Nothing is checked. This section is informational: it never affects the verdict. It shows a ready-to-read plan for trying the PR on a real cluster with [easy-db-lab](https://github.com/rustyrazorblade/easy-db-lab): build the merge-base and the PR head, run a workload that fits the change, and compare. The plan is generated from the diff by fixed rules (no model call), and it is **never run** by this tool. The report shows a "Not run" banner, the rendered plan, and Copy and Download buttons. `cpr review` also writes the same text next to the report as `plan.md`.

The plan follows easy-db-lab's plan format: Objective, Cluster Name, Datacenters, Environment, Artifacts under test, numbered Steps (a bash block plus Pass and Fail lines), a results table, and Notes. Steps build both commits with the `build-cassandra-ref.yml` workflow of a cassandra-builds repo, provision 3 database nodes and 1 application node (`i4i.xlarge`), install both builds side by side, calibrate, run the scenario in the order base, head, head, base, and tear down.

Scenarios the rules can choose:

| Scenario | Chosen when changed production code is under | Workload |
|---|---|---|
| kill -9 during compaction | `db/commitlog/`, `db/lifecycle/`, `hints/`, or `io/sstable/` when the title or ticket mentions crash, delete, corrupt, ordering | write load, repeated kill and restart |
| Accord against LWT | `service/accord/` | `TxnCounter` with `LWT` as control |
| LWT contention | `service/paxos/`, conditional statements | `LWT`, `Locking` |
| compaction | `db/compaction/` | `RandomPartitionAccess` |
| repair and streaming | `repair/`, `streaming/`, `ActiveRepairService` | `KeyValue` with a node down 10 minutes, then repair |
| mixed-version ring | serialization, messaging, or sstable format code (the CI profile check's list) | `KeyValue` against a ring with one upgraded node |
| write path | `db/memtable/`, `io/sstable/` (not delete-only), `io/compress/`, `db/rows/`, `db/partitions/`, `db/view/` | `KeyValue -r 0` |
| read path | read commands, `cache/`, `service/reads/` | `KeyValue -r .95` |
| index | `index/` | `SAI` |
| mixed read and write | `utils/`, `concurrent/`, `tcm/`, `gms/` | `KeyValue -r .5 -t 200` |
| smoke | `transport/`, `cql3/`, nodetool, `metrics/`, virtual tables, guardrails, `auth/`, or any server code no rule matched | `KeyValue -r .5` on the PR build only |

The rules, workloads, durations, instance type and caps live in `cpr/config/labplan.json`.

## Why

- Reviewers are asked to judge performance and stability claims with evidence, and "performance claims must be measurable" with repeated, before-and-after runs. Sources: [testing page](https://cassandra.apache.org/_/development/testing.html), section Performance Testing; [How to review](https://cassandra.apache.org/_/development/how_to_review.html).
- Crash and recovery bugs need a control arm that can fail: if the base build never shows the failure, a clean head run proves nothing. The plan says so and marks that outcome inconclusive.
- Both arms run on one cluster, in the order base, head, head, base, after two calibration runs. That cancels hardware and drift, and a delta counts only if it exceeds twice the calibration spread.
- The plan builds the merge-base, not the branch tip, so the only difference between arms is the PR's own diff.
- Generating the plan is cheap and deterministic; running it costs AWS money and hours. The owner decided that this tool generates and embeds plans only.

## How each status is decided

The section has no checks. Its status badge is one of:

- **info**: a plan was generated. The summary names the scenarios and says "not run".
- **not-applicable**: no plan, with the reason in the section. Reasons: documentation-only; tests-only; dependency change; build or CI change; generated files only; no server code under `src/java` changed; more than 300 production files changed (an A-B run would not isolate anything); or the head repository or commits cannot be used safely.

How the scenarios are chosen: each rule matches changed production files by path (and, for some rules, by keywords in the PR title and ticket summary, or by the CI profile check's upgrade-sensitive list). A rule counts only if it covers at least its minimum number of changed lines. Matching scenarios are ranked by rule priority, then by changed lines covered, and at most two are kept. If no rule matches, the plan is a smoke test of the PR build. The plan's Notes name the rule that chose each scenario and any scenario dropped by the cap.

Text from the PR reaches the plan only as a sanitised title (letters, digits, spaces and `-_.:()`, at most 80 characters) in the heading, plus validated repository names, branch names and SHAs. Titles never appear inside a code block. Every `easy-db-lab` command in a plan is checked in the test suite against a stored copy of the `easy-db-lab commands` listing.

## How to fix

There is nothing to fix. To use a plan:

1. Read it, and edit it: the plan says which rule chose each scenario, and a reviewer knows the change better than a path rule.
2. Decide which cassandra-builds repo builds the two commits (`BUILDS` in step 1). The default repo may not let you run its workflows; use your own fork.
3. Run it from a cluster directory with the easy-db-lab plugin: `/easy-db-lab:run plan.md <cluster-dir>`. The runner confirms each step and logs to `journal.md`.
4. Fill the results table, apply the decision rule from the Objective, and post the result on the ticket.

## Limits

- **Never run.** Commands are checked for spelling only. Items marked "Unverified until run" (systemd unit name, data directory path, whether `stress start` returns before the job ends, how `nt` handles dash arguments) come from the plugin documentation, not from a run.
- **Path rules, not understanding.** A subtle change can match the wrong scenario, or none, and fall back to a smoke test. Docs and tests are ignored.
- **Two scenarios at most**, and none above 300 production files.
- **Estimates only.** Wall-clock hours and cost are rough; the first real run should correct them.
- **One cluster shape.** The plan always uses 3 database nodes and 1 application node on `i4i.xlarge`; changes that need other topologies (multiple datacenters, vnodes, very large data) are not covered.
- **Branch assumptions.** The JDK comes from the target branch (4.0 and 4.1: 11, 5.0: 17, newer: 21). The Accord scenario assumes the build contains Accord.
