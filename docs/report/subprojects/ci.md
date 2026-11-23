# CI

## What is checked

Whether GitHub Actions CI ran on the PR's current head, whether it finished, and which checks failed.

Cassandra Sidecar and Cassandra Analytics run their CI as GitHub Actions workflows on pull requests to `trunk` (Sidecar's `.github/workflows/ci.yml`, Analytics' `.github/workflows/test.yaml`). Nothing is attached to JIRA. The tool reads, for the PR head sha, the commit's **check-runs** (one per CI job, with status and conclusion) and the **workflow runs** for that sha.

A first-time contributor's workflow runs wait at `action_required` until a maintainer approves them, and produce no check-runs until then.

## Why

- Sidecar's code quality checks (checkstyle, SpotBugs, RAT) run before its tests, and CI runs both. Source: [Sidecar TESTING.md](https://github.com/apache/cassandra-sidecar/blob/trunk/TESTING.md), "Continuous Integration".
- Sidecar's `trunk` is a protected branch with required status checks, and the head branch must be up to date before merging. Source: [Sidecar .asf.yaml](https://github.com/apache/cassandra-sidecar/blob/trunk/.asf.yaml), `protected_branches`.
- "Code must not be committed before CI results have been provided for all affected branches." Source: [Cassandra Project Governance](https://cwiki.apache.org/confluence/display/CASSANDRA/Cassandra+Project+Governance); both repositories are part of the Apache Cassandra project.

## How each status is decided

The checks do not need a JIRA ticket: the check-runs are read from GitHub for the head sha itself.

### `ci.evidence`

**Blocking.** Owner: committer.

- **not-applicable**: the PR targets a branch the CI workflows do not run for (anything but `trunk`, for example Analytics' `mutation-tracking-support`) and GitHub shows no check-run or workflow run for the head.
- **unknown**: GitHub could not be read; or there are no check-runs and at least one workflow run is `action_required` ("waiting for a maintainer to approve"); or at least one check-run has not completed ("still running"). Each waiting or pending run is listed. The recommendation becomes "insufficient evidence".
- **fail**: no check-runs and no workflow run waiting for approval ("CI not yet run on the head"). The recommendation becomes "awaiting review".
- **pass**: every check-run completed. The evidence counts passed, failed, skipped and cancelled checks. Failures do not affect this check; `ci.failures` reports them.

### `ci.freshness`

Advisory. Owner: committer.

- **not-applicable**: no check-runs.
- **pass**: any check-runs exist. They are read for the head sha, so they are always for the current head.

### `ci.profile`

**not-applicable** for both projects: "Not part of Cassandra Sidecar's process" (or Cassandra Analytics'). CI profiles (`pre-commit w/ upgrades`) are Cassandra's Jenkins CI; the GitHub workflows run the same jobs for every PR.

### `ci.failures`

Advisory. Owner: reviewer.

- **not-applicable**: no completed check-runs.
- **warn**: at least one completed check-run concluded `failure`, `timed_out`, or `startup_failure`. Each failed check is listed with its link; cancelled checks are listed but not counted. Failures are not compared with known flaky tests. The recommendation becomes "awaiting review".
- **pass**: no failed check. `success`, `neutral` and `skipped` count as not failed.

## How to fix

- **Waiting for approval**: a committer reads the change, then approves the workflow runs on the PR's Checks tab. A contributor can ask for this in a PR comment.
- **Not run**: push to the PR branch to trigger CI, or ask a committer to re-run the workflows. Workflows run only for PRs to `trunk`.
- **Still running**: wait for the checks to finish and re-run the review.
- **Failures**: open each failed check, fix failures the patch caused, and explain the rest on the PR (pre-existing or flaky, with a link to the ticket or run that shows it). Re-run a flaky job from the Checks tab.
- To run the same checks locally: `./gradlew codeCheckTasks` (checkstyle and RAT, plus SpotBugs in Sidecar) and the test commands in [Sidecar TESTING.md](https://github.com/apache/cassandra-sidecar/blob/trunk/TESTING.md) or [Analytics DEV-README.md](https://github.com/apache/cassandra-analytics/blob/trunk/DEV-README.md).

## Limits

- Only check-runs on the head sha are read. Results from a fork's CircleCI or any other system are not seen.
- Every check-run on the commit counts, whichever GitHub app created it; each is listed by name.
- If some checks exist while another workflow still waits for approval, the waiting workflow is not reported.
- A PR against a feature branch has no CI, so nothing about its tests is known; `ci.evidence` says so instead of failing.
- Failures are counted, not triaged.
