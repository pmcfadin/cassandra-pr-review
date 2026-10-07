## Why

Reviewers asked for two things the report does not give them: the history behind the code a patch
changes (which tickets last touched it, so they can read the context) and who should review it
(the people who know that code best). Today a reviewer finds both by hand with `git blame` and
`git log`, file by file.

## What Changes

- Related tickets: run `git blame` on the base-branch lines each hunk modifies or deletes (and the
  lines around pure additions), collect the commits that last changed them, and list their
  CASSANDRA tickets with summary, status, and how many changed lines each one owns. JIRA issue links
  on the PR's own ticket are listed too.
- People: parse `patch by …; reviewed by … for CASSANDRA-N` lines from the history of every changed
  file, resolve names to ASF committers where possible, and score each person per file by recency.
- Suggested reviewers: the top committers across the changed files, excluding the PR author, with
  reviewers already on the ticket shown as "already reviewing".
- A new **Context** report section, a "Suggested reviewers" card on the summary, and a
  `docs/report/context.md` aspect doc.

## Non-goals

- Requesting reviews, assigning, or notifying anyone (read-only, as everywhere).
- Code ownership rules or CODEOWNERS files.
- Using the GitHub contributor graph or mailing-list activity.

## Research relied on

- docs/research/cassandra-standards.md §1.3 (commit message format), §1.6 (committer votes).
- The `patch by` lines in trunk history: committers merge other people's patches, so the git author
  is not reliable; names vary (full names, ASF ids, nicknames) and lines sometimes wrap.
- The ASF roster already loaded for votes (whimsy public LDAP data, with names).

## Capabilities

### New Capabilities

- `reviewer-context`: related tickets from blame, per-file experts, and suggested reviewers.

### Modified Capabilities

- `review-report`: adds the Context section and the suggested-reviewers card to the summary.

## Impact

- New `cpr/context.py`; `cpr/ingest/clone.py` gains blame and log helpers; JIRA batch lookup by key
  (`/search?jql=key in (...)`); `cpr/data/people-aliases.json`; template and aspect doc updates.
- Blame runs on the full local clone; a budget bounds the work on huge PRs.
