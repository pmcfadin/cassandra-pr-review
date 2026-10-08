# Build and coverage section: research

Input for roadmap item 6 (`build-and-coverage`). Everything below was run on 2026-10-07 on an Apple-silicon Mac (10 cores, 32 GB, macOS 26.6), ant 1.10.14. JDKs: Temurin 17.0.13 (sdkman, pre-installed), Temurin 11.0.32 (installed for this research, see 1.2), Homebrew OpenJDK 21 and 26 (present, not used). Scratch work lived in `.work/build-research/` (gitignored); all worktrees were removed afterwards. No repo code was changed.

Test subjects: PR 5201 (base `cassandra-4.0`, head `d1095cbd`, `SSTable.java` +8/-11, no tests) and PR 5212 (base `trunk`, merge-base `ce537027`, head `cff64233`, 9 src files, 10 added lines, no tests). PR 4967 (trunk, 173 files) was used for test selection only.

## Findings in one table

| Question | Answer |
|---|---|
| JDK per branch | trunk and 6.0: 11, 17, 21. 5.0: 11, 17. 4.1 and 4.0: 11 (and 8, not installed). The build refuses anything else (`Unsupported JDK version used: 26`; 4.0 on JDK 17 dies in `build.xml:202`, Nashorn removed). 4.0/4.1 on JDK 11 also need `CASSANDRA_USE_JDK11=true`. |
| Cheapest JDK set | Install one JDK 11 (`sdk install java 11.0.32-tem`). Then 11 runs 4.0/4.1/5.0/6.0, 17 runs 5.0/trunk/6.0. JDK 8 is not needed. |
| Build cost | Clean with warm Maven cache 30 to 70 s; no-op 6 to 12 s; one-file incremental 6 to 13 s. Disk 300 to 750 MB per worktree. |
| Network | First build downloads jars (~50 MB, resolver, Maven Central) into `~/.m2`. After that offline works. Trunk and 6.0 also clone the `modules/accord` submodule from github.com during `init`. |
| Coverage | `ant jacoco-run -Dtaskname=testclasslist -Dtest.classlistfile=F` then `ant jacoco-report`. Same on all four branches. XML at `build/jacoco/report.xml`, 5 to 8 s. |
| Changed-line coverage | 62-line stdlib script joining `git diff -U0` with JaCoCo XML. 0.5 s. 5201: 7 of 7 added executable lines covered. 5212: 0 of 10. |
| Test selection | stdlib script, 3 s. Ranks tests by: changed by PR, `FooTest` name, references to the class, calls to the changed method. Cap 25 to 30. |
| Cost per PR | Small PR with 12 to 25 test classes: ~1 min build (reused) + 3 to 4 min tests + 10 s report. |
| Two blockers on Apple silicon | (1) 4.0 bundles JNA 5.6.0 with no arm64 macOS library: every test that touches `Memory` fails. Fix: overwrite `lib/jna-5.6.0.jar` with 5.13.0 after resolve. (2) trunk's `init` installs git hooks into the shared `.git` (section 6.1). |
| Security | Real. Recommended: sandbox-exec profile (no external network, writes only to the worktree and a Maven repo clone), committer PRs or owner approval, separate build clone. Section 6. |

## 1. Per branch

### 1.1 Targets

| Branch | `java.supported` (build.xml) | Build | Build tests | Notes |
|---|---|---|---|---|
| trunk (7.0) | `11,17,21` | `ant jar` | `ant build-test` | Needs submodule `modules/accord` (git clone from github.com) and a gradle run (~13 s first, 5 s later). On 4.0, `ant jar` also compiles the tests (`_build-test` in its log); elsewhere run `build-test` explicitly. |
| cassandra-6.0 | `11,17,21` | same | same | Appears as a PR base (5228). Not built here. |
| cassandra-5.0 | `11,17` | `ant jar` | `ant build-test` | JDK 17 needs no extra flag. |
| cassandra-4.1 | none in file; JDK 8 or 11 | `ant jar` | `ant build-test` | `CASSANDRA_USE_JDK11=true` on 11. Runs checkstyle on JDK 8 only. JNA 5.9.0. |
| cassandra-4.0 | none in file; JDK 8 or 11 | `ant jar` | `ant build-test` | `CASSANDRA_USE_JDK11=true` on 11. JNA 5.6.0 (arm64 problem). |

