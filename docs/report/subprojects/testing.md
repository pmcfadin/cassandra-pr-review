# Testing

## What is checked

One automated check: when a PR changes production code, does it also change test code? It looks only at which files changed. It does not build, run, or read the tests.

The rest of this page explains what each project expects from tests, so you can meet the standard reviewers apply by hand.

### The test suites

Both projects are Gradle multi-module builds; each module keeps its tests in its own `src/` directories.

**Cassandra Sidecar**

| Suite | Where | Run with | Use it for |
|---|---|---|---|
| Unit | `src/test/` in each module | `./gradlew test`, `./gradlew :server:test` | Components in isolation, no external dependencies. |
| Integration | `src/integrationTest/`, `server/src/test/integration/` and the `integration-tests` module | `./gradlew integrationTest` (`integrationTestLightWeight`, `integrationTestHeavyWeight`) | Behaviour against running in-JVM Cassandra instances. Multi-node and complex tests are tagged `@Tag("heavy")`. |
| Container | `server/src/test/containerTest/` (and any `src/containerTest/`) | `./gradlew containerTest`, or `./gradlew check` for every suite | Only tests that need testcontainers, such as the S3 mock for restore. |
| Test fixtures | `src/testFixtures/` | | Shared test utilities. |

Integration tests need the in-JVM dtest jars built from Cassandra first (`./scripts/build-dtest-jars.sh`) and network aliases for multi-node tests; container tests need Docker. Source: [Sidecar TESTING.md](https://github.com/apache/cassandra-sidecar/blob/trunk/TESTING.md).

**Cassandra Analytics**

| Suite | Where | Use it for |
|---|---|---|
| Unit | `src/test*/` in each module | Logic that runs without a cluster. |
| Integration | `cassandra-analytics-integration-tests` | Bulk reader and bulk writer against in-JVM Cassandra clusters with Sidecar, including topology changes. |
| Integration framework | `cassandra-analytics-integration-framework` | Shared cluster setup for the integration tests. |
| Test fixtures | `src/testFixtures*/` | Shared test utilities. |

Integration tests need the dtest jars and Sidecar libraries built first (`./scripts/build-dependencies.sh`) and loopback aliases and host names for multi-node tests. Source: [Analytics DEV-README.md](https://github.com/apache/cassandra-analytics/blob/trunk/DEV-README.md), "Dependencies" and "Running Integration Tests".

### Which suite fits which change

- **A bug fix**: a regression test that fails without the fix, in the lowest suite that can reproduce it.
- **A Sidecar endpoint or handler**: a unit test for the handler, and an integration test for behaviour that needs Cassandra.
- **Behaviour that differs by Cassandra version** (Sidecar adapters, Analytics bridges): tests that run against every supported version.
- **Topology changes in Analytics** (expansion, shrink, replacement, movement): the integration tests that pause a change with ByteBuddy. Source: [Analytics DEV-README.md](https://github.com/apache/cassandra-analytics/blob/trunk/DEV-README.md), "Topology-change tests".

## Why

- Sidecar's container tests are only for tests that need testcontainers; "otherwise, a unit or in JVM dtest integration test is preferred". Source: [Sidecar TESTING.md](https://github.com/apache/cassandra-sidecar/blob/trunk/TESTING.md), "Container Tests".
- Sidecar APIs must behave the same on Cassandra trunk and every supported version, and "testing and validation must cover the trunk and all supported versions". Source: [Sidecar CONTRIBUTING.md](https://github.com/apache/cassandra-sidecar/blob/trunk/CONTRIBUTING.md), "RESTful API Design Guidelines".
- In Analytics, a Cassandra API that changed between majors compiles and fails only at runtime, so tests on each version catch what the build does not. Source: [Analytics DEV-README.md](https://github.com/apache/cassandra-analytics/blob/trunk/DEV-README.md), "Bridge Modules".

## How each status is decided

### `tests.present`

**Blocking.** Owner: contributor.

The check sorts changed files by path:

- **Production code** is any path under a module's `src/main/` that is not a test path.
- **Test code**, Sidecar: `src/test/` (its `integration/` and `containerTest/` subdirectories are their own suites), `src/integrationTest/`, `src/containerTest/`, `src/testFixtures/`, and the `integration-tests`, `integration-framework` and `test-common` modules. Analytics: `src/test*/`, `src/testFixtures*/`, and the `cassandra-analytics-integration-tests` and `cassandra-analytics-integration-framework` modules. Each test file is assigned the suite from the tables above (`other` for Sidecar's `integration-framework` and `test-common`).

Then:

- **not-applicable**: no production lines changed. Docs-only, build-only, and test-only PRs land here.
- **fail**: production code changed and no test file changed. The recommendation becomes "needs contributor work".
- **pass**: production code changed and at least one test file changed. The summary names the suites and the ratio of test lines to production lines; files under the tests' `resources/` directories count as a test change but not toward the ratio.

## How to fix

Write the test before the fix, watch it fail, then apply the fix. Run one class with Gradle:

```
./gradlew :server:test --tests "org.apache.cassandra.sidecar.HealthServiceTest"
./gradlew :integration-tests:integrationTestLightWeight --tests "<IntegrationTestClass>"
./gradlew cassandra-analytics-integration-tests:test --tests "<TestClass>"
```

- Pick the suite from the tables above, starting with the lowest level that can show the behaviour.
- For a timing-sensitive or multi-node test, run it several times and say so on the PR.
- If no test is possible, explain why in the PR description. The check still fails; a reviewer decides.

## Limits

- **Presence only.** A one-line edit to an unrelated test, or to a test fixture, satisfies it.
- **Tests are not run.** Results come only from the GitHub CI checks (see the CI aspect).
- **No judgement of fit.** Whether version-dependent behaviour is tested on every supported Cassandra version is the reviewer's call.
