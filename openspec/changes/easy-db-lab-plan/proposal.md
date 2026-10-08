## Why

Reviewers want to know how a change behaves on a real cluster, and the owner wants each report to
carry a ready-to-run easy-db-lab plan for that: build the base and the PR head, run a workload that
fits the change, and compare. Owner decision: generate and embed the plan only; never provision AWS
or run it from this tool. Research: docs/research/easy-db-lab-plan.md.

## What Changes

- `cpr/labplan.py`: a deterministic generator (no model call) that maps the PR's changed paths and
  existing triage and compatibility signals to at most two scenarios (crash safety, compaction,
  memtable and write path, read path, LWT, Accord, repair and streaming, mixed-version, smoke), and
  writes an easy-db-lab `plan.md` in the plugin's format: Objective, Cluster Name, Datacenters,
  Environment, Artifacts under test, Steps (build base and head, provision, install both, calibrate,
  A-B-B-A scenario runs with Pass/Fail lines, results table, teardown), Notes.
- No plan for docs-only, tests-only, build or tooling changes, dependency bumps, or PRs over 300
  production files; the section says why.
- A new report section "Lab plan" with a fixed "Not run" banner, the rendered plan, and Copy and
  Download buttons. The plan is also written next to the report as `plan.md`.
- PR text that reaches the plan (title, ticket summary) is sanitised so it cannot inject commands.

## Non-goals

- Running plans, provisioning clusters, or triggering cassandra-builds workflows.
- Model-written plans.

## Capabilities

### New Capabilities
- `lab-plan`: scenario selection, plan generation, and the report section.

### Modified Capabilities
- (none; the report gains a section through the existing section table)

## Impact

`cpr/labplan.py`, `cpr/config/labplan.json` (rules, instance type, durations, caps),
`cpr/model.py` (section), `cpr/assets/report.html` (rendering, copy/download), docs/report/labplan.md,
tests (5201 and 4967 golden plans, no-plan cases, sanitising, command spelling against a stored
copy of `easy-db-lab commands` output).
