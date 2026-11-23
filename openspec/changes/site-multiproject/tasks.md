## 1. Site

- [x] 1.1 `<slug>/pr/<N>/` layout, `(slug, N)` keys, index by project (tests: same number side by side)
- [x] 1.2 `migrate` with redirects; `merge` runs it (tests: legacy site, idempotent, richer kept)
- [x] 1.3 `bin/publish-pages` local-path check over every project

## 2. Poll and comment

- [x] 2.1 `cpr poll` per project, `--project`, `heads_from_git` over both layouts; workflow caches per project
- [x] 2.2 `pages_base()` is the site root; `pages_url(project, N)`; sidecar comments (tests)

## 3. Ship

- [x] 3.1 Browser test: index sections per project
- [x] 3.2 Against a copy of upstream gh-pages: 729 reports moved, rerun moves nothing, no local paths
- [x] 3.3 `cpr poll --site <copy>` dry run lists picks per project; `cpr comment sidecar#400` dry run
- [ ] 3.4 First push of the migrated site (owner's go-ahead)
