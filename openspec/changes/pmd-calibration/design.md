## D1. Rate test
baseline: per rule {files_hit, violations}; totals {files, loc} (non-blank lines of src/java).
PR: added_loc = added lines in changed production Java files. e = violations/loc × added_loc.
usual(rule) = trunk violations > 0 and P(X >= observed | Poisson(e)) >= 0.01. Pure-Python Poisson tail.
Applies to production violations only; test-file violations keep the current treatment.
Rules meeting the 25%-of-files test stay "house style"; rate-usual rules are a separate section.

## D2. Type-dependent rules
cpr/config/pmd-type-rules.json: rule names + source ("docs" or "measured"). Measured by running the full
ruleset on a sample (the changed files of a built PR) with and without the aux classpath; any rule whose
count differs is added. Without type info those rules render greyed and are excluded from the check.

## D3. Keep classes
On a finished build run, keep build/classes/main, build/test/classes and the resolved jar list (paths in the run's
Maven repo) under the run dir; write status.json "classpath": {"classes": [...], "jars": [...]}.
Prune kept classpaths beyond the 5 newest runs. Still sandboxed; nothing outside the run dir.

## D4. Check
static.pmd-rules warns only on red-category production violations that are neither house style, nor usual
for Cassandra, nor type-dependent-without-types. Pass otherwise; summary still gives the other counts.
