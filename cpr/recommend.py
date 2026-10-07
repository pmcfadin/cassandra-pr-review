"""Turn check results and review findings into one recommendation, with the reasons for it."""

LABELS = {
    "draft": "Draft — early feedback only",
    "blocked": "Blocked — merge requirements not met",
    "insufficient-evidence": "Insufficient evidence — some required inputs could not be read",
    "needs-work": "Needs work — contributor action needed",
    "requirements-met-unreviewed": "Requirements met — code not yet reviewed",
    "ready": "Ready to merge",
}


def _reason(c):
    return {"check": c["id"], "title": c["title"], "status": c["status"], "summary": c["summary"],
            "action": c.get("action"), "owner": c.get("owner"), "blocking": c["blocking"]}


def recommend(pr, checks, findings=None):
    """First matching rule wins (see design D8). `findings` is None when no review lens ran."""
    blocking_fail = [c for c in checks if c["blocking"] and c["status"] == "fail"]
    blocking_unknown = [c for c in checks if c["blocking"] and c["status"] == "unknown"]
    actionable = [c for c in checks if c["status"] in ("warn", "fail") and c.get("action_required")
                  and not (c["blocking"] and c["status"] == "fail")]
    must_fix = [f for f in (findings or []) if f.get("severity") in ("blocker", "major")]

    if pr.get("draft"):
        verdict, reasons = "draft", [{"check": None, "title": "Draft PR", "status": "info",
                                      "summary": "The PR is marked as a draft; checks are shown as early feedback.",
                                      "action": None, "owner": "contributor", "blocking": False}]
        reasons += [_reason(c) for c in blocking_fail]
    elif blocking_fail:
        verdict, reasons = "blocked", [_reason(c) for c in blocking_fail]
    elif blocking_unknown:
        verdict, reasons = "insufficient-evidence", [_reason(c) for c in blocking_unknown]
    elif actionable:
        verdict, reasons = "needs-work", [_reason(c) for c in actionable]
    elif findings is None:
        verdict, reasons = "requirements-met-unreviewed", [{
            "check": None, "title": "Code review has not run", "status": "unknown",
            "summary": "All blocking requirements pass. No code review lens has run yet, so this cannot be called ready.",
            "action": None, "owner": "reviewer", "blocking": False}]
    elif must_fix:
        verdict, reasons = "needs-work", [{"check": None, "title": f"[{f['severity']}] {f.get('rule', '')}",
                                           "status": "fail", "summary": f.get("problem", ""), "action": f.get("fix"),
                                           "owner": "contributor", "blocking": True} for f in must_fix]
    else:
        verdict, reasons = "ready", [{"check": None, "title": "All requirements met and code review approved",
                                      "status": "pass", "summary": "", "action": None, "owner": "committer",
                                      "blocking": False}]
    return {"verdict": verdict, "label": LABELS[verdict], "reasons": reasons,
            "waiting_on": sorted({r["owner"] for r in reasons if r.get("owner")})}
