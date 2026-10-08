## Why

Reports are published to GitHub Pages, but nobody on the PR knows they exist. The owner wants the
report link posted as a comment on the apache/cassandra PR from the owner's own account, so
contributors and reviewers find it where they work.

## What Changes

- `cpr comment <N>` builds a short comment from the rendered report: the recommendation, the triage
  rating, must-fix issue count, the main reasons (up to 5), and the Pages link
  (`https://pmcfadin.github.io/cassandra-pr-review/pr/<N>/`). Dry run by default: it prints the
  comment and what it would do.
- `cpr comment <N> --post` posts it with `gh` as the logged-in account, or edits the existing
  comment when one carrying our hidden marker is already on the PR, so a PR never gets a second
  comment from the tool. The posted comment id, head sha, and time are recorded.
- Guards: refuse to post when the Pages report for that head sha is not live yet, when the local report
  is for a different head sha, or when the recommendation has no reasons to show; `--post` asks
  for confirmation on a terminal unless `--yes`.
- `bin/publish-pages` stays the way to publish; `cpr comment` checks the published page.

## Non-goals

- Inline review comments on code lines, GitHub reviews (approve or request changes), JIRA comments.
- Posting from a bot account or from automation (pr-polling decides that later).

## Capabilities

### New Capabilities
- `pr-comment`: building, guarding, posting, and updating the report-link comment.

## Impact

`cpr/comment.py` (new), `cpr/cli.py`, docs/report/about.md (how the comment works), tests with a
fake `gh` runner. Outward-facing: the first live post is confirmed with the owner.
