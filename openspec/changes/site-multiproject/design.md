## Context

The live site (upstream gh-pages, 2026-11-21) holds 729 Cassandra reports at `pr/<N>/index.html`
(about 226 MB) and PR comments link `…/cassandra-pr-review/pr/<N>/`.

## Decisions

### D1. Layout and keys
Reports live at `<slug>/pr/<N>/index.html`. `published_reports` and `published_heads` are keyed by
`(slug, N)`, read only from known project directories, and a model is filed under its own
`project.slug` (a report rendered before projects existed is Cassandra's).

### D2. Migration with redirects
`site.migrate` moves each `pr/<N>/` that holds a Cassandra report model to `cassandra/pr/<N>/`, unless a
report already there is richer (`replaces`), and writes a redirect page in its place: meta refresh,
canonical link and `location.replace` keeping the `#fragment`, all relative
(`../../cassandra/pr/<N>/`) so forks and user sites work. Redirects have no model, so a second run
skips them. `site.merge` runs it first, so `bin/publish-pages` migrates; `cpr poll --run` runs it
before reading heads; a dry run writes nothing. Only migrated numbers get a redirect: no new links to
`pr/<N>/` are made after this change.

### D3. Index
One section per project, Cassandra first, then the others by slug, each with its group cards
(`g-<slug>-<group>`), a groups nav and a link to its open PRs. A top nav jumps between projects when
more than one has reports.

### D4. Polling
`cmd_poll` loops over projects; `select` is unchanged and gets one project's heads (`heads_for`).
`heads_from_git` reads both layouts. `refresh` takes picks with a `project` and calls
`review(slug, number, out)`. `--limit` is per project.

### D5. Comment URL
`pages_base()` returns the site root (PR #1 returned `<root>/pr`) and `pages_url(project, N)` adds
`<slug>/pr/<N>/`. `CPR_PAGES_BASE` is the site root. PR #1 is not merged upstream, so its commit is
included here; nobody can have set the old meaning.

## Risks / Trade-offs

- [The first publish rewrites 729 files] → tested against a copy of upstream gh-pages: 729 moved, a
  second run moved nothing, no local paths; the push waits for the owner.
- [Redirects lose history in the Pages URL] → canonical link and `location.replace` keep the anchor.
