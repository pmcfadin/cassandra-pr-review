"""Build and validate the report model: the one JSON object the HTML template renders."""

import re
import time

from cpr import VERSION, buildresult, labplan, paths
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
    ("build", "Build & coverage", ["build"], ["build"]),
    ("labplan", "Lab plan", ["labplan"], []),
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
    "Tests are built and run only for committers' PRs (or a PR the owner approved) and only a selection of unit "
    "tests; otherwise CI evidence comes only from summaries attached to JIRA.",
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
    lab_plan = labplan.build_plan(bundle)
    run = bundle.get("build")
    if not (isinstance(run, dict) and run.get("head") == pr["head_sha"] and run.get("status") != "not-built"):
        run = buildresult.not_built(run.get("reason") if isinstance(run, dict) and run.get("status") == "not-built" else None)
    run = {**run, "author_is_committer": buildresult.author_is_committer(bundle)}

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
        elif sid == "build":
            if run["status"] == "not-built":
                status = "not-applicable"
            elif status == "info":
                status = "unknown" if run["status"] in ("unknown", "timeout") else "info"
        elif sid == "labplan":
            status = "info" if lab_plan["status"] == "plan" else "not-applicable"
        sec = {"id": sid, "title": title, "status": status, "docs": doc_aspects, "checks": [c["id"] for c in sec_checks]}
        if sid == "labplan":
            sec["summary"] = labplan.section_summary(lab_plan)
        sections.append(sec)

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
        "lab_plan": lab_plan,
        "build": run,
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
    model["view"] = derive_view(model)
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
            for k in ("impact", "confidence", "title"):
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
        for k in ("impact", "confidence", "title"):
            need(issue.get(k) is None or isinstance(issue[k], str), f"review.issues[{i}].{k}")
    for s in model.get("sections", []):
        for a in s["docs"]:
            need(isinstance(model["docs"].get(a), str), f"docs.{a}")
    lp = model.get("lab_plan") or {}
    need(lp.get("status") in ("plan", "none"), "lab_plan.status")
    need(isinstance(lp.get("markdown"), str), "lab_plan.markdown")
    need(isinstance(lp.get("scenarios"), list), "lab_plan.scenarios")
    need(lp["status"] == "none" or (lp["markdown"] and lp["scenarios"] and isinstance(lp.get("filename"), str)),
         "lab_plan.markdown")
    need(lp["status"] == "plan" or isinstance(lp.get("reason"), str), "lab_plan.reason")
    if "build" in model:
        need((model["build"] or {}).get("status") in buildresult.STATUSES, "build.status")
    need(model.get("diffview", {}).get("status") in ("ok", "unavailable"), "diffview.status")
    view = model.get("view")
    if view is not None:
        need(isinstance(view, dict), "view")
        need((view.get("verdict") or {}).get("kind") in ("blocked", "waiting", "ready", "unknown", "draft"), "view.verdict.kind")
        need(isinstance(view.get("steps"), list), "view.steps")
        need(isinstance((view.get("todo") or {}).get("roles"), list), "view.todo.roles")
        need(isinstance(view.get("groups"), list), "view.groups")
        need(isinstance(view.get("words"), dict), "view.words")
    ctx = model.get("context") or {}
    need(ctx.get("status") in ("ok", "unavailable"), "context.status")
    if ctx.get("status") == "ok":
        for k in ("related_tickets", "untracked_commits", "linked_issues", "suggested_reviewers", "already_reviewing"):
            need(isinstance(ctx.get(k), list), f"context.{k}")
        need(isinstance(ctx.get("experts"), dict), "context.experts")


# ---------------------------------------------------------------------------------------------
# Derived view fields. Pure functions of the model above; they change no check or verdict, they
# only phrase the existing facts for the report's layout (design D1 and D2 of report-redesign).
# ---------------------------------------------------------------------------------------------

