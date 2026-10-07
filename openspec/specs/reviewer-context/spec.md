# reviewer-context Specification

## Purpose
TBD - created by archiving change reviewer-context. Update Purpose after archive.
## Requirements
### Requirement: Related tickets from blame
The system SHALL run `git blame` against the PR's merge base for every base-side line a hunk
modifies or deletes, and for up to 3 base lines on each side of a hunk that only adds lines. It
SHALL collect the commits that last changed those lines, skipping merge commits, extract CASSANDRA
keys from their messages, and list each ticket with its summary, status, the commits, and how many
of the blamed lines it owns, ordered by that count. Tickets SHALL be looked up in one batched JIRA
query.

#### Scenario: Modified lines lead to their tickets
- **WHEN** a PR modifies 10 lines that commit A (CASSANDRA-100) last changed and 2 lines that commit B (CASSANDRA-200) last changed
- **THEN** the related tickets are CASSANDRA-100 (10 lines) then CASSANDRA-200 (2 lines), each with its summary and status

#### Scenario: Pure addition uses surrounding lines
- **WHEN** a hunk only adds lines between base lines 40 and 41
- **THEN** base lines 38–43 are blamed

#### Scenario: Commit without a ticket
- **WHEN** a blamed commit's message has no CASSANDRA key
- **THEN** the commit is listed under "commits without a ticket" with its subject and sha

#### Scenario: New file
- **WHEN** the PR only adds new files
- **THEN** the section says there is no prior history for the changed code

### Requirement: Linked issues
The system SHALL list the JIRA issue links of the PR's own ticket (type, direction, key, summary,
status) alongside the blame-derived tickets.

#### Scenario: Ticket has links
- **WHEN** the ticket "is caused by" CASSANDRA-300
- **THEN** the Context section lists CASSANDRA-300 with the relation "is caused by"

### Requirement: Contributors from commit messages
The system SHALL parse `patch by <names>; reviewed by <names> for CASSANDRA-N` (case-insensitive,
`;` or `,` before `reviewed by`, possibly wrapped across lines, names separated by `,` or `and`)
from commit messages, ignoring `TBD`. When a commit has no such line, its git author SHALL count as
the patch author.

#### Scenario: Several authors and reviewers
- **WHEN** a message says "patch by Yaman Ziadeh, Bernardo Botella, Stefan Miklosovic; reviewed by Dmitry Konstantinov, Jyothsna Konisa for CASSANDRA-20854"
- **THEN** three authors and two reviewers are recorded for that commit

#### Scenario: Wrapped line
- **WHEN** "Patch by Nivy Kani; reviewed by Sam Tunnicliffe and Caleb Rackliffe for" ends one line and "CASSANDRA-21539" starts the next
- **THEN** one author and two reviewers are recorded

### Requirement: Identity resolution
The system SHALL resolve each name to an ASF committer when it matches, case- and
accent-insensitively, an ASF id or a roster display name, or an entry in a checked-in aliases file
(for example "Mick Semb Wever" and "Michael Semb Wever" to the same id). Unresolved names SHALL be
kept as written and marked as not matched to a committer.

#### Scenario: Alias
- **WHEN** one commit names "Mick Semb Wever" and another "Michael Semb Wever", and the aliases file maps both to `mck`
- **THEN** both count toward one person

#### Scenario: ASF id written as a name
- **WHEN** a message says "Patch by marcuse"
- **THEN** it resolves to the committer whose ASF id is `marcuse`

### Requirement: File experts
For each changed file (up to a configured number of files, largest first), the system SHALL score
people over that file's non-merge history in the last 5 years, read from trunk when the file exists
there and from the merge base otherwise (stating which): 1.0 per authored patch and 0.6 per
review, halved for every 2 years of age. It SHALL show the top 3 per file with their score,
patch and review counts, and the date of their latest commit.

#### Scenario: Recent work outranks old work
- **WHEN** Alice authored 2 patches to a file this year and Bob authored 3 patches 6 years ago
- **THEN** Alice is listed and Bob is not (outside the 5-year window)

### Requirement: Suggested reviewers
The system SHALL suggest up to 5 committers with the highest summed expert score across the changed
files, excluding the PR author. People already involved (in the ticket's Reviewers field, or who have commented on the ticket)
SHALL be shown as "already involved" rather than suggested. Each suggestion SHALL name the files that earned it.

#### Scenario: Author excluded
- **WHEN** the PR author is the top expert on every changed file
- **THEN** the author is not suggested

#### Scenario: Already involved
- **WHEN** the ticket's Reviewers field lists the top expert
- **THEN** that person appears as "already involved" and the next committer is suggested

### Requirement: Bounded work
The system SHALL blame at most a configured number of hunks (default 300) and compute experts for at
most a configured number of files (default 25), and SHALL state in the section what was skipped.

#### Scenario: Huge PR
- **WHEN** a PR has 1,200 hunks
- **THEN** the 300 hunks in the largest production files are blamed and the section says 900 were skipped

#### Scenario: Commented on the ticket
- **WHEN** the Reviewers field is empty and the top expert has commented on the ticket
- **THEN** that person appears as "already involved" and is not suggested

