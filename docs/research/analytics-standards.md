# Apache Cassandra Analytics contribution and review standards (as of 2026-11-20)

Research input for the cassandra-pr-review tool, used as trusted input by the review lenses for
apache/cassandra-analytics PRs. Every rule cites a primary source. Repo paths refer to
`apache/cassandra-analytics` trunk at commit `55b6e4660150b0819dec72634a4d6af632f3e18a`
(2026-11-19, "CASSANALYTICS-209: Preserve empty tuple and UDT field values on read"). Review
evidence comes from merged and closed PRs #205 to #261, read through the GitHub API. Where sources
conflict or are stale, the note says so. Anything not read directly is marked *(inferred)*.

Abbreviations: **[DR]** = `DEV-README.md`; **[RM]** = `README.md`; **[AG]** = `AGENTS.md`;
**[SEC]** = `SECURITY.md`; **[BG]** = root `build.gradle`; **[GP]** = `gradle.properties`;
**[CS]** = `config/checkstyle/checkstyle.xml`; **[SUP]** = `config/checkstyle/suppressions.xml`;
**[IDE]** = `ide/idea/codeStyleSettings.xml`; **[GHA]** = `.github/workflows/test.yaml`;
**[CCI]** = `.circleci/config.yml`; **[ASF]** = `.asf.yaml`; **[CH]** = `CHANGES.txt`;
**[NW]** = `NEWS.txt`; **[UG]** = `docs/src/user.adoc`; **[CV]** =
`cassandra-analytics-common/src/main/java/org/apache/cassandra/bridge/CassandraVersion.java`;
**[BSC]** = `cassandra-analytics-core/src/main/java/org/apache/cassandra/spark/bulkwriter/BulkSparkConf.java`;
**[GOV]** = https://cwiki.apache.org/confluence/display/CASSANDRA/Cassandra+Project+Governance;
**PR#n** = `https://github.com/apache/cassandra-analytics/pull/n`, and **PR#n rX** is the review
comment `https://github.com/apache/cassandra-analytics/pull/n#discussion_rX`; **PR#n iX** is the
conversation comment `#issuecomment-X`.

The deterministic checks of cpr (JIRA key, Fix Version, commit credit line, CHANGES.txt entry,
test presence, checkstyle, CI check-runs, touched compatibility surfaces) are described in
`docs/report/subprojects/*.md`. The lenses must not repeat them. This file covers what needs
judgement.

---

## 0. Things a reviewer tool must not get wrong

- **One long-lived branch.** Work lands on `trunk`. There are no release branches and no
  backports. A feature branch, `mutation-tracking-support`, takes mutation tracking work
  (PR#214, #238, #244, #247, #250 target it). Source: `git branch -r`; PR base refs.
- **PRs are merged on GitHub.** Squash and rebase buttons are enabled, merge commits are not
  ([ASF] `enabled_merge_buttons`). Recent PRs show `merged_at` set. A committer may still commit
  "the legacy way" when the PR misses something, for example a CHANGES.txt line (PR#205
  i4438006200).
- **Default build is Spark 4, Scala 2.13, JDK 17.** [GP] sets `scala=2.13`, `spark=4`,
  `analyticsJDKLevel=17`, and [NW] 0.5 "Upgrading" says so. Spark 3 is still supported.
  [DR] still says "Cassandra Analytics will build for Spark 3 and Scala 2.12 by default" and
  [RM] says "Spark 3 (Scala 2.12)" and "Cassandra 4.x and 5.0". Both are stale.
- **Supported Cassandra versions:** 4.0 (4.0.17), 4.1 (4.1.4), 5.0 (5.0.7), 6.0 (6.0-alpha2).
  Sources: [BG] `cassandraFullVersionMap`; [GP]; `scripts/build-dtest-jars.sh`
  `CANDIDATE_BRANCHES`. `cassandra-three-zero/` holds only a `build.gradle` and is not in
  `settings.gradle`; 3.0 is an enum value in [CV] with no bridge.
- **All modules compile with `options.release = 11`** unless the label is 1.8 ([BG], `tasks.withType(JavaCompile)`).
  Main code may not use JDK 12+ APIs even in the JDK 17 build.
- **`scripts/build-dependencies.sh` now only builds the dtest jars.** [DR] says it also builds
  the Sidecar libraries. The Sidecar client is in-tree (`analytics-sidecar-*`) and Sidecar is
  taken as `sidecarVersion=0.4.0` from [GP]. [DR] is stale on this point.
- **The checkstyle config bans none of Cassandra's APIs.** There is no `ExecutorFactory`,
  `Clock.Global`, `CassandraRelevantProperties`, `JVMStabilityInspector`, `File`, or
  `CompletableFuture` rule ([CS]). Trunk main code uses `System.getProperty` ([CV]) and JDK
  futures. Do not apply those Cassandra rules to analytics PRs.
- **Agent guidance in the repo is only a security pointer.** [AG] points to [SEC], which defers
  to the Cassandra security model at
  `apache/cassandra:doc/modules/cassandra/pages/reference/security-model.adoc`.

---

## 1. Workflow

### 1.1 JIRA ticket
- Issues are tracked in the CASSANALYTICS JIRA project. [RM] "Contributing".
- Design discussion happens on ASF Slack `#cassandra-dev` and in JIRA. [RM] "Contributing".
- An upstream Cassandra bug that analytics works around gets its own CASSANDRA ticket, named in a
  comment at the workaround. PR#211 r3334550055 (reviewer asked; author filed CASSANDRA-21423 and
  added it to the FIXME comments).
