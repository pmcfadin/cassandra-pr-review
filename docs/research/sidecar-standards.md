# Apache Cassandra Sidecar contribution and review standards (as of 2026-11-20)

Research input for the cassandra-pr-review tool (cpr), read by its review lenses when they review an
apache/cassandra-sidecar PR. Every rule cites a primary source. Repo paths refer to `apache/cassandra-sidecar`
trunk at commit `19e3143801e497534d441dd53c04155ee87e98ef` (2026-11-17, "CASSSIDECAR-378: Add support for
creation and coordination of local Sidecar jobs (#397)"). Review evidence comes from the inline comments and
reviews of merged PRs #356 to #400 (29 PRs read). Anything marked **(inferred)** was not read in a source but
follows from code or practice.

Abbreviations: **[C]** = `CONTRIBUTING.md`; **[T]** = `TESTING.md`; **[OA]** = `OPENAPI.md`;
**[VT]** = `docs/vertx-threading-model.md`; **[G]** = `server/src/main/java/org/apache/cassandra/sidecar/modules/guice-best-practice.md`;
**[R]** = `README.md`; **[AG]** = `AGENTS.md`; **[SEC]** = `SECURITY.md`; **[N]** = `NEWS.txt`;
**[CH]** = `CHANGES.txt`; **[CS]** = `checkstyle.xml`; **[B]** = `build.gradle` and the module `build.gradle`
files; **[CI]** = `.github/workflows/ci.yml`; **[ASF]** = `.asf.yaml`; **[U]** = `docs/src/user.adoc`;
**[GOV]** = https://cwiki.apache.org/confluence/display/CASSANDRA/Cassandra+Project+Governance.
**#N rID** = `https://github.com/apache/cassandra-sidecar/pull/N#discussion_rID` (inline comment);
**#N review ID** = `https://github.com/apache/cassandra-sidecar/pull/N#pullrequestreview-ID`.

What cpr's deterministic checks already judge for sidecar is in `docs/report/subprojects/*.md`: ticket key and
JIRA state, Fix Version, CHANGES.txt line presence and format, commit credit line, AI provenance trailers,
checkstyle, licence headers, test presence, which surfaces a PR touches (by path), and CI status. The lenses
must not repeat those checks. This file covers what needs reading the code.

---

## 0. Things a reviewer tool must not get wrong

- **One branch, squash merge on GitHub.** Sidecar has only `trunk`. GitHub allows squash only, and `trunk`
  requires status checks with an up-to-date head. [ASF] `enabled_merge_buttons`, `protected_branches`. Unlike
  Cassandra, PRs are merged on GitHub, often by the author once a committer has given +1 (for example #400 was
  merged by its author after frankgh's +1, #400 review 5906822397). There are no backports.
- **Two Java levels.** `client`, `client-common` and `vertx-client` compile with `sourceCompatibility = 1.8`.
  The server modules compile with Java 11. `settings.gradle` includes the server modules only on Java 11+.
  Sources: `settings.gradle`; `client/build.gradle`; `client-common/build.gradle`; `vertx-client/build.gradle`;
  `server/build.gradle`. `sourceCompatibility = 1.8` on a JDK 11 compiler does not stop Java 9+ API calls such
  as `List.of`. Only the CI job "Unit tests (Java 8 - Client only)", which runs `./gradlew build` on JDK 8,
  catches them. [CI] `unit-tests-java8`. **(inferred from the build setup)**
- **Supported Cassandra versions.** 4.0, 4.1, 5.0 and 5.1 (trunk) in CI, on Java 11 and 17 (17 only for 5.0
  and 5.1). [CI] `integration-tests-lightweight` matrix. Local default is `4.1,5.1`.
  `test-common/src/testFixtures/java/org/apache/cassandra/testing/TestVersionSupplier.java`.
- **Stale names in [C].** [C] shows `builderForUnprotectedRoute()` and `SidecarFailureHandler`. Trunk has
  `RouteBuilder.Factory#builderForUnauthorizedRoute()` (`server/.../routes/RouteBuilder.java`) and
  `JsonErrorHandler` (`server/.../handlers/JsonErrorHandler.java`). Judge against trunk code.
- **Test directories differ from [T].** [T] says integration tests live in `src/integrationTest/` and container
  tests in `src/containerTest/`. That holds for the `integration-tests` module. In `server`, integration tests
  are in `server/src/test/integration/` and container tests in `server/src/test/containerTest/`.
  `server/build.gradle` `sourceSets`. A file under `server/src/test/integration/` is an integration test, not a
  unit test.
- **NEWS.txt exists** with `Upgrading` and `New features` per release ([N] `0.5`, `0.4`). cpr does not check it.
- **AGENTS.md is only a security pointer.** It sends agents to [SEC], which links the umbrella Cassandra
  security model (`doc/modules/cassandra/pages/reference/security-model.adoc` in apache/cassandra). [AG]; [SEC].

---

## 1. Workflow

### 1.1 JIRA and design
- Find an existing JIRA issue or start a discussion on the Cassandra dev list first. Then create a ticket with a
  self-contained description, because JIRA holds the design decisions. [C] "Discuss", "Create a Ticket".
- The JIRA project is CASSSIDECAR; the old key CASSANDRASC still autolinks. [R]; [ASF] `autolink_jira`.
- A new API or a significant API change needs a design proposal first: the API spec in the ticket, a one-page
  public doc where complex, and a `[DISCUSS]` thread for groups of APIs. The proposal states the HTTP method,
  full URL, request and response structure, and marks each field required or optional. [C] "API Proposal
  Process", "RESTful API Design Guidelines". Sample: CASSSIDECAR-274.
- The proposal must state the Cassandra compatibility matrix and any version-specific limits. [C] "Cassandra
  Compatibility Considerations".
- Long-running operations use the job framework (`OperationalJob`), return a job UUID for polling, and must
  document resource needs, expected duration and user-visible statuses. [C] "Job Management for Long-Running
  Commands".

### 1.2 PR, commit and changelog conventions
- PR title and squash subject: `CASSSIDECAR-N: summary (#PR)`. Credit line:
  `Patch by <authors>; Reviewed by <reviewers> for CASSSIDECAR-N`, sometimes with the key as a Markdown link.
  Trunk history, for example `19e31438`. (cpr checks this.)
- `CHANGES.txt` entry ` * summary (CASSSIDECAR-N)` at the **top** of the section of the **unreleased**
  version. Reviewers push back on placement: "can we move this to the top of the list?" (#358 r3489084323);
  "Lets add this under `0.5.0`, `0.4.0` release is already out" (#376 r3786164134). cpr checks presence, not
  the section.
- The entry must describe everything the patch fixes: when a patch fixed a second bug, the reviewer asked to
  name both in the line (#374 r3753934222).
- `NEWS.txt` gets an entry under the unreleased version for new features, new internal tables, renamed or
  deprecated settings, and changed validation defaults. [N] `0.5`/`0.4` "Upgrading"; #376 r3786166502.
- AI assistance: one trunk commit carries `Assisted-by: Claude Opus 4.8 (1M context)` (git log since
  2026-01-01). cpr checks trailers.

### 1.3 Reviews and votes
- Sidecar is part of the Apache Cassandra project, so [GOV] applies: code changes need review by another
  contributor and two committer +1s (author plus reviewer counts); CI results before commit. **(applying
  [GOV] to sidecar is inferred; [GOV] does not name subprojects)**
- Observed: reviewers give "+1" as a GitHub approval; non-committers mark "+1 (nb)" (#360 review 4665815968).
  Reviewers ask for a rebase before merge (#357 review 4382721278; #386 issue comment 6348524815) and sometimes
  for a CircleCI link from the contributor's fork (#389 review 5435373546).
- A reviewer may hold a PR until a dependent piece lands in the same PR: "I am afraid to merge this PR without
  calling clearActive" (#360 r3436977162).

---

## 2. Code style beyond checkstyle

Checkstyle ([CS], version 7.8.1 in [B]) enforces Allman braces (`LeftCurly nl`), `RightCurly alone`, import
order (`java`, `javax`, `com.google.common`, `org.apache.commons`, `org.junit`, `org.slf4j`, others, statics at
the bottom), javadoc on protected and public types and methods, no `System.out/err.println`, no
`printStackTrace()`, `TODO` followed by `:`, space or `(`, no `FIXME`, line length 160 (warning). SpotBugs 4.2.3
runs on non-test modules with `spotbugs-exclude.xml` ([B]); RAT checks headers. cpr runs checkstyle; it does not
run SpotBugs. What remains for a human:

- **Format with the project IntelliJ settings** (`ide/idea/codeStyleSettings.xml`, installed by
  `./gradlew idea`). [C] "Integration with IntelliJ IDEA". Continuation style seen across the code puts `=` on
  the next line for long initialisers (for example `metrics/server/CoordinationMetrics.java`).
- **Guice, not statics.** Prefer injected singleton classes over static utility methods and unmanaged global
  state. [G] "Prefer binding utility as singleton". Reviewer: a static map in `LiveMigrationInstanceMetadataUtil`
  should be injected via Guice and bounded (#367 r3539501130).
- **Bind to interfaces** where another implementation may follow. [G]. Prefer a no-op implementation to a
  nullable collaborator: "The nullable `OperationalJobCoordinator` feels like a bit of a smell", leading to
  `DisabledOperationalJobCoordinator` (#360 r3544181050; `server/.../job/DisabledOperationalJobCoordinator.java`).
- **Feature modules own their bindings.** Bindings used only by one feature live in that feature's module, and a
  conditionally installed module (installed with `SidecarModules#addIf`) must be self-contained. Classes owned by
  a conditional module must not carry `@Singleton` on the class, because `@Singleton` plus `@Inject` makes Guice
  create them by just-in-time binding even when the module is absent; declare the scope in the module. [G]
  "Scope all dependencies to the feature module", "Declare scope in the module".
- **Routes use multibinding annotations** (`@ProvidesIntoMap` plus `@KeyClassMapKey(VertxRouteMapKeys.X.class)`),
  with the DSL only when the bound instance is also injected directly elsewhere and must stay one instance. [G]
  "Multi-bindings", "Using binding DSL".
- **Routes go in the module of their feature** under `server/.../modules/` (for example
  `CassandraOperationsModule`, `HealthCheckModule`). [C] "Implementation Details".
- **Return immutable collections** from data objects (#376 r3787559413). Reuse an existing helper instead of a
  near copy (#376 r3787512938, "Can we use `getKnownStatus()` instead").
- **Keep the PR to its ticket.** Reviewers flag unrelated changes: "It also seems to be unrelated to the goal"
  (#366 r3448026677); "noticed some unrelated CDC changes. Can we revert them" (#390 review 5609744981).
- **Remove what the patch leaves unused** (#391 r4212724466, `UNKNOWN_SHORT`) and stale javadoc (#358
  r3395485888; #369 r3570687133).
- **Annotations in use:** `org.jetbrains.annotations.NotNull/Nullable`, Guava `Preconditions` and
  `@VisibleForTesting`, time-based UUIDs from `UUIDs.timeBased()`; `OperationalJob` rejects non-v1 UUIDs.
  `server/.../job/OperationalJob.java`; `handlers/NodeDrainHandler.java`.

---

## 3. Testing regime

### 3.1 Suites

| Suite | Location | Run with | What it is for |
|---|---|---|---|
| Unit | `<module>/src/test/java/` | `./gradlew test`, `./gradlew :server:test` | One component in isolation, no Cassandra. Handlers are tested through a real Vert.x server built with `Modules.override(SidecarModules.all()).with(new TestModule())`, `VertxExtension`, `WebClient`, and Mockito mocks of `CassandraAdapterDelegate` and friends (for example `server/src/test/java/.../handlers/NodeDrainHandlerTest.java`). |
| Integration, lightweight | `server/src/test/integration/`, `integration-tests/src/integrationTest/` | `./gradlew integrationTestLightWeight` | Behaviour against in-JVM dtest Cassandra clusters. Two styles: `@CassandraIntegrationTest` with `CassandraTestContext` (runs per version from `TestVersionSupplier`; `IntegrationTestBase`), and `SharedClusterIntegrationTestBase` / `SharedClusterSidecarIntegrationTestBase` (one cluster for the class, first test version only). |
| Integration, heavyweight | same, tagged `@Tag("heavy")` | `./gradlew integrationTestHeavyWeight` | Multi-node and topology tests (token range joining, leaving, moving, replacement with ByteBuddy helpers in `server/src/test/integration/.../testing/bytebuddy/`). |
| Container | `server/src/test/containerTest/` | `./gradlew containerTest` | Only tests that need testcontainers, today the S3 mock (`restore/StorageClientTest.java`). "otherwise, a unit or in JVM dtest integration test is preferred". |
| Fixtures | `src/testFixtures/`, `test-common`, `integration-framework` | | Shared helpers: `AssertionUtils.loopAssert`/`waitUntil`, `CertificateBuilder`, `TestVersionSupplier`, `MtlsTestHelper`. |

Sources: [T] "Test Types"; `server/build.gradle`; `integration-tests/build.gradle`;
`gradle/common/integrationTestTask.gradle`; `integration-framework/.../SharedClusterIntegrationTestBase.java`;
`docs/src/development.adoc` "Tests".

### 3.2 How they run
- Integration tests need dtest jars from `./scripts/build-dtest-jars.sh` (branches 4.0, 4.1, 5.0, trunk), loopback
  aliases `127.0.0.2..20`, and `localhost1..20` in `/etc/hosts`. [T] "Build Prerequisites", "Network Setup".
- Integration tasks use `forkEvery = 1`, mTLS on by default (`INTEGRATION_MTLS_ENABLED=true`), and log any test
  over 60 s. `gradle/common/integrationTestTask.gradle`. State leaking inside a class is the test's problem; split
  the class if needed. [T] "Test Isolation Issues".
- CI runs checkstyle; unit tests plus SpotBugs on Java 11 and 17 (`build -x integrationTest`, which also runs
  `containerTest` because `server` `check` depends on it **(inferred)**); lightweight and heavyweight integration
  tests per Cassandra version and Java; the Java 8 client job; deb and rpm packaging. [CI]; `server/build.gradle`
  `check.dependsOn containerTest, integrationTest`.

### 3.3 What reviewers expect
- A fix comes with a test that fails without it. PR descriptions say so: "The test fails without the fix"
  (#387 body). Reviewers ask for tests of untested new code: "would be good to test this code" (#400
  r4575422919); "maybe add test exercising cancellation" (#392 r4343278922).
- Tests must reach every code path the fix claims. A reviewer changed an existing integration test to mixed-case
  names and showed the fix missed a path (#365 review 4539350474).
- Mocks must not hide the bug: a unit test passed because it mocked `getFullSchema()` to return `""` (#390
  r4275268029).
- Assert the state after a failure path too: "Also verify that tracker doesn't have entry for this job after
  conflict detected" (#360 r3436915257).
- Async assertions must wait for all retries, not race them: `verify(..., times(1))` against a three-attempt
  retry was flaky; use `loopAssert` until all attempts are seen (#392 r4383662442).
- Config validation must be tested through YAML parsing, not only through the builder (#386 r4153903363).
- Behaviour that differs by Cassandra version must be tested on trunk and all supported versions. [C] "RESTful API
  Design Guidelines".

---

## 4. Review criteria

### 4.1 REST API design and versioning
- Nouns, plural, lower case with `-`, sub-resources for hierarchy; operations such as
  `PUT /api/v1/cassandra/operations/decommission` are an accepted exception. [C] "Design Principles", "Exceptions".
- `GET` never mutates; `POST` creates or triggers; `PUT` is idempotent; `202 Accepted` for async work, `200` when
  done; `409` for conflicts such as a job already running; `500` for server failures; always return a body. [C]
  "Requests and Responses". Job handlers answer through `OperationalJobUtils.sendStatusBasedResponse`
  (`handlers/NodeDrainHandler.java`).
- Responses are bounded: paginate, do not return unbounded lists. [C] "Design Principles" 5.
- No internal details in URLs or responses, and the API is not specific to one Cassandra version. [C] "RESTful API
  Design Guidelines". Removing a filesystem path from responses was its own fix (CASSSIDECAR-477, PR #366).
- Major version is in the URL (`/api/v1`, `/api/v2`). Compatible: new optional fields, new operations, new content
  types. Incompatible (needs a new version): removed fields, removed or changed default fields, changed field
  types, removed operations or content types. Deprecated APIs are marked in code and supported until the next
  version change or a sunset period, and responses should say so. [C] "API Lifecycle". Example of the pattern:
  `ApiEndpointsV2.NODE_SETTINGS_ROUTE` with `common/response/v2/V2NodeSettings` next to the V1 route
  (CASSSIDECAR-272, `f41b3ca8`); deprecated V1 constants keep the old route next to the new one
  (`ApiEndpointsV1.DEPRECATED_SNAPSHOTS_ROUTE`).
- A changed output format is a breaking change even when the type is still `String`: switching schema output from
  the driver's `exportAsString` to `DESCRIBE` changed formatting and contents, and the reviewer asked to normalise
  it or document it (#390 r4275424502, r4275397592).
- A changed status code needs a reason: "Is it expected? 404 -> 400" (#367 r3539598358).
- New endpoints carry JAX-RS (`@GET`, `@Path`) and MicroProfile OpenAPI (`@Operation`, `@APIResponse`, `@Schema`
  with the real response class) annotations. [OA] "Adding Documentation to New Endpoints".
- Vert.x HTTP server metrics are registered only for routes matching `API_V1_ALL_ROUTES` (`/api/v1/.*`).
  `modules/ApiModule.java` `vertx()`. A `/api/v2` route gets no Vert.x route metrics. **(inferred)**

### 4.2 Request and response DTOs, and the Java 8 client
- DTOs live in `client-common/src/main/java/org/apache/cassandra/sidecar/common/` (`request/`, `response/`,
  `data/`) and are shared by server and client. They must stay Java 8. `client-common/build.gradle`.
- The client ignores unknown response fields (`JsonResponseBytesDecoder`, `FAIL_ON_UNKNOWN_PROPERTIES=false`), so
  adding a response field is safe for old clients. A field a new client relies on may be absent from an old server
  and decode as null. **(inferred)**
- Request payloads should carry `@JsonIgnoreProperties(ignoreUnknown = true)` so a newer client can talk to an
  older server (#376 r3801685019).
- `toString()` of a DTO with secrets must redact them, because `AbstractHandler` logs `request={}` at debug and
  error paths. `StorageCredentials#toString` writes `"redacted"`; `AbstractHandler#handle` and `#processFailure`.

### 4.3 Vert.x threading and blocking
- Never block the event loop. Blocking I/O or CPU-heavy work goes to `ExecutorPools`: `service()`
  (`sidecar-worker-pool`, short request work) or `internal()` (`sidecar-internal-worker-pool`, background). Prefer
  `ExecutorPools` over Vert.x worker pools; never use the internal worker pool directly. [C] "Thread Pool Model".
- Prefer async handlers over `blockingHandler`. [C] "Asynchronous Handlers".
- Golden rule: one request runs on exactly one event loop. When a callback comes from a non-Vert.x future
  (Caffeine `Cache<K, Future<V>>`, AWS SDK, any `CompletableFuture`), capture `Vertx.currentContext()` at handler
  entry and `runOnContext` back before touching `RoutingContext`, in success and failure branches. Not needed for
  Vert.x-native async calls or background tasks. [VT]; example `acl/authorization/CachedAuthorizationHandler.java`.
  The CASSSIDECAR-368 bug lost 8 KiB chunks of uploaded SSTables. [VT].
- `TaskExecutorPool#executeBlocking(callable)` defaults to ordered execution per context; two jobs submitted from
  one context then run one at a time and a hung job blocks the rest (#397 r4543978652). Pass `ordered=false` where
  tasks are independent.
- Timers: `executorPools.service().setTimer`, `internal().setPeriodic`. `setPeriodic` can overlap runs; use
  `PeriodicTask` with `PeriodicTaskExecutor` for serial runs with memory visibility between runs. [C] "One-shot
  Timers", "Advanced Periodic Task Scheduling".
- Do not do I/O inside a `ConcurrentHashMap.compute` or other lock (#359 r3405554604; #357 r3307382125).

### 4.4 Cassandra adapters
- `adapters/adapters-base` supports Cassandra 4.0 and later including trunk. A breaking Cassandra change is
  implemented in `base`, with shims for older versions in a versioned adapter whose classes are named
  `CassandraNN*`, selected by `@MinimumVersion` on the factory. [C] "Cassandra Adapters";
  `adapters/adapters-cassandra50/.../Cassandra50Factory.java` (`@MinimumVersion("5.0.0")`). Factories are
  registered in `modules/ConfigurationModule.java`.
- Use the version abstraction, not scattered version checks; degrade gracefully with a clear error where a version
  lacks the feature. [C] "Cassandra Compatibility Considerations". `OperationUnavailableException` maps to 503
  (`handlers/AbstractHandler#determineHttpException`); PR #387 made a disabled-schema path return 503 instead of a
  500 NPE.
- JMX proxies (`adapters-base/.../jmx/*JmxOperations`) are interfaces; calling a method an older Cassandra MBean
  lacks fails at runtime, not compile time. **(inferred)**

### 4.5 Configuration (`conf/sidecar.yaml`)
- Each setting has an interface in `server/.../config/` and an implementation in `config/yaml/*Impl.java` with
  `@JsonProperty` snake_case getters and setters and defaults. `config/yaml/OperationalJobConfigurationImpl.java`.
- YAML is read with `FAIL_ON_UNKNOWN_PROPERTIES=false` (`config/yaml/SidecarConfigurationImpl.java`). A renamed or
  misspelled key is silently ignored and the default applies. A rename must keep the old key working and mark it
  `@Deprecated`, as `DriverConfiguration#username/password` and `#unsupportedTableSchemaRefreshTime` do.
  **(inferred from the mapper setting and the deprecation pattern)**
- Keep the default of a deprecated getter until it is removed; dropping it made a public getter return null (#390
  r4275467449).
- Validate in the setter and handle empty YAML values: `node_execution_timeout:` deserialises to null, skips the
  check and causes an NPE at startup (#397 r4544046235). Validation that runs only in the builder is bypassed by
  Jackson (#386 r4153762015). Validate new options at all (#397 r4399579811) and validate interacting options at
  startup (`CassandraOperationsModule#validateOperationalJobConfiguration`, #397 r4543730099).
- New or changed settings appear, commented, in `conf/sidecar.yaml` with what they affect (#386 r4154300234; #397
  r4432682336) and in [U]; renames and changed defaults go in [N] "Upgrading" (CASSSIDECAR-407, 461).
- Features that persist state require `sidecar.schema.is_enabled: true`; fail or warn loudly when not (#397
  r4432682336; `CassandraOperationsModule#warnIfLowReplicationFactor`).

### 4.6 Sidecar schema tables (`server/.../db/schema/`)
- Tables extend `TableSchema` (`server-common/.../db/schema/AbstractSchema.java`). Creation is
  `CREATE TABLE IF NOT EXISTS` and runs only when the table is absent, so editing the column list of an existing
  table changes nothing on deployed clusters while new prepared statements expect the new columns. The project
  adds a new versioned table instead (`restore_job_v6` then `restore_job_v7` in `RestoreJobsSchema`) and documents
  it in [N] "Upgrading", including what operators must pause during the upgrade (CASSSIDECAR-415, 463).
  **(the reason is inferred from `AbstractSchema`)**
- Statements are prepared at `LOCAL_QUORUM` (`AbstractSchema#prepare`); coordination state is unavailable when
  replicas are down, so RF below 3 is warned about (`CassandraOperationsModule`; #397 r4432682336).
- Schema creation that must happen once implements `ExecuteOnClusterLeaseholderOnly`.
- Several Sidecars of different versions may read the same tables during a rolling upgrade. **(inferred)**

### 4.7 Security and authorization
- When `access_control.enabled` is true, a global `ChainAuthHandler` authenticates every route (mTLS via
  `MutualTlsAuthenticationHandlerFactory`, JWT via `JwtAuthenticationHandlerFactory`). `modules/AuthModule.java`
  `chainAuthHandler`. Default is `enabled: false`. `conf/sidecar.yaml`.
- Routes built with `RouteBuilder.Factory#builderForRoute()` need a handler implementing `AccessProtected` that
  returns its `requiredAuthorizations()`, usually from `acl/authorization/BasicPermissions`
  (`DOMAIN:ACTION` with a cluster, keyspace, table or operation scope). `builderForUnauthorizedRoute()` is for
  health, OpenAPI and similar, and needs a comment explaining why (see `cassandraNodeSettings` in
  `CassandraOperationsModule`). `RouteBuilder#requiredAuthorization` throws `ConfigurationException` for a
  protected route without authorizations, but only when access control is enabled, so the default test setup does
  not catch it. `routes/RouteBuilder.java` `build()`. **(the gap is inferred)**
- Input validation: validate fail-fast with 400 and guard against command injection; use
  `CassandraInputValidator` for keyspace, table, snapshot and component names. [C] "RESTful API Design Guidelines";
  `utils/CassandraInputValidator.java`; `cassandra_input_validation` in `conf/sidecar.yaml`.
- Paths built from request input must stay inside the configured directory after resolving symlinks
  (`toRealPath()`), not only after rejecting `..` (CASSSIDECAR-479, PR #367 body).
- Error payloads: "Be careful what you add in the response payload of the `HttpException`". [C] "Failure
  Handling". `JsonErrorHandler` shows exception details only in Vert.x dev mode.
- Secrets: clear stored cloud credentials when a restore job completes, without a race that restores them (#384
  r4200170077). Do not log request or response bodies: Netty wire logging wrote cleartext bodies and DDL to logs
  (CASSSIDECAR-496, PR #381 body). Passwords and tokens in `sidecar.yaml` can come from files
  (`driver_parameters.auth_provider`, CASSSIDECAR-407).
- Report vulnerabilities privately to security@apache.org, not in PRs. [SEC].

### 4.8 Jobs and periodic tasks
- New long-running operations extend `OperationalJob` and implement `hasConflict` and `operationType`; submit
  through `OperationalJobManager#trySubmitJob`. [C]; `job/OperationalJob.java`; `handlers/NodeDrainHandler.java`.
- Reviewers trace job state across crash, retry exhaustion and restart: a status write that fails must not leave
  a record that says CREATED or RUNNING forever (#359 r3554025176, review 4665758157; #397 r4432458967,
  r4432482602); removal from the live map comes after the terminal write (#359 r3405716074); a timeout must not
  write FAILED while the job still runs (#397 r4543831190); in-memory per-operation state must be pruned (#397
  r4544001306); one failing item in a loop must not skip the rest (#397 r4432643108, r4412071907).
- Initialisation that can throw in a periodic task must not prevent rescheduling (#397 r4399495332).

### 4.9 Error handling and logging
- Handlers extend `AbstractHandler<T>`: `extractParamsOrThrow` then `handleInternal`; failures go through
  `processFailure`, which logs 4xx at warn and 5xx at error and calls `context.fail(HttpException)`. Map new
  exception types in `determineHttpException` or override `processFailure` (#367 r3882768938).
- Exceptions thrown on paths the caller does not handle (for example `Preconditions` throwing
  `IllegalStateException`) are findings (#360 r3436894747).
- Log level must fit: a mode the operator chose explicitly is info, not warn (#389 r4195249805); an unexpected
  state needs at least warn (#397 r4399619492). Messages are short and do not repeat request context the caller
  already has (#366 r3448034693).

### 4.10 Metrics
- Metrics are Dropwizard, created through `NamedMetric.builder(...).withDomain(...).withName(...)` under a domain
  such as `SERVER_PREFIX + ".Coordination"`, grouped in `metrics/server/*Metrics` and
  `metrics/instance/*Metrics`, and filtered by `metrics.include/exclude`. `metrics/NamedMetric.java`,
  `metrics/server/CoordinationMetrics.java`, `metrics/MetricRegistryFactory.java`.
- Dead or dropped metrics and duplicate stats interfaces were a fix of their own (CASSSIDECAR-489). Metric names
  are what operators' dashboards use, so a rename is user visible. **(inferred)**

---

## Lens notes

### cassandra-standards
- API change without a version: a removed or renamed field, a changed field type, a removed operation, or a
  changed default field under an existing `/api/vN` path; the fix is a new `ApiEndpointsV(N+1)` route and DTO
  with the old one marked `@Deprecated`. [C] "API Lifecycle".
- API shape against [C]: verb in a resource URL, `GET` that mutates, non-idempotent `PUT`, `200` for async work
  instead of `202`, missing `409` for a conflicting job, unbounded list responses, internal names or filesystem
  paths in URLs or payloads, Cassandra-version-specific endpoints.
- New route without `@Operation`/`@APIResponse`/`@Schema(implementation = RealResponse.class)` annotations, or
  placed in a module that does not own the feature. [OA]; [C] "Implementation Details".
- Long-running operation run inside a request handler instead of an `OperationalJob` returning a job id. [C]
  "Job Management".
- Guice: static utility or global state where an injected singleton fits; `@Singleton` on a class owned by a
  conditionally installed module; a conditional module that leaves bindings other modules need; a nullable
  collaborator where a disabled implementation fits. [G]; #367 r3539501130; #360 r3544181050.
- User surface not updated: new or changed setting missing from `conf/sidecar.yaml` comments or
  `docs/src/user.adoc`; new internal table, renamed key or changed default without a `NEWS.txt` "Upgrading" entry;
  CHANGES.txt line under an already released version or not naming every fix. #376 r3786164134; #374
  r3753934222.
- Scope: unrelated refactors or behaviour changes in another feature (often CDC) mixed into the patch. #390
  review 5609744981; #366 r3448026677.
- Security (self-gating). First decide whether the diff touches security surface: routes and `RouteBuilder`,
  `AccessProtected`/`BasicPermissions`, `acl/`, `vertx-auth-mtls/`, `AuthModule`, `access_control` or `ssl`
  config, TLS keystores, file paths built from request input, handlers that stream or list files, credentials
  (`StorageCredentials`, `RestoreJobSecrets`, `driver_parameters`, JWT or keystore passwords), logging of requests
  or responses, or error payloads. If none, write "no security surface touched" and report no security findings.
  If it does, check: a new protected route has an `AccessProtected` handler with a permission of the right scope
  (table for table data, operation for node operations); `builderForUnauthorizedRoute()` is used only for health
  and docs-like routes, with a comment; no new route bypasses the global auth chain; path parameters pass
  `CassandraInputValidator` before use and resolved paths stay inside the base directory after `toRealPath()`;
  secrets are redacted in `toString()` (the handler logs `request={}`), absent from responses, error messages and
  logs, and cleared when no longer needed; secure defaults are kept. Findings use rules such as
  `security-authz-bypass`, `security-secret-exposure`, `security-path-traversal`.

### cass-logic-boundary
- Path, query and body parameters used before `CassandraInputValidator` or the handler's own validation in
  `extractParamsOrThrow`; invalid input reaching Cassandra or the filesystem instead of a 400. [C] "RESTful API
  Design Guidelines".
- Keyspace and table name case: mixing raw and quoted names (`quoteIfNecessary` versus `MetadataUtils.keyspace`)
  so mixed-case quoted names fail on one path. #365 r3429964906, review 4539350474.
- Null from optional request fields, empty YAML values (`key:` deserialises to null and skips setter checks), or a
  deprecated getter whose default was removed. #397 r4544046235; #390 r4275467449.
- Wrong exception to status mapping in `AbstractHandler#determineHttpException`: a client error returned as 500,
  `IllegalArgumentException` surfacing as 400 when it is a server bug, or a 404 turned into 400. #367 r3539598358.
- Duration and size units: `MillisecondBoundConfiguration` versus `SecondBoundConfiguration` versus
  `MinuteBoundConfiguration`, `toMillis()` versus `toSeconds()`, and non-positive overrides that make `setTimer`
  throw. #397 r4544086891.
- Enum and string mismatches between live objects and stored records (`name()` lowercase on a job versus
  `OperationType.name()` uppercase on `OperationalJobRecord`). #359 r3405586945.
- State machine conditions in restore and job code (`RestoreJob`, `RestoreJobDiscoverer`): inverted or
  incomplete status predicates when a new mode such as fast-forward is added. #376 r3802617419.
- Regex validators and parsers (`GossipInfoParser`, `allowed_chars_for_*`): bracketed IPv6, anchors, and patterns
  that accept spaces or injected keys. #388; #369 r3570734120.
- Merge and overlay semantics with nulls and keys absent from the base (`ConfigUtils`,
  `ConfigurationOverlaySnapshot`). #358 r3374629589, r3365194863.

### cass-concurrency-lifecycle
- Blocking call on an event loop thread: JMX, CQL `session.execute`, file I/O, `Future.result()` waits or sleeps
  inside a `Handler<RoutingContext>`, an event-bus consumer or a Vert.x callback, instead of
  `executorPools.service()`/`internal()`. [C] "Thread Pool Model"; CASSSIDECAR-452.
- Request state (`RoutingContext`, request, response) touched from a callback of a non-Vert.x future (Caffeine
  `Future` values, AWS SDK, `CompletableFuture`) without `originCtx.runOnContext`, in every branch. [VT].
- `executeBlocking` with the default `ordered=true` for independent tasks, which serialises them and lets one hang
  block the rest. #397 r4543978652.
- `setPeriodic` where runs must not overlap; use `PeriodicTask` with `PeriodicTaskExecutor`. A `PeriodicTask`
  whose setup throws before it reschedules. [C] "Advanced Periodic Task Scheduling"; #397 r4399495332.
- I/O or remote calls inside `ConcurrentHashMap.compute`, `synchronized` blocks or other locks. #359 r3405554604.
- Check-then-act on caches that a concurrent refresh can clear or replace (`SchemaCache` `compareAndSet` after an
  invalidation; clearing the live cache while building a new one). #390 r4275314687, r4275479399.
- Job lifecycle order: removal from the live job map before the terminal status is persisted; lock
  (`trySetActive`/`clearActive`) not released on conflict or failure; FAILED written on timeout while the job keeps
  running after `cancel()`. #359 r3405716074; #360 r3406169010; #397 r4543831190.
- Lost status after retry exhaustion or a restart, leaving durable records CREATED or RUNNING forever and the
  operation lock held. #359 r3554025176; #397 r4432458967.
- Per-operation maps and handles never pruned on Sidecars that do not finalise; caches without size bounds.
  #397 r4544001306; #359 r3405744447.
- Race between two requests that both pass a status check (secrets nulled at completion, then restored by a
  concurrent update). #384 r4200170077.

### cass-persistence-compat
- REST compatibility: a removed, renamed or retyped field in a `client-common` `request/`, `response/` or `data/`
  class, or a changed format of a string field (schema text, status words like `"?"` to `"Unknown"`), served under
  the same `/api/vN`. [C] "API Lifecycle"; #390 r4275424502.
- New request payload class without `@JsonIgnoreProperties(ignoreUnknown = true)`, or a new client relying on a
  response field older servers do not send. #376 r3801685019.
- Java 8 client break: Java 9+ APIs (`List.of`, `Optional.isEmpty`, `String.isBlank`, `var`) or Java 11-only
  dependencies in `client`, `client-common` or `vertx-client`. `sourceCompatibility = 1.8` does not reject API
  calls; only the CI Java 8 job does. `client-common/build.gradle`; [CI] `unit-tests-java8`.
- Sidecar schema: a column added to, or removed from, an existing `createSchemaStatement()` in `db/schema/*Schema`
  (never applied to deployed tables because of `CREATE TABLE IF NOT EXISTS` and the existence check) instead of a
  new versioned table such as `restore_job_v8`; no `NEWS.txt` upgrade note on in-flight state; old and new
  Sidecars reading different tables during a rolling upgrade. `AbstractSchema#initializeInternal`; [N] `0.5`.
- Config compatibility: renamed or removed `@JsonProperty` key without keeping the old one as `@Deprecated`
  (unknown keys are ignored silently, so old files fall back to defaults); a changed default that alters behaviour
  on upgrade. `SidecarConfigurationImpl` `FAIL_ON_UNKNOWN_PROPERTIES=false`; [N] CASSSIDECAR-407, 461.
- Adapters: a JMX or CQL call added to `adapters-base` that older supported Cassandra versions (4.0, 4.1) lack,
  without an override in a `CassandraNN*` adapter or an `OperationUnavailableException` (503). [C] "Cassandra
  Adapters".
- IO and file safety: upload, staging and import paths (`SSTableUploadHandler`, `SSTableImporter`,
  live migration file routes) that leave partial files, skip checksum verification, or resolve outside the base
  directory.
- Observability: a failure logged at the wrong level (expected 4xx at error, an unexpected state at debug); request
  or response bodies, credentials or tokens in logs (Netty wire logging, `request={}` with an unredacted
  `toString()`); metrics created outside `NamedMetric` and the `metrics/` groups, registered twice, never
  incremented on error paths, or renamed. #381 body; #375; [C] "Failure Handling".

### cass-completeness-symmetry
- New endpoint missing a piece of its set: `ApiEndpointsV*` constant, DTO in `client-common`, handler,
  `@ProvidesIntoMap` route in the owning module, `VertxRouteMapKeys` key, `BasicPermissions` entry and
  `AccessProtected` handler, OpenAPI annotations, and where clients use it a `SidecarClient` method. Compare with
  CASSSIDECAR-272 (`f41b3ca8`).
- Adapter change made in one adapter only: `adapters-base` changed but `Cassandra41*`/`Cassandra50*` overrides of
  the same operation not, or `ICassandraAdapter` extended without `CassandraAdapterDelegate` wiring.
- Config setting added to the `*Impl` class but not to the interface, `conf/sidecar.yaml`, `docs/src/user.adoc`,
  the test YAMLs under `server/src/test/resources/config/`, or startup validation of options that depend on it.
  #397 r4399579811, r4543730099.
- Sibling paths left unfixed: the same name handling, validation or redaction fixed in one handler but not in the
  others that take the same input (snapshot list versus clear, upload versus import, restore discoverer versus
  processor). #365 review 4539350474; #366 r3448035859.
- Counterparts: `trySetActive` without `clearActive`, `persistJob` without the terminal update, `toJson` field
  without `fromJson` (`hash`), add without remove. #360 r3436977162; #358 r3374738069.
- New table schema not registered through the schema multibinding or `SidecarSchema`, or a new versioned table
  while accessors and `CqlLiterals` still point at the old name.
- Deprecated getter, route or key whose fallback no longer works, or callers still on the deprecated path.
  #390 r4275467449.
- Refactor aftermath: stale javadoc, unused constants and helpers (`UNKNOWN_SHORT`), code only used by tests, and
  classes added for a "future PR" with no caller. #391 r4212724466; #392 r4312812327; #358 r3492845685.

### cass-test-regime
- Handler or route logic, request parsing, status codes, error mapping: unit test in `server/src/test/java/`
  using `Modules.override(SidecarModules.all()).with(TestModule)`, `VertxExtension` and `WebClient` with mocked
  `CassandraAdapterDelegate` (pattern: `handlers/NodeDrainHandlerTest.java`).
- Behaviour that needs real Cassandra (JMX results, CQL, schema, sidecar tables, auth against `system_auth`):
  integration test with `@CassandraIntegrationTest` under `server/src/test/integration/` or
  `SharedClusterSidecarIntegrationTestBase` under `integration-tests/src/integrationTest/`. A fix that only adds a
  mocked unit test for such behaviour is a finding.
- Version-dependent behaviour (adapters, JMX, `system_views`): a test run by the `@CassandraIntegrationTest`
  template, which iterates `TestVersionSupplier` versions; `SharedClusterIntegrationTestBase` uses only the first
  version and does not cover the matrix. [C] "testing and validation must cover the trunk and all supported
  versions".
- Multi-node, topology (joining, leaving, moving, replacement), multi-DC or repair: heavyweight integration test
  tagged `@Tag("heavy")`, using the ByteBuddy helpers for in-flight topology changes.
- S3 or other external services: container test in `server/src/test/containerTest/` only when testcontainers are
  needed; otherwise unit or integration. [T] "Container Tests".
- Config parsing and validation: a test that loads a YAML from `server/src/test/resources/config/`, not only the
  builder, including empty and invalid values. #386 r4153903363.
- Java 8 client code: unit test in `client/src/test/java/` or `client-common/src/test/java/` (MockWebServer),
  which the CI Java 8 job runs.
- Authorization: a protected route needs a test with access control enabled (for example extending
  `RoleBasedAuthorizationIntegrationTest` or `RouteBuilderTest`), because the default setup skips the
  `requiredAuthorizations` check.
- Regression test that cannot fail: mocks return the value that hides the bug, or the test never reaches the
  changed branch. #390 r4275268029.
- Async and retry tests: `Thread.sleep` or a single `verify` racing retries instead of
  `AssertionUtils.loopAssert`/`waitUntil`; shared-cluster tests that change cluster state other tests depend on;
  static state that leaks inside a class run with `forkEvery = 1`. #392 r4383662442; [T] "Test Isolation Issues".
