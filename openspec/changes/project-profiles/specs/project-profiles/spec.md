## ADDED Requirements

### Requirement: Name the project
The system SHALL review PRs of apache/cassandra, apache/cassandra-sidecar and
apache/cassandra-analytics, taking the project from the PR reference (`sidecar#397`,
`apache/cassandra-sidecar#397`, a PR URL) or `--project`, defaulting to apache/cassandra, and
SHALL record it in the bundle.

#### Scenario: Sidecar PR by short reference
- **WHEN** the owner runs `cpr review sidecar#397`
- **THEN** every GitHub call reads apache/cassandra-sidecar, the clone is `.work/cassandra-sidecar`, and the bundle's `meta.project` is `sidecar`

#### Scenario: Old bundle
- **WHEN** a bundle saved before profiles existed is re-rendered
- **THEN** it is treated as apache/cassandra

### Requirement: Storage per project
The system SHALL keep each project's per-PR data, worktrees, build runs, reports and PMD
baselines apart, so the same PR number in two projects never shares a file, and SHALL move
existing apache/cassandra data into its project directory once without losing it.

#### Scenario: Same number in two projects
- **WHEN** Cassandra PR #397 and sidecar PR #397 are both reviewed
- **THEN** they have separate bundles, reports and build approvals

#### Scenario: Upgrade with existing data
- **WHEN** `.work/pr/5201`, `.work/build-runs/5201` with a kept classpath, and `reports/5201` exist
- **THEN** the first command moves them under `cassandra/`, the moved status.json points at the moved classpath, and a second run changes nothing

### Requirement: Classify paths per project
The system SHALL classify changed files as production, test (with suite), test resource,
generated, doc or build, and name their subsystem, using the project's layout.

#### Scenario: Sidecar module layout
- **WHEN** a sidecar PR changes `server/src/main/java/org/apache/cassandra/sidecar/Foo.java` and `server/src/test/java/org/apache/cassandra/sidecar/FooTest.java`
- **THEN** the first is production in subsystem `server` and the second is a unit test

#### Scenario: Cassandra unchanged
- **WHEN** an apache/cassandra PR is classified
- **THEN** every result is the same as before this change

### Requirement: Ticket keys per project
The system SHALL find the ticket key and credit lines using the project's JIRA key prefixes.

#### Scenario: Sidecar credit line with a markdown link
- **WHEN** a sidecar commit ends `Patch by A; Reviewed by B for [CASSSIDECAR-378](https://issues.apache.org/jira/browse/CASSSIDECAR-378)`
- **THEN** the key is CASSSIDECAR-378, the author A and the reviewer B

#### Scenario: Other project's key is not the ticket
- **WHEN** a sidecar PR title says `CASSSIDECAR-12: ...` and its body cites CASSANDRA-20000
- **THEN** the key is CASSSIDECAR-12
