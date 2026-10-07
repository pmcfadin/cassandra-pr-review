## ADDED Requirements

### Requirement: Context section
The report SHALL include a Context section after Triage with related tickets (from blame and from
issue links), commits without a ticket, per-file experts, and suggested reviewers, and SHALL embed
`docs/report/context.md` as its "How this is judged" panel. The summary page SHALL show a
"Suggested reviewers" card listing the suggestions and anyone already involved.

#### Scenario: Summary card
- **WHEN** the report is generated for a PR with prior history
- **THEN** the summary shows up to 5 suggested reviewers, each linking to the Context section

#### Scenario: No history
- **WHEN** the changed code has no prior history
- **THEN** the Context section and the card say so instead of showing empty tables
