# Report aspect documents

Each file here explains one aspect of the PR review report: what is checked, the Cassandra project rule behind it, and how each result is decided. The report embeds each document in its section as a collapsed "How this is judged" panel. Rendering fails if a document is missing.

## Outline

Every aspect document uses this outline, in this order:

```
# <Aspect name>
## What is checked
## Why
## How each status is decided
### `<check id>`        (one per check whose aspect is this document)
## How to fix
## Limits
```

- **Why** cites the Cassandra source for each rule, with a full https link where one exists.
- **How each status is decided** states, for each check, whether it is blocking or advisory, who acts (contributor, reviewer, or committer), and the exact conditions for pass, fail, warn, unknown, and not-applicable. Documents without checks describe how their content is produced.
- Markdown is limited to what the report's renderer supports: headings, lists, fenced code, inline code, bold, italic, links, and pipe tables. No HTML and no images.

`tests/test_aspect_docs.py` fails when a registered check id has no `### ` entry in its aspect document, when an aspect lacks a document, or when a document lacks one of the five `##` headings.

## Index

| Aspect document | Report section | Check ids |
|---|---|---|
| [summary.md](summary.md) | Summary | none (recommendation rules) |
| [jira.md](jira.md) | JIRA ticket | `jira.key-present`, `jira.ticket-exists`, `jira.key-consistent`, `jira.not-resolved`, `jira.fix-version` |
| [ci.md](ci.md) | Branches & CI | `ci.evidence`, `ci.freshness`, `ci.profile`, `ci.failures` |
| [branches.md](branches.md) | Branches & CI | `branches.coverage` |
| [testing.md](testing.md) | Testing | `tests.present` |
| [labplan.md](labplan.md) | Lab plan | none (informational plan) |
| [commits.md](commits.md) | Commits & changelog | `commits.message-format`, `commits.provenance`, `changelog.entry` |
| [static.md](static.md) | Code style | `static.banned-api`, `static.license-header`, `static.protected-paths`, `static.deprecated-since` |
| [compatibility.md](compatibility.md) | Compatibility | `compat.config-pairing`, `compat.system-properties`, `compat.nodetool-help`, `compat.surfaces` |
| [votes.md](votes.md) | Reviews & votes | `votes.committer-plus-ones` |
| [triage.md](triage.md) | Triage | none (difficulty signals) |
| [code-review.md](code-review.md) | Code review | none (lenses not in this version) |
| [changes.md](changes.md) | Changes | none (diff view) |

The section-to-document mapping is `SECTIONS` in `cpr/model.py`. Each check's aspect is set in its `@check` decorator in `cpr/checks/`.

## Sources

The research behind these documents, with every rule's primary source, is in `docs/research/cassandra-standards.md` and `docs/research/pr-landscape.md`.
