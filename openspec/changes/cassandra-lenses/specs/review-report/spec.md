## MODIFIED Requirements

### Requirement: Findings slot uses the review schema
The report model SHALL accept code review results in the review schema, grouped by lens: per lens
its name, agent, status (ran, missing, invalid), approval, summary, and findings (id, severity
blocker|major|minor|nit, location, rule, problem, fix, and optional impact and confidence), plus the
merged issues across lenses, the checklist sha, and whether the panel as a whole approved. New lenses
SHALL plug in without a template change.

#### Scenario: Findings present
- **WHEN** the model contains two findings from a lens named "cass-logic-boundary"
- **THEN** the Code review section lists them under that lens, ordered by severity

#### Scenario: Lens status shown
- **WHEN** one lens is missing and another approved with no findings
- **THEN** the Code review section shows the missing lens as missing and the other as approved

#### Scenario: Issues lead
- **WHEN** four lenses reported the same problem
- **THEN** the Code review section and the summary show it once as an issue naming the four lenses, and the headline reads "5 issues (11 findings from 4 lenses)"