WORD_FAIL, WORD_SHOULD, WORD_NOTE = "Must fix", "Should fix", "Note"
WORD_UNKNOWN, WORD_PASS, WORD_NA = "Unknown", "Passed", "Not needed"
_GROUP_RANK = {"fail": 0, "warn": 1, "unknown": 2, "pass": 3, "not-applicable": 4, "info": 4}
ROLE_ORDER = ("contributor", "committer", "reviewer", "other")
ROLE_NAMES = {"contributor": "Contributor", "committer": "Committer", "reviewer": "Reviewers", "other": "Other"}


def status_word(status, action_required=False):
    """The plain word for a check status: fail is Must fix, warn is Should fix only when action is required."""
    if status == "fail":
        return WORD_FAIL
    if status == "warn":
        return WORD_SHOULD if action_required else WORD_NOTE
    if status == "pass":
        return WORD_PASS
    if status == "not-applicable":
        return WORD_NA
    return WORD_UNKNOWN


def first_sentence(text, limit=150):
    """First sentence or clause of `text`, cut at a word boundary under `limit` characters."""
    s = " ".join(str(text or "").split())
    m = re.search(r"(?<!e\.g)(?<!i\.e)(?<!etc)(?<!vs)\. ", s)  # "e.g. foo" does not end a sentence
    if m and m.start() > 0:
        s = s[:m.start()]
    s = s.rstrip(".:;")
    if len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0]
        if s.count("`") % 2:  # never cut inside an inline-code span
            s = s[:s.rindex("`")]
        s = s.rstrip(" ,;:") + "…"
    return s


def _plural(n, word, many=None):
    return f"{n} {word if n == 1 else many or word + 's'}"


def _check_rank(c):
    return {"fail": 0, "unknown": 1, "warn": 2, "pass": 3, "not-applicable": 4}.get(c["status"], 1)


def _issue_counts_text(ic):
    parts = [(ic[k], k) for k in ("blocker", "major", "minor", "nit") if ic.get(k)]
    if not parts:
        return "No issues found."
    bits = [f"{n} {k}" for n, k in parts]
    text = bits[0] if len(bits) == 1 else ", ".join(bits[:-1]) + " and " + bits[-1]
    return text + (" issue found." if len(bits) == 1 and parts[0][0] == 1 else " issues found.")


def _group_summary(sec, cs, review):
    if sec["id"] == "review":
        if review.get("status") != "ran":
            return "Code review has not run for this PR."
        return _issue_counts_text(review.get("issue_counts") or {})
    live = sorted((c for c in cs if c["status"] in ("fail", "unknown", "warn")), key=_check_rank)
    if live:
        return live[0]["summary"] or live[0]["title"]
    passed = [c for c in cs if c["status"] == "pass"]
    if passed:
        return "All checks passed." if len(passed) == len(cs) else f"{_plural(len(passed), 'check')} passed; the rest are not needed."
    return "Nothing to check for this change."


def _derive_groups(model, by_id):
    review = model.get("review") or {}
    groups = []
    for sec in model["sections"]:
        cs = [by_id[i] for i in sec.get("checks", []) if i in by_id]
        if not cs and sec["id"] != "review":
            continue
        status = "not-applicable" if sec["status"] == "info" else sec["status"]
        if sec["id"] == "review":
            word = {"fail": WORD_FAIL, "warn": WORD_NOTE, "pass": WORD_PASS}.get(status, WORD_UNKNOWN)
            count = _plural(len(review.get("issues") or []), "finding") if review.get("status") == "ran" else "not run"
        else:
            word = status_word(status, any(c["status"] == "warn" and c.get("action_required") for c in cs))
            open_n = sum(1 for c in cs if c["status"] in ("fail", "warn", "unknown"))
            passed = sum(1 for c in cs if c["status"] == "pass")
            count = (f"{open_n} open · " if open_n else "") + (
                f"{passed} passed" if passed or open_n else f"{_plural(len(cs), 'check')} not needed")
        groups.append({"id": sec["id"], "title": sec["title"], "status": status, "word": word,
                       "summary": _group_summary(sec, cs, review), "count_label": count,
                       "is_review": sec["id"] == "review"})
    groups.sort(key=lambda g: _GROUP_RANK.get(g["status"], 2))  # stable: ties keep section order
    return groups


