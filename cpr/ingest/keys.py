"""Find the project's JIRA keys (CASSANDRA-NNNNN, CASSSIDECAR-N, ...) in a PR's title, branch, body, and commits."""

import functools
import re

# Cassandra branch names often carry the bare number ("21649-5.0", "CASSANDRA-21649-trunk", "mck/21649/trunk").
_BRANCH_NUM_RE = re.compile(r"(?:^|[/_-])(\d{4,6})(?=$|[/_-])")

SOURCES = ("title", "branch", "body", "commits")


def _default():
    from cpr import project
    return project.load(project.DEFAULT)


@functools.lru_cache(maxsize=None)
def _key_re(prefixes, digits):
    return re.compile(rf"\b({'|'.join(map(re.escape, prefixes))})[-_ ]?(\d{{{digits},6}})\b", re.IGNORECASE)


def keys_in_text(text, project=None):
    p = project or _default()
    return [f"{k.upper()}-{n}" for k, n in _key_re(p.jira_keys, p.key_digits).findall(text or "")]


def keys_in_branch(branch, project=None):
    p = project or _default()
    found = keys_in_text(branch, p)
    if found or not p.bare_number_branch_key:
        return found
    # A bare 4-6 digit number in the branch name is taken as a ticket number.
    return [f"{p.jira_keys[0]}-{n}" for n in _BRANCH_NUM_RE.findall(branch or "")]


def resolve(title, branch, body, commit_messages, project=None):
    """Return {"key", "sources", "conflicts"}.

    The key is the first one found in precedence order title > branch > body > commits.
    `sources` lists where the chosen key appeared. `conflicts` lists every other key and where.
    """
    found = {
        "title": keys_in_text(title, project),
        "branch": keys_in_branch(branch, project),
        "body": keys_in_text(body, project),
        "commits": [k for msg in commit_messages for k in keys_in_text(msg, project)],
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
