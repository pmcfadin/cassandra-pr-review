"""Assemble the evidence bundle for one PR: every input the checks and the report need.

The bundle is plain JSON. Everything after ingest is a pure function of it, so a bundle saved
here can be re-rendered offline and recorded bundles serve as test fixtures.
"""

import json
import os
import re
import time

from cpr import REPO, VERSION
from cpr.ingest import ci_summary, clone, github, history as history_mod, jira, keys, roster
from cpr.net import NetError, Recorder, http_get

BUNDLE_SCHEMA = 1
_PR_URL_RE = re.compile(rf"https://github\.com/{re.escape(REPO)}/pull/(\d+)")
_CHECKSTYLE = ".build/checkstyle.xml"


class IngestError(Exception):
    pass


def pr_dir(work_dir, number):
    return os.path.join(work_dir, "pr", str(number))


def latest_bundle_path(work_dir, number):
    return os.path.join(pr_dir(work_dir, number), "latest", "bundle.json")


def _sibling(number, recorder, key):
    """The PR as a sibling record, or None when its own resolved key is a different ticket."""
    try:
        pr = github.fetch_pr(number, recorder)
    except (github.PRNotFound, NetError):
        return None
    resolved = keys.resolve(pr["title"], pr["head_ref"], pr["body"], [])
    if resolved["key"] != key:
        return None
    return {
        "number": pr["number"],
        "url": pr["url"],
        "title": pr["title"],
        "base": pr["base"],
        "state": pr["state"],
        "merged": pr["merged"],
        "draft": pr["draft"],
        "head_sha": pr["head_sha"],
    }


def discover_siblings(pr, key, ticket, recorder):
    numbers = set()
    for link in (ticket or {}).get("remotelinks", []):
        m = _PR_URL_RE.match(link.get("url") or "")
        if m:
            numbers.add(int(m.group(1)))
    try:
        numbers.update(github.search_pr_numbers(key, recorder))
    except NetError:
        pass
    numbers.discard(pr["number"])
    siblings = [{
        "number": pr["number"], "url": pr["url"], "title": pr["title"], "base": pr["base"],
        "state": pr["state"], "merged": pr["merged"], "draft": pr["draft"],
        "head_sha": pr["head_sha"], "is_self": True,
    }]
    for n in sorted(numbers):
        s = _sibling(n, recorder, key)
        if s:
            s["is_self"] = False
            siblings.append(s)
    return siblings


def collect_ci(ticket, siblings, recorder):
    """Download and parse every ci_summary attachment; map each to a target base branch."""
    if not ticket:
        return {"status": "skipped", "summaries": [], "result_archives": []}
    by_sha = {s["head_sha"]: s["base"] for s in siblings if s.get("head_sha")}
    summaries, archives = [], []
    for att in ticket["attachments"]:
        name = att.get("filename") or ""
        if ci_summary.is_result_details(name):
            archives.append({"filename": name, "url": att.get("url"), "size": att.get("size"),
                             "target_branch": ci_summary.guess_target_branch(name)})
            continue
        if not ci_summary.is_ci_summary(name):
            continue
        record = {"attachment": name, "url": att.get("url"), "created": att.get("created"),
                  "author": att.get("author"), "parse_status": "ok", "error": None}
        try:
            parsed = ci_summary.parse(http_get(att["url"], recorder=recorder))
            record.update(parsed)
        except NetError as e:
            record.update(parse_status="unavailable", error=str(e))
        except ValueError as e:
            record.update(parse_status="unparsed", error=str(e))
        sha = record.get("sha")
        if sha and sha in by_sha:
            record["target_branch"], record["mapped_by"] = by_sha[sha], "sha"
        else:
            guess = ci_summary.guess_target_branch(record.get("ref"), name)
            record["target_branch"], record["mapped_by"] = guess, ("name" if guess else None)
        summaries.append(record)
    return {"status": "ok", "summaries": summaries, "result_archives": archives}


def voter_emails(pr, reviews, recorder):
    """Commit emails for the PR author and every GitHub approver, used to match ASF ids."""
    logins = {pr["author"]} | {r["user"] for r in reviews if r["state"] == "APPROVED"}
    return {login: github.commit_emails_for(login, recorder) for login in sorted(filter(None, logins))}


