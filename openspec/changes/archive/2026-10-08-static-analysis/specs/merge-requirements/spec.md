## MODIFIED Requirements

### Requirement: Static diff checks
The system SHALL scan added lines in the diff for checkstyle-banned APIs (as listed in
`.build/checkstyle.xml` on the PR's base branch), missing ALv2 headers in new files, edits under
`src/gen-java/` or `lib/`, and `@Deprecated` without `since`. Results SHALL cite file and line.
These checks SHALL be advisory, because `ant check` (not run here) is authoritative. When real
checkstyle ran on the PR, the banned-API and `@Deprecated` scans SHALL be `not-applicable`
(superseded); otherwise they SHALL be labelled an approximation.

#### Scenario: Banned API added
- **WHEN** an added line calls `System.currentTimeMillis()` in `src/java/` and real checkstyle did not run
- **THEN** the static check warns, citing file:line and the checkstyle rule

#### Scenario: New file without licence header
- **WHEN** a new `.java` file lacks the Apache licence header
- **THEN** the static check warns, citing the file

#### Scenario: Superseded by checkstyle
- **WHEN** real checkstyle ran on the PR's changed files
- **THEN** the banned-API and `@Deprecated` scans are not-applicable, naming `static.checkstyle`
