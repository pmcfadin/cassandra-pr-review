# merge-requirements Specification

## Purpose
TBD - created by archiving change review-report-foundation. Update Purpose after archive.
## Requirements
### Requirement: Check result shape
Every requirement check SHALL produce a result with: an id, a title, a category (ticket, ci,
commit, changelog, tests, static, compatibility, governance), the aspect document that explains it,
a status (pass, fail, warn, unknown, not-applicable), a one-line summary, the evidence it used (with
links and file:line locations where they exist), and, when not passing, the next action and who
takes it (contributor, reviewer, or committer). Each check SHALL be either blocking or advisory. A
warning SHALL say whether it requires action; warnings that do not are shown but do not change the
recommendation. A check that crashes SHALL report unknown, never pass.

#### Scenario: Failing check explains itself
- **WHEN** a blocking check fails
- **THEN** its result names the evidence it saw and the action the contributor must take

#### Scenario: Missing input is unknown, not fail
- **WHEN** a check's input could not be fetched (for example, JIRA unavailable)
- **THEN** its status is unknown and its summary names the missing input

### Requirement: JIRA ticket checks
The system SHALL check that a JIRA key exists, the ticket exists, the keys in title and branch
agree, the ticket is not already resolved, and Fix Version(s) are set and consistent with the PR's
base branch. A missing ticket SHALL be blocking. Feature branches (base not `trunk` and not
`cassandra-X.Y`) SHALL relax the ticket requirement to advisory.

#### Scenario: No ticket
- **WHEN** no JIRA key was resolved and the base is trunk
- **THEN** the ticket check fails and is blocking

#### Scenario: Ticket already resolved
- **WHEN** the ticket status is Resolved with resolution Fixed
- **THEN** the check warns that the patch may already have landed or been superseded

#### Scenario: Feature-branch PR without ticket
- **WHEN** the base branch is `cep-45-mutation-tracking` and there is no key
- **THEN** the ticket check is warn, not fail

#### Scenario: Fix version mismatch
- **WHEN** the base is cassandra-5.0 and Fix Versions list only 6.x and 7.x
- **THEN** the fix-version check warns that the base branch is not among the fix versions

### Requirement: CI evidence checks
The system SHALL check, for every branch the patch targets (this PR plus siblings), that a CI
summary exists, that its sha matches that branch's PR head sha, that its profile is at least
`pre-commit` (and `pre-commit w/ upgrades` when the diff touches messaging, serialization,
sstable, commitlog, hints, or system-table code), and SHALL report its failure count. Missing CI
SHALL be reported as "not yet run", never as a test failure.

#### Scenario: CI matches head
- **WHEN** the cassandra-5.0 summary's sha equals the PR head sha and it shows 0 failures
- **THEN** the CI check for cassandra-5.0 passes

#### Scenario: Stale CI
- **WHEN** the summary's sha differs from the PR head sha
- **THEN** the check warns "CI ran on an older commit" and shows both shas

#### Scenario: No CI yet
- **WHEN** no summary exists for a targeted branch
- **THEN** the check fails as blocking with summary "CI not yet run for <branch>"

#### Scenario: Upgrade profile needed
- **WHEN** the diff modifies a class implementing `IVersionedSerializer` and the CI profile is plain `pre-commit`
- **THEN** the profile check fails, naming the touched file and the required profile

#### Scenario: Failures present
- **WHEN** the summary shows 3 failed tests
- **THEN** the check warns, lists the failure count, and states that triage against known flaky tests is not done in this version

### Requirement: Commit and changelog checks
The system SHALL check each commit message for a summary first line without the JIRA key and a
`patch by …; reviewed by … for CASSANDRA-N` line (reviewer "TBD" accepted before review); SHALL
report `Co-authored-by:` and `Assisted-by:`/`Generated-by:` trailers; SHALL check for a CHANGES.txt
entry in the format ` * <summary> (CASSANDRA-N)` when non-test source changed; and SHALL note the
commit count without failing on it.

#### Scenario: Good commit message
- **WHEN** a commit reads "Fix NPE in compaction\n\npatch by Alice; reviewed by Bob for CASSANDRA-21649"
- **THEN** the commit-format check passes

#### Scenario: Missing patch-by line
- **WHEN** no commit contains a `patch by` line
- **THEN** the commit-format check is a warning, never a failure, because committers often rewrite
  the message at commit time; this warning alone does not move the recommendation to `needs-work`

#### Scenario: Missing CHANGES.txt
- **WHEN** files under `src/java/` changed and CHANGES.txt did not
- **THEN** the changelog check warns with the expected entry format

#### Scenario: Test-only change
- **WHEN** only files under `test/` changed
- **THEN** the changelog check is not-applicable

### Requirement: Test presence check
The system SHALL check that a PR changing production code also changes or adds test code, and
SHALL report the production-to-test lines ratio and which test suites were touched (unit,
distributed, burn, long, microbench, simulator).

#### Scenario: No tests
- **WHEN** `src/java/` changed and nothing under `test/` changed
- **THEN** the test-presence check fails as blocking

#### Scenario: Docs-only change
- **WHEN** only `doc/` files changed
- **THEN** the test-presence check is not-applicable

