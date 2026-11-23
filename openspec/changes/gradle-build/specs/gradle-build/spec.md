## ADDED Requirements

### Requirement: Gradle builds for the subprojects
`cpr build` SHALL build a sidecar or analytics PR with the project's Gradle wrapper from the merge-base,
resolving dependencies only at the merge-base and building and testing the head offline in the
no-network sandbox, under the same gate as Cassandra builds.

#### Scenario: Committer PR
- **WHEN** `cpr build sidecar#400` runs for a committer's PR
- **THEN** the selected unit tests run with JaCoCo and status.json records pass, the test counts and the changed-line coverage

#### Scenario: Wrapper changed
- **WHEN** the PR changes `gradle/wrapper/gradle-wrapper.properties`
- **THEN** no Gradle command runs and the status is unknown, naming the wrapper file

#### Scenario: New dependency
- **WHEN** the head needs a dependency the merge-base did not resolve
- **THEN** the status is unknown, not build-failed

### Requirement: Sandbox holds
Code from the PR SHALL run only in the no-network profile, which denies the network, writes outside the
run's directories and reads of secrets and other PRs' data.

#### Scenario: Probe
- **WHEN** a test tries to read `~/.ssh`, write `$HOME`, connect out, or read `.work/pr/...`
- **THEN** each attempt fails
