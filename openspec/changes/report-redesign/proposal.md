## Why

The owner redesigned the report (canvas "PR Review Report", saved as `docs/design/report-v2.dc.html`).
The new layout answers "can this merge, and who has to do what" first, in plain words, and moves
detail and background below it. The current template shows every section as a peer tab with
Fail/Warning badges.

## What Changes

- Rebuild `cpr/assets/report.html` to the design: dark left nav grouped Overview / Checks /
  Background / Help with status icons; a header with PR number, base branch, author, ticket, and
  title; one scrolling page instead of one-section-at-a-time tabs.
- Overview: the verdict card (icon, headline, one sentence with must-fix and people counts, "steps to
  merge" pills for Ticket, Tests, Code review, CI, +1 votes) and a To do panel grouped by who acts
  (Contributor, Committer, Reviewers), must-fix items first, optional items behind a toggle, each item
  expandable to its how-to-fix detail.
- Checks: one collapsible row per check group, problems first, labelled Must fix / Should fix /
  Passed (plus Unknown and Not needed), each check with its summary, "How to fix", owner tag, and the
  group's "How this is judged" doc. Build & coverage, Code style (static analysis), and Compatibility
  are check groups too.
- Code review findings: severity count chips, one expandable card per merged issue (severity,
  headline, location, problem, suggested fix, raised by which lenses), per-lens detail collapsed below,
  checklist version line.
- Background: Review effort (three-step bar, signals), Who knows this code, History of this code,
  Files changed (with the embedded diff view behind "Open the diff view"), and the Lab plan (Not run
  banner, Copy and Download).
- Help: a glossary of project terms. Footer with tool version, time, commit, read-only note.
- Red Hat Text and Red Hat Mono, the design's palette and accessibility rules (real buttons,
  aria-expanded, 4.5:1 text, 44px targets), light theme only, works at phone width, prints expanded.

## Non-goals

- Changing checks, verdicts, or the model's meaning; a few derived fields are added for the view.

## Capabilities

### Modified Capabilities
- `review-report`: layout and navigation of the report.

## Impact

`cpr/assets/report.html` (rewrite), `cpr/model.py` (derived view fields: header facts, steps to merge,
to-do by role, glossary), `cpr/render.py` if fonts are linked, browser tests rewritten to the new DOM,
docs screenshots in README if any.