### Requirement: Static diff checks
The system SHALL scan added lines in the diff for checkstyle-banned APIs (as listed in
`.build/checkstyle.xml` on the PR's base branch), missing ALv2 headers in new files, edits under
`src/gen-java/` or `lib/`, and `@Deprecated` without `since`. Results SHALL cite file and line.
These checks SHALL be advisory, because `ant check` (not run here) is authoritative.

#### Scenario: Banned API added
- **WHEN** an added line calls `System.currentTimeMillis()` in `src/java/`
- **THEN** the static check warns, citing file:line and the checkstyle rule

#### Scenario: New file without licence header
- **WHEN** a new `.java` file lacks the Apache licence header
- **THEN** the static check warns, citing the file

### Requirement: Compatibility surface detection
The system SHALL detect when the diff touches config (`Config.java`, `cassandra*.yaml`), system
properties, native protocol, CQL grammar, nodetool commands, JMX/metrics, or virtual tables, and
SHALL check the deterministic pairings: config changes touch both `cassandra.yaml` and
`cassandra_latest.yaml` (on branches that have `cassandra_latest.yaml`; a change to
`cassandra_latest.yaml` alone is allowed, since its defaults differ on purpose); new system properties go through `CassandraRelevantProperties`; nodetool
changes update help fixtures. Detected surfaces SHALL be listed for human attention even when no
pairing rule applies.

#### Scenario: Config pairing missing
- **WHEN** `conf/cassandra.yaml` changed and `conf/cassandra_latest.yaml` did not
- **THEN** the pairing check fails as blocking

#### Scenario: Protocol touched
- **WHEN** the diff modifies files under `src/java/org/apache/cassandra/transport/`
- **THEN** the report lists "native protocol" as a touched compatibility surface

### Requirement: Branch coverage check
The system SHALL compare the set of targeted base branches (this PR plus siblings) against the
ticket's Fix Versions and SHALL list missing branches. For bug tickets it SHALL warn when trunk has
no PR and no sibling explains why.

#### Scenario: Missing branch
- **WHEN** Fix Versions are 5.0.x, 6.0 and 7.0 and PRs exist only for cassandra-5.0 and trunk
- **THEN** the check warns that cassandra-6.0 has no PR

### Requirement: Committer votes check
The system SHALL count +1 votes from Cassandra committers, from GitHub reviews in state APPROVED and
from JIRA comments containing "+1". Two votes SHALL be required (one for test-only changes). The
committer roster SHALL be derived at runtime from the public ASF roster
(`whimsy.apache.org/public/public_ldap_projects.json`, project `cassandra`, plus names from
`public_ldap_people.json`), cached for 24 hours. A voter SHALL be identified as a committer by, in
order: JIRA username equal to an ASF id on the roster; GitHub `author_association` of MEMBER or
OWNER; a GitHub login whose commits on apache/cassandra use an `<asf-id>@apache.org` email on the
roster. Each counted vote SHALL record which rule matched. A checked-in overrides file MAY correct
individual mappings. Votes from people not matched SHALL be listed separately.

#### Scenario: Two votes
- **WHEN** two distinct committers have +1'd
- **THEN** the votes check passes, names both, and shows how each was identified as a committer

#### Scenario: No votes yet
- **WHEN** no committer has +1'd
- **THEN** the votes check is fail, blocking, with summary "needs 2 committer +1s (has 0)"

#### Scenario: Non-committer vote
- **WHEN** a JIRA user not on the roster comments "+1"
- **THEN** the vote is listed as "non-committer +1" and not counted

#### Scenario: Roster unavailable
- **WHEN** the ASF roster cannot be fetched and no cached copy exists
- **THEN** the votes check is unknown and lists the raw +1s it found

### Requirement: Recommendation
The system SHALL compute one recommendation from the check results and the code review result,
using the owner of each item (contributor, reviewer, committer). The first matching rule wins:
- `draft`: the PR is a draft; checks are shown as early feedback and no merge recommendation is made;
- `needs-contributor-work`: a blocking check owned by the contributor fails, or code review reported
  a blocker or major finding;
- `needs-work`: an advisory warning that requires contributor action remains;
- `insufficient-evidence`: a blocking check is unknown because an input was unavailable;
- `awaiting-review`: the only blocking failures or required actions are owned by reviewers or
  committers (for example committer +1s, or CI that a committer runs);
- `requirements-met-unreviewed`: all blocking checks pass and the code review panel has not run or
  did not complete;
- `ready`: all blocking checks pass and every lens ran and approved with no blocker or major finding.
The recommendation SHALL list the reasons that produced it, each linked to its check or finding, and
SHALL name who it is waiting on.

#### Scenario: Without code review the best outcome is unreviewed
- **WHEN** every blocking check passes and no review lens has run
- **THEN** the recommendation is `requirements-met-unreviewed`, never `ready`

#### Scenario: Unknown dominates pass
- **WHEN** the CI check is unknown because JIRA was unavailable and nothing has failed
- **THEN** the recommendation is `insufficient-evidence`

#### Scenario: Draft
- **WHEN** the PR is a draft
- **THEN** the recommendation is `draft` and the checks are still shown as early feedback

#### Scenario: Contributor work outranks waiting on reviewers
- **WHEN** tests are missing (contributor) and committer +1s are missing (reviewer)
- **THEN** the recommendation is `needs-contributor-work` and lists the missing tests first

#### Scenario: Only reviewers and committers left
- **WHEN** the only blocking failures are committer +1s and CI not yet run
- **THEN** the recommendation is `awaiting-review` and is waiting on reviewer and committer

#### Scenario: Incomplete panel cannot be ready
- **WHEN** all blocking checks pass and one lens is missing
- **THEN** the recommendation is `requirements-met-unreviewed`

#### Scenario: Review findings need contributor work
- **WHEN** a lens reports a major finding
- **THEN** the recommendation is `needs-contributor-work` and lists the finding

