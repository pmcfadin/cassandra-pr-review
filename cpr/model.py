"""Build and validate the report model: the one JSON object the HTML template renders."""

import time

from cpr import VERSION, paths
from cpr.checks import STATUSES
from cpr.checks.compat import touched_surfaces
from cpr.merge import issues_of
from cpr.recommend import VERDICTS, recommend

MODEL_SCHEMA = 1
SEVERITIES = ("blocker", "major", "minor", "nit")
SEVERITY_ORDER = {s: i for i, s in enumerate(SEVERITIES)}

# Report sections in nav order: (id, title, aspect docs embedded, check aspects shown).
SECTIONS = [
    ("summary", "Summary", ["summary"], []),
    ("ticket", "JIRA ticket", ["jira"], ["jira"]),
    ("ci", "Branches & CI", ["ci", "branches"], ["ci", "branches"]),
    ("testing", "Testing", ["testing"], ["testing"]),
    ("commits", "Commits & changelog", ["commits"], ["commits"]),
    ("static", "Code style", ["static"], ["static"]),
    ("compatibility", "Compatibility", ["compatibility"], ["compatibility"]),
    ("votes", "Reviews & votes", ["votes"], ["votes"]),
    ("triage", "Triage", ["triage"], []),
    ("context", "Context", ["context"], []),
    ("review", "Code review", ["code-review"], []),
    ("changes", "Changes", ["changes"], []),
    ("about", "About", [], []),
]
ASPECTS = sorted({a for _, _, docs, _ in SECTIONS for a in docs})

NOT_CHECKED = [
    "`ant check` (checkstyle and RAT) was not run; the static checks here approximate it from the diff.",
    "No tests were built or run; CI evidence comes only from summaries attached to JIRA.",
    "CI failures are counted, not compared against known flaky tests (Butler) yet.",
    "Code review lenses read the diff; they do not build or run tests.",
]
HUMAN_ONLY = [
    "Whether the design and approach are acceptable.",
    "Backport scope: which branches should get the fix.",
    "Whether a new dependency or public API change has dev@ consensus.",
    "The final merge decision.",
]

_RANK = {"fail": 0, "unknown": 1, "warn": 2, "pass": 3}


def _file_kind(path):
    if paths.is_test_resource(path):
        return "test-resource"
    if paths.is_test(path):
        return "test"
    if paths.is_generated(path):
        return "generated"
    if paths.is_prod(path):
        return "production"
    if paths.is_doc(path):
        return "doc"
    if paths.is_build(path):
        return "build"
    return "other"


class ModelError(Exception):
    pass


def section_status(checks):
    statuses = [c["status"] for c in checks if c["status"] != "not-applicable"]
    if not statuses:
        return "info"
    return min(statuses, key=lambda s: _RANK[s])


def _branch_rows(bundle):
    by_branch = {}
    for s in bundle["ci"]["summaries"]:
        if s.get("parse_status") == "ok" and s.get("target_branch"):
            prev = by_branch.get(s["target_branch"])
            if prev is None or (s.get("created") or "") > (prev.get("created") or ""):
                by_branch[s["target_branch"]] = s
    rows = []
    for sib in sorted(bundle.get("siblings", []), key=lambda s: (s["base"] != "trunk", s["base"])):
        ci = by_branch.get(sib["base"])
        rows.append({
            "branch": sib["base"], "pr_number": sib["number"], "pr_url": sib["url"], "title": sib["title"],
            "is_self": sib.get("is_self", False), "state": sib["state"], "draft": sib.get("draft", False),
            "head_sha": sib["head_sha"],
            "ci": None if not ci else {
                "attachment": ci["attachment"], "url": ci.get("url"), "created": ci.get("created"),
                "sha": ci.get("sha"), "sha_matches": bool(ci.get("sha")) and ci.get("sha") == sib["head_sha"],
                "passed": ci.get("passed"), "failed": ci.get("failed"), "skipped": ci.get("skipped"),
                "total": ci.get("total"), "overall": ci.get("overall"),
                "has_upgrade_tests": ci.get("has_upgrade_tests"), "failures": ci.get("failures", [])[:50],
            },
        })
    rows.sort(key=lambda r: ["cassandra-4.0", "cassandra-4.1", "cassandra-5.0", "cassandra-6.0", "trunk"].index(r["branch"])
              if r["branch"] in ("cassandra-4.0", "cassandra-4.1", "cassandra-5.0", "cassandra-6.0", "trunk") else 99)
    unmapped = [{"attachment": s["attachment"], "url": s.get("url"), "parse_status": s.get("parse_status"),
                 "error": s.get("error"), "ref": s.get("ref")}
                for s in bundle["ci"]["summaries"] if s.get("parse_status") != "ok" or not s.get("target_branch")]
    return rows, unmapped


