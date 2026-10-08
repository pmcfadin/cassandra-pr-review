## Why

The owner reviewed the Status section of the #5201 report. The headline reads well, but the To do panel
underneath is hard work for a human reader:

- "7 must-fix items" counts 5 contributor fixes plus 2 routine merge steps (run CI, collect +1 votes).
- The same request shows up twice: the Tests check's generic "add a test that fails without this change"
  and the code review's specific "add a single-node unit test to LogTransactionTest.java".
- Code review items are cut to their first sentence and lose their meaning ("Add a comment explaining why
  ties are safe": which ties, where?).
- Nothing says whether an item is a project rule (a check) or an AI code review judgment.
- "Ask for review on the JIRA ticket or the dev@ list" sits in the Reviewers row, but the contributor does it.
- All roles look like they act now, though CI and votes come after the contributor's fixes.
- The verdict has three names ("Not ready to merge", "Needs contributor work", and "Overall: …" at the bottom),
  and a third sentence restates the headline.

## What Changes

- The verdict sentence says who does what next, in order, and counts only real fixes, e.g.
  "The contributor has 4 fixes to make. Then a committer runs CI and two committers vote."
- The To do panel splits into **Now** (the role that must act first) and **Then** (the later merge steps,
  shown as neutral steps, not red must-fix items).
- A code review finding that asks for the same thing as a failing check absorbs that check's to-do item;
  the specific wording wins and the item notes the check it satisfies.
- Each to-do item has a title that makes sense on its own, its file and line when it has one, and a small
  source tag ("Check" or "Code review") that links to the check or finding card.
- Lenses may return a short `title` per finding; merge keeps it. Older reviews without one fall back to a
  title built from the rule and location.
- "Ask for review" moves to the contributor. The Reviewers row shows the top 3 suggested names and the
  votes so far.
- One verdict name everywhere: the "Overall: …" line and the restating sentence go; the index page uses the
  same headline words as the report.

## Impact

- `cpr/model.py` (`_derive_todo`, `_derive_verdict`, steps), `cpr/assets/report.html`, the site index
  template's status words, lens agent output schema (optional `title`), `cpr/merge.py` (carry `title`),
  unit and browser tests.
- No change to check logic, verdict logic, or what blocks a merge.
