# Triage

## What is checked

How hard the PR is to review: **easy**, **moderate**, or **hard**. The rating is a sum of points from fixed signals in the diff. It says nothing about whether the code is good. Its purpose is to help reviewers choose what to pick up and to tell authors when a patch might be easier to review in pieces.

Thresholds and path lists live in `cpr/config/triage.json`.

## Why

- Less complex patches are reviewed faster; large work should be split. Source: [Contributing code changes](https://cassandra.apache.org/_/development/patches.html).
- A patch's scope should be the minimum necessary. Source: [Code style](https://cassandra.apache.org/_/development/code_style.html).
- How much care a change needs depends on its stability risk; tooling needs less than the storage engine. Source: [Contributing code changes](https://cassandra.apache.org/_/development/patches.html).
- Changes to serialization or on-disk formats need upgrade testing and break mixed-version clusters when wrong. Source: [CI page](https://cassandra.apache.org/_/development/ci.html), "Profiles".
- The project's own review skills pick a method by size: shallow review for small patches, targeted review for 50 to 1000 lines, mega review above 1000. Source: `.claude/skills/` in [apache/cassandra](https://github.com/apache/cassandra/tree/trunk/.claude/skills).

## How each status is decided

Line and file counts skip generated files (`src/gen-java/`, `*.db`, `*.bin`, `/gen/`), test data (`test/resources/`, `test/data/`, `test/conf/`), and binary files. Test code is counted. Production files are those under `src/java/` and `pylib/` outside test directories.

| Signal | Points |
|---|---|
| Changed lines (additions plus deletions) | over 1000: 4 (very large); over 400: 2 (large); over 100: 1 (medium) |
| Changed files | over 30: 2; over 10: 1 |
| Subsystems touched (top-level packages under `org/apache/cassandra/` in production files) | over 4: 2; over 2: 1 |
| Compatibility surfaces touched (see the Compatibility aspect) | 1 per surface |
| High-risk surfaces among them: messaging, sstable format, commitlog / hints, native protocol, schema / system tables | 1 more per surface |
| Concurrency-sensitive paths: `concurrent/`, `db/compaction/`, `service/paxos/`, `service/accord/`, `utils/concurrent/`, `tcm/`, `streaming/` | 2 if any production file is under one |
| Target branches (this PR plus open sibling PRs) | over 2: 1 |
| Production code changed with no test file changed | 1 |

**Rating**: 5 points or more is hard, 2 to 4 is moderate, 0 or 1 is easy.

**Forced hard**: if any upgrade-sensitive file changed (the same list the CI aspect uses for `ci.profile`: messaging, SSTable format, commit log, hints, schema and system keyspace, serializers), the rating is hard whatever the points, and the report says which files forced it.

**Split suggestion**: when production lines changed exceed 1000, the report suggests splitting and lists the five largest changed files.

Triage has no checks and no pass or fail. Its section badge is always info.

## How to fix

There is nothing to fix. To make review easier:

- Split unrelated changes, refactors, and whitespace fixes into separate tickets and PRs.
- For large features, land the work in reviewable steps, or discuss the plan on dev@ or in a CEP first.
- Explain in the PR description where to start reading and what is mechanical (renames, generated code).
- Include tests; a missing test adds a point.

## Limits

- Points measure size and risk areas, not difficulty. A one-line change to a Paxos invariant can be harder than 2,000 lines of new tooling.
- Surfaces and concurrency areas are matched by path prefix.
- Compatibility surfaces are counted over all changed files, including generated and test-data files that the line count skips.
- The five largest files in a split suggestion can include tests, even though the threshold counts only production lines.
- Thresholds are set by this tool, not by the Cassandra project.