- A fix to existing trunk code found while working on a feature-branch PR is fixed on trunk first,
  under its own ticket. PR#238 r4107623057 ("can you fix it in trunk first with a separate JIRA?");
  CASSANALYTICS-202 then landed on trunk as PR#249.

### 1.2 PR and commit conventions
- PR title and squash subject: `CASSANALYTICS-N: <summary>`; GitHub appends ` (#PR)`. Source:
  `git log origin/trunk` (for example `a982087`, `894dcb2`).
- Commit body: `Patch by <author>; Reviewed by <reviewer>[, <reviewer>] for CASSANALYTICS-N`.
  Source: `git log origin/trunk` (`fff3a6d`, `a982087`, `403c492`). Older style
  `patch by ...; reviewed by ...` also appears (`5e5f0ad`).
- AI assistance is recorded with an `Assisted-by:` trailer, for example `Assisted-by: Codex:GPT-6`
  in `5e5f0ad`. The form follows apache/cassandra [AG] *(inferred: analytics has no rule of its own)*.
- Small follow-ups by committers are "ninja" commits (`5ebb4a0`, `7ebb63b`, `827db21`).
- Unrelated edits in a PR get pushed back. PR#212 r3314519907 and r3314521127 ("Unrelated change;
  can we revert it?").
- Contributors post a CircleCI link from their fork as CI evidence, besides the GitHub Actions run.
  PR#255 i6926021163 ("please post Circle CI link"); PR#224 i5052657621; PR#227 i5113338963.

### 1.3 CHANGES.txt
- Format ` * <summary> (CASSANALYTICS-N)` at the top of the current version block (`0.5.0`). [CH].
- **Only user-facing changes.** Commit `7ebb63b` "ninja: remove non user-facing change from
  CHANGES.txt" removed the test-only CASSANALYTICS-67 line.
- Reviewers ask for the entry before approving. PR#239 review ("Please update the `CHANGES.txt`"),
  PR#234 review, PR#212 review.

### 1.4 NEWS.txt
- Each version has `Upgrading` and `New features` sections. [NW] 0.5.
- The 0.5 `Upgrading` section lists exactly the classes of change that need a NEWS entry:
  a removed option (`spark.cassandra_analytics.cassandra.version`, "silently ignored if still set");
  a changed public interface for custom implementations (`ClusterInfo.getBridgeVersion()`,
  `SchemaSupplier.getTables()`, `StorageAuth` for `StorageTransportExtension`); a fallback switch
  (`spark.cassandra_analytics.bridge.disable_sstable_version_based`); a persisted-state format
  change (`CdcState.ReplicaCountSerializer`, CASSANALYTICS-184); and Avro record name changes that
  consumers must regenerate or re-register (CASSANALYTICS-204). [NW].

### 1.5 Votes
- Analytics is part of the Apache Cassandra project, so [GOV] applies *(inferred from [SEC] and the
  shared PMC)*: code needs two committer +1s (author can be one), test-only changes one non-author
  committer +1, and CI results before commit.
- In practice the +1 is a GitHub approval, often with the text "+1" (PR#260, #249, #238), and the
  reviewers are named in the commit body (§1.2).

### 1.6 Feature work
- An incomplete feature either goes to a feature branch or ships behind a flag that is off by
  default. PR#214 r3364964346 and r3365199834 (skoppu22); the author moved the PR to the feature
  branch (r3422987590).
- Feature-branch PRs still get full review, but "Merge to feature branch is fine" is an accepted
  approval for staged work (PR#214 review).

---

## 2. Code style beyond checkstyle

### 2.1 What the build checks
- `codeCheckTasks` runs every module's Checkstyle and RAT, ordered before tests. [BG].
- CI runs `./gradlew codeCheckTasks` in both build jobs (JDK 11, JDK 17). [GHA].
- Checkstyle rules: Apache license header (`RegexpHeader`), line length 160, no tabs, no trailing
  spaces, braces on a new line for classes, methods and control statements but end-of-line for
  lambdas (`LeftCurly`), `NeedBraces`, no star imports, unused imports, method length 120,
  `MissingSwitchDefault`, `InnerAssignment`, `EqualsHashCode`, `HideUtilityClassConstructor`. [CS].
- Suppressed for all files: Javadoc package, method and variable checks, `HiddenField`,
  `MagicNumber`, `DesignForExtension`, `TodoComment`. [SUP]. In-line suppression is
  `// CHECKSTYLE IGNORE: <reason>` ([CS] `SuppressWithNearbyCommentFilter`).
- `githooks/pre-push` runs checkstyle for Scala 2.12 and 2.13 with Spark 3 only (optional hook).

### 2.2 Not machine-checked
- **Import order** comes from [IDE] (`./gradlew copyCodeStyle`, [DR] "IntelliJ"): `java`, `javax`;
  blank; `com.google.common`, `org.apache.log4j`, `org.apache.commons`, `org.junit`, `org.slf4j`;
  blank; everything else; blank; static imports. Checkstyle has no `ImportOrder` module ([CS]).
- **Names say intent.** PR#224 r3624641307 (rename `cdcEnabledTables`), r3624664332
  (`unregisterTable` to `unregisterNonCdcTables`); PR#244 r4364748206; PR#239 r3909522280
  (`getOrPrepareSSTable`). Avoid double negatives in boolean names: PR#241 r3986502494.
- **No stale or misplaced comments.** PR#239 r3909473859; PR#214 r3364906855; PR#205 r3209978556
  ("The OSS default <- this is the OSS project"); PR#244 r4378767920 (no test notes in production
  comments).
- **Delete dead code the change leaves behind.** PR#239 r3909482943 and r3909491040
  (`StreamSession.isFileStreamed`).
- **Reuse what exists.** PR#214 r3365186029 (use `writerContext.bridge()`); PR#224 r3624440857
  (one helper instead of repeated filter streams). Put a shared fix in the oldest bridge module and
  drop the override in newer ones: PR#236 r3928194672, r3928239204, r3928280213.
- **Keep shared constants immutable.** PR#239 r3909511024 (`EMPTY` was mutable).
- **Prefer builders over long constructor overloads** for new model classes. PR#227 r3670991149 (yifan-c on
  `CqlTable`, "constructor overloads are error prone"); PR#238 r4031398709.
