## MODIFIED Requirements

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
