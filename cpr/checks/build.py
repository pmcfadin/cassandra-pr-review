"""Checks that read the saved `cpr build` result for the PR's current head (bundle["build"]).

Nothing here builds anything. No result for this head, or a result for another head, means "not built":
the checks are not-applicable and never block. Unknown never blocks either, and a check never passes
without proof that the build or tests ran.
"""

from cpr.checks import Result, check, ev

NOT_BUILT = "not built"
MAX_ROWS = 20


def _run(bundle):
    """The saved result when it is for the PR's current head and the build was attempted, else None."""
    b = bundle.get("build")
    if not isinstance(b, dict) or b.get("status") in (None, "not-built"):
        return None
    if b.get("head") != bundle["pr"].get("head_sha"):
        return None
    return b


def _not_built(bundle):
    b = bundle.get("build")
    reason = NOT_BUILT
    if isinstance(b, dict) and b.get("status") == "not-built" and b.get("head") in (None, bundle["pr"].get("head_sha")) \
            and b.get("reason"):
        reason = f"{NOT_BUILT}: {b['reason']}"
    return Result("not-applicable", reason)


def _unknown(summary, evidence=None):
    # Unknown never blocks: the build could not tell us anything about the PR.
    return Result("unknown", summary, evidence, blocking=False)


def _compile_rows(b):
    rows = []
    for e in (b.get("compile_errors") or [])[:MAX_ROWS]:
        if isinstance(e, dict):
            loc = f"{e.get('file')}:{e.get('line')}" if e.get("line") else str(e.get("file") or "")
            rows.append(ev(f"`{loc}` {e.get('message', '')}".strip(), location=loc or None))
        else:
            rows.append(ev(str(e)))
    return rows


@check("build.compiles", "The PR branch compiles", "build", "build", blocking=True)
def compiles(bundle, ctx):
    b = _run(bundle)
    if b is None:
        return _not_built(bundle)
    st = b["status"]
    if st == "build-failed":
        rows = _compile_rows(b) or [ev(b.get("reason") or "the build failed")]
        n = len(b.get("compile_errors") or [])
        return Result("fail", f"The build failed with {n} compile error(s)" if n else "The build failed", rows,
                      action="Fix the compile errors; run `ant jar` and `ant build-test` on the branch to confirm.")
    if st == "timeout":
        return _unknown("The run timed out before the build outcome was recorded", [ev(b.get("reason") or "timeout")])
    if st == "unknown" and not b.get("tests"):
        return _unknown(b.get("reason") or "The build outcome could not be determined")
    t = b.get("tests") or {}
    where = f" ({b['jdk']})" if b.get("jdk") else ""
    detail = f"; {t.get('run')} tests ran" if t.get("run") is not None else ""
    return Result("pass", f"The PR branch compiled{where}{detail}")


def _is_sandbox(failure, unknowns):
    cls, test = failure.get("class"), failure.get("test")
    for u in unknowns or []:
        if isinstance(u, dict):
            if u.get("class") == cls and (u.get("test") in (None, test)):
                return True
        elif isinstance(u, str) and cls and cls in u and (not test or test in u):
            return True
    return False


def _fail_row(f):
    msg = str(f.get("message") or "").strip()
    return ev(f"`{f.get('class')}.{f.get('test')}`" + (f": {msg}" if msg else ""),
              location=f.get("class"))