- **ASCII only in main-code comments and javadoc.** CASSANALYTICS-140 (PR#210, merged) cleaned them up.
- **Code copied from Sidecar is marked.** [SUP] (`RestoreJobConstants.java is copied from Cassandra
  Sidecar`); the client modules exist to avoid a circular dependency (`settings.gradle` comment).
  Reviewers dislike new duplication with Sidecar (PR#212 review).

---

## 3. Testing regime

### 3.1 Suites and where they live
| Suite | Where | How it runs |
|---|---|---|
| Unit, per module | `<module>/src/test/` | `./gradlew check` (CI excludes the integration module with `-x cassandra-analytics-integration-tests:test`). [GHA] `unit-test`. |
| Core non-Sequential | `cassandra-analytics-core/src/test/` | `test`, `maxParallelForks=3`, `forkEvery=1` (fresh JVM per class). `cassandra-analytics-core/build.gradle`. |
| Core Sequential | tests tagged `@Tag("Sequential")` | `testSequential`, one fork, "to prevent OOM errors". Same file. |
| Bridge BTI | `cassandra-five-zero-bridge` tests | `testBti` with `cassandra.analytics.bridges.sstable_format=bti`, wired into `check`. `cassandra-five-zero-bridge/build.gradle`. |
| Integration | `cassandra-analytics-integration-tests/src/test/` | In-JVM dtest clusters plus in-process Sidecar; base class `SharedClusterSparkIntegrationTestBase`; one JVM per class. `cassandra-analytics-integration-tests/build.gradle`. |
| Integration framework | `cassandra-analytics-integration-framework` | `SharedClusterIntegrationTestBase`, `ClusterBuilderConfiguration`, `TestVersionSupplier`, `MtlsTestHelper`. |
| Container | `integration-tests/.../testcontainer/` | S3-compatible transport with Testcontainers; skipped with `skipContainerTest=true`. |

- Per-version Gradle tasks exist for local runs: `testCassandra40`, `testCassandra41`,
  `testCassandra50`, `testCassandra60` in core and integration modules. Local integration runs
  default to 5.0 only. Integration `build.gradle` comment.
- Version-parameterised unit tests use `@MethodSource("org.apache.cassandra.bridge.VersionRunner#bridges")`
  (or `#versions`), so they run once per implemented bridge
  (`cassandra-analytics-core/src/test/java/org/apache/cassandra/bridge/VersionRunner.java`;
  `spark/endtoend/DataTypeTests.java`). CI narrows this to one version per job through
  `CASSANDRA_VERSION` and the `implemented_versions` system property. [BG]
  `applyCassandraVersionFilter`.
- Property-based tests use QuickTheories (`qt().forAll(TestUtils.cql3Type(bridge))`). `DataTypeTests`.
- Core coverage gate: JaCoCo minimum 0.5 in `check`. `cassandra-analytics-core/build.gradle`.

### 3.2 Dependencies
- Integration tests need shaded in-JVM dtest jars built from Cassandra:
  `CASSANDRA_USE_JDK11=true ./scripts/build-dependencies.sh`, or `BRANCHES=...` to limit versions.
  [DR] "Dependencies"; `scripts/build-dtest-jars.sh`.
- Multi-node tests need loopback aliases 127.0.0.2 to .20 and `localhostN` host names. [DR]
  "Running Integration Tests".
- Topology tests (`expansion`, `shrink`, `replacement`, `movement`) pause a change with ByteBuddy
  through `TopologyChangeBBUtils`; hooks differ for 6.0 TCM. [DR] "Topology-change tests".

### 3.3 The CI matrix ([GHA]; [CCI] mirrors it)
- Unit: Scala 2.13/BTI/C5.0/Spark 3/JDK 11; Scala 2.12/BIG/C4.1/Spark 3/JDK 11;
  Scala 2.12/BIG/C4.0/Spark 3/JDK 11; Scala 2.13/BTI/C5.0/Spark 4/JDK 17.
- Integration: six configs (C6.0-alpha2, C5.0.7, C4.1.4, C4.0.17 on Spark 3; C6.0-alpha2 and C5.0.7
  on Spark 4), each sharded five ways by a SHA-seeded shuffle of test classes.
- Classes that cannot run on 4.0 are listed in `C40_EXCLUSIONS` in [GHA].
- A Spark/Scala/JDK combination builds only if `profiles/scala-<s>-spark-<n>-jdk-<j>.gradle`
  exists ([BG]); today: 2.12/3/11, 2.13/3/11, 2.13/4/17.

### 3.4 What reviewers expect
- A test for each behaviour change, including option parsing. PR#212 r3314476232 ("Add a test for this?").
- Removed tests need a reason. PR#212 r3314507146, r3314516827.
- Tests must exercise the changed code, not a mock that replaces it. PR#214 r3365153253.
- New bridge classes get tests like the previous version's. PR#236 r3983257646 (copy 5.0
  `BtiReaderUtilsTest` for 6.0), r3983522407 (force cache eviction and check the ref is released).
- Version parsing changes get cases for each version pattern. PR#236 r3982619730.
- A test skipped permanently on a version needs a rewrite or a follow-up ticket. PR#236 r3963484371.
- Retry loops in tests must catch the exception type actually thrown. PR#205 r3210248533.
- Probabilistic outcomes (bloom filter false positives) are documented in the test. PR#211 r3320616042.
- A behaviour change that breaks no existing test is a warning sign. PR#241 r3986465776.

---

## 4. Review criteria

### 4.1 Bridge consistency across Cassandra versions
- Each major has five modules: shaded library, bridge, types, Avro converter, Spark SQL converter.
  [DR] "Bridge Modules".
- Sources copy forward four-zero to five-zero to six-zero. To change a component for one version,
  copy the file with the same name into the newer module. Inherited classes are never recompiled,
  so a Cassandra API change between majors compiles and fails at runtime with
  `NoSuchMethodError`. [DR] "Bridge Modules"; `cassandra-five-zero-bridge/build.gradle` (`jar` copies
  `implCassV4` classes with `DuplicatesStrategy.EXCLUDE`).
- Core code reaches Cassandra only through `CassandraBridge`, `CdcBridge` and the types API. Bridge
  jars are embedded under `bridges/` in the core jar and loaded in isolated classloaders by
  `CassandraBridgeFactory` (`cassandra-analytics-core/build.gradle` `into('bridges')`;
  `PostDelegationClassLoader`).
- Version-specific objects are serialized through the bridge (`bridge.javaSerialize`,
  `CassandraDataLayer`).
- Version lists must stay in sync: [BG] `cassandraVersionEnumMap` and `cassandraFullVersionMap`,
  [CV] defaults, and `build-dtest-jars.sh`. [CV] header comment; [BG] comment. The CI matrix is
  part of that set: PR#246 review 5290097883 asked for 6.0 entries in [GHA].

### 4.2 Spark and Scala compatibility matrix
- Spark-specific code lives in `src/main/spark3` and `src/main/spark4` (core) and
  `src/main/scala-<scala>-spark-<n>` (spark converter); [BG] adds them by label.
- Jackson versions are forced to match Spark's ([BG] `resolutionStrategy`), set per profile.
- Avro stays on 1.11.x and Vert.x on 4.5.1 for older-runtime reasons ([GP] comments).
- Option names must start with `spark.` and must not start with `spark.cassandra`, to avoid the
  Spark Cassandra Connector. [BSC] comment on `SETTING_PREFIX = "spark.cassandra_analytics."`.

### 4.3 CDC and Avro schema evolution
- Base schemas: `cassandra-analytics-cdc-codec/src/main/resources/cdc_bytes.avsc` and
  `cdc_generic_record.avsc`; table schemas come from `CqlToAvroSchemaConverter` per version
  (`cassandra-*-avro-converter`). Record version is `AvroConstants.CURRENT_VERSION = "3"`.
- Record full names and namespaces are a contract with consumers. CASSANALYTICS-204 changed them
  and NEWS says consumers "must be regenerated or re-registered". [NW] 0.5.
- Generated names must not depend on other columns or collide. PR#255 i6782201339 (suffixes
  `a_b2`/`a_b3` shift when a column is dropped; `my-ks` and `my_ks` collide).
