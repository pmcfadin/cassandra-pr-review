"""Commit message, trailer, and CHANGES.txt checks."""

import re

from cpr import paths
from cpr.checks import Result, check, ev

_PATCH_BY_RE = re.compile(r"^patch by .+?[;,]\s*reviewed by .+? for (CASSANDRA-\d+)", re.IGNORECASE | re.MULTILINE)
_CHANGES_RE = re.compile(r"^ \* .+\((?:CASSANDRA-\d+(?:,\s*)?)+\)\s*$")
_AI_HINT_RE = re.compile(r"\b(claude|copilot|chatgpt|gpt-\d|codex|gemini|llm|ai[- ]generated|ai[- ]assisted)\b",
                         re.IGNORECASE)


@check("commits.message-format", "Commit message follows the project format", "commit", "commits", blocking=False)
def message_format(bundle, ctx):
    commits = bundle["commits"]
    if not commits:
        return Result("unknown", "No commits found")
    rows, problems = [], []
    for c in commits:
        first = c["message"].splitlines()[0] if c["message"] else ""
        m = _PATCH_BY_RE.search(c["message"])
        issues = []
        if ctx.key and ctx.key.lower() in first.lower():
            issues.append("first line repeats the ticket key")
        if not m:
            issues.append("no `patch by …; reviewed by … for CASSANDRA-N` line")
        elif ctx.key and m.group(1).upper() != ctx.key:
            issues.append(f"`patch by` line names {m.group(1)}, not {ctx.key}")
        rows.append(ev(f"`{c['sha'][:10]}` {first[:90]}" + (f" — {'; '.join(issues)}" if issues else " — ok")))
        problems.extend(issues)
    note = f"{len(commits)} commit(s); committers squash to one per branch when they commit."
    rows.append(ev(note))
    if problems:
        return Result("warn", "Commit message does not follow the `patch by … reviewed by … for CASSANDRA-N` format",
                      rows, action="Format the final commit as: one-line summary, blank line, "
                                   "`patch by <you>; reviewed by <reviewers> for CASSANDRA-N`. Committers often rewrite "
                                   "this when committing, so this alone does not block.",
                      action_required=False)
    return Result("pass", "Commit message(s) follow the project format", rows)


@check("commits.provenance", "Co-author and AI-assistance trailers", "commit", "commits", blocking=False)
def provenance(bundle, ctx):
    rows = []
    has_ai_trailer = False
    for c in bundle["commits"]:
        for t in c["trailers"]:
            rows.append(ev(f"`{c['sha'][:10]}` {t['name']}: {t['value']}"))
            if t["name"].lower() in ("assisted-by", "generated-by") or (
                    t["name"].lower() == "co-authored-by" and _AI_HINT_RE.search(t["value"])):
                has_ai_trailer = True
    hints = []
    pr = ctx.pr
    if (pr.get("head_ref") or "").lower().startswith(("claude/", "copilot/", "codex/")):
        hints.append(f"branch name `{pr['head_ref']}`")
    if _AI_HINT_RE.search(pr.get("body") or ""):
        hints.append("PR description mentions an AI tool")
    if hints and not has_ai_trailer:
        return Result("warn", "Signs of AI assistance without an `Assisted-by:` trailer",
                      rows + [ev(h) for h in hints],
                      action="If AI tools helped write this patch, add an `Assisted-by: <agent>:<model>` trailer "
                             "(see AGENTS.md in apache/cassandra).")
    summary = f"{len(rows)} trailer(s) found" if rows else "No co-author or AI trailers (none required)"
    return Result("pass", summary, rows)


@check("changelog.entry", "CHANGES.txt entry", "changelog", "commits", blocking=False)
def changelog(bundle, ctx):
    prod = [p for p in ctx.paths if paths.is_prod(p)]
    if not prod:
        return Result("not-applicable", "No production code changed (test, doc, or build only)")
    added = [t for _, t in ctx.added.get("CHANGES.txt", {}).get("added", [])]
    if not added:
        return Result("warn", "Production code changed but CHANGES.txt did not",
                      action=f"Add ` * <summary> ({ctx.key or 'CASSANDRA-N'})` at the top of the correct version "
                             "section in CHANGES.txt. Some committers add it at commit time; say so on the PR if agreed.")
    good = [t for t in added if _CHANGES_RE.match(t)]
    rows = [ev(f"`{t.strip()}`") for t in added[:5]]
    if not good:
        return Result("warn", "CHANGES.txt changed, but no line matches ` * <summary> (CASSANDRA-N)`", rows,
                      action="Use the format ` * <summary> (CASSANDRA-N)`.")
    if ctx.key and not any(ctx.key in t for t in good):
        return Result("warn", f"CHANGES.txt entry does not mention {ctx.key}", rows,
                      action=f"Reference {ctx.key} in the entry.")
    return Result("pass", "CHANGES.txt entry present", rows)
