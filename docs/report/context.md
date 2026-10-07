# Context

## What is checked

Nothing here passes or fails. This section gives a reviewer the history behind the code the patch changes and the people who know it best:

- **Tickets that last changed this code.** `git blame`, run against the PR's merge base, finds the commit that last changed each line the patch modifies or deletes. For a hunk that only adds lines, it blames the 3 base lines on each side of the insertion point. Each commit's ticket comes from its `patch by … for CASSANDRA-N` line, or else the first ticket key in the message. Tickets are ordered by how many of the blamed lines they own, and their summary and status come from one batched JIRA query.
- **Commits without a ticket.** Blamed commits whose message names no ticket.
- **Issues linked to this ticket.** The JIRA issue links on the PR's own ticket (for example "is caused by", "relates to").
- **Most experienced with each file.** The top 3 people per changed file, from that file's history over the last 5 years.
- **Suggested reviewers.** Up to 5 committers with the highest combined score across the changed files.

## Why

Reviewers read the history of the code a patch touches to understand why it is written the way it is. A patch that changes code written for an earlier ticket should be checked against that ticket's reasoning. Finding that history by hand means running `git blame` and `git log` file by file.

Reviews go faster with people who know the code. The [Cassandra Project Governance](https://cwiki.apache.org/confluence/display/CASSANDRA/Cassandra+Project+Governance) page requires two committer +1s, and the [how to review](https://cassandra.apache.org/_/development/how_to_review.html) page asks reviewers to judge correctness in context. Both favour reviewers who have worked on the same files.

Authorship comes from commit messages, not from the git author. Committers merge other people's patches, so the git author is often the committer. The project's commit format records the real contributors: `patch by <authors>; reviewed by <reviewers> for CASSANDRA-N` ([how to commit](https://cassandra.apache.org/_/development/how_to_commit.html)).

## How each status is decided

This section has no checks. Its navigation badge is info when the context was computed and unknown when it was not, for example on a report built from data gathered before this feature existed.

**Credit lines.** A message is parsed for `patch by <names>` followed by `;` or `,` and `reviewed by <names>`. Matching is case-insensitive, tolerates lines wrapped mid-credit, and accepts the verb typos found in history (`review by`, `reviwed by`, `reivewed by`). Names are split on `,`, `and`, `&`, and `+`; `TBD` is ignored. A commit without a credit line counts its git author as the patch author.

**Names.** Each name is matched, ignoring case and accents, to an ASF committer by, in order: the git author's `@apache.org` email, the aliases file `cpr/data/people-aliases.json`, an ASF id written as a name (`Patch by marcuse`), or the committer's display name on the ASF roster. Names that do not match stay as written and are marked "not matched to a committer".

**Scores.** Each authored patch counts 1.0 and each review 0.6, halved for every 2 years of age. Commits older than 5 years are ignored. The constants are in `cpr/config/context.json`.

**Suggestions.** Only matched committers are suggested. The PR author is excluded. Anyone already in the ticket's Reviewers field, or who has commented on the ticket, is listed as "already involved" instead.

**Budgets.** At most 300 hunks are blamed and 25 files' histories are read, production code first and largest first. The section says what was skipped.

## How to fix

Nothing to fix. To ask someone for a review, mention them on the JIRA ticket or the dev@ list.

If one person shows up twice under different names, add both spellings to `cpr/data/people-aliases.json` with their ASF id.

## Limits

- Blame finds the last change to a line. A mass reformat or a file move can hide older, more meaningful history.
- People who reviewed only on the mailing list or JIRA, with no credit line, are not counted.
- Old, stable code can have few recent commits. The experts list for it may be empty, though people who know it well still exist.
- Suggestions favour volume of recent work, not depth of knowledge. Treat them as a starting point.
