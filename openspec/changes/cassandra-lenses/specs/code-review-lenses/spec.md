## MODIFIED Requirements

### Requirement: Lens panel
The system SHALL define the review panel in one checked-in file listing each lens's name, agent
type, and focus. The default panel SHALL be six project lenses: `cassandra-standards`,
`cass-logic-boundary`, `cass-concurrency-lifecycle`, `cass-persistence-compat`,
`cass-completeness-symmetry`, and `cass-test-regime`. No lens SHALL depend on the spec-flow plugin.
The `/review-pr` skill SHALL run every lens in parallel against the prepared worktree and SHALL save
each lens's JSON output to the PR's lens directory.

#### Scenario: Panel is data
- **WHEN** a lens is added to the panel file
- **THEN** `/review-pr` runs it and the report shows it, with no code change

#### Scenario: No spec-flow dependency
- **WHEN** the spec-flow plugin is not installed
- **THEN** `/review-pr` runs the full panel

### Requirement: Render findings
`cpr review <N> --lenses <dir>` SHALL render the merged result: the merged issues first, each with
its severity, the lenses that reported it, location(s), rule, problem, and fix; then per lens its
status, approval, summary, and raw findings. Issue locations SHALL be added to the diff view's
explanation pane, once per issue with the reporting lenses named.

#### Scenario: Findings in the diff view
- **WHEN** an issue has location `src/java/org/apache/cassandra/io/sstable/SSTable.java:121` and was reported by two lenses
- **THEN** the Changes view's explanation for that file lists the issue once, naming both lenses

## ADDED Requirements

### Requirement: Checklists from trusted trunk
The system SHALL load lens checklists from apache/cassandra `.claude/skills/` on `origin/trunk`,
resolved to one commit sha per run (overridable by a pinned sha in configuration), reading only
allow-listed paths with `git show <sha>:<path>` into a run directory outside the PR worktree. It
SHALL never read checklists from the PR worktree, the PR head, or the base branch. Each file SHALL be
checked (exists, UTF-8, under a size cap) and the sha SHALL be recorded in the report. If a file is
missing, the lens SHALL be reported `missing`; there SHALL be no silent fallback to another copy.

#### Scenario: PR edits the skills
- **WHEN** the PR modifies `.claude/skills/shallow-review/references/general/specialists/logic.md`
- **THEN** lenses receive the trunk copy at the pinned sha, and the standards lens reports the edit as a finding

#### Scenario: Upstream renamed a checklist
- **WHEN** an allow-listed path does not exist at the resolved sha
- **THEN** the lenses that need it are recorded as missing with the path named, and the panel is not approved

#### Scenario: Report names the checklist version
- **WHEN** a report is rendered from a lens run
- **THEN** the Code review section states "checklists: apache/cassandra trunk @ <sha>"

### Requirement: Diff-size tiers
The system SHALL choose a tier from changed non-test lines: `small` under 50, `medium` 50 to 1,000,
`large` over 1,000. Each lens SHALL receive the checklist bundle for its tier from configuration:
shallow specialist checklists for small; shallow plus the targeted categories whose INDEX diff
signals match the diff (at most 8 categories across the panel) for medium; deep checklists plus a
list of focus files ranked by risk for large. A docs-only PR SHALL run no lenses. The lens summary
SHALL state which checklists were applied and what was not reviewed.

#### Scenario: Small patch
- **WHEN** a PR changes 19 lines of production code
- **THEN** each lens gets only its shallow specialist checklist

#### Scenario: Medium patch with serialization changes
- **WHEN** a 300-line PR adds a field to an `IVersionedSerializer`
- **THEN** the serialization-and-versioning category is in `cass-persistence-compat`'s bundle

#### Scenario: Large patch
- **WHEN** a PR changes 37,000 lines
- **THEN** lenses get deep checklists and a focus list, and their summaries name the files not reviewed

### Requirement: Severity from impact and confidence
Each Cassandra lens SHALL report, per finding, an `impact` (data-loss, crash, hang,
mixed-version-break, silent-wrong-result, performance, cosmetic) and a `confidence` (high, medium,
low), and SHALL set `severity` from this table: data-loss, crash, hang, or mixed-version-break gives
blocker, major, minor at high, medium, low confidence; silent-wrong-result gives major, major, minor;
performance gives minor, minor, nit; cosmetic gives nit. A finding with no concrete trigger SHALL be
dropped, not reported as a nit. The report SHALL show impact and confidence when present.

#### Scenario: Severity follows the table
- **WHEN** a lens reports impact data-loss with medium confidence and severity blocker
- **THEN** merging records the severity as major and notes the correction

### Requirement: Merge duplicate findings
The system SHALL merge findings from different lenses that describe the same issue, using a
deterministic score (no model call): identifier, word, and fix-identifier overlap between the
findings' texts, plus a location bonus (same file within 3 lines, within 10 lines, or a non-file
location). Findings SHALL merge when the text score is at least 0.18 and the total at least 0.40,
grouped strongest edge first; two findings from the same lens SHALL never merge. A merged issue SHALL
take the highest member severity, record every member and lens, keep fixes that differ, and keep all
locations. Panel approval SHALL be unchanged by merging; must-fix counts SHALL count issues.

#### Scenario: PR 5201 regression
- **WHEN** the 11 findings recorded on PR #5201 are merged
- **THEN** there are exactly 5 issues, 3 of them must-fix, and the silent-delete issue names all four lenses that reported it

#### Scenario: Same line, different issue
- **WHEN** two lenses report different problems at the same line with little shared text
- **THEN** they stay separate issues

### Requirement: Test regime lens
The `cass-test-regime` lens SHALL judge whether the patch's tests fit Cassandra's testing regime,
using the project's testing aspect doc, trunk's `cassandra-injvm-dtest` skill, and the AGENTS.md rule
that a bug fix starts with a regression test that fails without the fix: the right suite for the
change (unit, in-JVM dtest, python dtest, upgrade, simulator, fuzz, microbench), whether the test
would fail without the fix, and whether timing-sensitive tests need repeated runs.

#### Scenario: Multi-node fix with only a unit test
- **WHEN** a patch fixes cross-node behaviour and adds only a unit test
- **THEN** the lens reports that an in-JVM dtest is the fitting suite

### Requirement: Security and observability coverage
The `cassandra-standards` lens SHALL include a self-gating security check (auth, roles and
permissions, TLS, JMX exposure, UDFs, secrets in logs or virtual tables) against Cassandra's security
model, reporting nothing when the diff touches no security surface. The `cass-persistence-compat`
lens SHALL check that new failure paths are logged at the right level and that metrics stay
symmetric.

#### Scenario: Password in a virtual table
- **WHEN** a patch exposes a configuration field holding a password hash through `system_views.settings`
- **THEN** the standards lens reports it as a security finding