def ingest(number, work_dir, log=print):
    """Fetch everything for PR `number` and return the bundle. Raw responses go under work_dir."""
    raw = Recorder(os.path.join(pr_dir(work_dir, number), "raw"))
    log(f"fetching PR #{number}")
    pr = github.fetch_pr(number, raw)
    commits = github.fetch_commits(number, raw)
    reviews = github.fetch_reviews(number, raw)
    review_comments = github.fetch_review_comments(number, raw)
    issue_comments = github.fetch_issue_comments(number, raw)

    key_info = keys.resolve(pr["title"], pr["head_ref"], pr["body"], [c["message"] for c in commits])
    jira_info = {"status": "skipped", "ticket": None, "error": "no JIRA key"}
    if key_info["key"]:
        log(f"fetching {key_info['key']}")
        jira_info = jira.fetch_ticket(key_info["key"], raw)
    ticket = jira_info["ticket"]

    siblings = []
    if key_info["key"]:
        log("finding sibling PRs")
        siblings = discover_siblings(pr, key_info["key"], ticket, raw)
    else:
        siblings = [{"number": pr["number"], "url": pr["url"], "title": pr["title"], "base": pr["base"],
                     "state": pr["state"], "merged": pr["merged"], "draft": pr["draft"],
                     "head_sha": pr["head_sha"], "is_self": True}]

    ci = {"status": "skipped" if not key_info["key"] else ("unavailable" if jira_info["status"] == "unavailable" else "ok"),
          "summaries": [], "result_archives": []}
    if ticket:
        log("reading CI summaries")
        ci = collect_ci(ticket, siblings, raw)

    log("updating local clone")
    clone_path = os.path.join(work_dir, "cassandra")
    clone.ensure(clone_path)
    clone.fetch(clone_path, number, pr["base"])
    mb = clone.merge_base(clone_path, number, pr["base"])
    files = clone.changed_files(clone_path, mb, number)
    diff_text = clone.diff(clone_path, mb, number)
    checkstyle_xml = clone.show(clone_path, clone.base_ref(pr["base"]), _CHECKSTYLE)
    changes_head = clone.show(clone_path, clone.base_ref(pr["base"]), "CHANGES.txt")

    log("reading history of the changed code")
    history = history_mod.gather(clone_path, mb, diff_text, files)
    if history["keys"]:
        try:
            history["tickets"] = jira.lookup_keys(history["keys"], raw)
        except (NetError, ValueError) as e:
            history["tickets_error"] = str(e)

    roster_info = roster.load(os.path.join(work_dir, "roster.json"))
    emails = voter_emails(pr, reviews, raw)

    return {
        "schema": BUNDLE_SCHEMA,
        "meta": {"tool_version": VERSION, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "repo": REPO},
        "pr": pr,
        "commits": commits,
        "reviews": reviews,
        "review_comments": review_comments,
        "issue_comments": issue_comments,
        "jira_key": key_info,
        "jira": jira_info,
        "siblings": siblings,
        "ci": ci,
        "git": {"merge_base": mb, "head_ref": clone.pr_ref(number), "clone": clone_path},
        "release_branches": clone.release_branches(clone_path),
        "files": files,
        "diff": diff_text,
        "base_files": {
            "checkstyle_xml": checkstyle_xml,
            "changes_txt_head": "\n".join((changes_head or "").splitlines()[:40]),
            "has_cassandra_latest_yaml": clone.show(clone_path, clone.base_ref(pr["base"]), "conf/cassandra_latest.yaml") is not None,
        },
        "history": history,
        "roster": roster_info,
        "voter_emails": emails,
        "overrides": roster.load_overrides(),
    }


def save(bundle, work_dir):
    number = bundle["pr"]["number"]
    sha = bundle["pr"]["head_sha"]
    paths = [os.path.join(pr_dir(work_dir, number), sha, "bundle.json"), latest_bundle_path(work_dir, number)]
    for path in paths:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(bundle, f)
    return paths[0]


def load_cached(work_dir, number):
    path = latest_bundle_path(work_dir, number)
    if not os.path.exists(path):
        raise IngestError(f"no cached ingest for PR #{number} in {work_dir}; run without --offline first")
    with open(path) as f:
        return json.load(f)