def _derive_steps(model, groups):
    g = {x["id"]: x for x in groups}

    def step(label, ids, note_ok):
        gs = [g[i] for i in ids if i in g]
        bad = [x for x in gs if x["status"] == "fail"]
        unk = [x for x in gs if x["status"] == "unknown"]
        if bad:
            return {"label": label, "state": "bad", "note": bad[0]["summary"]}
        if unk:
            return {"label": label, "state": "unknown", "note": unk[0]["summary"]}
        return {"label": label, "state": "ok", "note": note_ok}

    steps = [step("Ticket", ["ticket"], "Ticket checks pass"), step("Tests", ["testing", "build"], "Tests accompany the change"),
             step("Code review", ["review"], "No must-fix review issues"), step("CI", ["ci"], "CI is in order")]
    votes = step("+1 votes", ["votes"], "Enough committer +1 votes")
    have, need = _votes(model)
    if have is not None:
        votes["label"] = f"+1 votes ({have} of {need if need is not None else 2})"
    steps.append(votes)
    return steps


def _role_of(owner):
    return owner if owner in ROLE_ORDER[:3] else "other"


# --- To do: fixes (the contributor changes something) and steps (later merge work) -------------------

# Pairs of (check section ids, regexes on a finding). A must-fix code review finding that matches takes over
# the failing check's to-do item. Add rows here to pair more checks with findings.
_TEST_ASK = (re.compile(r"\b(adds?|changes?|has|have|with)\s+(or\s+\w+\s+)?no\s+(regression |unit |new )?(tests?|dtests?)\b"
                        r"|\bregression test\b|\bunit test\b|\bdtests?\b|\b(lacks?|missing)\s+(a\s+)?(regression |unit )?tests?\b", re.I),
             re.compile(r"^\s*(add|write|include|extend)\b[^.]{0,80}?\b[A-Za-z]*tests?\b", re.I))
PAIRS = (({"testing", "build"}, _TEST_ASK),)

# Plain titles and verdict-sentence phrases for the merge steps that come after the contributor's fixes.
_CI_STEP = ("Run pre-commit CI on each target branch", "a committer runs CI")
ASK_REVIEW = "Ask for review on the JIRA ticket or the dev@ list"
_NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four"}


def _votes(model):
    """(have, need) committer +1 votes read from the votes check summary, or (None, None)."""
    vc = next((c for c in model["checks"] if c["id"] == "votes.committer-plus-ones"), None)
    summary = (vc or {}).get("summary") or ""
    have = re.search(r"\bhas (\d+)\b|^(\d+) committer", summary)
    need = re.search(r"needs (\d+)", summary)
    return (int(have.group(1) or have.group(2)) if have else None, int(need.group(1)) if need else None)


def humanize_rule(rule, limit=90):
    """A rule name as a label. Slugs ("test-rigor") become words; a rule that is a sentence is kept whole.

    Only when it is longer than `limit` is a trailing parenthetical dropped, then everything after the colon;
    it is cut at a word boundary only as a last resort.
    """
    r = " ".join(str(rule or "").split())
    if " " not in r:
        r = re.sub(r"[_-]+", " ", r)
    if len(r) > limit:
        r = re.sub(r"\s*\([^()]*\)\s*$", "", r)
    if len(r) > limit and ":" in r:
        r = r.split(":", 1)[0].strip()
    if len(r) > limit:
        r = r[:limit].rsplit(" ", 1)[0].rstrip(" ,;:") + "\u2026"
    return r[:1].upper() + r[1:]


