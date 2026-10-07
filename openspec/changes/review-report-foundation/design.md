## Context

The project is new; nothing exists beyond OpenSpec scaffolding and the research in `docs/research/`.
The owner's target pipeline is: poll apache/cassandra → check requirements → run deeper tests →
render one HTML report with left-hand navigation → publish to GitHub Pages → comment the link on
the PR. The owner chose to run locally first and get the report right before automating anything.

This change builds the spine every later change hangs off: ingest, requirement checks, triage, the
report model, and the HTML renderer. Later changes add review lenses (findings slot), deeper tests
(new check categories), and publish/comment/poll (wrapping `cpr review`).

Facts that constrain the design (sources in the research docs):
- No CI checks appear on PRs; CI evidence is `ci_summary*.html` attached to the JIRA ticket.
- One PR per target branch, linked only by the JIRA key; PRs close unmerged.
- 16% of PRs have no JIRA key; 17% have an empty body; PRs reach 20k+ lines.
- ide-explain (dev-skills 0.4.1) builds its diff from a local git checkout and can attach PR review
  comments with `--pr N`; it accepts `--explain-map` for per-file notes.

## Goals / Non-Goals

**Goals:**
- `cpr review <N>` produces a correct, honest report for any open apache/cassandra PR.
- Every stage is a pure transform over JSON, so it is unit-testable from recorded fixtures.
- The report model is stable enough that later changes add data, not restructure the page.

**Non-Goals:**
- Polling, publishing, PR comments, review lenses, deeper tests, running Ant (later changes).
- Flaky-test triage against Butler/Jenkins baselines (CI failures are counted, not triaged).
- Multi-repo support.

## Decisions

### D1. Report unit: one report per PR, aware of its siblings
Options: (a) one report per PR; (b) one report per JIRA key covering all branch PRs.
**Recommendation: (a).** The trigger is "a PR was opened" and the link is commented on that PR, so
the URL must be per PR. Branch coverage and per-branch CI still come from the siblings, shown in
the Branches & CI section. A per-key landing page can be added later without changing this.

### D2. Language and packaging: Python 3.11+, standard library only
A `cpr/` package run as `python3 -m cpr` with a thin `bin/cpr` wrapper. No pip dependencies, which
matches the rustyrazorblade generators we call and keeps a GitHub Actions runner trivial later.
`gh` provides GitHub auth (`gh api`); JIRA is anonymous HTTPS via `urllib`.
Alternative considered: Node/TypeScript. Rejected: no gain, and ide-explain is already Python.

### D3. Pipeline stages with JSON boundaries
```
ingest (network, cached) → bundle.json
checks(bundle)           → checks.json
triage(bundle)           → triage.json
model(bundle, checks, triage, findings=[]) → report-model.json  (validated)
render(model, diff_view_html) → reports/<N>/index.html
```
Each stage after ingest is a pure function. Fixtures are recorded bundles from real PRs (a backport
set, a no-JIRA PR, a draft, a huge PR, a stale-CI PR). `--offline` starts from the cached raw
responses.

### D4. Work directory and clone
`.work/cassandra.git`: a blobless partial clone (`--filter=blob:none`) of apache/cassandra, fetching
`refs/pull/<N>/head` and the base branch per review. `.work/pr/<N>/<head-sha>/` holds raw API
responses and stage outputs. Both are gitignored.

### D5. Diff view: call the installed ide-explain, embed it in a sandboxed iframe
Options: (a) run the installed generator and embed its output page; (b) port ide-explain's viewer
into our template; (c) write our own diff view.
**Recommendation: (a).** It uses the latest rustyrazorblade skill as the owner asked, and plugin
upgrades flow in without our code changing. The generator is run with cwd = the clone,
`--diff --base <merge-base> --head pr-<N> --pr <N> --title …`, and an `--explain-map` seeded with
per-file notes from our checks (for example "banned API at line 42"). Its HTML is stored in the
model as a base64 string; at load time our JS sets it as the `srcdoc` of an
`<iframe sandbox="allow-scripts">` (no `allow-same-origin`), so it cannot touch the outer page.
The generator path is resolved from the newest
`~/.claude/plugins/cache/rustyrazorblade-plugins/dev-skills/*/skills/ide-explain/scripts/generate-explain.py`,
overridable with `CPR_IDE_EXPLAIN`. Its version is recorded in About.
Trade-off: the report depends on a locally installed plugin; mitigated by the fallback file list
(spec: "ide-explain unavailable") and, for CI later, by installing the plugin or pinning a copy.