Failure when the flag is missing (4.0, JDK 11): `-Duse.jdk11=true or $CASSANDRA_USE_JDK11=true must be set when building from java 11`. On JDK 17: `Java 15 has removed Nashorn... Unable to create javax script engine`. On trunk with JDK 26: `Unsupported JDK version used: 26`. All three are immediate (under 1 s) and exit 1.

### 1.2 JDKs on this machine

`sdk list java` showed only 17.0.13-tem installed. Homebrew has `openjdk` (26) and `openjdk@21`. JDK 11 was missing; one install covered the rest:

```bash
sdk install java 11.0.32-tem        # 41 s. It answered the "set default?" prompt with yes; undo with:
sdk default java 17.0.13-tem
```

JDK 8 was not needed. If 4.0/4.1 ever require it: `sdk install java 8.0.504-amzn` (arm64 build). The pipeline should pick `JAVA_HOME` per base branch from a small table and report `unknown (JDK X missing: run <sdk install ...>)` when the directory is absent.

### 1.3 Timings (wall clock, `ant` run directly)

"Clean warm" means `rm -rf build` with the Maven cache already populated. "Incremental" means `touch` of one source file.

| Branch (JDK) | Cold first build | Clean, warm | No-op | Incremental 1 file | `build/` size | Worktree total |
|---|---|---|---|---|---|---|
| 4.0 (11), `ant jar` | 58 s (downloaded ~47 MB) | 29.5 s | 9.2 s | 9.5 s | 142 MB | 307 MB |
| 4.1 (11), `ant jar` then `build-test` | 46 s | 33.6 s | 6.8 s | 7.3 s | 170 MB | 347 MB |
| 5.0 (17), `ant jar` then `build-test` | 46 s | 42.5 s | 5.5 s | 6.1 s | 214 MB | 414 MB |
| trunk (17), `ant jar` then `build-test` | 80 s (submodule clone + gradle) | 67 s | 11.7 s | 12.7 s | 257 MB | 532 MB |

Maven cache: `~/.m2/repository` is 279 MB for all four branches together. Each worktree also keeps its own `lib/` and `build/lib/jars` (50 to 70 MB). Run-time artifacts add up: after a 12-class JaCoCo run on trunk `build/jacoco` was 150 MB (HTML 100+ MB, `report.xml` 32 MB). Delete the HTML after parsing the XML.

### 1.4 Offline

After the first run, the sandboxed build (no external network) succeeded. Two conditions:

- The resolver and a few `<get skipexisting>` tasks need write access to the Maven repo. Pass `-Dlocal.repository=<dir>` and point it at a copy-on-write clone of the warm cache: `cp -cR ~/.m2/repository $RUN/m2` (APFS clone, 0.8 s for 279 MB). This keeps the real `~/.m2` read-only for the PR.
- Trunk/6.0 need `modules/accord` present. Either let the (trusted) pre-step run `git submodule update --init` or clone it once and copy it (`cp -cR` of a built base worktree worked).

## 2. JaCoCo

### 2.1 Targets (same on 4.0, 4.1, 5.0, trunk; JaCoCo 0.8.6 on 4.x, 0.8.8 on 5.0/trunk)

