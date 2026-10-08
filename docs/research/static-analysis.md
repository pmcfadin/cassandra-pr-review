# Static analysis section: research

Input for roadmap item 5 (`static-analysis`). Everything below was run on 2026-10-07 on an Apple-silicon Mac, JDK 17 (Temurin 17.0.13) for checkstyle and JDK 21 (`/opt/homebrew/opt/openjdk@21`) for PMD. Tools live in `.work/tools/` (gitignored). No code in the repo was changed.

Test subjects: PR 5201 (base `3ccf9476`, head `d1095cbd`, branch `cassandra-4.0`, one file, `SSTable.java`, +8/-11) and PR 4967 (trunk, base `8cfc3a67` = merge-base, head `f72d4f0e`, one commit, 173 files, 150 Java files that exist at head, 85k lines).

## Findings in one table

| Question | Answer |
|---|---|
| Checkstyle on 4.0? | No. `cassandra-4.0` has no checkstyle config anywhere. Report `unknown`. Do not borrow the 4.1 config: it flags `java.io.File`, which 4.0 code uses legitimately (see 1.4). |
| Checkstyle version per branch | trunk and 5.0: 10.26.1. 4.1: 8.40. Pin the jar per branch. |
| Standalone `-all` jar works without ant? | Yes. Needs `-p props` with two properties. No custom check jars. 0.4 to 0.9 s per file set. |
| PMD | 7.28.0, ruleset and CPD both work on plain source with no classpath. 150 files: PMD ~6 s, CPD ~1.2 s. |
| PMD JSON vs XML | JSON has no enclosing class/method. Use PMD XML (`class=`, `method=` attributes). CPD: XML. |
| Introduced vs pre-existing | Key = (base path via rename map, enclosing class, method signature, rule). Not line numbers. Prototype ran on 4967 (section 3). |
| Perf PR detection | JIRA component "Performance" does not exist, and none of 5 sampled perf tickets carries the `performance` label. Detect by changed `test/microbench/**` plus title/body keywords. |
| Cost per PR | ~5 s small PR, ~45 s for a 150-file PR, one JVM start per tool. Cache per head sha and per blob sha. |

## 1. Checkstyle

### 1.1 Config files per branch (from `git ls-tree origin/<branch>`)

| Branch | `.build/checkstyle.xml` | `checkstyle_suppressions.xml` | `checkstyle_test.xml` | `build-checkstyle.xml` | Version | Notes |
|---|---|---|---|---|---|---|
| trunk | yes | yes (empty `<suppressions>`) | yes | yes | 10.26.1 (`.build/parent-maven-pom.xml`) | Includes Accord import groups, `AvoidStarImport`, `ImportOrder`, `blockToCases`, `blockInstantNow` |
| cassandra-5.0 | yes | yes | yes | yes | 10.26.1 (`.build/parent-pom-template.xml`) | No `ImportOrder`, no `blockToCases` |
| cassandra-4.1 | yes | yes | yes | no (targets are inline in `build.xml`) | 8.40 (`build.xml:617`) | Runs only `if="java.version.8"`; no `new Integer(` bans, no Jackson `ObjectMapper` ban |
| cassandra-4.0 | no | no | no | no | none | `grep -ci checkstyle build.xml` = 0; `git log origin/cassandra-4.0 -- .build/checkstyle.xml` is empty |

Config differences between branches are real (banned-API lists differ), so the config must come from the PR's base branch, as `docs/report/static.md` already does for its regex approximation. The jar version must match the branch.

How ant invokes it (trunk `.build/build-checkstyle.xml`): `checkstyle` runs `checkstyle.xml` over `src/java/**/*.java`; `checkstyle-test` runs `checkstyle_test.xml` over `test/**/*.java` (`${test.dir}`). Both define `checkstyle.suppressions=.build/checkstyle_suppressions.xml` and `checkstyle.log.dir=${build.dir}/checkstyle`. The Sevntu comment in the ant file is stale: no custom check jar is referenced; every module is stock Checkstyle (`RegexpSinglelineJava`, `IllegalImport`, `IllegalInstantiation`, `IllegalType`, `MatchXpath`, import checks, suppression filters).

### 1.2 Standalone run, no ant

Downloads (GitHub releases, `checkstyle-<v>-all.jar`):

| Jar | sha256 |
|---|---|
| checkstyle-10.26.1-all.jar | `e41c24433723ba310a30e41da4f449c105ad47cab2ae9e6be5e06606a647dbca` |
| checkstyle-8.40-all.jar | `670f057d61cc6cef8f0440f838f4adcea6a16c9e634bc0e96a1c6eeab53fc0e4` |

