"""The type-resolution classpath for PMD, taken from a saved build of this exact head.

`cpr build` records `classpath: {classes: [dirs], jars: [files]}` in the run's status.json when it keeps the
compiled tree. Without a run for this head, a failed build, or paths that no longer exist, PMD runs without
type info and the report says so: type-resolving rules (CloseResource, UnusedPrivateMethod, ...) may misfire.
"""

import os

from cpr import buildresult

NO_TYPES = "without type info: rules that resolve types may misfire"


def resolve(work_dir, number, head):
    """-> (classpath string or None, note). The note is always set: it says why type info was or was not used."""
    run = buildresult.load(work_dir, number, head)
    if not run:
        return None, "no build of this head; " + NO_TYPES
    if run.get("status") in ("not-built", "build-failed"):
        return None, f"build of this head: {run['status']}; " + NO_TYPES
    cp = run.get("classpath")
    if not isinstance(cp, dict):
        return None, "the build of this head did not keep its classes and jars; " + NO_TYPES
    classes = [p for p in cp.get("classes") or [] if isinstance(p, str) and os.path.isdir(p)]
    jars = [p for p in cp.get("jars") or [] if isinstance(p, str) and os.path.isfile(p)]
    if not classes:
        return None, "the build's classes directory is gone; " + NO_TYPES
    return os.pathsep.join(classes + jars), f"with type info from the build ({len(classes)} classes dir, {len(jars)} jars)"
