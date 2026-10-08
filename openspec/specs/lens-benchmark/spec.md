# lens-benchmark Specification

## Purpose
TBD - created by archiving change cassandra-lenses. Update Purpose after archive.
## Requirements
### Requirement: Known-issues cases
The project SHALL keep benchmark cases under `bench/cases/`, one JSON file per case: the PR or base
and head shas, the ticket, a context cut-off date, and known issues, each with its source link,
severity, files and line range, and match terms. Cases SHALL come from real apache/cassandra changes
where a reviewer or a follow-up ticket found the bug.

#### Scenario: Case is self-describing
- **WHEN** a case file is loaded
- **THEN** every known issue has a source URL and match terms, or loading fails naming the issue

### Requirement: No contamination
A benchmark run SHALL build the lens context from the ticket as of the cut-off date (no later
comments or issue links) and SHALL check out only the case's head, so lenses cannot see the fix.

#### Scenario: Later link removed
- **WHEN** the case's ticket later gained a link to the bug-fix ticket
- **THEN** that link is absent from the context file given to lenses

### Requirement: Run and score
`cpr bench run --panel <file> --case <id|all> --repeat <n>` SHALL run the panel on each case and save
lens outputs and merged issues per run. `cpr bench score` SHALL match merged issues to known issues
(a location within the issue's files and lines ±15, and the match terms present) and report recall
(hard, soft, major and above), raw and merged findings, duplicate rate, must-fix count, per-lens
unique share, and cost, per case and in total, plus findings that matched no known issue for a human
to label. Labels SHALL be cached so reruns only ask about new findings.

#### Scenario: Comparing panels
- **WHEN** `cpr bench score --panel new --against old` runs
- **THEN** it prints the metrics for both and lists known issues found by one panel and not the other

### Requirement: Quick loop
The project SHALL define a quick loop of two cases (CASSANDRA-21113 / PR #4887 and the PR #5201
merge fixture) that this change runs for the old and new panels before the new panel becomes the
default, and SHALL record the results in the change.

#### Scenario: Regression caught
- **WHEN** the new panel misses a known issue that the old panel found in the quick loop
- **THEN** the panel swap does not ship until the gap is explained or fixed

