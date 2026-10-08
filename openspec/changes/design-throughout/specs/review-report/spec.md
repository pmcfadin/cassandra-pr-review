## ADDED Requirements

### Requirement: One design system across pages
The report and the site index SHALL share one token stylesheet and the same status words, pills and fonts.

#### Scenario: Index and report match
- **WHEN** a reader opens the index and then a report
- **THEN** both use the same fonts, colors, and verdict pills

### Requirement: Detail tables in the design language
Every table in the report SHALL use the shared table component, stack into cards below 640px, and cap long
tables with a "Show all" control.

#### Scenario: Phone width
- **WHEN** the #4967 report is opened at 390px and the Branches & CI and Code style groups are expanded
- **THEN** there is no horizontal page scroll and every table row is readable as a card

### Requirement: Index grouped by who acts
The site index SHALL group PRs by who acts next, show a count per group, and show code review and build
chips only when those ran.

#### Scenario: Mixed site
- **WHEN** the site holds a draft, a PR waiting on its contributor, and a PR waiting on reviewers
- **THEN** each appears under its own group heading with that group's count
