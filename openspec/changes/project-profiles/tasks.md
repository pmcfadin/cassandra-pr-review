## 1. Profiles

- [x] 1.1 `cpr/config/projects/{cassandra,sidecar,analytics}.json` and `cpr/project.py` (load, list, of(bundle), parse_ref) (tests: lookup by slug and repo, old bundle, refs and URLs, unknown project)
- [x] 1.2 Classifier from the profile in `cpr/paths.py`; Cassandra profile reproduces today's prefixes (tests: every existing path case unchanged; sidecar and analytics layouts)
- [x] 1.3 Keys and credits from the profile, including `for [KEY-N](url)` (tests per design D3)

## 2. Repository and storage

- [x] 2.1 GitHub client, clone, bundle, poll, comment and bench take the repo from the project; bundle records `meta.project`
- [x] 2.2 `cpr/layout.py` per-PR paths; every caller uses it; PMD baseline keyed by project
- [x] 2.3 One-time migration (tests: moves, classpath rewrite, idempotent, never overwrites, worktree removal)
- [x] 2.4 CLI: PR references and `--project`; `cpr prepare` prints `project`

## 3. Consumers

- [x] 3.1 Checks, triage, lenses, history, context and model classify with the bundle's project (labplan stays Cassandra-only; sibling-checks turns it off for the siblings)
- [x] 3.2 Model `project` block; report title, base-branch link and test suites from it (browser test still passes)
- [x] 3.3 README

## 4. Ship

- [ ] 4.1 `cpr review 5201` before and after: same model apart from paths and `project` (done offline over every recorded bundle: identical); `cpr review sidecar#400` classifies modules (done); a live Cassandra run on the owner's existing `.work` to exercise the migration