@check("build.tests-pass", "The selected unit tests pass", "build", "build", blocking=True)
def tests_pass(bundle, ctx):
    b = _run(bundle)
    if b is None:
        return _not_built(bundle)
    st = b["status"]
    if st == "build-failed":
        return Result("not-applicable", "the build failed, so no tests ran")
    if st == "timeout":
        return _unknown(b.get("reason") or "The test run timed out", [ev(b.get("reason") or "timeout")])
    t = b.get("tests")
    if not isinstance(t, dict):
        return _unknown(b.get("reason") or "No test results were recorded")
    unknowns = b.get("sandbox_unknowns") or []
    fails = [f for f in t.get("failures") or [] if not _is_sandbox(f, unknowns)]
    sandboxed = [f for f in t.get("failures") or [] if _is_sandbox(f, unknowns)]
    counts = f"{t.get('run')} tests in {t.get('classes')} classes"
    if st == "tests-failed":
        rows = [_fail_row(f) for f in fails[:MAX_ROWS]]
        if fails or not unknowns:
            n = len(fails) or (t.get("failed", 0) + t.get("errors", 0))
            return Result("fail", f"{n} selected test(s) failed ({counts})",
                          rows or [ev(b.get("reason") or "failures were not itemised")],
                          action="Fix the failing tests, or explain on the ticket why they fail without this change "
                                 "too; run them with `ant testsome -Dtest.name=<class> -Dtest.methods=<method>`.")
    flaky = b.get("flaky") or []
    if st == "unknown" or unknowns or sandboxed or flaky:
        rows = [ev(f"flaky: `{f.get('class')}.{f.get('test')}` failed once, passed on retry: {f.get('message', '')}")
                for f in flaky]
        rows += [_fail_row(f) for f in sandboxed] + [ev(str(u)) for u in unknowns if not isinstance(u, dict)]
        rows += [_fail_row(f) for f in fails]
        if fails and st != "unknown":
            return Result("fail", f"{len(fails)} selected test(s) failed ({counts})", rows[:MAX_ROWS],
                          action="Fix the failing tests; run them with `ant testsome -Dtest.name=<class>`.")
        what = "Flaky tests failed once and passed on retry" if flaky and not fails else \
            "Only sandbox artifacts failed or the run is inconclusive"
        return _unknown(what + "; the tests were not proven to pass"
                        + (f" ({counts})" if t.get("run") is not None else ""), rows)
    if t.get("run") in (None, 0):
        return _unknown("No tests ran")
    if (t.get("failed") or 0) + (t.get("errors") or 0) > 0:
        return Result("fail", f"{(t.get('failed') or 0) + (t.get('errors') or 0)} test failure(s) ({counts})",
                      [_fail_row(f) for f in fails[:MAX_ROWS]],
                      action="Fix the failing tests; run them with `ant testsome -Dtest.name=<class>`.")
    skipped = f", {t['skipped']} skipped" if t.get("skipped") else ""
    return Result("pass", f"All {counts} passed{skipped}")


@check("build.changed-line-coverage", "Changed lines run under the selected tests", "build", "build",
       blocking=False)
def changed_line_coverage(bundle, ctx):
    b = _run(bundle)
    if b is None:
        return _not_built(bundle)
    if b["status"] == "build-failed":
        return Result("not-applicable", "the build failed, so no coverage was measured")
    total, files = b.get("changed_total"), b.get("changed_lines")
    if not isinstance(total, dict) or not isinstance(files, dict):
        return _unknown("Coverage was not measured for this run")
    if not total.get("executable"):
        return Result("not-applicable", "No added executable lines under src/java")
    rows, missed_n, unmeasured = [], 0, []
    for path in sorted(files):
        info = files[path]
        if info.get("in_report") is False:
            unmeasured.append(path)
            continue
        cov, part, miss = info.get("covered") or [], info.get("partial") or [], info.get("missed") or []
        n = len(cov) + len(part) + len(miss)
        if not n:
            continue
        missed_n += len(miss)
        text = f"`{path}`: covered {len(cov) + len(part)}/{n}"
        if part:
            text += f" ({len(part)} only partly)"
        if miss:
            text += ", missed lines " + ", ".join(str(x) for x in miss)
        rows.append(ev(text, location=f"{path}:{miss[0]}" if miss else path))
    sel = (b.get("tests") or {}).get("classes")
    scope = f" under {sel} selected test class(es)" if sel else ""
    if missed_n:
        return Result("warn", f"{missed_n} of {total['executable']} added executable line(s) did not run{scope}", rows,
                      action_required=False,
                      action="Check whether a test should reach these lines. Selection is limited, so a miss may be "
                             "a test that was not selected; read with the test regime lens.")
    if unmeasured:
        rows += [ev(f"`{p}` is not in the coverage report", location=p) for p in unmeasured]
        return _unknown(f"Coverage is missing for {len(unmeasured)} changed file(s)", rows)
    return Result("pass", f"All {total['executable']} added executable line(s) ran{scope}", rows)