Required inputs: the two `${...}` properties the configs reference. Without `checkstyle.log.dir` the config fails to parse (`Property ${checkstyle.log.dir} has not been set`). Without `checkstyle.suppressions` it fails (`cannot initialize module SuppressionFilter - Unable to find: checkstyle-suppressions.xml`). Both are hard errors with a stack trace, so a wrapper must treat a non-parse as `unknown`.

```bash
# props file (per branch, per run)
cat > run.properties <<EOF
checkstyle.log.dir=$SCRATCH/cs-log          # fresh dir per run: holds checkstyle_cachefile
checkstyle.suppressions=$CFGDIR/checkstyle_suppressions.xml
EOF
# configs come from the base branch:  git show origin/<base>:.build/checkstyle.xml > $CFGDIR/checkstyle.xml  (and _suppressions, _test)
java -jar checkstyle-10.26.1-all.jar -c $CFGDIR/checkstyle.xml -p run.properties -f xml -o out.xml  <files...>
```

- Use `checkstyle.xml` for files under `src/java`, `checkstyle_test.xml` for files under `test/`. Do not run the main config on test files (it would apply the test-incompatible bans).
- Exit code equals the number of errors (11 errors gave exit 11). A crash is a different, non-count failure with a stack trace on stderr.
- `-f xml -o file` is machine-readable: `<file name=...><error line column severity message source=.../></file>`. `source` is the check class, or for `RegexpSinglelineJava` the `id` (for example `blockSystemPropertyUsage`).
- The configs name a `cacheFile` inside `checkstyle.log.dir`. Give each run its own directory so a stale cache can never skip a file.
- Classpath: none needed. The checks used are syntactic. (`IllegalInstantiation` resolves names from imports, not from compiled classes.)
- Config cross-version: the 4.1 config loads under 10.26.1; the trunk config loads under 8.40 here too, but pin the real version anyway.

### 1.3 Run on PR 5201 (`SSTable.java`), config from trunk vs 4.1 vs 5.0

Output at head, 8.40 + 4.1 config (trimmed paths):

```
[ERROR] SSTable.java:117:41: Instantiation of java.io.File should be avoided. [IllegalInstantiation]
[ERROR] SSTable.java:258:17: ...  [IllegalInstantiation]
[ERROR] SSTable.java:287:22 / 316:24 / 322:33 / 335:24 ...
Checkstyle ends with 6 errors.     real 0.36 s
```

| Config + jar | Base | Head | Wall |
|---|---|---|---|
| 4.1 + 8.40 | 5 errors | 6 errors | 0.41 s / 0.36 s |
| 5.0 + 10.26.1 | 7 errors | 8 errors | 0.84 s / 0.83 s |
| trunk + 10.26.1 | n/a | 11 errors (adds AvoidStarImport x2, ImportOrder, blockSystemPropertyUsage, MissingDeprecated) | 0.88 s |

### 1.4 The 4.0 trap (why `unknown`, not borrowed config)

PR 5201 targets `cassandra-4.0`. The only line the PR adds that trips the 4.1 config is `new File(desc.filenameFor(component)).lastModified()` (diff line 24). In 4.0, `java.io.File` is the normal API; `org.apache.cassandra.io.util.File` arrived in 4.1. All 5 base-side errors are the same false-positive class. So the 4.1 numbers above are a demonstration of what NOT to report: for a 4.0 PR the result is `unknown (no checkstyle config on cassandra-4.0)`, never `pass` and never a borrowed-config count.

### 1.5 Run on PR 4967 (trunk config, 10.26.1)

| Set | Files | Errors | Wall (both runs, includes 2 JVM starts) |
|---|---|---|---|
| head `src/java` (`checkstyle.xml`) + `test/` (`checkstyle_test.xml`) | 85 + 65 | 0 + 0 | 10.3 s |
| base | 62 + 41 | 0 + 0 | 9.1 s |

Zero is a real result here (output lists each `<file>` with no `<error>`), not a failed run. The wrapper must check that the XML contains one `<file>` per input file before reporting `pass`.

### 1.6 Introduced vs already-there for checkstyle

Run the same config on base and head blobs of each changed file. A head violation is introduced when its line is in the head-side changed-line set (`git diff -U0`), or when no equal (file, source id, message) exists at base. Otherwise it is pre-existing. Line numbers shift, so the changed-line test is on head lines only; the base run is only needed to count "fixed". Many `RegexpSinglelineJava` messages are identical per line, so also compare the trimmed source line text.

