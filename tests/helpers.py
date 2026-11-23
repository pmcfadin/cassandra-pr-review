"""Builders for synthetic evidence bundles used by unit tests."""

import copy

SHA = "a" * 40
SHA2 = "b" * 40

CHECKSTYLE = """<?xml version="1.0"?>
<module name="Checker"><module name="TreeWalker">
  <module name="RegexpSinglelineJava">
    <property name="id" value="blockSystemClock"/>
    <property name="format" value="System\\.(currentTimeMillis|nanoTime)"/>
    <property name="message" value="Avoid System for time"/>
  </module>
  <module name="IllegalImport">
    <property name="illegalClasses" value="java.io.File,java.util.concurrent.Executors"/>
  </module>
  <module name="IllegalInstantiation">
    <property name="classes" value="java.lang.Thread"/>
  </module>
</module></module>"""

LICENSE = """/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.
 */"""


def file_diff(path, added_lines, new_file=False, start=1):
    old = "/dev/null" if new_file else f"a/{path}"
    body = "\n".join("+" + line for line in added_lines)
    return (f"diff --git a/{path} b/{path}\n--- {old}\n+++ b/{path}\n"
            f"@@ -0,0 +{start},{len(added_lines)} @@\n{body}\n")


def ticket(**kw):
    t = {
        "key": "CASSANDRA-21649", "url": "https://issues.apache.org/jira/browse/CASSANDRA-21649",
        "summary": "Fix things", "description": "", "status": "Patch Available", "resolution": None,
        "issuetype": "Bug", "components": ["Local/SSTable"], "fix_versions": ["5.0.x", "7.x"],
        "since_versions": [], "reviewers": [], "authors": [], "assignee": [], "test_doc_plan": "",
        "impacts": [], "source_control_link": "", "comments": [], "attachments": [], "remotelinks": [],
    }
    t.update(kw)
    return t


def ci_summary(branch="cassandra-5.0", sha=SHA, failed=0, upgrades=True, **kw):
    s = {"attachment": f"ci_summary_{branch}.html", "url": "https://issues.apache.org/jira/secure/attachment/1/x.html",
         "created": "2026-10-01T00:00:00.000+0000", "author": "maedhroz", "parse_status": "ok", "error": None,
         "layout": "classic", "sha": sha, "ref": f"CASSANDRA-21649-{branch}", "repo": None, "profile": None,
         "overall": "PASS" if not failed else "FAIL", "passed": 100, "failed": failed, "skipped": 0, "total": 100 + failed,
         "failures": [f"Test{i}" for i in range(failed)], "has_upgrade_tests": upgrades, "sha_note": None,
         "target_branch": branch, "mapped_by": "sha"}
    s.update(kw)
    return s


def bundle(**kw):
    """A passing-by-default bundle for a 5.0 bug fix with tests, CHANGES.txt, CI, and two votes."""
    diff = (file_diff("src/java/org/apache/cassandra/db/Foo.java", ["int x = 1;"]) +
            file_diff("test/unit/org/apache/cassandra/db/FooTest.java", ["@Test public void t() {}"]) +
            file_diff("CHANGES.txt", [" * Fix things (CASSANDRA-21649)"]))
    b = {
        "schema": 1,
        "meta": {"tool_version": "test", "fetched_at": "2026-10-07T00:00:00Z", "repo": "apache/cassandra"},
        "pr": {"number": 5198, "url": "https://github.com/apache/cassandra/pull/5198",
               "title": "CASSANDRA-21649: Fix things (5.0)", "body": "", "author": "alice",
               "author_association": "CONTRIBUTOR", "state": "open", "merged": False, "draft": False,
               "base": "cassandra-5.0", "head_ref": "21649-5.0", "head_sha": SHA, "head_repo": "alice/cassandra",
               "labels": [], "created_at": "", "updated_at": "", "additions": 3, "deletions": 0, "changed_files": 3},
        "commits": [{"sha": SHA, "message": "Fix things\n\npatch by Alice; reviewed by Bob, Carol for CASSANDRA-21649",
                     "author_name": "Alice", "author_email": "alice@example.com", "login": "alice", "trailers": []}],
        "reviews": [], "review_comments": [], "issue_comments": [],
        "jira_key": {"key": "CASSANDRA-21649", "sources": ["title", "branch"], "conflicts": [],
                     "mentioned": ["CASSANDRA-21649"]},
        "jira": {"status": "ok", "error": None, "ticket": ticket(comments=[
            {"id": "1", "author": "bob", "display": "Bob", "created": "", "body": "+1", "url": "u1"},
            {"id": "2", "author": "carol", "display": "Carol", "created": "", "body": "LGTM, +1 from me", "url": "u2"},
        ])},
        "siblings": [{"number": 5198, "url": "https://github.com/apache/cassandra/pull/5198", "title": "t",
                      "base": "cassandra-5.0", "state": "open", "merged": False, "draft": False,
                      "head_sha": SHA, "is_self": True},
                     {"number": 5113, "url": "https://github.com/apache/cassandra/pull/5113", "title": "t",
                      "base": "trunk", "state": "open", "merged": False, "draft": False,
                      "head_sha": SHA2, "is_self": False}],
        "ci": {"status": "ok", "summaries": [ci_summary("cassandra-5.0", SHA), ci_summary("trunk", SHA2)],
               "result_archives": []},
        "git": {"merge_base": "c" * 40, "head_ref": "refs/cpr/pr/5198", "clone": "/nonexistent"},
        "release_branches": ["cassandra-4.0", "cassandra-4.1", "cassandra-5.0", "cassandra-6.0", "trunk"],
        "files": [
            {"path": "src/java/org/apache/cassandra/db/Foo.java", "previous_path": None, "status": "M",
             "additions": 1, "deletions": 0, "binary": False},
            {"path": "test/unit/org/apache/cassandra/db/FooTest.java", "previous_path": None, "status": "M",
             "additions": 1, "deletions": 0, "binary": False},
            {"path": "CHANGES.txt", "previous_path": None, "status": "M", "additions": 1, "deletions": 0,
             "binary": False},
        ],
        "diff": diff,
        "base_files": {"checkstyle_xml": CHECKSTYLE, "changes_txt_head": "", "has_cassandra_latest_yaml": True},
        "roster": {"status": "ok", "error": None,
                   "roster": {"committers": {"bob": "Bob", "carol": "Carol", "dave": "Dave"}, "pmc": ["bob"],
                              "fetched_at": 0}},
        "voter_emails": {},
        "overrides": {"github": {}, "jira": {}},
    }
    for k, v in kw.items():
        if isinstance(v, dict) and isinstance(b.get(k), dict) and not k.startswith("_"):
            b[k] = {**b[k], **v}
        else:
            b[k] = v
    return copy.deepcopy(b)


