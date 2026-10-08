## 1. Generator

- [x] 1.1 `cpr/config/labplan.json` rules, cluster, durations, caps, Java by branch (test: rules load)
- [x] 1.2 `cpr/labplan.py` scenario selection and no-plan reasons (tests: 5201 crash scenario, 4967 Accord, docs-only, over 300 files)
- [x] 1.3 Plan text from templates with sanitising (tests: golden plans for 5201 and 4967; title injection; command spelling vs tests/fixtures/labplan/commands.txt)

## 2. Report

- [x] 2.1 Model section `labplan` and `reports/<N>/plan.md` (test: section status and summary)
- [x] 2.2 Template rendering with "Not run" banner, Copy and Download (browser test)
- [x] 2.3 docs/report/labplan.md

## 3. Ship

- [ ] 3.1 Render 5201 and 4967 locally, review with the owner
