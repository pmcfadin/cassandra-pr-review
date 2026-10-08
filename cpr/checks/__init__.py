"""Requirement checks: a registry of small pure functions over the evidence bundle.

Each check returns a result dict:

    id, title, category, aspect, blocking, status, summary, evidence, action, action_required, owner

`status` is one of pass, fail, warn, unknown, not-applicable. `evidence` is a list of
{"text", "url"?, "location"?}. `action` says what to do when not passing; `owner` says who acts
(contributor, reviewer, committer). A warn with action_required False is shown but does not move
the recommendation.
"""

STATUSES = ("pass", "fail", "warn", "unknown", "not-applicable")
CATEGORIES = ("ticket", "ci", "commit", "changelog", "tests", "build", "static", "compatibility", "governance")
OWNERS = ("contributor", "reviewer", "committer")

REGISTRY = []


def check(id, title, category, aspect, blocking, owner="contributor"):
    assert category in CATEGORIES, category
    assert owner in OWNERS, owner

    def wrap(fn):
        REGISTRY.append({"id": id, "title": title, "category": category, "aspect": aspect,
                         "blocking": blocking, "owner": owner, "fn": fn})
        return fn

    return wrap


def ev(text, url=None, location=None):
    e = {"text": text}
    if url:
        e["url"] = url
    if location:
        e["location"] = location
    return e


class Result:
    """Return value of a check function; the registry metadata is merged in by run_all."""

    def __init__(self, status, summary, evidence=None, action=None, action_required=None, blocking=None):
        assert status in STATUSES, status
        self.status = status
        self.summary = summary
        self.evidence = evidence or []
        self.action = action
        self.action_required = action_required
        self.blocking = blocking


def run_all(bundle, ctx=None):
    # Import the check modules so they register themselves.
    from cpr.checks import ticket, ci, commits, tests_presence, build, static, compat, votes  # noqa: F401

    ctx = ctx or Context(bundle)
    results = []
    for spec in REGISTRY:
        try:
            r = spec["fn"](bundle, ctx)
        except Exception as e:  # a broken check must never pass silently
            r = Result("unknown", f"check crashed: {type(e).__name__}: {e}")
        results.append({
            "id": spec["id"],
            "title": spec["title"],
            "category": spec["category"],
            "aspect": spec["aspect"],
            "blocking": spec["blocking"] if r.blocking is None else r.blocking,
            "owner": spec["owner"],
            "status": r.status,
            "summary": r.summary,
            "evidence": r.evidence,
            "action": r.action if r.status not in ("pass", "not-applicable") else None,
            "action_required": (r.status in ("fail", "warn")) if r.action_required is None else r.action_required,
        })
    return results


def registered_ids():
    from cpr.checks import ticket, ci, commits, tests_presence, build, static, compat, votes  # noqa: F401
    return [(c["id"], c["aspect"]) for c in REGISTRY]


class Context:
    """Derived views of the bundle shared by several checks."""

    def __init__(self, bundle):
        from cpr import diffparse
        self.bundle = bundle
        self.files = bundle.get("files", [])
        self.paths = [f["path"] for f in self.files]
        self.added = diffparse.parse(bundle.get("diff", ""))
        self.key = (bundle.get("jira_key") or {}).get("key")
        self.ticket = (bundle.get("jira") or {}).get("ticket")
        self.jira_status = (bundle.get("jira") or {}).get("status")
        self.pr = bundle["pr"]

    def targeted_branches(self):
        """Base branches this patch targets: this PR plus open sibling PRs, one per branch."""
        out = {}
        for s in self.bundle.get("siblings", []):
            if s.get("is_self") or s.get("state") == "open":
                out.setdefault(s["base"], s)
        return out
