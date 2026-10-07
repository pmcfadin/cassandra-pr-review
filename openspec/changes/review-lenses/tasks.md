## 1. Verdict by owner (spec: merge-requirements)

- [x] 1.1 Replace `blocked` with `needs-contributor-work` and `awaiting-review` in recommend.py (tests: contributor work outranks waiting, only reviewers left, draft, unknown dominates)
- [x] 1.2 `ready` requires a complete approved panel; incomplete panel stays unreviewed (tests: incomplete panel, review findings need contributor work)
- [x] 1.3 Update the template's verdict styling and docs/report/summary.md for the new verdicts

## 2. Prepare and merge (spec: code-review-lenses)

- [x] 2.1 `cpr/config/panel.json` with the default five lenses (test: panel is data)
- [x] 2.2 Worktree create/move in clone.py and `cpr prepare <N>` printing JSON and writing the ticket summary file (tests: first prepare, head moved)
- [x] 2.3 `cpr/review.py`: load lens files, validate schema, missing/invalid lenses, unexplained non-approval, panel approval (tests: missing lens, unexplained non-approval, invalid output)
- [x] 2.4 `cpr review --lenses <dir>`: merge, render, and add finding locations to the diff view's explain map (tests: findings in the diff view, lens status shown)

## 3. Lenses and skill

- [x] 3.1 `.claude/agents/cassandra-standards-reviewer.md` (ticket as contract, Cassandra standards, review schema)
- [x] 3.2 `.claude/skills/review-pr/SKILL.md`: prepare, parallel lens fan-out with guardrails, save outputs, render
- [x] 3.3 Update docs/report/code-review.md for the panel, lens statuses, and approval rules

## 4. End-to-end

- [x] 4.1 Run `/review-pr 5201` and review the report with the owner
