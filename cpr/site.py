"""Build the static GitHub Pages site: an index of every report plus the reports themselves.

Layout of the output directory:

    index.html            list of reports, newest first (rebuilt from pr/*/index.html)
    pr/<N>/index.html     each report, copied unchanged
    .nojekyll             serve files as-is
"""

import glob
import html
import json
import os
import re
import shutil

from cpr import VERSION
from cpr.model import ROLE_NAMES, derive_view
from cpr.render import tokens_style

_MODEL_RE = re.compile(r'<script id="report-model">window\.REPORT_MODEL = (.*?);</script>', re.S)


def read_model(report_path):
    """The report model embedded in a rendered report, or None."""
    with open(report_path) as f:
        m = _MODEL_RE.search(f.read())
    if not m:
        return None
    return json.loads(m.group(1))


def _build_label(build):
    st = (build or {}).get("status")
    return "not built" if st in (None, "not-built") else st


def has_results(model):
    """True when the report carries AI code review or build results (the richer kind of report)."""
    if (model.get("review") or {}).get("status") == "ran":
        return True
    return (model.get("build") or {}).get("status") not in (None, "not-built")


def replaces(published, local):
    """Keep-richer rule: should the local report model replace the published one for the same PR?

    A different head always replaces. For the same head, local replaces published when it has review or
    build results, or when the published one has neither (so a plain refresh still lands).
    """
    if published is None:
        return True
    if published["pr"].get("head_sha") != local["pr"].get("head_sha"):
        return True
    return has_results(local) or not has_results(published)


def published_reports(site_dir):
    """{PR number: report model} for every readable pr/<N>/index.html under site_dir."""
    out = {}
    for path in glob.glob(os.path.join(site_dir, "pr", "*", "index.html")):
        try:
            model = read_model(path)
        except (OSError, ValueError):
            continue
        if model:
            out[model["pr"]["number"]] = model
    return out


def published_heads(site_dir):
    return {n: m["pr"].get("head_sha") for n, m in published_reports(site_dir).items()}


def merge_report(site_dir, report_path):
    """Apply one local report to the site. Returns (number, action): added, replaced, kept, or skipped."""
    local = read_model(report_path)
    if not local:
        return None, "skipped"
    number = local["pr"]["number"]
    dest = os.path.join(site_dir, "pr", str(number), "index.html")
    published = None
    if os.path.exists(dest):
        try:
            published = read_model(dest)
        except (OSError, ValueError):
            published = None
    if published is not None and not replaces(published, local):
        return number, "kept"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(report_path, dest)
    return number, "added" if published is None else "replaced"


def rebuild_index(site_dir):
    """Write index.html from every pr/<N>/index.html in the site. Returns the rows."""
    rows = [summarize(m) for m in published_reports(site_dir).values()]
    rows.sort(key=lambda r: r["number"], reverse=True)
    os.makedirs(site_dir, exist_ok=True)
    with open(os.path.join(site_dir, "index.html"), "w") as f:
        f.write(index_html(rows))
    open(os.path.join(site_dir, ".nojekyll"), "w").close()
    return rows


def merge(reports_dir, site_dir):
    """Merge local reports into an existing site without deleting anything, then rebuild the index.

    Returns (rows, actions) where actions maps PR number to added/replaced/kept.
    """
    actions = {}
    for path in sorted(glob.glob(os.path.join(reports_dir, "*", "index.html"))):
        number, action = merge_report(site_dir, path)
        if number is not None:
            actions[number] = action
    return rebuild_index(site_dir), actions


GROUPS = (
    ("ready", "Ready for a committer", "A committer can act now: merge it, or run CI or vote."),
    ("reviewers", "Waiting on reviewers", "The contributor's part is done. Reviewers or committers are next."),
    ("contributor", "Waiting on the contributor", "The contributor has fixes to make first."),
    ("unknown", "Cannot tell yet", "Some required inputs could not be read, so the tool cannot say."),
    ("draft", "Drafts", "Early feedback only. Not a merge decision."),
)
CHIP_KIND = {"blocked": "fail", "waiting": "should", "ready": "pass", "unknown": "unknown", "draft": "na"}
EFFORT_WORDS = {"easy": "Small", "moderate": "Medium", "hard": "Large"}
BUILD_CHIPS = {"pass": ("pass", "Built, tests passed"), "tests-failed": ("fail", "Tests failed"),
               "build-failed": ("fail", "Build failed"), "timeout": ("unknown", "Build timed out"),
               "unknown": ("unknown", "Build inconclusive")}


