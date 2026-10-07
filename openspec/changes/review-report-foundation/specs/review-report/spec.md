## ADDED Requirements

### Requirement: Single self-contained HTML file
The system SHALL write exactly one HTML file per review, with all CSS, JS, and data inline. The
file SHALL start with `<!doctype html>`, SHALL make no network requests when opened, and SHALL work
when opened over `file://`. Links to GitHub, JIRA, and attachments are allowed as plain anchors.

#### Scenario: No network references
- **WHEN** a report is generated
- **THEN** it contains no `<script src`, `<link href`, `@import`, `url(http`, or `fetch(`

#### Scenario: Opens from disk
- **WHEN** the file is opened from the local filesystem in a browser with networking disabled
- **THEN** every section renders

### Requirement: Data and template separation
The report SHALL be produced by injecting one validated JSON report model into a checked-in static
template at a single marker, with JSON escaped so no embedded text can close or open a script
element (`<` encoded as `<`, ASCII-only). An invalid model SHALL produce no output file.

#### Scenario: Hostile diff content
- **WHEN** the diff contains the text `<!--<script></script>`
- **THEN** the report renders that text literally and no script from the diff runs

#### Scenario: Invalid model
- **WHEN** the report model fails validation
- **THEN** the command exits non-zero, names the invalid field, and writes no file

### Requirement: Left-hand navigation
The report SHALL have a persistent left-hand navigation listing every section, with a status badge
per section (pass, warn, fail, unknown, info). Selecting an entry SHALL show that section. The
current section SHALL be reflected in the URL fragment so a link can point at it.

#### Scenario: Deep link
- **WHEN** the report is opened with `#ci`
- **THEN** the CI section is shown and highlighted in the navigation

#### Scenario: Narrow screen
- **WHEN** the viewport is narrower than 800px
- **THEN** the navigation collapses behind a toggle and the content uses the full width

### Requirement: Summary first page
The first section SHALL show, above the fold: the PR title, number, author, base branch, JIRA key
and status; the recommendation with its reasons; the triage rating with its signals; and a
compact grid of every requirement check with its status. Blocking failures SHALL be listed first,
each with the contributor's next action.

#### Scenario: Blocked PR
- **WHEN** the recommendation is `blocked`
- **THEN** the first page shows each blocking failure and its action before anything else

#### Scenario: Unreviewed PR
- **WHEN** the recommendation is `requirements-met-unreviewed`
- **THEN** the first page states plainly that code review has not run yet

### Requirement: Detail sections
The report SHALL include these sections after the summary: Requirements (every check, grouped by
category, with evidence), JIRA (ticket fields, Reviewers, recent comments), Branches & CI (one row
per target branch: PR, head sha, CI sha, profile, counts), Commits, Changes (the diff view),
Compatibility surfaces, Triage signals, Code review (findings from review lenses, or "not run"), and
About (tool version, ide-explain version, generation time, input shas, what was not checked).

#### Scenario: Code review not run
- **WHEN** no review lens has produced findings
- **THEN** the Code review section says "Not run in this version" and its nav badge is unknown

#### Scenario: About states limits
- **WHEN** any report is generated
- **THEN** the About section lists checks that need a human (for example design acceptability) and checks not run (for example `ant check`, tests)

### Requirement: Findings slot uses the review schema
The report model SHALL accept code review findings in the rustyrazorblade review schema (id,
severity blocker|major|minor|nit, location, rule, problem, fix), grouped by lens, so later lenses
plug in without a template change.

#### Scenario: Findings present
- **WHEN** the model contains two findings from a lens named "correctness"
- **THEN** the Code review section lists them under "correctness", ordered by severity

### Requirement: Embedded diff view from ide-explain
The Changes section SHALL embed the page produced by the installed `dev-skills` ide-explain
generator for the PR's diff (merge-base of base branch to PR head, with PR review comments
attached), contained in a sandboxed iframe whose document is carried inline in the report. The
ide-explain version used SHALL be recorded in About.

#### Scenario: Diff view present
- **WHEN** the dev-skills plugin is installed and the clone holds the PR head
- **THEN** the Changes section shows the ide-explain file tree and diff for the PR

#### Scenario: ide-explain unavailable
- **WHEN** the dev-skills plugin is not installed or its generator fails
- **THEN** the Changes section shows a plain per-file list with additions/deletions and the reason the diff view is missing, and the rest of the report is unaffected

### Requirement: Light, dark, and print
The report SHALL support light and dark themes (following the system preference, with a manual
toggle) and SHALL print all sections in order with navigation hidden.

#### Scenario: Print
- **WHEN** the user prints the report
- **THEN** every section prints sequentially and the navigation does not print

### Requirement: Output location
The system SHALL write the report to `reports/<PR number>/index.html` by default, overwriting an
earlier report for the same PR, and SHALL print the absolute path.

#### Scenario: Default output
- **WHEN** `cpr review 5226` completes
- **THEN** `reports/5226/index.html` exists and its path is printed
