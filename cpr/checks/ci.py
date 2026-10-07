"""CI evidence checks: summaries attached to JIRA, their freshness, profile, and failures."""

import re

from cpr.checks import Result, check, ev

# Diff paths that need the "pre-commit w/ upgrades" profile.
UPGRADE_SENSITIVE = [
    re.compile(r"Serializ\w*\.java$"),
    re.compile(r"^src/java/org/apache/cassandra/net/(MessagingService|Verb|Message)\.java$"),
    re.compile(r"^src/java/org/apache/cassandra/io/sstable/format/[^/]*(Version|Format|Descriptor)[^/]*\.java$"),
    re.compile(r"^src/java/org/apache/cassandra/io/sstable/(Descriptor|Component)\.java$"),
    re.compile(r"^src/java/org/apache/cassandra/io/sstable/metadata/"),
    re.compile(r"^src/java/org/apache/cassandra/db/commitlog/CommitLogDescriptor\.java$"),
    re.compile(r"^src/java/org/apache/cassandra/hints/HintsDescriptor\.java$"),
    re.compile(r"^src/java/org/apache/cassandra/(schema/SchemaKeyspace|db/SystemKeyspace)[^/]*\.java$"),
    re.compile(r"^src/java/org/apache/cassandra/transport/ProtocolVersion\.java$"),
]
_SERIALIZER_RE = re.compile(r"implements\s+[^{]*\b(IVersionedSerializer|IVersionedAsymmetricSerializer|IPartitionerDependentSerializer)\b")


def upgrade_sensitive_files(ctx):
    hits = []
    for f in ctx.files:
        p = f["path"]
        if not p.startswith("src/java/"):
            continue
        if any(rx.search(p) for rx in UPGRADE_SENSITIVE):
            hits.append(p)
            continue
        added = "\n".join(t for _, t in ctx.added.get(p, {}).get("added", []))
        if _SERIALIZER_RE.search(added):
            hits.append(p)
    return hits


def _summaries_by_branch(bundle):
    out = {}
    for s in bundle["ci"]["summaries"]:
        if s.get("parse_status") != "ok" or not s.get("target_branch"):
            continue
        prev = out.get(s["target_branch"])
        if prev is None or (s.get("created") or "") > (prev.get("created") or ""):
            out[s["target_branch"]] = s
    return out


def _no_source(bundle, ctx):
    from cpr.checks.ticket import is_release_branch
    if not ctx.key and not is_release_branch(ctx.pr["base"]):
        return Result("not-applicable", f"Feature branch `{ctx.pr['base']}` with no ticket; its owners set the CI rules")
    if not ctx.key:
        return Result("unknown", "No JIRA ticket, so there is nowhere to read CI results from")
    if ctx.jira_status == "unavailable":
        return Result("unknown", "JIRA could not be reached, so CI results could not be read")
    if ctx.jira_status == "not_found":
        return Result("unknown", "The ticket does not exist, so CI results could not be read")
    return None


@check("ci.evidence", "CI results exist for every target branch", "ci", "ci", blocking=True, owner="committer")
def evidence(bundle, ctx):
    missing_src = _no_source(bundle, ctx)
    if missing_src:
        return missing_src
    by_branch = _summaries_by_branch(bundle)
    targets = ctx.targeted_branches()
    rows, missing = [], []
    for branch, pr in sorted(targets.items()):
        s = by_branch.get(branch)
        if s:
            rows.append(ev(f"`{branch}`: {s['attachment']} — {s.get('failed', '?')} failed of {s.get('total', '?')}",
                           s.get("url")))
        else:
            missing.append(branch)
            rows.append(ev(f"`{branch}` (PR #{pr['number']}): CI not yet run"))
    unparsed = [s for s in bundle["ci"]["summaries"] if s.get("parse_status") != "ok" or not s.get("target_branch")]
    for s in unparsed:
        rows.append(ev(f"{s['attachment']}: {s.get('parse_status')}"
                       f"{'' if s.get('target_branch') else ', branch unknown'} {s.get('error') or ''}".strip(), s.get("url")))
    if missing:
        return Result("fail", "CI not yet run for " + ", ".join(f"`{b}`" for b in missing), rows,
                      action="Run pre-commit CI (`.build/run-ci`) for each branch and attach `ci_summary.html` and "
                             "the `results_details` archive to the ticket. Contributors without CI access should say so on "
                             "the ticket so a committer can run it.")
    return Result("pass", f"CI summaries attached for all {len(targets)} target branches", rows)