## 2. PMD and CPD

### 2.1 Versions

| Item | Value |
|---|---|
| PMD | 7.28.0 (2026-09-25), `pmd-dist-7.28.0-bin.zip` from github.com/pmd/pmd/releases |
| sha256 (matches the release API digest) | `f974ba571f7bc01c73fffe11bade25fbc1f438698f9e9c00e416e8d65e9fbac2` |
| Skill ruleset | `~/.claude/plugins/cache/rustyrazorblade-plugins/dev-skills/0.4.1/skills/complexity-reduction/pmd-complexity.xml`, sha256 `c8610fae...e471` |
| Skill thresholds | CognitiveComplexity `reportLevel=15`; CyclomaticComplexity and NPathComplexity at PMD defaults (method 10, class 80; NPath 200). SKILL.md: "15 or above for one function marks a potential problem ... a threshold to report, not a rule to enforce." Diff mode: score whole changed files, mark introduced vs existing. |
| CPD | `pmd cpd --minimum-tokens 45 --language java` per SKILL.md. Also run 100 (CPD's usual default). |

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@21
unzip pmd-dist-7.28.0-bin.zip -d x          # -> x/pmd-bin-7.28.0/bin/pmd
pmd check -R pmd-complexity.xml --file-list files.txt -f xml -r out.xml --no-progress --no-cache
pmd cpd --minimum-tokens 100 --language java --file-list files.txt --format xml -r cpd.xml     # no --no-progress on cpd
```

Exit codes: `check` 0 = clean, 4 = violations found; `cpd` 4 = duplicates found, 5 = recoverable error. Treat 0 and 4 as "ran"; anything else (including 1, 2 usage) as `unknown`. `--file-list` takes absolute paths, one per line. No classpath is needed for these rules (no type resolution), so no build of the branch is needed. Parsing works for Java 8 code (4.0) and trunk (Java 17/21 syntax): 0 processing errors on 253 files.

### 2.2 Output formats

| Format | Has enclosing class/method? | Verdict |
|---|---|---|
| `-f json` | No. Violation = `beginline, endline (name line only), description, rule` | Not enough to match methods; description holds the signature but not the class |
| `-f xml` | Yes: `package=` `class=` (innermost class, e.g. `AccordCache.Type.Instance`) `method=` (name only, no params) plus signature in the message text | Use this |
| `cpd --format xml` | `<duplication lines tokens><file path line endline/>...<codefragment>` | Use this; csv also works (`lines,tokens,occurrences,line,path,...`) |

Message form (cognitive): `The method 'delete(Descriptor, Set<Component>)' has a cognitive complexity of 2, current threshold is 1`. Constructors read `The constructor 'SSTable(...)'`. Class-level cyclomatic has no `method=` attribute.

### 2.3 Method line ranges

Violations point at the method name, not the body, so touched-method tests need the body range. A single XPath rule emits it in the same pass:

```xml
<rule name="MethodBody" language="java" message="body" class="net.sourceforge.pmd.lang.rule.xpath.XPathRule">
  <properties><property name="xpath"><value>//MethodDeclaration/Block | //ConstructorDeclaration/Block | //Initializer/Block</value></property></properties>
</rule>
```
Output: `beginline="110" endline="124" ... class="SSTable" method="delete"`. Join to a complexity violation on (class, method, smallest body begin >= name line). The combined one-pass ruleset (`.work/tools/pmd/pmd-pr.xml`) is the skill's three rules, with `CognitiveComplexity reportLevel=1` so every method with score >= 1 is reported (a missing method means 0), plus this rule. Measuring everything costs output size, not much time: 5.2 s base / 6.1 s head for 150 files (the XML is ~2 MB). With `reportLevel=1` on all three rules it took 10 to 12 s and 11.5k violations, so keep cyclomatic and NPath at their thresholds.

### 2.4 PR 5201 (`SSTable.java`)

| Run | Base | Head | Wall |
|---|---|---|---|
| skill ruleset (thresholds) | "Found no violations" | "Found no violations" | 1.2 s / 0.8 s |
| CPD, 45 tokens | 0 duplicates | 0 duplicates | 0.7 s |
| Per-method cognitive (reportLevel 1) | 12 methods | 12 methods | 0.8 s |

Per changed method delta (only change): `SSTable.delete(Descriptor, Set<Component>)` cognitive 6 (base) -> 2 (head), improved by 4. The other 11 methods are unchanged (largest: `componentsFor(Descriptor)` = 6).

### 2.5 PR 4967 (150 Java files at head, 103 at base, 85k / 64k lines)

| Run | Base | Head | Wall |
|---|---|---|---|
| skill ruleset (threshold report) | 229 violations (95 cog, 110 cyc, 24 NPath) | 373 (165 cog, 164 cyc, 44 NPath) | 1.6 s / 1.75 s |
| one-pass PR ruleset (all methods + bodies) | 6,311 rows | 7,947 rows | 5.2 s / 6.1 s |
| CPD 100 tokens | 18 duplicates | 66 | ~1.2 s |
| CPD 45 tokens | 147 | 363 | ~1.2 s |

CPD over the head set only sees duplication among the changed files. It cannot see a new copy of existing code elsewhere. Option: add the same-package siblings of each changed file to the CPD input (cost is small: CPD is ~1 s) and keep the base list the same size.

## 3. Introduced vs already-there

### 3.1 Proposed algorithm

Inputs: `git diff --name-status -M <base> <head> -- '*.java'` (rename map), `git diff -U0 -M` (head-side and base-side changed line ranges), PMD XML for the base and head blobs of the changed files, same ruleset on both.

1. Extract blobs: `git show <base>:<oldpath>` and `git show <head>:<newpath>` into two scratch trees (`base/`, `head/`) keeping paths. No worktree or checkout is needed (253 files).
2. Run PMD (and CPD, checkstyle) once per side, same ruleset, same version.
3. Key each finding by `(base path via rename map, class, method signature, rule)`. Never by line number.
4. For each head finding at/above threshold:

| Condition | Class |
|---|---|
| File status A | introduced (new file) |
| Method key not at base | introduced (new method); flag "?moved" if the same signature exists elsewhere in the PR's base files |
| In base and head > base, base was >= threshold | introduced: worsened by +d |
| In base and head > base, base < threshold | introduced: crossed the threshold |
| head == base and body overlaps changed head lines | pre-existing, touched |
| head == base, body untouched | pre-existing |
| head < base | pre-existing, improved |

5. Fixed = base findings at/above threshold with no head finding at/above threshold (method removed or reduced).
6. Report introduced first; show pre-existing as a count plus a collapsed list. Never fail the PR on pre-existing.

Prototype: `.work/tools/pmd/classify.py` (stdlib only, `xml.etree`). Real result on PR 4967 (threshold hits at head, 150 files):

| Class | Cognitive>=15 | Cyclomatic>=10 | NPath>=200 |
|---|---|---|---|
| introduced: new file | 72 | 55 | 23 |
| introduced: new method (existing file) | 8 | 5 | 0 |
| introduced: worsened | 6 | 6 | 3 |
| introduced: crossed threshold | 2 | 0 | 1 |
| pre-existing, untouched | 57 | 64 | 13 |
| pre-existing, touched | 14 | 8 | 4 |
| pre-existing, improved | 5 | 1 | 0 |
| fixed or removed (base breach not at head) | 34 (all rules) | | |

Sample introduced-by-existing-method rows (base -> head cognitive): `AccordCommandStore.ensureDurable` 22 -> 71; `AutoRepair.repairKeyspace` 36 -> 39; `SaferCommandStore.visitForKey` 6 -> 17 (crossed); `ActionSchedule.next` 13 -> 15 (crossed); `DatabaseDescriptor.applySimpleConfig` 199 -> 200.

Per-method cognitive delta for the report (all changed methods, not only threshold hits) is the same join with threshold ignored: the 5201 example above is `delete` 6 -> 2.

### 3.2 Pitfalls

| Pitfall | Handling |
|---|---|
| Renamed files (13 of 150 in 4967) | Use `-M` rename map. If the class also got renamed (`AccordExecutorAbstractLockLoop` -> `AbstractLockLoop`), the class part of the key misses. Fallback implemented: within the matched base file, if exactly one method has the same signature, use it. Without this, 5 findings (4 cognitive, 1 cyclomatic) were wrongly "new method (moved?)". |
| Moved methods across files | Not matched by file; fall back to a signature match across all of the PR's base files and label "moved?" (not "introduced") when found. |
| New files | All findings introduced. Say so, separate from "new method in existing file". |
| Overloads | The signature text (with parameter types) in the message disambiguates; `method=` does not. |
| Nested/anonymous classes | `class=` is the innermost named class (`AccordCache.Type.Instance`). Lambdas and anonymous classes fold into the enclosing method score. |
| Method signature changed | Looks like removed + new. Same fallback as moved: a unique same-name match in the same class is labelled "signature changed" with both scores. |
| Reformat-only edits | Complexity is unchanged, so the delta is 0; "touched" is true, so report it as pre-existing, touched. |
| Zero-score methods | Not emitted at `reportLevel=1`; treat missing as 0. |
| Deleted files | Excluded from head; base findings count as "fixed or removed". |
| Generated or vendored code (`src/gen-java`, `modules/accord`) | Exclude by path before running. |
| CPD | Introduced = at least one occurrence overlaps a head changed line, or all occurrences are in new files. On 4967 at 100 tokens: 47 of 66 are all-new-file, 6 touch changed lines, 13 pre-existing with no changed line. |
| Test files | Report separately; tests often have large builder methods. Do not mix with main code in the headline count. |

## 4. Performance commit-structure rule

### 4.1 What Cassandra PRs look like

Sampled with `gh pr list/view` plus `gh api .../commits/<sha>` (read-only):

| PR | Commits | Order of changes | JIRA component / labels |
|---|---|---|---|
| 4965 (CASSANDRA-21535) | 3 | 1: `Mutation.java` change; 2: adds `MutationSerializationCachingBench`; 3: modifies change and bench | Local/Other, no labels |
| 4966 (CASSANDRA-21536) | 3 | 1: 20 files incl. `CHANGES.txt` and bench; 2: `AbstractType.java`; 3: a unit test | Local/Other, no labels |
| 5132 (21492), 5181 (21683), 4919 | 1 | change + bench in one commit | none or Local/SSTable, no labels |
| 5039 (21587) | 1 | change only, no bench | Local/Other, no labels |

No PR sampled puts the benchmark first. On trunk, 20 of 25 commits since 2025-01-01 that touch `test/microbench` also touch `src/java` (squashed at merge), so the check applies to the PR branch's commits, not to what lands. JIRA: there is no "Performance" component (components include `Test/benchmark`, 18 tickets, and the `Local/*` family). The `performance` label exists (187 tickets) but 0 of the last 90 days' 238 new tickets use it and none of the 5 sampled tickets have it. Issue type is `Improvement`.

### 4.2 Detection of a perf PR (any of; record which fired)

| Signal | Strength | Notes |
|---|---|---|
| Changed or added file matches `^test/microbench/.*\.java$` | strong | Also tells us where the benchmark is |
| JIRA label `performance` or component `Test/benchmark` | strong when present | Rare, do not require |
| Title or JIRA summary matches `(?i)\b(perf(ormance)?|faster|speed.?up|latency|throughput|allocation|megamorphic|avoid (an )?(extra )?cop(y|ies)|copy-on-write|optimi[sz]e|reduce (overhead|allocation))` | medium | Matches all 5 sampled titles/summaries |
| PR body mentions `JMH` or `benchmark` | medium | |

Perf PR = strong signal, or two medium signals. Single medium signal = "possible perf PR": run the check but cap severity at note.

### 4.3 Rule

Walk `git rev-list --reverse --no-merges <merge-base>..<head>`. Drop `fixup!`/`squash!` commits only for ordering (keep them for display). For each commit classify paths: `B` = touches `test/microbench/**`; `S` = touches `src/java/**` (excluding `CHANGES.txt`, docs, `NEWS.txt`). Let `b` = first commit with a bench file added or modified, `s` = first commit with a `src/java` change.

| Result | Condition |
|---|---|
| n/a | Not a perf PR; or perf PR with no `src/java` change (benchmark-only or build-only PR) |
| pass | `b` exists and `b < s` (bench commit first, optionally bench-only) |
| warn: combined | `b == s`: bench and change in one commit, includes every squashed single-commit PR (5132, 5181, 4919). A/B at the parent commit is impossible without cherry-picking the bench onto base. |
| warn: no benchmark | Strong or medium-plus perf signal, `src/java` change, but no `test/microbench` change and the body names no existing benchmark class. Matches 5039. |
| fail | `b > s`: change lands before the benchmark (4965: `Mutation.java` first, bench second). Commit order is what the owner wants fixed. |
| unknown | Commit list unavailable, head not fetched, more than 250 commits (GitHub API cap), or the PR was force-pushed since the cached sha |

`fail` here means "does not meet the owner's rule" in the report. It should not gate other sections. Rationale for warn rather than fail on the single-commit case: it is the dominant pattern on trunk, and the squash happens at merge; the useful action is "split the commit so the bench can run at the parent". Ties to roadmap item 7 (perf-ab), which needs the benchmark commit as the A side.

Edge cases: a later commit that edits the benchmark alongside the change (4965 commit 3) does not change `b`. A PR with several benches uses the earliest. A benchmark that only reformats an existing file with no behavior difference still counts; do not try to judge it.

## 5. Budget, caching, missing tools

### 5.1 Budget (measured; wall clock, one machine)

| PR size | Checkstyle | PMD (pr ruleset) x2 sides | CPD x2 | Total tool time |
|---|---|---|---|---|
| 1 file (5201) | 0.4 to 0.9 s per side | 0.8 s per side | 0.7 s per side | about 5 s |
| 150 files, 85k lines (4967) | ~10 s per side (main + test, 2 JVMs) | 5 to 6 s per side | 1.2 s per side | about 45 s |

Setup: extracting blobs via `git show` is a few seconds for 250 files and needs no checkout. Suggested caps: 120 s per tool, 300 s per PR; above 400 changed Java files, run checkstyle and CPD only and mark PMD `skipped: too large`. All tools are JVM single-shot; they use multiple cores (PMD ~6x CPU time vs wall), so run tools sequentially, not in parallel. No AI tokens are used.

### 5.2 Cache

| Level | Key | Contents |
|---|---|---|
| Per PR run | `static/<pr>/<head_sha>/<tool>-<version>-<config_sha>.json` | normalized findings + `status` + `tool_cmd` + `ran_at` |
| Base side | `blob_sha` of the file at base + tool version + ruleset sha | per-file findings; reused across PRs and head updates |
| Config | sha256 of the checkstyle config set or the PMD ruleset | invalidates when `.build/checkstyle*.xml` changes upstream |

A new head sha recomputes only blobs that changed. Base-side results come from the blob cache. Store raw tool output next to the normalized JSON so reports can be regenerated.

### 5.3 Status values and failure handling

Statuses per tool: `pass`, `findings`, `unknown`, `skipped`, `n/a`. `pass` requires proof the tool ran on every changed file of the type.

| Situation | Status | Reason text |
|---|---|---|
| Checkstyle: base branch has no config (`cassandra-4.0`, older) | unknown | "no checkstyle config on cassandra-4.0" |
| Config from base branch fetched but jar for that version not downloaded or checksum mismatch | unknown | "checkstyle 8.40 jar missing" |
| Checkstyle config parse error / non-count exit | unknown | first stderr line |
| Checkstyle XML lacks a `<file>` for some input | unknown | "N of M files not analyzed" |
| `java` missing, or JDK too old (checkstyle 10.x needs 17+; PMD 7 needs 8+) | unknown | "needs JDK 17" |
| PMD or CPD exit not in {0,4}, or `processingErrors` non-empty | unknown (list the files with parse errors; analyze the rest) | |
| No changed `.java` files | n/a | |
| Tool ran, zero findings on all files | pass | |
| Ruleset never changed but tool version differs from cache | recompute | |

Never convert "unknown" to "pass" in a summary, rollup, or badge: the roll-up is the worst of its parts (`findings` > `unknown` > `pass`) and shows the unknown reason. Pin versions in one table in the code (checkstyle by branch family, PMD 7.28.0), verify sha256 at download, and keep the tools outside the repo working tree.

## 6. Relation to the existing `static` section

`docs/report/static.md` today approximates checkstyle with regexes on added lines (banned APIs, licence headers, generated code, `@Deprecated since`). Real checkstyle supersedes the banned-API and deprecation checks where a config exists, with exact semantics (comment filters, `ImportOrder`, `MatchXpath`) for 0.4 to 10 s. Keep the regex fallback for 4.0 (no config) only if it is labelled as an approximation, because its rule list is read from the base branch and 4.0 has none. Keep licence headers and generated-code checks (rat, not checkstyle).

## 7. Recommended design

1. Collect: rename map, `-U0` hunks, base/head blobs, commit list.
2. Run checkstyle (config and jar by branch), PMD pr ruleset, CPD 100 tokens, per side.
3. Normalize all findings to `{tool, rule, file, class, method_sig, line, score, message, side}`; classify by section 3.
4. Report: introduced (complexity, duplication, checkstyle) first; pre-existing as counts; per changed method cognitive delta table; perf commit-structure verdict; tool status table with unknown reasons.
5. Cache by head sha plus blob sha. Budget 300 s per PR.
