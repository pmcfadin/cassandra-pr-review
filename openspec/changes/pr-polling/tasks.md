## 1. Poll

- [x] 1.1 `cpr/poll.py` selection from open PRs and the published site (tests with recorded API JSON: unchanged, new head, stale draft, cap)
- [x] 1.2 `cpr poll [--run] [--site DIR] [--limit N]`; keep-richer rule; index rebuilt from the site dir (tests: richer report kept; new head replaces)
- [x] 1.3 Site index: generated time and whether code review ran

## 2. Workflow

- [x] 2.1 `.github/workflows/poll.yml` per design D4 (test: workflow file parses and has only contents: write)
- [x] 2.2 `bin/publish-pages` fetches gh-pages and merges local reports into it (keep-richer, never deletes), then rebuilds the index; docs (README, about.md)

## 3. Ship

- [ ] 3.1 Dispatch once with limit 3, check the site, then leave the schedule on
