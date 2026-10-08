## 1. Tools

- [x] 1.1 `cpr/config/static.json` (versions, URLs, sha256, branch families, thresholds, caps) and `cpr/staticanalysis/tools.py` (install, verify, locate java) (test: digest mismatch)
- [x] 1.2 `cpr tools install` command (test: already installed is a no-op)

## 2. Collect and run

- [x] 2.1 Inputs: rename map, changed lines, base/head blob extraction, commit list with paths (test: rename map and changed lines on a temp repo)
- [x] 2.2 Runners for checkstyle, PMD, CPD with exit-code handling, caps, and file-coverage proof (tests: parse recorded XML; missing file → unknown)
- [x] 2.3 Classifier (tests: 5201 delta 6 → 2; renamed class; new file; moved method; CPD introduced)
- [x] 2.4 Wire into ingest with caches (head sha, base blob sha); offline replay (test: offline re-render runs no tool)

## 3. Checks

- [ ] 3.1 `static.checkstyle`, `static.complexity`, `static.duplication` (tests: branch without checkstyle; introduced error; complexity note)
- [ ] 3.2 `commit.perf-structure` (tests: bench after change; combined; not a perf PR)
- [ ] 3.3 Superseding regex banned-API and `@Deprecated` checks when checkstyle ran (test: superseded)

## 4. Docs and ship

- [ ] 4.1 Update docs/report/static.md and the commits doc (statuses, introduced vs pre-existing, perf rule, limits)
- [ ] 4.2 Run on PR 5201 and PR 4967, re-render, review with the owner
