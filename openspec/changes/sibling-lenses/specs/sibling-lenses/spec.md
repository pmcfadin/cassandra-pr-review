## ADDED Requirements

### Requirement: Checklists from Cassandra, guides from the project
For a sidecar or analytics PR the system SHALL read the lens checklists from the apache/cassandra
clone at trunk, and the project's own guides from that project's trunk, both with `git show` into
the refdir, never from the PR head or worktree.

#### Scenario: Sidecar PR
- **WHEN** `cpr prepare sidecar#401` runs
- **THEN** the refdir holds the Cassandra checklists and `sidecar/CONTRIBUTING.md`, `sidecar/TESTING.md`, `sidecar/OPENAPI.md` and `sidecar/docs/vertx-threading-model.md` at sidecar trunk, and the JSON names both trunk shas

#### Scenario: Missing guide
- **WHEN** a guide the profile names is absent at the project's trunk
- **THEN** the plan carries a note naming it and every lens still runs

### Requirement: Per-project lens inputs
The system SHALL give each lens the project's name, standards file and testing doc, and SHALL leave
Cassandra-only checklists out of a subproject's bundles.

#### Scenario: Test regime for analytics
- **WHEN** an analytics PR is prepared
- **THEN** the cass-test-regime bundle has `analytics/DEV-README.md` and not the in-JVM dtest guide, and `testing_doc` is `docs/report/subprojects/testing.md`

#### Scenario: Cassandra unchanged
- **WHEN** a Cassandra PR is prepared
- **THEN** every bundle is the same as before this change and `standards` is `docs/research/cassandra-standards.md`

### Requirement: Benchmark per subproject
The benchmark SHALL hold at least one hard known-issue case per subproject.

#### Scenario: Cases load
- **WHEN** `cpr bench score --case S1,A1` runs
- **THEN** both cases load, map to their projects, and are scored against their known issues
