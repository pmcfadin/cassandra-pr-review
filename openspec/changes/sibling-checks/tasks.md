## 1. Profiles and checks

- [x] 1.1 Profile fields per design D1; Cassandra values moved out of code (test: recorded Cassandra models identical)
- [x] 1.2 Disabled checks and `{key}` titles (tests: sidecar not-applicable reasons)
- [x] 1.3 Commit, ticket and changelog wording; subject key allowed for the subprojects

## 2. CI

- [x] 2.1 `cpr/ingest/gh_checks.py` and the bundle (tests with the recorded sidecar #400 and #401 responses)
- [x] 2.2 `ci.evidence`, `ci.freshness`, `ci.failures` for `github-checks`; branch row from the check-runs

## 3. Static analysis and surfaces

- [x] 3.1 Checkstyle config, version, scopes and properties from the profile; checkstyle 7.8.1 and 9.3 pins
- [x] 3.2 Main and test split, exclude and baseline roots from the profile
- [x] 3.3 Compatibility surfaces and triage paths per project; lab plan off for the subprojects

## 4. Docs and ship

- [x] 4.1 `docs/report/subprojects/`; docs loaded per project; aspect-doc test over every docs directory
- [x] 4.2 README
- [x] 4.3 Live: sidecar #400 and #401, analytics #262, with the tools installed
