# Quick loop: new panel vs spec-flow panel

Run 2026-10-07. Cases B3 (CASSANDRA-21113, landed 4.0 commit of PR #4887; the hard `$$` issue
from CASSANDRA-21559) and B6 (PR #5201, CASSANDRA-21649). One run per panel per case, all lenses
on Sonnet, cut-off contexts from `cpr bench run`, trunk checklists @ `617fd3b935a0`. Both cases
are tier `small`. Raw lens outputs and `merged.json` are in `bench/runs/<panel>/<case>/1/`.

Reproduce the table: `bin/cpr bench score --panel cpr/config/panel.json --against cpr/config/panel-spec-flow.json --case B3,B6`

| metric | new (6 Cassandra lenses) | old (standards + 4 spec-flow) |
|---|---|---|
| hard recall | 100% (1/1) | 100% (1/1) |
| soft recall | 100% (3/3) | 67% (2/3) |
| major+ recall | 100% (4/4) | 75% (3/4) |
| raw findings | 23 | 15 |
| merged issues | 9 | 8 |
| duplicate rate | 61% | 47% |
| invalid lens outputs | 0 | 1 (old observability on B3 omitted `rule`) |
| tokens (sum of lenses) | 733k | 282k |
| wall time (slowest lens) | 74 s / 96 s | 86 s / 28 s |

Known issues by case:

| case | issue | new | old |
|---|---|---|---|
| B3 | K1 (hard): `$$`-quoted password with `'` reaches the audit log | found by 5 of 6 lenses | found (correctness, security; test-rigor at the test file) |
| B6 | K1: swallowed delete failures (`deleteWithConfirm` dropped) | found by all 6 lenses | found |
| B6 | K2: `SSTableTidier` still deletes DATA first, so the fix is incomplete | found (persistence-compat, completeness-symmetry) | **missed** |
| B6 | K3: no LogTransactionTest regression test | found | found |

## Verdict

The gate in the spec ("the new panel misses a known issue the old one found") is not triggered:
the new panel found everything the old one did, plus B6 K2, the most important issue on #5201
(the old panel found K2 in the original 5201 run but not in this one; one run each proves little).
The swap ships.

## Findings about the new panel, and what changed

1. **Severity inflation from the table.** Two issues were raised to `blocker` by findings whose
   impact was overstated: cass-test-regime gave a *missing test* the impact `crash` (the impact of
   the bug it would catch), and cass-persistence-compat called leaked files `data-loss`. Fixed after
   the run: every `cass-*` prompt now defines each impact, and cass-test-regime leaves impact out
   for missing or weak tests and sets severity directly (major for a bug fix with no failing-first
   regression test). The standards lens already did this for non-behaviour findings. Not yet
   re-measured; the 6.1 re-run of #5201 exercises it.
2. **Cost.** New-panel tokens are 2.6x the old panel's. Most of it is the fallback: the `cass-*`
   agents were created during this session, so they ran as `general-purpose` agents carrying the full
   tool set (55-75k tokens each) instead of named project agents with four tools (the named
   standards lens used 13-15k). Re-measure in a fresh session, where the agents load by name, before
   applying the 1.5x cost bar.
3. **Unique-lens share.** On these two small patches concurrency-lifecycle, logic-boundary and
   persistence-compat found nothing another lens did not also find (persistence-compat did find K2,
   shared with completeness-symmetry). Two small cases cannot judge this; the full benchmark (all
   six cases, three runs) applies acceptance rule 6.
4. **Merge.** 23 findings became 9 issues. One merge joins two different problems that share a
   location and vocabulary (B3: "no fallback when the match fails" with "earlier occurrence not
   obfuscated", lines 74). Acceptable for now; watch it in the full benchmark.

## Not covered

Three repeats per case, cases B1, B2, B4, B5 (B5 has no reachable head sha), the spot-check labels
for the 6 unmatched issues (listed by `cpr bench score`), and medium/large tiers (both cases were
small).

## Follow-up: #5201 re-run with named agents (task 6.1)

Same session, after the prompt fixes, with the six lenses loaded as named project agents (model
inherited from the session). Tokens per lens: standards 24k, logic-boundary 30k,
concurrency-lifecycle 23k, persistence-compat 31k, completeness-symmetry 33k, test-regime 23k:
**163k total**, against 135-147k for the old panel per case above (1.2x, inside the 1.5x bar). So
the 2.6x in the quick loop was the general-purpose fallback.

Result: 12 findings from 6 lenses → 5 issues, 3 must-fix, **no blockers** (the quick loop's two
inflated blockers are gone: test-regime now leaves impact off missing-test findings, and no lens
called leaked files data loss). Issues: swallowed delete failures (5 lenses), tidier still deletes
DATA first (4 lenses; known issue K2), no regression test (test-regime), untested ties and missing
files (minor), needless HashMap (nit).
