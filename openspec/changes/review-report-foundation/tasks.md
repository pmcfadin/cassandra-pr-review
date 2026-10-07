## 1. Project setup

- [x] 1.1 Create `cpr/` package, `python3 -m cpr` entry point, `bin/cpr` wrapper, and argument parsing (`review <N>`, `--offline`, `--out`, `--work-dir`)
- [x] 1.2 Set up `unittest` test layout under `tests/` and a `make test` (or script) target
- [x] 1.3 Add a test that fails if any HTTP call in ingest uses a method other than GET, or any mutating `gh` subcommand is invoked

## 2. Ingest (spec: pr-ingest)

- [x] 2.1 GitHub client over `gh api` with raw-response caching under `.work/pr/<N>/<sha>/`
- [x] 2.2 Fetch PR metadata, commits, files, diff, reviews and review comments; error on missing PR (test: "PR does not exist")
- [x] 2.3 JIRA key resolution across title, branch, body, commits with precedence and conflict recording (tests: key in title, conflicting keys, no key)
- [x] 2.4 JIRA client: anonymous fetch, custom fields by name, retries, 404 and unavailable handling (tests: ticket exists, not found, unreachable)
- [x] 2.5 Sibling PR discovery via remote links and GitHub search, filtering unrelated mentions (tests: backport set, unrelated mention)
- [x] 2.6 CI attachment discovery and `ci_summary` parsing; record fixtures from at least three tickets (tests: summary attached, unparseable, none)
- [x] 2.7 Partial clone management: create once, fetch PR head and base per review (tests: first run, subsequent run)
- [x] 2.8 `--offline` replay from cache (tests: offline re-render, offline with no cache)
- [x] 2.9 Record fixture bundles for: a backport set, a no-JIRA PR, a draft, a huge PR, a stale-CI PR
- [x] 2.10 Test that instructions inside PR body/JIRA text do not change any check result

## 3. Merge requirements (spec: merge-requirements)

- [x] 3.1 CheckResult type and check registry (tests: failing check explains itself, missing input is unknown)
- [x] 3.2 JIRA ticket checks (tests: no ticket, already resolved, feature branch, fix version mismatch)
- [x] 3.3 CI evidence checks with upgrade-profile detection (tests: matches head, stale, not yet run, upgrade profile needed, failures present)
- [x] 3.4 Commit format and CHANGES.txt checks (tests: good message, missing patch-by, missing CHANGES.txt, test-only)
- [x] 3.5 Test presence check and suite classification (tests: no tests, docs-only)
- [x] 3.6 Static diff checks reading banned APIs from the base branch's `.build/checkstyle.xml` (tests: banned API added, missing licence header)
- [x] 3.7 Compatibility surface detection and pairing rules (tests: config pairing missing, protocol touched)
- [x] 3.8 Branch coverage check (test: missing branch)
- [x] 3.9 Derived committer roster from ASF whimsy data with 24h cache and overrides file; votes check with per-vote match rule (tests: two votes, no votes, non-committer vote, roster unavailable)
- [x] 3.10 Recommendation rules (tests: unreviewed is best without review, unknown dominates pass, draft)

## 4. Triage (spec: review-triage)

- [x] 4.1 `cpr/config/triage.json` with thresholds and path lists (test: thresholds configurable)
- [x] 4.2 Signal computation and rating (tests: small test-only change is easy, serialization change is hard, signals shown)
- [x] 4.3 Size guard with top-five files (test: huge PR)

## 5. Report model and rendering (spec: review-report)

- [x] 5.1 Report model JSON schema and validator; invalid model writes no file (test: invalid model)
- [x] 5.2 Manifest injection with `<` escaping (test: hostile diff content renders literally)
- [x] 5.3 `cpr/assets/report.html`: doctype, CSS tokens, light/dark/toggle, print stylesheet
- [x] 5.4 Left-hand navigation with status badges, URL-fragment routing, narrow-screen collapse (tests: deep link, narrow screen)
- [x] 5.5 Summary first page: header, recommendation and reasons, triage, check grid, blocking-first ordering (tests: blocked PR, unreviewed PR)
- [x] 5.6 Detail sections: Requirements, JIRA, Branches & CI, Commits, Compatibility, Triage, Code review, About (tests: code review not run, About states limits)
- [x] 5.7 Findings slot in rustyrazorblade schema, grouped by lens (test: findings present)
- [x] 5.8 ide-explain integration: resolve generator, build explain-map from checks, run in clone, size budget, embed in sandboxed iframe (tests: diff view present, ide-explain unavailable)
- [x] 5.9 Output to `reports/<N>/index.html` and print path (test: default output)
- [x] 5.10 Self-containment test: no network references; open with networking disabled renders all sections (tests: no network references, opens from disk, print)

## 6. Aspect docs (spec: review-report, Aspect documentation)

- [x] 6.1 Write `docs/report/README.md` defining the aspect doc outline and listing every aspect
- [x] 6.2 Write aspect docs: summary, jira, ci, commits, testing, static, compatibility, branches, votes, triage, code-review, changes, each citing docs/research sources
- [x] 6.3 Embed each aspect doc as a collapsed "How this is judged" panel in its report section (tests: contributor reads the standard, doc missing)
- [x] 6.4 Doc coverage test: every registered check id appears in its aspect doc (test: every check is documented)

## 7. End-to-end

- [ ] 7.1 Run `cpr review` against five live PRs covering the fixture cases; review the reports with the owner
- [x] 7.2 Write README usage and document what the report does not check yet