def build(bundle, checks, triage, docs, diffview, review=None, context=None):
    """Assemble the report model. `review` is None until review lenses exist."""
    pr = bundle["pr"]
    ticket = (bundle.get("jira") or {}).get("ticket")
    rec = recommend(pr, checks, review)
    branches, unmapped = _branch_rows(bundle)

    sections = []
    for sid, title, doc_aspects, check_aspects in SECTIONS:
        sec_checks = [c for c in checks if c["aspect"] in check_aspects]
        status = section_status(sec_checks)
        if sid == "summary":
            status = {"needs-contributor-work": "fail", "needs-work": "warn", "insufficient-evidence": "unknown",
                      "awaiting-review": "info", "requirements-met-unreviewed": "pass", "ready": "pass",
                      "draft": "info"}[rec["verdict"]]
        elif sid == "review":
            if review is None or not review.get("complete"):
                status = "unknown"
            elif any(i["severity"] in ("blocker", "major") for i in issues_of(review)):
                status = "fail"
            elif any(l["findings"] for l in review["lenses"]):
                status = "warn"
            else:
                status = "pass"
        elif sid == "context":
            status = "info" if context and context.get("status") == "ok" else "unknown"
        elif sid == "changes":
            status = "info" if diffview.get("status") == "ok" else "unknown"
        sections.append({"id": sid, "title": title, "status": status, "docs": doc_aspects,
                         "checks": [c["id"] for c in sec_checks]})

    model = {
        "schema": MODEL_SCHEMA,
        "generated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "tool": {"name": "cassandra-pr-review", "version": VERSION},
        "pr": {k: pr.get(k) for k in ("number", "url", "title", "body", "author", "author_association", "base",
                                      "head_ref", "head_repo", "head_sha", "draft", "state", "labels",
                                      "created_at", "updated_at", "additions", "deletions", "changed_files")},
        "jira_key": bundle["jira_key"],
        "jira": {
            "status": bundle["jira"]["status"], "error": bundle["jira"].get("error"),
            "ticket": None if not ticket else {
                **{k: ticket[k] for k in ("key", "url", "summary", "status", "resolution", "issuetype", "components",
                                          "fix_versions", "since_versions", "reviewers", "authors", "assignee",
                                          "test_doc_plan", "impacts")},
                "description": ticket["description"][:4000],
                "comments": ticket["comments"][-10:],
                "comment_count": len(ticket["comments"]),
            },
        },
        "branches": branches,
        "ci_unmapped": unmapped,
        "ci_archives": bundle["ci"].get("result_archives", []),
        "commits": [{"sha": c["sha"], "message": c["message"], "author_name": c["author_name"],
                     "login": c["login"], "trailers": c["trailers"],
                     "url": f"{pr['url']}/commits/{c['sha']}" if pr.get("url") else None} for c in bundle["commits"]],
        "files": [{**{k: f.get(k) for k in ("path", "previous_path", "status", "additions", "deletions", "binary")},
                   "kind": _file_kind(f["path"]), "suite": paths.test_suite(f["path"])}
                  for f in bundle["files"]],
        "compat_surfaces": touched_surfaces([f["path"] for f in bundle["files"]]),
        "checks": checks,
        "recommendation": rec,
        "triage": triage,
        "review": review or {"status": "not-run", "lenses": []},
        "context": context or {"status": "unavailable", "reason": "Reviewer context was not computed."},
        "github_reviews": [{k: r.get(k) for k in ("user", "state", "association", "submitted_at", "url")}
                           for r in bundle.get("reviews", [])],
        "sections": sections,
        "docs": docs,
        "diffview": diffview,
        "about": {
            "not_checked": NOT_CHECKED,
            "human_only": HUMAN_ONLY,
            "inputs": {
                "fetched_at": bundle["meta"]["fetched_at"],
                "head_sha": pr["head_sha"],
                "merge_base": bundle["git"]["merge_base"],
                "jira_status": bundle["jira"]["status"],
                "roster_status": (bundle.get("roster") or {}).get("status"),
                "ide_explain_version": diffview.get("version"),
            },
        },
    }
    validate(model)
    return model