@check("ci.freshness", "CI ran on the current PR head", "ci", "ci", blocking=False, owner="committer")
def freshness(bundle, ctx):
    missing_src = _no_source(bundle, ctx)
    if missing_src:
        return missing_src
    by_branch = _summaries_by_branch(bundle)
    targets = ctx.targeted_branches()
    stale, rows, unknown = [], [], []
    for branch, pr in sorted(targets.items()):
        s = by_branch.get(branch)
        if not s:
            continue
        if not s.get("sha"):
            unknown.append(branch)
            rows.append(ev(f"`{branch}`: {s.get('sha_note') or 'no sha recorded'}", s.get("url")))
        elif s["sha"] != pr["head_sha"]:
            stale.append(branch)
            rows.append(ev(f"`{branch}`: CI ran on `{s['sha'][:10]}`, PR head is `{pr['head_sha'][:10]}`", s.get("url")))
        else:
            rows.append(ev(f"`{branch}`: CI sha matches PR head `{pr['head_sha'][:10]}`", s.get("url")))
    if not rows:
        return Result("not-applicable", "No CI summaries to compare")
    if stale:
        return Result("warn", "CI ran on an older commit for " + ", ".join(f"`{b}`" for b in stale), rows,
                      action="Re-run CI on the current head, or note on the ticket why the later commits do not need it.")
    if unknown:
        return Result("warn", "Could not tell which commit CI ran on for " + ", ".join(f"`{b}`" for b in unknown), rows,
                      action="Confirm on the ticket which commit the CI run used.", action_required=False)
    return Result("pass", "Every CI summary matches its PR head", rows)


@check("ci.profile", "CI profile covers the change", "ci", "ci", blocking=True, owner="committer")
def profile(bundle, ctx):
    sensitive = upgrade_sensitive_files(ctx)
    if not sensitive:
        return Result("not-applicable", "No upgrade-sensitive code touched; `pre-commit` is enough")
    missing_src = _no_source(bundle, ctx)
    if missing_src:
        return missing_src
    by_branch = _summaries_by_branch(bundle)
    if not by_branch:
        return Result("unknown", "Upgrade-sensitive code touched, but no CI summary to check",
                      [ev(p, location=p) for p in sensitive[:10]])
    lacking = [b for b, s in by_branch.items() if not s.get("has_upgrade_tests")]
    files = [ev(f"touches `{p}`", location=p) for p in sensitive[:10]]
    if lacking:
        return Result("fail", "Upgrade-sensitive code changed, but CI for " + ", ".join(f"`{b}`" for b in sorted(lacking))
                      + " ran no upgrade tests", files,
                      action="Run CI with the `pre-commit w/ upgrades` profile for those branches.")
    return Result("pass", "Upgrade tests ran on every branch with CI", files)


@check("ci.failures", "CI failures", "ci", "ci", blocking=False, owner="reviewer")
def failures(bundle, ctx):
    by_branch = _summaries_by_branch(bundle)
    if not by_branch:
        return Result("not-applicable", "No CI summaries")
    rows, total, uncounted = [], 0, []
    for branch, s in sorted(by_branch.items()):
        n = s.get("failed")
        if n is None:
            uncounted.append(branch)
            rows.append(ev(f"`{branch}`: failure count not found in the summary", s.get("url")))
            continue
        total += n
        rows.append(ev(f"`{branch}`: {n} failed" + (": " + "; ".join(s["failures"][:5]) if s.get("failures") else ""),
                       s.get("url")))
    if uncounted and not total:
        return Result("unknown", "Could not read the failure count for " + ", ".join(f"`{b}`" for b in uncounted), rows)
    if total:
        return Result("warn", f"{total} test failure(s) across CI runs; not yet compared against known flaky tests", rows,
                      action="Explain each failure on the ticket (pre-existing, flaky, or caused by this patch).")
    return Result("pass", "No test failures in attached CI", rows)
