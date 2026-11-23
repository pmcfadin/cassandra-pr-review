"""Parse `patch by …; reviewed by … for KEY-N` credit lines and resolve names to ASF committers.

`keys` is the project's JIRA key prefixes (project.jira_keys). Sidecar sometimes writes the key as a markdown
link, `for [CASSSIDECAR-378](https://...)`, so an opening bracket before the key is allowed.
"""

import functools
import json
import os
import re
import unicodedata

ALIASES = os.path.join(os.path.dirname(__file__), "data", "people-aliases.json")
CASSANDRA = ("CASSANDRA",)


@functools.lru_cache(maxsize=None)
def _regexes(keys):
    k = "(?:" + "|".join(map(re.escape, keys)) + r")-\d+"
    # The verb tolerates the typos found in history: reviwed, reviewd, revieewed, reivewed, review by.
    credit = re.compile(rf"patch by (.+?)[;,]\s*re[a-z]*w[a-z]*[- ]by (.+?)(?:\s+for\s+\[?({k})|\s*$|\n\n)",
                        re.IGNORECASE)
    patch_only = re.compile(rf"patch by (.+?)(?:\s+for\s+\[?({k})|\s*$)", re.IGNORECASE)
    for_key = re.compile(rf"\bfor\s+\[?({k})", re.IGNORECASE)
    any_key = re.compile(rf"\b{k}\b", re.IGNORECASE)
    return credit, patch_only, for_key, any_key


_SPLIT_RE = re.compile(r"\s*(?:,|\band\b|&|\+)\s*", re.IGNORECASE)
_PLACEHOLDERS = {"tbd", "tba", "?", "", "none", "n/a"}


def _names(text):
    out = []
    for part in _SPLIT_RE.split(text.strip().rstrip(".")):
        name = part.strip().strip("'\"").strip()
        if name.lower() not in _PLACEHOLDERS:
            out.append(name)
    return out


def parse(message, keys=CASSANDRA):
    """Return {"authors": [...], "reviewers": [...], "key": "KEY-N" | None, "credited": bool}.

    The text is whitespace-collapsed first so lines wrapped mid-credit still parse.
    """
    credit, patch_only, _, _ = _regexes(tuple(keys))
    flat = " ".join((message or "").split())
    m = credit.search(flat)
    if m:
        return {"authors": _names(m.group(1)), "reviewers": _names(m.group(2)),
                "key": m.group(3).upper() if m.group(3) else primary_key(message, keys), "credited": True}
    m = patch_only.search(flat)
    if m:
        return {"authors": _names(m.group(1)), "reviewers": [],
                "key": m.group(2).upper() if m.group(2) else primary_key(message, keys), "credited": True}
    return {"authors": [], "reviewers": [], "key": primary_key(message, keys), "credited": False}


def primary_key(message, keys=CASSANDRA):
    """The ticket a commit belongs to: the `for KEY-N` of its credit line, else the first key."""
    _, _, for_key, any_key = _regexes(tuple(keys))
    flat = " ".join((message or "").split())
    m = for_key.search(flat)
    if m and re.search(r"patch by", flat, re.IGNORECASE):
        return m.group(1).upper()
    m = any_key.search(message or "")
    return m.group(0).upper() if m else None


def normalize(name):
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def load_aliases(path=ALIASES):
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    return {normalize(k): v for k, v in data.get("aliases", {}).items()}


class Resolver:
    """Resolve names, ASF ids, and emails to a person key: the ASF id when known, else the name."""

    def __init__(self, roster, aliases=None):
        self.committers = dict((roster or {}).get("committers") or {})
        self.by_name = {}
        for asf_id, display in self.committers.items():
            self.by_name.setdefault(normalize(display), asf_id)
        self.aliases = aliases if aliases is not None else load_aliases()

    def resolve(self, name, email=None):
        """(person_key, display, asf_id or None)."""
        if email and email.lower().endswith("@apache.org"):
            asf = email.lower().split("@")[0]
            if asf in self.committers:
                return asf, self.committers[asf], asf
        n = normalize(name)
        asf = self.aliases.get(n)
        if asf is None and n.replace(" ", "") in self.committers and " " not in n:
            asf = n
        if asf is None:
            asf = self.by_name.get(n)
        if asf:
            return asf, self.committers.get(asf, name), asf if asf in self.committers else None
        return "name:" + n, name, None
