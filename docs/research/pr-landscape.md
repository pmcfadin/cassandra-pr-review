# Apache Cassandra PR landscape (research, 2026-10-07)

Survey of real pull requests on `github.com/apache/cassandra`, their linked JIRA
tickets, and the CI evidence a reviewer tool can reach. All calls were read-only
(`gh`, anonymous JIRA REST, anonymous Jenkins/Butler/CircleCI APIs).

Sample: the 30 newest open PRs and 25 newest closed PRs looked at in detail;
aggregate stats over all 545 open PRs and the last 200 closed PRs.

---

## 1. GitHub PRs

### 1.1 Volume and age

- 545 open PRs. 23 are drafts. 303 (56%) were opened more than a year ago;
  49 carry the `stale` label. 229 were opened in 2026 alone.
- Every one of the newest 200 open PRs comes from a fork (`isCrossRepository=true`).
  Committers also work from personal forks (e.g. `maedhroz`, `frankgh`, `bbotella`).

### 1.2 Target base branches (all 545 open)

| base | count | | base | count |
|---|---|---|---|---|
| trunk | 380 | | cassandra-4.0 | 23 |
| cassandra-5.0 | 47 | | cep-45-mutation-tracking | 21 |
| cassandra-4.1 | 41 | | cassandra-6.0 | 16 |
| cassandra-3.11 | 11 | | cassandra-3.0 / 2.2 | 5 / 1 |

Feature branches exist (`cep-45-mutation-tracking`), and PRs against 3.0/3.11/2.2
target branches that are effectively end-of-life.

### 1.3 Size

Over the newest 200 open PRs (additions + deletions):
p50 = 231 lines, p90 = 2,701, p99 = 19,605, max = 37,766. Files changed:
p50 = 5, p90 = 46, max = 390. 14 PRs exceed 5k lines, 9 touch 100+ files.

Examples:
- #4967 "Executor QoS" (trunk): +31,504/-6,262, 173 files.
- #4790 "Accord/C* timestamp integration" (trunk): +14,004/-5,601, 390 files.
- #5201 CASSANDRA-21649 (4.0): 1 file, 8 lines. A typical backport.
- #5235/#5230 CASSANDRA-18216 SAI sharding: 27 files, +2,186.

### 1.4 JIRA key presence (all 545 open)

| where | PRs with a `CASSANDRA-NNNNN` key |
|---|---|
| title | 362 (66%) |
| head branch name | 349 (64%) |
| body | 249 (46%) |
| none of the three | 88 (16%) |