- One naming convention (CQL or Avro) across all key and field lists. PR#255 r4487273256,
  r4531887649.
- Schema changes while running: a field added by `ALTER TYPE` before the CDC schema refresh.
  PR#256 r4468972136. Tables that lose CDC must still publish a schema update. PR#224 r3624426846.
- Namespace mistakes in `.avsc` files were fixed as bugs (CASSANALYTICS-166). [CH] 0.4.0.

### 4.4 Persisted and wire formats
- Kryo serializers sit next to their class (`public static class Serializer`) and are registered in
  `KryoRegister` (core) or `CdcKryoRegister` (CDC). Java serialization (`writeObject`/`readObject`)
  exists in parallel for many classes (`CassandraRing`, `CassandraDataLayer`).
- Broadcast objects travel driver to executor in one job, so both sides load the same jar. A
  reviewer still asked for a version byte when a Kryo format changed; the author added it.
  PR#238 r4078376579 and reply.
- `CdcState` is persisted between runs (`StatePersister`, `SidecarStatePersister`). Its format change
  in 0.5 made old state unreadable and needed a NEWS entry. [NW] 0.5; `CdcState.java` comment at
  `ReplicaCountSerializer`.
- Narrow types in serializers overflow: CASSANALYTICS-184 (`short` map size). [CH].

