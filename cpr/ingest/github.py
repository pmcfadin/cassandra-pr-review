"""Read-only GitHub access for apache/cassandra, via `gh api`."""

import urllib.parse

from cpr import REPO
from cpr.net import NetError, gh_json

_TRAILERS = ("co-authored-by", "assisted-by", "generated-by", "signed-off-by")


class PRNotFound(Exception):
    pass


def trailers(message):
    out = []
    for line in (message or "").splitlines():
        name, sep, value = line.partition(":")
        if sep and name.strip().lower() in _TRAILERS:
            out.append({"name": name.strip(), "value": value.strip()})
    return out


def _user(u):
    return (u or {}).get("login")


def fetch_pr(number, recorder):
    try:
        pr = gh_json(f"repos/{REPO}/pulls/{number}", recorder=recorder)
    except NetError as e:
        if e.status == 404 or "Not Found" in str(e):
            raise PRNotFound(f"#{number} is not a pull request on {REPO}") from e
        raise
    head = pr.get("head") or {}
    return {
        "number": pr["number"],
        "url": pr.get("html_url"),
        "title": pr.get("title") or "",
        "body": pr.get("body") or "",
        "author": _user(pr.get("user")),
        "author_association": pr.get("author_association"),
        "state": pr.get("state"),
        "merged": bool(pr.get("merged")),
        "draft": bool(pr.get("draft")),
        "base": (pr.get("base") or {}).get("ref"),
        "head_ref": head.get("ref"),
        "head_sha": head.get("sha"),
        "head_repo": ((head.get("repo") or {}).get("full_name")),
        "labels": [lbl.get("name") for lbl in pr.get("labels") or []],
        "created_at": pr.get("created_at"),
        "updated_at": pr.get("updated_at"),
        "mergeable": pr.get("mergeable"),
        "commits": pr.get("commits"),
        "additions": pr.get("additions"),
        "deletions": pr.get("deletions"),
        "changed_files": pr.get("changed_files"),
    }


def fetch_commits(number, recorder):
    raw = gh_json(f"repos/{REPO}/pulls/{number}/commits?per_page=100", recorder=recorder, paginate=True) or []
    out = []
    for c in raw:
        commit = c.get("commit") or {}
        author = commit.get("author") or {}
        out.append({
            "sha": c.get("sha"),
            "message": commit.get("message") or "",
            "author_name": author.get("name"),
            "author_email": author.get("email"),
            "login": _user(c.get("author")),
            "trailers": trailers(commit.get("message")),
        })
    return out


def fetch_reviews(number, recorder):
    raw = gh_json(f"repos/{REPO}/pulls/{number}/reviews?per_page=100", recorder=recorder, paginate=True) or []
    return [{
        "user": _user(r.get("user")),
        "state": r.get("state"),
        "association": r.get("author_association"),
        "body": r.get("body") or "",
        "submitted_at": r.get("submitted_at"),
        "url": r.get("html_url"),
        "commit_id": r.get("commit_id"),
    } for r in raw]


def fetch_review_comments(number, recorder):
    raw = gh_json(f"repos/{REPO}/pulls/{number}/comments?per_page=100", recorder=recorder, paginate=True) or []
    return [{
        "user": _user(r.get("user")),
        "association": r.get("author_association"),
        "path": r.get("path"),
        "line": r.get("line") or r.get("original_line"),
        "body": r.get("body") or "",
        "created_at": r.get("created_at"),
        "url": r.get("html_url"),
    } for r in raw]


def fetch_issue_comments(number, recorder):
    raw = gh_json(f"repos/{REPO}/issues/{number}/comments?per_page=100", recorder=recorder, paginate=True) or []
    return [{
        "user": _user(r.get("user")),
        "association": r.get("author_association"),
        "body": r.get("body") or "",
        "created_at": r.get("created_at"),
        "url": r.get("html_url"),
    } for r in raw]


def search_pr_numbers(key, recorder):
    """PR numbers whose title or body mention `key` (comments are excluded by `in:title,body`)."""
    q = urllib.parse.quote(f"repo:{REPO} is:pr {key} in:title,body")
    pages = gh_json(f"search/issues?q={q}&per_page=50", recorder=recorder) or {}
    return [item["number"] for item in pages.get("items", []) if "pull_request" in item]


def commit_emails_for(login, recorder):
    """Emails on a user's recent commits to apache/cassandra, used to match ASF ids."""
    try:
        raw = gh_json(f"repos/{REPO}/commits?author={urllib.parse.quote(login)}&per_page=20", recorder=recorder) or []
    except NetError:
        return []
    emails = set()
    for c in raw:
        for who in ("author", "committer"):
            email = ((c.get("commit") or {}).get(who) or {}).get("email")
            if email:
                emails.add(email.lower())
    return sorted(emails)
