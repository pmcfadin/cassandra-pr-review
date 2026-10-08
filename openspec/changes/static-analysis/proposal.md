## Why

The report's "Code style" section approximates checkstyle with regexes on added lines and says
nothing about complexity or copy-paste. Reviewers asked for real static analysis split into what the
PR introduced and what was already there, and the owner wants a check that a performance PR puts its
benchmark commit before the change (so the benchmark can run on both sides). Research
(docs/research/static-analysis.md) shows the project's real checkstyle and PMD run standalone on a
PR's changed files in about 5 s (1 file) to 45 s (150 files), with no Cassandra build.

## What Changes

- Pinned tools, installed by `cpr tools install` into `.work/tools/` with sha256 checks: checkstyle
  10.26.1 (trunk, 5.0) and 8.40 (4.1), PMD 7.28.0 (rules and CPD).
- During ingest, run checkstyle (the base branch's own config), PMD complexity rules, and CPD on the
  base and head versions of the changed Java files; classify each finding as introduced or
  pre-existing by (file via rename map, class, method signature, rule), never by line number. Cached
  per head sha, base side per blob sha.
- New checks: `static.checkstyle`, `static.complexity` (per changed method cognitive complexity,
  base → head), `static.duplication`, and `commit.perf-structure`.
- Real checkstyle supersedes the regex banned-API and `@Deprecated` checks where the base branch has
  a checkstyle config; the regex checks stay, labelled as an approximation, for `cassandra-4.0`.
- A missing tool, missing config, parse failure, or incomplete file list is `unknown`, never `pass`.

## Non-goals

- Building the branch or running tests (build-and-coverage).
- Running benchmarks (perf-ab).
- Failing a PR on pre-existing findings.

## Capabilities

### New Capabilities
- `static-analysis`: tool provisioning, running checkstyle, PMD and CPD on base and head, classifying
  findings, caching, and the perf commit-structure rule.

### Modified Capabilities
- `merge-requirements`: the static diff checks requirement now defers to real checkstyle when it ran.

## Impact

`cpr/staticanalysis/` (new), `cpr/checks/static.py`, `cpr/checks/commits.py`, `cpr/ingest/bundle.py`,
`cpr/cli.py` (`cpr tools install`), `cpr/config/static.json`, docs/report/static.md and commits doc,
tests with recorded tool output. Java 17+ needed on the machine for checkstyle 10.x.
