## Why

The owner wants reviews for apache/cassandra-sidecar and apache/cassandra-analytics as well as
apache/cassandra, at the same depth. Today the tool is hardwired to apache/cassandra: one `REPO`
constant, `CASSANDRA-N` keys, the `src/java` / `test/unit` layout, and storage keyed by PR number
alone. A sibling PR is misjudged (every `<module>/src/main/java` file counts as non-production),
and PR numbers collide across the three repos, so a sidecar PR would overwrite a Cassandra PR's
cache, report, build approval and PMD baseline.

This change is the foundation for the multi-project work (later changes: sibling-checks,
site-multiproject, sibling-lenses, gradle-build). It makes the project an input and stops the
collisions; it does not yet make every check right for the siblings.

## What Changes

- Project profiles in `cpr/config/projects/<slug>.json` (cassandra, sidecar, analytics) and
  `cpr/project.py`. A bundle records `meta.project`; older bundles resolve by `meta.repo`, and a
  bundle with neither is apache/cassandra.
- Every GitHub call, the clone remote, sibling-PR discovery, poll, comment and bench take the
  repository from the project instead of `cpr.REPO`.
- CLI: a PR is `5201`, `sidecar#397`, `apache/cassandra-sidecar#397` or a PR URL; `--project`
  names the project for a bare number (default cassandra).
- Storage: per-PR paths gain the project slug (`.work/pr/<slug>/<N>`, `.work/wt/<slug>/<N>`,
  `.work/build-runs/<slug>/<N>`, `reports/<slug>/<N>`); each project has its own clone
  (`.work/<repo name>`, so the Cassandra clone stays where it is). Existing Cassandra data is moved
  once, in place, on the first run.
- The PMD baseline cache is keyed by project as well as branch.
- The path classifier (production, test, suite, generated, doc, build, subsystem) is data-driven
  from the profile; checks, triage, lenses, history, model and the report use the bundle's project.
- JIRA keys and credit lines (`patch by …; reviewed by … for KEY-N`, including sidecar's
  `for [KEY-N](url)`) use the project's key prefixes.
- The report model carries the project (slug, repo, name, test-suite labels); the report title,
  base-branch link and test-suite grouping use it.

## Non-goals

- Making checks, CI evidence, static analysis, lenses or builds correct for the siblings (later
  changes). Until then a sibling report is produced but some sections still apply Cassandra rules.
- The published site layout (site-multiproject).

## Capabilities

### New Capabilities
- `project-profiles`: naming the project, per-project storage, path classification and ticket keys.

## Impact

New `cpr/project.py`, `cpr/config/projects/*.json`, `cpr/layout.py`. Changed: `cpr/paths.py`,
`cpr/ingest/{github,clone,bundle,keys,history}.py`, `cpr/credits.py`, `cpr/checks/__init__.py`
and the checks that classify paths, `cpr/triage.py`, `cpr/lenses.py`, `cpr/labplan.py`,
`cpr/context.py`, `cpr/model.py`, `cpr/assets/report.html`, `cpr/build/__init__.py`,
`cpr/buildresult.py`, `cpr/staticanalysis/{__init__,auxpath,baseline}.py`, `cpr/comment.py`,
`cpr/poll.py`, `cpr/bench.py`, `cpr/cli.py`, README. Tests: new profile, classifier, key, layout
and migration tests; existing tests keep passing with the cassandra default.
