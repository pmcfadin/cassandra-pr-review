"""Project profiles: what differs between apache/cassandra and its subprojects (repo, JIRA keys, path layout).

A bundle names its project in `meta.project`. Bundles saved before profiles existed carry only `meta.repo`,
and anything with neither is apache/cassandra.
"""

import functools
import json
import os
import re

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config", "projects")
DEFAULT = "cassandra"
_REF_RE = re.compile(r"^(?:(?P<project>[\w.-]+(?:/[\w.-]+)?)#)?(?P<number>\d+)$")
_URL_RE = re.compile(r"^https://github\.com/(?P<project>[\w.-]+/[\w.-]+)/pull/(?P<number>\d+)/?$")


class ProjectError(Exception):
    pass


class Project:
    def __init__(self, data):
        self.data = data
        self.slug = data["slug"]
        self.repo = data["repo"]
        self.name = data["name"]
        self.jira_keys = tuple(data["jira_keys"])
        self.key_digits = data.get("key_digits", 1)
        self.bare_number_branch_key = bool(data.get("bare_number_branch_key"))
        self.ci_provider = data.get("ci_provider", "jira-ci-summary")
        self.disabled_checks = frozenset(data.get("disabled_checks", ()))
        self.labplan = bool(data.get("labplan"))
        self.docs_dir = data.get("docs_dir")
        self.commit_subject_key = data.get("commit_subject_key", "forbidden")
        self.commands = data.get("commands", {})
        self.static = data.get("static", {})
        self.triage = data.get("triage", {})
        self.not_checked = list(data.get("not_checked", ()))
        lens = data.get("lenses", {})
        self.lens_standards = lens.get("standards", "docs/research/cassandra-standards.md")
        self.lens_testing_doc = lens.get("testing_doc", "docs/report/testing.md")
        self.lens_guides = {p: tuple(names) for p, names in lens.get("guides", {}).items()}
        self.lens_drop = frozenset(lens.get("drop", ()))
        self.build = data.get("build") or {}

    @property
    def key_n(self):
        """The placeholder ticket key in messages: CASSANDRA-N, CASSSIDECAR-N."""
        return f"{self.jira_keys[0]}-N"

    @property
    def key_placeholder(self):
        """How a key is written where the text shows its form: CASSANDRA-NNNNN, CASSSIDECAR-N."""
        return self.data.get("key_placeholder") or self.key_n

    @functools.cached_property
    def compat_surfaces(self):
        return [(name, re.compile(rx)) for name, rx in self.data.get("compat_surfaces", ())]

    @functools.cached_property
    def static_scope(self):
        """(main, test) regex lists for the Java files static analysis checks as main and test code."""
        st = self.static
        return [re.compile(r) for r in st.get("main", ())], [re.compile(r) for r in st.get("test", ())]

    def static_kind(self, path):
        """"main", "test" or None: which checkstyle config applies to a changed file."""
        main, test = self.static_scope
        if any(r.search(path) for r in main):
            return "main"
        if any(r.search(path) for r in test):
            return "test"
        return None

    @property
    def clone_name(self):
        """Directory name of the project's clone under the work dir: the repository name."""
        return self.repo.split("/")[1]

    @functools.cached_property
    def paths(self):
        from cpr import paths
        return paths.Classifier(self.data["paths"])

    def summary(self):
        """The part of the profile the report model carries."""
        return {"slug": self.slug, "repo": self.repo, "name": self.name, "suite_labels": self.paths.suite_labels(),
                "ci_provider": self.ci_provider}

    def __repr__(self):
        return f"Project({self.slug})"


def slugs():
    return sorted(n[:-5] for n in os.listdir(CONFIG_DIR) if n.endswith(".json"))


@functools.lru_cache(maxsize=None)
def load(slug):
    path = os.path.join(CONFIG_DIR, f"{slug}.json")
    if not re.fullmatch(r"[a-z][a-z0-9-]*", slug or "") or not os.path.exists(path):
        raise ProjectError(f"unknown project '{slug}' (known: {', '.join(slugs())})")
    with open(path) as f:
        return Project(json.load(f))


def by_repo(repo):
    for slug in slugs():
        p = load(slug)
        if p.repo.lower() == (repo or "").lower():
            return p
    raise ProjectError(f"no project for repository '{repo}' (known: {', '.join(load(s).repo for s in slugs())})")


def lookup(name):
    """A project by slug or by `owner/repo`."""
    return by_repo(name) if "/" in name else load(name)


def of(bundle):
    meta = (bundle or {}).get("meta") or {}
    if meta.get("project"):
        return load(meta["project"])
    if meta.get("repo"):
        return by_repo(meta["repo"])
    return load(DEFAULT)


def parse_ref(text, project=None):
    """(Project, PR number) from `5201`, `sidecar#397`, `apache/cassandra-sidecar#397` or a PR URL.

    `project` (a slug or repo, e.g. from --project) names the project of a bare number and must agree with one
    named in the reference.
    """
    text = (text or "").strip()
    m = _REF_RE.match(text) or _URL_RE.match(text)
    if not m:
        raise ProjectError(f"'{text}' is not a PR reference: use 5201, sidecar#397, apache/cassandra-sidecar#397 "
                           "or a pull request URL")
    named = lookup(m["project"]) if m["project"] else None
    given = lookup(project) if project else None
    if named and given and named.slug != given.slug:
        raise ProjectError(f"'{text}' is a {named.slug} PR but --project is {given.slug}")
    return named or given or load(DEFAULT), int(m["number"])
