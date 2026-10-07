## ADDED Requirements

### Requirement: Triage rating
The system SHALL rate each PR as `easy`, `moderate`, or `hard` to review, using only deterministic
signals, and SHALL list every signal with its value and its contribution to the rating, so a
reviewer can see why.

#### Scenario: Small test-only change
- **WHEN** the PR changes 40 lines, all under `test/`, and touches no compatibility surface
- **THEN** the rating is `easy`

#### Scenario: Serialization change
- **WHEN** the PR touches a messaging or sstable serializer
- **THEN** the rating is `hard`, regardless of size, and the signal list says why

#### Scenario: Signals are shown
- **WHEN** any rating is produced
- **THEN** the report lists each signal (for example "1,240 changed lines", "touches native protocol") next to the rating

### Requirement: Triage signals
The signals SHALL include at least: changed lines and files (excluding generated and test-resource
files), number of top-level subsystems touched (by package under `org.apache.cassandra`),
compatibility surfaces touched, concurrency-sensitive paths touched (for example
`concurrent/`, `db/compaction/`, `service/paxos/`, `service/accord/`), number of target branches,
and whether production code changed without tests. Thresholds SHALL live in one checked-in
configuration file.

#### Scenario: Thresholds are configurable
- **WHEN** the size threshold for `hard` is changed in the configuration file
- **THEN** the next rating uses the new threshold with no code change

### Requirement: Size guard
The system SHALL flag PRs over a configured size (default 1,000 changed lines in `src/`) as
"consider splitting" and SHALL state which files dominate the size.

#### Scenario: Huge PR
- **WHEN** a PR changes 20,000 lines
- **THEN** the report flags it and lists the five largest files by changed lines

### Requirement: Small changes are not rated hard on breadth alone
The system SHALL cap the rating at `moderate` when a PR changes fewer than a configured number of
lines (default 50), unless it changes serialization or on-disk format code.

#### Scenario: Tiny change across many packages
- **WHEN** a PR changes 12 lines across 9 files in 6 subsystems and touches no serializer
- **THEN** the rating is `moderate` and the report says it was capped because the change is small
