# Compatibility

## What is checked

Which public or on-disk surfaces the PR touches, and a few mechanical rules around them: both yaml files change together, system properties go through `CassandraRelevantProperties`, and nodetool changes update the help fixtures.

The surfaces, by changed path:

| Surface | Paths |
|---|---|
| config | `conf/cassandra*.yaml`, `config/Config.java` |
| native protocol | `transport/`, `doc/native_protocol*` |
| CQL grammar | `src/antlr/` |
| CQL semantics | `cql3/` |
| messaging | `net/` |
| sstable format | `io/sstable/` |
| commitlog / hints | `db/commitlog/`, `hints/` |
| schema / system tables | `schema/`, `db/SystemKeyspace*` |
| nodetool | `tools/nodetool/` |
| JMX | any `*MBean.java` |
| metrics | `metrics/` |
| virtual tables | `db/virtual/` |
| guardrails | `db/guardrails/` |
| dependencies | `.build/*.xml`, `build.xml`, `lib/` |

Java paths are under `src/java/org/apache/cassandra/`.

## Why

- "Changes must not break compatibility between different Cassandra versions." Source: [Contributing code changes](https://cassandra.apache.org/_/development/patches.html).
- CQL, virtual tables, JMX, yaml, and system properties are public APIs. Changes must follow the approach of existing APIs, and plans to change an API go to dev@. Source: [Code style](https://cassandra.apache.org/_/development/code_style.html), "Public APIs".
- Both `conf/cassandra.yaml` and `conf/cassandra_latest.yaml` ship with Cassandra (5.0 and later). Renamed settings need `@Replaces` and converters so old yaml keeps loading; `ConfigCompatibilityTest` and `LoadOldYAMLBackwardCompatibilityTest` guard this. Source: [conf/](https://github.com/apache/cassandra/tree/trunk/conf) and the tests named.
- System properties must be declared in `CassandraRelevantProperties`; checkstyle bans direct `System.getProperty` and friends. Source: [.build/checkstyle.xml](https://github.com/apache/cassandra/blob/trunk/.build/checkstyle.xml).
- nodetool help output is pinned by fixtures under `test/resources/nodetool/help/`, checked by `NodetoolHelpCommandsOutputTest`.
- Reviewers check that NEWS.txt, the CQL docs, and the native protocol spec (`doc/native_protocol_v*.spec`) are updated when needed, and that the ticket's Impacts field is set. Source: [How to review](https://cassandra.apache.org/_/development/how_to_review.html), Documentation.
- Changes that could affect upgrades, serialization, or on-disk formats need upgrade tests and the `pre-commit w/ upgrades` CI profile. Source: [CI page](https://cassandra.apache.org/_/development/ci.html).

## How each status is decided

### `compat.config-pairing`

**Blocking.** Owner: contributor.

- **not-applicable**: none of `conf/cassandra.yaml`, `conf/cassandra_latest.yaml`, or `Config.java` changed.
- **fail**: one yaml file changed and the other did not. The recommendation becomes "blocked".
- **warn** (informational): `Config.java` changed and neither yaml file did. Shown, but does not change the recommendation.
- **pass**: both yaml files changed.

### `compat.system-properties`

Advisory. Owner: contributor.

Scans added lines under `src/java/` (except `CassandraRelevantProperties.java` itself, and lines starting with `//` or `*`) for `System.getProperty`, `System.setProperty`, `System.getenv`, `Integer.getInteger`, `Long.getLong`, or `Boolean.getBoolean`.

- **warn**: at least one hit. Moves the recommendation to "needs work".
- **pass**: none.

### `compat.nodetool-help`

Advisory. Owner: contributor.

- **not-applicable**: nothing under `src/java/org/apache/cassandra/tools/nodetool/` changed.
- **warn** (informational): nodetool code changed and no file under `test/resources/nodetool/help/` did. Shown, but does not change the recommendation.
- **pass**: a help fixture changed too.

### `compat.surfaces`

Advisory. Owner: reviewer.

- **warn** (informational): at least one surface in the table above is touched. Each surface lists up to five files. Shown, but does not change the recommendation. It tells reviewers where to look.
- **pass**: no surface touched.

## How to fix

- **Config**: add or change the setting in `Config.java`, document it in both `conf/cassandra.yaml` and `conf/cassandra_latest.yaml`, and use `@Replaces` with a converter for a rename. Run `ConfigCompatibilityTest`.
- **System property**: add an entry to `CassandraRelevantProperties` and read it from there.
- **nodetool**: if options or help text changed, regenerate the fixtures under `test/resources/nodetool/help/`, run `NodetoolHelpCommandsOutputTest`, and update the nodetool docs.
- **Messaging, SSTable, commit log, hints, schema**: gate new behaviour on the messaging or SSTable version so mixed-version clusters work, add serialization and upgrade tests, and run CI with `pre-commit w/ upgrades`.
- **Native protocol**: gate on `ProtocolVersion`, update `doc/native_protocol_v*.spec`, and set the ticket's Impacts field to Clients.
- **CQL**: update the CQL docs; for grammar changes, check reserved keywords and discuss on dev@ first.
- **JMX and metrics**: do not rename or remove silently. Deprecate with `@Deprecated(since = "X.Y")` and note it in NEWS.txt.
- **Defaults and guardrails**: add a NEWS.txt "Upgrading" note when a default or a guardrail's meaning changes.
- **Dependencies**: start a dev@ `[DISCUSS]` thread.

## Limits

- Surfaces are detected by path. A compatibility change in a file outside these paths is not seen, and a harmless edit inside them (a comment, a test helper) is flagged.
- `compat.config-pairing` treats any change to one yaml file as needing the same change in the other. Changes that belong in only one file (a default that differs in `cassandra_latest.yaml` on purpose) are failed, and on 4.0 and 4.1, which have no `cassandra_latest.yaml`, any `cassandra.yaml` change fails. A reviewer must override in those cases.
- The `dependencies` surface matches every XML file under `.build/`, including checkstyle config.
- `compat.system-properties` overlaps with `static.banned-api`, so one line can be reported twice.
- Whether a change is version-gated, has upgrade tests, or needs NEWS.txt is a reviewer's judgement; no check reads the code for it.