### 4.5 Bulk reader and writer options
- Writer options: enum `WriterOptions`, parsed in [BSC]. Reader options: string keys in
  `ClientConfig`. Job-level settings: `spark.cassandra_analytics.*` constants in [BSC].
- Keys are case-insensitive: `MapUtils.lowerCaseKey` lowercases with `Locale.ROOT` and the
  `MapUtils.get*` helpers use it (`cassandra-analytics-common/.../spark/utils/MapUtils.java`).
- Renames keep the old name as `@Deprecated` and resolve both with `MapUtils.resolveDeprecated`
  (`SIDECAR_INSTANCES`, `SSTABLE_DATA_SIZE_IN_MB`). [BSC]; `WriterOptions.java`.
- Defaults are public constants (`DEFAULT_*` in [BSC]) and documented in [UG] tables. Some newer
  options (`SKIP_SECONDARY_INDEX_CHECK`, `bridge.disable_sstable_version_based`) are missing from
  [UG], so docs lag the code.
- Option interplay is logged and corrected: a `LOCAL_DC` with a non-local CL is dropped with a
  warning; `COORDINATED_WRITE_CONFIG` overrides contact points, port and DC. [BSC].

### 4.6 SSTable reading and writing through the bridges
- Bridge selection is by SSTable version: the writer picks the lowest version on the cluster so
  every node can import the output, and fails on incompatible sets.
  `cassandra-analytics-core/.../bridge/SSTableVersionAnalyzer.java`; [CV] `nativeSSTableVersions`,
  `lowestCompatibleVersionNumber`.
- 5.0 and 6.0 read and write both `big` and `bti`. [CV]; `BtiReaderUtils`, `BtiIndexReader`.
- Every component written must be consistent and complete. A component that cannot be rebuilt is
  deleted, not uploaded broken; the server rebuilds it. PR#211 r3327301498 and replies.
- Edge cases in readers are a recurring bug class: last unaligned chunk (CASSANALYTICS-147), big
  partitions in BTI (CASSANALYTICS-151, -156), empty tuple and UDT values (CASSANALYTICS-209),
  non-frozen UDTs with unset fields (CASSANALYTICS-217). [CH].

