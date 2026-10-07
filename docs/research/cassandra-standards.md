# Apache Cassandra contribution and review standards (as of 2026-10-07)

Research input for the cassandra-pr-review tool. Every rule cites a primary source. Repo paths refer to
`apache/cassandra` trunk at commit `617fd3b9` (2026-10-07). Website pages are the sources in
`apache/cassandra-website` under `site-content/source/modules/ROOT/pages/development/`, published at
`https://cassandra.apache.org/_/development/<page>.html`. Where sources conflict or are stale, the note says so.

Abbreviations: **[C]** = `CONTRIBUTING.md`; **[AG]** = `AGENTS.md` (`CLAUDE.md` just points to it);
**[T]** = `TESTING.md`; **[PT]** = `.github/pull_request_template.md`; **[W:x]** = website page `x.adoc`;
**[GOV]** = https://cwiki.apache.org/confluence/display/CASSANDRA/Cassandra+Project+Governance

---

## 0. Things that changed recently and that a reviewer tool must not get wrong

- **Version lines.** trunk is **7.0** (`CHANGES.txt` head is `7.0`, with a "Merged from 6.0:" block). The
  `cassandra-6.0` branch exists and is not GA yet. Maintained lines are 5.0, 4.1, and 4.0, plus 6.0 pre-GA.
  Sources: `CHANGES.txt`, `gh api repos/apache/cassandra/branches`,
  https://cassandra.apache.org/_/download.html (5.0.9, 4.1.12, 4.0.21, all released 2026-08-07).
- **Pre-commit CI moved to Jenkins plus `.build/run-ci`.** Contributors must attach `ci_summary_*.html` and
  `results_details_*.tar.xz` to the JIRA ticket. CircleCI config still exists in `.circleci/`, but the
  current docs no longer name it as the pre-commit path. Sources: [C] "Continuous Integration", [W:ci], [W:patches] step 4.
- **The repo has agent instructions and in-tree review skills.** `AGENTS.md` was added 2026-04-12. It sets
  an `Assisted-by: AGENT_NAME:MODEL_VERSION` commit trailer. `.claude/skills/` contains shallow-review,
  deep-review, targeted-review, mega-review, patch-explainer, heatmap, bug-archaeology, write-reproducer,
  cassandra-injvm-dtest, and tla-plus. The deep review uses a "444-pattern catalog" mined from about 3000
  Cassandra bugs. Sources: [AG]; `.claude/skills/README.md`.
- **Stale website content.** [W:patches] still shows a "4.0 code freeze" table and a 2.1 to trunk merge
  order. [W:how_to_commit] is current: 4.0, 4.1, 5.0, 6.0, then trunk. [W:how_to_review] mentions
  `lib/licences` and "CVH tests", which are older artifacts. Prefer [W:how_to_commit], [W:ci], [C], and [AG].

---

## 1. Workflow

### 1.1 JIRA ticket
- Find or create an issue in the CASSANDRA JIRA before doing the work. [C] step 1; [W:patches] "Before You Start Coding".
- Create the ticket early, link related tickets, and update it with progress and a WIP branch link. [W:patches].
- Major features need discussion on dev@ first. Otherwise they are "likely not accepted". [W:patches] rule of thumb.
- Changes to public APIs (CQL, virtual tables, JMX, yaml, system properties) must follow the approach of the
  existing APIs. Any plan to change an API goes to dev@. [W:code_style] "Public APIs".
- New dependencies need a `[DISCUSS]` thread on dev@ and community consensus first. [W:dependencies]; [AG] "Environment".
- CEPs (Cassandra Enhancement Proposals) cover large features. Commit messages and CHANGES entries
  reference them, for example "Implementation of CEP-49 ... (CASSANDRA-20975)" (`CHANGES.txt`). CEP work
  sometimes lands on feature branches (`cep-45-mutation-tracking`). See the PR #5196 base branch and the
  labeller skill rule `CEP-45`.
- JIRA status workflow: `Triage Needed`, `Open`, `In Progress`, `Patch Available`, `Review In Progress`,
  `Changes Suggested`, `Needs Committer`, `Ready to Commit`, `Resolved`, plus `Awaiting Feedback`, `Testing`,
  and `Requires Testing`. Source: `GET /rest/api/2/project/CASSANDRA/statuses`. "Submit Patch" moves the
  ticket to Patch Available. [W:patches] steps 10 and 12.
- The "Component" field must be set. Mark the ticket "client-impacting" and "doc-impacting" where relevant
  (today this is the `Impacts` field, with values such as `None` and `Clients`). [W:how_to_review] Documentation; JIRA field `customfield_12313922`.