def short_location(loc):
    """`File.java:123` from `path/to/File.java:123 (note)`; the plain text when it names no file."""
    m = re.search(r"([^/\s:()]+):(\d+)", str(loc or ""))
    if m:
        return f"{m.group(1)}:{m.group(2)}"
    m = re.search(r"([^/\s:()]+\.\w+)", str(loc or ""))
    return m.group(1) if m else " ".join(str(loc or "").split())


def finding_title(issue):
    """The lens's title, else the humanized rule and the short location."""
    t = " ".join(str(issue.get("title") or "").split())
    if t and len(t) <= 80:
        return t
    rule, loc = humanize_rule(issue.get("rule")), short_location(issue.get("location"))
    return f"{rule} — {loc}" if rule and loc else rule or loc or "Code review finding"


def _paired(check_section, issue):
    for sections, (problem_re, fix_re) in PAIRS:
        if check_section in sections and (problem_re.search(issue.get("problem") or "") or fix_re.search(issue.get("fix") or "")):
            return True
    return False


def _item(**kw):
    base = {"must": True, "kind": "fix", "word": WORD_FAIL, "title": "", "summary": "", "action": "", "owner": "other",
            "check": None, "finding": None, "issue": None, "source": "Check", "tag": "", "location": "", "also": "",
            "who": "", "phrase": "", "requested": False}
    base.update(kw)
    base["text"] = base["title"]
    return base


