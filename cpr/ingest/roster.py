"""The Cassandra committer roster, derived from the public ASF LDAP data on whimsy.apache.org."""

import json
import os
import time

from cpr.net import NetError, http_get

PROJECTS_URL = "https://whimsy.apache.org/public/public_ldap_projects.json"
PEOPLE_URL = "https://whimsy.apache.org/public/public_ldap_people.json"
MAX_AGE_SECONDS = 24 * 3600
OVERRIDES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "committer-overrides.json")


def load_overrides(path=OVERRIDES):
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        return {"github": {}, "jira": {}}
    return {"github": data.get("github", {}), "jira": data.get("jira", {})}


def _fetch():
    projects = json.loads(http_get(PROJECTS_URL))
    cassandra = projects["projects"]["cassandra"]
    people = json.loads(http_get(PEOPLE_URL)).get("people", {})
    members = sorted(cassandra.get("members", []))
    return {
        "source": PROJECTS_URL,
        "fetched_at": int(time.time()),
        "committers": {m: (people.get(m) or {}).get("name") or m for m in members},
        "pmc": sorted(cassandra.get("owners", [])),
    }


def load(cache_path, offline=False, now=None, fetch=_fetch):
    """Return {"status": ok|stale|unavailable, "roster": {...}|None, "error": str|None}.

    A cached roster younger than 24 hours is used as is. Offline, any cached roster is used.
    When a refresh fails, an older cached roster is used and marked stale.
    """
    now = now or time.time()
    cached = None
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            cached = json.load(f)
    if cached and (offline or now - cached["fetched_at"] < MAX_AGE_SECONDS):
        return {"status": "ok", "roster": cached, "error": None}
    if offline:
        return {"status": "unavailable", "roster": None, "error": "offline and no cached roster"}
    try:
        fresh = fetch()
    except (NetError, KeyError, ValueError) as e:
        if cached:
            return {"status": "stale", "roster": cached, "error": str(e)}
        return {"status": "unavailable", "roster": None, "error": str(e)}
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(fresh, f)
    return {"status": "ok", "roster": fresh, "error": None}