### 1.2 PR and branch conventions
- Suggested branch name: `<name>/CASSANDRA-NNNNN/<base-branch>`, for example `jcshepherd/CASSANDRA-12345/trunk`. [C].
- PR title: "summarize what this PR proposes". [PT]. In practice the title is `CASSANDRA-NNNNN <summary>`
  (recent PRs #5226 to #5235). The `missing-ticket` heuristic in `~/.claude/skills/cassandra-pr-labeller`
  accepts `CASSANDRA-N`, `Cassandra N`, `C-N`, or a bare 5-digit number.
- Open **one PR per target branch**. For example, #5227, #5228, and #5229 are the same ticket against
  trunk, 6.0, and 5.0.
- **PRs are never merged on GitHub.** Committers cherry-pick, then push to gitbox. On GitHub the PR shows as
  *closed, unmerged*. [W:how_to_commit] "Introduction for New Committers". Observed: every recent closed PR
  except one CEP feature-branch PR has `mergedAt=null`.
- Keep the PR description up to date and give a concise reproduction where possible. [PT].
- Squash before commit. Multiple commits are fine during review. Once the patch has its +1, squash it to
  one commit per branch. [W:patches] step 6.

### 1.3 Commit message format
```
<One sentence description, usually Jira title or CHANGES.txt summary, no jira id>

<Optional lengthier description>

patch by <Authors>; reviewed by <Reviewers> for CASSANDRA-#####

Co-authored-by: Name <email>
Assisted-by: AGENT_NAME:MODEL_VERSION
```
Sources: [PT]; [W:how_to_commit] "Commit Message"; [AG] "Git Workflow" (which adds "no jira id" in the first
line and the `Assisted-by` trailer). Nightly contribulyze pages parse this format
(https://nightlies.apache.org/cassandra/devbranch/misc/contribulyze/html/). Use `TBD` for reviewers until
review finishes. [W:patches] step 8. Observed variation: some commits capitalize "Patch by" or use ", reviewed by",
and multiple reviewers are joined with "," or "and". A parser should be lenient.

### 1.4 CHANGES.txt
- Add an entry at the **top of the list** for the version section of the branch, in the form
  ` * <summary> (CASSANDRA-NNNNN)`. [W:patches] step 7; format observed in `CHANGES.txt`.
- **Only user-impacting changes get an entry.** Test-only fixes with no runtime code change need none.
  [W:patches] step 7 (links a dev@ thread).
- Merge-ups record older-branch entries under `Merged from X.Y:` sub-headings in the newer branch's section.
  `CHANGES.txt` (for example "Merged from 6.0:", "Merged from 5.0:", "Merged from 4.0:").
- Committers often add or fix the entry at commit time, so a missing entry in a PR is a soft finding, not a blocker. (Inference from the merge workflow in [W:how_to_commit].)

### 1.5 NEWS.txt
- Update NEWS.txt "if needed". [W:how_to_review] Documentation.
- Each version has `New features`, `Upgrading`, `Deprecation`, and similar subsections (see the `7.0` block
  in `NEWS.txt`). NEWS is needed for new features that operators see, changed defaults, upgrade steps,
  deprecations or removals, and security notes such as the CVE section. (Inference from the NEWS.txt structure.)

### 1.6 Review votes and commit preconditions ([GOV], ratified 2020-06-25)
- "Code modifications must have been reviewed by at least one other contributor."
- "Code modifications require two +1 committer votes (can be author + reviewer)." This means a patch from a
  non-committer needs **two committer +1s**. A committer's own patch needs **one other committer's +1**.
- "Modifications involving only test code require one +1 vote from a non-author committer."
- Code must not be committed while it is under active reasonable discussion, while a committer has
  requested time to review, or while it has an unresolved reasoned committer -1.
- "Code must not be committed before CI results have been provided for **all affected branches**."
- JIRA records reviewers in the `Reviewers` field (`customfield_12313420`) and authors in `Authors`
  (`customfield_12313920`). Reviewers give their "+1" in JIRA comments. Example: CASSANDRA-21700 has the
  comment "+1 thanks for the port".

### 1.7 Branches and merge-up
- Fix the **oldest applicable branch** first. Then forward-merge with `git merge <older> -s ours --log`,
  cherry-pick the branch-specific patch with `-n`, and amend it into the merge commit. Push every branch
  with `git push --atomic`. Chain: `cassandra-4.0 → 4.1 → 5.0 → 6.0 → trunk`. [W:how_to_commit].
- A fix that touches only older branches is still merged up through trunk with an empty "ours" merge. [W:how_to_commit].
- Patch releases on GA branches take **bug fixes only**. Improvements and features go to trunk only.
  https://cwiki.apache.org/confluence/spaces/CASSANDRA/pages/132320437/Release+Lifecycle.
- Contributors should state which versions they verified as affected, patch the lowest branch, and check
  that the patch merges cleanly upward. [W:patches] "Bug Fixes". That page lists obsolete branch names; apply its intent only.
- Committers run `ant realclean && ant jar` on each branch, plus `check` on 5.0 and later, before pushing. [W:how_to_commit].
- Submodule changes such as `modules/accord` (cassandra-accord) are committed and pushed to the submodule
  first. The parent repo then updates its pointer with `.build/sh/bump-accord.sh`. [C] "Working with Submodules"; `.gitmodules`.

### 1.8 AI-assisted contributions and provenance
- The ASF Generative Tooling Guidance (page version Aug 2026) is at
  https://www.apache.org/legal/generative-tooling.html. It requires the following:
  - The tool's terms must not conflict with the Open Source Definition.
  - The output must be uncopyrightable, or contain no third-party material, or contain only third-party
    material under a compatible license with permission.
  - The contributor must take reasonable steps to check for similarity to training data.
  - It recommends a `Generated-by: <tool> <version>` (or Co-authored-by) commit token.
- The Cassandra-specific form is `Assisted-by: AGENT_NAME:MODEL_VERSION`. [AG] "Git Workflow". It appears
  on trunk now, for example `Assisted-by: Claude Code:claude-opus-5` in recent commits.
- [AG] also gives agents these boundaries:
  - Never modify `src/gen-java/`, which is generated from `src/antlr/`.
  - Never modify files in `lib/`.
  - Never commit secrets.
  - Never bypass Checkstyle without a suppression comment that explains why.
  - Ask before changing `src/antlr/Cql.g`.
  - Do not add dependencies without community approval.
  - When fixing a bug, write the regression test first.
  - Provide test coverage for all new or modified code.
- No Cassandra-specific dev@ AI policy thread was found in this research. The ASF guidance and [AG] are the operative texts. (Gap; worth a follow-up search of lists.apache.org.)
- The contributor must be able to license the work: ALv2 clause 5, or an ICLA for large contributions.
  https://www.apache.org/licenses/contributor-agreements.html. Fixed rule: "Contributions must be covered by the Apache License". [W:patches].

---

## 2. Code style and static checks

### 2.1 What `ant check` runs
`build.xml` target `check` depends on `_main-jar, build-test, gen-asciidoc` and runs **`rat-check`**,
**`checkstyle`** (src), and **`checkstyle-test`** (test). The wrapper is `.build/check-code.sh`, or
`.build/docker/check-code.sh <jdk>`. Sources: `build.xml:791`; [AG] "Linting".
- **GitHub Actions** (`.github/workflows/code-check.yaml`) runs `ant check` on JDK 11 and JDK 17 on
  **push to any branch of any fork**. It does not run on `pull_request`, so the results are on the
  *fork's* commit and do not appear in the PR's status rollup (see §5.1).
- `jenkins-check.yaml` (pylint and tests for run-ci, helm and Jenkinsfile validation) and `build-scripts.yaml`
  (shellcheck `-S error`, dash POSIX syntax, script unit tests) run only when `.build/run-ci*`, `.jenkins/`,
  or `.build/` change.
- The Jenkins `lint` stage is `check-code.sh`. `.jenkins/Jenkinsfile` line 200.
- No ecj, SpotBugs, or ErrorProne in the default check. The `eclipse-warnings` target is empty and gated on
  Java 8 (`build.xml:2367`). `ant sonar` exists but is experimental and opt-in (`.build/README.md`). OWASP
  `dependency-check` exists in `.build/build-owasp.xml` and is not part of `check`.
- `checkstyle` also runs during `build` and `jar` unless `-Dno-checkstyle=true` is set. [W:code_style] "Checkstyle".

### 2.2 Checkstyle rules (`.build/checkstyle.xml`; tests use `.build/checkstyle_test.xml`; suppressions in `.build/checkstyle_suppressions.xml`)
Banned APIs, enforced with `RegexpSinglelineJava`, `IllegalImport`, and `IllegalInstantiation`. Each line
shows the banned pattern and its replacement:
- `System.currentTimeMillis` or `nanoTime`: use `Clock.Global` or the `Clock` interface.
- `Instant.now`: use `FBUtilities.now()`.
- `Executors.new*`, `defaultThreadFactory`: use `ExecutorFactory.Global#executorFactory`.
- `MoreExecutors.directExecutor`: use `ImmediateExecutor.INSTANCE`.
- `Path#toFile()`: banned.
- `new Integer(`, `Long`, `Float`, `Byte`, `Double`, `Short`: use `valueOf`.
- `toLowerCase(` and `toUpperCase(`: use `LocalizeString`.
- `System.getenv`, `getProperty`, `setProperty`, `Integer.getInteger`, `Long.getLong`, `Boolean.getBoolean`:
  use `CassandraRelevantProperties` or `CassandraRelevantEnv`.
- Illegal imports: `java.io.File`, `FileInputStream`, `FileOutputStream`, `FileReader`, `FileWriter`,
  `RandomAccessFile`, `java.nio.file.Paths`, the JDK `Semaphore`, `CountDownLatch`, `Executors`,
  `LinkedBlockingQueue`, `SynchronousQueue`, `ArrayBlockingQueue`, `CompletableFuture`, Guava `Futures`,
  `ListenableFuture`, `ListenableFutureTask`, `AbstractFuture`, Netty `Future`, `Promise`,
  `AbstractFuture`, the `junit.framework` package, and `org.jboss.byteman`.
- Illegal instantiation: `ObjectMapper`, `File`, `Thread`, `FutureTask`, `Semaphore`, `CountDownLatch`,
  `ScheduledThreadPoolExecutor`, `ThreadPoolExecutor`, `ForkJoinPool`, `OutOfMemoryError`.
- `var` is banned (`IllegalType`).
- `AvoidStarImport`, `RedundantImport`, and `UnusedImports` apply.
- `MissingDeprecated` applies, and `@Deprecated` **must have `since=`** (`MatchXpath`).
- **Import order** (`ImportOrder`, groups separated by blank lines, sorted, static imports at the bottom):
  `java`, `javax`, `com.`, `net.`, `org.`, `accord.`, `org.apache.cassandra.`, then others, then statics.
  This matches [W:code_style] "Imports".
- Suppressions use `SuppressWithNearbyCommentFilter` comments, and [AG] requires an explanation with each one.

### 2.3 Licence headers (RAT)
- Every new file needs the ALv2 header. Template: `.build/header.txt`. [AG] "Code Style"; `rat-check` in
  `.build/build-rat.xml`. Exclusions include `.claude/**`, `**/*.json`, `**/cassandra*.yaml`, `test/**/*.txt`, and `test/**/*.csv`.

### 2.4 Human style rules ([W:code_style]; not machine-checked)
- Follow Sun conventions as a fallback. Keep a patch's scope to the minimum necessary. Fix whitespace in a separate patch.
- Formatting: braces on new lines, except for empty blocks or a multi-line lambda opener. Braces may be
  elided to depth one. Indent with 4 spaces and no tabs. Aim for lines under 120 characters but use
  judgment. Ternaries split one clause per line with the operator carried.
- Naming: avoid `getX`/`setX` where it makes sense. Use the standard verbs: `computeX` (expensive),
  `lookupX`, `toX`/`asX`/`asXView`, `isX`/`hasX`/`canX`. Keep naming consistent across the project.
- Prefer enums to boolean parameters, dedicated types to `Pair`, and `public final` fields to getters.
- Make fields `final` where possible, but **never mark locals or params `final`**. Use `@Override` always.
  Use `@Nullable`, `@ThreadSafe`, and similar annotations where they apply.
- Delete single-implementation interfaces and unused methods. Don't add `equals`, `hashCode`, or `toString` without a use.
- Exceptions: never write an empty catch or a log-only catch just to satisfy the compiler. Catch the
  narrowest type. If you catch `Throwable`, rethrow it. Wrap unhandled checked exceptions in unchecked ones.
  A deliberately ignored exception needs a comment. Pass Throwables to `JVMStabilityInspector`. [W:how_to_review].
- Logging: use parameterized messages. Guard with `isTraceEnabled()` or `isDebugEnabled()` **only** when
  building the arguments is expensive or uses varargs with more than 2 arguments. Check log levels and avoid
  logging on hot paths. [W:code_style] "Logging"; [W:how_to_review] "Logging".
- Comments should explain *why* and stay short. Add javadoc for complex classes and methods. Mark incomplete code with `TODO`. [AG]; [W:how_to_review].

---

## 3. Testing regime

### 3.1 Test suites (dirs; `.build/run-tests.sh -a <type>`)
| Suite | Location | Notes |
|---|---|---|
| Unit / single-node integration (JUnit, CQLTester) | `test/unit` | `-a test`; variants `test-latest`, `test-cdc`, `test-compression`, `test-oa`, `test-system-keyspace-directory`, `test-tries` |
| In-JVM dtests | `test/distributed` (`o.a.c.distributed.test`, `o.a.c.upgrade`) | `-a jvm-dtest`, `jvm-dtest-upgrade`, `jvm-dtest-novnode`; uses cassandra-in-jvm-dtest-api; upgrade needs `ant dtest-jar` per version |
| Fuzz / Harry | `test/distributed/o.a.c.fuzz`, `test/harry` | property and model-based (Harry) testing |
| Simulator | `test/simulator` | `-a simulator-dtest`; deterministic simulation (Accord, CMS) |
| Burn | `test/burn` | `-a test-burn` |
| Long | `test/long` | `-a long-test` (post-commit only) |
| Microbench (JMH) | `test/microbench` | `ant microbench -Dbenchmark.name=X`; `-a microbench-test` compiles and smoke-runs them in pre-commit |
| Tools | `tools/stress`, fqltool, sstableloader | `stress-test`, `fqltool-test`, `sstableloader-test` |
| cqlsh | `pylib/cqlshlib/test` | `-a cqlsh-test` (pytest) |
| Python dtests | separate repo `apache/cassandra-dtest` (ccm) | `dtest`, `dtest-novnode`, `dtest-offheap`, `dtest-large*`, `dtest-upgrade*`; run-ci takes `-d/-k` for a dtest fork and branch |
Sources: [W:testing]; `.build/README.md`; `.build/run-tests.sh` `TARGET_TYPES`; `test/` listing.
Supported JDKs: 11 (default), 17, and 21 (`build.xml` `java.supported`). CI runs all JDKs a branch supports
by default (`.build/run-ci.d/README.md`).

### 3.2 What to test ([T])
- Unit level: every state transition, illegal transitions (they must throw), all conditional branches
  (including partial matches of compound predicates), range boundaries, and exception handling.
  Do not test implementation details.
- Integration level: messages sent and received, side effects, restart from clean and unclean shutdown,
  dry start, shutdown, and **upgrade with data from a previous version**.
- dtests are black-box tests for cluster and client contracts. They are "not a replacement for proper
  functional java tests". Systems that dtests cover also need granular Java tests.
- Distributed components should be testable in JUnit, with injected dependencies instead of singletons or
  `@VisibleForTesting` protected hooks. Global state is "not an excuse to not test something".
- Test structure: setup, precondition assert, action, postcondition assert.
- Paying down test debt should be proportional to the change. Refactor-heavy, test-light patches "are not likely to get committed".
- Bug fixes: write a regression test that reproduces the failure first. [AG] "Testing".
- How much testing is needed depends on stability risk. Tooling needs less than the storage engine. [W:patches].

### 3.3 CI systems
| System | What | Evidence a tool can read |
|---|---|---|
| GitHub Actions on the fork | `ant check` on JDK 11 and 17 | fork check-runs for the head SHA |
| Pre-commit Jenkins (pre-ci.cassandra.apache.org, an employer clone, or your own via `.build/run-ci --only-setup`) | profile chosen by the author | `ci_summary_<fork>_<branch>_<build>.html` + `results_details_*.tar.xz` **attached to JIRA**; JIRA comment with totals |
| Post-commit Jenkins ci-cassandra.apache.org | `post-commit` profile per branch | Jenkins JSON API; nightlies.apache.org/cassandra; Butler |
| CircleCI (`.circleci/`, still in tree) | legacy; `generate.sh` auto-detects changed tests and **repeats** them (`REPEATED_*_COUNT`, e.g. 500×) | CircleCI links in JIRA comments on older tickets |
Sources: [C]; [W:ci]; `.circleci/readme.md`.

Pipeline profiles (`.jenkins/Jenkinsfile` `pipelineProfiles()`):
- `skinny` (default): lint, cqlsh-test, test, jvm-dtest, simulator-dtest, dtest.
- `pre-commit`: artifacts, lint, debian, redhat, fqltool-test, sstableloader-test, cqlsh-test, test,
  test-latest, stress-test, test-burn, jvm-dtest, simulator-dtest, dtest, dtest-latest, microbench-test.
- `pre-commit w/ upgrades`: pre-commit plus jvm-dtest-upgrade, dtest-novnode, and dtest-upgrade.
  **Required whenever the patch could affect upgrades, serialization, or on-disk formats.** [W:ci] "Profiles".
- `post-commit`: everything, 140k to 200k tests. Adds test-cdc, test-compression, long-test, test-oa,
  dtest-large*, and dtest-upgrade-large*.
- `packaging`: for build or packaging-only changes. `custom -e <regexp>`: a subset.

Expectations:
- "Every patch is expected to carry" the CI artifacts. Contributors without CI access say so on the ticket,
  and the reviewer or committer runs CI. [C]; [W:patches] step 4; [W:testing].
- Reviewers check "pre-commit CI results attached to the ticket, for all affected branches (up to trunk, if
  applicable)? Are there any regressions?" [W:how_to_review] Testing. [GOV] makes CI for all branches a hard precondition.
- Failures are triaged against Butler (https://butler.cassandra.apache.org) and JIRA to tell new regressions
  from known flaky tests. A new post-commit failure caused by the patch needs a JIRA ticket. [W:ci] "Post-commit CI".
- A pre-commit run with some failures (for example "Passed 113880, Failed 16", UNSTABLE) is normal. The
  author or reviewer is expected to show the failures are pre-existing or flaky. Example: CASSANDRA-21700 comments and attachments.
- Repeated runs of new or modified tests (the "multiplexer"): use `.build/run-tests.sh -a <type>-repeat -t
  <Class> -e REPEATED_TESTS_COUNT=N` (`.build/README.md` "Repeating tests"). The CircleCI `generate.sh` does
  this automatically for changed tests. The Jenkins pre-commit profiles **do not** repeat tests. Reviewers
  commonly expect evidence that new or changed flaky-prone tests (dtests, timing-sensitive tests) pass
  repeatedly. (The expectation is convention; I found no current doc that requires it.)
- Performance: if the patch affects the read or write path, test for performance regressions with multiple
  workloads. [W:how_to_review]. Performance claims "must be measurable" (JMH, cassandra-stress, NoSQLBench). [W:testing] "Performance Testing".
- Coverage: `ant codecoverage -Dtaskname=testsome ...` writes JaCoCo output to `build/jacoco`. [W:testing]. It is optional, not gating.

---

## 4. Review criteria ([W:how_to_review], plus compatibility rules from other sources)

**General.** Code style is followed. No redundant or duplicate code. Code is modular. Singletons are
avoided. Library functions are used where possible. Units of measurement are consistent.

**Error handling.** Inputs and outputs are validated for type, length, format, and range. Errors from
third-party code are caught. Invalid parameters are handled. Throwables go to `JVMStabilityInspector`.
Error messages tell the user how to proceed. Exceptions propagate to the right level.

**Documentation.**
- Comments explain *why*. Javadoc is present where appropriate. Edge cases, units, and data structures are explained.
- No incomplete code without a `TODO`.
- **NEWS.txt, the CQL docs (`doc/cql3/`, `doc/modules/cassandra/pages/developing/cql/`), and the native
  protocol spec (`doc/native_protocol_v*.spec`) are updated when needed.**
- The JIRA ticket has the client- and doc-impact flags and its Component set.
- New third-party libraries are Apache-compatible. Since 5.0, dependencies live in the `.build/*-template.xml`
  POMs and need dev@ consensus. [W:dependencies]. `lib/licenses` is gone from trunk.

**Testing.**
- Code is testable. Tests exist, are comprehensive, and actually exercise the behavior.
- Tests reuse CQLTester, dtest, and ccm helpers.
- Multi-node behavior has (in-JVM or Python) dtests. Long-running behavior has long or fuzz tests.
- Pre-commit CI is attached for every branch with no regressions.
- Changes to the read or write path have been perf-tested.
- New features are validated against their SLA and use case.

**Logging.** Levels are right. Nothing on the critical path hurts performance. Logging is useful for
troubleshooting. Unnecessary statements are removed.

**Compatibility.** These are fixed rules: "Changes must not break compatibility between different Cassandra
versions" and "Patches will only be applied to branches by following the release model". [W:patches].
Concrete surfaces a reviewer checks:
- **Internode messaging:** `MessagingService.Version` (VERSION_30, 3014, 40, 50, 60). Serializers must
  branch on version and handle mixed-version clusters. Serializer coverage: `*SerializationsTest`, with
  golden data in `test/data/serialization/<ver>/`.
- **SSTable format:** `BigFormat` / BTI versions ("nb", "oa", "pa"), gated by `storage_compatibility_mode`
  (NEWS.txt explains the CASSANDRA_4 / UPGRADING / NONE rollout). On-disk changes need upgrade tests and the
  `pre-commit w/ upgrades` profile. [W:ci].
- **Native protocol:** spec files in `doc/native_protocol_v{3,4,5}.spec`. Behavior must be gated by
  `ProtocolVersion`. Drivers are affected, so set the client-impacting flag.
- **Config:** `conf/cassandra.yaml` and **`conf/cassandra_latest.yaml`** (both shipped), and `Config.java`.
  `ConfigCompatibilityTest` checks against `test/data/config/version=*.yml`. Renames need the
  backward-compatible `@Replaces` and converters. `LoadOldYAMLBackwardCompatibilityTest` covers old yaml.
  Any yaml or system-property addition is a public API. [W:code_style]. New system properties go through
  `CassandraRelevantProperties` (checkstyle). Docs are generated from these sources by `ant gen-asciidoc`.
- **nodetool:** help text fixtures in `test/resources/nodetool/help/**`, checked by
  `NodetoolHelpCommandsOutputTest`. Autocompletion is generated at build time (CASSANDRA-20794). Commands need docs.
- **JMX and metrics:** MBean interfaces are checked by `JMXStandardsTest`. A metric or MBean rename or
  removal breaks operators and needs deprecation (`@Deprecated(since=...)`, enforced by checkstyle) and NEWS.
- **Virtual tables:** `src/java/org/apache/cassandra/db/virtual`. They are public API ([W:code_style]).
  Exposure defaults matter; see CASSANDRA-21720.
- **CQL grammar:** `src/antlr/*.g`, including `Cql.g`. Changes "cascade widely"; ask first. [AG]. CQL docs
  must be updated, and reserved keywords live in `src/resources/.../reserved_keywords.txt`.
- **Guardrails, defaults, security:** changing a default or a guardrail semantic needs NEWS "Upgrading"
  (for example CASSANDRA-21517, "zero treated as zero"). Security model: `SECURITY.md` →
  `doc/modules/cassandra/pages/reference/security-model.adoc`.

**Process and scope.**
- Patches limit their scope to the minimum necessary. [W:code_style].
- Less complex patches are reviewed faster; split large work. [W:patches].
- Bug fixes take priority over features. Release branches take bug fixes only (Release Lifecycle).

**In-tree AI review methodology** (`.claude/skills/`): reviewers pick a skill by patch size:
shallow-review for small patches, targeted-review for 50 to 1000 LOC, and mega-review above 1000 LOC.
shallow-review uses six specialist lenses: logic and types, boundaries and I/O, concurrency and state,
resources and serialization, absence, and API completeness. targeted-review has category files for
serialization-and-versioning, lifecycle-and-ordering, concurrency-and-locking, io-and-crash-safety,
state-and-resource-cleanup, boundaries-and-numbers, null-and-type-safety, validation, refactor-aftermath,
and api-contracts-and-completeness. These are the project's own encoded bug patterns and should be reused,
not reinvented.

---

## 5. Data sources a tool can pull

### 5.1 GitHub (no auth needed for public reads, but auth raises rate limits)
- PR metadata: `gh pr view N -R apache/cassandra --json title,body,baseRefName,headRefName,headRefOid,headRepositoryOwner,headRepository,author,labels,files,commits,reviews,comments,state,mergedAt`.
- Diff: `gh pr diff N -R apache/cassandra`, or `GET /repos/apache/cassandra/pulls/N/files` (paginated, patch per file).
- **Checks: the PR's `statusCheckRollup` is usually empty.** The Actions runs live on the fork. Query
  `GET /repos/{headOwner}/{headRepo}/commits/{headSha}/check-runs`. Verified: PR #5226 returned
  `ant-check-jdk11` and `ant-check-jdk17` as success. They are missing if the fork has Actions disabled.
- Sibling PRs for other branches: search `repo:apache/cassandra is:pr "CASSANDRA-NNNNN"`.
- Landed commit: the JIRA `Source Control Link` field (`customfield_12313924`), or search trunk commits for
  `for CASSANDRA-NNNNN`. A closed PR with `mergedAt=null` may still be committed.
- Base-branch files to diff against: `CHANGES.txt`, `NEWS.txt`, `.build/checkstyle*.xml`, and the conf yamls
  (via `gh api repos/apache/cassandra/contents/<path>?ref=<base>`).

### 5.2 JIRA (`https://issues.apache.org/jira/rest/api/2/`; anonymous read works)
- `issue/CASSANDRA-N?expand=names` gives these fields: `status`, `resolution`, `fixVersions`,
  `customfield_12311420` *Since Version*, `components`, `issuetype`, `priority`, `assignee`,
  `customfield_12313920` **Authors**, `customfield_12313420` **Reviewers**, `customfield_12313823`
  **Test and Documentation Plan** (free text, often lists the tests run), `customfield_12313922` **Impacts**
  (None / Clients / Docs), `customfield_12313821` Complexity, `customfield_12313820` Severity,
  `customfield_12313825` Bug Category, `customfield_12313822` Discovered By, `customfield_12313924` Source
  Control Link, `attachment[]`, and `comment.comments[]`.
- **CI evidence:** `attachment[].filename` matches `ci_summary_<fork>_<branch>_<build>.html` and
  `results_details_*.tar.xz`. Branch names in the filename show which branches were tested. The summary HTML
  (around 6 MB) contains `sha:`, `repo:`, `branch:`, `profile:`, `[Totals] Passed N Failed N Skipped N`, and a
  `[Test Failures]` list. Parse it with an HTML parser and do not execute it. Comments often summarize the
  same data, for example "UNSTABLE, ... profile pre-commit w/ upgrades. Passed 113880 – Failed 16".
- **+1s:** scan comments for `+1`, and compare the commenters with the Reviewers field and the committer list
  (https://projects.apache.org/committee.html?cassandra, or `https://whimsy.apache.org/public/public_ldap_projects.json`).
- `remotelink` is usually empty. PR links show up in comments or worklogs from "ASF GitHub Bot" and in the Development field.
- `project/CASSANDRA/statuses` lists the workflow states (§1.1).

### 5.3 CI and flaky-test history
- Post-commit Jenkins JSON: `https://ci-cassandra.apache.org/job/Cassandra-<branch>/lastCompletedBuild/api/json`. Verified: trunk build 2627 was UNSTABLE.
- Archive: https://nightlies.apache.org/cassandra/.
- Butler is a Vue SPA with an undocumented JSON API under `/api/`. `GET /api/ci/jobs/upstream` works. Other
  paths are `/api/upstream/failures/...` and `/api/upstream/compare/...`. Treat it as unstable and best-effort.
- Pre-commit Jenkins instances (pre-ci.cassandra.apache.org and private clones) may need auth or be private.
  The JIRA attachments are the canonical record. [W:ci].

---

## 6. Checklist candidates

Tags: **[automatable]** = deterministic from APIs or diff · **[heuristic/LLM]** = judgment over diff and
context · **[human-only]** = needs a committer's decision.

**Ticket and metadata**
1. PR title or branch references a CASSANDRA-NNNNN ticket that exists in JIRA. [automatable]
2. JIRA status is consistent with review stage (Patch Available / Review In Progress / Needs Committer / Ready to Commit). [automatable]
3. JIRA Component(s) set. [automatable]
4. JIRA Fix Version(s) set and consistent with the PR's base branch(es). [automatable]
5. JIRA issue type vs target branch: Improvement/New Feature targeting a GA release branch (≤6.0 once GA) is flagged — features go to trunk only. [automatable]
6. Bug ticket has Since Version and the patch targets the oldest affected maintained branch. [heuristic/LLM]
7. Sibling PRs (or branches) exist for every branch in Fix Version(s), from oldest affected to trunk. [automatable]
8. JIRA "Test and Documentation Plan" field filled in. [automatable]
9. Impacts field (Clients/Docs) set when diff touches protocol, CQL grammar, config, nodetool, JMX, metrics, or virtual tables. [automatable]
10. New feature or public API change has a linked dev@ DISCUSS thread or CEP. [heuristic/LLM]
11. New dependency (changes to `.build/*-template.xml` POMs or `lib/`) has a dev@ DISCUSS reference and an ALv2-compatible license. [automatable] detection / [human-only] approval

**Commit and changelog**
12. Commit message first line is a single sentence without the JIRA id; there is a `patch by …; reviewed by … for CASSANDRA-N` line (TBD allowed pre-review). [automatable]
13. Co-authors use `Co-authored-by:` trailers. [automatable]
14. AI assistance disclosed with `Assisted-by:` (or ASF `Generated-by:`) when used; PR body/commits mention of AI tooling cross-checked. [automatable] presence / [heuristic/LLM] for undisclosed use
15. Commits squashed to one per branch before commit (multiple acceptable during review — report, don't fail). [automatable]
16. CHANGES.txt entry present at top of the correct version section, format ` * <summary> (CASSANDRA-N)`, when runtime code changed. [automatable]
17. CHANGES.txt entry absent or optional for test-only or build-only changes (don't penalize). [automatable]
18. NEWS.txt updated when defaults, config semantics, upgrade steps, deprecations, or user-visible features change. [heuristic/LLM]
19. PR description is current and includes reproduction steps for bug fixes. [heuristic/LLM]

**Static checks and style**
20. Fork `ant-check-jdk11` and `ant-check-jdk17` check-runs passed on head SHA (or flag unknown). [automatable]
21. New files carry the ALv2 header (RAT). [automatable]
22. No banned APIs in added lines (System time, Instant.now, Executors, File/Paths, toLowerCase/toUpperCase, System.getProperty/getenv, boxed constructors, `var`, JDK futures and latches). [automatable]
23. Import order and grouping matches checkstyle; no star, unused, or redundant imports. [automatable]
24. `@Deprecated` has `since=`. [automatable]
25. New checkstyle suppressions carry an explanatory comment. [automatable] detection / [heuristic/LLM] adequacy
26. No edits to `src/gen-java/` or `lib/`; `src/antlr/Cql.g` edits flagged for discussion. [automatable]
27. Tabs, trailing whitespace, and unrelated reformatting in the diff (scope creep). [automatable]
28. Brace placement, `final` on locals or params, missing `@Override`, and lines much longer than 120. [automatable] (approximate)
29. Naming, enum-vs-boolean, Pair usage, single-impl interfaces, and unused methods. [heuristic/LLM]
30. Exception handling: no swallowed or log-only catches; Throwable rethrown; JVMStabilityInspector used. [heuristic/LLM]
31. Logging levels, hot-path logging, and `isXEnabled` guards only where needed. [heuristic/LLM]
32. Comments explain why, javadoc on complex new public classes, no stray TODO without ticket. [heuristic/LLM]

**Tests**
33. Production code changed ⇒ test code changed or added in the same PR. [automatable]
34. Bug fix includes a regression test that would fail without the fix. [heuristic/LLM] (or [automatable] if the tool runs it)
35. Test type fits the change: multi-node behavior has jvm-dtest or python dtest; storage or serialization change has upgrade test. [heuristic/LLM]
36. New tests follow setup, precondition, action, postcondition; cover branches, boundaries, and illegal states. [heuristic/LLM]
37. Tests reuse CQLTester, in-JVM dtest, or Harry utilities instead of ad-hoc harnesses. [heuristic/LLM]
38. Paired cassandra-dtest PR exists when python dtests were changed or needed. [automatable] (search) / [heuristic/LLM]
39. Evidence of repeated runs (`*-repeat`, CircleCI multiplexer) for new or modified timing-sensitive tests. [automatable] (JIRA comments) / [heuristic/LLM]
40. Microbenchmark or perf data provided for performance claims or read/write-path changes. [heuristic/LLM]

**CI evidence**
41. `ci_summary_*.html` and `results_details_*.tar.xz` attached to JIRA. [automatable]
42. CI attached for **every** affected branch (branch names in attachment filenames vs Fix Versions or sibling PRs). [automatable]
43. CI SHA matches the PR head SHA (stale CI flagged). [automatable]
44. CI profile is adequate: `pre-commit` minimum; `pre-commit w/ upgrades` when messaging, sstable, commitlog, hints, schema serialization, or system tables change. [automatable]
45. Failures listed in ci_summary are pre-existing or flaky (cross-check Butler or post-commit Jenkins or JIRA), with new failures explained. [heuristic/LLM]
46. Contributor without CI access stated so on the ticket (acceptable substitute for 41). [automatable]

**Compatibility and public surface**
47. Diff touches `MessagingService`, `*Serializer`, or `IVersionedSerializer` ⇒ version-gated logic and serialization tests present. [heuristic/LLM]
48. SSTable, commitlog, or hints format change ⇒ version bump, `storage_compatibility_mode` gating, upgrade tests. [heuristic/LLM]
49. Native protocol change ⇒ `doc/native_protocol_v*.spec` updated, ProtocolVersion-gated. [automatable] detection / [heuristic/LLM]
50. CQL grammar or semantics change ⇒ CQL docs updated, reserved keywords considered. [automatable] detection / [heuristic/LLM]
51. New or renamed config ⇒ `cassandra.yaml` **and** `cassandra_latest.yaml` updated, `Config.java` consistent, `@Replaces` for renames, ConfigCompatibility data unaffected. [automatable] partial
52. New system property goes through `CassandraRelevantProperties`. [automatable]
53. nodetool command change ⇒ help fixtures under `test/resources/nodetool/help/` updated, docs updated. [automatable]
54. JMX, metrics, or virtual-table change ⇒ no silent rename or removal; deprecation path; docs. [heuristic/LLM]
55. Default value or guardrail semantic changed ⇒ NEWS.txt Upgrading note. [heuristic/LLM]
56. Generated docs (`ant gen-asciidoc`) affected inputs touched ⇒ docs consistent. [heuristic/LLM]

**Correctness and quality** (reuse `.claude/skills/*-review` categories)
57. Concurrency and locking, lifecycle and ordering, resource cleanup, IO and crash safety, boundaries and numbers, null safety, validation, refactor aftermath, API completeness. [heuristic/LLM]
58. Patch scope is minimal and focused on the ticket; unrelated refactors split out. [heuristic/LLM]
59. Patch size suggests splitting (for example >1000 LOC without CEP). [automatable] signal / [human-only] decision
60. Security-sensitive change (auth, TLS, UDF, JMX exposure) assessed against the security model. [heuristic/LLM]

**Governance (report only)**
61. Count of committer +1s on JIRA or PR: two committer votes needed (author may be one); test-only changes need one non-author committer +1. [automatable] (needs committer roster)
62. Outstanding committer -1, or "requested time to review", not yet resolved. [heuristic/LLM]
63. Final merge decision, backport scope, and design acceptability. [human-only]
