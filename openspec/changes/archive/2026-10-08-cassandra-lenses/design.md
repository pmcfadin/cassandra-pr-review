## Context

Research: docs/research/cassandra-review-skills.md and lens-findings-merge-and-eval.md. Upstream's
review skills (trunk only; release branches have no `.claude/`) are checklists plus orchestration
that needs nested agents and a skill not in the tree. Our panel already gives one agent per lens in
parallel, so we take the checklists, item format, confidence rubric, and plausibility rules, and keep
the orchestration in `cpr`.

## Goals / Non-Goals

**Goals:** Cassandra-native review with no spec-flow dependency; checklists that track upstream
safely; one finding per real issue; a way to show the new panel is not worse.
**Non-Goals:** builds or tests in lenses; upstream's multi-iteration picking; full benchmark now.

## Decisions

### D1. Six lenses, all ours (owner decision)
| Lens | Checklists from trunk (shallow / deep / targeted) | Also covers |
|---|---|---|
| cassandra-standards | (own prompt) | ticket contract, standards, security (self-gating), PR edits to `.claude/`/AGENTS.md |
| cass-logic-boundary | specialists logic, boundary / deep-logic, deep-boundary / conditions-and-predicates, boundaries-and-numbers, null-and-type-safety, validation-and-input-handling | |
| cass-concurrency-lifecycle | specialists concurrency / deep-concurrency / concurrency-and-locking, lifecycle-and-ordering, state-and-resource-cleanup | |
| cass-persistence-compat | specialists resources / deep-resources / serialization-and-versioning, io-and-crash-safety | observability: logging of new failure paths, metric symmetry |
| cass-completeness-symmetry | specialists absence, completeness / deep-absence-completeness, deep-cross-cutting / api-contracts-and-completeness, refactor-aftermath | |
| cass-test-regime | cassandra-injvm-dtest SKILL; our docs/report/testing.md | suite fit, fails-without-fix, repeated runs |

The exact paths and the tier bundles live in `cpr/config/lenses.json`; the agent prompts in
`.claude/agents/cass-*.md` carry method, trust, severity table, and output contract, and contain no
copied upstream text.

### D2. Trusted loading (`cpr/lenses.py`)
After `cpr prepare` fetches trunk: resolve `origin/trunk` (or `lens_ref` from config) to a sha;
`git show <sha>:<path>` for each allow-listed path into `.work/pr/<N>/<head>/refdir/`; validate
UTF-8 and size (64 KB cap); write `refdir/manifest.json` (sha, files, per-lens bundle). `prepare`
prints the bundle per lens; the skill passes `refdir` and `bundle` to each agent.

### D3. Tiers and INDEX pre-filter
Non-test changed lines from the bundle's file list. Medium tier parses trunk's
`targeted-review/references/categories/INDEX.md` ("## <category>" then "Diff signals" bullets) into
keyword/regex signals and matches them against the diff; matched categories go to the lens that owns
them (D1), capped at 8 overall by match strength. Large tier ranks files by risk (production, size,
compatibility surface, concurrency paths from triage, blame heat) and passes the top files as `focus`.

### D4. Severity derivation
Lenses report `impact` and `confidence`; `cpr/review.py` recomputes severity from the table and
records `severity_corrected` when the lens's own severity differed. Old lens outputs without impact
keep their severity.

### D5. Deterministic merge (`cpr/merge.py`)
The research algorithm (stdlib, about 90 lines): cross-lens pairs only; T = 0.4·J(idents of
problem) + 0.3·J(words of problem) + 0.3·J(idents of fix); location bonus 0.30 / 0.15 / 0.10 / 0;
edge if T ≥ 0.18 and T+bonus ≥ 0.40; greedy union strongest first, never two findings from one lens
in one issue. Issue record: max severity, `severity_spread`, `lenses`, primary member's text
(highest severity, then most identifiers), `also_fixes`, `locations`, `members`. Constants in
`cpr/config/merge.json`. The 5201 outputs become a golden test.

### D6. Benchmark (`cpr/bench.py`)
Cases and the matching rule from the research (2.2–2.6). A run reuses `prepare` with a case's head
sha (detached worktree) and a cut-off context. Agents are launched by the review-pr skill flow, so
`bench run` prints the per-case lens prompts and directories for the session to execute, then
`bench score` reads the outputs. The quick loop runs B3 (21113) and B6 (5201) for both panels.

## Risks / Trade-offs

- [Upstream checklists change under us] → sha pinned per run and shown in the report; a smoke test
  fails loudly if allow-listed paths or INDEX parsing break.
- [Merge thresholds tuned on one PR] → golden tests per benchmark case; constants in config.
- [Six agents cost more than five] → small tier keeps bundles to about 2k tokens per lens; docs-only
  PRs skip lenses.
- [Trunk checklists mention APIs absent on release branches] → prompt line: ignore items about APIs
  that do not exist in the base branch.
- [Model may have seen benchmark fixes in training] → cases after the model's training data are
  preferred; noted per case.

## Open Questions

- Whether to raise severity when two lenses independently report the same issue (cross-lens
  reinforcement). Not in this change; `severity_spread` makes it visible.
