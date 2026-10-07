# CI

## What is checked

Whether pre-commit CI has run for every branch this patch targets, whether it ran on the current PR head, whether it used a profile that covers the change, and how many tests failed.

apache/cassandra runs no CI checks on pull requests. CI evidence is the `ci_summary*.html` file that `.build/run-ci` produces and that someone attaches to the JIRA ticket. The tool downloads every attachment whose name contains `ci_summary` and ends in `.html`, and reads the tested commit sha, the branch, the profile, and the pass, fail, and skip counts from it.

Each summary is assigned to a base branch: first by matching its sha to the head sha of this PR or a sibling PR, otherwise by a version (`4.0`, `4.1`, `5.0`, `6.0`) or `trunk` in the branch name it records or in the attachment's file name. When a branch has several summaries, the newest attachment wins.

The **target branches** are this PR's base plus the base of every open sibling PR (other PRs for the same ticket). The Branches aspect explains how siblings are found.

## Why

- "Code must not be committed before CI results have been provided for all affected branches." Source: [Cassandra Project Governance](https://cwiki.apache.org/confluence/display/CASSANDRA/Cassandra+Project+Governance).
- Every patch is expected to carry its CI artifacts, attached to the ticket. Contributors without CI access say so on the ticket and a reviewer or committer runs CI. Sources: [CONTRIBUTING.md](https://github.com/apache/cassandra/blob/trunk/CONTRIBUTING.md), "Continuous Integration"; [Contributing code changes](https://cassandra.apache.org/_/development/patches.html) step 4; [CI page](https://cassandra.apache.org/_/development/ci.html).
- Reviewers check for "pre-commit CI results attached to the ticket, for all affected branches (up to trunk, if applicable)" and ask "are there any regressions?". Source: [How to review](https://cassandra.apache.org/_/development/how_to_review.html), Testing.
- The `pre-commit w/ upgrades` profile is required whenever the patch could affect upgrades, serialization, or on-disk formats. Source: [CI page](https://cassandra.apache.org/_/development/ci.html), "Profiles".
- Failures are triaged against [Butler](https://butler.cassandra.apache.org) and JIRA to separate new regressions from known flaky tests. A pre-commit run with a few failures is normal if they are shown to be pre-existing or flaky. Source: [CI page](https://cassandra.apache.org/_/development/ci.html), "Post-commit CI".

## How each status is decided

The first three checks share a rule: with no ticket key, a ticket that does not exist, or JIRA unreachable, they report **unknown**, because there is nowhere to read CI from.

### `ci.evidence`

**Blocking.** Owner: committer.

- **unknown**: no ticket to read (see above). The recommendation becomes "insufficient evidence".
- **fail**: at least one target branch has no parsed summary assigned to it ("CI not yet run"). The recommendation becomes "blocked".
- **pass**: every target branch has a summary.

Summaries that could not be downloaded, could not be parsed, or could not be assigned to a branch are listed as evidence but do not count.

### `ci.freshness`

Advisory. Owner: committer.

Compares, for each target branch with a summary, the sha CI tested against that branch's PR head sha.

- **unknown**: no ticket to read.
- **not-applicable**: no target branch has a summary.
- **warn** (needs action): CI ran on an older commit for at least one branch. Moves the recommendation to "needs work".
- **warn** (informational): the summary recorded no usable sha (some `run-ci` versions write a placeholder). Shown, but does not change the recommendation.
- **pass**: every summary's sha matches its PR head.

### `ci.profile`

**Blocking.** Owner: committer.

A file is upgrade-sensitive when it is under `src/java/` and either its path is in messaging (`net/`), SSTable format (`io/sstable/format/`, or `io/sstable/` files named `*Version*`, `*Descriptor*`, `*Component*`, `*Metadata*`), commit log, hints, `SchemaKeyspace`, `SystemKeyspace`, any `*Serializer.java`, or a serializer under `db/rows/`; or its added lines implement `IVersionedSerializer`, `IVersionedAsymmetricSerializer`, or `IPartitionerDependentSerializer`.

- **not-applicable**: no upgrade-sensitive file changed; `pre-commit` is enough.
- **unknown**: upgrade-sensitive files changed, but there is no ticket to read or no parsed summary for any branch.
- **fail**: upgrade-sensitive files changed and at least one branch's summary shows no upgrade tests. A summary counts as having upgrade tests when its text mentions `upgrade-dtest`, `upgrade_dtest`, `upgrade-jdk`, or `upgrade_jdk`. The recommendation becomes "blocked".
- **pass**: every branch with a summary ran upgrade tests.

### `ci.failures`

Advisory. Owner: reviewer.

- **not-applicable**: no parsed summary.
- **warn**: the newest summaries report one or more failed tests in total. Up to five failing test names per branch are listed. Failures are not yet compared with known flaky tests. Moves the recommendation to "needs work".
- **pass**: zero failures across all summaries.

## How to fix

**Run pre-commit CI for each target branch.** Use `.build/run-ci` against your own Jenkins (`.build/run-ci --only-setup` creates one in your Kubernetes cluster), the project's pre-commit Jenkins, or an employer's. Options and profiles are described in `.build/run-ci.d/README.md` and on the [CI page](https://cassandra.apache.org/_/development/ci.html).

Choose the profile:

- `pre-commit`: the minimum for code changes.
- `pre-commit w/ upgrades`: when the change touches messaging, serialization, SSTable or commit log formats, hints, or system tables.
- `packaging`: build or packaging-only changes.

**Attach the results to the JIRA ticket**, one pair per branch: the `ci_summary` HTML file and the `results_details` archive. Open the ticket, choose More → Attach files (or drag the files onto the ticket). Keep the branch in the file name, for example `ci_summary_<fork>_CASSANDRA-12345-5.0_<build>.html`, so the branch can be identified even if the sha does not match. Then add a comment with the totals per branch and an explanation of each failure: pre-existing (link the Butler entry or JIRA ticket), flaky, or fixed in a later commit.

**No CI access?** Say so in a comment on the ticket and ask a committer to run it. `ci.evidence` stays failed until someone attaches results.

**Stale CI**: re-run CI on the current head, or say on the ticket why the later commits do not need it (for example, a comment-only change).

## Limits

- Only `ci_summary` HTML attachments on JIRA are read. Results posted as links (CircleCI workflows, ci-cassandra.apache.org builds), pasted as text in comments, or reported on the fork's GitHub Actions are not seen.
- A summary whose sha does not match any sibling PR and whose branch and file name contain no version is not assigned to a branch, so it does not count.
- If a summary's failure count is missing, it is treated as zero failures.
- Upgrade-test detection is a text search of the summary page. A profile name that does not contain those words is missed.
- The upgrade-sensitive file list is a path heuristic. Changes to serialization code in other places are missed, and a rename-only change to a `*Serializer.java` file is flagged.
- Failures are counted, not triaged. A PR with only known flaky failures still gets a warn until Butler comparison is added.
- Target branches come from open PRs. A branch that needs CI but has no PR yet is covered by the Branches aspect, not here.
