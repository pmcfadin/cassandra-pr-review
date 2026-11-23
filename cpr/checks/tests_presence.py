"""Does a PR that changes production code also change tests?"""

from cpr import paths
from cpr.checks import Result, check, ev


def test_summary(files, classify=paths):
    prod_lines = sum(f["additions"] + f["deletions"] for f in files if classify.is_prod(f["path"]))
    test_lines = sum(f["additions"] + f["deletions"] for f in files
                     if classify.is_test(f["path"]) and not classify.is_test_resource(f["path"]))
    suites = {}
    for f in files:
        s = classify.test_suite(f["path"])
        if s:
            suites.setdefault(s, []).append(f["path"])
    return prod_lines, test_lines, suites


@check("tests.present", "Tests accompany production changes", "tests", "testing", blocking=True)
def present(bundle, ctx):
    files = ctx.files
    prod_lines, test_lines, suites = test_summary(files, ctx.classify)
    if prod_lines == 0:
        return Result("not-applicable", "No production code changed")
    rows = [ev(f"production lines changed: {prod_lines}; test lines changed: {test_lines}")]
    rows += [ev(f"{suite}: {len(fs)} file(s)", location=fs[0]) for suite, fs in sorted(suites.items())]
    if not suites:
        return Result("fail", "Production code changed with no test changes", rows,
                      action=ctx.project.commands["test_advice"])
    ratio = test_lines / prod_lines if prod_lines else 0
    return Result("pass", f"Tests changed in {', '.join(sorted(suites))} (test/prod line ratio {ratio:.2f})", rows)