### D6. Our report template
A checked-in `cpr/assets/report.html` with a `<!--REPORT_MODEL-->` marker, following the
rustyrazorblade pattern (static shell + validated JSON + escaping from `html_shell.py`), but with
a doctype, light and dark themes (CSS tokens on `:root`), a print stylesheet, and a left-hand nav.
Vanilla JS, no libraries. Markdown in JIRA/PR text is shown as escaped preformatted text in this
change; a sanitizing renderer can come later.

### D7. Checks are a registry of small functions
Each check is `check(bundle) -> CheckResult`, registered with id, category, and blocking/advisory.
The banned-API list is read from `.build/checkstyle.xml` at the PR's base branch in the clone, so
it tracks the project instead of a hard-coded copy. Triage thresholds and path lists live in
`cpr/config/triage.json`.

### D8. Recommendation computation
Ordered rules, first match wins: draft → `draft`; any blocking fail → `blocked`; any blocking
unknown → `insufficient-evidence`; any advisory warn needing action → `needs-work`; no findings
supplied → `requirements-met-unreviewed`; findings with no blocker/major → `ready`; otherwise
`needs-work`. `ready` is unreachable in this change by construction (no lenses), which the spec
requires.

### D9. Committer roster: derived from ASF, not hand-maintained
The owner chose to derive the roster. The public ASF data gives committer ASF ids
(`public_ldap_projects.json` → `cassandra.members`, 101 as of 2026-10-07; `owners` = PMC, 49) and
names (`public_ldap_people.json`), but no GitHub usernames. So committer status is matched per
source: JIRA username = ASF id; GitHub `author_association` MEMBER/OWNER (ASF-linked accounts are
apache org members); or `<asf-id>@apache.org` commit emails in the clone. The roster is cached for
24 hours under `.work/`. `cpr/data/committer-overrides.json` (empty to start) corrects individual
mappings found to be wrong. Every counted vote shows the rule that matched, so a human can audit it.

### D10. Aspect docs: one document per report aspect, embedded in the report
Each aspect of the report (summary and recommendation, JIRA ticket, CI, commits and changelog,
testing, static checks, compatibility, branches, votes, triage, code review, changes view) gets
`docs/report/<aspect>.md`, following a fixed outline: what is checked, why (with the project-standard
source), how each status is decided (per check id), what the contributor does to fix it, and known
limits. The docs are the single source for this explanation: at render time each section's doc is
embedded in its section as a collapsible "How this is judged" panel, rendered by the template's
escaped markdown renderer. A test fails if any registered check id is not documented in its aspect
doc, so the docs and the checks cannot drift apart.

## Risks / Trade-offs

- [ci_summary HTML format changes or varies by era] → parse defensively, keep fixtures from several
  tickets, report "unparsed" instead of failing.
- [JIRA anonymous rate limits or outages] → cache, retry with backoff, degrade to unknown.
- [JIRA usernames that differ from ASF ids miss committer matches] → fall back to GitHub signals;
  list unmatched +1s; correct via the overrides file.
- [Heuristic +1 detection in JIRA comments misreads "+1 to the idea"] → show every counted vote
  with a link to its comment so a human can verify; votes never move the recommendation past
  `requirements-met-unreviewed`.
- [Huge PRs make the embedded diff view enormous] → if the ide-explain output exceeds a size
  budget (default 8 MB), scope it to `src/` and record what was left out.
- [ide-explain makes its own `gh` calls] → run it with cwd in the clone (origin = apache/cassandra);
  its calls are read-only. Its output is checked for network references before embedding.
- [Banned-API grep is approximate] → advisory only; `ant check` remains authoritative and is listed
  as "not run" in About.

## Migration Plan

Not applicable; new project.

## Open Questions

Resolved by the owner (2026-10-07): roster is derived (D9); a missing `patch by` line is a warning;
reports are per PR.

1. "Deeper tests" will need their own section and check category; their shape is left to that change.
