## Why

The report says whether a PR adds tests, but not whether the branch builds, whether the relevant
tests pass, or whether the changed lines run under any test. Research
(docs/research/build-and-coverage.md) and a one-off sandboxed run on PR #5201 (build 39 s, 25 test
classes in 245 s, 7 of 7 changed lines covered) show this works on the owner's Mac. Building runs the
PR author's code, so the owner decided: automatic builds only for committers' PRs, always sandboxed;
other PRs only when the owner approves a specific head sha.

## What Changes

- `cpr build <N>`: gate, then build the PR head in a throwaway build clone inside a `sandbox-exec`
  profile (no external network, writes only to the run directory, secrets unreadable), run selected
  unit tests with JaCoCo, and write `.work/build-runs/<N>/<head>/status.json`. Dependency resolution
  is the only networked step and uses the base commit's build file.
- Gate: the PR author is in the committer roster, or the owner passes `--approve` for that exact head
  sha (recorded). Otherwise the result is "not built (author is not a committer)".
- Test selection (stdlib): tests the PR adds or changes, name matches, references to changed classes
  and methods; skip dtests, long, burn, simulator; cap 25 classes.
- Changed-line coverage of added executable `src/java` lines from JaCoCo XML.
- A report section "Build & coverage" from the saved result for the current head: build status,
  tests run and failed, changed-line coverage per file with missed lines, tests selected and why, and
  a fixed note that line coverage does not prove the fix's behaviour is tested.
- New checks: `build.compiles` and `build.tests-pass` (blocking only when they ran and failed),
  `build.changed-line-coverage` (advisory).
- JDK per branch (4.0 and 4.1 → 11 with `CASSANDRA_USE_JDK11=true`; 5.0 → 17; trunk → 17), the
  4.0 arm64 JNA swap, sandbox artifacts reported as unknown.

## Non-goals

- Running unknown authors' PRs automatically, dtests, upgrade tests, GitHub Action (later).
- Benchmarks (perf-ab).

## Capabilities

### New Capabilities
- `build-and-coverage`: gate, sandboxed build and test run, selection, coverage, result file, section.

### Modified Capabilities
- (none; checks register through the existing registry)

## Impact

`cpr/build/` (new: gate, sandbox, runner, select, coverage), `cpr/config/build.json`,
`cpr/assets/sandbox.sb`, `cpr/checks/build.py`, `cpr/model.py`, template, `cpr/cli.py`
(`cpr build`), the review-pr skill (runs `cpr build` for committer PRs), docs/report/build.md.
