## ADDED Requirements

### Requirement: Pick PRs to refresh
The system SHALL list open apache/cassandra PRs and pick those with no published report or whose
head sha differs from the published report's, skipping drafts not updated in 30 days, newest first,
capped per run.

#### Scenario: Unchanged PR
- **WHEN** PR #5212's published report is for its current head
- **THEN** `cpr poll` does not pick it

### Requirement: Cheap pipeline only
The polling run SHALL produce reports with requirement checks, triage, static analysis, context,
and lab plan, and SHALL NOT run AI review lenses, builds, or post PR comments.

#### Scenario: New PR
- **WHEN** a new PR appears
- **THEN** its report is published with code review "not run" and build "not built"

### Requirement: Keep richer reports
The system SHALL NOT replace a published report that has code review or build results for the same
head with a report without them; a new head SHALL replace it.

#### Scenario: Owner reviewed a PR
- **WHEN** the owner published #5201 with the lens panel for head `d1095cb` and polling runs again on the same head
- **THEN** the published #5201 report is unchanged

### Requirement: Scheduled workflow
The repository SHALL contain a workflow that runs the polling pipeline every six hours and on manual
dispatch, with only the default token and `contents: write`, caching the clone and tools, and never
overlapping with itself.

#### Scenario: Manual dispatch with a limit
- **WHEN** the workflow is dispatched with limit 3
- **THEN** at most three PRs are refreshed and the site index is rebuilt and pushed