def _derive_todo(model, by_id):
    rec = model["recommendation"]
    section_of = {cid: sec["id"] for sec in model["sections"] for cid in sec.get("checks", [])}
    all_issues = (model.get("review") or {}).get("issues") or []
    issues = {i["members"][0]["id"]: i for i in all_issues if i.get("members")}
    have, need = _votes(model)
    items, seen = [], set()

    def check_item(c, must, status, reason=None):
        r = reason or {}
        cid = c["id"]
        kw = dict(must=must, word=status_word(status, c.get("action_required")), owner=_role_of(r.get("owner") or c.get("owner")),
                  summary=r.get("summary") or c.get("summary") or "", action=r.get("action") or c.get("action") or "", check=cid)
        title = first_sentence(kw["action"], 220) or c["title"]
        if cid == "ci.evidence":
            kw.update(kind="step", title=_CI_STEP[0], phrase=_CI_STEP[1])
        elif cid == "votes.committer-plus-ones":
            left = max((need if need is not None else 2) - (have or 0), 1)
            n = _NUMBER_WORDS.get(left, str(left))
            kw.update(kind="step", title=f"Collect {n} committer +1 vote{'' if left == 1 else 's'}",
                      phrase=f"{n} committer{'' if left == 1 else 's'} vote{'s' if left == 1 else ''}")
        elif kw["owner"] != "contributor":
            kw.update(kind="step", title=title, phrase=title[:1].lower() + title[1:])
        else:
            kw.update(title=title)
        return _item(**kw)

    for r in rec.get("reasons", []):
        if r.get("status") == "pass":
            continue
        c = by_id.get(r.get("check")) if r.get("check") else None
        must = bool(r.get("blocking")) or r.get("status") in ("fail", "unknown")
        if c:
            seen.add(c["id"])
            items.append(dict(check_item(c, must, r["status"], r), requested=True))
        elif r.get("finding"):
            iss = issues.get(r["finding"]) or {}
            items.append(_item(requested=True, owner=_role_of(r.get("owner")), title=finding_title(iss or r), summary=iss.get("problem") or r.get("summary") or "",
                               action=iss.get("fix") or r.get("action") or "", finding=r["finding"], issue=iss.get("id"), source="Code review",
                               location=short_location(iss.get("location") or r.get("location")), tag=f"Code review · {r.get('severity', '')}".strip(" ·")))
        else:
            items.append(_item(must=must, word=WORD_UNKNOWN if r["status"] == "unknown" else WORD_NOTE, owner=_role_of(r.get("owner")),
                               title=r.get("title") or "", summary=r.get("summary") or "", source="Note", tag="Note"))
    for c in model["checks"]:
        if c["id"] in seen or c["status"] not in ("fail", "warn", "unknown"):
            continue
        items.append(check_item(c, False, c["status"]))

    # One item per need: a finding that asks for what a failing check asks for takes that check's item.
    for it in [i for i in items if i["source"] == "Code review"]:
        issue = next((x for x in all_issues if x["id"] == it["issue"]), None)
        if not issue:
            continue
        for dup in [d for d in items if d["check"] and d["kind"] == "fix" and d["must"] and _paired(section_of.get(d["check"]), issue)]:
            it["also"] = it["also"] or by_id[dup["check"]]["title"]
            it["also_check"] = dup["check"]
            items.remove(dup)

    votes = by_id.get("votes.committer-plus-ones")
    if votes and votes["status"] != "pass" and rec.get("verdict") not in ("ready", "draft"):
        items.append(_item(kind="step", owner="contributor", title=ASK_REVIEW, phrase="the contributor asks for review", must=True,
                           word=WORD_UNKNOWN, summary="A committer cannot vote on a patch nobody has asked them to read.",
                           check=votes["id"], source="Check"))

    ctx = model.get("context") or {}
    sug = [p.get("name") for p in (ctx.get("suggested_reviewers") or []) if p.get("name")]
    votes_text = f"+1 votes: {have} of {need if need is not None else 2}" if have is not None else ""
    names = ", ".join(sug[:3]) + (f" and {len(sug) - 3} more" if len(sug) > 3 else "")
    who = {"contributor": model["pr"].get("author") or "", "committer": "Any Cassandra committer",
           "reviewer": " · ".join(x for x in (("Suggested: " + names) if sug else "", votes_text) if x), "other": ""}
    for n, it in enumerate(items):
        it["id"] = f"todo-{n}"
        it["who"] = who[it["owner"]]
        it["tag"] = it["tag"] or it["source"]

    # A fix is a contributor change the verdict asked for: a must-fix, or a should-fix the verdict lists.
    fixes = [i for i in items if i["kind"] == "fix" and i["owner"] == "contributor" and (i["must"] or i["requested"])]
    must_fixes = [i for i in fixes if i["must"]]
    if fixes:
        now_role = "contributor"
        for i in items:
            i["phase"] = "now" if i["kind"] == "fix" and i["owner"] == "contributor" else "then"
    else:
        now_role = next((r for r in ROLE_ORDER if any(i["owner"] == r and i["must"] for i in items)), None)
        for i in items:
            i["phase"] = "now" if i["owner"] == now_role and (i["must"] or i["kind"] == "fix") else "then"
    now_items = sorted((i for i in items if i["phase"] == "now"), key=lambda i: not i["must"])  # must first, then stable
    then_items = sorted((i for i in items if i["phase"] == "then"), key=lambda i: (ROLE_ORDER.index(i["owner"]), not i["must"]))
    for i in then_items:
        i["role"] = ROLE_NAMES[i["owner"]]
    roles = []
    if now_items:
        roles.append({"id": now_role, "role": ROLE_NAMES[now_role], "who": who[now_role], "phase": "now",
                      "must_count": len(must_fixes), "fix_count": len(fixes), "items": now_items})
    return {"roles": roles, "then": then_items, "now_role": now_role, "fix_count": len(fixes), "must_count": len(must_fixes),
            "optional_count": sum(1 for i in items if not i["must"])}


def _join(parts):
    parts = [p for p in parts if p]
    if len(parts) < 2:
        return parts[0] if parts else ""
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _cap(s):
    return s[:1].upper() + s[1:]


