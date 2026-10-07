# Merging duplicate lens findings, and evaluating new lenses

Research for the `cassandra-lenses` change. Two parts: (1) a deterministic way to
collapse findings that several lenses report about the same issue; (2) a small
benchmark and harness to show the Cassandra-native lenses are at least as good as the
current generic ones. Nothing in the project was modified; the scoring scripts live
in the session scratchpad (`score.py`, `lens_merge.py`).

Inputs: `cpr/review.py` (current merge), `cpr/config/panel.json`, and the five lens
outputs for PR #5201 (`.work/pr/5201/d1095cbd.../lenses/*.json`).

---

## Part 1. Duplicate merging

### 1.1 What the merge does today

`cpr/review.py:merge()` keeps every finding under its lens. Panel approval is
`complete and all(lens.approve) and not must_fix`, where `must_fix` is every blocker/major
finding across lenses, so one issue seen by four lenses counts and prints four times.

### 1.2 The 11 findings on PR #5201, clustered by hand

PR #5201 backports CASSANDRA-21649 to 4.0 (`SSTable.delete` sorts components by mtime).
Security returned 0 findings. The other four lenses returned 11.

| Cluster | Underlying issue | Members (lens) | Severities |
|---|---|---|---|
| A | `FileUtils.delete` replaces `deleteWithConfirm`; failed deletes are silent and the tidier no longer retries (`SSTable.java:121`) | cs-1 (standards), C2 (correctness), OBS-1 (observability), TR-3 (test-rigor) | major, major, **blocker**, major |
| B | `SSTableTidier.run` still deletes DATA first, so the ticket's scenario survives (`LogTransaction.java:396`) | cs-2 (standards), C1 (correctness), TR-2 (test-rigor) | major, major, major |
| C | No regression test in `LogTransactionTest` for partial delete with staggered mtimes | cs-3 (standards, location `ticket`), TR-1 (test-rigor, `SSTable.java:113`) | major, major |
| D | New comment says "overall SSTable timestamp" without naming the `verifyRecord` invariant | cs-4 (standards, `SSTable.java:113`) | minor |
| E | No CHANGES.txt entry / commit message format | cs-5 (standards, `CHANGES.txt:1`) | minor |

Raw 11 findings, 5 issues. Duplicate rate `1 - 5/11 = 55%`. Raw must-fix count 9
(1 blocker + 8 major); merged must-fix count 3 (A, B, C).

Two judgement calls that any algorithm will have to live with:

* **TR-3 and TR-2 are phrased as test gaps** ("no test pins the failure contract",
  "test must go through the real tidier path") but they sit on the defect's line and
  quote the defect's identifiers. I put them with the defect (A, B), because a reader
  who fixes A has also dealt with TR-3's request. The alternative is to treat them as
  members of C (test gaps). The algorithm below follows locality, so it agrees with my
  choice; if the team prefers "all tests in one cluster", that needs a `kind` tag,
  which is out of scope here.
* **cs-4 and TR-1 share `SSTable.java:113` but are different issues** (a comment
  wording nit vs a missing test). This is the trap for any location-only rule.

### 1.3 Algorithm

Pure Python 3 stdlib. Same-lens pairs are never merged (a lens that lists two findings
meant two). Clustering is greedy union in descending score order, with a guard that
refuses a union if the two groups already share a lens. That limits single-link
chaining: a cluster can never hold more findings than there are lenses.

For each cross-lens pair `(a, b)`:

```
T  = 0.4 * jaccard(idents(a.problem), idents(b.problem))
   + 0.3 * jaccard(words(a.problem),  words(b.problem))
   + 0.3 * jaccard(idents(a.fix),     idents(b.fix))          # text score
Lb = location bonus:
       both "path:line", same path, |dline| <= 3   -> 0.30
       same path, |dline| <= 10                    -> 0.15
       either side is not path:line (ticket, "(lens report)", "ticket") -> 0.10
       different path / far                        -> 0.00
S  = T + Lb
merge edge  iff  T >= 0.18  and  S >= 0.40
```

Definitions:

* `idents(text)`: tokens matching `[A-Za-z_]\w*(\.\w+)*` that look like code: contain a
  lower-to-upper transition (`failedDeletions`, `deleteWithConfirm`), start with 2+
  capitals then a lowercase (`SSTable`, `FSWriteError`), or are dotted
  (`FileUtils.delete`). Dotted names also contribute their segments. Drops `*.java`.
