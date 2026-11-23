"""Classify a project's paths: production code, tests, docs, generated files.

The rules come from the project profile (`paths` in cpr/config/projects/<slug>.json). Code that has a bundle
uses `of(bundle)`; the module-level functions apply apache/cassandra's rules.
"""

import re


class Classifier:
    def __init__(self, cfg):
        def compile_all(key):
            return [re.compile(p) for p in cfg.get(key, [])]

        self._prod, self._test = compile_all("prod"), compile_all("test")
        self._resources, self._generated = compile_all("test_resources"), compile_all("generated")
        self._doc, self._build = compile_all("doc"), compile_all("build")
        self._suites = [(re.compile(p), suite, label) for p, suite, label in cfg.get("suites", [])]
        self._subsystem = cfg.get("subsystem") or {"kind": "module"}

    @staticmethod
    def _any(patterns, path):
        return any(p.search(path) for p in patterns)

    def is_prod(self, path):
        return self._any(self._prod, path) and not self.is_test(path)

    def is_test(self, path):
        return self._any(self._test, path)

    def is_test_resource(self, path):
        return self._any(self._resources, path)

    def is_generated(self, path):
        return self._any(self._generated, path)

    def is_doc(self, path):
        return self._any(self._doc, path)

    def is_build(self, path):
        return self._any(self._build, path)

    def test_suite(self, path):
        for pattern, suite, _ in self._suites:
            if pattern.search(path):
                return suite
        return "other" if self.is_test(path) else None

    def suite_labels(self):
        """{suite: label} in profile order, first label of each suite; `other` last."""
        labels = {}
        for _, suite, label in self._suites:
            labels.setdefault(suite, label)
        labels.setdefault("other", "Other tests")
        return labels

    def subsystem(self, path):
        """Cassandra: the top-level package under org.apache.cassandra ("db", "service", ...).
        Gradle projects: the module, i.e. the path before `/src/` ("server", "adapters/adapters-base")."""
        if self._subsystem.get("kind") == "package":
            marker = self._subsystem["root"]
            i = path.find(marker)
            if i < 0:
                return None
            rest = path[i + len(marker):].split("/")
            return rest[0] if len(rest) > 1 else "(root)"
        i = path.find("/src/")
        if path.startswith("src/"):
            return "(root)"
        return path[:i] if i > 0 else None

    def counted(self, f):
        """Whether a changed file counts toward review size (generated and test data do not)."""
        return not (self.is_generated(f["path"]) or self.is_test_resource(f["path"]) or f.get("binary"))


def of(bundle):
    from cpr import project
    return project.of(bundle).paths


def _cassandra():
    from cpr import project
    return project.load("cassandra").paths


def is_prod(path):
    return _cassandra().is_prod(path)


def is_test(path):
    return _cassandra().is_test(path)


def is_test_resource(path):
    return _cassandra().is_test_resource(path)


def is_generated(path):
    return _cassandra().is_generated(path)


def is_doc(path):
    return _cassandra().is_doc(path)


def is_build(path):
    return _cassandra().is_build(path)


def test_suite(path):
    return _cassandra().test_suite(path)


def subsystem(path):
    return _cassandra().subsystem(path)


def counted(f):
    return _cassandra().counted(f)
