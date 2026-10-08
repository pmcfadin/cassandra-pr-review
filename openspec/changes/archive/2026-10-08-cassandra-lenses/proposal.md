## Why

Reviewers asked for the generic rustyrazorblade spec-flow lenses to be pulled out. They review any
codebase the same way; apache/cassandra ships its own review method (`.claude/skills/` on trunk:
shallow, targeted, deep, and mega review, with checklists distilled from hundreds of real Cassandra
bugs). On PR #5201 the generic panel also reported the same two problems four times: 11 findings for
5 issues, 9 must-fix entries for 3 real ones, which buries the signal reviewers came for.

## What Changes

- **BREAKING (panel):** replace the four spec-flow lenses with five project lenses built on
  apache/cassandra's own checklists: `cass-logic-boundary`, `cass-concurrency-lifecycle`,
  `cass-persistence-compat` (also observability), `cass-completeness-symmetry`, and
  `cass-test-regime`. `cassandra-standards` stays and gains a self-gating security check. The
  spec-flow plugin is no longer needed.
- Checklists are read at run time from apache/cassandra trunk, pinned to one sha per run, from an
  allow-list of paths, into a directory outside the PR worktree. A PR can never supply its own.
- The orchestrator picks a diff-size tier (small, medium, large) and each lens's checklist bundle;
  medium PRs get targeted categories chosen by the upstream INDEX "diff signals".
- Lenses report impact and confidence; severity is derived from both with one table.
- Duplicate findings across lenses merge deterministically into issues (no LLM call). The report
  leads with issues and shows which lenses found each.
- A small benchmark (`cpr bench`) of real PRs where reviewers caught bugs, to compare panels. This
  change runs the quick loop (2 cases, old vs new); the full comparison runs later.

## Non-goals

- Running Cassandra builds or tests in lenses.
- Upstream's multi-iteration category picking and nested-agent orchestration (one flat agent per
  lens instead).
- The full 36-run benchmark comparison (later, on demand).
- Changing apache/cassandra's skills.

## Research relied on

- docs/research/cassandra-review-skills.md §2 (categories), §6.2–6.7 (panel, input contract,
  severity mapping, tiers, trusted runtime loading), §8 (evaluation), §9 (open questions; owner
  decided: six lenses, all ours).
- docs/research/lens-findings-merge-and-eval.md Part 1 (merge algorithm, scores on #5201, merged
  record shape) and Part 2 (benchmark cases, contamination rules, metrics, acceptance bar).

## Capabilities

### New Capabilities

- `lens-benchmark`: known-issues cases, a run/score harness, and panel comparison metrics.

### Modified Capabilities

- `code-review-lenses`: new panel, trusted checklist loading, tiers, severity derivation, duplicate
  merging, and rendering of merged issues.
- `review-report`: the findings slot carries merged issues alongside per-lens results.

## Impact

- New: `.claude/agents/cass-*.md` (5), `cpr/config/lenses.json`, `cpr/lenses.py` (ref resolution,
  extraction, tiers, INDEX pre-filter), `cpr/merge.py`, `cpr/bench.py`, `bench/cases/*.json`.
- Changed: `cpr/config/panel.json`, `.claude/skills/review-pr/SKILL.md`, `cpr/review.py`,
  `cpr/cli.py`, the template's Code review section, `docs/report/code-review.md`,
  `.claude/agents/cassandra-standards-reviewer.md`.
- Removed: the dependency on the spec-flow plugin.
