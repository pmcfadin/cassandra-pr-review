# Code style

## What is checked

Real checkstyle, cognitive complexity (PMD), and duplicate-code (CPD) results for the PR's changed Java files, each split into what the PR introduced and what was already there. If a tool did not run, its checks are `unknown`, never `pass`. Tool versions are shown in each result; tools are pinned and installed with `cpr tools install`.

Checkstyle runs standalone, outside Gradle, with the project's own config from the base branch and the version its Gradle build uses:

| Project | Checkstyle | Config (main and test) |
|---|---|---|
| Cassandra Sidecar | 7.8.1 (pinned in `build.gradle`) | `checkstyle.xml` at the repository root |
| Cassandra Analytics | 9.3 (no `toolVersion` set, so Gradle 8's default) | `config/checkstyle/checkstyle.xml`, which reads `${config_loc}/suppressions.xml`; the tool passes `config_loc` |

Main code is any Java file under a module's `src/main/java/` (Sidecar) or `src/main/<dir>/` (Analytics, which also keeps Java in directories such as `src/main/scala-2.13-spark-4/`). Test code is `src/test/`, `src/integrationTest/`, `src/containerTest/` and `src/testFixtures/` (Sidecar), or `src/test*/` and `src/testFixtures*/` (Analytics).

PMD and CPD run exactly as for Cassandra: PMD's whole Java rule catalog on the changed files, listed rule by rule in the report's **PMD rules** block, and CPD with a 100-token minimum. Sidecar's CI also runs SpotBugs; this tool does not, and its result arrives through the CI checks.

Two diff checks also run: banned APIs (only when real checkstyle did not run) and licence headers on new files.

## Why

- Both projects run checkstyle and RAT (licence headers) as `codeCheckTasks`, ordered before their tests, and their CI runs checkstyle on every PR to `trunk`. Sources: [Sidecar build.gradle](https://github.com/apache/cassandra-sidecar/blob/trunk/build.gradle), [Analytics build.gradle](https://github.com/apache/cassandra-analytics/blob/trunk/build.gradle), [Sidecar TESTING.md](https://github.com/apache/cassandra-sidecar/blob/trunk/TESTING.md), "Code Quality Checks". A checkstyle error the PR introduces is something the contributor must fix.
- The configs are the projects' own: [Sidecar checkstyle.xml](https://github.com/apache/cassandra-sidecar/blob/trunk/checkstyle.xml), [Analytics checkstyle.xml](https://github.com/apache/cassandra-analytics/blob/trunk/config/checkstyle/checkstyle.xml). Analytics' config also requires the Apache licence header on Java files.
- Cognitive complexity above 15, house-style PMD rules (firing in a quarter or more of the base branch's main files), and CPD's 100-token duplicates are judged as for Cassandra. Sources: [PMD rules](https://pmd.github.io/pmd/pmd_rules_java.html); [PMD CPD](https://pmd.github.io/pmd/pmd_userdocs_cpd.html).

## How each status is decided

All checks are advisory. Unless noted, a warn moves the recommendation to "needs work".

A finding is **introduced** when it is in a new file, a new method, a method whose score got worse, a method that crossed the threshold, or (checkstyle) on a changed line or with no equal error at base. It is **pre-existing** when it was already there, and **fixed** when it is gone. Matching uses the base path (through renames), class, method signature, and rule, never the line number alone.

### `static.checkstyle`

Advisory. Owner: contributor.

- **unknown**: the base branch lacks the config file, the tool or a JDK is missing, it crashed or timed out, or its output omits a changed file. The reason is shown with the tool version.
- **not-applicable**: no changed Java files under the main or test directories.
- **warn** (needs action): at least one introduced error. Each shows file, line, rule, and message (up to 50), plus counts of pre-existing and fixed errors.
- **pass**: checkstyle ran on every changed file and nothing was introduced.

### `static.complexity`

Advisory and informational: a warn is a note and does not change the recommendation. Owner: contributor.

- **unknown**: PMD is missing or failed, or it could not read some changed files and found nothing in the rest.
- **warn** (note): a method scoring 15 or more that is new, got worse, or crossed the threshold.
- **pass**: no such method.

### `static.pmd-rules`

Advisory and informational. Owner: contributor.

As for Cassandra: a rule is **house style** when it fires in at least 25% of the base branch's main Java files (the branch baseline is scored once from the files under the main directories above and cached), and **usual for** the project when the PR's production count is not significantly above the branch's rate (one-sided Poisson test, p of at least 0.01). Neither is listed per line or counted. As for Cassandra, when a saved build of this head kept its classes and jars, PMD uses them for type resolution; otherwise rules that need compiled classes are greyed and ignored.

- **unknown**: PMD or its rule catalog did not run, or PMD skipped some files and found nothing red in the rest.
- **warn** (note): at least one Error Prone, Multithreading or Security violation introduced in production code that is not house style, not usual, and not type-dependent.
- **pass**: PMD ran on every changed file and introduced no such violation.

### `static.duplication`

Advisory and informational. Owner: contributor.

- **unknown**: CPD is missing or failed.
- **warn** (note): an introduced duplicate, listed with every occurrence.
- **pass**: none introduced.

### `static.banned-api`

Advisory. Owner: contributor.

**not-applicable** ("superseded by static.checkstyle") when real checkstyle ran. Otherwise it scans added lines of main Java files against the `RegexpSinglelineJava`, `IllegalImport` and `IllegalInstantiation` modules of the base branch's main config.

- **not-applicable**: the base branch has no config file.
- **unknown**: the config has no rule of those kinds. This is the normal result for Analytics, whose `IllegalImport` and `IllegalInstantiation` list nothing.
- **warn**: an added line matches a rule. Sidecar's config has one such rule: no imports from `junit.framework`.
- **pass**: no added line matches.

### `static.license-header`

Advisory. Owner: contributor.

New files ending in `.java`, `.py`, `.sh`, `.xml`, `.g`, `.yaml`, `.yml`, or `.properties`, outside any `src/*/resources/` directory, must contain "Licensed to the Apache Software Foundation" in their first 30 lines.

- **warn**: at least one such new file lacks it.
- **pass**: all have it, or there are no such new files.

### `static.protected-paths`

**not-applicable** for both projects: "Not part of Cassandra Sidecar's process" (or Cassandra Analytics'). Neither tree has generated sources, bundled jars, or a CQL grammar.

### `static.deprecated-since`

**not-applicable** for both projects. Neither config requires `since=`, and Sidecar's client modules compile for Java 8, where `@Deprecated` has no `since`.

## How to fix

Run the projects' checks locally before pushing:

```
./gradlew checkstyleMain checkstyleTest   # checkstyle
./gradlew codeCheckTasks                  # checkstyle and RAT (and SpotBugs in Sidecar)
```

- **Checkstyle**: fix each error, or add a suppression the config supports with a comment that explains why.
- **Licence header**: copy the header of any existing source file to the top of the new file.

## Limits

- Real analysis covers changed Java files only; Scala files in Analytics are not analyzed. Over 400 changed files PMD is skipped (`unknown`); each tool has a 120 s cap and a PR a 300 s cap.
- Sidecar's checkstyle 7.8.1 predates newer Java syntax; the result matches what the project's own Gradle build would report.
- PMD has type info only when `cpr build` built this head (committer PRs, or an owner-approved build), and only after that build. A plain `cpr review` runs it without.
- The first PR against `trunk` builds the PMD baseline (its own 900 s cap); later PRs reuse it. If it cannot be built, house style falls back to the touched files, which the block states.
- Results are computed when the PR is fetched; an offline re-render runs no tool.
- RAT and SpotBugs are not run.
