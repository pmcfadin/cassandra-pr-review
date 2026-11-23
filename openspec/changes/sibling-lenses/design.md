## Context

- `cli.prepare_lenses` extracted the allow-listed checklists from `bundle.git.clone`, the PR's own
  clone. For a sidecar PR that is `.work/cassandra-sidecar`, which has no `.claude/skills/`.
- The subprojects' contributor guides at trunk (checked 2026-11-20): sidecar `CONTRIBUTING.md`
  (32 KB: REST API design and versioning, Vert.x threading, handlers, futures, Guice, adapters),
  `TESTING.md` (12 KB), `OPENAPI.md` (4 KB), `docs/vertx-threading-model.md` (5 KB); analytics
  `DEV-README.md` (9 KB: building, integration tests, bridge modules). Both repos have an
  `AGENTS.md`; it is written as instructions to agents, so it is a source for the standards docs
  but not passed to the lenses.

## Decisions

### D1. Checklist source and target repo are separate
`lenses.prepare(proj, bundle, d, checklists_from, target_clone, offline, log)` replaces the body of
`cli.prepare_lenses` and the copy in `bench.prepare_run`. `checklists_from` is
`lenses.checklist_clone(work_dir, target_clone, proj)`: the PR's clone for Cassandra, else
`.work/cassandra` (cloned on first use; offline with no clone is an error). `lens_ref` pins only
the Cassandra checklists; guides always come from the project's `origin/trunk`.

### D2. Guides are trusted the same way
`extract_guides` reads each path in the profile's `lenses.guides` with `git show <trunk sha>:<path>`
under the same size cap and path checks, into `<refdir>/<slug>/`, and records `{sha, files,
missing}` under `guides` in `manifest.json`. `lenses.guides` maps each path to the lenses that get
it. A guide missing at trunk is a plan note, not a missing lens: the Cassandra checklists still
apply.

### D3. Per-project bundle edits
`lenses.drop` removes checklist paths from every bundle (the in-JVM dtest guide for the
subprojects, so test-regime gets the project's testing guide instead). The Cassandra profile
names no guides and drops nothing, so its plans are unchanged.

### D4. Prompts: mark, don't fork
The six agent files stay one set. Each gains `project` and `standards` inputs and marks its
Cassandra-only items *(Cassandra)*; for a subproject PR the lens skips those and applies the
bullets under `### <lens name>` in the standards file's `## Lens notes`. The standards reviewer's
Cassandra list and security surface follow the same rule. Cassandra lenses read
`cassandra-standards.md`, which has no Lens notes, so their instructions are unchanged.

### D5. Benchmark
Cases are named by project letter: `S1-347` and `A1-124`, scored like the B cases. Both are hard
issues whose follow-up ticket says the case change introduced them. Ship gate as for
cassandra-lenses: the panel finds each hard issue.

## Risks / Trade-offs

- [Guides at today's trunk may describe rules newer than a bench case] → the same holds for the
  Cassandra checklists; the guides do not name the later fixes.
- [The Cassandra checklists talk about Cassandra internals] → most items are generic Java review
  questions; the lens notes say what applies instead, and the prompts already tell lenses to ignore
  items about APIs absent from the base.
