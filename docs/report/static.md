# Code style

## What is checked

Real checkstyle, cognitive complexity (PMD), and duplicate-code (CPD) results for the PR's changed Java files, each split into what the PR introduced and what was already there. Checkstyle uses the base branch's own `.build` configs; the tools are pinned and installed with `cpr tools install`, and their versions are shown in each result. If the tools did not run, those checks are `unknown`, never `pass`.

PMD also runs its whole Java rule catalog (296 rules in 8 categories: Error Prone, Multithreading, Security, Performance, Best Practices, Design, Code Style, Documentation) on the same files, and the report's **PMD rules** block lists the violations the PR introduces, rule by rule. The three complexity rules are left to the Method complexity table.

Alongside them is a fast approximation of the project's static checks, run on the lines the PR adds: APIs that checkstyle bans, licence headers on new files, edits to generated code or bundled jars, and `@Deprecated` without `since`. These checks read the diff only. They do not compile code or run `ant check`, which stays authoritative.

The banned-API rules are read from `.build/checkstyle.xml` on the PR's base branch, so they follow the project as it changes.

## Why

- Checkstyle errors fail CI's `ant check`, so an error the PR introduces is something the contributor must fix. Errors already in a touched file are counted but not blamed on the PR.
- Cognitive complexity above 15 is the default threshold of the complexity-reduction skill the owner uses; the report lists every changed method with its base and head score so a simplification (6 to 2) is visible, and flags only methods the PR made newly or more complex.
- A PMD rule that fires in a quarter or more of the base branch's own files is one the code does not follow (`CommentRequired`, `MethodArgumentCouldBeFinal`, `LocalVariableCouldBeFinal` and the like). The report counts those under "House style differs" and does not list them line by line, or judge the PR by them. The threshold comes from the code, not from a hand-kept list. Source: [PMD rules](https://pmd.github.io/pmd/pmd_rules_java.html).
- Duplicated blocks of 100 or more tokens (PMD CPD default) are flagged when the PR adds one. Source: [PMD CPD](https://pmd.github.io/pmd/pmd_userdocs_cpd.html).
- `ant check` runs `rat-check` (licence headers), `checkstyle` (main code), and `checkstyle-test` (tests). It also runs on every push to a fork through GitHub Actions on JDK 11 and 17, and checkstyle runs during `ant build` and `ant jar`. Sources: `build.xml`; [AGENTS.md](https://github.com/apache/cassandra/blob/trunk/AGENTS.md), "Linting"; [Code style](https://cassandra.apache.org/_/development/code_style.html), "Checkstyle".
- [.build/checkstyle.xml](https://github.com/apache/cassandra/blob/trunk/.build/checkstyle.xml) bans APIs that bypass Cassandra's own abstractions, for example `System.currentTimeMillis` (use `Clock.Global`), `Executors.new*` (use `ExecutorFactory.Global`), `java.io.File` (use `org.apache.cassandra.io.util.File`), `toLowerCase` (use `LocalizeString`), and `System.getProperty` (use `CassandraRelevantProperties`). It also requires `@Deprecated` to carry `since=`.
- Every new file needs the Apache licence header; the template is `.build/header.txt`. Source: [AGENTS.md](https://github.com/apache/cassandra/blob/trunk/AGENTS.md), "Code Style".
- Never modify `src/gen-java/` (generated from `src/antlr/`) or files in `lib/`. Ask before changing `src/antlr/Cql.g`. Never bypass checkstyle without a suppression comment that explains why. Source: [AGENTS.md](https://github.com/apache/cassandra/blob/trunk/AGENTS.md).
- New dependencies need a `[DISCUSS]` thread and consensus on dev@. Since 5.0 they are declared in the `.build/*-template.xml` POMs. Source: [Dependencies](https://cassandra.apache.org/_/development/dependencies.html).

## How each status is decided

All checks are advisory. Unless noted, a warn moves the recommendation to "needs work".

A finding is **introduced** when it is in a new file, a new method, a method whose score got worse, a method that crossed the threshold, or (checkstyle) on a changed line or with no equal error at base. It is **pre-existing** when it was already there (touched, untouched, or improved), and **fixed** when it is gone. Matching uses the base path (through renames), class, method signature, and rule, never the line number alone.

### `static.checkstyle`

Advisory. Owner: contributor.

Runs checkstyle on the changed Java files, `.build/checkstyle.xml` for `src/java` and `checkstyle_test.xml` for `test/`, both taken from the base branch. Branch families pick the version: trunk and 5.0 use 10.26.1, 4.1 uses 8.40, 4.0 has no config.

- **unknown**: the base branch has no checkstyle config (`cassandra-4.0`; no other branch's config is borrowed), the tool or a JDK is missing, it crashed, or its output omits a changed file (the count not analyzed is named). The reason is shown with the tool version.
- **not-applicable**: no changed Java files, or the tool does not apply.
- **warn** (needs action): at least one introduced error. Each shows file, line, rule, and message (up to 50), plus counts of pre-existing and fixed errors.
- **pass**: checkstyle ran on every changed file and nothing was introduced.

### `static.complexity`

Advisory and informational: a warn here is a note and does not change the recommendation. Owner: contributor.

Evidence always lists every changed method as `Class.method(signature): base → head` cognitive complexity (`new → N` for added methods, `N → removed` for deleted ones), introduced methods first.

- **unknown**: PMD is missing or failed, or it did not analyze every changed file.
- **warn** (note): a method scoring 15 or more that is new, got worse, or crossed the threshold.
- **pass**: no such method. A method that got simpler, or an old complex method left alone, passes.

### `static.pmd-rules`

Advisory. Owner: contributor.

Runs every non-deprecated rule of PMD's eight Java categories on the head and base of the changed files in the same PMD pass as the complexity scores. A violation is **introduced** when its first line is an added line of the head file, or the file is new; a modified file without a line map falls back to the head count of a rule minus its base count. A rule is **house style** when it fires in at least 25% of the base branch's `src/java` files (the baseline: the whole branch is scored once and cached by branch tip). House-style rules are counted and collapsed, never listed per line and never part of the verdict.

A second test catches rules Cassandra breaks on purpose but rarely per file (`DoNotUseThreads`, `AvoidUsingVolatile`, `NullAssignment` and the like). The baseline also records each rule's violation count and the lines it scanned. For a PR, a rule's expected count is the base branch's rate (violations per non-blank line) times the PR's added production lines. A rule is **usual for Cassandra** when the PR's production count is not significantly above that expectation (one-sided Poisson test, p of at least 0.01). The block lists such rules in a collapsed section with observed against expected, and the check ignores them. A rule the base branch never breaks is never usual, and test-file violations are not rate-tested. The bands are red for Error Prone, Multithreading and Security, yellow for Performance, Best Practices and Design, green for Code Style and Documentation.

When a saved build of this head keeps its classes and jars they go to PMD as `--aux-classpath`, so rules that resolve types are reliable. `cpr build` keeps them for the five most recent runs (hard links inside the run directory, about 200 MB each). Otherwise PMD runs without type info, and the block and the check say so. Rules that need type resolution (`cpr/config/pmd-type-rules.json`: taken from PMD's rule text, then confirmed by running the same files with and without a classpath) are then shown greyed as "needs compiled classes" and the check ignores them.

- **unknown**: PMD or its rule catalog did not run, or PMD could not read some changed files and found nothing red in the rest (the skipped files are named).
- **warn** (note): at least one red-band violation is introduced in production code, outside house style, not usual for Cassandra, and not a type-dependent rule that ran without classes. The summary names the top rules; tests are counted in the block but not in the verdict.
- **pass**: PMD ran on every changed file and introduced no such red-band violation. Yellow and green counts are shown in the summary and in the block.

### `static.duplication`

Advisory and informational. Owner: contributor.

CPD with 100 tokens minimum over the changed files.

- **unknown**: CPD is missing or failed.
- **warn** (note): an introduced duplicate, listed with every occurrence (file and line range).
- **pass**: none introduced.

### `static.banned-api`

Advisory. Owner: contributor.

When real checkstyle ran on the PR this check is **not-applicable** ("superseded by static.checkstyle"). Otherwise it is an approximation of checkstyle, and its summary says so. Rules come from three checkstyle modules: `RegexpSinglelineJava` (the regex as written), `IllegalImport` (listed classes and packages), and `IllegalInstantiation` (`new` of listed classes). Only added lines in `src/java/**/*.java` are scanned. A line is skipped when it starts with `//`, `/*`, or `*`, when it contains `checkstyle: permit`, or when the added line before it does.

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

Scans added lines in every `.java` file, including tests, for `@Deprecated` not immediately followed by `(since`. Comment lines are skipped. Like `static.banned-api`, it is **not-applicable** (superseded by `static.checkstyle`) when real checkstyle ran, and otherwise labelled an approximation.

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

- Real analysis covers changed Java files only, excluding `src/gen-java/` and `modules/accord/`. Over 400 changed files PMD is skipped (`unknown`); each tool has a 120 s cap and a PR a 300 s cap.
- `cassandra-4.0` has no checkstyle config, so `static.checkstyle` is `unknown` there and the diff approximations below keep running.
- Results are computed when the PR is fetched and stored in the evidence bundle; an offline re-render replays them and runs no tool. The report shows the tool versions used.
- The first PR against a branch builds the baseline (about four and a half minutes for trunk on four threads; its own 900 s cap) and later PRs reuse it. A baseline for the same branch built less than seven days ago is reused when the tip moved. If the baseline cannot be built, house style falls back to the density of each rule in the base versions of the touched files, which the block states.
- PMD without type info can misfire on rules that resolve types, for example `WrongTestAnnotation` and `CloseResource`. The block says whether type info was used, and greys those rules when it was not. Only a PR that was built (committer PRs, or an owner-approved build) has type info.
- The usual-for-Cassandra test uses the base branch's overall rate, not the rate of the touched packages, and a small PR has little power to show a rule is unusual: expect one or two violations of a common rule to count as usual.
- Complexity matching is by signature; a method moved between classes may be reported as new or removed, or labelled "moved".
- A tool that is missing or crashes shows `unknown` with the reason; it is never counted as clean.
- The diff-based checks (banned API, licence header, `@Deprecated`) approximate `ant check` from the diff. The report's About section lists `ant check` as not run.
- `.build/checkstyle_suppressions.xml` is not applied, so files the project exempts can be flagged. Test code (`checkstyle_test.xml`) is not scanned for banned APIs.
- Rules that need a parse tree are not checked: import order, unused or star imports, the `var` ban, and `MissingDeprecated`.
- A multi-line statement is checked line by line, so a banned call split across lines is missed.
- `@Deprecated(forRemoval = true, since = "5.0")` is flagged, because `since` is not first.
- The licence check flags new `.yaml` and `.xml` files that RAT itself excludes (for example `cassandra*.yaml`).
- The human style rules on the [Code style](https://cassandra.apache.org/_/development/code_style.html) page (braces, naming, `final` on locals, exception handling, logging) are not checked.
