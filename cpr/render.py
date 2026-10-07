"""Inject a validated report model into the static template and write the HTML file."""

import json
import os

from cpr.model import ASPECTS, validate

TEMPLATE = os.path.join(os.path.dirname(__file__), "assets", "report.html")
MARKER = "<!--REPORT_MODEL-->"
DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "report")


class RenderError(Exception):
    pass


def load_docs(directory=DOCS_DIR, aspects=ASPECTS):
    docs = {}
    for aspect in aspects:
        path = os.path.join(directory, f"{aspect}.md")
        if not os.path.exists(path):
            raise RenderError(f"missing aspect document: {path}")
        with open(path) as f:
            docs[aspect] = f.read()
    return docs


def script_tag(model):
    # ASCII-only JSON with every "<" escaped, so no text inside (diffs, PR bodies) can close or open
    # a script element, including the "<!--<script" double-escape trap. Same rule as dev-skills html_shell.py.
    payload = json.dumps(model, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    return f'<script id="report-model">window.REPORT_MODEL = {payload};</script>'


def render_html(model, template_path=TEMPLATE):
    validate(model)
    with open(template_path) as f:
        template = f.read()
    if template.count(MARKER) != 1:
        raise RenderError(f"template must contain exactly one {MARKER}")
    return template.replace(MARKER, script_tag(model))


def write(model, out_path, template_path=TEMPLATE):
    html = render_html(model, template_path)  # raises before anything is written
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "w") as f:
        f.write(html)
    os.replace(tmp, out_path)
    return os.path.abspath(out_path)