| Target | What it does |
|---|---|
| `ant jacoco-run -Dtaskname=<target>` | Runs `<target>` (default `test`) with `-javaagent:build/lib/jars/jacocoagent.jar=destfile=build/jacoco/partials/partial.exec` added to every forked test JVM (`usejacoco=yes`). |
| `ant jacoco-merge` | Merges `build/jacoco/**/*.exec` into `build/jacoco/jacoco.exec`. |
| `ant jacoco-report` | Merge plus report over `build/classes/main` and `src/java`, `src/gen-java`. Writes `index.html`, `report.csv`, `report.xml` in `build/jacoco/`. |
| `ant codecoverage` | `jacoco-run` then `jacoco-report` (the full unit suite; hours; not for us). |
| `ant jacoco-cleanup` | Deletes `build/jacoco`. |

There is no ant switch to restrict the report to some classes. The XML always covers all ~4000 classes (17 MB on 4.0, 32 MB trunk); filter in Python.

### 2.2 Choosing tests: a list of classes

`testsome` runs exactly one class (`-Dtest.name=<FQCN> [-Dtest.methods=a,b]`) and `test -Dtest.name=<glob>` takes an ant glob (`**/${test.name}.java`), neither takes a list. The list form is `testclasslist`, with a file of paths relative to `test/unit`:

```
org/apache/cassandra/db/lifecycle/LogTransactionTest.java
org/apache/cassandra/io/sstable/SSTableWriterTest.java
```

```bash
export JAVA_HOME=~/.sdkman/candidates/java/11.0.32-tem CASSANDRA_USE_JDK11=true   # 4.0 example
ant jar                                         # or build-test on 4.1+/trunk
# 4.0 only, after resolve: swap in a JNA with an arm64 macOS library (see 2.4)
cp ~/.m2/repository/net/java/dev/jna/jna/5.13.0/jna-5.13.0.jar lib/jna-5.6.0.jar
cp lib/jna-5.6.0.jar build/lib/jars/jna-5.6.0.jar
ant jacoco-run -Dno-build-test=true -Dtaskname=testclasslist -Dtest.classlistfile=$PWD/tests.txt
ant jacoco-report -Dno-build-test=true
```

`-Dno-build-test=true` matters: without it every `ant` call re-runs the resolver, which copies the old JNA over the patched jar. The class list file path must be absolute. Other knobs: `-Dtest.timeout=<ms>` per class (4.0 default 240000, trunk 480000), `-Dtest.methods` only for `testsome`.

### 2.3 Where output lands

| Item | Path |
|---|---|
| Raw coverage | `build/jacoco/partials/partial.exec` (appended by every test JVM; 0.5 MB for 3 classes) |
| Merged | `build/jacoco/jacoco.exec` |
| Line-level XML | `build/jacoco/report.xml` (`<package name><sourcefile name><line nr mi ci mb cb/>`) |
| JUnit results | `build/test/output/TEST-<class>.xml` (trunk: `TEST-<class>-_jdk17.xml`). Root `<testsuite tests failures errors skipped time>`. |
| Console | `[junit-timeout] Testsuite: <class> Tests run: N, Failures: F, Errors: E, Skipped: S, Time elapsed: T sec` |

`ci`/`mi` = covered/missed instructions, `cb`/`mb` = covered/missed branches, per source line. Lines absent from the XML are not executable (comments, braces, declarations).

### 2.4 Run on PR 5201 (4.0, JDK 11, head `d1095cbd`)

| Step | Wall time |
|---|---|
| `ant jar` clean, warm cache | 29.5 s |
| `jacoco-run` with LogTransactionTest + SSTableWriterTest + SSTableReaderTest (72 tests, all passed) | 36 s (1 JVM start per class; test time 8.7 + 16.8 + 7.4 s) |
| `jacoco-report` (3944 classes) | 5 s |
| changed-line coverage script | 0.5 s |
| Same, with the macOS sandbox (section 6.3) | build 33 s, tests 40 s, report 6 s |
| 25 auto-selected classes (section 3), sandboxed | 223 s |

