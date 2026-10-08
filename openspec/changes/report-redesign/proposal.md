## Why

The summary page tries to say everything at once: a long recommendation with every reason expanded,
the triage signals, the reviewers card, and a grid of every check, all above the fold. Contributors
who are new to the project, or who read English as a second language, have to read a wall of text
to learn three things: can this merge, what is missing, and who has to act.

The owner reviewed a design for the report (a Design canvas made in a Claude session, PR 5201 as
the example) and chose: a short summary that answers those three things first and reveals detail on
demand; an "inspection sheet" look (navy ink, dark navigation, teal / ochre / vermilion status
colours); and Red Hat Text and Red Hat Mono as the typefaces.

## What Changes

- Summary: a compact header (number, base, author, ticket and status, title); one status card with
  the recommendation, one plain sentence, and a row of merge steps (Ticket, Tests, Build, Code review,
  CI, Votes) that link to their sections; a collapsed "To do" bar that counts the must-fix items per
  owner and opens to the items grouped by owner, each item opening to its action. Advisory items
  sit behind "Show N optional items". Review effort and suggested reviewers become two small cards;
  the grid of every check moves into a collapsed "Every check" panel; a collapsed glossary ("Words
  used in this report") explains project terms in plain words.
- Navigation: a "To do" link under the PR number (`#todo` opens the summary with the list open).
- Visual language: new colour tokens for light and dark, dark navigation in both themes, square
  status tags that always carry a glyph and a word, Red Hat Text and Red Hat Mono embedded in the
  report as base64 `@font-face` data (SIL Open Font License, files in `cpr/assets/fonts/`), with
  system fonts as the fallback.
- `docs/report/summary.md` describes the new summary layout.

## Non-goals

- No change to the report model, the checks, the recommendation rules, or any other section's content.
- No change to routing: one section at a time, the section in the URL fragment.
- No web fonts loaded over the network; the report stays one offline file.

## Research relied on

None from `docs/research/`; this is a presentation change. The audience statement in
`openspec/config.yaml` (contributor first, then reviewers and committers) drives the ordering.

## Capabilities

### Modified Capabilities
- `review-report`: Summary first page, Left-hand navigation, Light/dark/print, and a new Visual
  language requirement.

## Impact

`cpr/assets/report.html`, `cpr/render.py` (font inlining), `cpr/assets/fonts/` (new, OFL),
`docs/report/summary.md`, `tests/browser/report.spec.js`, `tests/test_template_static.py`.
Reports grow by about 105 KB (embedded fonts).
