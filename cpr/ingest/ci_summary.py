"""Parse the ci_summary HTML files that `.build/run-ci` produces and people attach to JIRA.

Two layouts are known:

* "classic": "CI results for CASSANDRA-21520-5.0: FAIL", "sha: ...", "JUnit results summary",
  "- Passed: N", "- Failed: N", "- Total: N".
* "totals": "Build State", "sha:", "repo:", "branch:", "profile:", then "[Totals]" followed by
  Passed/Failed/Skipped/Total value pairs and a "[Test Failures]" list.

The parser works on the page's text lines, so cosmetic HTML changes do not break it.
"""

import html
import re
from html.parser import HTMLParser

_SHA_RE = re.compile(r"\b([0-9a-f]{40})\b")
# git's empty-blob hash; some run-ci versions print it when the real sha was not captured.
PLACEHOLDER_SHAS = {"e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"}
_UPGRADE_RE = re.compile(r"upgrade[-_](?:dtest|jdk)", re.IGNORECASE)


class _TextLines(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self._skip += 1
        if tag in ("br", "p", "div", "tr", "td", "th", "li", "h1", "h2", "h3", "h4", "pre", "table"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("style", "script") and self._skip:
            self._skip -= 1
        if tag in ("td", "th", "tr", "p", "div", "li", "h1", "h2", "h3", "h4"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def text_lines(page):
    p = _TextLines()
    p.feed(page)
    p.close()
    text = html.unescape("".join(p.parts))
    return [line.strip() for line in text.split("\n") if line.strip()]


def _int(s):
    try:
        return int(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def _field(lines, name):
    """Value of a "name: value" line, or of the line after a bare "name:" line."""
    prefix = name.lower() + ":"
    for i, line in enumerate(lines):
        if line.lower().startswith(prefix):
            value = line[len(prefix):].strip()
            if value:
                return value
            return None
    return None


def parse(page):
    """Return a dict describing one CI run. Raises ValueError when the page is not a CI summary."""
    lines = text_lines(page)
    if not lines:
        raise ValueError("empty page")
    joined = "\n".join(lines)

    result = {
        "layout": None,
        "sha": None,
        "ref": None,
        "repo": None,
        "profile": None,
        "overall": None,
        "passed": None,
        "failed": None,
        "skipped": None,
        "total": None,
        "failures": [],
        "has_upgrade_tests": bool(_UPGRADE_RE.search(joined)),
        "sha_note": None,
    }

    sha_line = _field(lines, "sha")
    m = _SHA_RE.search(sha_line or "")
    if m:
        result["sha"] = m.group(1)

    head = re.search(r"CI results for\s+(\S+?):\s*(PASS|FAIL\w*)", joined, re.IGNORECASE)
    if head:
        result["layout"] = "classic"
        result["ref"] = head.group(1)
        result["overall"] = head.group(2).upper()
        for name in ("passed", "failed", "total", "skipped"):
            mm = re.search(rf"^-\s*{name}:\s*([\d,]+)", joined, re.IGNORECASE | re.MULTILINE)
            if mm:
                result[name] = _int(mm.group(1))
        result["profile"] = _field(lines, "profile")
    elif "[Totals]" in lines:
        result["layout"] = "totals"
        result["ref"] = _field(lines, "branch")
        result["repo"] = _field(lines, "repo")
        result["profile"] = _field(lines, "profile")
        i = lines.index("[Totals]") + 1
        while i + 1 < len(lines) and not lines[i].startswith("["):
            key = lines[i].lower()
            if key in ("passed", "failed", "skipped", "total"):
                result[key] = _int(lines[i + 1])
                i += 2
            else:
                i += 1
        if "[Test Failures]" in lines:
            j = lines.index("[Test Failures]") + 1
            while j < len(lines) and not lines[j].startswith("["):
                result["failures"].append(lines[j])
                j += 1
        if result["failed"] is not None:
            result["overall"] = "PASS" if result["failed"] == 0 else "FAIL"
    else:
        raise ValueError("not a recognised ci_summary layout")

    if result["sha"] in PLACEHOLDER_SHAS:
        result["sha"] = None
        result["sha_note"] = "summary records a placeholder sha (git empty-blob hash)"
    if result["sha"] is None and result["sha_note"] is None:
        raise ValueError("no tested sha found")
    return result


def is_ci_summary(filename):
    name = filename.lower()
    return "ci_summary" in name and name.endswith((".html", ".htm"))


def is_result_details(filename):
    name = filename.lower()
    return ("result_details" in name or "results_details" in name) and (".tar" in name or name.endswith(".gz"))


_BRANCH_HINTS = [
    (re.compile(r"(?:^|[^0-9.])(4\.0)(?:$|[^0-9])"), "cassandra-4.0"),
    (re.compile(r"(?:^|[^0-9.])(4\.1)(?:$|[^0-9])"), "cassandra-4.1"),
    (re.compile(r"(?:^|[^0-9.])(5\.0)(?:$|[^0-9])"), "cassandra-5.0"),
    (re.compile(r"(?:^|[^0-9.])(6\.0)(?:$|[^0-9])"), "cassandra-6.0"),
    (re.compile(r"trunk", re.IGNORECASE), "trunk"),
]


def guess_target_branch(*texts):
    """Guess the apache base branch a CI run was for from its ref or attachment name."""
    for text in texts:
        if not text:
            continue
        for rx, branch in _BRANCH_HINTS:
            if rx.search(text):
                return branch
    return None
