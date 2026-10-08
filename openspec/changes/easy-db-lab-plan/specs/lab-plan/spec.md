## ADDED Requirements

### Requirement: Scenario selection
The system SHALL choose at most two lab scenarios for a PR from configured rules over its changed
paths and existing triage and compatibility signals, and SHALL produce no plan for docs-only,
tests-only, build or tooling, dependency-bump PRs, or PRs over 300 production files, stating why.

#### Scenario: Crash-safety fix
- **WHEN** PR #5201 changes `src/java/org/apache/cassandra/io/sstable/SSTable.java` deletion order
- **THEN** the plan's scenario is a kill-during-compaction crash loop, and the plan names the rule that chose it

#### Scenario: Docs-only PR
- **WHEN** a PR changes only `doc/` files
- **THEN** the Lab plan section is not-applicable with the reason, and no plan.md is written

### Requirement: Plan format
The system SHALL write the plan in easy-db-lab's plan format (Objective, Cluster Name, Datacenters,
Environment, Artifacts under test, numbered Steps with bash blocks and Pass/Fail lines, Results table,
Notes), with build steps for the merge-base and the PR head, an A-B-B-A run order after calibration,
and only sanitised PR text. Every `easy-db-lab` command in a plan SHALL be one the tool lists.

#### Scenario: Title injection
- **WHEN** a PR title contains "`; rm -rf ~`"
- **THEN** the plan contains the title with the backticks and semicolon removed, and no extra command

### Requirement: Lab plan section
The report SHALL show a "Lab plan" section with a "Not run" banner, the rendered plan, and Copy and
Download buttons, and `cpr review` SHALL write the plan next to the report as `plan.md`. The tool
SHALL never provision infrastructure or run the plan.

#### Scenario: Plan shown, not run
- **WHEN** a report is rendered for PR #4967
- **THEN** the Lab plan section shows the Accord scenario plan under a "Not run" banner with Copy and Download
