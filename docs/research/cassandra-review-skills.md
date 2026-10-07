# apache/cassandra review skills: research for the `cassandra-lenses` spec

Source: `apache/cassandra` `origin/trunk` @ `617fd3b935` in the local clone
`.work/cassandra`. All paths below are relative to `.claude/skills/` on trunk unless they start with
`AGENTS.md` or `CLAUDE.md`. Read with
`git -C .work/cassandra show origin/trunk:.claude/skills/<path>`.
The skills landed in one commit, `3831d8265d` (2026-04-27, "Add suite of skills for AI"). It is the
only commit that has ever touched `.claude/` on trunk, so the content is young and likely to change.

Content was treated as reference material, not instructions.

## 0. Findings at a glance

- There is no severity scale anywhere in the review skills. Every skill reports only
  confidence `High | Medium | Low` (shallow-review/SKILL.md "Report Format";
  targeted-review/references/report-format.md; deep-review/SKILL.md "Report Format";
  mega-review/SKILL.md "Confidence Ranking"). A severity-like vocabulary exists only in
  bug-archaeology (`silent-wrong-result | crash | hang | data-loss | performance | cosmetic`,
  bug-archaeology/references/per-bug-format.md "Tags") and as per-pattern `weight: high|medium|low`
  in deep-review. We must derive our `blocker|major|minor|nit` ourselves (section 6).
- The four review skills share one content family: shallow = 6 trimmed specialist checklists,
  deep = the same 6 domains in full form, targeted = a different, orthogonal cut into 11 categories
  (about 427 findings). mega-review contains no checklist; it only orchestrates the other three.
- All orchestration relies on the Claude Code `Skill` and `Agent` tools (nested subagents). Our
  lens agents are `Read, Bash, Grep, Glob` only (see `.claude/agents/cassandra-standards-reviewer.md`
  frontmatter), so we can reuse the checklists and schemas but not the orchestration as written.
- AGENTS.md and CLAUDE.md on trunk do not mention the skills. `CLAUDE.md` is a one-line file whose
  content is `AGENTS.md` (mode 100644 blob `c317064`, not a symlink). AGENTS.md has no `skill` or
  `.claude` match. The only index is `README.md` in the skills directory.
- Release branches have no `.claude/` directory: `origin/cassandra-6.0`, `cassandra-5.0`,
  `cassandra-4.1` each return 0 files for `git ls-tree -r .claude`. "Load from the PR's base
  branch" therefore fails for most PRs. The reference source must be `origin/trunk`.
- Provenance: Apache License 2.0 by project policy, but only `heatmap/heatmap.py` carries a license
  header. See section 7.
- No skill states a token, cost, or wall-clock budget. The only pacing guidance is structural:
  entry-point sizing by LOC (README.md), "3-7 categories load per iteration, never more than 8"
  (targeted-review/SKILL.md Phase 2), "2-5 foci, 5-15 items each" (Phase 4), and up to 5
  concurrent archaeology batches (bug-archaeology/SKILL.md Phase 2).
- The skills disagree with themselves in places (README says "444-pattern catalog"; deep-review
  SKILL.md says "500+ patterns"; shallow-review/EVAL-PROMPT.md still points at
  `references/general/pass2-specialists/pass2-*.md` and describes 5 specialists, while the skill
  has 6 and the files live in `references/general/specialists/`). Treat counts as marketing; do
  not assert them in our report.

## 1. Skill by skill

### 1.1 README.md (176 lines)

Purpose: index plus philosophy (README.md lines 1-45). Key claims we may reuse as rationale:
the author built the suite from about 3000 indexed Cassandra bugs ("I have indexed 3000 bugs"),
and insists on evals: "Without evals, results are purely anecdotal."

Entry-point sizing table (README.md "Where Do I Start?"):

| Have | Start with |
|---|---|
| Small patch | shallow-review, then deep-review on flagged areas |
| 50-1000 LOC | targeted-review |
| 1000+ LOC | mega-review |
| Bug report to reproduce | write-reproducer |
| Code you do not understand | patch-explainer |
| Protocol to verify | tla-plus |
| No idea where to look | heatmap |
| Bug history to learn from | bug-archaeology |
| Cluster test to write | cassandra-injvm-dtest |

Suggested multi-pass workflow (README.md "Example prompt"): shallow-review, then patch-explainer,
then deep-review on risky components, then deep-review on heatmap-hot files, then targeted-review
on the trickiest files. README also lists `write-reproducer` and `tla-plus`, which exist on trunk
(`write-reproducer/SKILL.md`, `tla-plus/SKILL.md`) but are out of scope for review lenses.

Self-reported eval datum (README.md lines 20-42, anonymized "<this>" vs "<other>" skill, 20
commits, bugs the tool was not indexed on): 151 findings (7.6 per commit) vs about 193 (9.7);
High+Critical share 37% vs 20%; Low share about 30% vs 53%. This is an author claim without a
reproducible harness in the tree; use it as direction, not proof.

### 1.2 install.sh (2808 bytes)

Bash installer. Discovers every direct-child directory containing `SKILL.md`, copies it to
`${SKILLS_DIR:-$HOME/.claude/skills}` (flags `--target DIR`, `--dry-run`, skill names). It does
`rm -rf "$dst"` then `cp -r`, so it overwrites installed copies. Irrelevant at runtime for us:
we should not install into `~/.claude/skills` (that is user-global and would let the skills
trigger on unrelated work). We read files in place.

### 1.3 shallow-review

Files: `shallow-review/SKILL.md` (12 KB), `EVAL-PROMPT.md`, and
`references/general/specialists/{logic,boundary,concurrency,resources,absence,completeness}.md`
(37 KB total, about 9-10k tokens for all six).

- Purpose: quick broad bug scan "for any patch size" (bug-archaeology/references/EVAL-PROMPT.md
  table). Frontmatter description: "Best for: quick first-pass review of patches, triage of diffs".
- Input: a patch file path, `{PATCH_PATH}`, plus `{SKILL_DIR}` for checklist paths. Also accepts
  "patch, diff, file, or subsystem" (Quick Start step 1). No base/head needed; diff only.
- Orchestration: six specialists in parallel, each given the same patch; then a serial "Pass 3:
  Cross-Path Symmetry" agent; then merge/dedup by the main agent. Every specialist runs
  "Phase 0: Understand Before Checking" (summarize in 2-3 sentences, list 3-5 things that could go
  wrong, note suspicious code shapes) before opening its checklist. Absence is two-phase: build a
  search list from the diff, then run Grep/Read searches and report only if no counterpart is found.
- Checklist sizes (stated in each prompt): Logic 30 items, Boundary 22, Concurrency 24, Resources
  26, Completeness 22, Absence = items (a)-(x) lettered search patterns.