First attempt failed on every test: `Could not initialize class com.sun.jna.Native` (plus noisy `netty_tcnative_osx_aarch_64` warnings, which are harmless). `jna-5.6.0.jar` has only `darwin/libjnidispatch.jnilib` (x86_64). JNA 5.9+ ships `darwin-aarch64`; 4.1 uses 5.9.0 (not run), 5.0/trunk use 5.13.0 (trunk tests ran clean). For 4.0 the fix above works but must be applied after every resolve. The patched jar sits in a throwaway worktree, never in the repo.

### 2.5 Run on a trunk PR (5212, JDK 17, 12 selected classes)

| Step | Wall time |
|---|---|
| Base build (`ce537027`), `ant build-test` | 70 s |
| PR build reusing the base `build/` (section 5.4), 14 files recompiled | 23 to 24 s |
| `jacoco-run`, 12 classes, 237 tests, all passed (sandboxed) | 187 s (AutoRepairParameterizedTest alone 91 s) |
| `jacoco-report` | 8 s |

## 3. Choosing tests

### 3.1 Algorithm (prototype `proto/select_tests.py`, stdlib, 95 lines, 2 to 22 s)

Input: worktree, base sha, head sha. Output: a ranked list and the `testclasslist` file.

1. Changed src classes: basenames of changed `src/java/**/*.java`. Changed method names: the nearest method declaration above each added line (git's own hunk header only shows the class for indented Java, so the script scans the head file).
2. Candidate pool: every `*Test.java` under `test/unit` (735 files on 4.0, 1724 on trunk) that contains `@Test`, `@RunWith` or extends `CQLTester` (this drops abstract bases).
3. Score per candidate (points add up):

| Signal | Points |
|---|---|
| The PR added or changed this test file | 1000 |
| Name is exactly `<Class>Test` | 500 |
| Name is `<Class><Capital>...Test` (prefix) | 15 |
| Word-boundary references to a changed class | 2 per hit, max 30 |
| Calls a changed method name, when it also references the class | 5 per hit, max 30 |
| References a direct subtype of a changed class (`SSTable` -> `SSTableReader`) | 1 per hit, max 15 |

4. "Hub" classes (referenced by more than 8% of all tests, for example `DatabaseDescriptor` on 4967) are ignored for the reference signals.
5. Keep the top `--cap` (default 25) with score at least `--min-score` (default 15).

Skipped on purpose: `test/distributed` (in-JVM dtests, minutes each, multi-node, need extra loopback addresses on macOS), `test/long`, `test/burn`, `test/simulator`, `test/microbench`, `test/memory`, and the Python dtests (separate repo, need ccm). A PR that adds such a test gets it listed under `skipped.non_unit` and the report says "not run: needs the dtest suite". Variant suites (`test-compression`, `test-cdc`, `test-system-keyspace-directory`) are not run.

### 3.2 Measured

| PR | Src classes | Unit test files | Candidates scored | Selected (cap 25) | Notes |
|---|---|---|---|---|---|
| 5201 (4.0) | 1 | 735 | 110 | 25 | No FooTest. Ranking from subtype and method signal: SSTableReaderTest, CompactionTaskTest, SSTableRewriterTest, SSTableWriterTest, ..., LogTransactionTest at rank 13. |
| 5212 (trunk) | 9 | 1724 | 123 | 25 (12 used) | 4 `FooTest` hits (AsyncStreamingInputPlusTest, AutoRepairTest, LocalLogTest, NewGossiperTest), then CompactionManager callers. |
| 4967 (trunk) | 85 | 1709 | 1546 | 25 | 32 tests changed by the PR (8 more non-`*Test` helper files and 33 dtest/simulator/burn files skipped), 18 `FooTest` matches. Before hub filtering and the min-score cut it picked 1546, which is useless. |

Run cost of the 5201 selection: 25 classes, 223 s, all green except 2 sandbox artifacts (6.2). Median class 8 s, longest SSTableCorruptionDetectionTest 24 s and CleanupTest 20 s.

### 3.3 Caps

- Class count: 25 (30 when the PR itself adds tests, they are always first).
- Time: keep a per-class duration table keyed by class name from previous `TEST-*.xml` (`time` attribute) and stop adding classes when the estimate exceeds the budget (suggest 10 min per PR). Unknown classes count as 15 s. Not built yet.
- Per-class timeout `-Dtest.timeout=240000`; overall wall cap in the runner (5.3).

Known limits: the signals are textual. A test that reaches the changed code only through other classes is missed (5201's LogTransactionTest ranks 13 only because it also mentions `SSTableReader`). JaCoCo itself is the check: if changed lines come back "missed", the report says "selected tests did not reach these lines", which is not the same as "PR is untested".

## 4. Changed-line coverage

Prototype `proto/changed_cov.py` (62 lines, 0.5 s on a 17 to 32 MB XML):

1. `git diff -U0 --no-renames <base> <head> -- src/java`, collect new-file line numbers per `+++ b/...java`.
2. Parse `report.xml` with `iterparse`; for the wanted `<package>/<sourcefile>` keep `{nr: (mi, ci, mb, cb)}`.
3. For each added line: no entry means not executable; `ci == 0 and cb == 0` means missed; `ci > 0` with `mi > 0` or `mb > 0` means partial (executed, some instructions or branches never); otherwise covered.

Use the PR head's `src/java`, not the base: line numbers come from the head and the classes were built from the head. For a PR that targets a different base branch than the one built, diff against the merge-base.

PR 5201, 3 test classes, JSON trimmed:

```json
{"files": {"src/java/org/apache/cassandra/io/sstable/SSTable.java": {
    "covered": [114,115,116,117,118,120,121], "partial": [], "missed": [],
    "nonexec": [112,113,119], "in_report": true}},
 "total": {"covered": 7, "partial": 0, "missed": 0, "nonexec": 3, "executable": 7, "pct_executed": 100.0}}
```

The same result with 25 selected classes (so the extra 22 added no coverage here). PR 5212 (12 classes): 9 files, 10 executable added lines, all `missed` (`CompactionManager.java:353`, `NewGossiper.java:86-87`, `HintsDispatcher.java:477`, `PathUtils.java:391`, `AsyncStreamingInputPlus.java:210`, `AutoRepair.java:365`, `AccordResult.java:92`, `LocalLog.java:811`, `ReconfigureCMS.java:385`; one non-executable line). That is plausible: the PR restores the interrupt flag inside `catch (InterruptedException)` blocks, which no test triggers. This is the useful reviewer signal.

Report fields: per file `covered/partial/missed/nonexec` line lists, a total with `pct_executed` (covered plus partial over executable), `in_report=false` when the class has no entry (file not compiled, for example under a different `src/` root; report `unknown` for it). Also store tests run, tests failed, and the list of selected-but-not-run suites.

## 5. Failure modes and operations

### 5.1 Status mapping

| Situation | How it shows | Status |
|---|---|---|
| JDK for the branch missing | no `JAVA_HOME` directory | `unknown` + the exact `sdk install` command in the report |
| Wrong JDK / flag | build exits 1 in under 1 s with the messages in 1.1 | `unknown (harness)` |
| Compile error in the PR | `ant jar` exit 1; `[javac] <file>:118: error: cannot find symbol` ... `1 error` ... `BUILD FAILED` (5 s to reach it) | `build-failed`, include the first `error:` lines and file:line; this is a finding about the PR |
| Dependency download fails (offline, first build) | `BUILD FAILED` in the resolver target | `unknown (network)` |
| Test failure | `[junit-timeout] Test X FAILED`, `Tests run: N, Failures: F, Errors: E`, ant exit 1, but the remaining classes in the list still run | `tests-failed`, list class, method and first assertion line from `TEST-*.xml` (`<failure>`/`<error>`) |
| Class timeout (`-Dtest.timeout=4000` demo) | `Test X FAILED (timeout)`, `Timeout occurred`, a jstack dump in the XML; no JVM left behind | `timeout` for that class, others continue |
| Sandbox artifact | tests fail only under sandbox-exec (6.2) | `unknown`, rerun that class unsandboxed only if the PR is trusted |
| JaCoCo report missing | no `report.xml` | `coverage unknown`, test results still shown |

Exit code of the sequence: build failure stops the run; test failure does not stop `jacoco-report` (`jacoco-run` fails the build, run `jacoco-report` anyway, it reads the partial exec).

### 5.2 Flaky tests

Rerun each failed class once, alone. Pass on rerun means `flaky` (show both outcomes); fail twice means failed. Then rerun the same class on the base (cached base build, section 5.4) when the PR touches nothing the test mentions: fails on base too means `pre-existing`. Neither `repeat.runs` nor `-Drepeat` exists in these build files; the repeat loop is ours (call `testclasslist` again).

### 5.3 Resource caps

| Resource | Existing control | Add |
|---|---|---|
| Heap per test JVM | `maxmemory="1024m"` fixed in `testmacrohelper` (trunk: attribute, default 1024m) | none |
| ant JVM | default | `ANT_OPTS=-Xmx1g` |
| CPU | tests run sequentially in `testclasslist` (one forked JVM at a time); observed ~200% CPU; `-XX:ActiveProcessorCount=${cassandra.test.processorCount}` (2) | run under `nice -n 10` (or `taskpolicy -b`) so the Mac stays usable |
| Per class | `-Dtest.timeout` | 240000 ms |
| Whole PR | none | `timeout`-style wrapper: 25 min total (build 3 + tests 10 + report 1 are typical), kill the process group on expiry |
| Disk | 300 to 750 MB per worktree + 150 MB jacoco | delete HTML after parse, delete worktree after the run (5.5) |

Only one build or test at a time on the machine (another agent runs static analysis there): a lock file, queue the rest.

### 5.4 Cache and reuse

- Result cache key: `(head sha, jdk, selected test list)`. Store `status.json`, the changed-line coverage JSON and the trimmed `TEST-*.xml` summaries. Everything else is disposable.
- Build reuse across PRs on the same base (works, measured): keep one built worktree per base sha (`build-test` done). For a PR, make a new worktree, then `cp -cR base/build wt/build`, `cp -cR base/lib/. wt/lib/`, copy `modules/accord` on trunk, set every tracked file to an old mtime (`git ls-files | xargs touch -t 202001010000`), then `touch` only the files `git diff --name-only <base> <head>` lists. ant's javac recompiles stale files only. Result on 5212: 70 s clean build became 23 s, 14 files compiled for 9 changed.
- Risk: dependents of a changed signature are not recompiled, so a binary-incompatible change can produce `NoSuchMethodError` at test time instead of a compile error. Rule: use reuse only when the diff touches no `src/java` file's public or protected signatures; otherwise do a clean build (30 to 70 s). A cheap guard is a full `ant build-test` clean run when the changed file count is above 20 or any `.xml`, `.yaml`, `build.xml` or `lib/` file changed.
- Base build cache invalidates when the base branch advances: key it by base sha, keep the last 2 per branch.
- Maven cache: one warm `~/.m2` per machine, `cp -cR` per run (free on APFS).

### 5.5 Running in the background and cleanup

Run as a detached job writing `status.json` and a log under `reports/<pr>/build/`; the report shows `pending` until it lands. Keep at most 3 PR worktrees and 2 base builds (~3 GB). `git worktree remove --force` after the coverage JSON is saved; failed runs keep the log only. A weekly `git worktree prune` and deletion of `reports/*/build/work` older than 14 days.

## 6. Security

### 6.1 The risk

Building a PR runs the PR author's code on the owner's Mac with the owner's privileges, in several ways: `build.xml` and everything under `.build/` and `test/anttasks/` (ant `<exec>`, `<script language="javascript">`, `javac` annotation processors), the PR's tests (any JUnit code, forked JVMs), and shell scripts the build calls. A malicious PR can read `~/.ssh`, browser data, the GitHub token used for commenting (`gh` config, `.claude`), write to any user file, install a launch agent, or exfiltrate over the network. Reading the diff is not a defense: the payload can sit in a test or a build file, or be obfuscated.

Observed in practice, not hypothetical: trunk's `init` target runs `.build/git/install-git-defaults.sh`. In a worktree it resolves `git rev-parse --git-common-dir`, so it wrote `post-checkout`, `post-switch` and `pre-commit` hooks plus `submodule.recurse=true` into the shared `.work/cassandra/.git` (the fetch clone the pipeline uses). Those hooks then run on every later checkout and commit in that clone. I found and removed them after my unsandboxed trunk builds. A malicious `build.xml` can do the same to any hook. Under the sandbox the same step fails with `cp: .../.git/hooks/post-checkout.d/...: Operation not permitted`.

### 6.2 Options

| Option | Stops | Does not stop | Cost / state here |
|---|---|---|---|
| Only build PRs by committers (`roster.json` has the committer list) or after owner approval per PR | drive-by PRs | compromised committer account, malicious change smuggled in an approved PR | trivial; do it regardless |
| `sandbox-exec` profile (6.3) | external network, writes outside the run dirs, reads of chosen secret dirs | kernel/sandbox escapes, reads of anything not denied (default is read-allow), CPU/disk abuse | works, tested; `sandbox-exec` is deprecated but present on macOS 26.6 |
| Dedicated macOS user | reading owner files | local network, shared hardware | needs admin setup, shared Maven cache and sdkman access to arrange |
| Container/VM | most of it | VM escapes | `docker` is a symlink to Docker Desktop, the app is installed, but the daemon was not running (`Cannot connect to the Docker daemon at unix:///Users/patrickmcfadin/.docker/run/docker.sock`) and `colima` is not installed. Untested here. Linux arm64 images work, but a bind-mounted worktree builds slower on macOS and JDK images must be pulled (network). |
| GitHub Action on a fresh runner (planned) | everything local | secrets in the workflow | the end state; use `pull_request`-style isolation, no secrets in the build job, upload results as an artifact |

### 6.3 Tested sandbox profile

```scheme
(version 1)
(allow default)
(deny network*)
(allow network-bind)                          ; tests bind loopback ports, also on 0.0.0.0
(allow network-inbound)
(allow network-outbound (remote unix-socket))
(allow network-outbound (remote ip "localhost:*"))   ; loopback only; external connect gives EPERM
(deny file-write*)
(allow file-write*
  (subpath (param "WT"))                      ; the PR worktree
  (subpath (param "M2"))                      ; cp -cR clone of ~/.m2, used with -Dlocal.repository
  (subpath (param "GIT"))                     ; the throwaway build clone's .git (hooks land here)
  (subpath "/private/tmp") (subpath "/private/var/folders")
  (subpath (string-append (param "HOME") "/Library/Caches/JNA"))
  (literal "/dev/null") (literal "/dev/tty") (literal "/dev/dtracehelper") (regex #"^/dev/fd/"))
(deny file-read*
  (subpath (string-append (param "HOME") "/.ssh"))   (subpath (string-append (param "HOME") "/.aws"))
  (subpath (string-append (param "HOME") "/.gnupg")) (subpath (string-append (param "HOME") "/.config/gh"))
  (subpath (string-append (param "HOME") "/Library/Keychains"))
  (subpath (string-append (param "HOME") "/.claude")))
```

```bash
export JAVA_TOOL_OPTIONS=-Djava.net.preferIPv4Stack=true     # see below
sandbox-exec -D WT=$ABS/wt -D M2=$ABS/m2 -D GIT=$ABS/buildclone/.git -D HOME=$HOME -f sandbox.sb \
  ant jacoco-run -Dno-build-test=true -Dlocal.repository=$ABS/m2 -Dtaskname=testclasslist -Dtest.classlistfile=$ABS/tests.txt
```

Verified inside the sandbox: `curl https://repo.maven.apache.org` fails (exit 7), raw sockets to 1.1.1.1:443 and 8.8.8.8:443 fail with EPERM, `echo x > ~/pwned` fails, `ls ~/.claude` fails, `cat /etc/hosts` works, clean `ant jar` (33 s) and 25-class JaCoCo run succeed. Gotchas found on the way:

- Parameter paths must be absolute and normalized: a `..` in `-D WT=` silently gave no write access.
- `(local ip "localhost:*")` forms for bind/inbound did not match Java's listen sockets (`Listen failed`); the unrestricted bind/inbound lines above are needed. Side effect: a test's listening socket on 0.0.0.0 is reachable from the LAN while it runs. Outbound stays local-only.
- Java dual-stack sockets are not matched by `remote ip "localhost:*"` for connect; `-Djava.net.preferIPv4Stack=true` through `JAVA_TOOL_OPTIONS` fixes it (adds a "Picked up" line to stderr).
- `getLocalHost()` returns the LAN address inside the sandbox (no DNS), harmless for the tests that passed.
- Remaining difference: `StreamingTransferTest.testTransferRangeTombstones` fails only under the sandbox (`IOException: Operation not permitted` in `FileChannelImpl.transferTo0`, the zero-copy `sendfile` path); passes 2 of 2 outside it. Other network-heavy classes (ImportTest 19 tests, rest of StreamingTransferTest, AutoRepair, Gossip) passed. Rule: a failure whose stack contains `transferTo0` or `Operation not permitted` is `unknown (sandbox)`.
- The profile reads everything not denied. Add more denies as needed (`~/Library/Application Support`, the repo checkout of this tool, the GitHub token file). Better: run as a build clone under a directory tree that holds nothing else, and never export `GH_TOKEN`/`GITHUB_TOKEN` into the build environment.

### 6.4 Recommendation

1. Gate: build only PRs whose author is in the committer roster, or that the owner marks approved (a one-line `approved.txt` per PR number plus head sha; a new push needs a new approval).
2. Run every build and test inside the sandbox profile above, in a dedicated build clone (`git clone --shared --no-checkout .work/cassandra buildclone`, origin removed) with a per-run `cp -cR` of `~/.m2`. This also keeps the git-hook writes and the submodule fetch away from the fetch clone. Do the two network steps (first resolve of a branch's dependencies, trunk submodule clone) in a separate trusted pre-step using the base branch's `build.xml`, never the PR's.
3. Scrub the environment (`env -i` with `PATH`, `JAVA_HOME`, `HOME`, `CASSANDRA_USE_JDK11`), no tokens, `nice`, wall-clock cap.
4. When the GitHub Action lands, move the whole job there and keep only the result JSON on the Mac. Revisit a container (Docker Desktop, once the daemon is running) if the owner wants to open this to non-committer PRs without per-PR approval.

## 7. Design hand-off

Inputs per PR: base branch, base sha, head sha, `refs/cpr/pr/N`. Steps: gate, pick JDK (table 1.1), ensure base build (5.4), worktree in the build clone, reuse or clean `build-test`, select tests (3), `jacoco-run` + `jacoco-report` in the sandbox, parse `TEST-*.xml` and `report.xml`, write `status.json` (`status`, `timings`, `tests{run,failed,flaky,skipped}`, `selected[]` with reasons, `changed_lines{file:{covered,partial,missed,nonexec}}`, `unknowns[]`), delete worktree. Report section: status banner, tests table, changed-line coverage per file with the missed line numbers linked to the head blob, "not run" list (dtests etc.), and a note that coverage is from a limited test selection.

Open items: per-class duration table; run on 4.1 and 5.0 (built and timed only); JDK 8 behavior on 4.x; container option untested; a PR whose build reuse is unsafe (signature changes) needs the clean-build rule implemented; cassandra-6.0 base not built.
