## Why

After sibling-checks a sidecar or analytics PR gets requirement checks judged by its own rules, but
`/review-pr` still cannot review it. `cpr prepare` reads the lens checklists from the PR's own
clone, and the subprojects have no `.claude/skills/` checklists, so every lens would be "missing".
The lens prompts and the standards file are Cassandra's: sstables, commit log, messaging versions,
`cassandra.yaml`, nodetool, in-JVM dtests and `cassandra-X.Y` backports. And there is no benchmark
case that shows the panel finds a real bug in a subproject change.

## What Changes

- The checklists always come from the apache/cassandra clone at trunk, whatever the PR's project.
  A subproject's own guides (sidecar `CONTRIBUTING.md`, `TESTING.md`, `OPENAPI.md`,
  `docs/vertx-threading-model.md`; analytics `DEV-README.md`) are read the same trusted way from
  that project's trunk into `<refdir>/<slug>/` and join the bundles of the lenses the profile names.
  The PR head stays untrusted.
- The in-JVM dtest guide leaves the test-regime bundle for the subprojects.
- `cpr prepare` (and `cpr bench run`) print the project's name, standards file and testing doc;
  `/review-pr` accepts `sidecar#N` and `analytics#N` and passes them to every lens.
- Lens prompts mark their Cassandra-only items. For a subproject PR the lens skips them and applies
  its own section of the project's standards file instead.
- New `docs/research/sidecar-standards.md` and `analytics-standards.md`, each with a "Lens notes"
  section per lens.
- One known-bug benchmark case per subproject: S1 (CASSSIDECAR-347, race found by CASSSIDECAR-349)
  and A1 (CASSANALYTICS-124, commit log marked fully read, found by CASSANALYTICS-127).

## Non-goals

- Publishing the reports (site-multiproject) and building the PRs (gradle-build).
- A separate panel per project: the same six lenses run for every project.

## Capabilities

### New Capabilities
- `sibling-lenses`: code review lenses for the subprojects.

## Impact

`cpr/lenses.py`, `cpr/project.py`, `cpr/config/projects/*.json` (`lenses` block), `cpr/cli.py`,
`cpr/bench.py`, `.claude/agents/*.md`, `.claude/skills/review-pr/SKILL.md`,
`docs/research/{sidecar,analytics}-standards.md`, `bench/cases/{S1-347,A1-124}.json`, README.
Cassandra lens plans are unchanged.