Formats vary: `CASSANDRA-21724: Fix ...`, `[CASSANDRA-21723]CEP-45: ...`,
`CASSANDRA-21571 - Guardrail ...`, bare numbers (`21463 cursor compaction ...`,
merged #5058), and keys only in the branch (`CASSANDRA-21710-trunk` with title
"Preserve the original exception ..." on #5199). Branch-only keys appear in some
committer branches too (#5217 `CASSANDRA-21721-trunk`, #5204 `CASSANDRA-21712-trunk`).
Mismatches happen: #5208's branch says `CASSANDRA-19786`, its title says `CASSANDRA-21715`.

PRs with no key, e.g. #5212 "Restore interrupted status in 9 InterruptedException
catch blocks" (Claude-generated, no ticket) and #5220 "LLM Usage Policy". The
`missing-ticket` label marks 63 of them.

### 1.5 PR description

The template (`.github/pull_request_template.md`) holds tips only, with no
checklist. It asks for a commit message of the form:

```
<one sentence>
<optional detail>
patch by <Authors>; reviewed by <Reviewers> for CASSANDRA-#####
```

90 of 545 open PRs have an empty or near-empty body. Body quality ranges from
none to excellent. #5236 (CASSANDRA-21724) lists tests run, before/after results,
per-branch applicability, "noticed, not changed" notes, an AI disclosure, and
"I don't have CI access. Could a committer run pre-commit CI?". Only 9 of 545
bodies mention AI assistance. An `AI_POLICY.md` is under review in #5220.

### 1.6 Labels

Defined: `missing-ticket`, `needs-committer` ("Patch ready, waiting for a committer
to review and merge"), `stale`, `docs`, `tests`, `test-failure`, `typo`, `javadoc`,
`apidoc`, `python`, `dependencies`, `bot`, `needs merging`, plus project tags
`accord` (CEP-15), `constraints` (CEP-42), `CEP-45`, `CEP-52`, `CEP-54`, `CEP-55`.
Counts on open PRs: needs-committer 98, missing-ticket 63, stale 49, python 31,
accord 27, CEP-45 20, tests 17, docs 14, dependencies 9. Most PRs (about 60%) have
no label. Labels are applied by hand, inconsistently.

### 1.7 Reviews on GitHub

Review activity is uneven. GitHub `reviewDecision` over 200 open PRs:
none = 153, APPROVED = 34, CHANGES_REQUESTED = 13. Many PRs have no GitHub review
at all, and the real review happens on JIRA (#5195 and #5194: zero reviews and zero
comments on GitHub, while CASSANDRA-21694 holds a full review thread with "+1"s).

When review happens on GitHub it is inline and substantive:
- #5211 (Accord IN clause): `belliottsmith` on `StorageProxy.java` objects to
  `ArrayList.removeIf` allocation, then to the method's whole design. The author
  rewrites the code.
- #5225 (docs + `RangeStreamer`): a contributor checks doc claims against code paths.
  A committer (`michaelsembwever`, MEMBER) then approves.
- #5220: wording nits on a policy file.

A "+1" from a committer is the approval signal ("Nice! +1" on #5165). The
non-binding form "+1 (nb)" is used on JIRA. `author_association` (MEMBER vs
CONTRIBUTOR vs NONE) separates committer reviews from the rest.

### 1.8 Multi-branch patches: one PR per branch

A fix for several release lines arrives as one PR per target branch, linked by a
shared JIRA key and usually a `-<branch>` suffix on the head branch:

- CASSANDRA-21649: #5201 (4.0), #5200 (4.1), #5198 (5.0), #5197 (6.0). Note there is
  no trunk PR, and the 4.x patches are 8 lines while the 5.0/6.0 ones are 137.
- CASSANDRA-21615: #5213 (5.0), #5214 (6.0), #5215 (trunk), branches
  `millerjp/CASSANDRA-21615/<branch>`.
- CASSANDRA-21520: #5229/#5228/#5227 (5.0/6.0/trunk), all closed after commit.
- CASSANDRA-21618: #5222 (5.0), #5223 (6.0), #5203 (trunk), with differing branch names
  (`CASSANDRA-21618-mixed-cdc-state` vs `CASSANDRA-21618-6.0`).
- CASSANDRA-21688: #5173/#5174/#5175. #5175's title says "(5.0)", yet its base is
  `trunk`, which is a base-branch mistake.

Across all open PRs, 51 JIRA keys have 2+ open PRs (26 x2, 10 x3, 6 x4, 8 x5, 1 x7).
Sometimes only one branch has a PR and the others are mentioned in the body or JIRA
(#5236: "I can prepare per-branch patches"), or as fork compare links on JIRA
(CASSANDRA-21615 comment). Patches also get superseded ("supersedes #5152" on #5202).

### 1.9 How merges actually land: committers push, PRs close unmerged

Only 4 of the last 200 closed PRs were merged through GitHub (#5196 and #5020 into
the `cep-45-mutation-tracking` feature branch, plus #5058 and #4972). Everything else
is committed by a committer pushing to `apache/cassandra`. The committer then closes
the PR by hand, often leaving a comment:

- #5227: "Committed as https://github.com/apache/cassandra/commit/bf293fa..."
- #5199, #5204, #5217: "Closed via https://github.com/apache/cassandra/commit/..."
- #5226, #5177: closed with no comment at all.

Release branches merge forward: a commit lands on the oldest branch and is merged up
(`Merge branch 'cassandra-5.0' into cassandra-6.0`, then `'cassandra-6.0' into trunk`).
Commit messages follow the template: `patch by Pranav Shenoy; reviewed by Caleb
Rackliffe and David Capwell for CASSANDRA-21520`. "ninja:" commits fix fallout
(`ba946abc45 ninja: fix cqlshlib tests after CASSANDRA-21720`).

So "closed, not merged" means nothing. To check whether a PR landed, look at JIRA
resolution plus Source Control Link, or a "Committed as / Closed via" comment.

---

## 2. JIRA (issues.apache.org/jira, project CASSANDRA)

Anonymous `GET /rest/api/2/issue/CASSANDRA-N` works and returns comments and
attachments inline. Tickets checked:

| ticket | PRs | status | Reviewers | Fix Version | CI evidence |
|---|---|---|---|---|---|
| 21724 | #5236 | Open | none | 4.1.x,5.0.x,6.x,7.x | none |
| 21618 | #5203/5222/5223 | Patch Available | none | 7.0 | none |
| 21595 | #5225/5224/5047 | Changes Suggested | Erick Ramirez | 5.0.x,6.0.x,7.0 | none, "+1" from mck |
| 21615 | #5213/5214/5215 | Review In Progress | Johnny Miller, Michael Semb Wever | 5.0.x,6.0.x,7.x | none |
| 21571 | #5195 | Needs Committer | none | 7.x | none (benchmark script attached) |
| 21694 | #5194 + others | Needs Committer | Caleb Rackliffe, Marcus Eriksson | 4.0.x through 7.x | `ci_summary.html` per branch |
| 21520 | #5227-5229 | Resolved/Fixed | Caleb Rackliffe, David Capwell | 5.0.10,6.0-alpha3,7.x | `ci_summary.html` x3 |
| 21671 | #5152/5168/5202/5210 | Resolved/Fixed | Rackliffe, Guerrero, Lightfoot | 5.0.10,6.0-alpha3,7.x | `ci_summary.html` x3 |

### 2.1 Fields that matter

- `status`. The workflow is: Open, Triage Needed, In Progress, Patch Available,
  Review In Progress, Changes Suggested, Awaiting Feedback, Needs Committer,
  Requires Testing, Testing, Ready to Commit, Resolved. "Needs Committer" mirrors the
  GitHub `needs-committer` label.
- `resolution` (Fixed, etc.) and `fixVersions` (`5.0.x` means unreleased line,
  `5.0.10` means the release it shipped in). Fix versions show which branches need a PR.
- `customfield_12313420` **Reviewers** (users). Two committer +1s are the norm.
  Contributors (non-committers) can be listed too.
- `customfield_12313920` **Authors**.
- `customfield_12313924` **Source Control Link**: the commit URL, set on resolution.
- `customfield_12313823` Test and Documentation Plan; `customfield_12313820` Severity;
  `customfield_12313825` Bug Category; `customfield_12313822` Discovered By;
  `customfield_12313821` Complexity; `customfield_12311420` Since Version.
- `components` (e.g. `Feature/SAI`, `Consistency/Streaming`, `Local/Compaction/UCS`).
- `issuelinks` (Duplicate, Reference, and so on).
- `GET .../remotelink` lists linked GitHub PRs ("GitHub Pull Request #5227") as
  auto-created by the ASF bot when a PR names the key.
- Custom field ids come from `GET /rest/api/2/field` (173 custom fields). Map them by
  name at runtime instead of hard-coding.

### 2.2 Where CI results live: JIRA attachments, not links

Committers post pre-commit CI results as **attachments** on the ticket: `ci_summary.html`
(small, around 20-200 KB) and `result_details.tar.gz` (3-60 MB), one pair per branch
(`ci_summary-1.html`, or `4.0-ci_summary.html` when the poster names them per branch).
Comments then summarize: "CI for 5.0 is 100% green. 6.0 and trunk don't have any
regressions. Moving this to commit..." (21520).
"Need clean CI now, and another reviewer?" (21694).

`ci_summary.html` downloads anonymously and parses into plain text:

```
CI results for CASSANDRA-21520-5.0: FAIL  sha: 1c9f391e...  Build JDK: 11
JUnit results summary - Passed: 28804 - Failed: 0 - Total: 30478
jdk build: pass | packaging build: fail (NO DATA FOUND) | Checkstyle: PASS
suites: cqlshlib, jvm11-dtests, jvm17-utests, python-dtests, python-upgrade-dtests, ...
```

It includes the **sha** that was tested, so we can compare it with the PR head sha
to detect stale CI. These files come from `.build/run-ci` (Jenkins on Kubernetes,
run by committers or contributors with their own cluster). No CircleCI or Butler
links appeared in the sampled comments. Older tickets (pre-2024) do link CircleCI
workflows and `ci-cassandra.apache.org` devbranch builds, so expect both forms.

---

## 3. CI evidence reachable programmatically

| source | what it gives | auth | notes |
|---|---|---|---|
| GitHub checks on the PR (`gh pr checks`) | nothing | gh token | apache/cassandra runs Actions only on `push` to its own branches. PR checks list is empty for every PR sampled. |
| GitHub check-runs on the **fork** head commit (`GET repos/{fork}/commits/{sha}/check-runs`) | `ant-check-jdk11`, `ant-check-jdk17` (checkstyle/rat/build via `.build/docker/check-code.sh`) | gh token | Present when the fork has Actions enabled (e.g. #5234, #5221, #5195, #5194, #5225). Missing for #5236, #5216, #5212, #5209. Lint/compile only, no tests. |
| Fork commit statuses (`GET repos/{fork}/commits/{sha}/status`) | CircleCI `ci/circleci: java11_separate_tests/start_*` contexts | gh token | #5203, #5206. Typically all `pending` with "Your job is on hold": approval-gated jobs nobody started. Paginate, since there are 30+ contexts. |
| CircleCI API v2 (`/api/v2/project/gh/{owner}/cassandra/pipeline?branch=`, `/workflow/{id}/job`) | pipelines, workflows (`java17_pre-commit_tests`), job status (`on_hold`, `approval`) | none for public projects | Works anonymously for `gh/yifan-c/cassandra`. Contributor-account dependent. |
| JIRA attachments `ci_summary.html` / `result_details.tar.gz` | full pre-commit run summary with sha, per suite | none | **Best signal.** Present only once a committer or contributor ran `.build/run-ci`. |
| ci-cassandra.apache.org Jenkins JSON API | post-commit runs for `Cassandra-trunk`, `-6.0`, `-5.0`, ...; `testReport/api/json` (trunk #2627: 26 fail / 322,942 pass) | none to read; ASF LDAP to trigger | `Cassandra-devbranch-5` (parameterized repo/branch) last ran 2026-05-22, so it is rarely used now. Use `tree=` filters, since responses are large. |
| butler.cassandra.apache.org | upstream failure tracking. `/api/upstream/workflows`, `/api/ci/jobs/upstream`, `/api/upstream/trends`, `/api/upstream/compare/{workflow}/{job}` (per-test failures with Jenkins links) | none to read | Undocumented and slow. `/api/upstream/failures/{workflow}` hit a 504 at 60 s. Useful as the "known flaky on trunk" baseline for triaging a PR's CI failures. |

Rate limits: GitHub REST and GraphQL each allow 5,000 per hour with a token. The
GraphQL search behind `gh pr list --json additions,...` returned 502s for limits
over 200, so page in chunks of 100 or less. JIRA anonymous REST had no rate-limit
headers, but ASF throttles abusive clients, so cache responses and keep under about
1 req/s. Jenkins and Butler are shared ASF infrastructure, so use light, cached reads.
Attachments of 60 MB (`4.0-result_details.tar.gz` on 21694) should be fetched only
on demand.

---

## 4. Related repositories

| repo | open PRs | merged via GitHub (last 40 closed) | JIRA key in title (last 30) | consider later? |
|---|---|---|---|---|
| cassandra-dtest | 52 | 10/40 | 18/30 | Yes, soon. Python dtests usually pair with a core PR on the same CASSANDRA ticket. |
| cassandra-website | 20 | 31/40 | 3/30 | Low. Docs and site, mostly merged on GitHub with no JIRA. Different review criteria. |
| cassandra-java-driver | 45 | 30/40 | 11/30 | Later. Separate project (CASSJAVA), its own CI on Jenkins multibranch. |
| cassandra-analytics | 26 | 32/40 | 27/30 | Later. GitHub-merged with real GitHub Actions checks (compile, integration matrix). Easier CI story. |
| cassandra-sidecar | 28 | 33/40 | 28/30 | Later. GitHub-merged, rich GitHub Actions checks (checkstyle, integration per C* version). |

The satellite repos merge through GitHub and expose checks on the PR. The core repo
does neither. A design that supports core will cover the others with less work.

---

## 5. Design implications

### What the reviewer can rely on

- **The diff and PR metadata from GitHub**: title, body, base and head refs, head sha,
  files, commits, inline review comments with `author_association`, labels, draft flag.
- **A JIRA key in 84% of PRs** (title, branch, or body), plus anonymous JIRA REST for
  status, Reviewers, Authors, Fix Versions, components, comments, attachments, and
  remote links to sibling PRs.
- **The commit message convention** (`patch by X; reviewed by Y for CASSANDRA-N`),
  which we can check on the PR's commits.
- **Post-commit baselines** from ci-cassandra Jenkins and Butler, to tell "new failure"
  from "already failing on trunk".

### What is usually missing

- **CI evidence on the PR itself.** There are no PR checks. Fork Actions give
  lint/compile at best. CircleCI is usually on hold. Real test evidence exists only
  as JIRA `ci_summary.html` attachments, and only late in review. The report should
  state that CI evidence is missing ("CI not yet run"); it must not read the absence
  as a failure.
- **GitHub reviews**: 77% of open PRs have no review decision. Review state lives in
  JIRA status, the Reviewers field, and "+1" comments. The report needs both sources.
- **Committer sign-off**: two committer +1s are needed, but there is no structured
  field for "+1". Parse comments, using the Reviewers field as a hint.
- **Tests and CHANGES.txt** are often absent or deferred ("A CHANGES.txt entry will
  follow after review"). Flag them, but do not block on them.
- **Body content**: 17% of PRs have an empty body. Fall back to the JIRA description.

### Readiness signals to compute

1. JIRA key found, ticket exists, and title and branch keys agree (catch #5208-style
   mismatches).
2. JIRA status (Needs Committer / Ready to Commit = late; Open / Patch Available = early).
3. Reviewers populated, plus count of committer +1s (GitHub APPROVED by MEMBER, and
   "+1" in JIRA comments).
4. Branch coverage: Fix Versions against sibling PRs found via remotelink or same-key
   search. Report missing branches and base-branch mistakes (#5175).
5. CI: the newest `ci_summary.html` per branch, whether its sha matches the PR head,
   its pass/fail counts, and failures compared against the Butler/Jenkins baseline.
6. Mergeability and conflicts against the base branch, and the PR's age and staleness.
7. Code review proper: tests added, `test/` vs `src/` ratio, config/yaml/protocol/
   sstable-format changes that need upgrade tests, and NEWS.txt for user-visible changes.

### Edge cases

- **Drafts** (23 open, e.g. #5238 "CEP-36 draft"): give an early-feedback report,
  with no merge verdict.
- **Huge PRs** (p99 around 20k lines; #4967 at 37k lines, #4790 at 390 files): need
  chunked or summarized review and a token budget. Prioritize `src/` over generated
  or test-resource files and say what was skipped.
- **Multi-branch**: review a JIRA key as a set of PRs. Diff the backports against the
  trunk patch, expecting small divergences (#5201 is 8 lines vs 137 on 6.0 for
  CASSANDRA-21649). One report per key, with a section per branch, is probably the
  right unit.
- **No JIRA** (16%, e.g. #5212, #5220): the verdict is "not mergeable until a ticket
  exists", while the code is still reviewed.
- **Feature branches** (`cep-45-mutation-tracking`): these really are merged through
  GitHub, often with no ticket (#5196, labelled `missing-ticket,CEP-45`). Relax the
  JIRA rules there.
- **EOL bases** (3.0, 3.11, 2.2) and stale PRs (56% are over a year old): flag that
  the target branch is unlikely to accept the change, and flag that the PR needs a rebase.
- **Superseded or already-committed PRs**: open PRs whose JIRA is Resolved/Fixed, or
  whose key appears in base-branch history, should be reported as "already landed /
  superseded".
- **Closed-unmerged ≠ rejected**: never infer the outcome from GitHub merge state.
- **AI-generated PRs** (#5212, #5236, #5237 on branch `claude/...`): check for the
  disclosure the proposed AI policy asks for (#5220).
