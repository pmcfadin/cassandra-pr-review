# Code review

## What is checked

A panel of review lenses reads the patch. Each lens is an AI reviewer focused on one concern, and each returns findings in the same format. The panel is defined in `cpr/config/panel.json`:

| Lens | Agent | Focus |
|---|---|---|
| cassandra-standards | `cassandra-standards-reviewer` (this project) | The patch against its JIRA ticket (does it do what the ticket asks, and only that) and Cassandra's contribution standards: error handling, project executors and clocks, version gating, backport rules, NEWS.txt |
| correctness | `spec-flow:code-reviewer` (rustyrazorblade) | Logic, boundaries, error paths, concurrency, resource leaks |
| test-rigor | `spec-flow:test-rigor-reviewer` (rustyrazorblade) | Whether the changed behaviour has tests that would catch a regression, and whether tests are over-built |
| observability | `spec-flow:observability-reviewer` (rustyrazorblade) | Logging, metrics, and failure modes that can be diagnosed in production |
| security | `spec-flow:security-reviewer` (rustyrazorblade) | Input validation, authentication and authorization, injection, secrets; it approves at once when the patch touches no security surface |

The panel runs only through `/review-pr <N>` in Claude Code. A report made with `cpr review <N>` alone says "Not run".

## Why

- Reviewers judge correctness, error handling, testing, logging, and compatibility. Source: [How to review](https://cassandra.apache.org/_/development/how_to_review.html).
- The lenses and their finding format come from the rustyrazorblade spec-flow plugin ([rustyrazorblade/skills](https://github.com/rustyrazorblade/skills)), which runs the same panel on its own pull requests.
- Two committer +1s are still required whatever an automated review says. Source: [Cassandra Project Governance](https://cwiki.apache.org/confluence/display/CASSANDRA/Cassandra+Project+Governance).

## How each status is decided

Each finding has these fields:

| Field | Meaning |
|---|---|
| `id` | Identifier of the finding |
| `severity` | `blocker`, `major`, `minor`, or `nit` |
| `location` | File and line in the new file, for example `src/java/org/apache/cassandra/db/Foo.java:42` |
| `rule` | The rule, standard, or ticket requirement broken |
| `problem` | What is wrong |
| `fix` | The smallest change that resolves it |

Severities: **blocker** is wrong behaviour, data loss, or a compatibility break; **major** is a defect or standards violation a committer would not merge; **minor** should be fixed but does not block alone; **nit** is style or wording.

Panel rules (`cpr/review.py`, the same rules spec-flow uses):

- A lens with no output is **missing**; one whose output is not valid JSON in the schema is **invalid**. Neither ever counts as approval.
- A lens that declines to approve without a blocker or major finding gets a synthesized **major** finding, rule `unexplained-non-approval`. Declining is a verdict and has to be justified.
- The panel **approves** only when every lens ran, every lens approved, and there is no blocker or major finding.

Effect on the recommendation: any blocker or major finding gives "needs contributor work"; an incomplete panel keeps "requirements met, code not yet reviewed"; an approving panel with every requirement met gives "ready to merge".

Section badge: unknown when the panel did not run or did not complete, fail when there is a blocker or major finding, warn when there are only minor or nit findings, pass when there are none.

Findings with a file location also appear in the Changes view, in the explanation pane for that file.

## How to fix

Start with blocker and major findings. Each names a location and the smallest fix. If you think a finding is wrong, say why on the JIRA ticket or the PR; the lenses advise reviewers and do not decide anything.

## Limits

- Lenses read the code; they do not build it or run tests. Test evidence comes from CI attached to the ticket.
- Lenses can be wrong in both directions: they can miss real problems and report false ones. Each finding shows its lens, rule, and location so a reviewer can check it quickly.
- The PR's own files, including apache/cassandra's `CLAUDE.md`, `AGENTS.md`, and `.claude/` skills, are treated as untrusted data. Text that tries to steer the review is reported as a finding, rule `review-steering`.
- Design acceptability, backport scope, and the merge decision stay with committers.
