# Commits and changelog

## What is checked

The PR's commit messages, their trailers (`Co-authored-by:`, `Assisted-by:`, and similar), signs of undisclosed AI assistance, and whether `CHANGES.txt` has an entry when production code changed.

## Why

Both projects squash-merge on GitHub. The commit that lands on `trunk` has this form:

```
CASSSIDECAR-513: Add server option to disable all SSTable verification in SSTableImporter (#400)

<Optional longer description>

Patch by <Authors>; Reviewed by <Reviewers> for CASSSIDECAR-513
```

The subject is `KEY-N: title (#PR)`; repeating the key there is the convention, unlike Cassandra. Sidecar sometimes writes the key in the credit line as a link, `for [CASSSIDECAR-378](https://issues.apache.org/jira/browse/CASSSIDECAR-378)`. Sources: the trunk history of both repositories; the credit line follows Cassandra's, see [How to commit](https://cassandra.apache.org/_/development/how_to_commit.html), "Commit Message". Sidecar allows only squash merges. Source: [Sidecar .asf.yaml](https://github.com/apache/cassandra-sidecar/blob/trunk/.asf.yaml).

- `CHANGES.txt` lists each change as ` * <summary> (KEY-N)` under the version header it ships in. Sources: [Sidecar CHANGES.txt](https://github.com/apache/cassandra-sidecar/blob/trunk/CHANGES.txt); [Analytics CHANGES.txt](https://github.com/apache/cassandra-analytics/blob/trunk/CHANGES.txt).
- The ASF requires contributors using generative tools to check the tool's terms and the output's provenance, and recommends a `Generated-by:` token. Source: [ASF Generative Tooling Guidance](https://www.apache.org/legal/generative-tooling.html). Cassandra's form is `Assisted-by: AGENT_NAME:MODEL_VERSION`. Source: [AGENTS.md](https://github.com/apache/cassandra/blob/trunk/AGENTS.md).

## How each status is decided

### `commits.message-format`

Advisory and informational: a warn here never changes the recommendation. Owner: contributor.

Every commit in the PR is checked. A commit has a problem when it has no line starting `patch by …; reviewed by … for KEY-N` (case-insensitive; `;` or `,` before `reviewed by`; the key may be inside `[...]`), or when that line names a different ticket than the PR. The key may be any of the project's keys (Sidecar: `CASSSIDECAR` or `CASSANDRASC`; Analytics: `CASSANALYTICS`). A key in the first line is **not** a problem.

- **unknown**: the PR has no commits.
- **warn**: at least one commit has a problem. Each commit is listed with its problems.
- **pass**: every commit has a matching credit line.

### `commit.perf-structure`

**not-applicable** for both projects: "Not part of Cassandra Sidecar's process" (or Cassandra Analytics'). The benchmark-first commit order is a Cassandra convention for `test/microbench/`; neither project has that layout.

### `commits.provenance`

Advisory. Owner: contributor.

Signs of AI assistance are a head branch starting with `claude/`, `copilot/`, or `codex/`, or a PR description that mentions `claude`, `copilot`, `chatgpt`, `gpt-N`, `codex`, `gemini`, `llm`, `AI-generated`, or `AI-assisted`.

- **warn**: at least one sign is present and no commit has an `Assisted-by:` or `Generated-by:` trailer, or a `Co-authored-by:` trailer naming one of those tools. Moves the recommendation to "needs work".
- **pass**: otherwise. All trailers found are listed. No trailer is required when there are no signs.

### `changelog.entry`

Advisory. Owner: contributor.

Production code is any path under a module's `src/main/` that is not a test path (see the Testing aspect).

- **not-applicable**: no production code changed.
- **warn**: production code changed but the root `CHANGES.txt` has no added lines; or added lines exist but none matches ` * <summary> (KEY-N)` (one or more comma-separated keys in the parentheses); or a matching line does not mention the PR's ticket. Moves the recommendation to "needs work".
- **pass**: a well-formed added line names the PR's ticket.

## How to fix

A squash merge replaces the PR's commits with one commit, so the message that matters is the squash commit's. It should read:

```
CASSANALYTICS-216: Fix CDC Avro schema conversion for quoted UDT names

Patch by Jane Doe; Reviewed by TBD for CASSANALYTICS-216
```

- If an AI tool helped write the patch, add a trailer per tool, for example `Assisted-by: Claude Code:claude-opus-5`, and say so in the PR description.
- Add co-authors with `Co-authored-by: Name <email>`.

For `CHANGES.txt`, add a line at the top of the section for the next release:

```
 * Fix CDC Avro schema conversion for quoted UDT names (CASSANALYTICS-216)
```

## Limits

- The PR's commits are checked, not the squash commit that will land, so `commits.message-format` is informational.
- Every commit is checked, including review fix-ups.
- AI detection reads only the branch name and the PR description, not commit messages.
- `changelog.entry` does not check that the line is in the right version section, and asks for an entry for every production change, including refactors.
- NEWS.txt is not checked.
