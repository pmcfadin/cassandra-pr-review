## Why

The owner's design (docs/design/report-v2.dc.html) drew the main reading path: nav, header, verdict,
To do, check list, finding cards, background cards, glossary. Everything else the report holds was placed
without a design and still looks like the old report, and the site index has its own older look. The owner:
"We need to make this design throughout."

## What Changes

- **One set of design tokens.** Colors, status colors, type scale, spacing, radii and the Red Hat fonts move
  to `cpr/assets/tokens.css`, inlined into both the report and the site index at render time.
- **Check-group detail in the design language.** Target branches, CI summaries, result archives, build and
  coverage (test classes, failing and flaky tests, per-file changed-line coverage), code style rows,
  compatibility: one table component (design card, header row, status pill cells, mono for code), a
  stacked card layout below 640px instead of sideways scrolling, and long tables capped with "Show all N".
- **"How this is judged" panels** become the design's quiet collapsible card, the same in every group.
- **Lab plan and diff view** cards match the Background cards (same header, icon, action buttons as the
  design's buttons). The diff iframe content is not restyled; only its frame and toolbar.
- **Every status and empty state** uses the design's pill and notice styles: the added verdicts (Cannot tell
  yet, Draft, Not reviewed yet), group words (Note, Unknown, Not needed), and empty states (code review not run,
  not built, no ticket, no CI attached), each with one sentence saying what would fill it.
- **Phone layout** is checked for every section at 390px: no sideways scroll, tables stack, tap targets
  >= 40px.
- **Site index redesigned** in the same system: header with counts per group, PRs grouped by who acts next
  (Ready for a committer, Waiting on reviewers, Waiting on the contributor, Drafts, Cannot tell), one row per
  PR with the verdict pill, the must-fix count, who acts, review effort in plain words, and code review and
  build chips only when they ran; author, branch and ticket on a quiet second line; date only.

## Impact

`cpr/assets/report.html`, new `cpr/assets/tokens.css`, `cpr/render.py`, `cpr/site.py` (index template and
summary fields), browser tests for report and index, `tests/test_site.py`. No change to checks, verdicts, or
what blocks a merge.
