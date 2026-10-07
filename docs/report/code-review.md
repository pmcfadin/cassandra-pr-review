# Code review

## What is checked

Nothing yet. Automated code review lenses are not part of this version, so this section says "Not run in this version" and its badge is unknown. The rest of this page describes what the section will hold once lenses exist, so the format is known ahead of time.

A lens is a reviewer focused on one concern: for example correctness, test rigour, compatibility, or performance. Each lens reads the diff and returns findings.

## Why

- Reviewers judge code style, error handling, documentation, testing, logging, and compatibility. Source: [How to review](https://cassandra.apache.org/_/development/how_to_review.html).
- The project keeps its own review methods in `.claude/skills/` in [apache/cassandra](https://github.com/apache/cassandra/tree/trunk/.claude/skills): shallow-review (six lenses: logic and types, boundaries and I/O, concurrency and state, resources and serialization, absence, API completeness), targeted-review (categories such as serialization and versioning, lifecycle and ordering, concurrency and locking, IO and crash safety), and mega-review for patches above 1000 lines. Future lenses should reuse these. Source: [AGENTS.md](https://github.com/apache/cassandra/blob/trunk/AGENTS.md) and `.claude/skills/README.md`.
- Two committer +1s are still required whatever an automated review says. Source: [Cassandra Project Governance](https://cwiki.apache.org/confluence/display/CASSANDRA/Cassandra+Project+Governance).

## How each status is decided

There are no checks in this section. How it will work:

Each finding has these fields:

| Field | Meaning |
|---|---|
| `id` | Stable identifier of the finding |
| `severity` | `blocker`, `major`, `minor`, or `nit` |
| `location` | File and line, for example `src/java/org/apache/cassandra/db/Foo.java:42` |
| `rule` | The rule or pattern broken |
| `problem` | What is wrong |
| `fix` | What to change |

Severities:

- **blocker**: wrong behaviour, data loss, or a compatibility break. Must be fixed before merge.
- **major**: a real defect or a missing test for changed behaviour. Should be fixed before merge.
- **minor**: worth fixing; does not block.
- **nit**: style or wording.

Findings are grouped by lens and ordered by severity. Any blocker or major finding makes the recommendation "needs work". When lenses ran and found no blocker or major issue, and every requirement check passes, the recommendation can become "ready to merge".

Section badge: unknown when no lens ran, pass when lenses ran with no findings, warn when there are findings.

## How to fix

Nothing to do in this version. Ask for a human review on the JIRA ticket.

## Limits

- No automated code review runs today. "Requirements met" on the summary does not mean the code has been reviewed.
- When lenses arrive, they will advise reviewers, not replace them. Design acceptability, backport scope, and the merge decision stay with committers.
