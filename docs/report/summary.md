# Summary and recommendation

## What is checked

The summary page collects the result of every other section: the PR's title, number, author, base branch, and JIRA key and status; one recommendation with the reasons for it and who it is waiting on; the triage rating; and a grid of every requirement check with its status. Blocking failures come first, each with the next action.

The recommendation is computed from the check results. It is not a merge decision. Committers make that.

## Why

The project's merge preconditions are spread over several pages: a ticket ([CONTRIBUTING.md](https://github.com/apache/cassandra/blob/trunk/CONTRIBUTING.md)), CI for every affected branch and two committer +1s ([Cassandra Project Governance](https://cwiki.apache.org/confluence/display/CASSANDRA/Cassandra+Project+Governance)), tests ([AGENTS.md](https://github.com/apache/cassandra/blob/trunk/AGENTS.md)), and the reviewer checklist ([How to review](https://cassandra.apache.org/_/development/how_to_review.html)). The summary puts them in one place and says what is missing and whose move it is.

## How each status is decided

Every check has a status (pass, fail, warn, unknown, not-applicable), is either **blocking** or **advisory**, and names an owner: contributor, reviewer, or committer. A warn either needs action or is informational; each aspect page says which.

The recommendation applies these rules in order. The first rule that matches wins. Who acts decides the result: contributor items come first, because they are the only ones the contributor can move.

| Order | Condition | Recommendation |
|---|---|---|
| 1 | The PR is a GitHub draft. | **Draft**: checks are early feedback only; blocking failures are still listed. |
| 2 | A blocking check owned by the contributor failed, or a code review lens reported a blocker or major finding. | **Needs contributor work** |
| 3 | An advisory warning owned by the contributor needs action. | **Needs work**: contributor fixes requested |
| 4 | A blocking check is unknown (an input such as JIRA or the committer roster could not be read). | **Insufficient evidence** |
| 5 | What remains is owned by reviewers or committers: committer +1s, CI that a committer runs, explaining CI failures. | **Awaiting review**: the contributor's part is done |
| 6 | Every blocking check passes, but the code review panel has not run or did not complete. | **Requirements met, code not yet reviewed** |
| 7 | Every blocking check passes and every lens ran and approved with no blocker or major finding. | **Ready to merge** |

The reasons listed are the checks or findings that triggered the rule, plus anything owned by others that is still open. "Waiting on" is the set of owners of those reasons.

**Ready to merge** needs the full code review panel (`/review-pr`). A report made with `cpr review` alone stops at rule 6.

The summary's navigation badge follows the recommendation: needs contributor work is fail, needs work is warn, insufficient evidence is unknown, awaiting review and draft are info, requirements met and ready are pass.

Other sections take the worst status of their checks, ignoring not-applicable, in the order fail, unknown, warn, pass. A section with no applicable checks shows info.

## How to fix

Work through the reasons from the top. Blocking failures stop everything else, so fix those first; each one links to its section and names the action. For anything owned by a reviewer or committer, your step is usually to ask on the JIRA ticket. Then regenerate the report.

## Limits

- Rule 3 counts every contributor-owned warning that needs action, so one small issue (for example a missing `CHANGES.txt` line) gives "needs work" even when all blocking checks pass.
- A check that crashes reports unknown. When that check is blocking, the result is "insufficient evidence", not a pass.
- The recommendation knows only what the checks can see. Design, scope, backport choices, and dev@ consensus are left to people; the About section lists them.
- Data is a snapshot from the fetch time shown in About.
