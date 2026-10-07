# Branches

## What is checked

Whether every branch named by the ticket's Fix Versions has a PR. The Branches & CI table shows one row per PR for this ticket (this PR and its siblings): base branch, PR, state, head sha, and the CI summary assigned to that branch, if any.

Sibling PRs are found two ways: GitHub PR links recorded on the JIRA ticket, and a GitHub search for the ticket key in apache/cassandra. A found PR counts as a sibling only if its own title, branch, or body resolves to the same ticket key.

## Why

- Open **one PR per target branch**. A fix for several release lines arrives as one PR per branch, linked by the ticket key. Source: observed practice, and the merge workflow in [How to commit](https://cassandra.apache.org/_/development/how_to_commit.html).
- Fix the oldest applicable branch first, then merge forward: `cassandra-4.0 → cassandra-4.1 → cassandra-5.0 → cassandra-6.0 → trunk`. Contributors should say which versions they verified as affected, patch the lowest branch, and check the patch merges cleanly upward. Sources: [How to commit](https://cassandra.apache.org/_/development/how_to_commit.html); [Contributing code changes](https://cassandra.apache.org/_/development/patches.html), "Bug Fixes" (that page lists old branch names; follow its intent).
- Patch releases on GA branches take bug fixes only. Improvements and features go to trunk only. Source: [Release Lifecycle](https://cwiki.apache.org/confluence/spaces/CASSANDRA/pages/132320437/Release+Lifecycle).
- CI must cover all affected branches before commit. Source: [Cassandra Project Governance](https://cwiki.apache.org/confluence/display/CASSANDRA/Cassandra+Project+Governance).

## How each status is decided

### `branches.coverage`

Advisory. Owner: contributor.

Each Fix Version is mapped to a branch the same way as in the JIRA aspect (`5.0.x` → `cassandra-5.0`; a version with no release branch, such as `7.x`, → `trunk`). A branch is covered when this PR or an **open** sibling PR targets it.

- **unknown**: JIRA could not be reached.
- **not-applicable**: no ticket was read, or Fix Version is empty, so the expected branches are unknown.
- **warn**: at least one Fix Version branch has no PR. Moves the recommendation to "needs work".
- **pass**: every Fix Version branch has a PR.

## How to fix

- Open a PR against each missing branch, using a branch name like `<you>/CASSANDRA-12345/cassandra-5.0`, and put the ticket key in each PR title so the tool and the ASF bot link them.
- Backports often differ from the trunk patch. Make each PR apply cleanly to its own base.
- If a branch does not need the fix (the bug is not present there, or the change is a feature for trunk only), remove that Fix Version from the ticket or explain on the ticket. The check will keep warning until the Fix Versions match the PRs.
- If a sibling PR exists but is not found, make sure its title or branch carries the same ticket key.

## Limits

- Closed sibling PRs do not count. After a committer pushes one branch and closes its PR, the check may warn for that branch.
- Patches offered as fork compare links or branch names in JIRA comments, not as PRs, are not found.
- Fix Versions are taken as the truth. If the ticket's Fix Versions are wrong, the check is wrong in the same way.
- The check does not judge whether a branch should get the change (bug fix versus feature, end-of-life branches). That decision belongs to the committer.
- It does not test whether the patch merges forward cleanly.
