## Context

Design source: `docs/design/report-v2.dc.html` (a Design canvas artboard; its `renderVals()` holds the
sample data for PR 5201 and shows every interaction). The report stays one self-contained HTML file
with the model embedded as JSON and rendered by vanilla JS; the embedded diff view stays in its
sandboxed iframe.

## Decisions

### D1. Mapping our sections onto the design
| Design area | Our data |
|---|---|
| Header | pr number, base, author (+ "first-time contributor" when the context says so), ticket key, title |
| Verdict card | recommendation verdict and label; sentence from reasons (must-fix count, number of owners) |
| Steps to merge | Ticket (ticket checks), Tests (testing + build), Code review (review section), CI (ci), +1 votes (votes, "n of 2") — each ok when its section passes |
| To do by role | recommendation reasons grouped by `owner`; must = blocking or action-required, optional = notes |
| Checks groups | ticket, ci, testing, build, commits, static, compatibility, votes, review (link to findings); sorted fail, warn, unknown, pass |
| Findings | review.issues (+ per-lens detail collapsed), checklists sha |
| Background | triage (effort bar: easy 1, moderate 2, hard 3 of 3), context (people, history), changes (file list + diff view), lab plan |
| Help | fixed glossary in the template |

### D2. Status words
fail → "Must fix"; warn with action required → "Should fix"; warn note → "Note"; unknown →
"Unknown"; pass → "Passed"; not-applicable → "Not needed". Colours from the design (#C0360C,
#8C6400, #00766C, grey).

### D3. Navigation
One page; nav links scroll to anchors and open the target group; current item highlighted by scroll
position (IntersectionObserver). Deep links `#sec-<id>`, `#findings`, `#background`, `#labplan` open
their target on load.

### D4. Fonts
Google Fonts link for Red Hat Text/Mono with system fallbacks; the report still renders offline.
