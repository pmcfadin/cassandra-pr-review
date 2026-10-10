## 1. Record

- [x] 1.1 `review.merge` records `about` (models from agent front matter, newest lens output time, tier, lines) and each lens's `focus` (tests)
- [x] 1.2 A report with no review carries `review.panel`; model validation for `about`, `panel`, `focus` (tests)

## 2. Render

- [x] 2.1 "About this review" box at the top of Code review; "not recorded" fallbacks; no-review variant; per-lens "Looks for" (browser tests: ran, older review, no review)
- [x] 2.2 `docs/report/code-review.md` describes the box

## 3. Ship

- [ ] 3.1 Re-render published reports so the box appears (the poller re-renders only on a new head)
