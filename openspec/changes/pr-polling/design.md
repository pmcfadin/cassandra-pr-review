## Context

`bin/publish-pages` builds the site from local `reports/` and pushes `gh-pages`. In Actions the
runner has no local reports, so the site build must start from the published site.

## Decisions

### D1. Selection
`gh api repos/apache/cassandra/pulls?state=open&per_page=100 --paginate` gives number, head sha,
draft, updated_at. The published state comes from the `gh-pages` branch: each `pr/<N>/index.html`
model's head sha (site.read_model). Picked: no published report, or a different head. Skip: drafts not
updated in 30 days. Order: most recently updated first; cap 25 per run (config).

### D2. Run
For each picked PR: `cpr review <N> --out <site>/pr/<N>/index.html` with the cached clone and
installed tools; failures are logged and skipped, never abort the run. Then rebuild `index.html`
from all `pr/*/index.html` in the site checkout, commit, push.

### D3. Keep the richer report
Before writing a report for PR N: if the existing published model has the same head and contains a
code review (`review.status == "ran"`) or build result, keep it. A new head always replaces it.

### D4. Workflow
`schedule: cron "17 */6 * * *"` and `workflow_dispatch` (input: limit). Steps: checkout main;
checkout gh-pages into `site/`; `actions/cache` for `.work/cassandra` (keyed by week) and
`.work/tools`; setup-java 21 (temurin); `bin/cpr tools install`; `bin/cpr poll --run --site site
--limit N`; commit and push `site/` to gh-pages. Permissions: `contents: write`, nothing else.
Concurrency group so two runs never overlap.

### D5. Local
`cpr poll` without `--run` prints the picked PRs; the owner can run the same locally.

## Risks / Trade-offs

- [First run is slow (full clone)] → cache; the limit caps work per run.
- [A local publish and the Action race] → both rebuild the index from the site; the Action uses
  concurrency and pulls before push; `bin/publish-pages` pulls first too.
