## 1. Trusted checklists and tiers

- [x] 1.1 `cpr/config/lenses.json`: allow-listed trunk paths, per-lens bundles per tier, size cap, optional `lens_ref`
- [x] 1.2 `cpr/lenses.py`: resolve ref to sha, extract allow-listed files to refdir, validate, manifest (tests: PR edits the skills, upstream renamed a checklist)
- [x] 1.3 Tier selection and INDEX diff-signal pre-filter with the 8-category cap (tests: small patch, medium patch with serialization changes, large patch, docs-only)
- [x] 1.4 Smoke test against the real clone: every allow-listed path exists at origin/trunk and INDEX parses
- [x] 1.5 `cpr prepare` fetches trunk, builds refdir, prints per-lens bundles and tier

## 2. Lenses

- [x] 2.1 Agent prompts `.claude/agents/cass-{logic-boundary,concurrency-lifecycle,persistence-compat,completeness-symmetry,test-regime}.md`: inputs, trust, method, impact/confidence/severity table, JSON contract
- [x] 2.2 `cassandra-standards-reviewer`: self-gating security check and reporting PR edits to `.claude/`/AGENTS.md (test: `tests/test_agents.py` checks the prompt text; the password-in-a-virtual-table behaviour is runtime and covered by benchmark case B4)
- [x] 2.3 `cpr/config/panel.json` swap and `/review-pr` skill update (refdir, bundle, tier; no spec-flow) (tests: panel is data, no spec-flow dependency)

## 3. Severity and merge

- [x] 3.1 Severity derivation from impact and confidence with `severity_corrected` (test: severity follows the table)
- [x] 3.2 `cpr/merge.py` and `cpr/config/merge.json` (tests: PR 5201 regression golden, same line different issue, same-lens never merged)
- [x] 3.3 Wire merged issues into `review.merge`, the model, explain notes, and must-fix counts (test: findings in the diff view)

## 4. Report

- [x] 4.1 Template: issues first with lens chips, impact/confidence, per-lens detail below, checklist sha; summary headline "N issues (M findings from K lenses)" (tests: issues lead, lens status shown, report names the checklist version)
- [x] 4.2 Update docs/report/code-review.md (panel, tiers, trusted loading, severity table, merging, limits)

## 5. Benchmark

- [x] 5.1 `bench/cases/` for the six research cases with known issues and cut-offs (test: case is self-describing)
- [x] 5.2 Cut-off context builder (test: later link removed)
- [ ] 5.3 `cpr/bench.py` run and score, label cache (test: comparing panels on recorded outputs)
- [ ] 5.4 Quick loop: run old and new panels on B3 (PR #4887) and B6 (PR #5201), record results in `openspec/changes/cassandra-lenses/benchmark.md` (test: regression caught)

## 6. Ship

- [ ] 6.1 Re-run `/review-pr 5201` with the new panel, re-render and republish reports, review with the owner
