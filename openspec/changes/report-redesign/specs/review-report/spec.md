## ADDED Requirements

### Requirement: Merge-first layout
The report SHALL open with the verdict card (headline, one-sentence summary, and steps-to-merge pills
for Ticket, Tests, Code review, CI, and +1 votes) and a To do panel grouped by who must act, before any
check detail.

#### Scenario: PR 5201
- **WHEN** the PR 5201 report opens
- **THEN** the first thing shown is "Not ready to merge" with the must-fix count, and the To do panel lists the contributor's must-fix items first

### Requirement: Checks in plain status words
Each check group SHALL be a collapsible row labelled Must fix, Should fix, Note, Unknown, Passed, or
Not needed, sorted with problems first, and each check SHALL show its summary, how to fix, and owner.

#### Scenario: Open a group
- **WHEN** a reviewer opens the Branches & CI group
- **THEN** each CI check is listed with its status icon, summary, how to fix, and owner tag

### Requirement: Findings and background
The report SHALL show merged code review findings as expandable cards with severity, headline,
location, problem, suggested fix, and the lenses that raised them, and SHALL show review effort, who
knows the code, history, files changed with the diff view, and the lab plan under Background.

#### Scenario: Finding detail
- **WHEN** a reviewer opens a finding card
- **THEN** the problem, the suggested fix, and the lenses that raised it are shown
