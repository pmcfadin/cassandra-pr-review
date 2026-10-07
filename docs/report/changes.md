# Changes

## What is checked

This section shows the PR's diff. It is a viewer, not a check. The diff runs from the merge base of the PR and its base branch to the PR head, with the PR's GitHub review comments attached to their lines.

The view is produced by the ide-explain generator from the rustyrazorblade `dev-skills` plugin: a file tree on the left, the diff top right, and an explanation pane bottom right. Files that a check flagged (a fail or warn whose evidence names a file) carry a note in the explanation pane listing the check and what it found.

## Why

Reviewers need the code next to the results. A contributor looking at a warning such as "banned API at line 42" can open that file and line here. ide-explain is used rather than a custom viewer so that improvements to the plugin reach the report without changes to this tool.

## How each status is decided

The section badge is **info** when the diff view was produced and **unknown** when it was not.

How the view is produced:

1. The tool finds the newest installed generator under `~/.claude/plugins/cache/rustyrazorblade-plugins/dev-skills/<version>/skills/ide-explain/scripts/generate-explain.py`. The environment variable `CPR_IDE_EXPLAIN` overrides the path. The version used is recorded in About.
2. It runs the generator inside the local clone of apache/cassandra with the merge base, the PR head, the PR number (for review comments), and a per-file notes map built from the check results.
3. **Size budget**: if the output is larger than 8 MB, the generator runs again limited to `src/`, and the section notes that tests and other files appear only in the file table. If the `src/`-only view is still over 8 MB, no view is embedded.
4. **Safety**: the output is checked for external scripts, external stylesheets, `@import`, and `fetch(`. If any is found, the view is not embedded. Otherwise the page is stored base64-encoded in the report and loaded into an `<iframe sandbox="allow-scripts">` through `srcdoc`. Without `allow-same-origin`, the embedded page cannot read or change the rest of the report.

When there is no view (plugin not installed, the generator failed, too large, or network references found), the section shows a plain list of changed files with additions and deletions, and the reason. The rest of the report is unaffected.

## How to fix

Nothing for contributors. If you generate reports yourself and the view is missing, install the `dev-skills` plugin from rustyrazorblade-plugins in Claude Code, or set `CPR_IDE_EXPLAIN` to the path of `generate-explain.py`, then run `cpr review <N>` again.

## Limits

- The view depends on a plugin installed on the machine that built the report. Reports built elsewhere may lack it.
- On very large PRs only `src/` is shown.
- The diff is against the merge base, so it can differ from GitHub's "Files changed" tab when the base branch has moved.
- Review comments are those on GitHub when the report was built. JIRA comments are in the JIRA section.
- Notes come only from checks whose evidence names a file. Checks about the PR as a whole (votes, CI) add no notes.
