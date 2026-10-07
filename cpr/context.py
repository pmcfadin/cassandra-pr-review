"""Reviewer context: related tickets, per-file experts, and suggested reviewers.

A pure function of the bundle's `history` (gathered by cpr.ingest.history), the ticket, and the
ASF roster. See openspec change reviewer-context for the rules.
"""

import datetime

from cpr import credits
from cpr.ingest.history import load_config


def _date(s):
    try:
        return datetime.date.fromisoformat((s or "")[:10])
    except ValueError:
        return None


def _subject(message):
    return (message or "").splitlines()[0][:160] if message else ""


def related_tickets(history):
    tickets, untracked = {}, {}
    for b in history.get("blame", []):
        c = history["commits"].get(b["sha"])
        if not c or c.get("merge"):
            continue
        key = credits.primary_key(c["message"])
        if key:
            t = tickets.setdefault(key, {"key": key, "lines": 0, "commits": {}, "files": set()})
            t["lines"] += b["lines"]
            t["files"].add(b["path"])
            t["commits"][c["sha"]] = {"sha": c["sha"], "date": c["date"], "subject": _subject(c["message"])}
        else:
            u = untracked.setdefault(c["sha"], {"sha": c["sha"], "date": c["date"], "subject": _subject(c["message"]),
                                                "author": c["author_name"], "lines": 0})
            u["lines"] += b["lines"]
    looked_up = history.get("tickets") or {}
    out = []
    for t in sorted(tickets.values(), key=lambda t: (-t["lines"], t["key"])):
        info = looked_up.get(t["key"], {})
        out.append({"key": t["key"], "lines": t["lines"], "files": sorted(t["files"]),
                    "summary": info.get("summary"), "status": info.get("status"), "resolution": info.get("resolution"),
                    "issuetype": info.get("issuetype"),
                    "url": info.get("url") or f"https://issues.apache.org/jira/browse/{t['key']}",
                    "commits": sorted(t["commits"].values(), key=lambda c: c["date"], reverse=True),
                    "last_changed": max(c["date"] for c in t["commits"].values())})
    return out, sorted(untracked.values(), key=lambda u: -u["lines"])


def _credits_for(commit):
    parsed = credits.parse(commit["message"])
    if parsed["authors"]:
        return [(n, None, "author") for n in parsed["authors"]] + [(n, None, "reviewer") for n in parsed["reviewers"]]
    # No credit line: the git author is the patch author.
    return [(commit["author_name"], commit["author_email"], "author")]


def experts(history, resolver, today, cfg):
    per_file, totals = {}, {}
    for path, log in (history.get("file_logs") or {}).items():
        people = {}
        for c in log:
            d = _date(c["date"])
            if not d:
                continue
            age = max(0.0, (today - d).days / 365.25)
            if age > cfg["window_years"]:
                continue
            decay = 0.5 ** (age / cfg["half_life_years"])
            for name, email, role in _credits_for(c):
                pkey, display, asf = resolver.resolve(name, email)
                p = people.setdefault(pkey, {"person": pkey, "name": display, "asf_id": asf, "score": 0.0,
                                             "patches": 0, "reviews": 0, "latest": c["date"]})
                weight = cfg["author_weight"] if role == "author" else cfg["reviewer_weight"]
                p["score"] += weight * decay
                p["patches" if role == "author" else "reviews"] += 1
                p["latest"] = max(p["latest"], c["date"])
        ranked = sorted(people.values(), key=lambda p: (-p["score"], p["name"]))
        for p in ranked:
            p["score"] = round(p["score"], 2)
            t = totals.setdefault(p["person"], {**p, "score": 0.0, "files": []})
            t["score"] += p["score"]
            t["files"].append(path)
            t["latest"] = max(t["latest"], p["latest"])
        per_file[path] = ranked[:cfg["top_per_file"]]
    return per_file, totals


def pr_author_keys(bundle, resolver):
    """Person keys for everyone who authored this PR: whoever opened it and every commit author.

    A committer sometimes opens a PR for someone else's patch, so both count. The GitHub login is
    tried as an ASF id too (many committers use the same name for both).
    """
    keys = set()
    login = bundle["pr"].get("author") or ""
    keys.add(resolver.resolve(login)[0] if login.lower() in resolver.committers else None)
    for c in bundle.get("commits", []):
        keys.add(resolver.resolve(c.get("author_name") or "", c.get("author_email"))[0])
    for email in (bundle.get("voter_emails") or {}).get(login, []):
        keys.add(resolver.resolve("", email)[0])
    return {k for k in keys if k and k != "name:"}


def suggest(totals, bundle, resolver, cfg):
    author = pr_author_keys(bundle, resolver)
    ticket = (bundle.get("jira") or {}).get("ticket") or {}
    reviewing = set()
    # Already involved: in the Reviewers field, or has commented on the ticket.
    people = list(ticket.get("reviewers", []))
    people += [{"name": c.get("author"), "display": c.get("display")} for c in ticket.get("comments", [])]
    for u in people:
        reviewing.add(resolver.resolve(u.get("display") or "", None)[0])
        if u.get("name") in resolver.committers:
            reviewing.add(u["name"])
    candidates = [p for p in totals.values() if p["asf_id"] and p["person"] not in author]
    candidates.sort(key=lambda p: (-p["score"], p["name"]))
    already = [p for p in candidates if p["person"] in reviewing]
    suggested = [p for p in candidates if p["person"] not in reviewing][:cfg["max_suggestions"]]

    def row(p):
        return {"person": p["person"], "name": p["name"], "asf_id": p["asf_id"], "score": round(p["score"], 2),
                "patches": p["patches"], "reviews": p["reviews"], "latest": p["latest"], "files": p["files"]}
    return [row(p) for p in suggested], [row(p) for p in already]


def build(bundle, cfg=None, today=None):
    cfg = cfg or load_config()
    history = bundle.get("history")
    if not history:
        return {"status": "unavailable", "reason": "This bundle has no history; re-run the review to gather it."}
    roster = ((bundle.get("roster") or {}).get("roster")) or {}
    resolver = credits.Resolver(roster)
    today = today or _date(bundle["meta"]["fetched_at"]) or datetime.date.today()
    tickets, untracked = related_tickets(history)
    per_file, totals = experts(history, resolver, today, cfg)
    suggested, already = suggest(totals, bundle, resolver, cfg)
    ticket = (bundle.get("jira") or {}).get("ticket") or {}
    own_key = (bundle.get("jira_key") or {}).get("key")
    return {
        "status": "ok",
        "new_files_only": history.get("new_files_only", False),
        "related_tickets": [t for t in tickets if t["key"] != own_key],
        "untracked_commits": untracked,
        "linked_issues": ticket.get("issuelinks", []),
        "experts": per_file,
        "experts_from": history.get("log_refs", {}),
        "suggested_reviewers": suggested,
        "already_reviewing": already,
        "budget": {k: history.get(k) for k in ("hunks_total", "hunks_blamed", "hunks_skipped", "files_total",
                                                "files_logged", "files_skipped")},
        "tickets_error": history.get("tickets_error"),
    }
