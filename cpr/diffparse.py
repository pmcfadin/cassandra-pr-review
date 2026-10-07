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


_HUNK_FULL_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def old_side_hunks(diff_text, context=3):
    """Base-side line ranges to blame, per hunk.

    Returns [{"path": old path, "new_path", "start", "end", "kind": "changed"|"insertion", "lines"}].
    For hunks that modify or delete lines, the range covers the deleted ('-') lines. For hunks that
    only add lines, it covers `context` base lines on each side of the insertion point. New files
    (old side /dev/null) have nothing to blame and are skipped.
    """
    out = []
    old_path = new_path = None
    hunk = None
    old_line = 0

    def close():
        if hunk is None:
            return
        if hunk["deleted"]:
            out.append({"path": hunk["old_path"], "new_path": hunk["new_path"], "start": min(hunk["deleted"]),
                        "end": max(hunk["deleted"]), "kind": "changed", "lines": len(hunk["deleted"])})
        elif hunk["added"]:
            at = hunk["insert_after"]
            out.append({"path": hunk["old_path"], "new_path": hunk["new_path"], "start": max(1, at - context + 1),
                        "end": at + context, "kind": "insertion", "lines": 0})

    in_header = False
    for raw in (diff_text or "").split("\n"):
        if raw.startswith("diff --git "):
            close()
            hunk, old_path, new_path, in_header = None, None, None, True
            continue
        if in_header:
            if raw.startswith("--- "):
                t = raw[4:]
                old_path = None if t == "/dev/null" else (t[2:] if t.startswith("a/") else t)
            elif raw.startswith("+++ "):
                t = raw[4:]
                new_path = None if t == "/dev/null" else (t[2:] if t.startswith("b/") else t)
                in_header = False
            continue
        m = _HUNK_FULL_RE.match(raw)
        if m:
            close()
            hunk = None
            if old_path is None:
                continue
            old_start, old_count = int(m.group(1)), int(m.group(2) or 1)
            # "-40,0" means "insert after line 40": the next base line is 41.
            old_line = old_start + 1 if old_count == 0 else old_start
            insert_after = old_line - 1
            hunk = {"old_path": old_path, "new_path": new_path, "deleted": [], "added": 0,
                    "insert_after": insert_after}
            continue
        if hunk is None:
            continue
        if raw.startswith("-"):
            hunk["deleted"].append(old_line)
            old_line += 1
        elif raw.startswith("+"):
            if not hunk["deleted"] and not hunk["added"]:
                hunk["insert_after"] = old_line - 1
            hunk["added"] += 1
        elif raw.startswith(" "):
            old_line += 1
    close()
    return out