def github_ci(fixture, head):
    """The bundle's `ci.github` from recorded check-runs and workflow runs (tests/fixtures/ci/gh-*-<fixture>.json)."""
    import json
    import os
    from unittest import mock
    from cpr.ingest import gh_checks
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "ci")
    pages = {}
    for kind in ("check-runs", "workflow-runs"):
        with open(os.path.join(d, f"gh-{kind}-{fixture}.json")) as f:
            pages[kind] = [json.load(f)]
    for w in pages["workflow-runs"][0]["workflow_runs"]:
        w["head_sha"] = head  # recorded for the real head; the synthetic bundle has its own
    with mock.patch.object(gh_checks, "gh_json",
                           side_effect=lambda path, **k: pages["check-runs" if "/check-runs" in path else "workflow-runs"]):
        return gh_checks.fetch("apache/cassandra-sidecar", head, None)


def sidecar_bundle(**kw):
    """A sidecar PR: Gradle modules, CASSSIDECAR key, trunk only, credit line with a markdown-link key."""
    files = [("server/src/main/java/org/apache/cassandra/sidecar/routes/FooHandler.java", ["int x = 1;"], False),
             ("server/src/test/java/org/apache/cassandra/sidecar/routes/FooHandlerTest.java", ["@Test void t() {}"], False),
             ("CHANGES.txt", [" * Fix the foo handler (CASSSIDECAR-378)"], False)]
    b = with_files(bundle(), files)
    b["meta"] = {**b["meta"], "project": "sidecar", "repo": "apache/cassandra-sidecar"}
    b["pr"] = {**b["pr"], "number": 397, "url": "https://github.com/apache/cassandra-sidecar/pull/397",
               "title": "CASSSIDECAR-378: Fix the foo handler", "base": "trunk", "head_ref": "CASSSIDECAR-378",
               "head_repo": "alice/cassandra-sidecar"}
    b["commits"] = [{**b["commits"][0], "message": "CASSSIDECAR-378: Fix the foo handler (#397)\n\nPatch by Alice; "
                     "Reviewed by Bob, Carol for [CASSSIDECAR-378](https://issues.apache.org/jira/browse/CASSSIDECAR-378)"}]
    b["jira_key"] = {"key": "CASSSIDECAR-378", "sources": ["title", "branch"], "conflicts": [],
                     "mentioned": ["CASSSIDECAR-378"]}
    b["jira"] = {**b["jira"], "ticket": {**b["jira"]["ticket"], "key": "CASSSIDECAR-378",
                                          "url": "https://issues.apache.org/jira/browse/CASSSIDECAR-378",
                                          "fix_versions": ["0.5.0"], "components": []}}
    b["siblings"] = [{**b["siblings"][0], "number": 397, "url": b["pr"]["url"], "base": "trunk"}]
    b["release_branches"] = ["trunk"]
    b["ci"] = {"status": "ok", "provider": "github-checks", "github": github_ci("sidecar-400", SHA),
               "summaries": [], "result_archives": []}
    b["base_files"] = {**b["base_files"], "checkstyle_xml": None}
    for k, v in kw.items():
        b[k] = {**b[k], **v} if isinstance(v, dict) and isinstance(b.get(k), dict) else v
    return copy.deepcopy(b)


def with_files(b, files):
    """Replace files and diff. `files` is [(path, added_lines, new_file)]."""
    b["files"] = [{"path": p, "previous_path": None, "status": "A" if new else "M", "additions": len(lines),
                   "deletions": 0, "binary": False} for p, lines, new in files]
    b["diff"] = "".join(file_diff(p, lines, new) for p, lines, new in files)
    return b


def result(results, check_id):
    return next(r for r in results if r["id"] == check_id)
