## ADDED Requirements

### Requirement: Full PMD Java catalog on every PR
Static analysis SHALL run every rule in PMD's eight Java categories on the head and base of the changed files
and SHALL report only violations the PR introduces.

#### Scenario: Introduced only
- **WHEN** a rule fires on an unchanged line that also fires in base
- **THEN** it is not counted as introduced

### Requirement: House style decided by the code
A rule that fires in at least 25% of the base branch's source files SHALL be shown as "house style differs":
counted and collapsed, not listed per line and not part of the check's verdict.

#### Scenario: Final locals
- **WHEN** LocalVariableCouldBeFinal fires in most trunk files
- **THEN** it appears only in the collapsed house-style section

### Requirement: Readable rule table
The report SHALL show a category summary and a rule table sorted by colour band then introduced count, each
rule linking to its PMD documentation and opening to its file:line list.

#### Scenario: Bug-finding rule
- **WHEN** a PR introduces a CloseResource violation
- **THEN** the rule table shows CloseResource in red with its count, and the static.pmd-rules check warns
