## Context

All commands, timings, pitfalls, and the sandbox profile are in docs/research/build-and-coverage.md;
prototypes in `.work/build-research/proto/` (select_tests.py, changed_cov.py, sandbox.sb); a real
run's outputs in `.work/build-runs/5201/d1095cbd.../` (status.json schema to keep).

## Decisions

### D1. Separate command, saved result
Builds take minutes, so `cpr build <N>` runs on its own and saves `status.json` per head sha;
`cpr review` reads the result for the current head (like lens outputs) and never builds. The
`/review-pr` skill runs `cpr build <N>` in the background for committer PRs before rendering.

### D2. Gate
`author in roster.committers` (bundle roster) → allowed. Else allowed only with
`cpr build <N> --approve`, which records `{head, approved_at}` in `.work/build-runs/<N>/approved.json`
and applies to that head only. Not allowed → `status.json` with `status: not-built`, reason.

### D3. Isolation (research 6.3, 6.4, and the 5201 run's profile fixes)
Throwaway `git clone --shared --no-checkout` of the fetch clone with origin removed; a per-run
`cp -cR` of `~/.m2`; resolve at the merge-base with network (trusted base build file); checkout head;
4.0 JNA swap; every ant call under `sandbox-exec -f cpr/assets/sandbox.sb` with absolute params;
deny reads of `~/.ssh ~/.aws ~/.gnupg ~/.config/gh ~/Library/Keychains ~/.claude` and read-data of
this repository except the run dir and the fetch clone's objects; `env -i` with PATH, JAVA_HOME,
HOME, the JDK flag, `JAVA_TOOL_OPTIONS=-Djava.net.preferIPv4Stack=true`; `nice`; 30 min cap. After
the run, assert the fetch clone's hooks and config are unchanged (else status `unknown` with a loud
note). Clean up the clone, m2 copy, and `build/`.

### D4. Status mapping
Research 5.1: `build-failed` (compile errors with file:line), `tests-failed` (class, test, first
line), `timeout`, `unknown` (JDK missing with the `sdk install` command, network, harness, sandbox
artifact matching `transferTo0`/`Operation not permitted`, coverage missing), `pass`, `not-built`.

### D5. Checks
`build.compiles`: fail when build-failed (blocking, owner contributor); `build.tests-pass`: fail on
failures not marked sandbox (blocking, contributor); `build.changed-line-coverage`: warn note when any
added executable line is missed; `unknown` or `not-applicable` (not built) never block.

## Risks / Trade-offs

- [Sandbox escape or read of an undenied file] → committers only by default; deny list; the Action
  later.
- [Selection misses the right test] → selection reasons shown; coverage is labelled partial.
