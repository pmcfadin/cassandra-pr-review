## MODIFIED Requirements

### Requirement: Render findings
`cpr review <N> --lenses <dir>` SHALL render the merged result: the merged issues first, each with
its severity, the lenses that reported it, location(s), rule, problem, and fix; then per lens its
status, approval, summary, what it looks for, and raw findings. Issue locations SHALL be added to the
diff view's explanation pane, once per issue with the reporting lenses named.

The Code review section SHALL open with an "About this review" box that states the reviewers are AI,
can be wrong or miss problems, and that committers decide; and that lists the model the lens agents
pin, when the lenses ran, the patch-size tier, the checklist commit, and each lens with its focus.
When merging, the system SHALL record the models (from each lens agent's `model:` front matter), the
time of the newest lens output, and the tier and changed-line count from the lens plan. A field the
saved review lacks SHALL read "not recorded". A report with no review SHALL carry the panel's lens
names and focus, and its box SHALL list the lenses that would run and name `/review-pr <N>`.

#### Scenario: Findings in the diff view
- **WHEN** an issue has location `src/java/org/apache/cassandra/io/sstable/SSTable.java:121` and was reported by two lenses
- **THEN** the Changes view's explanation for that file lists the issue once, naming both lenses

#### Scenario: About a review that ran
- **WHEN** six Sonnet lenses ran on a 19-line patch and wrote their last output at 21:08 UTC on 2026-10-07
- **THEN** the box reads "Six AI reviewers (Claude Sonnet) read this patch", with Model "Claude Sonnet", Ran "2026-10-07 21:08 UTC", Patch size "small (19 changed lines, tests not counted)", and each lens with its focus

#### Scenario: Review saved before the run was recorded
- **WHEN** the review has no `about` block
- **THEN** the box still states the reviewers are AI, and Model and Ran read "not recorded"

#### Scenario: No review
- **WHEN** code review has not run for the PR
- **THEN** the box says so, lists every lens in the panel with its focus, and names `/review-pr <N>`