* `words(text)`: lowercase alphabetic tokens, stop words and tokens shorter than 3
  removed, crude suffix stemming (`ing ed es s ation`).
* The `T >= 0.18` floor stops "same line, different topic" from merging on location
  alone. The `Lb` of 0.10 for non-file locations means a `ticket` finding needs
  `T >= 0.30` to merge with anything.
* `rule` is deliberately not scored. Rules differ in wording per lens (`correctness`,
  `observability`, "Error handling: no swallowed failures ...") and carried no signal.

Full implementation (about 90 lines, stdlib only) is `lens_merge.py` in the session scratchpad; it is
`clusters(findings)` = score all cross-lens pairs, keep edges with `T >= 0.18 and S >= 0.40`, union
strongest first, skip a union when the two groups share a lens.

### 1.4 Pairwise scores on #5201

All 55 pairs computed (final code, T floor 0.18). The 18 highest, then the rest:

| Pair | T | Lb | S | Same lens | Outcome | Gold |
|---|---|---|---|---|---|---|
| cs-2 / TR-2 | 0.527 | 0.30 | 0.827 | no | merge | B |
| cs-1 / C2 | 0.474 | 0.30 | 0.774 | no | merge | A |
| cs-2 / C1 | 0.457 | 0.30 | 0.757 | no | merge | B |
| C2 / OBS-1 | 0.448 | 0.30 | 0.748 | no | merge | A |
| cs-1 / OBS-1 | 0.432 | 0.30 | 0.732 | no | merge | A |
| C1 / TR-2 | 0.420 | 0.30 | 0.720 | no | merge | B |
| C2 / TR-3 | 0.325 | 0.30 | 0.625 | no | merge | A |
| cs-1 / TR-3 | 0.307 | 0.30 | 0.607 | no | merge | A |
| OBS-1 / TR-3 | 0.231 | 0.30 | 0.531 | no | merge | A |
| cs-3 / TR-1 | 0.372 | 0.10 | 0.472 | no | merge (ticket wildcard) | C |
| cs-4 / TR-1 | 0.135 | 0.30 | 0.435 | no | **rejected by T floor** | D vs C, distinct |
| cs-3/C1, cs-3/cs-4, cs-4/C1, cs-2/cs-3, C1/TR-1, cs-3/TR-3, cs-1/cs-4 | 0.05-0.24 | 0-0.15 | 0.20-0.30 | mixed | reject | distinct |
| other 37 pairs | | | <= 0.2 | | reject | distinct |

Result of the greedy pass: `{cs-1, C2, OBS-1, TR-3}`, `{cs-2, C1, TR-2}`,
`{cs-3, TR-1}`, `{cs-4}`, `{cs-5}`. This is exactly the hand clustering (5 clusters,
same members). All 10 within-cluster pairs (A 6, B 3, C 1) merged; none of the other 45 did.

Margins, stated plainly because this is tuned on one PR:

* Smallest merged `S` is 0.472 (cs-3/TR-1); largest rejected `S` that was not already
  blocked by the T floor or the same-lens rule is 0.299. Comfortable.
* The dangerous pair is cs-4/TR-1: same file, same line, `S = 0.435`, which would
  merge on `S` alone. Only the T floor stops it (T 0.135 vs floor 0.18; smallest merged
  T is 0.231). An earlier 0.15 floor passed with 0.015 to spare; 0.18 is the midpoint
  of the gap. The T floor is the load-bearing constant and needs more PRs behind it.
* cs-3/TR-1 merges only because of the `ticket` wildcard bonus; its T is 0.372. If a
  test-gap finding at a ticket location uses different vocabulary it will stay
  separate. That fails safe (a duplicate remains), which is the right direction.

Tuning plan: store each benchmark run's lens JSON as a fixture with a hand-labelled
partition; a golden test asserts the exact partition and prints min merged / max rejected
`S` and `T`, so a change that narrows a margin shows in review.

### 1.5 Merged record shape

```json
{
  "id": "m1", "severity": "blocker",              // max over members
  "severity_spread": {"blocker": ["observability"], "major": ["cassandra-standards", "correctness", "test-rigor"]},
  "lenses": ["observability", "correctness", "cassandra-standards", "test-rigor"],  // panel.json order
  "location": "src/java/.../SSTable.java:121",    // primary member's
  "locations": ["src/java/.../SSTable.java:121"], // all distinct, primary first
  "rule": "observability", "problem": "...", "fix": "...",   // primary member's
  "also_fixes": [{"lens": "test-rigor", "fix": "..."}],     // fixes with idents-Jaccard < 0.3 vs primary
  "members": [{"lens": "...", "id": "OBS-1", "severity": "...", "location": "...", "rule": "...", "problem": "...", "fix": "..."}],
  "merge": {"size": 4, "min_pair_score": 0.531}
}
```

