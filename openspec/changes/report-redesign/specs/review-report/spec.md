## MODIFIED Requirements

### Requirement: Summary first page
The first section SHALL show, above the fold: the PR number, base branch, author, JIRA key and
status, and title; a status card with the recommendation, one plain sentence that counts the
must-fix items and names who they wait on, and a row of merge steps (Ticket, Tests, Build, Code
review, CI, Votes, each present only when the model has that section) showing each step's status and
linking to its section; and a "To do" bar that counts the must-fix items per owner. The "To do" bar
SHALL open to every recommendation reason grouped by owner (contributor, committer, reviewer), each
item opening to its summary, next action, and a link to its section; advisory checks that warn or
fail SHALL follow behind a "Show N optional items" control. Below the card the summary SHALL show
the review effort rating, the suggested reviewers card, a collapsed "Every check" panel holding the
grid of every check with its status, and a collapsed glossary of project terms.

#### Scenario: Blocked PR
- **WHEN** the recommendation has blocking reasons
- **THEN** the status sentence counts them and names their owners, and the "To do" bar shows the count per owner before anything else on the page

#### Scenario: Unreviewed PR
- **WHEN** the recommendation is `requirements-met-unreviewed`
- **THEN** the status card states plainly that code review has not run yet

#### Scenario: Code review issue as a to-do item
- **WHEN** a reason comes from a merged code review issue
- **THEN** its to-do item reads "Fix the <severity> code review issue in <file>", opens to the problem and the fix, and links to Code review

#### Scenario: No reasons
- **WHEN** the recommendation has no reasons and no advisory check warns
- **THEN** the "To do" bar says there is nothing to do

#### Scenario: Every check
- **WHEN** the reader opens "Every check" and selects a check
- **THEN** the report shows that check's section and scrolls to the check

### Requirement: Left-hand navigation
The report SHALL have a persistent left-hand navigation listing every section, with a status badge
per section (pass, warn, fail, unknown, info). Selecting an entry SHALL show that section. The
current section SHALL be reflected in the URL fragment so a link can point at it. Above the section
list the navigation SHALL show the PR number, the recommendation, and a "To do" link with the
must-fix count; `#todo` SHALL show the summary with the "To do" list open.

#### Scenario: Deep link
- **WHEN** the report is opened with `#ci`
- **THEN** the CI section is shown and highlighted in the navigation

#### Scenario: To do link
- **WHEN** the report is opened with `#todo`
- **THEN** the summary is shown, its "To do" list is open, and Summary is highlighted in the navigation

#### Scenario: Narrow screen
- **WHEN** the viewport is narrower than 800px
- **THEN** the navigation collapses behind a toggle and the content uses the full width

### Requirement: Light, dark, and print
The report SHALL support light and dark themes (following the system preference, with a manual
toggle) and SHALL print all sections in order with navigation hidden. Collapsed panels, the "To do"
list, and optional items SHALL print expanded.

#### Scenario: Print
- **WHEN** the user prints the report
- **THEN** every section prints sequentially, the navigation does not print, and the "To do" list prints with its optional items

## ADDED Requirements

### Requirement: Visual language
The report SHALL use Red Hat Text for text and Red Hat Mono for code, embedded in the file as
base64 `@font-face` data at render time from `cpr/assets/fonts/` (SIL Open Font License), with system
fonts as the fallback when the font files are absent. Every status shown SHALL carry a glyph and a
word, never colour alone. The navigation SHALL be dark in both themes.

#### Scenario: Fonts embedded
- **WHEN** a report is generated
- **THEN** it holds `@font-face` rules for "Red Hat Text" and "Red Hat Mono" with `data:font/woff2;base64,` sources and makes no network request

#### Scenario: Bare template
- **WHEN** the template is opened without rendering
- **THEN** it shows the no-data banner in system fonts
