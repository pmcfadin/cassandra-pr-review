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

For a full report with AI code review and build results, run `/review-pr 5201` in Claude Code from
this repo. It runs `cpr prepare`, starts `cpr build` in the background when the author is a
committer, runs the six review lenses in parallel, and renders the report with `cpr review --lenses`.
The steps can also be run by hand:

```
bin/cpr prepare 5201             # check out the PR head, write the lens context; prints JSON
bin/cpr build 5201               # build and run selected unit tests with JaCoCo, sandboxed
bin/cpr build 5201 --approve     # build a non-committer's PR: approves this exact head sha
bin/cpr review 5201 --lenses DIR # merge saved lens outputs into the report
bin/cpr tools install            # download and verify the pinned checkstyle and PMD
```

Requirements: Python 3.11+ (standard library only), `git`, and `gh` logged in. Builds need `ant`, a
JDK, and macOS (`sandbox-exec`). The diff view comes from the rustyrazorblade `dev-skills` plugin
(`/plugin install dev-skills@rustyrazorblade-plugins`); without it, the report shows a plain file
list instead. Set `CPR_IDE_EXPLAIN` to point at a specific `generate-explain.py`.

The first run makes a full clone of apache/cassandra in `.work/cassandra` (about 480 MB, about
3 minutes). After that the requirement checks take a few seconds; a build takes about 5 minutes.
Every network call to apache/cassandra and JIRA is read-only. The one write is `cpr comment --post`
(see below), which you run yourself.

Building runs the PR author's code, so `cpr build` builds automatically only for authors on the
committer roster. Every step that runs that code runs inside `sandbox-exec`, with no external
network and no access to credential directories. Results are saved per head sha; a push needs a new
build, and for a non-committer a new approval.

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
holds only the generated site. It refuses to push a page that contains a local path.

To link a published report from the PR:

```
bin/cpr comment 5201             # print the comment that would be posted
bin/cpr comment 5201 --post      # post it as your gh account, or edit our earlier comment
```

`--post` asks for confirmation unless `--yes` is given.

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
| Static analysis | the project's checkstyle, PMD cognitive complexity, the full PMD rule catalog, and CPD duplicate code on changed Java files, split into introduced by the PR and already there |
| Compatibility | both yaml files updated together, system properties, nodetool help fixtures, touched compatibility surfaces |
| Build & coverage | the PR head compiles, selected unit tests pass, and which added `src/java` lines those tests ran (JaCoCo) |
| Code review | six AI review lenses (standards and ticket, logic and boundaries, concurrency and lifecycle, persistence and compatibility, completeness, test regime), each applying checklists from apache/cassandra trunk |
| Reviews & votes | two committer +1s, matched against the public ASF roster |
| Triage | informational: how hard the PR is to review (easy, moderate, hard) |
| Context | informational: tickets that last changed this code (`git blame`), linked issues, and the people most experienced with each file |
| Lab plan | informational: a generated, never-run easy-db-lab plan (`plan.md`) to compare the merge-base and the PR head on a cluster |

`docs/report/` explains each aspect: what is checked, why (with project sources), how each status
is decided, how to fix it, and limits. The same text appears in the report under "How this is
judged".

## What it does not do yet

- Run `ant check` or dtests. Builds run selected unit tests only; the rest of the CI evidence comes
  from `ci_summary` files attached to JIRA.
- Compare CI failures against known flaky tests.
- Run JMH benchmarks to compare the PR head with the base (`perf-ab` in `docs/roadmap.md`).
- Run code review or builds in the scheduled workflow. Both run only on the owner's Mac, so a report
  without them reads "requirements met, code not yet reviewed" at best.
- Post PR comments automatically. `cpr comment --post` is run by hand.

## Development

Spec-driven with [OpenSpec](https://github.com/Fission-AI/OpenSpec): specs in `openspec/specs/`,
changes in `openspec/changes/`, research in `docs/research/`.

```
make test          # unit tests and browser tests
make test-unit     # python3 -m unittest discover -s tests -t .
make test-browser  # Playwright, offline, against rendered fixtures
```
