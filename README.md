# cassandra-pr-review

Reviews a pull request against [apache/cassandra](https://github.com/apache/cassandra) and writes a
single self-contained HTML report. The report tells a contributor and their reviewers whether the
patch is ready to merge, what is missing and who has to act, and how hard it will be to review.

## Usage

```
bin/cpr review 5201              # fetch, check, and write reports/5201/index.html
bin/cpr review 5201 --offline    # re-render from the cached ingest, no network
bin/cpr review 5201 --model-out model.json   # also write the report model
```

Requirements: Python 3.11+ (standard library only), `git`, and `gh` logged in. The diff view comes
from the rustyrazorblade `dev-skills` plugin (`/plugin install dev-skills@rustyrazorblade-plugins`);
without it, the report shows a plain file list instead. Set `CPR_IDE_EXPLAIN` to point at a specific
`generate-explain.py`.

The first run makes a full clone of apache/cassandra in `.work/cassandra` (about 480 MB, about
3 minutes). After that a review takes a few seconds. Every network call is read-only: the tool
never comments, labels, or changes anything on GitHub or JIRA.

## Published reports

Reports are published at <https://pmcfadin.github.io/cassandra-pr-review/>, with an index of every
reviewed PR. To publish after reviewing:

```
bin/publish-pages    # merges reports/ into the published site and pushes the gh-pages branch
```

`bin/publish-pages` starts from the current `gh-pages` contents, so it never removes reports it does
not have locally. For a PR in both places, a local report replaces the published one when the head
differs, or when the head is the same and the local report is at least as rich (it has code review or
build results, or the published one has neither). `main` never contains reports; the `gh-pages` branch
holds only the generated site.

### Automatic refresh

`.github/workflows/poll.yml` runs every six hours (and on manual dispatch, with a `limit` input). It
lists open apache/cassandra PRs, picks those with no published report or a new head (newest first;
drafts untouched for 30 days are skipped; 25 per run), runs the cheap pipeline for each (requirement
checks, triage, static analysis, context, lab plan), and pushes the result to `gh-pages` with the
default `GITHUB_TOKEN`. It runs no AI code review and no builds and posts no comments, so those
sections read "not run" for a PR until you run `/review-pr` and `cpr build` and publish. A published
report with code review or build results for the current head is never replaced by a plainer one; a
new head replaces it. The index shows when each report was generated and whether code review ran.

Locally, `cpr poll` prints what a run would pick (reading `origin/gh-pages`); `cpr poll --run --site DIR`
refreshes a checkout of `gh-pages` the same way the workflow does.

## What the report checks

| Aspect | Checks |
|---|---|
| JIRA ticket | ticket key present, ticket exists, title and branch agree, ticket still open, Fix Version matches base |
| Branches & CI | PR per Fix Version branch, CI summary attached per branch, CI ran on the PR head, upgrade profile when serialization changes, failure count |
| Testing | tests accompany production changes |
| Commits & changelog | `patch by …; reviewed by … for CASSANDRA-N` format, co-author and `Assisted-by:` trailers, CHANGES.txt entry |
| Code style | checkstyle-banned APIs (read from the base branch), licence headers, generated or bundled files, `@Deprecated(since=)` |
| Compatibility | both yaml files updated together, system properties, nodetool help fixtures, touched compatibility surfaces |
| Reviews & votes | two committer +1s, matched against the public ASF roster |
| Lab plan | informational: a generated, never-run easy-db-lab plan (`plan.md`) to compare the merge-base and the PR head on a cluster |

`docs/report/` explains each aspect: what is checked, why (with project sources), how each status
is decided, how to fix it, and limits. The same text appears in the report under "How this is
judged".

## What it does not do yet

- Run `ant check`, unit tests, or dtests. CI evidence comes from `ci_summary` files attached to JIRA.
- Compare CI failures against known flaky tests.
- AI code review lenses. Without them the best possible verdict is "requirements met, code not yet
  reviewed".
- Comment on PRs or find new PRs automatically. See `docs/roadmap.md`.

## Development

Spec-driven with [OpenSpec](https://github.com/Fission-AI/OpenSpec): specs in `openspec/specs/`,
changes in `openspec/changes/`, research in `docs/research/`.

```
make test          # unit tests and browser tests
make test-unit     # python3 -m unittest discover -s tests -t .
make test-browser  # Playwright, offline, against rendered fixtures
```
