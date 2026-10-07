# Code review

## What is checked

A panel of six review lenses reads the patch. Each lens is an AI reviewer focused on one concern, and each returns findings in the same format. The panel is defined in `cpr/config/panel.json`; every lens is a project agent, so nothing depends on an outside plugin:

| Lens | Focus |
|---|---|
| cassandra-standards | The patch against its JIRA ticket (does it do what the ticket asks, and only that) and Cassandra's contribution standards: error handling, project executors and clocks, version gating, backport rules, NEWS.txt. It also runs a security check (auth, roles and permissions, TLS, JMX exposure, UDFs, secrets in logs or virtual tables) that reports nothing when the diff touches no security surface, and it reports PR edits to `.claude/` or `AGENTS.md` |
| cass-logic-boundary | Conditions and predicates, boundaries and numbers, null and type safety, validation of input |
| cass-concurrency-lifecycle | Locking and shared state, ordering and lifecycle, cleanup of state and resources |
| cass-persistence-compat | Serialization and versioning, I/O and crash safety, whether new failure paths are logged at the right level and metrics stay symmetric |
| cass-completeness-symmetry | Missing counterparts (the read path without the write path, the new option without its docs or tests), API contracts, what a refactor left behind |
| cass-test-regime | Whether the tests fit Cassandra's testing regime: the right suite for the change, whether the test fails without the fix, whether timing-sensitive tests need repeated runs |

Reviewers judge correctness, error handling, testing, logging, and compatibility, and the lenses follow the same list.

**Trusted checklists.** The five `cass-*` lenses work from the checklists the Cassandra project keeps in its own `.claude/skills/` directory. Those are read from `origin/trunk`, resolved to one commit for the whole run, and only from a fixed list of paths. They are never read from the PR's branch or from the base branch, so a patch cannot change how it is reviewed. The report names the commit as "checklists: apache/cassandra trunk @ <sha>". If a listed file is missing at that commit, the lens that needs it is reported as **missing**; there is no fallback to another copy.

**Tiers.** The amount of checklist each lens receives depends on how many non-test lines the patch changes:

| Tier | Changed non-test lines | What each lens gets |
|---|---|---|
| docs-only | Only documentation changed | No lenses run |
| small | Under 50 | Its shallow checklist |
| medium | 50 to 1,000 | Shallow checklists plus the targeted categories whose diff signals match the patch (at most 8 across the panel) |
| large | Over 1,000 | Deep checklists plus a list of focus files ranked by risk; the lens summary names the files it did not review |

Each lens summary states which checklists were applied and what was not reviewed.

The panel runs only through `/review-pr <N>` in Claude Code. A report made with `cpr review <N>` alone says "Not run".

## Why

- Reviewers judge correctness, error handling, testing, logging, and compatibility. Source: [How to review](https://cassandra.apache.org/_/development/how_to_review.html).
- The checklists come from apache/cassandra itself, so the lenses ask the questions the project's own review skills ask. Pinning to a commit makes a report reproducible; reading only from trunk keeps a patch from editing its own reviewer.
- Several lenses often notice the same defect. Merging their findings stops one problem from being counted and listed four times.
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
| `impact` | Optional. `data-loss`, `crash`, `hang`, `mixed-version-break`, `silent-wrong-result`, `performance`, or `cosmetic` |
| `confidence` | Optional. `high`, `medium`, or `low`: how sure the lens is that the failure can happen |

**Severity comes from impact and confidence.** When a finding names an impact, `cpr/review.py` sets the severity from this table, whatever severity the lens wrote. If they differ, the report keeps the lens's value as "was <severity>". A finding with no impact keeps its own severity.

| Impact | High confidence | Medium | Low |
|---|---|---|---|
| data-loss, crash, hang, mixed-version-break | blocker | major | minor |
| silent-wrong-result | major | major | minor |
| performance | minor | minor | nit |
| cosmetic | nit | nit | nit |

A finding with no concrete way to trigger it is dropped by the lens, not reported as a nit.

**Merging.** Findings from different lenses that describe the same problem are merged into one **issue**. For each pair of findings from different lenses the merger scores how much their problem texts share code identifiers (such as `FileUtils.delete`) and ordinary words, and how much their fixes share identifiers. Findings in the same file get a bonus that is larger the closer the lines are (within 3 lines, within 10 lines); findings at a place that is not a file line, such as the ticket, get a small fixed bonus. Two findings merge only when the text score reaches a floor and the total reaches a threshold, so two different problems on the same line stay separate. Pairs are joined strongest first, and an issue never holds two findings from one lens. The weights, bonuses, line distances, floor, and threshold are in `cpr/config/merge.json`.

An issue takes the highest severity of its members and lists every lens that reported it, every location, and the member findings. The wording, fix, rule, impact, and confidence come from the most severe member (ties go to the one naming the most identifiers). Fixes from other members that differ are kept as "also suggested".

Panel rules (`cpr/review.py`):

- A lens with no output is **missing**; one whose output is not valid JSON in the schema is **invalid**. Neither ever counts as approval.
- A lens that declines to approve without a blocker or major finding gets a synthesized **major** finding, rule `unexplained-non-approval`. Declining is a verdict and has to be justified.
- The panel **approves** only when every lens ran, every lens approved, and there is no blocker or major finding. Merging does not change this.

The report headline reads "N issues (M findings from K lenses)", where K counts the lenses that reported at least one finding. "Must fix" counts issues, not findings.

Effect on the recommendation: any blocker or major issue gives "needs contributor work"; an incomplete panel keeps "requirements met, code not yet reviewed"; an approving panel with every requirement met gives "ready to merge".

Section badge: unknown when the panel did not run or did not complete, fail when there is a blocker or major issue, warn when there are only minor or nit findings, pass when there are none.

The Code review section lists the issues first, then each lens's status, approval, summary, and raw findings. Issues with a file location also appear in the Changes view, once per file, naming every lens that reported them.

## How to fix

Start with blocker and major issues. Each names its locations and the smallest fix. If you think an issue is wrong, say why on the JIRA ticket or the PR; the lenses advise reviewers and do not decide anything.

## Limits

- Lenses read the code; they do not build it or run tests. Test evidence comes from CI attached to the ticket.
- Lenses can be wrong in both directions: they can miss real problems and report false ones. Each issue shows its lenses, rule, and location so a reviewer can check it quickly.
- Merging is a text-overlap heuristic. Its thresholds were tuned on one real PR (apache/cassandra#5201, where 11 findings became 5 issues), so it can leave a duplicate unmerged or, rarely, join two different problems. The member findings stay visible under each lens.
- Checklists are upstream's. If trunk changes a checklist, reports made later follow it; the sha in the report says which version was used. Items about APIs that do not exist on a release branch are told to be ignored, but a lens can still apply one.
- The PR's own files, including apache/cassandra's `CLAUDE.md`, `AGENTS.md`, and `.claude/` skills, are treated as untrusted data. Text that tries to steer the review is reported as a finding, rule `review-steering`.
- Design acceptability, backport scope, and the merge decision stay with committers.
