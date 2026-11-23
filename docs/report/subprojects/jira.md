# JIRA ticket

## What is checked

Whether the PR names a ticket of its project, whether that ticket exists, whether the PR's title and branch agree on which ticket it is, whether the ticket is still open, and whether it has a Fix Version.

The keys are per project:

| Project | Keys |
|---|---|
| Cassandra Sidecar | `CASSSIDECAR-N`, and `CASSANDRASC-N` (the project's former key) |
| Cassandra Analytics | `CASSANALYTICS-N` |

A key is the prefix, an optional `-`, `_` or space, and 1 to 6 digits, in any case. The tool looks in four places, in this order: PR title, head branch name, PR body, commit messages. The first key found is the PR's ticket. A bare number in the branch name is not taken as a key (that rule is Cassandra's only). A `CASSANDRA-N` key does not count for these projects. The ticket is read anonymously from the [ASF JIRA](https://issues.apache.org/jira).

## Why

- Find an existing JIRA issue or start a discussion first, then create a ticket; JIRA is where design discussions and decisions are kept. Source: [Sidecar CONTRIBUTING.md](https://github.com/apache/cassandra-sidecar/blob/trunk/CONTRIBUTING.md), "Discuss" and "Create a Ticket".
- Analytics issues are tracked in the CASSANALYTICS JIRA project. Source: [Analytics README.md](https://github.com/apache/cassandra-analytics/blob/trunk/README.md), "Contributing".
- PR titles and squash-merged commit subjects take the form `KEY-N: summary`, and every `CHANGES.txt` entry names its ticket. Sources: [Sidecar CHANGES.txt](https://github.com/apache/cassandra-sidecar/blob/trunk/CHANGES.txt), [Analytics CHANGES.txt](https://github.com/apache/cassandra-analytics/blob/trunk/CHANGES.txt), and the trunk history of both repositories.
- Both projects have one long-lived branch, `trunk`; there are no release branches to map Fix Versions to.

## How each status is decided

When JIRA cannot be reached, every check below that needs the ticket reports **unknown** with the error.

"Feature branch" means any base other than `trunk` (for example Analytics' `mutation-tracking-support`).

### `jira.key-present`

**Blocking** on `trunk`, advisory on feature branches. Owner: contributor.

- **pass**: a key was found. The summary lists where.
- **warn** (advisory): no key, and the base is a feature branch. Moves the recommendation to "needs work".
- **fail**: no key, and the base is `trunk`. The recommendation becomes "needs contributor work".

### `jira.ticket-exists`

**Blocking.** Owner: contributor.

- **not-applicable**: no key was found.
- **unknown**: JIRA could not be reached. The recommendation becomes "insufficient evidence".
- **fail**: JIRA says the ticket does not exist.
- **pass**: the ticket was read. The summary shows its title and status.

### `jira.key-consistent`

Advisory. Owner: contributor.

- **not-applicable**: no key was found.
- **warn**: a different key of the project also appears in the title or the branch name. Keys in the body or commits do not count. Moves the recommendation to "needs work".
- **pass**: only one key appears across title and branch.

### `jira.not-resolved`

Advisory. Owner: reviewer.

- **not-applicable**: no ticket was read.
- **unknown**: JIRA could not be reached.
- **warn**: the ticket is Resolved or Closed. The patch may already have landed or been superseded.
- **pass**: any other status.

### `jira.fix-version`

Advisory. Owner: contributor.

With no release branches, every Fix Version that starts with a digit (for example `0.5.0`) maps to `trunk`.

- **not-applicable**: no ticket was read, or the base is a feature branch.
- **unknown**: JIRA could not be reached.
- **warn**: Fix Version is empty, or none of them starts with a digit. Moves the recommendation to "needs work".
- **pass**: the base is `trunk` and at least one Fix Version maps to it.

## How to fix

- **No key**: put it at the start of the PR title, `CASSSIDECAR-123: <summary>` or `CASSANALYTICS-123: <summary>`. If no ticket exists, create one in the project's JIRA first. An ASF JIRA account is free.
- **Ticket does not exist**: correct the typo in the key.
- **Two keys**: rename the PR title or the branch so both name the same ticket.
- **Ticket resolved**: check the ticket's comments and the trunk history for a commit with the key. If the change landed, close the PR; otherwise ask on the ticket to reopen it or open a follow-up.
- **Fix Version**: set the next release version on the ticket, or ask a committer to.

## Limits

- Key detection is pattern matching. A key mentioned in passing in the title wins over the real one in the branch.
- A PR whose key appears only in the body or commits still passes `jira.key-present`.
- A Sidecar ticket filed under `CASSANDRASC` is looked up under that key; whether JIRA redirects it to the new key is up to JIRA.
- The Fix Version check only confirms there is a version; it does not judge whether it is the right release.
- JIRA is read anonymously and cached. Changes after the fetch time (shown in About) are not reflected.
