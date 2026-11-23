# Compatibility

## What is checked

Which public surfaces the PR touches, by changed path. The surfaces differ per project.

**Cassandra Sidecar**

| Surface | Paths |
|---|---|
| REST API | `client-common/src/main/java/org/apache/cassandra/sidecar/common/`: `ApiEndpointsV*.java`, `request/`, `response/`, `data/` |
| configuration | `conf/sidecar*.yaml`, `server/src/main/java/org/apache/cassandra/sidecar/config/` |
| sidecar schema | `server/src/main/java/org/apache/cassandra/sidecar/db/schema/` |
| Cassandra adapters | `adapters/` |
| client (Java 8) | `src/main/` of `client`, `client-common`, `vertx-client`, `vertx-client-shaded` |
| authentication and authorization | `vertx-auth-mtls/src/main/`, `server/src/main/java/org/apache/cassandra/sidecar/acl/` |
| metrics | `server/src/main/java/org/apache/cassandra/sidecar/metrics/` |
| packaging | `docker/`, `scripts/`, `server/src/main/dist/` |
| dependencies | `gradle.properties`, `gradle/`, the root and module `build.gradle` files |

**Cassandra Analytics**

| Surface | Paths |
|---|---|
| Cassandra version bridges | `src/main/` of `cassandra-bridge*`, `cassandra-three-zero*`, `cassandra-four-zero*`, `cassandra-five-zero*`, `cassandra-six-zero*` |
| CDC Avro schemas | any `*.avsc` under `src/main/resources/` |
| Spark converters | `src/main/` of `cassandra-analytics-spark*-converter` and `cassandra-*avro-converter` |
| bulk writer and reader options | `BulkSparkConf`, `BulkWriterConfig`, `WriterOptions`, `ClientConfig` in `cassandra-analytics-core` |
| CDC API | `cassandra-analytics-common/src/main/java/org/apache/cassandra/cdc/api/` |
| supported Cassandra versions | `gradle.properties`, `scripts/build-dtest-jars.sh`, `scripts/build-dependencies.sh` |
| bundled Sidecar client | `analytics-sidecar-*` |
| dependencies | `gradle/`, the root and module `build.gradle` files, `profiles/` |

## Why

- Sidecar APIs must stay compatible with Cassandra trunk and every supported older version; new features or breaking changes are introduced backward-compatibly or under a new API version (`/v1/...`). Removing fields, changing field types, or removing operations needs a version change, and deprecated APIs stay until the next version change. Source: [Sidecar CONTRIBUTING.md](https://github.com/apache/cassandra-sidecar/blob/trunk/CONTRIBUTING.md), "RESTful API Design Guidelines" and "API Lifecycle".
- Sidecar supports several Cassandra versions through adapters; a breaking change goes into the `base` adapter with shims in a version-named adapter. Source: [Sidecar CONTRIBUTING.md](https://github.com/apache/cassandra-sidecar/blob/trunk/CONTRIBUTING.md), "Cassandra Adapters".
- New endpoints carry OpenAPI annotations. Source: [Sidecar OPENAPI.md](https://github.com/apache/cassandra-sidecar/blob/trunk/OPENAPI.md).
- Each major Cassandra version has its own Analytics bridge modules, and later bridges inherit earlier ones' sources; a Cassandra API that changed between majors compiles and then fails at runtime with `NoSuchMethodError`. Source: [Analytics DEV-README.md](https://github.com/apache/cassandra-analytics/blob/trunk/DEV-README.md), "Bridge Modules".
- "Changes must not break compatibility between different Cassandra versions." Source: [Contributing code changes](https://cassandra.apache.org/_/development/patches.html).

## How each status is decided

### `compat.config-pairing`

**not-applicable** for both projects: "Not part of Cassandra Sidecar's process" (or Cassandra Analytics'). The rule is about Cassandra's `conf/cassandra.yaml` and `conf/cassandra_latest.yaml`.

### `compat.system-properties`

**not-applicable** for both projects. `CassandraRelevantProperties` exists only in Cassandra.

### `compat.nodetool-help`

**not-applicable** for both projects. They have no nodetool.

### `compat.surfaces`

Advisory. Owner: reviewer.

- **warn** (informational): at least one surface in the project's table above is touched. Each surface lists up to five files. Shown, but does not change the recommendation.
- **pass**: no surface touched.

## How to fix

- **REST API**: add fields as optional; for a removal, type change or renamed field, add a new API version and deprecate the old one. Update the OpenAPI annotations.
- **Client (Java 8)**: `client` and `client-common` compile with `sourceCompatibility = 1.8`; keep them free of newer language features and APIs.
- **Configuration**: document new settings in `conf/sidecar.yaml`, and say in the PR what happens to existing configuration files.
- **Adapters and bridges**: make the change in the base module, and add or override a version-specific file where a Cassandra API differs; test against every supported Cassandra version.
- **CDC Avro schemas and converters**: check that records written with the old schema still read.
- **Dependencies**: say in the PR why the dependency or version changes.

## Limits

- Surfaces are detected by path. A compatibility change outside these paths is not seen, and a harmless edit inside them is flagged.
- Whether a change is backward-compatible, versioned, or tested on every supported Cassandra version is a reviewer's judgement; no check reads the code for it.
