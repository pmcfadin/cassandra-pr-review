## ADDED Requirements

### Requirement: Reports by project
The site SHALL publish each report at `<project>/pr/<N>/` and SHALL keep reports of different
projects with the same number apart.

#### Scenario: Same number in two projects
- **WHEN** Cassandra #5198 and Sidecar #5198 are merged into the site
- **THEN** both exist, at `cassandra/pr/5198/` and `sidecar/pr/5198/`, and the index lists each in its project's section

### Requirement: Old links keep working
The site SHALL move reports published at `pr/<N>/` to `cassandra/pr/<N>/` and leave a redirect.

#### Scenario: First publish after the change
- **WHEN** `bin/publish-pages` runs on a site with `pr/5201/index.html`
- **THEN** the report is at `cassandra/pr/5201/` and `pr/5201/` redirects there

#### Scenario: Idempotent
- **WHEN** the migration runs again
- **THEN** nothing moves and no file changes

### Requirement: Poll and comment every project
`cpr poll` SHALL pick PRs of every project against that project's published heads, and `cpr comment`
SHALL link the project's page and post to the project's repository.

#### Scenario: Sidecar comment
- **WHEN** `cpr comment sidecar#400` runs
- **THEN** the body links `<site>/sidecar/pr/400/` and the plan targets apache/cassandra-sidecar
