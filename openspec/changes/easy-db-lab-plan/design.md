## Context

The research doc has the plan format (`easy-db-lab:run` parses only Cluster Name and Datacenters,
then walks `### N.` steps), the build path (cassandra-builds `build-cassandra-ref.yml` → tarball →
`cassandra install <name> --url <tarball> --java N`), the 16 workloads of cassandra-easy-stress, the
mapping rules, the A/B design, and filled examples for PR 5201 and 4967.

## Decisions

### D1. Scenario selection
Rules in `cpr/config/labplan.json`: each rule has path patterns (and optional compat surfaces or
triage flags), a scenario id, and a priority. Matching rules are ranked by priority then by number of
changed lines they cover; at most two scenarios. No match on production code → `smoke`. The
no-plan list: docs, tests only, build/tooling, dependency bumps, over 300 production files.

### D2. Plan text
Built from fixed templates per scenario with only these substitutions: PR number, sanitised title
(alphanumerics, spaces, and `-_.:()` kept, 80 chars), base branch, merge-base sha, head sha, Java
version by branch (4.0 → 11, 4.1 → 11, 5.0 → 17, trunk → 21), workload names and arguments from
config. Cluster: 3 db + 1 app `i4i.xlarge`, one cluster, arms run base, head, head, base after two
calibration runs; a delta counts only above twice the calibration spread. The build step names the
cassandra-builds workflow and says the dispatching repo is the operator's choice.

### D3. Report section
Section id `labplan`, after Testing. Status `info` with summary "Plan for <scenarios> (not run)", or
`not-applicable` with the no-plan reason. The template renders the markdown with the existing safe
renderer (escape first, then a small subset), and adds Copy and Download (`plan-<N>.md`) buttons.
`cpr review` also writes `reports/<N>/plan.md`.

### D4. Command spelling test
A stored copy of `easy-db-lab commands` output (`tests/fixtures/labplan/commands.txt`) is checked
against every `easy-db-lab ...` line in generated plans, so a renamed command fails a test.

## Risks / Trade-offs

- [Plans go stale as easy-db-lab changes] → command-spelling test; tool version recorded in the plan.
- [Wrong scenario for a subtle change] → the plan says which rule fired, and reviewers can edit it.