def _group(kind, now_role):
    """Who acts next, from the report's own derived view: verdict kind plus the first role in To do."""
    if kind == "draft":
        return "draft"
    if kind == "unknown":
        return "unknown"
    if kind == "ready" or now_role == "committer":
        return "ready"
    if kind == "blocked" or now_role == "contributor":
        return "contributor"
    return "reviewers"


def _plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def _review_chip(review):
    """(kind, text) when the AI code review ran, else None."""
    if review.get("status") != "ran":
        return None
    c = review.get("issue_counts") or review.get("counts") or {}
    parts = [f"{c[k]} {k}" for k in ("blocker", "major", "minor", "nit") if c.get(k)]
    kind = "fail" if c.get("blocker") or c.get("major") else ("should" if c.get("minor") else "pass")
    return kind, "Code review: " + (", ".join(parts) if parts else "no issues")


def _build_chip(build):
    return BUILD_CHIPS.get((build or {}).get("status"))


def summarize(model):
    pr, review, tri = model["pr"], model.get("review") or {}, model.get("triage") or {}
    try:
        view = model.get("view") or derive_view(model)
        verdict, todo = view["verdict"], view["todo"]
    except (KeyError, TypeError):
        verdict, todo = {"kind": "unknown", "headline": model["recommendation"]["label"]}, {}
    kind = verdict.get("kind", "unknown")
    now_role = todo.get("now_role")
    group = _group(kind, now_role)
    lines, files = tri.get("lines"), tri.get("files")
    effort = EFFORT_WORDS.get(tri.get("rating"), "")
    if effort and lines is not None and files is not None:
        effort += f" · {_plural(lines, 'line')} in {_plural(files, 'file')}"
    return {
        "number": pr["number"], "title": pr["title"], "author": pr["author"], "base": pr["base"],
        "url": pr["url"], "jira": (model.get("jira_key") or {}).get("key"),
        "verdict": model["recommendation"]["verdict"], "label": verdict["headline"], "kind": CHIP_KIND.get(kind, "unknown"),
        "group": group, "must": todo.get("must_count") or 0, "fixes": todo.get("fix_count") or 0,
        "acts": ROLE_NAMES.get(now_role) or ("Committer" if group == "ready" else ""),
        "triage": tri.get("rating"), "effort": effort,
        "generated_at": model["generated_at"], "head": pr.get("head_sha"),
        "review_chip": _review_chip(review), "build_chip": _build_chip(model.get("build")),
        "build": _build_label(model.get("build")),
    }


