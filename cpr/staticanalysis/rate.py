"""The second house-style test: is a PMD rule's count on this PR usual for Cassandra?

The branch baseline records each rule's violation count and the lines it scanned. For a PR, a rule's expected
count is the branch's rate (violations per non-blank line) times the PR's added production lines. A rule is
"usual for Cassandra" when the PR's observed production count is not significantly above that expectation:
one-sided Poisson tail P(X >= observed | mean expected) >= `P_USUAL`. A rule the branch never breaks is never usual.
"""

import math
import os

P_USUAL = 0.01


def poisson_tail(k, mu):
    """P(X >= k) for X ~ Poisson(mu), summed from the upper end so small tails keep their precision."""
    if k <= 0:
        return 1.0
    if mu <= 0:
        return 0.0
    term = math.exp(-mu + k * math.log(mu) - math.lgamma(k + 1))
    total, i = term, k
    while True:
        i += 1
        term *= mu / i
        total += term
        if term < total * 1e-16 or i > k + 50 + 20 * mu:
            return min(1.0, total)


def expected(violations, loc, added_loc):
    """Trunk's rate times the PR's added production lines."""
    return violations / loc * added_loc if loc else 0.0


def judge(observed, trunk_violations, loc, added_loc, p_usual=P_USUAL):
    """-> (usual, expected, p). `observed` is the PR's production count for the rule."""
    mu = expected(trunk_violations, loc, added_loc)
    if observed <= 0 or trunk_violations <= 0 or not loc or added_loc <= 0:
        return False, mu, None
    p = poisson_tail(observed, mu)
    return p >= p_usual, mu, p


def nonblank_in(path, ranges=None):
    """Non-blank lines of a file, limited to the 1-based inclusive `ranges` when given."""
    try:
        with open(path, errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return 0
    if ranges is None:
        return sum(1 for ln in lines if ln.strip())
    wanted = set()
    for s, e in ranges:
        wanted.update(range(s, min(e, len(lines)) + 1))
    return sum(1 for n in wanted if n >= 1 and lines[n - 1].strip())


def added_production_loc(changed, head_lines, head_root):
    """Added non-blank lines in the changed production (non-test) Java files of the head.

    New files, and modified files with no line map, count whole.
    """
    total = 0
    for c in changed:
        if c["status"] == "D" or c["path"].startswith("test/"):
            continue
        path = os.path.join(head_root, c["path"])
        whole = c["status"] == "A" or c["path"] not in head_lines
        total += nonblank_in(path, None if whole else head_lines[c["path"]])
    return total