### 4.7 Consistency levels and token ranges
- Writer CL defaults to `EACH_QUORUM`. [BSC]; [UG].
- Reader and writer each have a `ConsistencyLevel`
  (`common/.../data/partitioner/ConsistencyLevel.java`, `core/.../bulkwriter/token/ConsistencyLevel.java`)
  and a `TokenPartitioner`; reviewers note the duplication (PR#234 r3901342348).
- Replica sets from Cassandra must be checked against the CL, not just for emptiness. PR#244 r4379235500.
- Ranges are open-closed; Guava and Sidecar reject wrap-around ranges. PR#244 r4383518372.
- Gaps in range coverage must be detected (CASSANALYTICS-180). Node replacement must not fail a job
  (CASSANALYTICS-175, `RingInstance` equality). [CH].
- Invalid replication settings throw, not parse leniently. PR#238 r4018343334.

### 4.8 Sidecar client use
- The bundled client (`analytics-sidecar-client`, `-common`, `-vertx-client`) has retry policies
  (`ExponentialBackoffRetryPolicy`, `OncePerInstanceRetryPolicy`, ...) and instance selection
  policies. Timeouts and retries come from [BSC] `sidecar.request.*` settings.
- Total timeouts across retries must be computed correctly (CASSANALYTICS-179). [CH].

### 4.9 Performance and memory on executors
- Heavy end-to-end tests run Sequential "to prevent OOM errors" (core `build.gradle`); executors
  hold sstable buffers (`BufferingInputStream`), caches (`SSTableCache`, `CassandraDataSourceHelper`)
  and writers.
- Avoid repeated work in hot or per-call paths: PR#238 r4039597244 (precompute in the constructor),
  PR#244 r4385532345, CASSANALYTICS-104 (redundant file system lookups). A silent fallback to a slow
  path is a bug (CASSANALYTICS-187, `FastByteOperations`). [CH].
- A failed Spark task retries at high cost, so prefer recoverable handling where output stays
  correct. PR#211 r3327301498.

### 4.10 Error handling, logging, metrics
- No swallowed exceptions without a reason in a comment. PR#211 r3320620135 and reply.
- Log levels match the situation: expected per-job conditions are not errors (PR#211 r3320569695);
  impossible states are errors (PR#244 r4392325332, PR#224 r3624455845); logs carry the context an
  operator needs (PR#224 r3624413279).
- Stats go through interfaces (`Stats`, `ICdcStats`, `SidecarCdcStats`, `KafkaStats`,
  `BufferingInputStreamStats`, `JobStatsPublisher`). A stats object dropped by a builder is a bug
  (CASSANALYTICS-191). [CH].
- Exception types for analytics live in `org.apache.cassandra.spark.exception`
  (`SidecarApiCallException`, `ConsistencyNotSatisfiedException`, `ImportFailedException`, ...).

---

## Lens notes

### cassandra-standards
- Scope: flag edits outside the ticket, especially in `cassandra-analytics-integration-tests` or
  unrelated modules, and ask for a revert or a separate ticket (PR#212 r3314521127).
- A partial feature on `trunk` without an off-by-default flag is a finding; it belongs on
  `mutation-tracking-support` or behind a flag (PR#214 r3364964346). A feature-branch PR that fixes
  existing trunk code should land that fix on trunk first under its own CASSANALYTICS ticket
  (PR#238 r4107623057).
- A workaround for a Cassandra server bug needs a CASSANDRA-N ticket named in the code comment
  (PR#211 r3334550055).
- NEWS.txt `Upgrading` entry is required when the patch removes or renames an option, changes a
  default, changes a public interface others implement (`ClusterInfo`, `IBroadcastableClusterInfo`,
  `BulkWriterConfig`, `SchemaSupplier`, `StatePersister`, `StorageTransportExtension`,
  `cdc/api/*`), changes persisted `CdcState`, or changes CDC Avro names or schemas ([NW] 0.5).
  CHANGES.txt takes user-facing changes only (commit `7ebb63b`).
- Do not apply Cassandra's banned-API rules (`ExecutorFactory`, `Clock.Global`,
  `CassandraRelevantProperties`, `JVMStabilityInspector`, NEWS for CQL); analytics has none of them
  ([CS]). Do flag JDK 12+ APIs in main code, since modules compile with `release 11` ([BG]).
- Style checkstyle misses: import order from `ide/idea/codeStyleSettings.xml`; names that state
  intent and no double negatives (PR#224 r3624641307, PR#241 r3986502494); stale comments and dead
  code left by the change (PR#239 r3909482943); a fix copied into a newer bridge when it belongs in
  the oldest one (PR#236 r3928194672); new duplication of Sidecar code (PR#212 review).
- Error handling: a catch that swallows or only logs on an executor path, where the result is a
  corrupt or incomplete upload or read, is a finding; deleting an optional broken component with a
  comment is accepted (PR#211 r3327301498).
- Security (self-gating). First decide whether the diff touches security surface: TLS and mTLS to
  Sidecar (`KEYSTORE_*`, `TRUSTSTORE_*` in `WriterOptions`, `BulkSparkConf.validateSslConfiguration`,
  `isSslEnabled`, `AnalyticsSidecarClient`, `SslConfig`, `SslConfigSecretsProvider`), the
  `CASSANDRA_ROLE` option, S3 transport credentials (`StorageCredentials`, `IamStorageAuth`,
  `StorageAccessConfiguration`, `StorageTransportExtension`), CDC connections to Cassandra and Kafka
  (`CassandraClientSource`, `SidecarCdcCassandraClient`, `KafkaOptions`), or secrets in Spark
  options, logs, exception messages or `toString`. If none, write "no security surface touched" and
  report no security findings.
- If it does: TLS must not silently turn off when part of a truststore or keystore is configured
  (CASSANALYTICS-220, PR#260); a password must be required with its store (PR#260 r4589697850);
  secrets are redacted in `toString` and never in log lines or messages (`StorageCredentials.redact`,
  PR#212 r3314386538); the role sent to Sidecar is not widened or dropped; credentials are not
  broadcast or persisted further than before *(inferred)*. Judge against the Cassandra security
  model that [SEC] links. Use rules `security-secret-exposure`, `security-tls-downgrade`,
  `security-authz-bypass`.

### cass-logic-boundary
- Option lookup: keys are lowercased with `Locale.ROOT`; a new option read with a raw
  `options.get("camelCase")` instead of `MapUtils.get*` or `MapUtils.lowerCaseKey` never matches
  (`MapUtils.java`, `ClientConfig.java`).
- Deprecated pairs: when both old and new names are set, check which wins in
  `MapUtils.resolveDeprecated`, and that units stay right (`SSTABLE_DATA_SIZE_IN_MB` is treated as MiB).
- Consistency level and DC: `LOCAL_*` without `LOCAL_DC`, non-local CL with a DC, per-DC quorum math
  with transient or witness replicas, and a replica set that is non-empty but cannot satisfy the CL
  (PR#244 r4379235500). Do not mix the reader and writer `ConsistencyLevel` classes.
- Token ranges: open-closed bounds, wrap-around, min and max tokens for Murmur3 versus
  `RandomPartitioner`, gaps and overlaps in coverage (CASSANALYTICS-180), `BigInteger` versus `long`.
- Replication factor parsing: `<replicas>/<transient>` forms, separate maps that can diverge, and
  invalid input that should throw rather than parse leniently (PR#238 r4018343334, r4018304093).
- Values: null versus empty versus unset for tuple and UDT fields (CASSANALYTICS-209, -217); quoted
  and mixed-case identifiers with `QUOTE_IDENTIFIERS` (CASSANALYTICS-216); vector, decimal and
  varint (`BigNumberConfig`); micros versus millis in `TIMESTAMP`, `TTL` and
  `sstable_*_timestamp_micros`.
- Narrowing in serializers: counts or values written with `writeByte` or `writeShort` that can exceed
  the range (CASSANALYTICS-184; `ReplicationFactor.Serializer` writes RF values as bytes).
- CDC naming: CQL names and Avro names mixed within `primary_keys`, `partition_keys`,
  `update_fields`, `truncatedFields` or UDT keys (PR#255 r4487273256, r4531887649).
- Null contracts across bridge and file APIs: `dataFile()`, filter components, `typeLookup`
  results (PR#239 r3909496936, PR#211 r3320575738, PR#252 r4262872419).

### cass-concurrency-lifecycle
- Static per-JVM state shared by concurrent tasks in one executor: `CassandraBridgeFactory`
  bridges map, `CassandraDataSourceHelper` cache, `SSTableCache`, CDC `TypeCache`. Check thread
  safety, cache keys, and that eviction releases what the entry holds (PR#236 r3983522407).
- `Schema.instance` is global per bridge classloader: schema changes go under
  `synchronized (Schema.instance)` (`CassandraSchema`, `SchemaUpdater`), and writer construction,
  schema building and scanner table lookup share that lock (commit `5e5f0ad`). Opening one keyspace
  must not rebuild others (CASSANALYTICS-202).
- Driver versus executor: transient fields rebuilt on executors (`BulkSparkConf.sidecarContactPoints`,
  `coordinatedWriteConf`), `IBroadcastable*` and `Broadcastable*` classes; a driver-only object used
  on an executor is null or stale there (PR#205 r3209854713).
- Resources acquired in a constructor or open path and leaked when a later step throws (PR#236
  r3983656417, compression dictionary ref in six-zero `SSTableReader`); data file streams not in
  try-with-resources (PR#211 r3348169486).
- Thread pools: storage client pools, `COMMIT_THREADS_PER_INSTANCE`, `SimpleTaskScheduler`,
  `CassandraTopologyMonitor`, `ImportCompletionCoordinator`; threads named and daemon through
  `ThreadUtil.threadFactory`; shut down on job end and on `CancelJobEvent`.
- Futures and timeouts: `CompletableFuture` chains in the Sidecar client and CDC, `FutureUtils`,
  blocking `get()` without a timeout on an executor thread, total timeouts across retries
  (CASSANALYTICS-179), `JOB_TIMEOUT_SECONDS`.
- Shutdown: `CassandraBridgeFactory.maybeRegisterShutdownHook` and `CdcBridgeFactory` close; a
  closed classloader or bridge used afterwards.
- CDC ordering: state persisted before the events it covers are consumed, or markers advanced on a
  failed batch (`MicroBatchIterator`, `SidecarStatePersister`) *(inferred)*.
- Shared mutable "constants" handed to callers (PR#239 r3909511024).

### cass-persistence-compat
- Bridge selection by SSTable version: a new native version must be added to `CassandraVersion`
  `nativeSSTableVersions` and `lowestCompatibleVersionNumber`; the writer must choose a version
  every node can import (`SSTableVersionAnalyzer.determineBridgeVersionForWrite`); the
  `bridge.disable_sstable_version_based` fallback must keep working.
- SSTable formats: a reader or writer change on 5.0 or 6.0 must handle both `big` and `bti`
  (`BigIndexReader`, `BtiIndexReader`, `BtiReaderUtils`). Written sstables must have every component
  consistent; a component that fails to rebuild is deleted, not uploaded partly written (PR#211).
- Copy-forward bridges: a fix in `cassandra-four-zero-bridge` or `-types` does not reach five or six
  where those modules override the same file; a call to a Cassandra API that changed between
  majors fails at runtime with `NoSuchMethodError` ([DR] "Bridge Modules").
- CDC Avro: changes to `cdc_bytes.avsc`, `cdc_generic_record.avsc`, `CqlToAvroSchemaConverter*`,
  `AvroSchemas` or `AvroNames` that change a record full name, namespace, field name or type break
  schema-registry consumers and old records; names must be stable and collision-free regardless of
  other columns (PR#255 i6782201339); bump `AvroConstants.CURRENT_VERSION` and add NEWS when the
  record shape changes.
- Persisted state: a change to `CdcState`, `Marker`, `CommitLogMarkers` or their Kryo serializers
  breaks resume from stored state; it needs a version marker or a NEWS `Upgrading` entry
  (CASSANALYTICS-184).
- Kryo and Java serialization: write and read agree field by field; both paths
  (`Serializer` and `writeObject`/`readObject`) change together; a new class is registered in
  `KryoRegister` or `CdcKryoRegister`; a format change gets a version byte (PR#238 r4078376579).
- Spark and Scala binary compatibility: code that differs by Spark lives in `src/main/spark3` and
  `src/main/spark4`, and by Scala in `scala-2.12-spark-3`, `scala-2.13-spark-3`,
  `scala-2.13-spark-4`; a Spark 4-only API in shared code breaks the Spark 3 build; JDK 12+ APIs
  break `release 11`; dependency bumps must respect the Jackson pins in `build.gradle` and the
  Avro and Vert.x pins in `gradle.properties`.
- Option and config compatibility: a renamed option keeps the old name as `@Deprecated`; a removed
  option is ignored, not rejected, and listed in NEWS; a changed `DEFAULT_*` value is user-visible;
  new settings use the `spark.cassandra_analytics.` prefix (`BulkSparkConf`).
- Sidecar compatibility: calls must work against the Sidecar version in `gradle.properties`
  (`sidecarVersion=0.4.0`); a new endpoint needs behaviour for an older Sidecar without it
  *(inferred)*.
- IO: reads at chunk and file ends (`BufferingInputStream`, CASSANALYTICS-147); executor temp
  directories cleaned unless `job.skip_clean`; S3 bundles sized by
  `MAX_SIZE_PER_SSTABLE_BUNDLE_IN_BYTES_S3_TRANSPORT`; digests computed over final bytes.
- Observability: a new stat wired through every builder to the `Stats`/`ICdcStats` implementation
  (CASSANALYTICS-191); log levels fit (expected per-job events not at error, PR#211 r3320569695);
  no keystore or truststore passwords, S3 secrets or session tokens in logs or messages.

### cass-completeness-symmetry
- Every bridge: a change to one `CassandraBridgeImplementation`, `CdcBridgeImplementation`,
  `SSTableReader`, `CompactionStreamScanner` or `ReaderUtils` copy is checked against the four,
  five and six-zero copies; a new abstract method in `CassandraBridge` or `CdcBridge` is implemented
  in each.
- Every types module: `cassandra-four-zero-types`, `-five-zero-types` and `-six-zero-types` overrides
  (for example `CqlUdt`, `AbstractCqlList`, `TimeUUID`) and the matching Spark SQL and Avro
  converters.
- Every Spark and Scala twin: a change in `src/main/spark3` has its counterpart in `src/main/spark4`,
  and `ScalaConversionUtils`/`SparkTypeUtils` per Scala directory.
- Every write transport: `DIRECT` (`DirectStreamSession`, `CassandraDirectDataTransportContext`),
  `S3_COMPAT` (`CloudStorageStreamSession`) and coordinated multi-cluster (`CassandraClusterInfoGroup`,
  `CoordinatedImportCoordinator`) (PR#214 r3365068279, r3365137189).
- Reader, writer and CDC: a type or schema fix in the bulk reader also checked in the bulk writer
  (`SqlToCqlTypeConverter`, `TableSchema`) and CDC (`FourZeroCdcEventBuilder`, `AvroDataUtils`,
  `CdcEventUtils`), as CASSANALYTICS-217 spanned reader and CDC.
- Serialization pairs: Kryo `write`/`read`, Java `writeObject`/`readObject`, `equals`/`hashCode`
  including a new field (PR#224 r3624564484), and registration in `KryoRegister`.
- Version lists in sync: `build.gradle` maps, `CassandraVersion`, `scripts/build-dtest-jars.sh`,
  `gradle.properties` `cassandraXXVersion`, the [GHA] and [CCI] matrices, and `C40_EXCLUSIONS`
  (PR#246 review 5290097883).
- User surface: `docs/src/user.adoc` option tables, `WriterOptions` javadoc, `NEWS.txt`; and
  `README.md` version claims when support changes.
- Interface implementers: `ClusterInfo`, `IBroadcastableClusterInfo`, `JobInfo`, `SchemaSupplier`,
  `StatePersister`, `StorageTransportExtension`, including test mocks (`MockBulkWriterContext`) and
  `cassandra-analytics-core-example`.
- Refactor aftermath: methods left dead (`isFileStreamed`, PR#239), stale comments and javadoc
  (PR#224 r3633449128), and tests still asserting the old behaviour.

### cass-test-regime
- Pure logic in `cassandra-analytics-common` or core (option parsing, RF parsing, token math,
  partitioning): a unit test in that module (`BulkSparkConfTest`, `ClientConfigTests`,
  `ReplicationFactorTests`, `TokenPartitionerTests`, `RangeUtils` tests).
- Anything in a bridge or types module, or that reads or writes sstables: a test parameterised over
  `VersionRunner#bridges` or `#versions` so it runs on each bridge, or a test in each affected bridge
  module (`SSTableReaderTests`, `SSTableWriterImplementationTest`); for 5.0 and 6.0, the BTI run
  (`testBti`) too. A change tested on one bridge only is a finding.
- Data type changes: QuickTheories over `TestUtils.cql3Type(bridge)` (`DataTypeTests`) plus the
  specific edge case (null, empty, unset, quoted names); heavy end-to-end classes tagged
  `@Tag("Sequential")`.
- Serialization: round-trip tests in `KryoSerializationTests`, `JDKSerializationTests`,
  `CdcKryoSerializationTests`, `CdcStateTests`; for a persisted format, a fixture of old bytes
  *(inferred)*.
- CDC Avro: `CqlToAvroSchemaConverterTest`, `AvroSchemasTest`, transformer tests, and `.avsc` fixtures
  in `cassandra-analytics-cdc-codec/src/test/resources/table_schemas/`.
- Cluster behaviour (Sidecar calls, CL, multi-DC, token ownership, real read and write): an
  integration test extending `SharedClusterSparkIntegrationTestBase`; topology changes under
  `expansion`, `shrink`, `replacement`, `movement` with `TopologyChangeBBUtils`; S3 transport under
  `testcontainer`. A cross-node fix with only a mocked unit test is a finding.
- Version gating: integration tests skip unsupported versions with assumptions; a permanent skip on
  a supported version needs a follow-up ticket (PR#236 r3963484371); new 4.0-incompatible classes
  go in `C40_EXCLUSIONS`.
- Tests that cannot fail: a mock that overrides the changed method (PR#214 r3365153253), a retry
  that catches the wrong exception class (PR#205 r3210248533), removed tests without a reason
  (PR#212 r3314507146).
- Timing and chance: fixed sleeps, tight timeouts, and probabilistic assertions (bloom filter false
  positives) without a comment (PR#211 r3320616042); ask for repeated runs or the CircleCI link.
- Hygiene: integration classes rely on `forkEvery = 1`; a test that sets static or system state
  outside that guarantee leaks; edits to unrelated integration tests are out of scope (PR#212).
