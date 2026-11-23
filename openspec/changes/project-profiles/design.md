## Context

`cpr.REPO = "apache/cassandra"` is imported by the GitHub client, the clone, the bundle, poll,
comment and bench. Paths are classified by fixed prefixes in `cpr/paths.py` (31 call sites in 8
modules), keys by a fixed `CASSANDRA` regex, and every per-PR directory is named by the PR number
alone. The siblings (see the plan and docs/research once written) are Gradle multi-module repos
with `<module>/src/{main,test,integrationTest,...}/java`, a single `trunk`, and keys
`CASSSIDECAR-N` (legacy `CASSANDRASC-N`) and `CASSANALYTICS-N`, often with small numbers.

## Decisions

### D1. One JSON profile per project
`cpr/config/projects/<slug>.json` with `slug`, `repo`, `name`, `jira_keys`, `key_digits` (the
minimum digits of a ticket number: 3 for Cassandra as today, 1 for the siblings, whose tickets
start at 1), `bare_number_branch_key` (a bare 4-6 digit number in the branch name is a ticket:
Cassandra only), and `paths`. Later changes add their own fields. `cpr/project.py` loads them
(cached), lists them, and resolves a bundle's project: `meta.project`, else `meta.repo`, else
cassandra. Unknown slugs or repos raise `ProjectError`.

### D2. The classifier is regex lists
Each class in `paths` is a list of regular expressions searched against the repo-relative path:
`prod`, `test`, `test_resources`, `generated`, `doc`, `build`; `suites` is an ordered list of
`[regex, suite, label]` (first match wins; any other test is `other`); `subsystem` is
`{"kind": "package", "root": "org/apache/cassandra/"}` (Cassandra, as today) or
`{"kind": "module"}` (the path before `/src/`, e.g. `server`, `adapters/adapters-base`).
`is_prod` is `prod` and not `test`, as today. The Cassandra profile reproduces the current
prefixes exactly; the module-level functions in `cpr/paths.py` stay and use the Cassandra
classifier, so code without a bundle and the existing tests are unchanged. Code with a bundle
uses `paths.of(bundle)`; checks use `ctx.classify` (the Context already has `ctx.paths`, the list
of changed paths).

### D3. Ticket keys from the profile
`keys.resolve(..., project)` builds `\b(KEY1|KEY2)[-_ ]?(\d{n,6})\b` from `jira_keys` and
`key_digits`, and only applies the bare-number branch rule when `bare_number_branch_key`. Keys are
canonicalised to `KEY-N` in upper case. `credits.parse/primary_key(message, keys=...)` and the
commit and changelog regexes in `checks/commits.py` use the same prefixes and accept an optional
`[` before the key (sidecar writes `for [CASSSIDECAR-378](https://...)`). Defaults stay
`("CASSANDRA",)` so callers without a project are unchanged.

### D4. Storage
`cpr/layout.py` owns every per-PR path (each function takes the slug explicitly; nothing defaults
to Cassandra, since a silent default is exactly the collision this change removes): `pr_dir(work, slug, n)` = `.work/pr/<slug>/<n>`,
`worktree(work, slug, n)` = `.work/wt/<slug>/<n>`, `build_runs(work, slug, n)` =
`.work/build-runs/<slug>/<n>`, `report(root, slug, n)` = `reports/<slug>/<n>/index.html`. The
clone is `.work/<repo name>` (`cassandra`, `cassandra-sidecar`, `cassandra-analytics`): the
existing Cassandra clone needs no move. Slugs are never numeric, so old and new layouts cannot
collide during migration.

### D5. One-time migration of Cassandra data
`layout.migrate(work, reports)` runs at the start of every command and is a no-op once done. It
migrates this checkout's `reports/` only when the command uses the default work dir, so tests and
other work dirs never touch it. It
moves numeric `.work/pr/<n>`, `.work/build-runs/<n>` and `reports/<n>` into the `cassandra/`
subdirectory, rewrites the absolute classpath paths in each moved `status.json` (the kept build
classpath is recorded as absolute paths; without the rewrite PMD would silently lose type info),
and removes numeric `.work/wt/<n>` worktrees with `git worktree remove --force` (they are a
checkout of a sha and are recreated on demand). A target that already exists is left alone and
the source kept, and the run logs it; nothing is deleted except the old worktrees.

### D6. PMD baseline per project
Branch baselines live in `<work>/static-cache/baselines/<repo name>/` (the clone's directory name),
so sidecar's `trunk` never reuses Cassandra's. Old Cassandra baselines at the top of `static-cache/`
are not found and get rebuilt once. The per-file result caches beside them are keyed by tool,
config hash and blob sha, so they are safe to share across projects and stay where they are.

### D7. Report
The model gains `project: {slug, repo, name, suite_labels}` (optional in `validate`, so models
from before this change still read). The report's title and eyebrow use `project.name`, the base
branch link uses `project.repo`, and the testing section groups files by the model's per-file
`suite` with the profile's labels instead of its own copy of the Cassandra prefixes.

### D8. CLI
`pr` is a string: `5201`, `sidecar#397`, `apache/cassandra-sidecar#397`, or a
`https://github.com/<repo>/pull/<n>` URL; `--project` sets the project for a bare number and must
agree with an explicit one. `cpr prepare` prints `project` in its JSON.

## Risks / Trade-offs

- [Some checks still apply Cassandra rules to sibling PRs until sibling-checks] → the README says
  sibling reports are preliminary; poll does not list sibling PRs, `bin/publish-pages` publishes only
  `reports/cassandra/`, and `cpr comment` refuses other projects until site-multiproject.
- [Migration runs on the owner's real caches] → moves only numeric directories, never overwrites,
  tested against a fake work dir with a kept classpath and a real git worktree.
