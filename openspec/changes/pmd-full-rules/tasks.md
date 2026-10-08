## 1. Analysis
- [x] 1.1 Full ruleset (8 categories, minus misconfigured and complexity duplicates); one pass with complexity (tests)
- [x] 1.2 Introduced classification by added lines with count fallback (tests)
- [x] 1.3 Branch baseline, cached; house-style rules at >= 25% of files; fallback to touched base files (tests)
- [x] 1.4 Aux classpath from a build of this head when present (tests)
- [x] 1.5 Static cache schema bump; Action caches the baseline

## 2. Check and model
- [x] 2.1 static.pmd-rules advisory check (tests)
- [x] 2.2 Model field with limits (tests)

## 3. Report
- [x] 3.1 PMD rules block: category summary, rule table with bands, rule docs links, file:line lists, house style collapsed; phone layout; browser test
- [x] 3.2 Static aspect doc ("How this is judged") updated

## 4. Ship
- [ ] 4.1 Run on all 8 PRs locally; owner review
