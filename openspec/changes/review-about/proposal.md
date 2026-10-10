## Why

The Code review section never says what the code review is. A reader sees "Found by 6 automated review
lenses" and a list of findings, with no statement that the reviewers are AI, which model ran, when it
ran, or what a "lens" looks for. The explanation exists only in the closed "How this is judged" panel,
and the report model does not record the model or the run time at all. On the 125 published reports
with no review, "Not run" does not say what would run. The owner asked for an "About this review" box.

## What Changes

- `cpr/review.py` records, when `/review-pr` merges the lens outputs, a `review.about` block: the models
  the lens agents pin (the `model:` front matter of `.claude/agents/<agent>.md`), when the lenses wrote
  their output (newest lens file), and the size tier and changed-line count from the lens plan. Each lens
  entry carries its `focus` from `cpr/config/panel.json`.
- A report with no review carries `review.panel` (each lens's name and focus), so it can say what would run.
- The template shows "About this review" at the top of the Code review section: a plain statement that the
  reviewers are AI, can be wrong, and that committers decide; Model, Ran, Patch size, Checklists (linked
  to the commit); and the lenses with what each looks for. Without a review: the lenses that would run and
  how to run them. Fields a saved review lacks read "not recorded".
- The per-lens cards show "Looks for: <focus>". The section subtitle says "AI review lenses".

## Non-goals

- Changing how lenses run, which model they use, or how findings are merged.
- Re-rendering published reports; they pick the box up the next time each is rendered.

## Research relied on

None from `docs/research/`. Facts come from `.claude/agents/*.md`, `cpr/config/panel.json`, and
`docs/report/code-review.md`.

## Capabilities

### Modified Capabilities
- `code-review-lenses`: Render findings.

## Impact

`cpr/review.py`, `cpr/model.py` (not-run panel, validation), `cpr/assets/report.html`,
`docs/report/code-review.md`, `tests/test_review.py`, `tests/browser/build_fixture.py`,
`tests/browser/report.spec.js`.