def index_html(rows):
    def e(s):
        return html.escape(str(s if s is not None else ""), quote=True)

    def chip(kind, text):
        return f'<span class="chip s-{e(kind)}">{e(text)}</span>'

    def row_html(r):
        jira = (f'<a href="https://issues.apache.org/jira/browse/{e(r["jira"])}">{e(r["jira"])}</a>' if r["jira"]
                else "no ticket")
        need = (f'<span class="count must">{e(r["must"])} must fix</span>' if r["must"]
                else (f'<span class="count">{e(_plural(r["fixes"], "fix"))}</span>' if r["fixes"] else ""))
        acts = f'<span class="acts">Next: <b>{e(r["acts"])}</b></span>' if r["acts"] else ""
        effort = f'<span class="effort">Review effort: {e(r["effort"])}</span>' if r["effort"] else ""
        chips = "".join(chip(*c) for c in (r["review_chip"], r["build_chip"]) if c)
        return f"""
      <li class="item" data-pr="{e(r['number'])}">
        <a class="main" href="pr/{e(r['number'])}/"><span class="num">#{e(r['number'])}</span><span class="title">{e(r['title'])}</span></a>
        <div class="meta">{chip(r['kind'], r['label'])}{need}{acts}{effort}{chips}</div>
        <div class="sub">{e(r['author'])} into <code>{e(r['base'])}</code> · {jira} ·
          <a href="{e(r['url'])}">GitHub PR</a> · Updated {e(str(r['generated_at'])[:10])}</div>
      </li>"""

    by_group = {key: [] for key, _, _ in GROUPS}
    for r in rows:
        by_group.setdefault(r["group"], []).append(r)
    stats, sections = [], []
    for key, title, hint in GROUPS:
        items = sorted(by_group.get(key, []), key=lambda r: (str(r["generated_at"]), r["number"]), reverse=True)
        if not items:
            continue
        stats.append(f'<a class="stat" href="#g-{key}"><span class="count">{len(items)}</span> {e(title)}</a>')
        sections.append(f"""
  <section class="card group" id="g-{key}" aria-labelledby="h-{key}">
    <div class="group-head"><h2 id="h-{key}">{e(title)}</h2><span class="count">{len(items)}</span><p class="hint">{e(hint)}</p></div>
    <ul>{"".join(row_html(r) for r in items)}
    </ul>
  </section>""")
    body = "".join(sections) or '<p class="empty">No reports yet.<span class="why">Run <code>cpr review &lt;PR number&gt;</code> and publish to add one.</span></p>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>Cassandra PR Reviews</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Red+Hat+Mono:wght@400;500&amp;family=Red+Hat+Text:wght@400;500;600;700&amp;display=swap" rel="stylesheet">
{tokens_style()}
<style>
main {{ max-width: 1040px; margin: 0 auto; padding: 28px 24px 64px; display: flex; flex-direction: column; gap: 20px; }}
header.top {{ display: flex; flex-direction: column; gap: 6px; }}
header.top .eyebrow {{ font-size: var(--fs-xs); font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--ink-3); }}
h1 {{ font-size: var(--fs-h1); font-weight: 600; }}
.lede {{ margin: 0; color: var(--ink-3); max-width: 70ch; }}
.stats {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
.stat {{ display: inline-flex; align-items: center; gap: 8px; min-height: 40px; padding: 0 12px; background: var(--panel); border: 1px solid var(--rule); border-radius: var(--r-card); color: var(--ink); text-decoration: none; font-size: var(--fs-md); font-weight: 500; }}
.stat:hover {{ background: var(--hover); }}
.group-head {{ display: flex; flex-wrap: wrap; align-items: center; gap: 4px 12px; padding: 16px 20px; background: var(--soft); border-bottom: 1px solid var(--rule-2); }}
.group-head h2 {{ font-size: var(--fs-lg); font-weight: 600; }}
.group-head .hint {{ margin: 0; flex: 1 1 280px; color: var(--ink-3); font-size: var(--fs-md); }}
ul {{ list-style: none; margin: 0; padding: 0; }}
.item {{ padding: 14px 20px; border-bottom: 1px solid var(--rule-2); display: flex; flex-direction: column; gap: 6px; }}
.item:last-child {{ border-bottom: 0; }}
.item:hover {{ background: var(--hover); }}
.main {{ display: flex; gap: 10px; align-items: baseline; color: var(--ink); text-decoration: none; font-weight: 600; font-size: var(--fs-lg); overflow-wrap: anywhere; }}
.main:hover .title {{ text-decoration: underline; }}
.num {{ font-family: var(--mono); font-size: var(--fs-md); font-weight: 500; color: var(--ink-3); flex: none; }}
.meta {{ display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; font-size: var(--fs-md); color: var(--ink-2); }}
.meta b {{ font-weight: 600; color: var(--ink); }}
.sub {{ font-size: var(--fs-sm); color: var(--ink-3); overflow-wrap: anywhere; }}
.empty {{ padding: 20px; }}
footer {{ font-size: var(--fs-sm); color: var(--ink-3); border-top: 1px solid var(--rule); padding-top: 16px; }}
@media (max-width: 639.98px) {{
  main {{ padding: 20px 16px 48px; }}
  .group-head, .item {{ padding-left: 16px; padding-right: 16px; }}
  .stat {{ flex: 1 1 100%; }}
  .main {{ min-height: 40px; }}
}}
</style>
</head>
<body>
<main>
  <header class="top">
    <div class="eyebrow">Cassandra PR review</div>
    <h1>Pull request reviews</h1>
    <p class="lede">Reports on <a href="https://github.com/apache/cassandra/pulls">apache/cassandra</a> pull requests, grouped by who acts next.
      Each report is advisory; committers decide.</p>
    <nav class="stats" aria-label="Groups">{"".join(stats)}</nav>
  </header>{body}
  <footer>Generated by <a href="https://github.com/pmcfadin/cassandra-pr-review">cassandra-pr-review</a> {e(VERSION)}.</footer>
</main>
</body>
</html>
"""


def build(reports_dir, out_dir):
    """Write a site into out_dir from reports/<N>/index.html alone. Returns the rows."""
    os.makedirs(out_dir, exist_ok=True)
    return merge(reports_dir, out_dir)[0]
