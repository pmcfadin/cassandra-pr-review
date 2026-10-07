"""Read-only, anonymous access to issues.apache.org JIRA."""

import json

from cpr.net import NetError, http_get

BASE = "https://issues.apache.org/jira"
API = BASE + "/rest/api/2"

# Custom fields are located by these names at runtime (ids differ between JIRA instances).
FIELD_NAMES = {
    "reviewers": "Reviewers",
    "authors": "Authors",
    "test_doc_plan": "Test and Documentation Plan",
    "impacts": "Impacts",
    "since_versions": "Since Version",
    "source_control_link": "Source Control Link",
}


def _users(value):
    if not value:
        return []
    if isinstance(value, dict):
        value = [value]
    out = []
    for u in value:
        if isinstance(u, dict):
            out.append({"name": u.get("name") or u.get("key"), "display": u.get("displayName")})
    return out


def _names(value):
    if not value:
        return []
    if isinstance(value, dict):
        value = [value]
    return [v.get("name") or v.get("value") for v in value if isinstance(v, dict)]


def _text(value):
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return ", ".join(_names(value))
    return str(value)


def _issuelink(link):
    kind = link.get("type") or {}
    if "outwardIssue" in link:
        other, relation = link["outwardIssue"], kind.get("outward")
    else:
        other, relation = link.get("inwardIssue") or {}, kind.get("inward")
    fields = other.get("fields") or {}
    return {"relation": relation or kind.get("name"), "key": other.get("key"),
            "summary": fields.get("summary") or "", "status": (fields.get("status") or {}).get("name"),
            "url": f"{BASE}/browse/{other.get('key')}"}


def lookup_keys(keys, recorder):
    """{key: {summary, status, resolution, issuetype, url}} for many keys; unknown keys are dropped.

    Uses validateQuery=warn so one key that does not exist does not fail the whole query.
    """
    import urllib.parse
    out = {}
    keys = sorted(set(keys))
    for i in range(0, len(keys), 50):
        chunk = keys[i:i + 50]
        jql = urllib.parse.quote(f"key in ({','.join(chunk)})")
        url = (f"{API}/search?jql={jql}&fields=summary,status,resolution,issuetype,created"
               f"&maxResults=50&validateQuery=warn")
        data = json.loads(http_get(url, recorder=recorder))
        for issue in data.get("issues", []):
            f = issue.get("fields") or {}
            out[issue["key"]] = {"summary": f.get("summary") or "", "status": (f.get("status") or {}).get("name"),
                                 "resolution": (f.get("resolution") or {}).get("name") if f.get("resolution") else None,
                                 "issuetype": (f.get("issuetype") or {}).get("name"),
                                 "created": (f.get("created") or "")[:10],
                                 "url": f"{BASE}/browse/{issue['key']}"}
    return out


def field_ids(recorder):
    """Map our logical field names to JIRA custom field ids, by field name."""
    fields = json.loads(http_get(API + "/field", recorder=recorder))
    by_name = {f.get("name"): f.get("id") for f in fields}
    return {logical: by_name.get(name) for logical, name in FIELD_NAMES.items()}


def normalize(issue, ids, remotelinks):
    f = issue.get("fields", {})

    def custom(logical):
        fid = ids.get(logical)
        return f.get(fid) if fid else None

    comments = (f.get("comment") or {}).get("comments", [])
    return {
        "key": issue.get("key"),
        "url": f"{BASE}/browse/{issue.get('key')}",
        "summary": f.get("summary") or "",
        "description": f.get("description") or "",
        "status": (f.get("status") or {}).get("name"),
        "resolution": (f.get("resolution") or {}).get("name") if f.get("resolution") else None,
        "issuetype": (f.get("issuetype") or {}).get("name"),
        "components": _names(f.get("components")),
        "fix_versions": _names(f.get("fixVersions")),
        "since_versions": _names(custom("since_versions")),
        "reviewers": _users(custom("reviewers")),
        "authors": _users(custom("authors")),
        "assignee": _users(f.get("assignee")),
        "test_doc_plan": _text(custom("test_doc_plan")),
        "impacts": _names(custom("impacts")),
        "source_control_link": _text(custom("source_control_link")),
        "comments": [
            {
                "id": c.get("id"),
                "author": (c.get("author") or {}).get("name"),
                "display": (c.get("author") or {}).get("displayName"),
                "created": c.get("created"),
                "body": c.get("body") or "",
                "url": f"{BASE}/browse/{issue.get('key')}?focusedCommentId={c.get('id')}",
            }
            for c in comments
        ],
        "attachments": [
            {
                "id": a.get("id"),
                "filename": a.get("filename"),
                "size": a.get("size"),
                "created": a.get("created"),
                "author": (a.get("author") or {}).get("name"),
                "url": a.get("content"),
            }
            for a in f.get("attachment") or []
        ],
        "issuelinks": [_issuelink(link) for link in f.get("issuelinks") or []],
        "remotelinks": [
            {"title": (r.get("object") or {}).get("title"), "url": (r.get("object") or {}).get("url")}
            for r in remotelinks or []
        ],
    }


def fetch_ticket(key, recorder):
    """Return {"status": ok|not_found|unavailable, "ticket": {...}|None, "error": str|None}."""
    try:
        issue = json.loads(http_get(f"{API}/issue/{key}?fields=*all", recorder=recorder))
    except NetError as e:
        if e.status == 404:
            return {"status": "not_found", "ticket": None, "error": str(e)}
        return {"status": "unavailable", "ticket": None, "error": str(e)}
    try:
        ids = field_ids(recorder)
    except NetError as e:
        return {"status": "unavailable", "ticket": None, "error": f"field list: {e}"}
    try:
        links = json.loads(http_get(f"{API}/issue/{key}/remotelink", recorder=recorder))
    except NetError:
        links = []
    return {"status": "ok", "ticket": normalize(issue, ids, links), "error": None}
