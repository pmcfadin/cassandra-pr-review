# About the report

## PR comment

`cpr comment <N>` builds a short comment for the pull request: the recommendation, the triage rating, the number of must-fix issues from the code review panel, up to five reasons in the report's order, and the link to the published report (`https://pmcfadin.github.io/cassandra-pr-review/pr/<N>/`). It is advisory and at most 1,500 characters.

By default it is a dry run: it prints the comment and what it would do, and writes nothing to GitHub. `cpr comment <N> --post` posts it with the logged-in `gh` account, or edits the comment it posted earlier (found by a hidden marker and the author) so a PR never gets a second one. A comment that has not changed is not written again. The result is recorded in `.work/pr/<N>/comment.json`.

Posting is refused when the local report is for a different head sha than the PR's current head, when the published report is missing or for a different head (run `bin/publish-pages` first), or when there is no confirmation: a prompt on a terminal, or `--yes` without one.

## Automatic refresh

A scheduled GitHub Action refreshes reports for open PRs with the cheap checks only: requirement checks, triage, static analysis, context, and the lab plan. It runs no AI code review and no builds. A report it publishes therefore shows code review as "not run" and build as "not built" until the owner runs `/review-pr` or `cpr build` and publishes. A report that already has those results for the same head is never replaced by a plainer one; a new head replaces it, and the new report says code review has not run for that head. The "generated" time on the index and on each report tells you how fresh it is.
