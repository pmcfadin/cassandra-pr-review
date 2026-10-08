## D1. Fix vs step

A to-do item is a **fix** when its owner is the contributor and it comes from a failing or unknown check or
a must-fix code review finding. Committer CI runs, committer +1 votes and reviewer asks are **steps**.
The verdict count and the red marks cover fixes only. Steps are listed under "Then" with a neutral marker.
If there are no contributor fixes, the first role with work is "Now" and nothing is "Then" except later steps.

## D2. Dedupe

Pair a failing check's to-do with a code review finding when both target the same need. The only pairing
rule for now: the `testing.*` checks (and `build.*` test checks) pair with a finding whose rule or problem is
about adding or fixing a test (keyword match on test/regression test/unit test/dtest). The finding's item
stays, gains "Also satisfies: <check title>", and the check's item is dropped from To do (the check itself is
unchanged in Checks). Keep the rule small and table-driven so more pairs can be added later.

## D3. Titles

Lens output gains optional `title` (<= 80 chars, imperative, standalone). `cpr/merge.py` keeps the title of
the representative finding. View falls back to: rule (humanized) + " — " + short location (file name:line).
Never cut a problem sentence mid-thought; a title is either the lens title or the fallback.

## D4. Verdict sentence

Built from the Now/Then split: "<Role> has N fixes to make." followed by "Then " + steps joined in order
(CI, votes). Drop the restating note for the blocked verdict. Remove "Overall: …". The index uses
`view.verdict.headline` for its status pill so both pages use the same words.

## D5. Reviewers row

Contributor gets "Ask for review on the JIRA ticket or dev@ list" as a step. Reviewers row shows at most
3 suggested names (+N more) and "+1 votes: X of 2".