* **Severity = max.** OBS-1 says blocker, the rest major. `severity_spread` shows it was
  one lens's call. Median would hide a lens that saw real impact.
* **Primary** (supplies text and location): highest severity, then most identifiers in
  `problem + fix`, then earliest lens in `panel.json`. For A that is OBS-1. Nothing is
  discarded: `members` keeps all texts. In B, TR-2's fix (test through the real tidier
  path) differs from the code fix and survives as `also_fixes`; in A all four fixes say
  "use `deleteWithConfirm`" and collapse.
* Non-file locations (`ticket`, `(x lens report)`) go into `locations` but never become
  primary when a file location exists. The synthetic `unexplained-<lens>` finding is
  exempt from merging.

### 1.6 Approval and must-fix counting

* Per-lens `approve` and `summary` are unchanged; lens JSON keeps raw findings. The merged
  list is a view on top.
* Panel `must_fix` = merged records with severity blocker/major. For #5201: 3 (A, B, C)
  instead of 9. Report headline: `5 issues (11 raw findings, 4 lenses)`.
* The verdict cannot flip: a cluster is must-fix iff at least one member is, so
  `approved` is logically unchanged. The merge changes counts and display only.
* Derived per-lens stats `unique` (clusters only that lens found) and `corroborated`
  feed Part 2. `explain_notes()` emits one note per merged record with lens names joined.

### 1.7 Deterministic merge vs an LLM "lead reviewer" pass

| | Deterministic | LLM consolidation |
|---|---|---|
| Reproducible | yes | no; makes benchmark deltas noisy |
| Can drop or invent findings | no; `members` keeps all text | yes; a summarising pass is where a finding quietly disappears |
| Cost / latency | milliseconds | one more large call after the slowest lens |
| Testable | golden-file test on stored lens JSON | needs another LLM eval |
| Paraphrase with no shared identifiers | weak, fails safe (duplicate remains) | strong |
| Re-rank, write verdict prose | no | yes |

Recommendation: **ship the deterministic merge only.** It reproduces the hand clustering
on the one real sample, and its failure mode is a leftover duplicate, not a lost finding.
If a lead pass is wanted later, limit it to presentation (summary and ordering written
from the merged list, with a check that every merged `id` appears) or to tie-breaking the
grey band `0.30 <= S < 0.40`, with decisions logged. Neither belongs in the first change.

---

## Part 2. Evaluating lens quality

### 2.1 Approach

"At least as good" needs a measurable unit: the **known issue**, a real defect a competent
reviewer should flag in a specific diff, with a public source. Two kinds exist:

* **Hard** (post-merge): a later bug ticket says it was introduced by an earlier ticket.
  Human review missed it, so a lens that finds it beats the original review.
* **Soft** (review-time): a maintainer's PR comment pointing at a real defect or design
  bug. The diff is the PR head at comment time (`original_commit_id` in
  `gh api repos/apache/cassandra/pulls/N/comments`), not the final head.

### 2.2 Benchmark cases

Sources fetched read-only on 2026-10-07 (JIRA REST GET, `gh api` GET). Ranges are
`base..head` in apache/cassandra.

**B1. CASSANDRA-19987, Direct IO for compaction reads (hard + soft).** PR #4178, commit
`6f5fe8c06d58`, range `940739a48897..6f5fe8c06d58` (43 files, +1666/-234). Known issues,
from CASSANDRA-21671 and fix PRs #5168/#5202/#5210:
1. `ThreadLocalReadAheadBuffer` caches `Block` in a static `FastThreadLocal<Map<String,
   Block>>` keyed by path (line 46); a second instance reuses the block, skips setup, and
   its `bufferSize` stays `-1` (lines 55, 92), so `ByteBuffer.limit(-1)` throws. major.
2. The same per-thread cache is unbounded and leaks (CASSANDRA-21684, linked as a
   duplicate from 21671). A reviewer warned at review time: aweisberg on
   `CompressedChunkReader.java:127`, thread-local memory must return promptly on close.
3. Compressed scans pollute the chunk cache (21671 title; fix touches `ChunkCache.java`).
Soft extra: aweisberg `SSTableReader.java:1437`, file handle leaked on exception.

