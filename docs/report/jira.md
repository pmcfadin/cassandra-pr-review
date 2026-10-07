# JIRA ticket

## What is checked

Whether the PR names a CASSANDRA ticket, whether that ticket exists, whether the PR's title and branch agree on which ticket it is, whether the ticket is still open, and whether its Fix Version covers the PR's base branch.

The tool looks for a key matching `CASSANDRA-NNNNN` (also `CASSANDRA_NNNNN`, `CASSANDRA NNNNN`, any case, 3 to 6 digits) in four places, in this order: PR title, head branch name, PR body, commit messages. In the branch name a bare 4 to 6 digit number also counts (`mck/21649/trunk`). The first key found, in that order, is the PR's ticket. The ticket is read anonymously from the [ASF JIRA](https://issues.apache.org/jira/projects/CASSANDRA).

## Why

- Find or create a JIRA ticket before doing the work. Sources: [CONTRIBUTING.md](https://github.com/apache/cassandra/blob/trunk/CONTRIBUTING.md) step 1; [Contributing code changes](https://cassandra.apache.org/_/development/patches.html), "Before You Start Coding".
- The ticket is where the project records the review: Reviewers, Authors, Fix Versions, CI results, and +1 votes. Committers find PRs through it. Source: [How to commit](https://cassandra.apache.org/_/development/how_to_commit.html).
- The suggested branch name is `<name>/CASSANDRA-NNNNN/<base-branch>`. Source: [CONTRIBUTING.md](https://github.com/apache/cassandra/blob/trunk/CONTRIBUTING.md).
- Fix Version records which release lines get the change. Patch releases on GA branches take bug fixes only; improvements and features go to trunk. Source: [Release Lifecycle](https://cwiki.apache.org/confluence/spaces/CASSANDRA/pages/132320437/Release+Lifecycle).
- PRs are never merged on GitHub; a committer pushes the commit and closes the PR. A Resolved ticket usually means the work already landed. Source: [How to commit](https://cassandra.apache.org/_/development/how_to_commit.html).

## How each status is decided

When JIRA cannot be reached, every check below that needs the ticket reports **unknown** with the error.

### `jira.key-present`

**Blocking** on release branches, advisory on feature branches. Owner: contributor.

- **pass**: a key was found. The summary lists where.
- **warn** (advisory): no key, and the base branch is a feature branch, meaning anything other than `trunk` or `cassandra-X.Y`. Feature-branch work often has no ticket. This warn moves the recommendation to "needs work".
- **fail**: no key, and the base is `trunk` or a `cassandra-X.Y` branch. The recommendation becomes "blocked".

### `jira.ticket-exists`

**Blocking.** Owner: contributor.

- **not-applicable**: no key was found.
- **unknown**: JIRA could not be reached. The recommendation becomes "insufficient evidence".
- **fail**: JIRA says the ticket does not exist.
- **pass**: the ticket was read. The summary shows its title and status.

### `jira.key-consistent`

Advisory. Owner: contributor.

- **not-applicable**: no key was found.
- **warn**: a different CASSANDRA key also appears in the title or the branch name. Keys in the body or commits do not count, since they often cite related tickets. Moves the recommendation to "needs work".
- **pass**: only one key appears across title and branch.

### `jira.not-resolved`

Advisory. Owner: reviewer.

- **not-applicable**: no ticket was read (no key, or the ticket does not exist).
- **unknown**: JIRA could not be reached.
- **warn**: the ticket status is Resolved or Closed. The patch may already have landed or been superseded. Moves the recommendation to "needs work".
- **pass**: any other status.

### `jira.fix-version`

Advisory. Owner: contributor.

Each Fix Version maps to a branch: `5.0.10`, `5.0.x`, and `5.0` map to `cassandra-5.0`; `6.x` maps to the newest `cassandra-6.Y` branch; a version with no matching release branch (for example `7.0` or `7.x` today) maps to `trunk`.

- **not-applicable**: no ticket was read, or the base is a feature branch.
- **unknown**: JIRA could not be reached.
- **warn**: Fix Version is empty, or no Fix Version maps to the PR's base branch. Moves the recommendation to "needs work".
- **pass**: one of the Fix Versions maps to the base branch.

## How to fix

- **No key**: put it at the start of the PR title, `CASSANDRA-12345: <summary>`, and name the branch `<you>/CASSANDRA-12345/<base>`. If no ticket exists, create one at [issues.apache.org/jira](https://issues.apache.org/jira/projects/CASSANDRA) first. An ASF JIRA account is free.
- **Ticket does not exist**: correct the typo in the key.
- **Two keys**: rename the PR title or open a new branch so both name the same ticket.
- **Ticket resolved**: check the ticket's Source Control Link and comments ("Committed as …"). If the change landed, close the PR. If the work continues, ask on the ticket to reopen it or open a follow-up ticket.
- **Fix Version**: set Fix Version on the ticket for every branch the patch should reach (for an unreleased line, use the `.x` form, for example `5.0.x`). If you lack JIRA permission, ask in a comment. If the base branch is wrong, retarget the PR.

## Limits

- Key detection is pattern matching. A bare number in a branch name (`fix-12345`) is read as a ticket key, and a key mentioned only in passing in the title wins over the real one in the branch.
- A PR whose ticket key appears only in the body or commits still passes `jira.key-present`.
- "Feature branch" means any base other than `trunk` or `cassandra-X.Y`. End-of-life branches such as `cassandra-3.11` count as release branches; nothing flags them as unlikely to accept changes.
- The Fix Version mapping assumes the newest release line without a branch is trunk. A Fix Version for a line whose branch does not exist yet, such as a future `6.1`, maps to trunk.
- The checks do not read the ticket's Component, Impacts, Since Version, Reviewers, or Test and Documentation Plan fields, though the report shows some of them.
- JIRA is read anonymously and cached. Changes on the ticket after the fetch time (shown in About) are not reflected.
