# Build & coverage

## What is checked

Three checks read the saved result of `cpr build <PR>`: whether the PR compiled, whether selected unit tests passed, and whether the lines the PR added ran under those tests.

For Cassandra Sidecar and Cassandra Analytics, `cpr build` runs the project's own Gradle build, in a sandbox, as follows:

1. **Wrapper check.** A PR that changes the Gradle wrapper (`gradlew`, `gradle/wrapper/`) is not built. The wrapper chooses and runs the Gradle distribution, so the PR would choose what runs.
2. **Resolve at the merge-base.** At the merge-base (trusted code), with network, cpr's own init script resolves every dependency into the run's Gradle home. It also uses an empty Maven repository of its own, never `~/.m2`.
3. **Sidecar's dtest jar.** Sidecar's test fixtures compile against an in-JVM dtest jar. It is built from the Cassandra sha that the merge-base's `scripts/build-dtest-jars.sh` pins, and shaded by the merge-base's `scripts/build-shaded-dtest-jar-local.sh`. The jar is cached, so later builds reuse it.
4. **Build the head.** At the PR head, offline and with no network, Gradle compiles every Java module, then runs the selected unit test classes with JaCoCo. The selected classes are the PR's own tests, `FooTest` for a changed `Foo`, and tests that reference the changed classes.

Building runs the PR author's code, so it is gated: committers' PRs build automatically, and anyone else's needs `--approve` for the exact head.

`cpr review` never builds. Without a saved result for the current head, all three checks are not-applicable and nothing blocks.

## Why

- The project's own CI builds the PR and runs its unit and integration tests on every PR to `trunk`; the CI aspect reads that result. The local build adds what CI does not report: which added lines the tests ran. Sources: [Sidecar TESTING.md](https://github.com/apache/cassandra-sidecar/blob/trunk/TESTING.md), "Code Coverage"; [Analytics DEV-README.md](https://github.com/apache/cassandra-analytics/blob/trunk/DEV-README.md).
- Sidecar builds its dtest jars the same way in CI (`scripts/build-dtest-jars.sh`, "Build dtest jars" in `.github/workflows/ci.yml`).

## How each status is decided

The saved result has a `status`: `pass`, `tests-failed`, `build-failed`, `timeout`, `unknown` or `not-built`. A result counts only if its `head` equals the PR's current head sha.

### `build.compiles`

**Blocking.** Owner: contributor.

- **fail**: a module failed to compile. The evidence lists the compile errors (file, line, message).
- **pass**: every Java module compiled with its tests.
- **unknown**:
  - The PR changes the Gradle wrapper (not built).
  - A dependency the head needs is not among those resolved at the merge-base. The PR probably added or changed one, and an offline build cannot fetch it.
  - Resolving at the merge-base failed, or the dtest jar could not be built.
  - The run hit its time cap.

  An unknown result does not block.
- **not-applicable**: not built for this head.

### `build.tests-pass`

**Blocking.** Owner: contributor.

- **fail**: a selected test failed again when re-run on its own. The evidence names each failing class and method.
- **pass**: the selected tests ran with no failures or errors.
- **unknown**:
  - A failure passed on the re-run (flaky).
  - A module's test task exited non-zero with no failing test found.
  - No test result was written.
  - The run hit its time cap.
- **not-applicable**: not built, or the build failed.

### `build.changed-line-coverage`

**Advisory.** Owner: contributor.

- **warn**: at least one added executable line under a module's `src/main/java` did not run. Each module writes its own JaCoCo report; they are merged.
- **pass**: every added executable line ran.
- **unknown**: no JaCoCo report was produced, or a changed file is missing from every report.
- **not-applicable**: not built, the build failed, or the PR adds no executable production line.

## How to fix

- A **compile error** or **failing test**: fix it on the branch.
- **Changed-line coverage**: add or extend a unit test that runs the added lines, in the module's `src/test/java`.
- A **dependency not resolvable offline** is not a defect. A committer can check the new dependency and rely on CI for the build.
- To build the same way yourself:

  ```
  ./gradlew :server:test --tests '<TestClass>'                      # Sidecar (after ./scripts/build-dtest-jars.sh)
  ./gradlew :cassandra-analytics-core:test --tests '<TestClass>'    # Analytics
  ```

## Limits

- Only unit tests run. Sidecar's integration and container tests, and Analytics' integration modules and per-Cassandra-version dtests, need Docker, dtest jars or a cluster, so they are listed as not run.
- Only selected classes run, so coverage reflects those classes, not the whole suite.
- Every Java module is compiled with its tests, but only the selected classes' modules run tests.
- PMD's type resolution uses the compiled classes and resolved jars this build keeps (see the Code style aspect).
