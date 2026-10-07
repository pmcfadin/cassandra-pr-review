## Why

Reviewing an apache/cassandra PR means hunting across GitHub, JIRA and CI attachments just to learn
whether the patch meets the basic merge requirements, before anyone reads a line of code. 545 PRs
are open, 56% are older than a year, and 77% have no GitHub review decision
(docs/research/pr-landscape.md §1). Reviewers need one page that shows, up front, whether a patch
is ready, what is missing, and how hard it will be to review.

This change builds that page, run locally against one PR. Automation (polling, publishing,
PR comments), AI review lenses and deeper tests come in later changes and plug into the report this
change defines.

## What Changes

- A local command, `cpr review <PR number>`, that reviews one apache/cassandra PR and writes one
  self-contained HTML file.
- Read-only ingest of the PR (metadata, commits, files, diff), its sibling PRs for the same JIRA
  key, the JIRA ticket (fields, comments, attachments, remote links) and the CI summaries attached
  to the ticket. Raw inputs are cached on disk so a report can be re-rendered offline.
- A merge-requirements gate: the deterministic checks from the project's standards (JIRA ticket,
  CI evidence per branch and its freshness, commit message format, CHANGES.txt, tests added, branch
  coverage, committer +1s, banned APIs, config-file pairing, licence headers).
- A triage rating (easy / moderate / hard) with the signals behind it, so reviewers can pick the
  easy patches first.
- The HTML report: a left-hand navigation, a first page with the merge recommendation, the
  requirement results and the triage rating, then detail sections. The "Changes" section embeds
  the diff view rendered by the rustyrazorblade `dev-skills:ide-explain` generator.
- A recommendation that never claims more than the evidence supports. Without code review, the
  best possible outcome is "requirements met, code not yet reviewed".

## Non-goals

- Polling apache/cassandra for new PRs, publishing to GitHub Pages, or commenting on PRs (later
  changes; see the owner decisions in project memory).
- AI review lenses (correctness, test rigor, compatibility, etc.) and the "deeper tests" suite.
  This change defines where their findings go in the report, not the lenses themselves.
- Running Cassandra builds or tests (`ant check`, unit tests, dtests).
- Repos other than apache/cassandra (cassandra-dtest comes later).
- Any write to GitHub, JIRA, Jenkins or Butler.

## Research relied on

- docs/research/pr-landscape.md §1.4 (JIRA key locations), §1.8 (one PR per branch), §1.9 (PRs
  close unmerged), §2.2 (CI lives in JIRA attachments), §5 (design implications, edge cases).
- docs/research/cassandra-standards.md §1 (workflow, commit format, CHANGES.txt, votes),
  §2.2 (checkstyle banned APIs), §3.3 (CI systems), §6 checklist items 1–17, 20–22, 26, 33,
  41–44, 51–53, 59, 61.
- docs/research/rustyrazorblade-skills.md §2.2 (finding schema and severities), §3.1 (HTML shell,
  manifest injection, escaping).

## Capabilities

### New Capabilities

- `pr-ingest`: Resolve a PR to its JIRA key, sibling PRs, JIRA ticket and CI attachments; fetch
  everything read-only into a cached, typed evidence bundle.
- `merge-requirements`: Evaluate the evidence against Cassandra's merge requirements; each check
  yields pass / fail / warn / unknown / not-applicable with the evidence behind it.
- `review-triage`: Rate how hard the PR is to review (easy / moderate / hard) from deterministic
  signals, and list those signals.
- `review-report`: Render a single self-contained HTML report with left-hand navigation, a
  recommendation first page, detail sections, and an embedded ide-explain diff view.

### Modified Capabilities

None. There are no existing specs.

## Impact

- New Python package (`cpr/`, standard library only) and its unit tests with recorded fixtures.
- Runtime dependencies: `gh` (authenticated), `git`, network read access to api.github.com and
  issues.apache.org, and the installed `dev-skills` plugin (for the diff view only).
- A local cache directory (`.work/`, gitignored) holding a partial clone of apache/cassandra and
  the raw ingest data.
- Output under `reports/` (gitignored for now; publishing comes later).