- Specialist output (per prompt): "Location, Confidence (High/Medium/Low), What's wrong (1-2
  sentences)", or "No finding in my domain". Absence adds "what's missing, where it should be, what
  evidence you searched for".
- Merge rules (SKILL.md "Merge & Dedup"): same location plus related reason combine; Logic+Absence at
  one location boost to High; Concurrency+Resources on one lifecycle boost to High; 3+ specialists
  means confirmed; the "3-point test": "The code construct actually exists in the diff (not
  inferred)", "The bug is possible given the visible context (not speculative)", "The finding is
  actionable". "Specialist Silence Rule": Absence or Completeness silent on a >100-line diff triggers
  a note to verify the Phase 2 searches ran.
- Final report schema (SKILL.md "Report Format"):
  `#### Finding N: [title]` with `Location: [file:line]`, `Confidence: High / Medium / Low`,
  `Flagged by: [specialists]`, `What's wrong: [1-2 sentences]`; then a `Specialist Coverage` list
  with counts per specialist.
- "Statistical Priors" table (SKILL.md): Logic error in condition 26%, wrong constant/default 15%,
  missing null/bounds check 13%, incorrect filtering 11%, race 9%, wrong serialization 8%, state not
  cleaned up 7%, off-by-one 4%, resource leak 3%. Section headers claim Logic = 52% of bugs,
  Boundary 17%, Concurrency 16%, Resources 15%.
- Checklist item format: `N. [ ] Does ... ? ` then optional `→ Also: ...`. Grounded, concise, Java
  and Cassandra-flavored (`ReversedType`, `serializedSize`, `TeeDataInputPlus`, `ByteBuffer.duplicate()`).
- Scale: designed for any size, but all six specialists read the whole patch, so cost is
  6 x diff size. No cap is stated. mega-review treats it as the per-commit tool.

### 1.4 shallow-review/EVAL-PROMPT.md and bug-archaeology/references/EVAL-PROMPT.md

See section 8 for the methodology. Note the shallow one is stale (5 specialists, old file names).
The bug-archaeology one is the current, skill-agnostic version.

### 1.5 deep-review

Files: `deep-review/SKILL.md` (10 KB) and `references/deep/deep-{logic,boundary,concurrency,resources,
absence-completeness,cross-cutting}.md` (98 KB total, about 25k tokens), plus an empty
`references/deep/.gitkeep`.

- Purpose: focused review of user-named files with "full" checklists and codebase searches.
- Input: a patch plus a list of focus files ("The user instructs which files to focus on").
  `{FILE_PATH}`, `{PATCH_PATH}`, `{SKILL_DIR}`. It reads the complete source of the file, not just
  the diff.
- Orchestration per focus file: Phase 0 context (class hierarchy, siblings, callers, lifecycle,
  state machine, invariants from Javadoc/tests, serialization trio); Phase 1 load "typically 2-4"
  domain checklists chosen by a table (SKILL.md "Domain Selection"); Phase 2 targeted Grep
  searches (equals/hashCode/serialize family, register/deregister, switch over enum, implements,
  callers, subclasses); Phase 3 cross-file symmetry, reinforcement, merge, 3-point test.
- Checklist entry format: `### Pattern name (weight: high|medium|low)` followed by bullet questions.
  Domain index: Logic (condition/comparison, sentinels, wrong variable, iterator, refactoring
  artifacts, inverted conditions), Boundary (off-by-one, null/bounds, ByteBuffer/I/O), Concurrency
  (TOCTOU, collections, visibility, lifecycle, counters, state machine, deadlock), Resources
  (serialization, leaks, lifecycle/config, file I/O crash safety, metrics), Absence+Completeness
  (registration, event coverage, field completeness, parallel path, visibility, interface/factory
  completeness, accumulation, retained-reference, idempotency, rollback), Cross-cutting
  (refactor/merge artifacts, shell scripts and platform, missing overrides, atomic writes, CLI
  output, versioning, filesystem identity).
- Output (SKILL.md "Report Format"): `Finding N: [title]`, `Location`, `Confidence`, `Domain`
  (Logic/Boundary/Concurrency/Resources/Absence/Completeness), `Pattern`, `What's wrong: 2-3
  sentences`, `Evidence`, `Suggested fix`, plus a per-file x domain coverage table and a cross-file
  symmetry section.
- Scale: one pass per focus file; cost grows with number of files and the 2-4 loaded checklists
  (each deep file is 10-22 KB). The README says it "starts with a heatmap pass" but the SKILL.md
  has no heatmap step; the user names the files. mega-review calls it once per HIGH/MEDIUM file.

### 1.6 targeted-review

Files: `targeted-review/SKILL.md` (13 KB), `references/report-format.md`,
`references/subagent-prompt-template.md`, `references/categories/INDEX.md` (17.6 KB) and 11
category files (196 KB total, about 49k tokens if all were loaded; the skill forbids that).

- Purpose: "Findings-driven targeted code review" for 50-1000 LOC patches; "not trivial 1-3 line
  changes", "not pure refactors", "not single comprehensive write-up of one file".
- Input: a patch or diff (commit, branch, staged), via path, ref, or paste. Needs the source tree
  to read surrounding code.
- Orchestration, seven phases (SKILL.md "Workflow"):
  1a. call `patch-explainer` skill; 1b. call a `codebase-analysis` skill in targeted mode (this
  skill is not in the tree: `git grep codebase-analysis` matches only README, targeted-review SKILL
  and its two reference files), or a lighter research subagent (<400 words: invariants, siblings,
  callers, recent bug-fix commits);
  2. 3-5 independent iterations: read INDEX.md, mark categories whose "Diff signals" match
  ("Typically 3-7 categories load per iteration. If you would load more than 8, re-examine");
  3. within loaded categories read full files and keep items whose "Look for" hint matches an actual
  code shape ("keep 3-12 per category per iteration");
  3b. items chosen in 2+ iterations are `priority`, others `speculative`;
  4. group into 2-5 foci, 5-15 items each; 5. one parallel subagent per focus using
  `references/subagent-prompt-template.md`; 6. merge, dedup, 3-point test.
