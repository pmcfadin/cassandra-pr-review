## ADDED Requirements

### Requirement: Build gate
The system SHALL build and test a PR automatically only when its author is in the committer roster;
any other PR SHALL be built only after the owner approves that exact head sha, and an unapproved PR
SHALL show "not built" with the reason.

#### Scenario: Non-committer PR
- **WHEN** `cpr build 5201` runs for a PR whose author is not a committer and no approval exists for its head
- **THEN** nothing is built and the result is not-built, "author is not a committer"

#### Scenario: Approval is per head
- **WHEN** the owner approved head `abc` and the PR is pushed to head `def`
- **THEN** head `def` is not built until approved

### Requirement: Sandboxed execution
The system SHALL run every step that executes PR code inside a sandbox with no external network,
writes limited to the run directory, and no read access to credential directories, from a throwaway
clone and a copy of the Maven cache; only dependency resolution at the merge-base SHALL use the
network. After a run the shared fetch clone's hooks and config SHALL be unchanged, or the result SHALL
be unknown with a warning.

#### Scenario: Build tries the network
- **WHEN** PR code opens a connection to an external host during the build
- **THEN** the connection fails and the run continues or fails without leaking data

### Requirement: Selected tests with coverage
The system SHALL select unit test classes for the PR (changed tests, name matches, references to
changed classes and methods; no dtests, long, burn, or simulator tests; at most 25), run them with
JaCoCo, and compute coverage of the PR's added executable `src/java` lines.

#### Scenario: PR 5201
- **WHEN** PR #5201 is built with owner approval
- **THEN** LogTransactionTest is among the selected classes and SSTable.java shows 7 of 7 changed lines covered

### Requirement: Build and coverage section
The report SHALL show build status, test counts and failures, changed-line coverage per file with
missed lines, the selected tests with reasons, and a note that line coverage does not show the fix's
behaviour is tested; results SHALL come from the saved run for the current head only.

#### Scenario: Stale run
- **WHEN** the saved run is for an older head than the PR's current head
- **THEN** the section says not built for this head and shows no old numbers as current
