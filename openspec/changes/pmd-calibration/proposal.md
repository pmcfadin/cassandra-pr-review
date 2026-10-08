## Why

After pmd-full-rules went live, the static.pmd-rules check warned on all 8 published PRs, so the warning
carries no signal. Two causes, from the owner review on 2026-10-08:

1. Rules Cassandra breaks on purpose are rare per file, so the 25%-of-files house-style test misses them:
   DoNotUseThreads, AvoidUsingVolatile, AvoidSynchronizedAtMethodLevel, NullAssignment,
   AvoidCatchingGenericException, UseConcurrentHashMap. 10 of #5128's 12 red production violations.
2. No type info: WrongTestAnnotation is the top red rule (48 on #5128, 160 on #4967) and almost certainly
   misfires without the compiled classes. The build runner deletes classes and jars after each run.

## What Changes

- **Second house-style test, by rate.** The branch baseline also records each rule's violation count and
  the lines of code scanned. For a PR, a rule's expected count is trunk's rate × the PR's added production
  lines. A rule is "usual for Cassandra" when the observed count is not significantly above expected
  (one-sided Poisson p >= 0.01). Such rules are counted in a second collapsed section with observed vs
  expected, and do not drive the check. A rule trunk never breaks is never "usual".
- **Type-dependent rules.** A checked-in list of rules that need type resolution, seeded from the PMD docs and
  confirmed by measurement (rules whose counts change with vs without an aux classpath). Without type info,
  those rules show greyed as "needs compiled classes" and do not drive the check.
- **Keep build classes.** The build runner keeps the head's compiled classes and resolved dependency jars
  for the last 5 runs and records them in status.json, so PMD runs with `--aux-classpath` for built PRs.

## Impact

cpr/staticanalysis (baseline, classify), cpr/checks/static.py, cpr/build runner and status.json, cpr/model.py,
report.html PMD block, docs/report/static.md, tests. Baseline file version bump (old baselines rebuilt).
