## MODIFIED Requirements

### Requirement: Findings slot uses the review schema
The report model SHALL accept code review results in the rustyrazorblade review schema, grouped by
lens: per lens its name, agent, status (ran, missing, invalid), approval, summary, and findings (id,
severity blocker|major|minor|nit, location, rule, problem, fix), plus whether the panel as a whole
approved. New lenses SHALL plug in without a template change.

#### Scenario: Findings present
- **WHEN** the model contains two findings from a lens named "correctness"
- **THEN** the Code review section lists them under "correctness", ordered by severity

#### Scenario: Lens status shown
- **WHEN** one lens is missing and another approved with no findings
- **THEN** the Code review section shows the missing lens as missing and the other as approved
