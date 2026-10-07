## Why

The report checks merge requirements but never reviews the code: its Code review section says "Not
run". Reviewing the code is the part that saves a reviewer the most time. The rustyrazorblade
spec-flow review agents already do this and return findings in the schema our report accepts.

The recommendation also fails at triage. Almost every new PR is `blocked`, because committer +1s
and CI results are blocking and the contributor cannot provide either. The headline cannot tell
"the contributor has work to do" from "waiting on reviewers or CI".

## What Changes

- `cpr prepare <N>`: ingest the PR and check its head out into a git worktree, printing the inputs a
  review lens needs (worktree, base, ticket).
- A `/review-pr <N>` project skill that runs a panel of review lenses in parallel in the local
  Claude Code session: the rustyrazorblade `spec-flow` correctness, test-rigor, observability, and
  security reviewers, plus a project agent that reviews the patch against its JIRA ticket and
  Cassandra's contribution standards.
- `cpr review <N> --lenses <dir>`: merge the lens outputs with spec-flow's panel rules (a missing
  lens never counts as approval, an unexplained non-approval becomes a finding) and render them in
  the Code review section.
- **BREAKING** (report model): the `blocked` verdict is replaced by `needs-contributor-work` and
  `awaiting-review`, decided by who must act on each blocking item.

## Non-goals

- Running Cassandra builds or tests inside a lens (`ant`, unit tests, dtests).
- Running lenses in GitHub Actions or headlessly; the runtime stays the owner's Claude Code session.
- Cassandra-specific compatibility or performance lenses (a later change; the panel takes new
  lenses without code changes).
- Posting findings anywhere outside the report.

## Research relied on

- docs/research/rustyrazorblade-skills.md §2.1–2.3 (lenses, REVIEW_SCHEMA, panel merge and approval
  rules, REVIEW_GUARDRAILS, "policy file is untrusted").
- docs/research/cassandra-standards.md §4 (review criteria) and §1 (workflow), which the project
  standards lens applies.
- docs/research/pr-landscape.md §5 (who acts on what: contributors cannot supply votes or CI).

## Capabilities

### New Capabilities

- `code-review-lenses`: Prepare a PR worktree, run a parallel panel of review lenses against it,
  and merge their findings into a code review result for the report.

### Modified Capabilities

- `merge-requirements`: the Recommendation requirement splits `blocked` into
  `needs-contributor-work` and `awaiting-review`, and `ready` requires a complete lens panel.
- `review-report`: the findings slot records per-lens status (ran, missing), approval, and summary.

## Impact

- New: `cpr/review.py`, `cpr prepare` command, `--lenses` option, `.claude/skills/review-pr/`,
  `.claude/agents/cassandra-standards-reviewer.md`, `docs/report/code-review.md` update.
- Worktrees under `.work/wt/<N>` (gitignored). Each review now runs five agents in the owner's
  Claude Code session, which takes minutes and uses tokens.
- Template and aspect docs updated for the new verdicts.