def _next_steps(todo):
    """What comes after the contributor's fixes (or, with no fixes, what the first role does and then who follows)."""
    lead = todo["fix_count"] > 0
    now = [] if lead or not todo["roles"] else [i["phrase"] for i in todo["roles"][0]["items"] if i["kind"] == "step" and i["must"] and i["phrase"]]
    then = [i["phrase"] for i in todo["then"] if i["must"] and i["phrase"] and not (lead and i["owner"] == "contributor")]
    out = []
    if now:
        out.append(_cap(_join(now)) + ".")
    if then:
        out.append(("Then " + _join(then)) + "." if (lead or now) else _cap(_join(then)) + ".")
    return " ".join(out)


def _derive_verdict(model, todo):
    v = model["recommendation"]["verdict"]
    n = todo["fix_count"]
    steps = _next_steps(todo)
    out = {"kind": "waiting", "headline": "Waiting for review", "sentence": "", "note": "",
           "must_count": todo["must_count"], "fix_count": n, "people_count": 1 if n else 0}
    if v == "needs-contributor-work":
        out.update(kind="blocked", headline="Not ready to merge",
                   sentence=" ".join(x for x in (f"The contributor has {_plural(n, 'fix', 'fixes')} to make." if n else "", steps) if x))
    elif v == "needs-work":
        changes = n
        out.update(headline="Needs changes",
                   sentence=" ".join(x for x in (f"The contributor has {_plural(changes, 'change')} to make." if changes else "", steps) if x))
    elif v == "awaiting-review":
        out.update(headline="Waiting for review",
                   sentence=steps if steps else
                   "The contributor's part is done. What remains is with reviewers or committers: votes, CI runs, or both.")
    elif v == "requirements-met-unreviewed":
        out.update(headline="Not reviewed yet", sentence="Every merge requirement passes, but no review lens has read the code.",
                   note="Code review has not completed, so this is not a ready-to-merge verdict.")
    elif v == "insufficient-evidence":
        out.update(kind="unknown", headline="Cannot tell yet",
                   sentence="Some required inputs could not be read, so the tool cannot say whether the requirements are met.")
    elif v == "draft":
        out.update(kind="draft", headline="Draft", sentence="Early feedback only. This is not a merge decision.",
                   note="This PR is a draft. Treat everything here as early feedback.")
    else:
        out.update(kind="ready", headline="Ready to merge", sentence="A committer can merge it.",
                   note="Every blocking requirement passes and every code review lens approved. A committer makes the final call.")
    return out


def _effort_text(tr):
    lines, files = tr.get("lines"), tr.get("files")
    base = f"{_plural(lines, 'changed line')} in {_plural(files, 'file')}" if lines is not None and files is not None else ""
    if tr.get("forced_by"):
        return f"Rated hard because it {tr['forced_by']}." + (f" ({base})" if base else "")
    raised = [s["signal"] for s in tr.get("signals", []) if (s.get("points") or 0) > 0]
    text = base[:1].upper() + base[1:] if base else "Rated by its signals"
    return text + (". Raised by: " + ", ".join(raised) + "." if raised else ".")


def derive_view(model):
    """Fields the report layout needs, computed from the model alone (no check or verdict logic changes)."""
    by_id = {c["id"]: c for c in model["checks"]}
    groups = _derive_groups(model, by_id)
    todo = _derive_todo(model, by_id)
    tr = model.get("triage") or {}
    return {
        "header": {"first_time_contributor": model["pr"].get("author_association") in ("FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER")},
        "verdict": _derive_verdict(model, todo),
        "steps": _derive_steps(model, groups),
        "todo": todo,
        "groups": groups,
        "headlines": {i["id"]: first_sentence(i["problem"], 110) for i in (model.get("review") or {}).get("issues") or []},
        "words": {c["id"]: status_word(c["status"], c.get("action_required")) for c in model["checks"]},
        "effort": {"level": {"easy": 1, "moderate": 2, "hard": 3}.get(tr.get("rating"), 0), "text": _effort_text(tr)},
    }
