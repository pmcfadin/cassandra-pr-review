## 1. Ingest

- [ ] 1.1 Old-side hunk ranges from the diff, with rename handling (tests: pure addition uses surrounding lines, new file)
- [ ] 1.2 Blame helper (line-porcelain, merge base, old path) and per-file non-merge log in a 5-year window
- [ ] 1.3 JIRA batch lookup by key and `issuelinks` in ticket normalize (test: ticket has links)
- [ ] 1.4 Budgets for hunks and files with a skipped count (test: huge PR)
- [ ] 1.5 Add `history` to the bundle; record a fixture bundle with history

## 2. Context (pure)

- [ ] 2.1 `patch by` / `reviewed by` parser (tests: several authors and reviewers, wrapped line, TBD ignored, git-author fallback)
- [ ] 2.2 Identity resolution with `cpr/data/people-aliases.json` (tests: alias, ASF id written as a name, unresolved)
- [ ] 2.3 Related tickets from blame with line counts and commits without a ticket (tests: modified lines lead to their tickets, commit without a ticket)
- [ ] 2.4 File experts with recency decay and window (test: recent work outranks old work)
- [ ] 2.5 Suggested reviewers (tests: author excluded, already reviewing)

## 3. Report

- [ ] 3.1 Model: `context` block, Context section after Triage, validation
- [ ] 3.2 Template: Context section and summary "Suggested reviewers" card (tests: summary card, no history)
- [ ] 3.3 `docs/report/context.md` aspect doc; aspect doc test covers it
- [ ] 3.4 Re-render the five published reports, review with the owner, then `bin/publish-pages`
