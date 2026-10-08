## Why

Reports exist only for PRs the owner runs by hand. The owner wants every open apache/cassandra PR
to have a current report without manual work. Owner decisions: a scheduled GitHub Action in our repo
does only the deterministic, cheap parts (ingest, requirement checks, static analysis, triage, lab
plan, publish); AI review lenses run only when the owner runs `/review-pr`; builds run only on the
owner's Mac.

## What Changes

- `cpr poll`: list open apache/cassandra PRs (GitHub API), compare each head sha with the published
  report on Pages, and pick the PRs that are new or have a new head; skip drafts older than a cut-off
  and PRs with no Java or doc changes; cap per run.
- `cpr poll --run`: for each picked PR, `cpr review <N>` (no lenses, no build), then rebuild the site.
- A published report that carries code review or build results for its head is never replaced by
  a cheaper report for the same head; for a new head it is replaced, and the new report says code review
  has not run for this head.
- `.github/workflows/poll.yml`: every 6 hours and on manual dispatch; caches the Cassandra clone and
  the analysis tools between runs; installs JDK 21 for static analysis; publishes to `gh-pages` with
  the workflow token; no secrets beyond the default `GITHUB_TOKEN`; posts no PR comments.
- The site index shows when each report was generated and whether code review ran.

## Non-goals

- AI lenses or builds in Actions; PR comments from automation.

## Capabilities

### New Capabilities
- `pr-polling`: selecting PRs to refresh, running the cheap pipeline, publishing, and the workflow.

## Impact

`cpr/poll.py`, `cpr/cli.py`, `cpr/site.py` (keep-richer rule, index columns),
`.github/workflows/poll.yml`, docs (README, docs/report/about.md), tests with recorded API responses.
