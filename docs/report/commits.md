# Commits and changelog

## What is checked

The PR's commit messages, their trailers (`Co-authored-by:`, `Assisted-by:`, and similar), signs of undisclosed AI assistance, and whether `CHANGES.txt` has an entry when production code changed, and, for performance PRs, whether the benchmark commit comes before the change.

## Why

The commit message format is:

```
<One sentence description, usually the Jira title or CHANGES.txt summary, no Jira id>

<Optional longer description>

patch by <Authors>; reviewed by <Reviewers> for CASSANDRA-#####

Co-authored-by: Name <email>
Assisted-by: AGENT_NAME:MODEL_VERSION
```

Sources: [.github/pull_request_template.md](https://github.com/apache/cassandra/blob/trunk/.github/pull_request_template.md); [How to commit](https://cassandra.apache.org/_/development/how_to_commit.html), "Commit Message"; [AGENTS.md](https://github.com/apache/cassandra/blob/trunk/AGENTS.md), "Git Workflow", which adds "no jira id" on the first line and the `Assisted-by` trailer.

- Use `TBD` for reviewers until review finishes. Squash to one commit per branch once the patch has its +1; several commits are fine during review. Source: [Contributing code changes](https://cassandra.apache.org/_/development/patches.html) steps 6 and 8.
- The ASF requires contributors using generative tools to check the tool's terms and the output's provenance, and recommends a `Generated-by:` token. Source: [ASF Generative Tooling Guidance](https://www.apache.org/legal/generative-tooling.html). Cassandra's form is `Assisted-by: AGENT_NAME:MODEL_VERSION`. Source: [AGENTS.md](https://github.com/apache/cassandra/blob/trunk/AGENTS.md).
- Add a `CHANGES.txt` entry at the top of the version section for the branch, as ` * <summary> (CASSANDRA-NNNNN)`. Only user-impacting changes need one; test-only fixes do not. Source: [Contributing code changes](https://cassandra.apache.org/_/development/patches.html) step 7. Committers often add or fix the entry at commit time.

- A performance change should be measurable on both sides: put the JMH benchmark (under `test/microbench/`) in an earlier commit than the change, so it can run at the parent commit and at the PR head. This is the project owner's convention; most PRs do not follow it yet (a single commit with code and benchmark together is the common case), so only the wrong order asks for action. Source: the static-analysis change design in this repository.

## How each status is decided

### `commits.message-format`

Advisory and informational: a warn here never changes the recommendation. Owner: contributor.

Every commit in the PR is checked. A commit has a problem when its first line contains the PR's ticket key, when it has no line matching `patch by …; reviewed by … for CASSANDRA-N` (case-insensitive, semicolon required), or when that line names a different ticket than the PR.

- **unknown**: the PR has no commits.
- **warn**: at least one commit has a problem. Each commit is listed with its problems.
- **pass**: every commit follows the format.

### `commit.perf-structure`

Advisory. Owner: contributor. Only the wrong order moves the recommendation.

A PR counts as a performance PR when a strong signal fires, or two medium ones do. Strong: a changed file under `test/microbench/`; a JIRA label `performance`; a JIRA component `Test/benchmark`. Medium: the PR title or JIRA summary has a performance keyword (perf, performance, faster, speed up, latency, throughput, allocation, optimize, and similar); the PR description mentions JMH or a benchmark. The evidence names every signal that fired. Commit order comes from the PR's commits, oldest first, ignoring `fixup!` and `squash!` commits; the first commit touching `test/microbench/` is compared with the first touching `src/java/`.

- **not-applicable**: not a performance PR (one medium signal is not enough), or a performance PR with no `src/java` change.
- **unknown**: the commit list is unavailable (static analysis did not run).
- **warn** (needs action): the benchmark commit comes after the change.
- **warn** (note): benchmark and change share a commit, or the PR changes `src/java` with no benchmark.
- **pass**: the benchmark commit comes first.

### `commits.provenance`

Advisory. Owner: contributor.

Signs of AI assistance are a head branch starting with `claude/`, `copilot/`, `codex/`, or `cursor/`, or a PR description that mentions `claude`, `copilot`, `chatgpt`, `gpt-N`, `codex`, `cursor`, `gemini`, `llm`, `AI-generated`, or `AI-assisted`.

- **warn**: at least one sign is present and no commit has an `Assisted-by:` or `Generated-by:` trailer. Moves the recommendation to "needs work".
- **pass**: otherwise. All trailers found are listed. No trailer is required when there are no signs.

### `changelog.entry`

Advisory. Owner: contributor.

- **not-applicable**: no production code changed (nothing under `src/java/` or `pylib/` outside test directories).
- **warn**: production code changed but `CHANGES.txt` has no added lines; or added lines exist but none matches ` * <summary> (CASSANDRA-N)` (one or more comma-separated keys in the parentheses); or a matching line exists but does not mention the PR's ticket. Moves the recommendation to "needs work".
- **pass**: a well-formed added line names the PR's ticket.

## How to fix

For a performance PR, reorder with an interactive rebase so the benchmark commit comes first, or split a combined commit in two.

Reword the final commit (`git commit --amend`, or squash with `git rebase` before the last push):

```
Fix NPE when reading an empty partition with a static column

patch by Jane Doe; reviewed by TBD for CASSANDRA-12345
```

- Keep the ticket key out of the first line; it belongs in the `patch by` line.
- If an AI tool helped write the patch, add a trailer per tool, for example `Assisted-by: Claude Code:claude-opus-5`, and say so in the PR description.
- Add co-authors with `Co-authored-by: Name <email>`.

For `CHANGES.txt`, add a line at the top of the section for your branch's version:

```
 * Fix NPE when reading an empty partition with a static column (CASSANDRA-12345)
```

If you agreed with a reviewer that the committer will add the entry, say so on the PR.

## Limits

- `commit.perf-structure` judges the PR branch's commits, not what lands: committers squash at merge. It does not judge whether a benchmark is meaningful. A benchmark touched again in a later commit does not change the order. The JIRA `performance` label is rarely used, so detection leans on paths and keywords, and keyword matches can misfire.

- Committers usually rewrite the commit message when they commit, so `commits.message-format` is informational.
- The `patch by` pattern needs a semicolon before `reviewed by`. Lenient variants seen in history (`, reviewed by`) are flagged.
- Every commit is checked, including review fix-ups that will be squashed away.
- AI detection reads only the branch name and the PR description, not commit messages. Common Cassandra words such as "cursor" (cursor-based compaction) trigger it, so the warning can be a false positive. A `Co-authored-by:` trailer naming an AI tool does not satisfy it.
- `changelog.entry` does not check that the line is at the top of the right version section, and it asks for an entry for every production change, including refactors that are not user-impacting.
- NEWS.txt is not checked. Update it yourself when a change affects defaults, upgrade steps, deprecations, or user-visible features.
