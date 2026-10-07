"""JIRA ticket and branch-coverage checks."""

import re

from cpr.checks import Result, check, ev

_RELEASE_RE = re.compile(r"^cassandra-(\d+)\.(\d+)$")
_VERSION_RE = re.compile(r"^(\d+)(?:\.(\d+|x))?")


def is_release_branch(base):
    return base == "trunk" or bool(_RELEASE_RE.match(base or ""))


def version_to_branch(version, release_branches):
    """Map a JIRA fix version ("5.0.10", "6.0-alpha3", "7.x") to an apache base branch."""
    m = _VERSION_RE.match(version or "")
    if not m:
        return None
    major = int(m.group(1))
    minor = m.group(2)
    candidates = []
    for b in release_branches:
        bm = _RELEASE_RE.match(b)
        if bm and int(bm.group(1)) == major and (minor in (None, "x") or int(bm.group(2)) == int(minor)):
            candidates.append((int(bm.group(2)), b))
    if candidates:
        return max(candidates)[1]
    return "trunk"


def _jira_unknown(ctx):
    if ctx.jira_status == "unavailable":
        return Result("unknown", "JIRA could not be reached", [ev((ctx.bundle["jira"] or {}).get("error") or "")])
    return None


@check("jira.key-present", "PR references a CASSANDRA ticket", "ticket", "jira", blocking=True)
def key_present(bundle, ctx):
    info = bundle["jira_key"]
    base = ctx.pr["base"]
    if info["key"]:
        return Result("pass", f"{info['key']} found in {', '.join(info['sources'])}")
    if not is_release_branch(base):
        return Result("warn", f"No CASSANDRA ticket, but the base `{base}` is a feature branch",
                      action="Feature-branch work often has no ticket; add one if the work will reach trunk.",
                      blocking=False)
    return Result("fail", "No CASSANDRA-NNNNN key in the title, branch, body, or commits",
                  action="Create or find the JIRA ticket and put its key in the PR title, e.g. `CASSANDRA-12345: <summary>`.")


@check("jira.ticket-exists", "Ticket exists in JIRA", "ticket", "jira", blocking=True)
def ticket_exists(bundle, ctx):
    if not ctx.key:
        return Result("not-applicable", "No ticket key to look up")
    unknown = _jira_unknown(ctx)
    if unknown:
        return unknown
    if ctx.jira_status == "not_found":
        return Result("fail", f"{ctx.key} does not exist in JIRA",
                      action="Fix the key in the PR title or create the ticket.")
    t = ctx.ticket
    return Result("pass", f"{t['key']}: {t['summary']} ({t['status']})", [ev(t["key"], t["url"])])


@check("jira.key-consistent", "Title and branch name the same ticket", "ticket", "jira", blocking=False)
def key_consistent(bundle, ctx):
    info = bundle["jira_key"]
    if not info["key"]:
        return Result("not-applicable", "No ticket key")
    if info["conflicts"]:
        others = ", ".join(f"{c['key']} ({'/'.join(c['sources'])})" for c in info["conflicts"])
        return Result("warn", f"Using {info['key']}, but also found {others}",
                      [ev(f"{c['key']} in {', '.join(c['sources'])}") for c in info["conflicts"]],
                      action="Make the PR title and branch name refer to the same ticket.")
    return Result("pass", f"Only {info['key']} is referenced in the title and branch")


@check("jira.not-resolved", "Ticket is still open", "ticket", "jira", blocking=False, owner="reviewer")
def not_resolved(bundle, ctx):
    if not ctx.ticket:
        return _jira_unknown(ctx) or Result("not-applicable", "No ticket")
    t = ctx.ticket
    if t["status"] in ("Resolved", "Closed"):
        return Result("warn", f"{t['key']} is {t['status']} ({t['resolution'] or 'no resolution'}); this patch may "
                      "already have landed or been superseded", [ev(t["key"], t["url"])],
                      action="Check whether this PR is still needed; close it if the change already landed.")
    return Result("pass", f"Status: {t['status']}")


@check("jira.fix-version", "Fix Version matches the base branch", "ticket", "jira", blocking=False)
def fix_version(bundle, ctx):
    if not ctx.ticket:
        return _jira_unknown(ctx) or Result("not-applicable", "No ticket")
    t = ctx.ticket
    base = ctx.pr["base"]
    if not is_release_branch(base):
        return Result("not-applicable", f"Base `{base}` is a feature branch")
    if not t["fix_versions"]:
        return Result("warn", "Fix Version is not set on the ticket",
                      action="Set Fix Version(s) on the JIRA ticket for every branch the patch targets.")
    branches = bundle.get("release_branches", [])
    mapped = {v: version_to_branch(v, branches) for v in t["fix_versions"]}
    if base in mapped.values():
        return Result("pass", f"Fix Versions {', '.join(t['fix_versions'])} include `{base}`")
    return Result("warn", f"Base branch `{base}` is not among the Fix Versions ({', '.join(t['fix_versions'])})",
                  [ev(f"{v} → {b}") for v, b in mapped.items()],
                  action="Either retarget the PR or update the ticket's Fix Version(s).")


@check("branches.coverage", "Every Fix Version branch has a PR", "ticket", "branches", blocking=False)
def branch_coverage(bundle, ctx):
    if not ctx.ticket:
        return _jira_unknown(ctx) or Result("not-applicable", "No ticket")
    t = ctx.ticket
    branches = bundle.get("release_branches", [])
    wanted = sorted({version_to_branch(v, branches) for v in t["fix_versions"]} - {None})
    have = ctx.targeted_branches()
    evidence = [ev(f"`{b}`: PR #{have[b]['number']}" if b in have else f"`{b}`: no PR",
                   have[b]["url"] if b in have else None) for b in wanted]
    if not wanted:
        return Result("not-applicable", "Fix Version is not set, so the expected branches are unknown")
    missing = [b for b in wanted if b not in have]
    if missing:
        return Result("warn", f"No PR yet for {', '.join('`' + b + '`' for b in missing)}", evidence,
                      action="Open a PR per missing branch (merge order 4.0 → 4.1 → 5.0 → 6.0 → trunk), "
                             "or explain on the ticket why it is not needed.")
    return Result("pass", f"PRs exist for all {len(wanted)} Fix Version branches", evidence)
