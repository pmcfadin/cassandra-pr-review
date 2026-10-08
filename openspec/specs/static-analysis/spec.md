# static-analysis Specification

## Purpose
TBD - created by archiving change static-analysis. Update Purpose after archive.
## Requirements
### Requirement: Pinned analysis tools
The system SHALL pin checkstyle and PMD versions with download URLs and sha256 digests in
configuration, install them with `cpr tools install` into the work directory after verifying the
digest, and choose the checkstyle version by the PR's base branch family.

#### Scenario: Digest mismatch
- **WHEN** a downloaded tool's sha256 differs from the pinned value
- **THEN** the install fails, nothing is unpacked, and analysis reports `unknown` naming the tool

### Requirement: Base and head analysis of changed files
The system SHALL run checkstyle (with the base branch's own `.build` configs), PMD complexity rules,
and CPD on the base and head versions of the PR's changed Java files, extracted from git without a
checkout, excluding generated and vendored paths, and SHALL store normalized findings in the evidence
bundle, cached per head sha and per base blob sha.

#### Scenario: Re-render offline
- **WHEN** `cpr review <N> --offline` runs after an online run
- **THEN** the static analysis results come from the bundle and no tool runs

### Requirement: Introduced versus pre-existing
Each finding SHALL be classified as introduced (new file, new method, worsened, crossed threshold),
pre-existing (touched, untouched, improved), or fixed, by matching (base path via the rename map,
class, method signature, rule), never by line number alone.

#### Scenario: Method made simpler
- **WHEN** PR #5201 changes `SSTable.delete(Descriptor, Set<Component>)` from cognitive complexity 6 to 2
- **THEN** the complexity check lists that method as 6 → 2 and reports nothing introduced

#### Scenario: Renamed class
- **WHEN** a file and its class are renamed and a method's complexity is unchanged
- **THEN** the method is matched through the rename and reported as pre-existing

### Requirement: Static analysis checks
The system SHALL report `static.checkstyle` (introduced checkstyle errors ask for action, as CI would
fail), `static.complexity` (every changed method's cognitive complexity base → head; a method at or
above 15 that is new, worsened, or crossed the threshold is a note), and `static.duplication`
(introduced duplicates of at least 100 tokens are a note). All are advisory.

#### Scenario: Branch without checkstyle
- **WHEN** the base branch is `cassandra-4.0`, which has no checkstyle config
- **THEN** `static.checkstyle` is `unknown` with that reason, and no other branch's config is used

### Requirement: Never pass without proof
The system SHALL report a check as `unknown`, with the reason, when its tool is missing, fails to
parse its config, crashes, or omits any input file from its output; it SHALL never make such a check `pass`, and summaries SHALL show the worst status of their parts.

#### Scenario: File missing from output
- **WHEN** checkstyle's XML has no entry for one of the changed files
- **THEN** `static.checkstyle` is `unknown` naming the count of files not analyzed

### Requirement: Performance commit structure
The system SHALL check commit order for a performance PR (a changed `test/microbench` file, a `performance` label or `Test/benchmark`
component, or two weaker title, summary, and body signals): `pass` when the first benchmark commit precedes the first `src/java` commit; a note when they
share a commit or there is no benchmark; a warning that asks for action when the benchmark comes
after the change; `not-applicable` for other PRs; `unknown` when commits are unavailable.

#### Scenario: Benchmark after the change
- **WHEN** commit 1 changes `src/java/.../Mutation.java` and commit 2 adds a JMH benchmark under `test/microbench`
- **THEN** `commit.perf-structure` warns that the benchmark commit should come first so it can run on both sides

