## ADDED Requirements

### Requirement: Usual-for-Cassandra rules
A rule SHALL be treated as usual for Cassandra when the PR's introduced count is not significantly above the
base branch's rate scaled to the PR's added production lines (one-sided Poisson p >= 0.01), and such rules
SHALL not drive the static.pmd-rules check.

#### Scenario: Threads in a database
- **WHEN** a PR adds 4 DoNotUseThreads violations over 2,000 added lines and trunk's rate predicts about 3
- **THEN** DoNotUseThreads is listed as usual for Cassandra and the check does not warn for it

### Requirement: Type-dependent rules need classes
Rules that need type resolution SHALL be shown as "needs compiled classes" and excluded from the check
when PMD ran without an aux classpath, and SHALL count normally when a build classpath was used.

#### Scenario: Unbuilt PR
- **WHEN** an unbuilt PR triggers WrongTestAnnotation
- **THEN** the rule is greyed as needing compiled classes and the check ignores it
