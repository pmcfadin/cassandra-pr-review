"""Compatibility surfaces: config, system properties, protocol, CQL, nodetool, JMX/metrics, vtables."""

import re

from cpr.checks import Result, check, ev

SURFACES = [
    ("config", re.compile(r"^(conf/cassandra[^/]*\.yaml|src/java/org/apache/cassandra/config/Config\.java)$")),
    ("native protocol", re.compile(r"^(src/java/org/apache/cassandra/transport/|doc/native_protocol)")),
    ("CQL grammar", re.compile(r"^src/antlr/")),
    ("CQL semantics", re.compile(r"^src/java/org/apache/cassandra/cql3/")),
    ("messaging", re.compile(r"^src/java/org/apache/cassandra/net/")),
    ("sstable format", re.compile(r"^src/java/org/apache/cassandra/io/sstable/")),
    ("commitlog / hints", re.compile(r"^src/java/org/apache/cassandra/(db/commitlog|hints)/")),
    ("schema / system tables", re.compile(r"^src/java/org/apache/cassandra/(schema/|db/SystemKeyspace)")),
    ("nodetool", re.compile(r"^src/java/org/apache/cassandra/tools/nodetool/")),
    ("JMX", re.compile(r"MBean\.java$")),
    ("metrics", re.compile(r"^src/java/org/apache/cassandra/metrics/")),
    ("virtual tables", re.compile(r"^src/java/org/apache/cassandra/db/virtual/")),
    ("guardrails", re.compile(r"^src/java/org/apache/cassandra/db/guardrails/")),
    ("dependencies", re.compile(r"^(\.build/(build-resolve|parent-pom-template|cassandra-deps-template|cassandra-build-deps-template)\.xml|lib/)")),
]
_SYSPROP_RE = re.compile(r"System\.(getProperty|setProperty|getenv)\s*\(|\b(Integer\.getInteger|Long\.getLong|Boolean\.getBoolean)\s*\(")


def touched_surfaces(paths):
    out = {}
    for p in paths:
        for name, rx in SURFACES:
            if rx.search(p):
                out.setdefault(name, []).append(p)
    return out


@check("compat.config-pairing", "Config changes update both yaml files", "compatibility", "compatibility", blocking=True)
def config_pairing(bundle, ctx):
    names = set(ctx.paths)
    yaml, latest, config = "conf/cassandra.yaml", "conf/cassandra_latest.yaml", "src/java/org/apache/cassandra/config/Config.java"
    if not names & {yaml, latest, config}:
        return Result("not-applicable", "No configuration files changed")
    changed = [ev(f"`{p}` changed", location=p) for p in (yaml, latest, config) if p in names]
    has_latest = bundle["base_files"].get("has_cassandra_latest_yaml", True)
    if not has_latest:
        return Result("not-applicable", f"`{ctx.pr['base']}` has no `{latest}`; only `{yaml}` applies", changed)
    if yaml in names and latest not in names:
        return Result("fail", f"`{yaml}` changed but `{latest}` did not", changed,
                      action=f"Make the matching change in `{latest}` too. New and renamed settings must appear in "
                             "both files; only the default values may differ.")
    if latest in names and yaml not in names:
        return Result("pass", f"Only `{latest}` changed; its defaults may differ from `{yaml}` on purpose", changed)
    if config in names and not (yaml in names or latest in names):
        return Result("warn", "`Config.java` changed but neither yaml file did", changed,
                      action="If a setting was added or renamed, document it in both `cassandra.yaml` and "
                             "`cassandra_latest.yaml` (use `@Replaces` for renames).",
                      action_required=False)
    return Result("pass", "Both yaml files changed together", changed)


@check("compat.system-properties", "System properties go through CassandraRelevantProperties", "compatibility",
       "compatibility", blocking=False)
def system_properties(bundle, ctx):
    hits = []
    for path, info in ctx.added.items():
        if not path.startswith("src/java/") or path.endswith("CassandraRelevantProperties.java"):
            continue
        for n, text in info["added"]:
            if _SYSPROP_RE.search(text) and not text.strip().startswith(("//", "*")):
                hits.append(ev(f"`{path}:{n}`", location=f"{path}:{n}"))
    if hits:
        return Result("warn", f"{len(hits)} direct system property read(s)", hits,
                      action="Declare the property in `CassandraRelevantProperties` and read it from there.")
    return Result("pass", "No direct system property access added")


@check("compat.nodetool-help", "nodetool changes update help fixtures", "compatibility", "compatibility", blocking=False)
def nodetool_help(bundle, ctx):
    tool = [p for p in ctx.paths if p.startswith("src/java/org/apache/cassandra/tools/nodetool/")]
    if not tool:
        return Result("not-applicable", "No nodetool commands changed")
    fixtures = [p for p in ctx.paths if p.startswith("test/resources/nodetool/help/")]
    if fixtures:
        return Result("pass", f"{len(fixtures)} nodetool help fixture(s) updated")
    return Result("warn", "nodetool code changed but no help fixture under `test/resources/nodetool/help/` did",
                  [ev(f"`{p}`", location=p) for p in tool],
                  action="If options or help text changed, update the fixtures (NodetoolHelpCommandsOutputTest "
                         "checks them) and the nodetool docs.",
                  action_required=False)


@check("compat.surfaces", "Compatibility surfaces touched", "compatibility", "compatibility", blocking=False,
       owner="reviewer")
def surfaces(bundle, ctx):
    found = touched_surfaces(ctx.paths)
    if not found:
        return Result("pass", "No public or on-disk compatibility surface touched")
    rows = [ev(f"**{name}**: " + ", ".join(f"`{p}`" for p in ps[:5]) + (f" (+{len(ps) - 5} more)" if len(ps) > 5 else ""))
            for name, ps in found.items()]
    return Result("warn", "Touches " + ", ".join(found), rows, action_required=False,
                  action="Reviewers: check version gating, upgrade paths, docs, and NEWS.txt for these surfaces.")