**B2. CASSANDRA-20829, index notification for fully expired SSTables (hard).** PR #4313
(4.0; #4300 original), commit `eb9586dc6844`, range `f4eb55097eaf..eb9586dc6844` (5 files,
+162). Known issues, from CASSANDRA-21577 and PR #5027:
1. `maybeNotifyIndexersAboutRowsInFullyExpiredSSTables` (`CompactionTask.java:451`, scanner
   `try` at 468) has no catch: a read error or throwing indexer aborts compaction and the
   expired SSTables are never obsoleted. major.
2. Only `partition.next()` rows reach `indexer.removeRow` (about line 500); the static row is
   never delivered. major.
3. New `Index.notifyIndexerAboutRowsInFullyExpiredSSTables()` defaults to `true`;
   `NoOpIndex`, `PaxosUncommittedIndex`, `RouteJournalIndex` inherit it and force pointless
   scans on `system.paxos`/Accord tables. minor.

**B3. CASSANDRA-21113, PasswordObfuscator (hard).** PR #4887, commit `22bbac9d6ab7`, range
`d30ac083b811..22bbac9d6ab7` (3 files, +134/-3). Known issue, from CASSANDRA-21559 and PR
#5012: the patch matches only the `''`-doubled form of the password, so
`CREATE ROLE r WITH PASSWORD = $$pa'ss$$` is written to the audit log in cleartext
(`PasswordObfuscator.java` about lines 73-79). major. Smallest case; good for fast runs.

**B4. CASSANDRA-21546, pluggable default role initializer (hard + soft).** PR #4990, commit
`bd22f9d3eea8`, range `78817fa41b32..bd22f9d3eea8` (39 files, +1499/-168). Hard issue, from
CASSANDRA-21686 and PR #5165: a `password_hash` parameter shows unredacted in
`system_views.settings`; the fix is in `SettingsTable.java`, a file **not in the diff**, so
tag it `stretch` (needs reasoning about unchanged surfaces). Soft issues from PR 4990
review: smiklosovic on `IDefaultRoleInitializer.java:88` (log text names
`CassandraRoleManager` in a generic interface), `:86` (declared method never called),
`AuthConfig.java:107` (initializers statically coupled to `CassandraRoleManager`).

**B5. CASSANDRA-20829 at review time (soft).** PR #4300 (base cassandra-4.1 `62150b08d5ed`,
head `e0fefea1830e`). blambov: the new SPI flag must default to `true` and be overridden by
SAI/SASI (`Index.java:443`); build index transactions once per partition, not per row
(`CompactionTask.java:196`). Tests parity with a maintainer's design review on a first draft.

**B6. CASSANDRA-21649, PR #5201 (seed).** Base cassandra-4.0 `3ccf94763b9f`, head
`d1095cbdca41`. No GitHub review comments. Known: the tidier still deletes DATA first
(`LogTransaction.java:396`), stated in the ticket itself. The silent `FileUtils.delete`
(`SSTable.java:121`) is verifiable from the code but its only evidence is the panel output,
so B6 is the **merge golden fixture**, not a recall target. (Caleb Rackliffe's JIRA comment
on 2026-09-11 mentions one trunk-PR comment I could not locate.)

### 2.3 Contamination rules

* Build the context file from JIRA as of the commit date: drop later comments and issue
  links. CASSANDRA-19987 has a `Reference` link to CASSANDRA-21671, which names the bug.
* Worktree at `head` only; never expose the fix PR, follow-up ticket key, or later commits.
* Old and new panels get identical context, model and settings. Whether the model has seen
  the fixes in training must be rechecked per model; B1, B3, B4 post-date mid-2026.

### 2.4 Known-issues file

`bench/cases/<id>.json`, one per case:

```json
{"case": "B3-21113", "pr": 4887, "base": "d30ac083b811", "head": "22bbac9d6ab7",
 "ticket": "CASSANDRA-21113", "context_cutoff": "2026-06-19",
 "issues": [{"id": "K1", "tier": "hard", "severity": "major",
   "source": "https://issues.apache.org/jira/browse/CASSANDRA-21559",
   "files": ["src/java/org/apache/cassandra/cql3/PasswordObfuscator.java"], "lines": [70, 85],
   "terms_all": ["$$"], "terms_any": ["escape", "quote", "cleartext", "audit", "obfuscat"],
   "summary": "Only the ''-doubled form is matched; $$...$$ literal leaks the password"}]}
```