- Category file format (every file): `# Category: Name`; paragraph; `## Diff signals (when to
  load this category)`; `## Findings` with `### F-NN: title`, one-sentence body, and
  `**Look for:** <code shape>`. Example (concurrency-and-locking.md F-01 "Atomic swap then drain
  window").
- Subagent confidence rubric (subagent-prompt-template.md, quoted): "HIGH: code construct exists
  in diff, you have evidence the bug occurs, you can point to specific failure inputs or scenarios.
  MEDIUM: code construct exists, the bug is plausible, but you couldn't fully verify the failure
  path or you're inferring some context. LOW: pattern match without strong evidence; flag for the
  human to investigate."
- Subagent finding schema: `## Finding: {title}`, `Location: {file:line}`, `Category:
  {category-id or "off-checklist"}`, `Confidence`, `What's wrong: {1-3 sentences}`, `Evidence`,
  `Suggested fix`; ends with `Checklist coverage: {N/M items applied}, {K off-checklist findings}`.
  Each item gets a disposition: APPLIES / DOES NOT APPLY / UNCERTAIN (uncertain reports at Low).
- Merged report (report-format.md): `# Targeted Review`, patch summary, categories loaded and
  skipped with one-word reasons, foci dispatched, findings ranked by confidence with `Found by`,
  `Category`, `Evidence`, `Suggested fix`; cross-cutting observations; "What was NOT reviewed";
  recommended follow-ups. Guidance: whole report fits one screen for small patches, 2-3 for larger.
- Scale: the cost is explicitly selective ("spend tokens on what matters for THIS patch"). The
  iteration scheme multiplies the cheap steps (INDEX read, item picking) by 3-5 and keeps the
  expensive step (subagent review) to 2-5 foci.
- Provenance statement (SKILL.md "Reference files"): categories are "project-agnostic patterns
  mined from real bug fixes across distributed-systems projects (Cassandra, Kafka, Iceberg)".
- Origin note (README.md): semgrep rules were tried first and abandoned as too noisy, so the
  catalog is meant for semantic LLM checks. README also says its evals are "somewhat more difficult
  to quantify" because the categories only fire on specific issues.

### 1.7 mega-review

File: `mega-review/SKILL.md` (19.6 KB). No reference files.

- Purpose: multi-pass review of large patches (1000+ LOC), feature branches, or commit ranges.
  "You MUST invoke /targeted-review, /shallow-review, and /deep-review".
- Input: Mode A, a git boundary (`<base>..<head>`, branch, or SHA); Mode B, a feature or file set
  with no range (asks the user to confirm the discovered file list, then diffs against `main`).
- Phases: 1 decompose and classify inline (git log --stat, diff --stat, risk HIGH/MEDIUM/LOW per
  commit and file, type = algorithmic | state machine | wiring | concurrency | documentation/config;
  writes `/tmp/mega_coverage.md`); 2 deep-review per HIGH/MEDIUM file (fresh subagent each);
  3 targeted-review once over all HIGH+MEDIUM files; 4 shallow-review per HIGH/MEDIUM commit;
  phases 2-4 run in parallel; 5A pattern amplification (generalize each found bug, grep codebase or
  patch, one subagent per pattern), 5B cross-commit consistency (changed signatures, renames),
  5C fix verification (one agent per "Fix" commit tries to re-trigger the original bug);
  5D optional extra passes; Coverage Gate (every file row green or gap-filled with shallow-review);
  6 merge and validate.
- Risk-assignment rules: HIGH file = deep + targeted (min 2 reviewers, also shallow via commit);
  MEDIUM = same; LOW = shallow only (min 1).
- Context discipline ("Chunking Strategy"): the orchestrator holds global state; each subagent gets
  its chunk plus a 100-200 word briefing and "must not receive the full patch".
- Plausibility rules, all four required (Phase 6): the code exists at file:line; "The bug is
  achievable: describe a concrete input"; "The result is wrong"; "Tests don't catch it". Findings
  failing any are discarded. Confidence: High = found by deep review or by 2+ phases; Medium =
  single phase with plausible trigger; Low = speculative.
- Output (Report Format): `[HIGH] Finding N: title`, `Location`, `Found by: Phase N`, `The bug`,
  `Trigger`, `Expected`, `Actual`, `Why tests miss it`, `Fix`; summary line counts; phase coverage
  table. Anti-patterns to omit: style/naming, performance, "might be wrong" without trigger,
  documentation mismatches.
- Scale/cost: roughly one deep run per HIGH/MEDIUM file plus targeted plus one shallow per commit;
  this is the most expensive path and is meant for a human-attended run. No limits are stated.

### 1.8 bug-archaeology

Files: `bug-archaeology/SKILL.md` and `references/{per-bug-format,synthesis-format,EVAL-PROMPT}.md`.

- Purpose: mine bug-fix commits from a repo's history and synthesize a generalized `PATTERNS.md`.
  This is how the author built the checklists; it is a catalog-building tool, not a PR review tool.
- Inputs: `--range` (default `HEAD~200..HEAD`), `--path`, `--since/--until`, `--limit` 200,
  `--batch-size` 10, `--output ./bug-archaeology/`.
- Git history use: yes. Phase 1 runs
  `git log --no-merges --pretty=format:"%H %s" ... | grep -iE '(fix|bug|patch|resolve|repair|correct|workaround|hotfix|regression|#[0-9]+|[A-Z]+-[0-9]+)'`,
  drops commits whose message is only cosmetic keywords, writes `QUEUE.txt`; Phase 2 runs
  `git show <hash>` per commit in batches (up to 5 concurrent batches); Phase 3 synthesizes.
- Data produced: per-bug `bug-NNNN-<slug>.md` with fields `Commit`, `Ticket`, `Detection Rule`
  ("One imperative sentence. Starts with 'When' or 'If'"), `Code Smell`, `Tags` (scope, category,
  code-pattern, severity, subsystem), `Root Cause`, `Example` (BEFORE/AFTER, at most 15 lines);
  `PROGRESS.md` (resume ledger); `PATTERNS.md` (grouped by category then code-pattern, singletons
  last, ticket IDs and class names stripped).
- Category enum (per-bug-format.md): `logic-error | race-condition | missing-null-check |
  off-by-one | resource-leak | wrong-constant | wrong-serialization | state-not-cleaned | deadlock |
  silent-skip | missing-override | non-atomic-write | wrong-filter-result`.
- Severity enum: `silent-wrong-result | crash | hang | data-loss | performance | cosmetic`.
- The 3000-bug corpus the README mentions is not in the tree; only the method is. So we cannot
  query the archaeology data directly, only re-run the method on trunk (expensive, offline, and
  out of scope for per-PR review).
- Complement to our reviewer-context: see section 5.

### 1.9 heatmap

Files: `heatmap/SKILL.md` and `heatmap/heatmap.py` (25 KB, Python 3, stdlib only: argparse,
colorsys, subprocess, re, dataclasses).

- Purpose: rank files and lines by recency-weighted churn, as a proxy for where bugs concentrate.
- Formula (heatmap.py docstring): `decay = 2^(-days/60)` (HALF_LIFE_DAYS = 60);
  `size_bonus = 1 + 1/(1 + lines/10)` (SMALL_CHANGE_SCALE = 10, small edits up to 2x);
  `commit_heat = decay * size_bonus`; file heat is the sum over commits; line heat is the sum over
  commits that touched the line, tracking line positions through diffs with a `VersionMap`.
- CLI: `heatmap.py repo [repo_path] --top N --since "2 years ago" --dir --exclude --json` and
  `heatmap.py file <path> [repo_path] --since --max-commits 500 --all --context 2 --json`.
  JSON for `repo`: `path, heat, commits, last_modified_days`; for `file`: `line, heat, content`
  (SKILL.md steps 2 and 4). Default excluded extensions cover docs, config, data, images, archives.
- Git calls: all through `git -C <repo> ...` subprocess. Repo level uses
  `git log --format='commit %H %at' --numstat -m --first-parent --since=...`; file level reads
  `git log -p` style hunks per file. Read-only.
- Workflow (SKILL.md): run repo heatmap, intersect with the PR's changed files
  (`git diff --name-only <base>...HEAD`), run line heatmap on 3-8 files, report "Heatmap Review
  Targets" as Priority 1..N with `heat`, `commits`, hot zones, why it matters, what to look for.
- Scale: repo-level scan walks two years of first-parent history of the whole repo each run, so for
  trunk it is slow. It is best precomputed once per base sha and cached, not run per PR.

### 1.10 patch-explainer

Files: `patch-explainer/SKILL.md`, `references/analysis_framework.md`, `references/ascii_patterns.md`.

- Purpose: ASCII-diagram explanation of a patch, class, subsystem, or repo: structure, flow, state
  transitions, before/after, assumptions, failure modes, concurrency.
- Input: a patch/diff, class, or subsystem. Output structure (SKILL.md "Output Structure"):
  Executive Summary (2-3 sentences), Visual Overview, and further sections (framework template:
  Summary, High-Level Structure, Key Behaviors, State Management, Critical Assumptions, Failure
  Modes, Concurrency Analysis, Before/After, Why This Change, Key Insights).
- No findings schema, no severity. It exists as Phase 1a input to targeted-review. Its value to us
  is the "assumptions, failure modes, concurrency" prompts; its ASCII output does not suit an HTML
  report and costs tokens.

### 1.11 cassandra-injvm-dtest

Files: `SKILL.md` (30.6 KB) and `references/{advanced_patterns,classloader_guide,cluster_utils}.md`
(about 57 KB).

- Purpose: authoring guide for in-JVM distributed tests (cluster creation, config, lifecycle,
  coordinator queries, `MessageFilters` fault injection, `IsolatedExecutor`, classloader pitfalls).
- Not a review skill; no findings format. It can serve as the knowledge base for a test-quality lens
  ("is this PR's test the right kind, does it use `Cluster.build(n)`, close the cluster in
  try-with-resources, use message filters for failure paths"). It is large; load selectively.

## 2. Dimension and category mapping

Rows are the union of review dimensions. "S" = shallow-review specialist (6 files), "D" = deep-review
domain file (6 files), "T" = targeted-review category file (11 files, with finding counts from
`grep -c '^### F-'`), "M" = mega-review (indirect, via S/D/T and its own passes). Paths omit the
`references/...` prefixes.

| Dimension | S | D | T (findings) | Bug patterns it looks for |
|---|---|---|---|---|
| Logic and conditions | logic.md (30) | deep-logic.md | conditions-and-predicates (38) | missing `return`, `else if` masking, `==` on value types, wrong operator polarity, inverted guards, wrong variable/constant, reversed-type bounds, sentinel in arithmetic, wrong error-message object |
| Boundaries and numbers | boundary.md (22) | deep-boundary.md | boundaries-and-numbers (46) | off-by-one, int overflow in unit conversion (`mebibytes*1024*1024`), `(int)` truncation, ByteBuffer position/limit, division by zero, `indexOf` then `substring` without -1 guard, time-unit mixups |
| Null and type safety | boundary.md (null part) | deep-boundary.md (null depth) | null-and-type-safety (37) | unguarded map/schema lookup, `File.listFiles()` null, bad casts, `Optional.orElse` eager, unboxing NPE, null on early-failure `close()` |
| Validation and input handling | boundary.md (partial) | deep-cross-cutting.md (parsing/shell) | validation-and-input-handling (40) | regex/delimiter anchoring, host:port and path parsing, suffix length limits, missing pre-conversion checks, unvalidated option strings |
| Concurrency and locking | concurrency.md (24) | deep-concurrency.md | concurrency-and-locking (40) | check-then-act, live-view iteration, signal before publish, shared `ByteBuffer` position, lock-order deadlock, blocking `get()` on own pool, missing volatile, refcount before read |
| Lifecycle and ordering | concurrency.md (partial), absence.md (m,t,u) | deep-concurrency.md (lifecycle) | lifecycle-and-ordering (44) | register before ready, init order, teardown order, polling without deadline, background thread in constructor, static-init side effects |
| State and resource cleanup | resources.md, concurrency.md | deep-resources.md (leaks) | state-and-resource-cleanup (39) | no try-with-resources, leak on mid-sequence failure, listener never deregistered, counter increment without rollback, tombstone/purge predicates |
| I/O and crash safety | resources.md (flush/fsync/abort) | deep-resources.md (file I/O) | io-and-crash-safety (26) | missing fsync before close, non-atomic rename, partial read/write loops, checksum range, multi-file atomicity, truncation flags |
| Serialization and versioning | resources.md (items 1-6) | deep-resources.md (serialization) | serialization-and-versioning (41) | serialize/deserialize/serializedSize drift, version-gated size arithmetic, stream wrapper bypass, enum ordinal decode, unconditional new wire field |
| Resources, metrics, config | resources.md (metric types, background tasks) | deep-resources.md (lifecycle, metrics) | state-and-resource-cleanup (partial) | Histogram vs Timer, metric on one branch only, config accepted but not threaded to builder, background task with no stop path |
| Absence (missing code) | absence.md (a)-(x) | deep-absence-completeness.md | api-contracts-and-completeness (partial) | listener without removal, new enum without switch update, parallel path B missing change, missing idempotency guard, missing version fallback |
| API completeness and contracts | completeness.md (22) | deep-absence-completeness.md | api-contracts-and-completeness (48) | new field not in equals/hashCode/toString/serialize/copy/builder, missing predicate override, visibility narrowing, `=` vs `+=` accumulation |
| Refactor aftermath | symmetry pass; absence (g) | deep-cross-cutting.md (refactor/merge) | refactor-aftermath (25) | stale name after rename, overload shim with stale default, narrowed type not propagated, merge drops input, dead branch after flag removal |
| Cross-path symmetry | "Pass 3: Cross-Path Symmetry" | Phase 3 cross-file | (none) | parallel class/version/event path not modified |
| Cross-commit and fix verification | (none) | (none) | (none); mega 5A/5B/5C | amplify a found pattern codebase-wide, stale callers, re-trigger original bug against a fix |
| Platform, shell, CLI, JDK | (none) | deep-cross-cutting.md | (none) | JDK version incompatibility, shell word splitting, locale, CLI fixed-width formatting, column access by position |
| Heat and history | (none) | (heatmap input) | (none) | churn-weighted focus selection (heatmap, bug-archaeology) |

Overlap summary:

- shallow and deep are the same six-domain taxonomy at two depths. The shallow checklists are
  "trimmed" subsets of the deep ones (shallow-review/SKILL.md "Specialist checklists (trimmed,
  ensemble mode)"). Running both on the same file mostly repeats questions.
- targeted is a second, orthogonal taxonomy over the same bug families. Rough projection:
  conditions + null + validation + boundaries = shallow Logic + Boundary; concurrency + lifecycle =
  Concurrency; state-cleanup + io-crash + serialization = Resources; api-contracts + refactor-aftermath
  = Absence + Completeness + Symmetry.
- Items unique to one taxonomy: targeted `validation-and-input-handling` and `io-and-crash-safety`
  have no dedicated shallow specialist (partly in boundary.md and resources.md). Deep
  `deep-cross-cutting.md` has shell, JDK-version, CLI, and filesystem-identity patterns that no
  targeted category covers.
- Not covered by any review skill: observability as a goal (only the metric-asymmetry items in
  resources.md, absence.md (x), deep-resources.md "Metrics & Observability Depth"), security (no
  auth/injection/secrets checklist; AGENTS.md instead points agents at
  `doc/modules/cassandra/pages/reference/security-model.adoc`), performance (mega-review
  anti-patterns explicitly exclude it), and test quality (mega-review has "Why tests miss it" only).

## 3. Scaling with diff size

| Diff size | Cassandra's own recommendation | Source |
|---|---|---|
| Small (under about 50 LOC) | shallow-review, then deep-review on flagged areas | README.md "Where Do I Start?" |
| 1-3 lines | direct review; targeted-review not worth it | targeted-review/SKILL.md "When NOT to use" |
| 50-1000 LOC | targeted-review (then deep-review on HIGH files) | README.md; targeted-review/SKILL.md |
| 1000+ LOC | mega-review (it decomposes and calls the other three) | README.md; mega-review/SKILL.md |
| Pure refactor | shallow-review symmetry pass is enough | targeted-review/SKILL.md "When NOT to use" |

Mechanisms that bound work:

- shallow: fixed 6 + 1 agents; per-agent work is O(diff), so it degrades past a few hundred lines
  (mega-review "Why This Exists": "A single pass of /shallow-review over 7000 LOC spreads attention too
  thin").
- targeted: 2-5 foci x 5-15 items, with category loading capped at about 8; the cap is what keeps
  large patches tractable.
- deep: bounded by the user's focus-file list, not by diff size.
- mega: context isolation per subagent, risk triage so LOW files only get shallow, and a coverage
  gate ("Do not proceed to Phase 6 until every row ... shows checkmark").
- Stated numbers (the only ones): 3-5 independent iterations; 3-7 (max 8) categories per iteration;
  3-12 items per category per iteration; 2-5 foci; 5-15 items per focus; 100-200 word briefings;
  up to 5 parallel archaeology batches; 10 commits per batch; default archaeology `--limit` 200.
- Token/time budgets: none stated. Approximate sizes if loaded in full (bytes / 4): shallow
  specialists 9-10k tokens (all six), deep checklists 25k, targeted INDEX 4.4k, all categories 49k.
  Our own budget must be set in cpr (section 6.6).

## 4. Output formats compared

| Skill | Finding fields | Confidence | Severity | Verdict |
|---|---|---|---|---|
| shallow | Location, Confidence, Flagged by, What's wrong | High/Medium/Low | none | none (coverage list only) |
| deep | Location, Confidence, Domain, Pattern, What's wrong, Evidence, Suggested fix | High/Medium/Low (High = confirmed by evidence) | none (pattern `weight` in checklist) | none |
| targeted | Location, Confidence, Found by, Category, What's wrong, Evidence, Suggested fix | High/Medium/Low (rubric in subagent template) | none | none; "What was NOT reviewed" |
| mega | Location, Found by (phase), The bug, Trigger, Expected, Actual, Why tests miss it, Fix | High/Medium/Low (High = deep or 2+ phases) | none | none; counts of H/M/L |
| bug-archaeology | Commit, Ticket, Detection Rule, Code Smell, Tags (severity), Root Cause, Example | n/a | silent-wrong-result, crash, hang, data-loss, performance, cosmetic | n/a |
| heatmap | path, heat, commits, last_modified_days; line, heat, content | n/a | n/a | n/a |

Nowhere do these skills emit an approve/reject verdict. The verdict in our tool must come from the
mapping rule in section 6.3.

## 5. Git history: bug-archaeology and heatmap vs our reviewer-context

Our `cpr/context.py` builds reviewer context from blame: `related_tickets(history)` groups blamed
lines by JIRA key through `credits.primary_key(commit.message)` and sums `lines` per ticket;
`experts(...)` and `suggest(...)` derive per-file experts and suggested reviewers from credit lines
(`cpr/context.py` lines 24-130). It answers "who and which tickets touched the lines this PR
changes".

| Capability | Ours | heatmap | bug-archaeology |
|---|---|---|---|
| Unit | lines the PR modifies, via blame | file and line churn over time | bug-fix commits matched by message regex |
| Time weighting | commit dates listed, no decay | 60-day half-life, small-edit bonus | none |
| Output | tickets, experts, suggested reviewers | ranked files, hot line zones (JSON) | detection rules and patterns (markdown) |
| Cost | blame over PR hunks (bounded by `hunks_*` budget) | repo log walk, slow on trunk | LLM per commit, offline batch |

How they could complement us:

1. heatmap: a PR-scoped, cheap variant is useful. Run only `heatmap.py file <path>` for the PR's
   changed files (3-8 files, `--max-commits 500`), or reimplement the formula in `cpr` over the
   `history` data we already fetch, and attach `heat` per file/line-range to the context file. That
   lets a lens prioritize "hot line zones" when the diff is large. The repo-level scan should be
   precomputed per trunk sha and cached; do not run it per PR. The script is read-only and stdlib
   only, so safe to execute against the clone at a fixed base sha (never against the PR worktree).
2. Fix-density signal: our blame-derived `related_tickets` already includes JIRA issuetype when
   looked up (`info.get("issuetype")`). Counting Bug-type tickets among them is a cheap analogue of
   bug-archaeology's "bug-fix commits in this area" and can be given to lenses as "this area has had
   N recent bug fixes: <keys>". This is also what targeted-review Phase 1b asks of codebase-analysis
   ("recent bug history in the affected area"), so we can supply it from data we already have
   instead of an LLM run.
3. bug-archaeology: do not run per PR. Its value for us is as a method for improving our own
   lens catalog (mine Cassandra history for `PATTERNS.md`) and as the source of the Detection Rule
   style ("When/If ... verify ...") for any checklist items we add.

## 6. Recommendations

### 6.1 Principle

Take the checklists, the item format, the confidence rubric, the 3-point test, and the plausibility
rules. Do not take the Skill/Agent orchestration, the patch-explainer and codebase-analysis
dependencies, or the multi-iteration category picking as-is. Our panel already provides parallelism
(one agent per lens, merged by `cpr/review.py`), so each lens should be a single flat agent with a
bounded checklist.

### 6.2 Proposed lens panel (replaces the four spec-flow lenses; `cassandra-standards` stays)

All lenses are read-only agents (`Read, Bash, Grep, Glob`) that follow the same input contract as
`cassandra-standards-reviewer` (worktree, base sha, context file) plus a new `checklists` input.

| Lens name | Replaces | Shallow file(s) | Deep file(s) (large/critical files) | Targeted categories (selected by INDEX signals) |
|---|---|---|---|---|
| `cass-logic-boundary` | `correctness` (part) | specialists/logic.md, specialists/boundary.md | deep-logic.md, deep-boundary.md | conditions-and-predicates, boundaries-and-numbers, null-and-type-safety, validation-and-input-handling |
| `cass-concurrency-lifecycle` | `correctness` (part) | specialists/concurrency.md | deep-concurrency.md | concurrency-and-locking, lifecycle-and-ordering, state-and-resource-cleanup |
| `cass-persistence-compat` | `security`/`observability` slots (see note) | specialists/resources.md | deep-resources.md | serialization-and-versioning, io-and-crash-safety, state-and-resource-cleanup (leak items only) |
| `cass-completeness-symmetry` | `test-rigor` slot (see note) | specialists/absence.md, specialists/completeness.md, the Pass 3 symmetry prompt | deep-absence-completeness.md, deep-cross-cutting.md | api-contracts-and-completeness, refactor-aftermath |
| `cassandra-standards` (existing) | n/a | n/a | n/a | n/a (keep as is, plus a rule for NEWS.txt etc.) |

Note on the slots we lose. The four generic lenses map to: correctness (covered, split in two for
focus and token budget), test-rigor, observability, security. The Cassandra skills give us a
four-lens split by bug family, not by those four concerns. Honest gap list:

- test-rigor: no Cassandra review skill. `cassandra-injvm-dtest/SKILL.md` is a test-authoring guide;
  mega-review has "Why tests miss it". Decision for the spec: either keep a slimmed generic
  test-rigor lens, or add an optional `cass-tests` lens fed with a condensed digest of
  cassandra-injvm-dtest (not the 30 KB original), plus AGENTS.md's "first create a regression test
  that reproduces the failure" rule.
- observability: only the metric-asymmetry items (resources.md items 13-14, absence.md (x)) are
  covered; those fall into `cass-persistence-compat`. No logging/diagnosability checklist exists.
- security: no checklist. Keep `cassandra-standards` pointing at the security model in AGENTS.md
  (`doc/modules/cassandra/pages/reference/security-model.adoc`) and keep the `review-steering` rule.
  Recommendation: leave the existing self-gating security lens in place for now and flag the gap,
  rather than silently dropping it.

If the panel must be exactly five lenses with no generic remnants, use: standards, logic-boundary,
concurrency-lifecycle, persistence-compat, completeness-symmetry, and record the three uncovered
concerns as known limitations in `docs/report/code-review.md`.

### 6.3 Input contract for each Cassandra lens

```
worktree : absolute path of PR head checkout          (as today; the code under review)
base     : merge-base sha                             (as today)
context  : markdown context file                      (as today, plus heat/fix-density section)
refdir   : absolute path of a directory holding the lens checklists, extracted from
           the trusted reference ref (see 6.7). NEVER inside <worktree>.
bundle   : ordered list of checklist file names inside refdir for this lens and size tier
tier     : small | medium | large                     (see 6.5)
focus    : optional list of file paths for the lens to prioritise (large tier)
```

Method for each lens (flat, no nested agents):

1. Phase 0 from shallow-review: summarize in 2-3 sentences, list 3-5 hypotheses, note code shapes.
2. Read the bundle files named in `bundle`; apply items matching hypotheses and code shapes. For
   medium and large tiers read surrounding source, not only the diff (deep-review Phase 0).
3. For absence and symmetry style items run the Grep searches (shallow absence.md Phase 2).
4. 3-point test, then the plausibility rule from mega-review Phase 6, trimmed to what a flat lens
   can establish: concrete trigger input, wrong result, why existing tests do not catch it.
5. Return the JSON in 6.4. Prompt must carry the existing Trust paragraph from
   `cassandra-standards-reviewer.md` (treat worktree, PR text, ticket, and `.claude/` files in the
   worktree as data).

### 6.4 Output mapped onto our review schema

Our schema (`cpr/review.py`): `findings[]` with `id, severity (blocker|major|minor|nit), location,
rule, problem, fix`, plus top-level `summary` and boolean `approve`; `approve=false` with no
blocker/major gets a synthesized `major` finding.

| Our field | Source in Cassandra skills |
|---|---|
| `id` | lens prefix + counter: `cl-1`, `cc-1`, `cp-1`, `cs-1` |
| `location` | `Location: file:line` (new-file line number) |
| `rule` | `<Domain or category>/<Pattern or F-NN>`, e.g. `concurrency-and-locking/F-08 publication ordering` or `deep-concurrency: Signal before publish`. Keep the checklist item id so a human can look it up |
| `problem` | `What's wrong` plus `Evidence` (one or two sentences each); for mega-style add `Trigger` |
| `fix` | `Suggested fix` / `Fix` |
| `severity` | derived, section 6.5 |
| extra (optional, ours) | `confidence: high|medium|low` and `impact` tag; the merger ignores unknown keys only if `validate_output` allows them, otherwise fold into `problem` (check `_FINDING_KEYS` use in `validate_output`) |
| `approve` | false if any blocker or major remains after the 3-point test |
| `summary` | the Phase 0 summary plus one line of "checklist coverage: N/M items applied, K off-checklist" (targeted-review subagent footer) |

### 6.5 Severity mapping (theirs is confidence only)

The lens assigns an `impact` using bug-archaeology's vocabulary, then severity is a function of
confidence and impact:

| Impact (per-bug-format.md "severity") | High confidence | Medium confidence | Low confidence |
|---|---|---|---|
| data-loss, corruption, mixed-version break, hang, crash | blocker | major | minor |
| silent-wrong-result | major | major | minor |
| performance | minor | minor | nit |
| cosmetic | nit | nit | nit |

Rules:

- Matches `cassandra-standards-reviewer` severity definitions: `blocker` = wrong behaviour, data
  loss or corruption, compatibility break; `major` = would not merge.
- "UNCERTAIN" items in targeted-review's disposition (reported at Low) become `minor` with the open
  question in `problem`. This also honors the existing instruction "if you are unsure, say so in
  `problem` and lower the severity".
- mega-review's discard rule (no concrete trigger means not a finding) should be applied in the
  lens: drop rather than emit a `nit` for hunches.
- Cross-lens reinforcement (shallow merge: Logic+Absence, Concurrency+Resources) is lost when lenses
  run separately; do it in `cpr/review.py merge` by raising one level when two lenses report the
  same file within a few lines. Optional, spec-level decision.

### 6.6 Which lens runs for which diff size

Measure changed non-test LOC from `git diff --numstat <base>...HEAD` before launching lenses. The
orchestrator (the review-pr skill / `cpr`) picks `tier` and `bundle`; lenses do not choose.

| Tier | Non-test LOC | Bundle per lens | Notes |
|---|---|---|---|
| small | under 50 (and docs-only gets no lenses) | shallow specialist file(s) only (about 1.5-3k tokens per lens) | Matches README "small patch -> shallow". Skip lenses whose domain has no diff signal (INDEX signals as a cheap pre-filter), but never skip the symmetry lens on a patch with a new field/enum/registration |
| medium | 50-1000 | shallow file(s) plus the targeted category files whose INDEX "Diff signals" match (cap 8 categories total across lenses; single iteration, not 3-5) | Do category selection in cpr code using the signal bullets (regex/keyword pre-filter), then let the lens do item picking. Avoids the 3-5 x iteration cost |
| large | over 1000 | per-file: deep checklist for HIGH/MEDIUM files only, shallow for LOW; `focus` set to top files by risk and heat | Mirror mega-review risk triage (HIGH/MEDIUM/LOW) as code in `cpr` (churn, file type, existing heat data) rather than an LLM Phase 1. Cap files per lens; report "What was NOT reviewed" so the report is honest about coverage |

Risk triage heuristics lifted from mega-review Step 1c-1d: HIGH = new algorithms, state machines,
bootstrap/recovery, orchestration layers; MEDIUM = new control flow with multiple callers; LOW =
renames, moves, test-only, docs. Fix commits get extra scrutiny (Phase 4b: "Fix commits have a
higher-than-average bug rate"); our `context.json` already knows the PR's JIRA issue type, so a Bug
ticket can raise the tier by one for fix-verification (5C), i.e. ask the standards or logic lens to
try to re-trigger the original bug against the patch.

Budget guard (not in upstream): cap per-lens input at a configured token count; if the tier's bundle
exceeds it, drop categories by INDEX relevance, and record the dropped list in the lens summary.

### 6.7 Runtime loading versus vendoring

Recommendation: load at runtime from a trusted ref of the clone, pinned per run, with a vendored
fallback only for offline/test use.

Why runtime:

- Upstream is actively authored ("Evals give you a way to quantify and iterate"; items such as
  absence.md (r)-(x) read like recent additions) and the stated goal is to "track upstream".
- Our `.work/cassandra` clone already exists and the pipeline fetches it.

Why not "the PR's base branch": `cassandra-6.0`, `cassandra-5.0`, `cassandra-4.1` contain no
`.claude/` at all (verified with `git ls-tree`). Only trunk has the skills. So the reference ref is
`origin/trunk` regardless of the PR's target branch. Note this means the checklists may mention
trunk-only constructs when reviewing a 5.0 PR; add one line to the lens prompt: "ignore items about
APIs that do not exist in the base branch".

Trust rules (hard requirements for the spec):

1. Resolve the reference ref to a commit sha once per run (`git -C .work/cassandra rev-parse
   origin/trunk` after fetch), record it in the report ("lens checklists: apache/cassandra trunk
   @ <sha>"), and read only with `git show <sha>:.claude/skills/<path>` or `git archive`. Never
   read these from the PR worktree, and never from `HEAD`, a working tree, or a PR ref.
2. Extract the chosen files into a run-scoped directory outside the worktree (for example
   `<run>/refdir/`) with a fixed allow-list of paths (the 6 specialists, 6 deep files, INDEX, 11
   categories, report-format and the two eval prompts if needed). Reject any other path. Pass `refdir`
   to agents; instruct them not to read `.claude/` inside the worktree.
3. Why this matters: a PR can add or modify `.claude/skills/**`, `AGENTS.md`, `CLAUDE.md` (the
   existing agent file already tells lenses to treat these as data). A PR that edits the skills
   would otherwise steer the review. Also: if the PR touches `.claude/` or `AGENTS.md`, surface
   that as an informational finding in the standards lens.
4. The checklists are prompts. Even from trunk, treat them as a trusted-but-versioned dependency:
   sanity-check at load time (file exists, size under a cap such as 64 KB, UTF-8 text, no
   tool-use instructions injected into the lens prompt beyond the checklist body). The orchestrator
   should wrap them as "checklist content" and keep our own instructions outside it.
5. Pin for reproducibility: allow a config override `lens_ref: "<sha>"` in `cpr/config/panel.json`
   so a rerun of an old report uses the same checklists. Default `origin/trunk` resolved at run time.
6. Failure mode: if the ref lacks the files (clone not fetched, upstream renamed the directory),
   fail the lens as `status: missing` in `cpr/review.py` merge (existing behavior marks the panel
   incomplete and unapproved) rather than falling back silently to a stale copy. A vendored
   snapshot should be used only when the operator opts in (`--offline-lenses`) and the report must
   say so.

What to vendor, if anything: nothing from upstream by default. We do need our own thin files:
`cpr/config/lenses.json` (lens name -> bundle files by tier, INDEX signal keywords for the pre-filter)
and the lens agent prompts (`.claude/agents/cass-*.md`) that carry method, trust, severity mapping and
JSON contract. Those are ours and contain no copied checklist text. This also avoids reproducing
upstream text (section 7).

### 6.8 Spec work items for `cassandra-lenses`

1. `cpr/config/lenses.json` plus loader that resolves `lens_ref` to a sha and extracts allow-listed
   files to `refdir`.
2. INDEX signal pre-filter: parse `references/categories/INDEX.md` ("## <name>" then "**Diff
   signals:**" bullets) at runtime so new categories are picked up automatically; fall back to loading
   by lens mapping when parsing yields nothing.
3. Tier selector from `git diff --numstat`.
4. Four lens agent definitions with the contract in 6.3 and the mapping in 6.4/6.5.
5. `panel.json` swap and `docs/report/code-review.md` update, including known limitations
   (security, observability, test-rigor) and the recorded checklist sha.
6. Optional heat/fix-density section in the context file (section 5).
7. Eval harness (section 8).

## 7. License and provenance

- `AGENTS.md` and the repo are ALv2 (the skills README ends: "Licensed under the Apache License,
  Version 2.0. See ../../LICENSE.txt").
- Per-file headers: of the 77 files under `.claude/` on trunk, only `heatmap/heatmap.py` has the ASF
  header (16 lines: "Licensed to the Apache Software Foundation (ASF) under one or more contributor
  license agreements ..."). The other 76 (all `*.md`, `install.sh`, `.sh`, `.tla`) have none (checked
  by grepping the first 30 lines for "licensed|apache license|SPDX").
- Why that is allowed: `.build/build-rat.xml:46` has `<exclude name=".claude/**/*"/>` and
  `build.xml:1212` and `build.xml:1265` have `<exclude name=".claude/**" />`, so the Apache RAT
  license check skips the directory. The headers are therefore not required to pass the build, and
  absence of a header does not mean a different license; the repo-level `LICENSE.txt` governs.
- No authorship note exists in the files themselves, except the README's first-person narrative.
  `git log` shows a single commit, `3831d8265d`, "Add suite of skills for AI" (2026-04-27).
- Reuse implications: runtime reading (not copying) from the clone avoids redistribution questions.
  If we ever vendor or quote checklist text in docs or the HTML report, include the ALv2 notice and
  attribute "apache/cassandra .claude/skills (ALv2)" with the commit sha, and mark our changes. A
  NOTICE entry is prudent. Short factual references (item ids such as `F-08`, category names) in
  findings are fine; do not paste whole checklist sections into reports.
- Targeted-review's categories claim origin in Cassandra, Kafka, and Iceberg bugs
  (targeted-review/SKILL.md "Reference files"); all are Apache projects, but we have no evidence of
  third-party text beyond that statement.
- AGENTS.md "Git Workflow" requires `Assisted-by: AGENT_NAME:MODEL_VERSION` in commit messages for
  AI-assisted contributions. This is a contribution rule for patches to Cassandra, not for our
  reports, but if a lens ever suggests `fix` text that users paste into patches, our docs should
  mention it (see also the `cassandra-contribution` skill's AI-disclosure guidance).

## 8. Evaluation methodology we can reuse

Two documents: `shallow-review/EVAL-PROMPT.md` (stale, 5 specialists, old file names) and
`bug-archaeology/references/EVAL-PROMPT.md` (current, works for any of the four review skills).
Method:

1. Pick a known fixed bug: a `bug-NNNN-*.md` file (needs the archaeology corpus, which is not in the
   tree), read its fix commit (`FIX_HASH`).
2. Find the introducing commit: take the first removed line of the fix in the primary non-test Java
   file, then `git blame -L <line>,<line> <FIX_HASH>~1 --porcelain -- <file>`; that is `INTRO`.
3. Extract the introducing diff: `git diff ${INTRO}~1 ${INTRO} -- <file> > /tmp/eval_patch.diff`.
4. Run the review on that patch (shallow: patch path; deep: patch plus focus file; targeted and mega:
   patch path).
5. Score against the bug's `## Root Cause` into four classes: Exact (found the specific bug that
   was later fixed), Partial (right area or pattern, different specific issue), Different bug (real
   bugs but not the target), Miss.
6. Aggregate. Target stated by the author: ">90% hit rate (exact + partial), <5% miss rate". For
   shallow-review also track per-specialist hits; compare skills side by side in a table (bug x
   skill). Optional baseline: a single generalist agent with the patch only (shallow EVAL "Comparison
   Eval: Single vs Ensemble").
7. "Prodding" for misses: tell the skill what it missed and ask "Which checklist or pattern ... would
   have helped you find it? If none exists, propose a new item to add." Use the answers to improve
   the checklist.
8. Volume and noise metrics from the README datum: findings per commit, share of High+Critical,
   share of Low.

How we reuse it for `cassandra-lenses`:

- Build a small local corpus without the missing archaeology data: use real fix commits on trunk that
  carry `CASSANDRA-NNNNN` keys (our `credits.primary_key` already extracts them) and tag them as bug
  type via JIRA lookup (`issuetype`). Blame to the introducing commit exactly as in step 2. 20-30
  patches is enough to compare lens bundles (shallow-only vs shallow+targeted) and tiers.
- Score with the four-class rubric, plus our two additions: false-positive rate (findings that
  fail the 3-point test on human read) and severity calibration (share of blocker/major among
  Exact hits).
- Hold-out discipline from the README: evaluate on bugs the checklists were not mined from. Since
  the corpus is mined from Cassandra history, prefer bugs introduced after `3831d8265d` (2026-04-27)
  or in subsystems under-represented in the checklists.
- Use the eval to decide the tier thresholds (50 and 1000 LOC) empirically rather than adopting the
  README's numbers.
- Do not run evals inside the review pipeline; keep them as an offline command (`cpr eval-lenses`)
  so production reports are not slowed.

## 9. Open questions for the spec

1. Exactly which generic lenses survive: drop all four (accept gaps in security, observability,
   test-rigor) or keep security self-gating (recommended) and fold observability into
   `cass-persistence-compat`?
2. Should the lens return a `confidence` field in addition to `severity` so the HTML report can show
   it? It requires a change to `validate_output` and the renderer.
3. Do we implement the 3-5 iteration category picking? Recommendation: no (cost); implement a single
   deterministic INDEX-signal pre-filter in `cpr` and one LLM pass.
4. Do we pass patch-explainer-like context? Recommendation: no; our context file (PR text, ticket,
   blame-based related tickets, experts) plus Phase 0 is the cheaper equivalent.
5. Does the clone refresh on every run, and who owns `lens_ref` pinning in CI?
6. The upstream skills may be refactored (single commit so far). Add a smoke test that fails loudly
   if the allow-listed files disappear or if INDEX.md no longer parses into category sections.

## 10. Source index (files read)

README.md; install.sh; shallow-review/SKILL.md; shallow-review/EVAL-PROMPT.md;
shallow-review/references/general/specialists/{logic,boundary,concurrency,resources,absence,completeness}.md;
deep-review/SKILL.md; deep-review/references/deep/{deep-logic,deep-boundary,deep-concurrency,
deep-resources,deep-absence-completeness,deep-cross-cutting}.md; targeted-review/SKILL.md;
targeted-review/references/{report-format,subagent-prompt-template}.md;
targeted-review/references/categories/INDEX.md and all 11 category files (headers, signals, and
sample findings read; finding counts via grep); mega-review/SKILL.md; bug-archaeology/SKILL.md and
its 3 references; heatmap/SKILL.md and heatmap.py (header, formula, CLI, git calls);
patch-explainer/SKILL.md and its 2 references (headings); cassandra-injvm-dtest/SKILL.md (headings
and overview) and reference file names; AGENTS.md; CLAUDE.md; `.build/build-rat.xml`; `build.xml`.
Not in scope but present: tla-plus/, write-reproducer/.
