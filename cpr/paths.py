"""Classify apache/cassandra paths: production code, tests, docs, generated files."""

TEST_SUITES = {
    "test/unit/": "unit",
    "test/distributed/": "distributed",
    "test/burn/": "burn",
    "test/long/": "long",
    "test/microbench/": "microbench",
    "test/simulator/": "simulator",
    "test/harry/": "harry",
    "test/memory/": "memory",
    "test/anttasks/": "anttasks",
    "pylib/cqlshlib/test/": "cqlsh",
}


def is_prod(path):
    return path.startswith(("src/java/", "pylib/")) and not is_test(path)


def is_test(path):
    return path.startswith("test/") or "/test/" in path or path.startswith("pylib/cqlshlib/test/")


def is_test_resource(path):
    return path.startswith(("test/resources/", "test/data/", "test/conf/"))


def is_generated(path):
    return path.startswith("src/gen-java/") or path.endswith((".db", ".bin")) or "/gen/" in path


def is_doc(path):
    return path.startswith("doc/") or (path.endswith((".adoc", ".md")) and not path.startswith("src/"))


def is_build(path):
    return path.startswith((".build/", ".circleci/", ".jenkins/", "build.xml", "ide/", ".github/"))


def test_suite(path):
    for prefix, suite in TEST_SUITES.items():
        if path.startswith(prefix):
            return suite
    return "other" if is_test(path) else None


def subsystem(path):
    """Top-level package under org.apache.cassandra, e.g. "db", "service", "net"."""
    marker = "org/apache/cassandra/"
    i = path.find(marker)
    if i < 0:
        return None
    rest = path[i + len(marker):].split("/")
    return rest[0] if len(rest) > 1 else "(root)"


def counted(f):
    """Whether a changed file counts toward review size (generated and test data do not)."""
    return not (is_generated(f["path"]) or is_test_resource(f["path"]) or f.get("binary"))
