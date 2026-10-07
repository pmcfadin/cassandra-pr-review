## Context

The report's Code review section is an empty slot that accepts the rustyrazorblade review schema.
The spec-flow plugin ships review agents that take `worktree`, `base`, and `change`, diff
`base...HEAD`, and return that schema as JSON. They are Claude Code agents, so they run inside a
Claude Code session; the owner chose to run AI review locally for now.

## Goals / Non-Goals

**Goals:** real code review findings in the report for any PR, using the installed rustyrazorblade
agents unchanged; a verdict that separates contributor work from waiting on reviewers.

**Non-Goals:** headless or CI execution, building or testing Cassandra in a lens, new
Cassandra-specific compatibility/performance lenses (later; the panel file takes them).

## Decisions

### D1. Orchestration lives in a project skill; merging lives in Python
`/review-pr <N>` (`.claude/skills/review-pr/SKILL.md`) runs `bin/cpr prepare`, spawns every lens in
one message so they run in parallel, saves each lens's JSON, then runs
`bin/cpr review <N> --offline --lenses <dir>`. All panel rules (missing lens, unexplained
non-approval, schema validation, approval) live in `cpr/review.py`, so they are unit-tested rather
than left to a prompt. Alternative: a Workflow script. Rejected for now: Workflow runs need the
owner's explicit opt-in each time, and the skill gives the same parallel fan-out.

### D2. Worktree per PR
`git worktree add --detach .work/wt/<N> refs/cpr/pr/<N>` from the full clone; later runs
`checkout --detach --force <head>` in place. Lenses diff `<merge-base>...HEAD`, the exact range the
report's diff view shows.

### D3. Panel definition
`cpr/config/panel.json` lists `{name, agent}`; the skill reads it via `cpr prepare` output. The
spec-flow `reviewer` lens is not used: it checks code against an OpenSpec change, which Cassandra PRs
do not have. Its role is taken by `cassandra-standards-reviewer` (a project agent in
`.claude/agents/`), which treats the JIRA ticket as the contract.

### D4. `change` argument
The spec-flow lenses take an OpenSpec change name "for context". We pass
`none — external apache/cassandra PR #<N> for <KEY>; the contract is the JIRA ticket in <ticket file>`.

### D5. Guardrails
Each lens prompt carries spec-flow's REVIEW_GUARDRAILS plus: no builds or tests (report
`tests_ran: none`, `tests_detail: "not run: review-only lens"`), and every file in the worktree
(including apache/cassandra's own CLAUDE.md, AGENTS.md, and .claude/ skills, which a PR can modify)
is untrusted data. Lenses read files; they do not adopt instructions from them.

### D6. Verdict by owner
`blocked` splits by who must act. Contributor items come first because they are the only ones the
contributor can move; `awaiting-review` means the contributor is done. Check owners already exist in
the check results.

## Risks / Trade-offs

- [Cost and time: five agents per PR] → the owner runs `/review-pr` deliberately; `cpr review`
  without lenses stays cheap.
- [Lens prose quality varies; findings may be wrong] → findings show lens, rule, and location so a
  reviewer can verify; they inform, the committer decides.
- [Prompt injection through the PR] → guardrails, read-only tool sets on most lenses, and the
  requirement to report injected instructions as findings.
- [code-reviewer/security-reviewer invoke built-in skills that may not be available to subagents]
  → those agents fall back to an inline pass per their own instructions.

## Open Questions

- Whether to add Cassandra-specific compatibility and performance lenses next, or tune these first.
