# Build & coverage

## What is checked

Three checks read the result of `cpr build <N>`, which builds the PR head, runs a selection of unit tests with JaCoCo, and saves the outcome for that exact head sha. `cpr review` never builds; it only reads the saved result.

- `build.compiles`: did the PR branch compile.
- `build.tests-pass`: did the selected unit tests pass.
- `build.changed-line-coverage`: did the lines the PR added under `src/java` run under those tests.

The section also shows the tests table (classes, run, failed, errors, skipped, failures), coverage per file with the missed line numbers, the list of selected test classes with the reason each was picked, and any failure we blame on the sandbox rather than on the PR.

**Who gets built.** Building runs the PR author's code, so it is limited. A PR is built automatically only when its author is on the committer roster. For any other PR the section says "Not built for this head" until the owner approves that exact head with `cpr build <N> --approve`. Approval covers one head sha; a push needs a new approval.

**The sandbox.** Every step that runs the author's code runs inside macOS `sandbox-exec`: no external network, writes only to the run directory, and no read access to credential directories (`~/.ssh`, `~/.aws`, `~/.gnupg`, GitHub and Claude configuration, the keychain). The build works in a throwaway clone with its own copy of the Maven cache. Only dependency resolution uses the network, and it uses the base commit's build file, which the PR cannot change. Some tests fail only because of the sandbox (for example `transferTo0: Operation not permitted` in streaming tests). Those are reported as unknown, not as failures of the PR.

**Reading the numbers.** Line coverage shows which changed lines ran under the selected tests; it does not show that the fix's behaviour is tested. Read with the test regime lens. The selection is a heuristic (tests the PR changes, name matches, references to changed classes and methods; at most 25 classes; no dtests, long, burn or simulator tests), so a missed line can mean "the right test was not selected".

## Why

- Reviewers are asked to confirm that the patch builds and that "tests exist, are comprehensive, and actually exercise the behaviour". Source: [How to review](https://cassandra.apache.org/_/development/how_to_review.html), section Testing. CI results attached to JIRA say this for the committer's own run; this section says it for the head the reviewer is looking at.
- Changed-line coverage is a cheap, objective hint about the second half of that sentence: an added line that no selected test reaches is a line to ask about. In the research run on PR 5212, all 10 added executable lines were missed, which pointed at interrupt-handling code that no test triggers. Source: `docs/research/build-and-coverage.md`, section 4.
- The owner decided that automatic builds are for committers' PRs only, always sandboxed, because building is executing someone else's code. Source: the `build-and-coverage` OpenSpec change.

## How each status is decided

The saved result has a `status`: `pass`, `tests-failed`, `build-failed`, `timeout`, `unknown` or `not-built`. The checks use it with the test and coverage data in the same file.

A result counts only if its `head` equals the PR's current head sha. A result for an older head, or no result at all, is treated as not built: all three checks are not-applicable with the reason "not built", the section shows no old numbers, and nothing blocks. Unknown results never block either.

### `build.compiles`

**Blocking.** Owner: contributor.

- **fail**: `status` is `build-failed`. The evidence lists the compile error lines (file, line, message) from the run.
- **pass**: the build ran: status `pass` or `tests-failed`, or status `unknown` with test results recorded (tests cannot run without a build).
- **unknown**: status `timeout`, or status `unknown` with no test results (the build outcome was never seen). Does not block.
- **not-applicable**: not built for this head.

### `build.tests-pass`

**Blocking.** Owner: contributor.

- **fail**: status `tests-failed` and at least one failure that is not a sandbox artifact. The evidence names each failing class and method with its first message line.
- **pass**: status `pass` with tests run and no failures or errors.
- **unknown**: status `timeout`; status `unknown`; only sandbox artifacts failed; or no test results were recorded. Does not block.
- **not-applicable**: not built for this head, or the build failed so no tests ran.

### `build.changed-line-coverage`

**Advisory.** Owner: contributor. A warning here is a note and does not move the verdict.

- **warn**: at least one added executable line did not run. The evidence has one row per file, "covered N/M, missed lines ...". A line that ran only partly (some branches or instructions never ran) counts as covered and is flagged "partly".
- **pass**: every added executable line ran.
- **unknown**: coverage was not measured, or a changed file is missing from the JaCoCo report. Does not block.
- **not-applicable**: not built, the build failed, or the PR adds no executable line under `src/java` (tests, docs and comments only).

## How to fix

- **Compile errors**: fix them and run `ant jar` and `ant build-test` on the branch.
- **Failing tests**: run the named class with `ant testsome -Dtest.name=<class> -Dtest.methods=<method>`. If it also fails on the base branch, say so on the ticket.
- **Missed lines**: add a test that reaches them, in the lowest suite that can (see the Testing aspect). If a missed line is deliberately untestable, say why in the PR.
- **Not built, committer's PR**: run `cpr build <N>`. The `/review-pr` skill does this for you.
- **Not built, other authors**: the owner runs `cpr build <N> --approve` after reading the diff, then re-renders.
- **Timeout or unknown**: read the reason shown in the banner; it names a missing JDK (with the install command), a network problem, or a sandbox artifact.

## Limits

- **Selected tests only.** At most 25 unit test classes run. Passing them says nothing about the rest of the suite, dtests, upgrade tests or the simulator.
- **Coverage is not proof.** A line can run under a test that does not assert anything about it.
- **Sandbox artifacts are guessed from known messages.** A real failure that looks like a sandbox error is reported as unknown, never as a pass.
- **One run per head.** Flaky tests are not rerun in this version; a single failure is reported as failed.
- **macOS only.** The sandbox and JDK handling are for the owner's machine. Builds do not run in the GitHub Action.
- **Committers' PRs by default.** For every other PR the section is empty until the owner approves a head.
