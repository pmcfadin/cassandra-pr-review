# Branches

## What is checked

Whether the branch the ticket's Fix Versions name has a PR. For Cassandra Sidecar and Cassandra Analytics that branch is always `trunk`: each has one long-lived branch, and Analytics also has a feature branch, `mutation-tracking-support`. There are no release branches and no backports.

The Branches & CI table shows one row per PR for this ticket (this PR and any siblings): base branch, PR, state, and head sha. This PR's row also shows the result of its head's GitHub checks; sibling rows show no CI. Siblings are found from GitHub PR links on the JIRA ticket and a GitHub search for the ticket key in the project's repository; a found PR counts only if its own title, branch, or body resolves to the same key.

## Why

- A change lands once, on `trunk`, as one squash-merged commit. Sidecar's repository allows only squash merges. Source: [Sidecar .asf.yaml](https://github.com/apache/cassandra-sidecar/blob/trunk/.asf.yaml), `enabled_merge_buttons`.
- Cassandra's one-PR-per-release-branch rule and merge order do not apply.

## How each status is decided

### `branches.coverage`

Advisory. Owner: contributor.

Every Fix Version that starts with a digit maps to `trunk`. A branch is covered when this PR or an **open** sibling PR targets it.

- **unknown**: JIRA could not be reached.
- **not-applicable**: no ticket was read, or no Fix Version maps to a branch.
- **warn**: no open PR targets `trunk`. Moves the recommendation to "needs work".
- **pass**: this PR or an open sibling targets `trunk`.

## How to fix

- If the PR targets a feature branch and the ticket has a Fix Version, either open the `trunk` PR when the work is ready, or clear the Fix Version until the work is meant for a release.
- If a sibling PR exists but is not found, make sure its title or branch carries the same ticket key.

## Limits

- A PR against a feature branch whose ticket has a Fix Version gets a warn, even when the feature branch is where the work belongs for now.
- Closed sibling PRs do not count.
- Fix Versions are taken as the truth.
