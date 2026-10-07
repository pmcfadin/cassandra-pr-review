# Reviews and votes

## What is checked

How many Cassandra committers have given the patch a +1, from GitHub reviews and JIRA comments, against the number the project's governance requires.

## Why

- "Code modifications must have been reviewed by at least one other contributor."
- "Code modifications require two +1 committer votes (can be author + reviewer)." A patch from a non-committer needs two committer +1s; a committer's own patch needs one other committer's +1.
- "Modifications involving only test code require one +1 vote from a non-author committer."
- Code must not be committed while under active discussion, while a committer has asked for time to review, or with an unresolved reasoned committer -1.

Source for all four: [Cassandra Project Governance](https://cwiki.apache.org/confluence/display/CASSANDRA/Cassandra+Project+Governance).

Reviewers usually give their +1 in a JIRA comment, and the ticket's Reviewers field names them. Some approve on GitHub instead. The committer list comes from the ASF: [projects.apache.org](https://projects.apache.org/committee.html?cassandra).

## How each status is decided

### `votes.committer-plus-ones`

**Blocking.** Owner: reviewer.

**What counts as a +1**: a GitHub review in state APPROVED, or a JIRA comment containing `+1` as a separate token (`+1`, `(+1`, `[+1`, but not `+10`).

**Who counts as a committer**, checked in this order and shown next to each vote:

1. An entry in `cpr/data/committer-overrides.json` maps the GitHub or JIRA user to an ASF id on the roster.
2. JIRA: the commenter's JIRA username is an ASF id on the Cassandra committer roster.
3. GitHub: the user has authored commits as `<asf-id>@apache.org` and that id is on the roster.
4. GitHub: the review's author association is MEMBER or OWNER (apache organisation members).

The roster is the `cassandra` group in the ASF's public LDAP data, cached for 24 hours. Each committer counts once, even if they approve on GitHub and comment on JIRA.

**How many are needed**: one if every changed file is a test file, otherwise two. When the PR author is a committer and the change is not test-only, the author counts as one vote.

- **unknown**: the roster could not be loaded and no vote was matched by another rule. Raw +1s are listed. The recommendation becomes "insufficient evidence".
- **fail**: fewer committer +1s than needed. The recommendation becomes "blocked".
- **pass**: enough committer +1s. Non-committer +1s are listed but not counted.

Even with enough votes, the recommendation cannot pass "requirements met, code not yet reviewed" in this version.

## How to fix

- Ask for review on the JIRA ticket: set it to Patch Available ("Submit Patch") and ask in a comment. If nobody responds, ask on the dev@cassandra.apache.org mailing list or in the #cassandra-dev channel on the ASF Slack.
- Address review comments, then ask the reviewer to record their +1 on the ticket.
- If a committer's +1 is not counted, their JIRA username or GitHub account could not be matched to an ASF id. Add a mapping in `cpr/data/committer-overrides.json`.
- Contributors cannot fix this alone. A fail here is normal for a new PR.

## Limits

- `+1` is found by pattern. "+1 to the idea", "+1 (nb)", or a quoted +1 from someone else count as votes if the commenter is a committer. Every counted vote links to its source so a human can check it.
- -1 votes, requests for time to review, and ongoing discussion are not detected.
- GitHub MEMBER and OWNER mean apache organisation member, which includes committers of other ASF projects. They are counted as `github:<login>`, so the same person approving on GitHub and commenting on JIRA can be counted twice when no `@apache.org` commit email links the two.
- A committer whose JIRA username differs from their ASF id is not matched unless an override exists.
- For test-only changes, the rule needs a non-author committer; the check does not exclude a +1 the author left on their own ticket.
- Votes on sibling PRs for other branches are not read; only this PR's GitHub reviews and the shared JIRA ticket.
