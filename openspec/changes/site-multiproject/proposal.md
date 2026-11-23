## Why

Sidecar and analytics PRs now get full reports, but the published site, the polling workflow and
`cpr comment` still cover apache/cassandra only. Reports sit at `pr/<N>/`, and the subprojects' PR
numbers fall in the same range as Cassandra's (sidecar #397, analytics #260), so they cannot share
that path.

## What Changes

- Every report is published at `<project>/pr/<N>/` (`cassandra/pr/5201/`, `sidecar/pr/397/`).
- The first publish or polling run after this change moves the existing `pr/<N>/` reports to
  `cassandra/pr/<N>/` and leaves a redirect at the old path, so links in posted comments keep working.
  Running it again changes nothing.
- The index has a section per project with its own groups and a link to the project's open PRs.
- `cpr poll` and the workflow poll every project (each with its own limit, `--project` for one);
  the workflow caches each project's clone separately.
- `cpr comment sidecar#N` links `<site>/sidecar/pr/<N>/` and posts to apache/cassandra-sidecar.
  `pages_base()` (PR #1) is now the site root.

## Non-goals

- Pushing the migrated site: the first push to the live gh-pages branch waits for the owner.

## Capabilities

### New Capabilities
- `site-multiproject`: publishing, polling and PR comments for every project.

## Impact

`cpr/site.py`, `cpr/poll.py`, `cpr/comment.py`, `cpr/cli.py` (`cmd_poll`), `bin/publish-pages`,
`.github/workflows/poll.yml`, `docs/report/about.md`, README, tests (unit and browser).
