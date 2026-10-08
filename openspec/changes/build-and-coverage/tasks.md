## 1. Runner

- [x] 1.1 `cpr/config/build.json` (JDK per branch, caps, skip suites) and `cpr/assets/sandbox.sb` (from the 5201 run) (test: config loads; profile has the deny list)
- [x] 1.2 Gate and approvals (tests: committer allowed; non-committer not-built; approval per head)
- [x] 1.3 Build clone, m2 copy, resolve at merge-base, head checkout, JNA swap, sandboxed ant with scrubbed env, caps, cleanup, fetch-clone integrity check (tests with a fake runner)
- [x] 1.4 Test selection and changed-line coverage ported from the prototypes (tests: 5201 fixture selects LogTransactionTest; coverage parse of a recorded report.xml)
- [x] 1.5 Status mapping and status.json (tests: compile error, test failure, sandbox artifact, JDK missing)
- [x] 1.6 `cpr build <N> [--approve]`

## 2. Report

- [x] 2.1 Checks `build.compiles`, `build.tests-pass`, `build.changed-line-coverage` (tests per status)
- [x] 2.2 Section "Build & coverage" from the saved run for the current head (tests: stale run; browser test)
- [x] 2.3 docs/report/build.md; review-pr skill runs `cpr build` for committer PRs

## 3. Ship

- [ ] 3.1 Run on a committer's PR and on 5201 (approved), render, review with the owner
