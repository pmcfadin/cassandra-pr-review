"""Inject a validated report model into the static template and write the HTML file."""

import base64
import json
import os

from cpr.model import ASPECTS, validate

TEMPLATE = os.path.join(os.path.dirname(__file__), "assets", "report.html")
MARKER = "<!--REPORT_MODEL-->"
FONT_MARKER = "/*REPORT_FONTS*/"
FONTS_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")
DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "report")

# (file, family, unicode-range). Ranges are the Google Fonts latin and latin-ext subsets.
LATIN = ("U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,"
         "U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD")
LATIN_EXT = ("U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,"
             "U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF")
FONTS = (
    ("red-hat-text-latin-ext-wght-normal.woff2", "Red Hat Text", LATIN_EXT),
    ("red-hat-text-latin-wght-normal.woff2", "Red Hat Text", LATIN),
    ("red-hat-mono-latin-wght-normal.woff2", "Red Hat Mono", LATIN),
)


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


def font_faces(directory=FONTS_DIR):
    # Embedded, so the report stays one offline file. A missing font file falls back to system fonts.
    rules = []
    for name, family, unicode_range in FONTS:
        path = os.path.join(directory, name)
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        rules.append(f'@font-face{{font-family:"{family}";font-style:normal;font-display:swap;font-weight:300 700;'
                     f'src:url(data:font/woff2;base64,{data}) format("woff2");unicode-range:{unicode_range};}}')
    return "\n".join(rules)


def render_html(model, template_path=TEMPLATE):
    validate(model)
    with open(template_path) as f:
        template = f.read()
    if template.count(MARKER) != 1:
        raise RenderError(f"template must contain exactly one {MARKER}")
    if FONT_MARKER in template:
        template = template.replace(FONT_MARKER, font_faces(), 1)
    return template.replace(MARKER, script_tag(model))


def write(model, out_path, template_path=TEMPLATE):
    html = render_html(model, template_path)  # raises before anything is written
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "w") as f:
        f.write(html)
    os.replace(tmp, out_path)
    return os.path.abspath(out_path)
