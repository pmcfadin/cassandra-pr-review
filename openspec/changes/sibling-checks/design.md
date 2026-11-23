## Context

Facts (checked 2026-11-20 against the repos and the GitHub API):
- Both subprojects run GitHub Actions on every PR: sidecar #400 head `7e621ed` has 21
  check-runs from one `CI` workflow run; analytics PRs about 36. Sidecar #401 (outside contributor)
  has 0 check-runs and one workflow run with `conclusion: action_required`. Nothing is attached
  to their JIRA tickets.
- Sidecar `build.gradle`: `checkstyle { toolVersion '7.8.1'; configFile rootDir/checkstyle.xml }`
  for main and test; the config uses `FileContentsHolder` (removed in checkstyle 8.2) and a
  `${...LineLength.ignorePattern}` property with a default. Checkstyle 7.8.1 runs it standalone.
- Analytics applies the checkstyle plugin with no `toolVersion`, so Gradle 8.14's default, 9.3;
  `config/checkstyle/checkstyle.xml` reads `${config_loc}/suppressions.xml`. Checkstyle 9.3 runs it
  standalone with `config_loc` set, and fails without it.
- Subjects are `KEY-N: title (#PR)` (squash merges); the credit line is the same as Cassandra's.

## Decisions

### D1. Everything per project lives in the profile
New profile fields: `ci_provider` (`jira-ci-summary` | `github-checks`), `disabled_checks`,
`labplan` (bool), `commit_subject_key` (`forbidden` | `allowed`), `commands` (the wording for the
project's own check commands), `static` (D4), `compat_surfaces` (`[[name, regex]]`), optional
`triage` overrides (`concurrency_paths`, `hard_surfaces`), `not_checked` (the About list) and
`docs_dir`. The Cassandra profile holds today's values, moved out of code, so its reports do not
change. Check titles may contain `{key}` (the project's first JIRA key).

### D2. Disabled checks
`checks.run_all` returns `not-applicable` for an id in `disabled_checks`, summary "Not part of
<name>'s process". The check still appears, so the report says what was not judged and why.
Subprojects disable: `compat.config-pairing`, `compat.system-properties`, `compat.nodetool-help`,
`ci.profile`, `commit.perf-structure`, `static.deprecated-since` (sidecar's client targets Java 8,
where `since` does not exist), `static.protected-paths` (no generated code or bundled jars in
the tree).

### D3. CI from GitHub
`cpr/ingest/gh_checks.py` reads `repos/<repo>/commits/<head>/check-runs` and
`repos/<repo>/actions/runs?head_sha=<head>` (read-only, recorded like every other call) into
`bundle.ci.github = {status, head_sha, check_runs: [{name, status, conclusion, app, url}],
workflow_runs: [{name, status, conclusion, event, url}]}`; `ci.summaries` stays empty. The checks:

- `ci.evidence`: no check-runs and a workflow run `action_required` → **unknown**, "CI is waiting for
  a maintainer to approve the workflow runs" (owner committer: approve them on the PR). No
  check-runs at all → **fail**, CI not run on the head. Any check-run not completed → **unknown**,
  still running. Otherwise **pass**. GitHub unreachable → **unknown**.
- `ci.freshness`: check-runs are read for the head sha itself, so **pass** whenever there are any,
  else not-applicable.
- `ci.failures`: completed runs with `failure`, `timed_out` or `startup_failure` → **warn** listing
  them; `cancelled` is listed, not counted; none → **pass**.
- The model's branch row for the PR gets a `ci` block from the check-runs (passed, failed,
  skipped, total, sha = head), so Branches & CI shows the run.

Both subprojects' workflows run only for PRs to `trunk` (`ci_branches`): a PR to another branch
with no check-run and no workflow run is `not-applicable` for `ci.evidence`, not a failure.

### D3b. Builds
`build_tool` names the build `cpr build` can run (`ant` for Cassandra; none for the subprojects).
`cpr build` on a project without one records "not built" with that reason and runs nothing, so a
committer's sidecar PR never gets an Ant build attempt (gradle-build adds `gradle`).

### D4. Static analysis follows the project's layout and config
`static.main` / `static.test` are regexes for the Java files checkstyle and PMD treat as main and
test (and for which complexity and PMD findings count as test code) (Cassandra: `^src/java/` and `^test/`, as today; not the general classifier, which also
counts e.g. `tools/stress/.../test/` as test and would change Cassandra results). `static.exclude`
moves from static.json into the profile. `static.baseline_roots` are the trees `git archive`
reads for the PMD branch baseline (`src/java` for Cassandra; the whole tree filtered by
`static.main` for the subprojects). `static.checkstyle` gives `tool` (a fixed tool id; Cassandra
keeps `checkstyle_by_branch`), `files` (copied from the base branch), `required`, `configs`
(`{main, test}` → file) and `properties` (`{logdir}` and `{config_dir}` are filled in). The bundle's
`base_files.checkstyle_xml` (the banned-API approximation) is the project's main config. Two pins
are added to static.json: checkstyle 7.8.1 and 9.3 (`-all` jars from the checkstyle GitHub
releases; sha256 recorded on first download, 2026-11-20).

### D5. Commit, ticket and changelog wording
`commit_subject_key: allowed` drops the "first line repeats the ticket key" problem. Messages that
name `CASSANDRA-N` use the project's key. The Cassandra-only merge-order text in
`branches.coverage` appears only when the project has release branches beyond trunk.

### D6. Docs
`render.load_docs(project)` reads `docs/report/<docs_dir>/<aspect>.md` when it exists, else the
shared `docs/report/<aspect>.md`. Both subprojects share `docs/report/subprojects/` for the aspects
whose rules differ (jira, branches, ci, commits, compatibility, static, testing, build, labplan);
each doc names the differences between sidecar and analytics where there are any. The aspect-doc
test applies to every docs directory.

## Risks / Trade-offs

- [Check-runs from other apps (e.g. a bot) are counted as CI] → all apps are listed with their app
  slug; only GitHub Actions runs exist today.
- [Checkstyle 7.8.1 cannot parse newer Java syntax] → that is the project's own gate; the report
  matches what their Gradle build would say. Parse failures surface as `unknown` per file.
- [Pinned jar hashes are trust-on-first-use] → the URLs are the project's GitHub releases over TLS;
  the hashes are recorded so later downloads must match.
