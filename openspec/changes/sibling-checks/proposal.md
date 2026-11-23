## Why

After project-profiles a sidecar or analytics PR gets a report, but most of its sections still
apply Cassandra's rules. On sidecar #400 (a clean, merged PR) the report fails `ci.evidence`
("CI not yet run") because it only reads `ci_summary` files attached to JIRA, which the
subprojects never attach; it warns that the commit subject repeats the ticket key, which is the
subprojects' own `KEY-N: title (#PR)` convention; checkstyle is not applicable because it looks for
`.build/checkstyle.xml`; and the compatibility, triage and lab-plan rules name Cassandra packages.

## What Changes

- CI for sidecar and analytics comes from the GitHub check-runs and workflow runs of the PR head.
  A workflow run waiting for a maintainer's approval (outside contributors on sidecar) is
  "awaiting approval", never a failure. Cassandra keeps the JIRA `ci_summary` reader.
- Checks a project does not use (yaml pairing, `CassandraRelevantProperties`, nodetool help
  fixtures, the upgrade-test CI profile, the perf commit structure, `@Deprecated(since=)`, CQL
  grammar and `src/gen-java` paths) are `not-applicable` for it, with the reason.
- Commit format: the subprojects put the ticket key in the subject; that is not flagged there.
- Checkstyle runs the project's own config from the base branch with the version its Gradle build
  uses: sidecar `checkstyle.xml` with checkstyle 7.8.1, analytics `config/checkstyle/checkstyle.xml`
  with 9.3 (Gradle 8's default) and `config_loc`. Static analysis splits main and test code and
  scores the PMD branch baseline with the project's source layout.
- Compatibility surfaces and triage's concurrency paths per project: sidecar REST endpoints and
  DTOs, `sidecar.yaml` and its configuration classes, sidecar schema, Cassandra adapters, the
  Java 8 client modules; analytics version bridges, CDC Avro schemas, Spark converters, bulk
  writer options, supported Cassandra versions, the bundled Sidecar client.
- No lab plan for the subprojects (it plans a Cassandra server cluster).
- "How this is judged" docs for the subprojects where their rules differ.

## Non-goals

- Publishing (site-multiproject), code review lenses (sibling-lenses), builds (gradle-build).
- SpotBugs (sidecar runs it in CI; its results come in through the check-runs).

## Capabilities

### New Capabilities
- `sibling-checks`: requirement checks, static analysis, compatibility and triage for the subprojects.

## Impact

`cpr/config/projects/*.json`, `cpr/project.py`, new `cpr/ingest/gh_checks.py`,
`cpr/ingest/bundle.py`, `cpr/checks/{__init__,ci,commits,compat,static,ticket}.py`,
`cpr/staticanalysis/{__init__,run,tools,inputs,classify,rate,baseline}.py`,
`cpr/config/static.json` (two checkstyle pins), `cpr/triage.py`, `cpr/lenses.py`, `cpr/labplan.py`,
`cpr/model.py`, `cpr/render.py`, `cpr/cli.py`, `docs/report/subprojects/`, README. Cassandra report
models stay identical for every recorded bundle.
