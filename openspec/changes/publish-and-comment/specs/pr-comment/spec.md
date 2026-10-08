## ADDED Requirements

### Requirement: Comment content
The system SHALL build the PR comment from the rendered report: a hidden marker with PR number and
head sha, the recommendation label, triage rating, must-fix issue count, up to five reasons in the
report's order, the GitHub Pages link, and a footer saying the report is advisory. The comment SHALL
be at most 1,500 characters.

#### Scenario: Dry run
- **WHEN** `cpr comment 5201` runs without `--post`
- **THEN** it prints the comment and the action it would take, and makes no write to GitHub

### Requirement: One comment per PR
The system SHALL post with the logged-in `gh` account only when `--post` is given, and SHALL edit its
own earlier comment (found by the marker and author) instead of adding a second one. It SHALL make
no write when the body is unchanged.

#### Scenario: Second run on a new head
- **WHEN** the tool already commented on PR #5201 and the PR gets a new head and a new report
- **THEN** the existing comment is edited to the new content and no new comment is created

### Requirement: Posting guards
The system SHALL refuse to post when the local report's head sha differs from the PR's current head,
when the published Pages report is missing or carries a different head sha, or when no
confirmation is given (an interactive yes, or `--yes` without a terminal).

#### Scenario: Pages not updated yet
- **WHEN** the local report is for head `abc` and the Pages report still shows head `def`
- **THEN** posting is refused with "publish first: run bin/publish-pages"
