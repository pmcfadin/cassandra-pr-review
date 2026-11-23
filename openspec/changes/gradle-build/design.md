## Context

Spike, 2026-11-23, on sidecar #400 (committer, merged) and analytics #262 / #260:
- Gradle 8.9 (sidecar) and 8.14.3 (analytics) resolve everything at the merge-base in about 65 s with a
  lenient resolve of every configuration from an init script; the head then builds `--offline` inside
  the no-network sandbox profile (with a writable GRADLE_USER_HOME).
- Sidecar's `test-common` test fixtures compile against `dtest-4.1.11.jar` (compileOnly). The raw
  `ant dtest-jar` output clashes with sidecar's driver (it bundles the driver with relocated Netty); the
  jar must be shaded the way sidecar's own script does it (Maven shade relocating `io.netty`,
  `com.datastax`, ...). Built once: about 100 s.
- Sidecar's repositories include `mavenLocal()`: with the real `~/.m2` a stale locally installed
  `cassandra-analytics 0.5-SNAPSHOT` from September won over the published snapshot and broke the test
  compile (`CassandraVersion.SIXZERO` missing). An empty run-local `maven.repo.local` fixed it.
- Analytics writes JUnit XML to the root `build/test-results/<module>/test/` and its JaCoCo XML to a file
  named `build/reports/jacocoXml` (no extension); sidecar uses the defaults.
- `JacocoPlugin` applied from `allprojects { plugins.withId('java') }` resolved `jacocoAgent` before
  analytics' `configurations { all*.exclude ... }` ran; wiring it in `afterEvaluate` avoids that.
- A probe test (read `~/.ssh`, write `$HOME`, connect to github.com, read `.work/pr/...`) run by Gradle
  under the real no-network profile: all four blocked.

## Decisions

### D1. Strategy by subclass
`GradleBuild(runner.Build)` overrides `prepare`, `make_clone`, `resolve_at_base`, `build_head`, `pick_tests`,
`run_tests`, `collect`, `retry_failures`, `changed_coverage` and `keep_classpath`; `execute`, `finish`,
`parse_junit`, `apply_retry`, `map_status`, the gate and the status schema are shared. `runner.build`
picks by the profile's `build.tool`.

### D2. Trusted init script
`cpr/assets/cpr-init.gradle` (copied into the run directory, since the sandbox cannot read cpr's checkout)
adds `cprResolve`, `cprProjects` (path, dir, Java or not) and `cprClasspath`, and wires JaCoCo XML on every
Java project after its own build script.

### D3. Wrapper and dependencies
A diff touching `gradlew`, `gradlew.bat` or `gradle/wrapper/` stops the run as unknown before any Gradle
call. Resolution runs at the merge-base in the networked profile; the head runs `--offline` in the
no-network profile. Gradle's "No cached version ... available for offline mode" / "Could not resolve all
files" maps to unknown with "did the PR add or change one?".

### D4. Sidecar's dtest jar
Profile `build.dtest_jar` names the file that declares the jar (`test-common/build.gradle`), the pin script
and the shade script. The jar name comes from the declaring file at the merge-base, the Cassandra sha from
the pin whose `build.xml` `base.version` matches. The shade script, copied from the merge-base into the
writable Cassandra checkout, runs in the networked profile with ANT_ARGS, M2_HOME, MAVEN_USER_HOME and
MAVEN_OPTS pointed at run-local dirs. The result is cached at
`.work/build-cache/<slug>/dtest-jars/<sha256 of both scripts>/`.

### D5. Steps at the head
`cprProjects`, then `testClasses` of every Java project not in `build.skip_modules` (so a compile break in
any module shows), then `:<module>:test --tests <class>...` for the selected classes plus `cprClasspath`,
with `--continue`. A failing class is re-run once with `--rerun`.

### D6. Selection and coverage
`select.select_gradle` indexes every module's `src/test/java/**/*Test.java` (skipping `build.skip_modules`),
scores with the same `_rank` as Cassandra (changed test, `FooTest`, prefix, references, changed methods,
one hop of subtypes) and maps each pick to the deepest owning module. Coverage reads added lines under
`**/src/main/java` and merges every module's JaCoCo report.

### D7. Results
JUnit (`TEST-*.xml`) and JaCoCo (by DOCTYPE, under a `reports/` dir, `.xml` or no extension) files are
found under any `build/` directory, newer than the test step's start, regular files only.

## Risks / Trade-offs

- [Snapshots move: a sidecar build depends on the published analytics SNAPSHOT of the day] → same as the
  project's CI; the merge-base resolve fixes it per run.
- [~560 MB of jars hard-linked per kept classpath] → the existing prune keeps five runs.
- [Only unit tests] → the CI aspect carries integration results.