A merged finding **matches** an issue when one of its `locations` is in `files` within
`lines` +/- 15 (any location when `files` is empty, for stretch issues) and its lowercased
`problem + fix` has every `terms_all` and at least one `terms_any`. This is a cheap first
pass; unmatched known issues and unmatched findings go to human review, so the matcher is
never the final judge.

### 2.5 Metrics

| Metric | Definition |
|---|---|
| Recall (hard, soft) | matched issues / issues, over all cases and runs; also counted at major+ only |
| Raw and merged findings | count per case before and after the Part 1 merge |
| Duplicate rate | `1 - merged/raw` (measures the merge, reported not gated) |
| Must-fix count | merged blocker/major records per case |
| Unique-lens share | per lens, clusters only that lens found / its clusters |
| False-positive rate | spot check: share of sampled findings a human marks `wrong` |
| Cost | tokens and wall time per panel run |

Spot check: per run, sample up to 8 merged findings that matched no known issue. A human
labels each `real`, `nit`, or `wrong` (incorrect or hallucinated). Labels are cached in
`bench/labels.json` keyed by `sha1(case + location + problem[:200])`, so reruns only ask
about new text. Unlabelled items are reported as unlabelled, never as passes.

### 2.6 Harness design

```
bench/cases/*.json   bench/labels.json   bench/runs/<panel>/<case>/<n>/{lenses/*.json,merged.json}
cpr/bench.py         # about 150 lines, stdlib + existing cpr modules + gh/git
```

* `python -m cpr.bench run --panel PANEL.json --case all --repeat 3`: per case, create a
  worktree at `head`, build the cut-off context (2.3), run the panel as `/review-pr` does,
  save lens JSON, apply the deterministic merge, save `merged.json`.
* `python -m cpr.bench score --panel A --against B`: match findings to known issues, print
  the 2.5 metrics per case and in total with per-run min/mean (one LLM run proves nothing),
  list "found by A not B" and the reverse, list unlabelled spot-check items and exit
  non-zero while any remain.
* Input is a PR number or `base/head` shas plus a known-issues file; output is JSON plus
  one markdown table. Full comparison = 6 cases x 2 panels x 3 repeats = 36 runs; B3 and B6
  alone give a quick loop.

### 2.7 Acceptance bar for "at least as good"

Over 3 repeats per case, the new panel passes when:
1. Hard recall >= current panel's, and it finds every hard issue the current panel finds in
   at least 2 of 3 runs.
2. Soft recall and major+ recall are not lower.
3. Merged findings per case <= 1.25x current.
4. Spot-check `wrong` rate <= current + 10 percentage points on labelled items.
5. Median tokens and wall time within 1.5x of current, or a written justification.
6. No lens has unique-lens share 0 across all cases unless it self-gates (security).

Sanity check on the benchmark itself: the current panel should catch B6's DATA-first issue
(it did, three times), probably miss B4's hard issue, and be unreliable on B1.1. If it
scores 100% everywhere the set is too easy; at 0% the matcher is too strict.

### 2.8 Limits

* Six cases are a smoke test. Add one whenever a post-merge bug appears. Seed query used:
  `project=CASSANDRA AND issuetype=Bug AND resolution=Fixed AND (description ~ "introduced by" OR description ~ "introduced in") AND created >= 2026-01-01`.
* Hard ground truth is only bugs someone noticed; a real unreported bug looks like a false
  positive until labelled, hence the spot check.
* Not verified: the ninja follow-up `591ad81119b4` (title: wrap iterated partition in
  try-with-resources), the 5.0/trunk variants of the fix PRs, and the body of CASSANDRA-21684.

### 2.9 Sources

* JIRA: https://issues.apache.org/jira/browse/CASSANDRA-{21649,19987,20829,21113,21546,21559,21577,21671,21686}
  (REST `/jira/rest/api/2/issue/KEY`)
* GitHub apache/cassandra PRs #4178, #4300, #4313, #4887, #4990, #5012, #5027, #5165, #5168,
  #5201, #5202, #5210 (`gh api repos/apache/cassandra/pulls/N`, `/files`, `/comments`)
* Commits `6f5fe8c06d58`, `eb9586dc6844`, `22bbac9d6ab7`, `bd22f9d3eea8`, `591ad81119b4`
* Lens outputs: `.work/pr/5201/d1095cbdca4173277488e6e93abeb06a35ea0bb8/lenses/*.json`
