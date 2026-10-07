## Context

The full clone in `.work/cassandra` makes `git blame` and `git log` fast (blame of a large file is
under a second). Commit messages carry authorship in `patch by …; reviewed by …` lines because
committers merge other people's patches, so the git author is a fallback, not the source.

## Goals / Non-Goals

**Goals:** a reviewer sees, without leaving the report, the tickets that last changed this code and
who knows it best. **Non-Goals:** assigning reviewers, notifications, ownership rules.

## Decisions

### D1. Ingest gathers raw history; a pure function builds the context
Ingest adds `history` to the bundle: per blamed hunk the blamed commit shas, per changed file its
non-merge log in the window (sha, date, author name and email, full message), and the JIRA rows for
every referenced key. `cpr/context.py` turns that into tickets, people, experts, and suggestions
with no I/O, so it is unit-tested from fixtures like the checks.

### D2. Blame ranges
Parse the diff's hunk headers for the old-side range. Modified or deleted lines are blamed directly;
pure-addition hunks blame 3 lines either side of the insertion point. Use
`git blame --line-porcelain -L a,b <merge-base> -- <old path>` (renames use the old path).

### D3. History window
`git log --no-merges --since=5.years --format=… <merge-base> -- <path>` per file. Merge commits
(the forward-merge "Merge branch 'cassandra-6.0' into trunk") are skipped; blame already attributes
lines to the original commits.

### D3a. Expert history reads trunk (added during implementation)
For backports, the release branch's own history of a file is thin (`SSTable.java` on cassandra-4.0
had 2 commits in 5 years), so experts were near-random ties. Expert history now reads
`origin/trunk` when the file exists there, and the merge base otherwise; the report says which.
Blame still uses the merge base, because it must match the exact lines the patch changes.

### D4. Names
Normalize (casefold, strip accents and punctuation, collapse spaces). Resolve in order: aliases file
`cpr/data/people-aliases.json` → ASF id → roster display name. The roster already loads names from
whimsy. Unresolved people still count as experts but are never suggested as reviewers, since the
suggestion is for committers.

### D5. Scoring
score = Σ weight × 0.5^(age_years / 2), weight 1.0 for an authored patch, 0.6 for a review.
Constants live in `cpr/config/context.json`.

### D6. JIRA batch lookup
One `search?jql=key in (…)&fields=summary,status,resolution,issuetype` call (chunks of 50) for all
blame-derived keys; issue links come from the ticket we already fetch (`issuelinks` added to
normalize).

## Risks / Trade-offs

- [Name variants not in the aliases file split one person in two] → unresolved names are visible
  in the report; the aliases file is easy to extend.
- [Blame points at a mass-reformat commit] → such commits usually have a ticket too; the line counts
  make the noise visible. A skip-list for known reformat shas can come later.
- [Old tickets dominate on stable code] → tickets are ordered by blamed lines but show their dates,
  and experts use a recency decay.