def validate(model):
    """Raise ModelError naming the first invalid field."""

    def need(cond, field):
        if not cond:
            raise ModelError(f"invalid report model: {field}")

    need(model.get("schema") == MODEL_SCHEMA, "schema")
    pr = model.get("pr") or {}
    need(isinstance(pr.get("number"), int), "pr.number")
    need(isinstance(pr.get("title"), str), "pr.title")
    need(isinstance(pr.get("head_sha"), str) and len(pr["head_sha"]) == 40, "pr.head_sha")
    for i, c in enumerate(model.get("checks", [])):
        need(c.get("status") in STATUSES, f"checks[{i}].status")
        need(isinstance(c.get("id"), str), f"checks[{i}].id")
        need(isinstance(c.get("evidence"), list), f"checks[{i}].evidence")
    rec = model.get("recommendation") or {}
    need(rec.get("verdict") in VERDICTS, "recommendation.verdict")
    need((model.get("triage") or {}).get("rating") in ("easy", "moderate", "hard"), "triage.rating")
    for i, lens in enumerate(model["review"].get("lenses", [])):
        need(isinstance(lens.get("name"), str), f"review.lenses[{i}].name")
        need(lens.get("status") in ("ran", "missing", "invalid"), f"review.lenses[{i}].status")
        for j, f in enumerate(lens.get("findings", [])):
            for k in ("id", "severity", "location", "rule", "problem", "fix"):
                need(isinstance(f.get(k), str), f"review.lenses[{i}].findings[{j}].{k}")
            need(f["severity"] in SEVERITIES, f"review.lenses[{i}].findings[{j}].severity")
            for k in ("impact", "confidence"):
                need(f.get(k) is None or isinstance(f[k], str), f"review.lenses[{i}].findings[{j}].{k}")
    issues = model["review"].get("issues")
    need(issues is None or isinstance(issues, list), "review.issues")
    for i, issue in enumerate(issues or []):
        for k in ("id", "rule", "problem", "fix", "location"):
            need(isinstance(issue.get(k), str), f"review.issues[{i}].{k}")
        need(issue.get("severity") in SEVERITIES, f"review.issues[{i}].severity")
        need(isinstance(issue.get("lenses"), list) and issue["lenses"], f"review.issues[{i}].lenses")
        need(isinstance(issue.get("locations"), list), f"review.issues[{i}].locations")
        need(isinstance(issue.get("members"), list) and issue["members"], f"review.issues[{i}].members")
        need(isinstance(issue.get("also_fixes", []), list), f"review.issues[{i}].also_fixes")
        for k in ("impact", "confidence"):
            need(issue.get(k) is None or isinstance(issue[k], str), f"review.issues[{i}].{k}")
    for s in model.get("sections", []):
        for a in s["docs"]:
            need(isinstance(model["docs"].get(a), str), f"docs.{a}")
    need(model.get("diffview", {}).get("status") in ("ok", "unavailable"), "diffview.status")
    ctx = model.get("context") or {}
    need(ctx.get("status") in ("ok", "unavailable"), "context.status")
    if ctx.get("status") == "ok":
        for k in ("related_tickets", "untracked_commits", "linked_issues", "suggested_reviewers", "already_reviewing"):
            need(isinstance(ctx.get(k), list), f"context.{k}")
        need(isinstance(ctx.get("experts"), dict), "context.experts")
