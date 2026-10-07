# Code style

## What is checked

A fast approximation of the project's static checks, run on the lines the PR adds: APIs that checkstyle bans, licence headers on new files, edits to generated code or bundled jars, and `@Deprecated` without `since`. These checks read the diff only. They do not compile code or run `ant check`, which stays authoritative.

The banned-API rules are read from `.build/checkstyle.xml` on the PR's base branch, so they follow the project as it changes.

## Why

- `ant check` runs `rat-check` (licence headers), `checkstyle` (main code), and `checkstyle-test` (tests). It also runs on every push to a fork through GitHub Actions on JDK 11 and 17, and checkstyle runs during `ant build` and `ant jar`. Sources: `build.xml`; [AGENTS.md](https://github.com/apache/cassandra/blob/trunk/AGENTS.md), "Linting"; [Code style](https://cassandra.apache.org/_/development/code_style.html), "Checkstyle".
- [.build/checkstyle.xml](https://github.com/apache/cassandra/blob/trunk/.build/checkstyle.xml) bans APIs that bypass Cassandra's own abstractions, for example `System.currentTimeMillis` (use `Clock.Global`), `Executors.new*` (use `ExecutorFactory.Global`), `java.io.File` (use `org.apache.cassandra.io.util.File`), `toLowerCase` (use `LocalizeString`), and `System.getProperty` (use `CassandraRelevantProperties`). It also requires `@Deprecated` to carry `since=`.
- Every new file needs the Apache licence header; the template is `.build/header.txt`. Source: [AGENTS.md](https://github.com/apache/cassandra/blob/trunk/AGENTS.md), "Code Style".
- Never modify `src/gen-java/` (generated from `src/antlr/`) or files in `lib/`. Ask before changing `src/antlr/Cql.g`. Never bypass checkstyle without a suppression comment that explains why. Source: [AGENTS.md](https://github.com/apache/cassandra/blob/trunk/AGENTS.md).
- New dependencies need a `[DISCUSS]` thread and consensus on dev@. Since 5.0 they are declared in the `.build/*-template.xml` POMs. Source: [Dependencies](https://cassandra.apache.org/_/development/dependencies.html).

## How each status is decided

All four checks are advisory. Unless noted, a warn moves the recommendation to "needs work".

### `static.banned-api`

Advisory. Owner: contributor.

Rules come from three checkstyle modules: `RegexpSinglelineJava` (the regex as written), `IllegalImport` (listed classes and packages), and `IllegalInstantiation` (`new` of listed classes). Only added lines in `src/java/**/*.java` are scanned. A line is skipped when it starts with `//`, `/*`, or `*`, when it contains `checkstyle: permit`, or when the added line before it does.

- **not-applicable**: the base branch has no `.build/checkstyle.xml` (older branches).
- **unknown**: the file exists but no rule could be read from it. Informational only.
- **warn**: at least one added line matches a rule. Each hit shows file, line, rule, and the project's message (up to 50 hits).
- **pass**: no added line matches.

### `static.license-header`

Advisory. Owner: contributor.

New files ending in `.java`, `.py`, `.sh`, `.xml`, `.g`, `.yaml`, `.yml`, or `.properties`, outside `test/resources/`, must contain "Licensed to the Apache Software Foundation" in their first 30 lines.

- **warn**: at least one such new file lacks it.
- **pass**: all have it, or there are no such new files.

### `static.protected-paths`

Advisory. Owner: contributor.

- **warn** (needs action): a file under `src/gen-java/` or `lib/` changed. Grammar files are listed too if present.
- **warn** (informational): only CQL grammar files under `src/antlr/` changed. Shown, but does not change the recommendation; the grammar change needs a dev@ discussion and a CQL docs update.
- **pass**: none of these paths changed.

### `static.deprecated-since`

Advisory. Owner: contributor.

Scans added lines in every `.java` file, including tests, for `@Deprecated` not immediately followed by `(since`. Comment lines are skipped.

- **warn**: at least one such annotation.
- **pass**: none.

## How to fix

Run the real checks locally before pushing:

```
ant checkstyle          # main code
ant checkstyle-test     # test code
ant check               # checkstyle, checkstyle-test, and RAT licence check
.build/docker/check-code.sh 11   # the same in Docker, as CI runs it
```

- **Banned API**: use the replacement named in the message. If the call is truly needed, add a suppression comment that explains why, as checkstyle's `SuppressWithNearbyCommentFilter` expects.
- **Licence header**: copy `.build/header.txt` (or the header of any existing source file) to the top of the new file.
- **Generated code**: change the source (`src/antlr/*.g`) and let the build regenerate `src/gen-java/`.
- **`lib/`**: dependencies are declared in the `.build/*-template.xml` POMs and need a dev@ `[DISCUSS]` thread first.
- **Grammar**: start a dev@ thread, and update the CQL docs and reserved keywords if needed.
- **Deprecation**: write `@Deprecated(since = "5.0")`.

## Limits

- These checks approximate `ant check` from the diff. The report's About section lists `ant check` as not run.
- `.build/checkstyle_suppressions.xml` is not applied, so files the project exempts can be flagged. Test code (`checkstyle_test.xml`) is not scanned for banned APIs.
- Rules that need a parse tree are not checked: import order, unused or star imports, the `var` ban, and `MissingDeprecated`.
- A multi-line statement is checked line by line, so a banned call split across lines is missed.
- `@Deprecated(forRemoval = true, since = "5.0")` is flagged, because `since` is not first.
- The licence check flags new `.yaml` and `.xml` files that RAT itself excludes (for example `cassandra*.yaml`).
- The human style rules on the [Code style](https://cassandra.apache.org/_/development/code_style.html) page (braces, naming, `final` on locals, exception handling, logging) are not checked.
