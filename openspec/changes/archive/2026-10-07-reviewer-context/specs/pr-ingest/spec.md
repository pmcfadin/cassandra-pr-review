## MODIFIED Requirements

### Requirement: Local clone for diffs
The system SHALL keep a full clone of apache/cassandra in the work directory and SHALL fetch the
PR's head (`refs/pull/<N>/head`) and base branch into it, plus `trunk` when the base is another
branch (expert history reads trunk), so the diff view (including its blame context), diff-based
checks, and reviewer context run against local git objects.

#### Scenario: First run
- **WHEN** no clone exists
- **THEN** a full clone is created, and the PR head and base are fetched

#### Scenario: Subsequent run
- **WHEN** the clone exists
- **THEN** only the PR head, the base, and (for a non-trunk base) trunk are fetched; the clone is not re-created
