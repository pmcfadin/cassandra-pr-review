"""Assemble the evidence bundle for one PR: every input the checks and the report need.

The bundle is plain JSON. Everything after ingest is a pure function of it, so a bundle saved
here can be re-rendered offline and recorded bundles serve as test fixtures.
"""

import json
import os
import re
import time

from cpr import VERSION, layout, project as project_mod, staticanalysis
from cpr.ingest import ci_summary, clone, gh_checks, github, history as history_mod, jira, keys, roster
from cpr.net import NetError, Recorder, http_get

BUNDLE_SCHEMA = 1


class IngestError(Exception):
    pass


def pr_dir(work_dir, slug, number):
    return layout.pr_dir(work_dir, slug, number)


def latest_bundle_path(work_dir, slug, number):
    return os.path.join(pr_dir(work_dir, slug, number), "latest", "bundle.json")


def _pr_url_re(project):
    return re.compile(rf"https://github\.com/{re.escape(project.repo)}/pull/(\d+)")


def _sibling(project, number, recorder, key):
    """The PR as a sibling record, or None when its own resolved key is a different ticket."""
    try:
        pr = github.fetch_pr(project.repo, number, recorder)
    except (github.PRNotFound, NetError):
        return None
    resolved = keys.resolve(pr["title"], pr["head_ref"], pr["body"], [], project)
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


def discover_siblings(project, pr, key, ticket, recorder):
    numbers = set()
    url_re = _pr_url_re(project)
    for link in (ticket or {}).get("remotelinks", []):
        m = url_re.match(link.get("url") or "")
        if m:
            numbers.add(int(m.group(1)))
    try:
        numbers.update(github.search_pr_numbers(project.repo, key, recorder))
    except NetError:
        pass
    numbers.discard(pr["number"])
    siblings = [{
        "number": pr["number"], "url": pr["url"], "title": pr["title"], "base": pr["base"],
        "state": pr["state"], "merged": pr["merged"], "draft": pr["draft"],
        "head_sha": pr["head_sha"], "is_self": True,
    }]
    for n in sorted(numbers):
        s = _sibling(project, n, recorder, key)
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


def voter_emails(project, pr, reviews, recorder):
    """Commit emails for the PR author and every GitHub approver, used to match ASF ids."""
    logins = {pr["author"]} | {r["user"] for r in reviews if r["state"] == "APPROVED"}
    return {login: github.commit_emails_for(project.repo, login, recorder) for login in sorted(filter(None, logins))}


def ingest(project, number, work_dir, log=print):
    """Fetch everything for `project` PR `number` and return the bundle. Raw responses go under work_dir."""
    repo = project.repo
    raw = Recorder(os.path.join(pr_dir(work_dir, project.slug, number), "raw"))
    log(f"fetching {repo}#{number}")
    pr = github.fetch_pr(repo, number, raw)
    commits = github.fetch_commits(repo, number, raw)
    reviews = github.fetch_reviews(repo, number, raw)
    review_comments = github.fetch_review_comments(repo, number, raw)
    issue_comments = github.fetch_issue_comments(repo, number, raw)

    key_info = keys.resolve(pr["title"], pr["head_ref"], pr["body"], [c["message"] for c in commits], project)
    jira_info = {"status": "skipped", "ticket": None, "error": "no JIRA key"}
    if key_info["key"]:
        log(f"fetching {key_info['key']}")
        jira_info = jira.fetch_ticket(key_info["key"], raw)
    ticket = jira_info["ticket"]

    siblings = []
    if key_info["key"]:
        log("finding sibling PRs")
        siblings = discover_siblings(project, pr, key_info["key"], ticket, raw)
    else:
        siblings = [{"number": pr["number"], "url": pr["url"], "title": pr["title"], "base": pr["base"],
                     "state": pr["state"], "merged": pr["merged"], "draft": pr["draft"],
                     "head_sha": pr["head_sha"], "is_self": True}]

    if project.ci_provider == "github-checks":
        log("reading GitHub checks of the head")
        gh = gh_checks.fetch(repo, pr["head_sha"], raw)
        ci = {"status": gh["status"], "provider": "github-checks", "github": gh, "summaries": [], "result_archives": []}
    else:
        ci = {"status": "skipped" if not key_info["key"] else ("unavailable" if jira_info["status"] == "unavailable" else "ok"),
              "summaries": [], "result_archives": []}
        if ticket:
            log("reading CI summaries")
            ci = collect_ci(ticket, siblings, raw)

    log("updating local clone")
    clone_path = layout.clone_dir(work_dir, project)
    clone.ensure(clone_path, repo)
    clone.fetch(clone_path, number, pr["base"])
    mb = clone.merge_base(clone_path, number, pr["base"])
    files = clone.changed_files(clone_path, mb, number)
    diff_text = clone.diff(clone_path, mb, number)
    checkstyle_xml = clone.show(clone_path, clone.base_ref(pr["base"]), project.static["checkstyle"]["configs"]["main"])
    changes_head = clone.show(clone_path, clone.base_ref(pr["base"]), "CHANGES.txt")

    log("reading history of the changed code")
    history = history_mod.gather(clone_path, mb, diff_text, files, project=project)
    if history["keys"]:
        try:
            history["tickets"] = jira.lookup_keys(history["keys"], raw)
        except (NetError, ValueError) as e:
            history["tickets_error"] = str(e)

    roster_info = roster.load(os.path.join(work_dir, "roster.json"))
    emails = voter_emails(project, pr, reviews, raw)

    git_info = {"merge_base": mb, "head_ref": clone.pr_ref(number), "clone": clone_path}
    log("running static analysis")
    static = staticanalysis.analyze({"meta": {"project": project.slug, "repo": repo}, "pr": pr, "git": git_info},
                                    work_dir, log=log)

    return {
        "schema": BUNDLE_SCHEMA,
        "meta": {"tool_version": VERSION, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "project": project.slug, "repo": repo},
        "pr": pr,
        "commits": commits,
        "reviews": reviews,
        "review_comments": review_comments,
        "issue_comments": issue_comments,
        "jira_key": key_info,
        "jira": jira_info,
        "siblings": siblings,
        "ci": ci,
        "git": git_info,
        "release_branches": clone.release_branches(clone_path),
        "files": files,
        "diff": diff_text,
        "base_files": {
            "checkstyle_xml": checkstyle_xml,
            "changes_txt_head": "\n".join((changes_head or "").splitlines()[:40]),
            "has_cassandra_latest_yaml": clone.show(clone_path, clone.base_ref(pr["base"]), "conf/cassandra_latest.yaml") is not None,
        },
        "history": history,
        "static_analysis": static,
        "roster": roster_info,
        "voter_emails": emails,
        "overrides": roster.load_overrides(),
    }


def save(bundle, work_dir):
    slug, number, sha = project_mod.of(bundle).slug, bundle["pr"]["number"], bundle["pr"]["head_sha"]
    paths = [os.path.join(pr_dir(work_dir, slug, number), sha, "bundle.json"), latest_bundle_path(work_dir, slug, number)]
    for path in paths:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(bundle, f)
    return paths[0]


def load_cached(work_dir, slug, number):
    path = latest_bundle_path(work_dir, slug, number)
    if not os.path.exists(path):
        raise IngestError(f"no cached ingest for {slug}#{number} in {work_dir}; run without --offline first")
    with open(path) as f:
        bundle = json.load(f)
    if project_mod.of(bundle).slug != slug:
        raise IngestError(f"{path} holds a {project_mod.of(bundle).slug} PR, not {slug}#{number}")
    bundle["static_analysis"] = staticanalysis.load_cached(bundle)
    return bundle
