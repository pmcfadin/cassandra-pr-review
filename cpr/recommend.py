"""Turn check results and the code review result into one recommendation, with the reasons for it.

Who must act decides the verdict: contributor items come first because they are the only ones the
contributor can move; `awaiting-review` means the contributor's part is done.
"""

LABELS = {
    "draft": "Draft — early feedback only",
    "needs-contributor-work": "Needs contributor work",
    "needs-work": "Needs work — contributor fixes requested",
    "insufficient-evidence": "Insufficient evidence — some required inputs could not be read",
    "awaiting-review": "Awaiting review — contributor's part is done",
    "requirements-met-unreviewed": "Requirements met — code not yet reviewed",
    "ready": "Ready to merge",
}
VERDICTS = tuple(LABELS)


def _reason(c):
    return {"check": c["id"], "finding": None, "title": c["title"], "status": c["status"], "summary": c["summary"],
            "action": c.get("action"), "owner": c.get("owner"), "blocking": c["blocking"]}


def _finding_reason(lens, f):
    return {"check": None, "finding": f["id"], "title": f"[{f['severity']}] {lens}: {f['rule']}", "status": "fail",
            "summary": f"{f['location']} — {f['problem']}", "action": f.get("fix"), "owner": "contributor",
            "blocking": True}


def _note(title, summary, owner, status="info"):
    return {"check": None, "finding": None, "title": title, "status": status, "summary": summary, "action": None,
            "owner": owner, "blocking": False}


def recommend(pr, checks, review=None):
    """`review` is the merged code review result (cpr.review.merge) or None when no panel ran.

    A plain findings list is accepted too and treated as one complete lens that approves unless it
    contains blocker or major findings.
    """
    if isinstance(review, list):
        review = {"status": "ran", "complete": True,
                  "approved": not any(f.get("severity") in ("blocker", "major") for f in review),
                  "lenses": [{"name": "review", "status": "ran", "findings": review}]}

    blocking_fail = [c for c in checks if c["blocking"] and c["status"] == "fail"]
    contributor_fail = [c for c in blocking_fail if c.get("owner") == "contributor"]
    others_fail = [c for c in blocking_fail if c.get("owner") != "contributor"]
    blocking_unknown = [c for c in checks if c["blocking"] and c["status"] == "unknown"]
    actionable = [c for c in checks if c["status"] == "warn" and c.get("action_required")]
    contributor_warn = [c for c in actionable if c.get("owner") == "contributor"]
    others_warn = [c for c in actionable if c.get("owner") != "contributor"]
    must_fix = []
    if review:
        for lens in review.get("lenses", []):
            for f in lens.get("findings", []):
                if f.get("severity") in ("blocker", "major"):
                    must_fix.append(_finding_reason(lens["name"], f))

    if pr.get("draft"):
        verdict = "draft"
        reasons = [_note("Draft PR", "The PR is marked as a draft; checks are shown as early feedback.", "contributor")]
        reasons += [_reason(c) for c in blocking_fail] + must_fix
    elif contributor_fail or must_fix:
        verdict = "needs-contributor-work"
        reasons = [_reason(c) for c in contributor_fail] + must_fix + [_reason(c) for c in others_fail]
    elif contributor_warn:
        verdict = "needs-work"
        reasons = [_reason(c) for c in contributor_warn] + [_reason(c) for c in others_fail + others_warn]
    elif blocking_unknown:
        verdict = "insufficient-evidence"
        reasons = [_reason(c) for c in blocking_unknown] + [_reason(c) for c in others_fail]
    elif others_fail or others_warn:
        verdict = "awaiting-review"
        reasons = [_reason(c) for c in others_fail + others_warn]
    elif not review or review.get("status") != "ran" or not review.get("complete"):
        verdict = "requirements-met-unreviewed"
        if not review or review.get("status") != "ran":
            why = "No code review lens has run yet, so this cannot be called ready."
        else:
            why = "The code review panel did not complete: " + ", ".join(
                l["name"] for l in review["lenses"] if l.get("status") != "ran") + "."
        reasons = [_note("Code review incomplete", "All blocking requirements pass. " + why, "reviewer", "unknown")]
    elif not review.get("approved"):
        verdict = "needs-contributor-work"
        reasons = [_note("Code review did not approve", "A lens declined to approve; see Code review.",
                         "contributor", "fail")]
    else:
        verdict = "ready"
        reasons = [_note("All requirements met and every review lens approved", "", "committer", "pass")]

    return {"verdict": verdict, "label": LABELS[verdict], "reasons": reasons,
            "waiting_on": sorted({r["owner"] for r in reasons if r.get("owner") and r["status"] != "pass"})}
