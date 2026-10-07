"""Committer +1 votes from GitHub reviews and JIRA comments, matched against the ASF roster."""

import re

from cpr import paths
from cpr.checks import Result, check, ev

_PLUS_ONE_RE = re.compile(r"(^|[\s(\[])\+1\b(?!\d)")


def committer_id(bundle, source, who, association=None):
    """Return (asf_id, rule) when `who` is a Cassandra committer, else (None, None)."""
    roster = ((bundle.get("roster") or {}).get("roster") or {}).get("committers") or {}
    overrides = bundle.get("overrides") or {}
    if source == "jira":
        mapped = overrides.get("jira", {}).get(who)
        if mapped and mapped in roster:
            return mapped, "overrides file"
        if who in roster:
            return who, "JIRA username is an ASF id on the roster"
        return None, None
    mapped = overrides.get("github", {}).get(who)
    if mapped and mapped in roster:
        return mapped, "overrides file"
    # Prefer a real ASF id (so the same person voting on GitHub and JIRA is counted once).
    for email in (bundle.get("voter_emails") or {}).get(who, []):
        if email.endswith("@apache.org") and email.split("@")[0] in roster:
            return email.split("@")[0], f"commits as {email}"
    if association in ("MEMBER", "OWNER"):
        return f"github:{who}", f"GitHub association {association} (apache org member)"
    return None, None


def collect_votes(bundle):
    counted, others = {}, []
    author = bundle["pr"]["author"]
    for r in bundle.get("reviews", []):
        if r["state"] != "APPROVED":
            continue
        cid, rule = committer_id(bundle, "github", r["user"], r["association"])
        item = {"who": r["user"], "source": "GitHub review", "url": r.get("url"), "rule": rule}
        if cid:
            counted.setdefault(cid, item)
        else:
            others.append(item)
    ticket = (bundle.get("jira") or {}).get("ticket") or {}
    authors = {u["name"] for u in ticket.get("authors", []) + ticket.get("assignee", []) if u.get("name")}
    for c in ticket.get("comments", []):
        if not _PLUS_ONE_RE.search(c["body"]) or c["author"] in authors:
            continue
        cid, rule = committer_id(bundle, "jira", c["author"])
        item = {"who": c["display"] or c["author"], "source": "JIRA comment", "url": c.get("url"), "rule": rule}
        if cid:
            counted.setdefault(cid, item)
        else:
            others.append(item)
    # The author counts as one vote when they are a committer (not for test-only changes; see the check).
    pr = bundle["pr"]
    cid, rule = committer_id(bundle, "github", author, pr.get("author_association"))
    author_vote = None
    if cid and cid not in counted:
        author_vote = (cid, {"who": author, "source": "PR author", "url": pr.get("url"),
                             "rule": f"author is a committer ({rule})"})
    return counted, others, author_vote


@check("votes.committer-plus-ones", "Two committer +1s", "governance", "votes", blocking=True, owner="reviewer")
def committer_votes(bundle, ctx):
    counted, others, author_vote = collect_votes(bundle)
    test_only = bool(ctx.paths) and all(paths.is_test(p) for p in ctx.paths)
    needed = 1 if test_only else 2
    if author_vote and not test_only:
        counted = {**counted, author_vote[0]: author_vote[1]}
    rows = [ev(f"{v['who']} via {v['source']} — committer by {v['rule']}", v.get("url")) for v in counted.values()]
    rows += [ev(f"{v['who']} via {v['source']} — non-committer +1, not counted", v.get("url")) for v in others]
    status = (bundle.get("roster") or {}).get("status")
    if status == "unavailable" and not counted:
        return Result("unknown", "Could not load the ASF committer roster; raw +1s are listed", rows)
    have = len(counted)
    if have >= needed:
        return Result("pass", f"{have} committer +1(s) (needs {needed})", rows)
    return Result("fail", f"needs {needed} committer +1s (has {have})", rows,
                  action="Ask for review on the JIRA ticket or the dev@ list; a committer marks +1 on JIRA or approves on GitHub.")
