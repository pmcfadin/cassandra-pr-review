## ADDED Requirements

### Requirement: CI evidence from GitHub for the subprojects
For apache/cassandra-sidecar and apache/cassandra-analytics the system SHALL judge CI from the
GitHub check-runs and workflow runs of the PR head, and SHALL NOT read JIRA attachments for them.

#### Scenario: Committer PR with green CI
- **WHEN** sidecar PR #400's head has 21 completed, successful check-runs
- **THEN** `ci.evidence` passes, `ci.freshness` passes and `ci.failures` passes

#### Scenario: Outside contributor waiting for approval
- **WHEN** a sidecar PR head has no check-runs and its workflow run is `action_required`
- **THEN** `ci.evidence` is unknown, says the workflows await a maintainer's approval, and names a committer as the one to act

#### Scenario: Failing job
- **WHEN** one check-run concluded `failure`
- **THEN** `ci.failures` warns and names it

### Requirement: Only the project's own rules
The system SHALL report checks that are not part of a project's process as not-applicable with
the reason, and SHALL word ticket, commit and changelog checks with the project's key.

#### Scenario: Ticket key in a sidecar commit subject
- **WHEN** a sidecar commit's subject is `CASSSIDECAR-513: Add option (#400)` and it has a credit line
- **THEN** `commits.message-format` passes

#### Scenario: Cassandra-only check
- **WHEN** a sidecar report is built
- **THEN** `compat.config-pairing` is not-applicable with "Not part of Cassandra Sidecar's process"

### Requirement: Static analysis with the project's config
The system SHALL run checkstyle with the project's own configuration from the base branch, at the
version the project's build uses, on the project's main and test sources.

#### Scenario: Sidecar
- **WHEN** a sidecar PR changes `server/src/main/java/.../SSTableImporter.java`
- **THEN** checkstyle 7.8.1 runs `checkstyle.xml` from the base branch on it

#### Scenario: Analytics
- **WHEN** an analytics PR changes a Java file under `cassandra-analytics-core/src/main/java`
- **THEN** checkstyle 9.3 runs `config/checkstyle/checkstyle.xml` with `config_loc` set to its directory

### Requirement: Compatibility surfaces per project
The system SHALL name the compatibility surfaces a PR touches using the project's list.

#### Scenario: Sidecar REST API
- **WHEN** a sidecar PR changes `client-common/src/main/java/org/apache/cassandra/sidecar/common/response/X.java`
- **THEN** `compat.surfaces` lists the REST API surface

### Requirement: Cassandra unchanged
The system SHALL produce the same report model for apache/cassandra PRs as before this change.

#### Scenario: Recorded bundles
- **WHEN** every recorded apache/cassandra bundle is rendered before and after
- **THEN** the models are identical
