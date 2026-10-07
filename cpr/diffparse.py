"""Parse a unified git diff into per-file added lines with their new-file line numbers."""

import re

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def parse(diff_text):
    """Return {path: {"added": [(line_no, text)], "new_file": bool}} for files with a new side."""
    files = {}
    current = None
    old_is_null = False
    new_line = 0
    in_header = False
    for raw in (diff_text or "").split("\n"):
        if raw.startswith("diff --git "):
            current, old_is_null, in_header = None, False, True
            continue
        if in_header:
            if raw.startswith("--- "):
                old_is_null = raw[4:] == "/dev/null"
                continue
            if raw.startswith("+++ "):
                target = raw[4:]
                in_header = False
                if target != "/dev/null":
                    path = target[2:] if target.startswith("b/") else target
                    current = files.setdefault(path, {"added": [], "new_file": old_is_null})
                continue
            continue
        if current is None:
            continue
        m = _HUNK_RE.match(raw)
        if m:
            new_line = int(m.group(1))
        elif raw.startswith("+"):
            current["added"].append((new_line, raw[1:]))
            new_line += 1
        elif raw.startswith(" ") or raw == "":
            new_line += 1
    return files
