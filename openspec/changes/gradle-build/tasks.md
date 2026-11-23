## 1. Seam and sandbox

- [x] 1.1 `GradleBuild(runner.Build)`; `runner.build` picks by `build.tool`; `keep_classpath` and `jdk_home` hooks
- [x] 1.2 GRADLE writable in the no-network profile; `sandbox.params` always passes it
- [x] 1.3 `cpr/assets/cpr-init.gradle` (resolve, projects, classpath, JaCoCo XML)

## 2. Steps

- [x] 2.1 Wrapper check, merge-base resolve, offline head build, `OFFLINE_DEPS` status
- [x] 2.2 Sidecar dtest jar from the pinned Cassandra sha, shaded by the merge-base's script, cached
- [x] 2.3 `select_gradle`, merged coverage, result discovery, `--rerun` retry, kept classpath

## 3. Ship

- [x] 3.1 Unit tests with the fake shell and a real repo (tests/test_gradle_build.py)
- [x] 3.2 Live: sidecar #400 pass (50 tests, 18/20 changed lines), analytics #260 pass (50 tests, 3/4)
- [x] 3.3 Sandbox probe under the real profile: ~/.ssh, $HOME write, network, other PR data all blocked
- [x] 3.4 Docs: subprojects build and static aspects, README
