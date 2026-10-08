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


_PERF_RE = re.compile(r"\b(perf(ormance)?|faster|speed.?up|latency|throughput|allocation|megamorphic|"
                      r"avoid (an )?(extra )?cop(y|ies)|copy-on-write|optimi[sz]e|reduce (overhead|allocation))",
                      re.IGNORECASE)
_BENCH_BODY_RE = re.compile(r"\b(JMH|benchmark)", re.IGNORECASE)
_FIXUP_RE = re.compile(r"^(fixup|squash)!")


def perf_signals(bundle, ctx):
    """([strong signals], [medium signals]) naming what fired."""
    strong, medium = [], []
    bench = [p for p in ctx.paths if p.startswith("test/microbench/")]
    if bench:
        strong.append(f"changed benchmark file `{bench[0]}`" + (f" (+{len(bench) - 1} more)" if len(bench) > 1 else ""))
    t = ctx.ticket or {}
    if "performance" in [l.lower() for l in t.get("labels") or []]:
        strong.append("JIRA label `performance`")
    if "Test/benchmark" in (t.get("components") or []):
        strong.append("JIRA component `Test/benchmark`")
    if _PERF_RE.search(ctx.pr.get("title") or "") or _PERF_RE.search(t.get("summary") or ""):
        medium.append("title or JIRA summary has a performance keyword")
    if _BENCH_BODY_RE.search(ctx.pr.get("body") or ""):
        medium.append("PR description mentions JMH or a benchmark")
    return strong, medium


@check("commit.perf-structure", "Performance PR: benchmark commit comes first", "commit", "commits", blocking=False)
def perf_structure(bundle, ctx):
    strong, medium = perf_signals(bundle, ctx)
    signals = [ev(f"Signal (strong): {s}") for s in strong] + [ev(f"Signal (medium): {s}") for s in medium]
    if not strong and len(medium) < 2:
        return Result("not-applicable", "Not detected as a performance PR" +
                      (f" (one weak signal: {medium[0]})" if medium else ""))
    commits = (bundle.get("static_analysis") or {}).get("commits")
    if not commits:
        return Result("unknown", "Commit order is unavailable (static analysis did not run or listed no commits)",
                      signals)
    ordered = [c for c in commits if not _FIXUP_RE.match(c.get("subject") or "")] or commits

    def first(prefix):
        return next((i for i, c in enumerate(ordered) if any(p.startswith(prefix) for p in c.get("paths") or [])), None)

    b, s = first("test/microbench/"), first("src/java/")

    def row(i):
        c = ordered[i]
        return ev(f"`{c['sha'][:10]}` {(c.get('subject') or '')[:90]}")

    if s is None:
        return Result("not-applicable", "Performance PR with no `src/java` change (benchmark or build only)", signals)
    if b is None:
        return Result("warn", "Performance PR changes `src/java` but adds or changes no JMH benchmark",
                      signals + [ev("First `src/java` commit:"), row(s)], action_required=False,
                      action="Add a benchmark under `test/microbench/` so reviewers can measure the change.")
    if b < s:
        return Result("pass", "The benchmark commit precedes the first `src/java` change",
                      signals + [ev("Benchmark commit:"), row(b), ev("First `src/java` commit:"), row(s)])
    if b == s:
        return Result("warn", "Benchmark and change are in one commit, so the benchmark cannot run on the parent",
                      signals + [row(b)], action_required=False,
                      action="Split the benchmark into its own earlier commit so it can run on both sides.")
    return Result("warn", "The benchmark commit comes after the change it measures",
                  signals + [ev("First `src/java` commit:"), row(s), ev("First benchmark commit:"), row(b)],
                  action_required=True,
                  action="Reorder the commits so the benchmark commit comes first (interactive rebase), "
                         "letting it run before and after the change.")
