## Why

Sidecar and analytics reports now have their own checks, lenses and published pages, but the Build &
coverage section always reads "not built": `cpr build` runs only apache/cassandra's Ant build. So a
subproject PR never gets compile, unit-test or changed-line coverage evidence, and PMD never has type
information for it.

## What Changes

- `cpr build sidecar#N` / `analytics#N` runs the project's Gradle build in the same sandbox and gate as
  Cassandra's (committers automatically, anyone else with `--approve <head>`), through a strategy seam in
  `cpr/build/runner.py`: `Build` stays the Ant build and `cpr/build/gradle.py` `GradleBuild` overrides its steps.
- A PR that changes the Gradle wrapper is not built.
- Dependencies are resolved at the merge-base (networked, trusted code, cpr's own init script, a run-local
  Gradle home and an empty run-local Maven repository); the head is compiled and tested offline with no
  network. A dependency the merge-base did not resolve reads unknown, never failed.
- Sidecar's test fixtures need an in-JVM dtest jar: it is built from the Cassandra sha the merge-base's
  `scripts/build-dtest-jars.sh` pins and shaded by its `scripts/build-shaded-dtest-jar-local.sh`, in the
  networked sandbox, and cached by those scripts' content.
- Test selection and changed-line coverage work over a Gradle multi-module layout; per-module JaCoCo
  reports are merged; JUnit and JaCoCo files are found wherever the project writes them.
- The no-network sandbox profile gets the writable GRADLE dir the networked one had.
- JDK homes include the Homebrew OpenJDK installs.

## Non-goals

- Integration, container and dtest suites (they need Docker, more dtest jars or a cluster).

## Capabilities

### New Capabilities
- `gradle-build`: sandboxed Gradle builds, unit tests and changed-line coverage for the subprojects.

## Impact

New `cpr/build/gradle.py`, `cpr/assets/cpr-init.gradle`; `cpr/build/{runner,select,coverage,sandbox}.py`,
`cpr/assets/sandbox{,-net}.sb`, `cpr/config/build.json`, `cpr/config/projects/*.json` (`build` block
replaces `build_tool`), `cpr/project.py`, `cpr/cli.py`, `cpr/assets/report.html` (one sentence),
`docs/report/subprojects/{build,static}.md`, README, tests. Cassandra builds are unchanged.
