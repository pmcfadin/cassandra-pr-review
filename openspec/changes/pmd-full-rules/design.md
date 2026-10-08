## D1. One pass
Extend the existing one-pass ruleset: complexity rules (as configured) + MethodBody + every rule from the 8
category files, excluding rules that need configuration to work (e.g. LoosePackageCoupling) and the three
complexity rules' duplicates. Generate the ruleset file from the PMD jar's category list at install time or
check in a static list; either way record the rule count in the result.

## D2. Introduced
A violation is introduced when its begin line is an added line of the head file (head_lines), or the file
is new. Fallback when line maps are missing: per (file, rule) head count minus base count, floored at 0.

## D3. Baseline
`static-cache/pmd-baseline-<branch>-<tip sha12>-<pmd id>.json`: per rule, files hit / files scanned.
Built on first use per branch tip; reuse any baseline for the same branch younger than 7 days if the tip
moved (log it). Time budget: if the baseline cannot be built within the PR budget, fall back to density in
the base versions of touched files and say so in the report.
Threshold 25% of files, in cpr/config/static.json.

## D4. Type info
If `bundle["build"]` has a run for this head with a classes dir and resolved jars, pass them as
`--aux-classpath`. Otherwise run without and note "without type info: some rules may misfire".

## D5. Colours
Category to band: errorprone/multithreading/security red; performance/bestpractices/design yellow;
codestyle/documentation green. Within the table, sort by band then introduced count.

## D6. Output limits
Keep at most 50 locations per rule and 2,000 locations total in the model; counts stay exact.
