## Why

PMD runs on every PR but only with three complexity rules. The owner wants the full Java catalog
(https://pmd.github.io/pmd/pmd_rules_java.html, ~300 rules in 8 categories): "the value is in coverage".

A trial on two PRs (all 8 categories, head vs base, changed files only):

| | #5125 (5 files) | #4967 (172 files) |
|---|---|---|
| time, head + base | 7 s | 54 s |
| violations the PR adds | 302 | 12,343 |
| from Error Prone, Multithreading, Performance, Security, Best Practices | 65 | 1,362 |

Time is fine. Volume is not: most added violations are rules Cassandra does not follow
(LocalVariableCouldBeFinal, MethodArgumentCouldBeFinal, CommentSize, CommentRequired,
ControlStatementBraces, LawOfDemeter, OnlyOneReturn, ShortVariable).

## What Changes

- Run every rule in the 8 Java categories on head and base of the changed files, every PR, in the existing
  static-analysis step (local and in the scheduled Action).
- Count only violations the PR introduces (on added lines, or rule count above base for that file).
- **House style from the code, not a hand list.** A per-branch baseline scores the base branch's whole
  `src/java` once (cached by branch tip sha and PMD version). A rule that fires in at least 25% of the
  branch's files is "house style differs": counted, collapsed, not listed per line.
- When a build of this head exists (committer PRs built on this Mac), pass its classes and jars to PMD as
  `--aux-classpath` so type-resolving rules are reliable; the report says whether type info was used.
- Report: a "PMD rules" block in Code style with a category summary and a rule table sorted by
  introduced count, colour by category (red: Error Prone, Multithreading, Security; yellow: Performance,
  Best Practices, Design; green: Code Style, Documentation). Each rule opens to its file:line list and links
  to the rule's PMD page. House-style rules sit in a collapsed section.
- New advisory check `static.pmd-rules`: warn when the PR introduces red-category violations, pass when it
  introduces none outside house style, unknown when PMD could not run. Never blocking.
- The three complexity rules stay in the Method complexity table and are excluded here.

## Impact

`cpr/config/` (full ruleset), `cpr/staticanalysis/*` (run, classify, baseline cache), `cpr/checks/static.py`,
`cpr/model.py` (model field), `cpr/assets/report.html`, docs/report static aspect doc, tests,
`.github/workflows/poll.yml` cache for the baseline. Static cache schema bump.
