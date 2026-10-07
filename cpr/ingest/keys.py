"""Find CASSANDRA-NNNNN keys in a PR's title, branch, body, and commit messages."""

import re

# Branch names often carry the bare number ("21649-5.0", "CASSANDRA-21649-trunk", "mck/21649/trunk").
_KEY_RE = re.compile(r"\bCASSANDRA[-_ ]?(\d{3,6})\b", re.IGNORECASE)
_BRANCH_NUM_RE = re.compile(r"(?:^|[/_-])(\d{4,6})(?=$|[/_-])")

SOURCES = ("title", "branch", "body", "commits")


def keys_in_text(text):
    return [f"CASSANDRA-{m}" for m in _KEY_RE.findall(text or "")]


def keys_in_branch(branch):
    found = keys_in_text(branch)
    if found:
        return found
    # A bare 4-6 digit number in the branch name is taken as a ticket number.
    return [f"CASSANDRA-{n}" for n in _BRANCH_NUM_RE.findall(branch or "")]


def resolve(title, branch, body, commit_messages):
    """Return {"key", "sources", "conflicts"}.

    The key is the first one found in precedence order title > branch > body > commits.
    `sources` lists where the chosen key appeared. `conflicts` lists every other key and where.
    """
    found = {
        "title": keys_in_text(title),
        "branch": keys_in_branch(branch),
        "body": keys_in_text(body),
        "commits": [k for msg in commit_messages for k in keys_in_text(msg)],
    }
    chosen = None
    for source in SOURCES:
        if found[source]:
            chosen = found[source][0]
            break
    where = {}
    for source in SOURCES:
        for k in found[source]:
            where.setdefault(k, [])
            if source not in where[k]:
                where[k].append(source)
    conflicts = []
    if chosen:
        # A different key in title or branch is a conflict. Bodies and commits often cite related tickets.
        for k, srcs in where.items():
            if k != chosen and ("title" in srcs or "branch" in srcs):
                conflicts.append({"key": k, "sources": srcs})
    return {
        "key": chosen,
        "sources": where.get(chosen, []) if chosen else [],
        "conflicts": conflicts,
        "mentioned": sorted(where),
    }
