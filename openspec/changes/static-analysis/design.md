## Context

Research: docs/research/static-analysis.md (commands, versions, sha256s, timings, prototype
classifier at `.work/tools/pmd/classify.py`). Checks are pure functions over the evidence bundle, so
tool runs happen at ingest and their normalized results are stored in the bundle; offline re-renders
replay them.

## Goals / Non-Goals

**Goals:** real checkstyle, complexity and duplication results on every PR, introduced vs
pre-existing; perf commit order; honest `unknown`. **Non-Goals:** builds, tests, benchmarks.

## Decisions

### D1. Tool provisioning
`cpr/config/static.json` pins each tool: version, download URL, sha256, and for checkstyle the branch
families that use it (trunk and 5.0 → 10.26.1, 4.1 → 8.40, 4.0 → none). `cpr tools install`
downloads into `.work/tools/<tool>-<version>/`, verifies sha256, and unpacks. Java is found from
`JAVA_HOME`, then `/opt/homebrew/opt/openjdk@21`, then `java` on PATH; checkstyle 10.x needs 17+.

### D2. Inputs
From the clone: rename map (`git diff -M --name-status base head -- '*.java'`), head-side changed
lines (`-U0`), base and head blobs written to `<sha_dir>/static/{base,head}/<path>` via `git show`
(no checkout), commit list with per-commit paths (`rev-list --reverse --no-merges`). Excluded paths:
`src/gen-java/`, `modules/accord/`, deleted files (base side only).

### D3. Runs
Checkstyle: `.build/checkstyle.xml` for `src/java`, `checkstyle_test.xml` for `test/`, both from the
base branch, with a per-run props file (`checkstyle.log.dir`, `checkstyle.suppressions`), `-f xml`.
PMD: one-pass ruleset (cognitive `reportLevel=1`, cyclomatic and NPath at the skill's thresholds,
plus an XPath rule emitting method body ranges), `-f xml`. CPD: 100 tokens, `--format xml`. Exit
codes: checkstyle = error count (crash otherwise), PMD/CPD 0 or 4 = ran. Caps: 120 s per tool,
300 s per PR; over 400 changed Java files PMD is `skipped`.

### D4. Classification
Findings normalize to `{tool, rule, file, base_file, class, method_sig, line, score, message}`.
Key = (base path, class, method signature, rule). Classes: introduced (new file, new method,
worsened, crossed threshold), pre-existing (touched, untouched, improved), fixed. Fallbacks: unique
same-signature method in the matched base file (class renamed), signature match across the PR's base
files labelled "moved?". Checkstyle: introduced when the head line is a changed line or no equal
(file, source, message, line text) exists at base. CPD: introduced when an occurrence overlaps a
changed line or all occurrences are in new files. Complexity threshold: cognitive 15 (skill default).

### D5. Checks and statuses
| Check | warn (action required) | warn (note only) | unknown |
|---|---|---|---|
| `static.checkstyle` | introduced checkstyle errors (CI's `ant check` would fail) | — | no config on base, tool missing, crash, file missing from output |
| `static.complexity` | — | a method crossed or worsened above 15, or new code at ≥15 | tool missing or parse errors |
| `static.duplication` | — | introduced duplicate ≥100 tokens | tool missing |
| `commit.perf-structure` | benchmark commit after the change | bench and change in one commit; perf PR with no benchmark | commit list unavailable |
`static.complexity` always lists every changed method with base → head cognitive complexity.
Perf PR: a changed `test/microbench/**` file (strong), JIRA label `performance` or component
`Test/benchmark` (strong), or two of title/summary perf keywords and JMH/benchmark in the PR body;
otherwise `not-applicable`. When checkstyle ran, `static.banned-api` and `static.deprecated-since`
are `not-applicable` ("superseded by checkstyle"); on branches without a config they run as before,
labelled an approximation. All four are advisory (non-blocking).

### D6. Cache
`<sha_dir>/static/results.json` keyed by tool version and config/ruleset sha; base-side results per
blob sha in `.work/static-cache/<tool>-<version>-<cfgsha>/<blobsha>.json`. Raw tool XML is kept next
to the results.

## Risks / Trade-offs

- [JDK missing or too old] → `unknown` with the reason; `cpr tools install` reports it.
- [Upstream config changes] → config read per base branch per run; its sha is in the cache key.
- [Complexity noise on big PRs] → only introduced findings drive the status; pre-existing are counts.
- [Owner's perf rule is rarely followed today (0 of 6 sampled PRs)] → combined commits are a note,
  only bench-after-change asks for action.
