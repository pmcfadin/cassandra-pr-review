"""Build the static GitHub Pages site: an index of every report plus the reports themselves.

Layout of the output directory:

    index.html            list of reports, newest first
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

_MODEL_RE = re.compile(r'<script id="report-model">window\.REPORT_MODEL = (.*?);</script>', re.S)

VERDICT_STATUS = {
    "ready": "pass", "requirements-met-unreviewed": "pass", "awaiting-review": "info", "draft": "info",
    "needs-work": "warn", "insufficient-evidence": "unknown", "needs-contributor-work": "fail",
}


def read_model(report_path):
    """The report model embedded in a rendered report, or None."""
    with open(report_path) as f:
        m = _MODEL_RE.search(f.read())
    if not m:
        return None
    return json.loads(m.group(1))


def summarize(model):
    pr, rec, review = model["pr"], model["recommendation"], model.get("review") or {}
    counts = review.get("issue_counts") or review.get("counts") or {}
    noun = "issues" if review.get("issue_counts") else "findings"
    return {
        "number": pr["number"], "title": pr["title"], "author": pr["author"], "base": pr["base"],
        "url": pr["url"], "jira": (model.get("jira_key") or {}).get("key"),
        "verdict": rec["verdict"], "label": rec["label"], "triage": model["triage"]["rating"],
        "generated_at": model["generated_at"],
        "review": "not run" if review.get("status") != "ran" else
        f"{counts.get('blocker', 0)} blocker · {counts.get('major', 0)} major · "
        f"{counts.get('minor', 0)} minor · {counts.get('nit', 0)} nit {noun}",
    }


def index_html(rows):
    def e(s):
        return html.escape(str(s if s is not None else ""), quote=True)

    items = []
    for r in rows:
        st = VERDICT_STATUS.get(r["verdict"], "unknown")
        jira = f'<a href="https://issues.apache.org/jira/browse/{e(r["jira"])}">{e(r["jira"])}</a>' if r["jira"] else "no ticket"
        items.append(f"""
      <li class="row s-{st}">
        <a class="main" href="pr/{e(r['number'])}/">
          <span class="num">#{e(r['number'])}</span>
          <span class="title">{e(r['title'])}</span>
        </a>
        <div class="meta">
          <span class="badge s-{st}">{e(r['label'])}</span>
          <span class="tag">triage: {e(r['triage'])}</span>
          <span class="tag">code review: {e(r['review'])}</span>
        </div>
        <div class="sub">{e(r['author'])} → <code>{e(r['base'])}</code> · {jira} ·
          <a href="{e(r['url'])}">GitHub PR</a> · generated {e(r['generated_at'])}</div>
      </li>""")
    body = "\n".join(items) or '<li class="empty">No reports yet.</li>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Cassandra PR Reviews</title>
<style>
:root {{
  --bg: #e9edf1; --panel: #ffffff; --ink: #16202a; --ink-2: #44525f; --rule: #d3d9df; --accent: #245a8c;
  --pass: #17663f; --pass-bg: #e2f1e8; --warn: #855600; --warn-bg: #fbefd6; --fail: #b0251d; --fail-bg: #fbe5e2;
  --unknown: #5c4799; --unknown-bg: #ebe6f6; --info: #2c5d7f; --info-bg: #e2edf5;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #0d1217; --panel: #151c23; --ink: #e3e9ef; --ink-2: #a3b0bc; --rule: #2a343e; --accent: #7fb2e5;
    --pass: #6fcf97; --pass-bg: #15301f; --warn: #f0b955; --warn-bg: #33270f; --fail: #ff8a80; --fail-bg: #3a1714;
    --unknown: #b9a6f2; --unknown-bg: #241d3a; --info: #8cc4ea; --info-bg: #13283a;
  }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.5 var(--sans); }}
main {{ max-width: 980px; margin: 0 auto; padding: 32px 16px 64px; }}
h1 {{ margin: 0 0 4px; font-size: 28px; letter-spacing: -0.02em; }}
.lede {{ margin: 0 0 24px; color: var(--ink-2); }}
a {{ color: var(--accent); }}
ul {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }}
.row {{ background: var(--panel); border: 1px solid var(--rule); border-left: 5px solid var(--c, var(--rule));
        border-radius: 6px; padding: 14px 16px; }}
.s-pass {{ --c: var(--pass); --cb: var(--pass-bg); }} .s-warn {{ --c: var(--warn); --cb: var(--warn-bg); }}
.s-fail {{ --c: var(--fail); --cb: var(--fail-bg); }} .s-unknown {{ --c: var(--unknown); --cb: var(--unknown-bg); }}
.s-info {{ --c: var(--info); --cb: var(--info-bg); }}
.main {{ display: flex; gap: 10px; text-decoration: none; color: var(--ink); font-weight: 650; font-size: 16px; }}
.main:hover .title {{ text-decoration: underline; }}
.num {{ font-family: var(--mono); color: var(--ink-2); flex: none; }}
.meta {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0 6px; }}
.badge {{ background: var(--cb); color: var(--c); border: 1px solid var(--c); border-radius: 999px; padding: 1px 10px;
          font-size: 13px; font-weight: 650; }}
.tag {{ border: 1px solid var(--rule); border-radius: 999px; padding: 1px 10px; font-size: 13px; color: var(--ink-2); }}
.sub {{ font-size: 13px; color: var(--ink-2); overflow-wrap: anywhere; }}
code {{ font-family: var(--mono); font-size: 12.5px; }}
footer {{ margin-top: 28px; font-size: 13px; color: var(--ink-2); }}
</style>
</head>
<body>
<main>
  <h1>Cassandra PR Reviews</h1>
  <p class="lede">Reports on <a href="https://github.com/apache/cassandra/pulls">apache/cassandra</a> pull requests:
    merge requirements, review difficulty, and AI code review findings. Each report is advisory; committers decide.</p>
  <ul>{body}
  </ul>
  <footer>Generated by <a href="https://github.com/pmcfadin/cassandra-pr-review">cassandra-pr-review</a> {e(VERSION)}.</footer>
</main>
</body>
</html>
"""


def build(reports_dir, out_dir):
    """Copy every reports/<N>/index.html into out_dir/pr/<N>/ and write the index. Returns the rows."""
    rows = []
    for path in glob.glob(os.path.join(reports_dir, "*", "index.html")):
        model = read_model(path)
        if not model:
            continue
        row = summarize(model)
        dest = os.path.join(out_dir, "pr", str(row["number"]))
        os.makedirs(dest, exist_ok=True)
        shutil.copyfile(path, os.path.join(dest, "index.html"))
        rows.append(row)
    rows.sort(key=lambda r: r["number"], reverse=True)
    with open(os.path.join(out_dir, "index.html"), "w") as f:
        f.write(index_html(rows))
    open(os.path.join(out_dir, ".nojekyll"), "w").close()
    return rows
