## 1. Rate test
- [ ] 1.1 Baseline records violations and LOC; version bump (tests)
- [ ] 1.2 Poisson usual-for-Cassandra classification for production violations (tests)

## 2. Type info
- [ ] 2.1 Build runner keeps classes + jars for last 5 runs, status.json classpath (tests)
- [ ] 2.2 pmd-type-rules.json seeded from docs; measured on a real built PR (#4967 rebuild)
- [ ] 2.3 Greyed type-dependent rules without classes (tests)

## 3. Check and report
- [ ] 3.1 static.pmd-rules uses only unusual, typed-or-safe red production violations (tests)
- [ ] 3.2 Report: usual-for-Cassandra section with observed vs expected; greyed type rules; static doc (browser test)

## 4. Ship
- [ ] 4.1 Re-run all 8 PRs; publish
