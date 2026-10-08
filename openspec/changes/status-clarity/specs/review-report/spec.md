## ADDED Requirements

### Requirement: Fixes and steps are separate
The To do panel SHALL list contributor fixes under "Now" and later merge steps (CI runs, votes, asking for
review) under "Then", and the verdict count SHALL count fixes only.

#### Scenario: PR 5201
- **WHEN** the #5201 report opens
- **THEN** the verdict says how many fixes the contributor has and then names CI and votes as the next steps, and CI and votes are not counted as must-fix items

### Requirement: One item per need
When a code review finding asks for the same thing as a failing check, the To do panel SHALL show one item
with the finding's specific wording and a note naming the check it satisfies.

#### Scenario: Test requested twice
- **WHEN** the Tests check fails and a code review finding asks for a specific unit test
- **THEN** To do shows only the specific test item, noting it also satisfies the Tests check

### Requirement: Standalone to-do items
Each to-do item SHALL have a title readable on its own, its file and line when known, and a source tag
(Check or Code review) linking to the check or finding card.

#### Scenario: Finding without a lens title
- **WHEN** a saved review has no title for a finding
- **THEN** the item title is built from the rule and the location, not from a cut-off problem sentence

### Requirement: One verdict name
The report and the index SHALL use the same verdict headline, and the report SHALL not restate it.

#### Scenario: Index matches report
- **WHEN** a PR's report says "Not ready to merge"
- **THEN** its index card says "Not ready to merge" and the report has no "Overall:" line
