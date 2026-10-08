# easy-db-lab plan section: research

Input for roadmap item 8 (`easy-db-lab-plan`). Researched 2026-10-07. Decision from memory: the report **generates and embeds a `plan.md` per PR only**. It never provisions AWS and never runs a plan. Everything below was read from files, `--help` output and GitHub (read-only); no cluster command was run. No repo code was changed.

Sources (all local unless noted): plugin `~/.claude/plugins/cache/rustyrazorblade-plugins/easy-db-lab/0.12.1/` (`skills/plan`, `skills/run`, `references/{plan-template,cassandra,environment,commands}.md`); binary 12 at `/opt/homebrew/Cellar/easy-db-lab/12/` (needs JDK 21: `JAVA_HOME=/opt/homebrew/opt/openjdk@21`; `help`, `commands`, `kit list`, `<cmd> --help` all work offline); GitHub `rustyrazorblade/cassandra-builds`, `rustyrazorblade/easy-db-lab` (`test-plans/`), `apache/cassandra-easy-stress`.

## Findings in one table

| Question | Answer |
|---|---|
| Plan format | Markdown with fixed headings: `# Lab Plan: <title>`, `## Objective`, `## Cluster Name`, `## Datacenters`, `## Environment`, `## Steps` (`### N. name`, prose, one fenced `bash` block, Pass/Fail lines), `## Notes`. Only `Cluster Name` and `Datacenters` are parsed by the runner; steps are read by an LLM and executed one at a time. |
| Real examples | Yes: 17 plans in `rustyrazorblade/easy-db-lab/test-plans/`. Closest to ours: `cassandra-build-s3-ecr-stress-validation.md` and `cassandra-6.0-rustyrazorblade-install-and-stress.md`. |
| Custom build, no AWS needed to *prepare* | `cassandra-builds` workflow `build-cassandra-ref.yml` builds any ref/SHA from any fork and publishes a tarball on a GitHub release. The plan then runs `cassandra install <name> --url <tarball> --java N`. |
| Blocker for the build step | `pmcfadin` has pull-only access to `rustyrazorblade/cassandra-builds` (`permissions.push=false`), so `gh workflow run` against it fails. Decision needed (see Open decisions). |
| Workloads | `cassandra-easy-stress` ships 16 workloads (list in section 3). `kit list` has only non-Cassandra kits (clickhouse, flink, ignite3, kafka, postgres, presto, sysbench, tidb, trino): irrelevant to Cassandra PRs. |
| `stress list` | Needs a provisioned cluster; the list in this doc comes from the stress repo's source (`src/main/kotlin/.../workloads/`). Re-verify at run time with `$EDB cassandra stress list`. |
| A/B shape | One cluster, both builds installed side by side, arms run sequentially in A B B A order, data wiped between arms. Cheaper than two clusters and removes hardware variance. |
| When to skip | docs-only, tests-only, build/CI-only, python tooling, or no production file under `src/java` that touches a server path. |
| Embed | A "Lab plan" section: rendered markdown (the report's `renderMarkdown` already handles fences and tables), Copy and Download buttons, a "not run" banner. Plan text lives in the report model; generation is deterministic, no model tokens. |

## 1. The plan format and what `easy-db-lab:run` expects

Template (`references/plan-template.md`, verbatim structure):

```markdown
# Lab Plan: <title>
## Objective          <research question; hypothesis; what metric defines success>
## Cluster Name       <cassandra-cluster-name>
## Datacenters        single            (or "- dc1: 10.0.0.0/16" lines)
## Environment        <nodes, instance types, storage>
## Steps
### 1. <Step name>    <prose> + ```bash <command>``` (+ **Pass:** / **Fail:** lines)
## Notes              <caveats, follow-ups>
```

What the runner does with it (`skills/run/SKILL.md`):

| Runner behavior | Consequence for a generated plan |
|---|---|
| Reads `## Cluster Name` and `## Datacenters`; asks the user for anything else (binary path, `--jdk`). | Always emit both headings. Name must be a valid cluster name: use `pr<N>-<short-sha>`. |
| `setup-cluster.sh <dir> <binary> --name N --plan plan.md` copies the plan to `<dir>/docs/plan.md`, scaffolds `journal.md`, `issues.md`, `results.md`, mdbook. | The plan must be self-contained; it is copied, not referenced. |
| Builds a checklist from `## Steps`, asks "Ready to execute?" per step, logs every command in `journal.md`. | One step = one command block or one tight group. Step titles become checklist lines: keep them short. |
| Commands use `$EDB` (the wrapper in the cluster dir), never bare `easy-db-lab`. | Emit `$EDB ...`. |
| Re-verifies each command against `references/commands.md` before running. | Every flag must exist; generator should self-check (section 7). |
| Provisioning (`init ... --up`) takes minutes; commands run in the foreground to completion. | Do not put background or `&` in steps. |
| After the last step: writes `results.md`, `make -C docs`, then asks keep-or-`down`. | Last step must be teardown (`$EDB down --auto-approve`), because cost matters. |
| `plan` skill's review gate: every check falsifiable, a step that records results, teardown included, "artifact exists is not feature works". | Each step gets **Pass:** and **Fail:** lines; the control arm must be able to fail. |

Gotchas from `references/cassandra.md` that the generator must encode (each cost someone a run):

| Gotcha | Rule |
|---|---|
| `stress start` parses option-shaped tokens itself. | Always `stress start -- <Workload> -d 30m ...` (note the `--`). |
| `--rate` is a global total; `--populate` is per thread. | Say so in the step; `-t 8 --populate 10m` writes 80m rows. |
| `exec run` has no shell; a non-zero exit discards all output. | Wrap in `bash -c "..."`, end with `; exit 0` when grepping. |
| `cassandra use` re-applies `cassandra.patch.yaml` to the hosts it targets. | `use` first, then per-host config. |
| `update-config` replaces the whole config from `conf.orig`. | Patch file must be complete; start from `write-config` output. |
| DB nodes need a data disk. | Use an NVMe type (`i4i.xlarge`) or `--ebs.type`. |
| `cassandra use <ver>` may switch JDK. | Pass `--java` on `install` explicitly. |
| `cassandra list` reads one node. | Check other nodes by `ssh -F "$(dirname "$EDB")/sshConfig" dbN`. |

### Reconstructed minimal example (offline-verified command names)

```bash
$EDB init pr5201-d1095cbd --db.count 3 --app.count 1 \
  --db.instance-type i4i.xlarge --app.instance-type i4i.xlarge --up
$EDB cassandra install pr5201-base --url <tarball-url> --java 11
$EDB cassandra use pr5201-base
$EDB cassandra start
$EDB cassandra nt status
$EDB cassandra stress start --name base --tags "arm=base,pr=5201" -- KeyValue -d 30m -t 100 --rate 20k
$EDB cassandra stress status
$EDB down --auto-approve
```

Flag facts confirmed with `--help` on binary 12: `cassandra install [--url <tarball.tar.gz | git url with --branch>] [--branch] [--java|-j] [--python] [--ant-flags] [--hosts] <version>`; `cassandra build [-j N] [--ant-flags] [--name] [--jira] [sourceDir]` builds locally and publishes to S3 (needs AWS, so not used by the generator); `cassandra stress start [--name] [--image] [--tags] -- <args>`; `exec run [-t cassandra|stress|control] [--hosts] [--bg] [--name] <command>`; `init <name> [--db.count] [--app.count] [--db.instance-type] [--app.instance-type] [--up]`.

## 2. Building the base and the PR head

`cassandra-builds` README and `build-cassandra-ref.yml` (read via `gh api`):

| Fact | Detail |
|---|---|
| Trigger | `gh workflow run build-cassandra-ref.yml -f ref=<branch\|tag\|sha> -f repo=<owner/name> [-f jdk=11] [-f base_image=...]`. `repo` defaults to `apache/cassandra`; `ref` may be a raw SHA (`resolve_ref` accepts one without a remote lookup). |
| Auto JDK/flags | `4.*` -> JDK 11 with `-Duse.jdk11=true`; `5.0*` -> JDK 17; everything else (5.1+, trunk) -> JDK 21. Source: `resolve-build-plan.sh`. |
| Version string | Read from `base.version` in the ref's `build.xml` (cassandra-4.0 at `3ccf9476`: `4.0.22`; trunk: `7.0`). |
| Artifacts | GHCR image `ghcr.io/<owner>/cassandra-builds/cassandra` (tag = sanitized ref) and a tarball on release **tag = sanitized ref**, named `apache-cassandra-<base.version>-<sha12>-bin.tar.gz`. A 40-hex SHA as `ref` therefore gives a unique release per SHA. |
| URL | `https://github.com/<builds-repo>/releases/download/<ref_tag>/apache-cassandra-<base.version>-<sha12>-bin.tar.gz`. Computable before the build runs if the generator reads `base.version` at that SHA (`git show <sha>:build.xml`). Verify with `gh release view <ref_tag> -R <builds-repo> --json assets` after the build. |
| Branch refs move | A branch-name release is deleted and recreated on every build. Always pass a **SHA**, never a branch name, for both arms. |
| Nightly URLs | `.../releases/download/nightly/apache-cassandra-<label>-bin.tar.gz` are stable but track branch HEAD (`5.0-HEAD`, `6.0-HEAD`, `trunk`). Not usable for a fixed base commit. |
| Cleanup | Per-SHA releases accumulate. Plan teardown step: `gh release delete <sha> -R <builds-repo> --cleanup-tag --yes`. |

Choosing the two refs from our bundle:

| Arm | `repo` | `ref` | Source in our code |
|---|---|---|---|
| base | `apache/cassandra` | merge-base SHA of PR head and `baseRefName` (for 5201: `3ccf9476`; for 4967: `8cfc3a67`) | already computed for static analysis (`git inputs`) |
| PR head | `headRepository.nameWithOwner` (5201: `nivykani/cassandra`; 4967: `belliottsmith/cassandra`) | `headRefOid` (5201: `d1095cbd...`; 4967: `f72d4f0e...`) | `gh pr view --json headRefOid,headRepository` |

Use the merge-base, not the current branch tip, so the only difference between arms is the PR's own diff.

Plan commands for each arm (shown for 5201; `BUILDS=rustyrazorblade/cassandra-builds` or our fork):

```bash
# build (run on the owner's machine, not on the cluster)
gh workflow run build-cassandra-ref.yml -R "$BUILDS" -f repo=apache/cassandra -f ref=3ccf9476...FULLSHA
gh workflow run build-cassandra-ref.yml -R "$BUILDS" -f repo=nivykani/cassandra -f ref=d1095cbdca4173277488e6e93abeb06a35ea0bb8
gh run list -R "$BUILDS" -w build-cassandra-ref.yml -L 2          # wait for success
# install on the cluster (names are free text; they become /usr/local/cassandra/<name>)
$EDB cassandra install pr5201-base --java 11 --url https://github.com/$BUILDS/releases/download/<BASESHA>/apache-cassandra-4.0.22-<BASESHA12>-bin.tar.gz
$EDB cassandra install pr5201-head --java 11 --url https://github.com/$BUILDS/releases/download/d1095cbdca4173277488e6e93abeb06a35ea0bb8/apache-cassandra-4.0.22-d1095cbdca41-bin.tar.gz
```

Notes: `--java` for `install` takes the runtime JDK (4.0: 11 matches the builds repo; 8 also valid for 4.0, but stay with the build JDK). `install` is idempotent per host ("already present"; seen in the 6.0 plan). The workflow resolves `ref` against `repo` with `git ls-remote`; a fork PR head SHA is reachable in the fork. Pitfall to check at generation time: if the head repo was deleted, fall back to `refs/pull/<N>/head` on `apache/cassandra` (untested; `resolve_ref` tries tag and branch forms, so confirm before relying on it).

## 3. Workloads and the change-to-workload mapping

`cassandra-easy-stress` workloads (source dir listing): `AllowFiltering, BasicTimeSeries, CountersWide, CreateDrop, DSESearch, KeyValue, LWT, Locking, Maps, MaterializedViews, RandomPartitionAccess, RangeScan, SAI, Sets, TxnCounter, UdtTimeSeries`. Flags used (manual + plugin gotchas): `-d <dur>` (min 1 min), `-t` threads, `--rate` global ops/s, `-r` read fraction (0 = writes only), `-p` partition count, `--populate N` (per thread, finishes before `-d` starts), `--compaction stcs|lcs|twcs|ucs`, `--workload.<param>=...`, `--parquet file` (per-op latencies, DuckDB-ready). `TxnCounter` is annotated `@RequireAccord`; `--workload.impl=ACCORD` creates the table `WITH transactional_mode='full'`, `LWT` is the comparator.

Inputs to the mapping: changed paths (`cpr/paths.py`: `is_prod`, `subsystem`), compat surface labels (`cpr/checks/compat.py: SURFACES` via `touched_surfaces`), `triage.json` `concurrency_paths` and `hard_surfaces`, and `upgrade_sensitive_files` from triage. Rules are evaluated top to bottom; a PR can match several, the generator keeps the first two by changed-line weight and emits one scenario per match.

| # | Match (any changed prod path starts with) | Scenario | Workload and parameters | Compare |
|---|---|---|---|---|
| 1 | `db/commitlog/`, `db/lifecycle/`, `hints/`, delete/cleanup code in `io/sstable/` (title or diff mentions crash, delete, corrupt, txn log, ordering) | **crash** | Write load plus compaction, repeated `kill -9` and restart, N cycles | restart success rate, error lines in `system.log`, base vs head |
| 2 | `db/compaction/` | **compaction** | `RandomPartitionAccess -r .1 -p 10m` plus `--compaction` set to the strategy named in the changed file (`LeveledCompactionStrategy` -> `lcs`, `TimeWindow` -> `twcs`, `unified` -> `ucs`, else `stcs`); `BasicTimeSeries` for TWCS | write throughput, pending compactions, bytes compacted, disk used, p99 |
| 3 | `io/sstable/` (not delete-only), `io/compress/`, `db/rows/`, `db/partitions/` | **write+read mix** | `KeyValue -r .5` on a dataset larger than the page cache | throughput, p99, GC, sstables per read |
| 4 | `db/memtable/`, `utils/memory/`, `db/Memtable*` | **memtable** | `KeyValue -r 0` (writes only; leave `--rate` unset, confirm default is unthrottled with `stress info`), then `BasicTimeSeries` | write throughput, GC pause, heap, flush count |
| 5 | `db/SinglePartitionReadCommand`, `cache/`, `db/ReadCommand*`, `service/reads/` | **read path** | `KeyValue -r .95 -p 1m` after `--populate`; `RandomPartitionAccess` for wide partitions | read p50/p99, cache hit rate (`nt info`) |
| 6 | `db/PartitionRangeReadCommand`, `service/reads/range` | **range scan** | `RangeScan --workload.table=...` after populate | scan duration, p99 |
| 7 | `index/sai/`, `index/` | **index** | `SAI` (set `--workload.fields` / indexed fields) | query p99, index build time, disk |
| 8 | `db/view/` | **views** | `MaterializedViews` | write throughput, view lag |
| 9 | `service/paxos/`, `cql3/statements/*Conditional*` | **LWT** | `LWT`, `Locking`; threads high, `-p` small to force contention | ops/s, p99, contention errors |
| 10 | `service/accord/`, `accord` in path | **Accord** | `TxnCounter --workload.impl=ACCORD` with `LWT` comparator (`--workload.impl=LWT`) in the same run; needs `accord.enabled: true` in the patch file and a trunk build | txn ops/s, p99, executor queue and cache metrics (`AccordExecutorMetrics`, `AccordCacheMetrics` if present) |
| 11 | `repair/`, `streaming/`, `service/ActiveRepairService` | **node ops** | `KeyValue -r .5` background; stop one node 10 min, start, `nt repair -full`; second variant: `nt decommission` is out of scope (needs spare node) | repair time, streamed bytes, load p99 during repair |
| 12 | `net/`, `*Serializer*`, `MessagingService`, `io/sstable/format/`, `db/commitlog/` format, any file `upgrade_sensitive_files` flagged | **mixed-version** | Install base on all, upgrade **one** node to head (`install --hosts`, `use --hosts`), run `KeyValue -r .5` against the mixed ring, then upgrade the rest, `nt upgradesstables` if sstable format changed | errors in client and `system.log`, schema agreement, all nodes UN |
| 13 | `transport/`, `cql3/` (parser, no execution path) | **smoke** | `KeyValue -d 5m` on head only; add `cqlsh` statement for the changed feature | starts, serves traffic |
| 14 | `config/Config.java`, `conf/*.yaml` only | **n/a** unless a default changed: then A/B the config on the *same* build via `update-config` | `KeyValue -r .5` | only if the default affects latency/throughput |
| 15 | `tools/nodetool/`, `metrics/`, `db/virtual/`, `db/guardrails/`, `auth/` | **smoke** | start the head build, run the changed command, read the vtable/metric | command works |
| 16 | `utils/`, `concurrent/`, `tcm/`, `gms/` (concurrency paths, no matching rule above) | **mixed read/write** | `KeyValue -r .5 -t 200` | throughput, p99, GC, thread-pool pending (`nt tpstats`) |

Multiple matches combine: 5201 matches rule 1 only. 4967 matches rule 10 (64 of 85 prod files under `service/accord`) and also rule 4 (`db/memtable`, 2 files), 11 (repair/ActiveRepairService, 3 files) and `metrics/` (rule 15). Keep the top two by line weight: Accord plus smoke. Cap at two scenarios per plan to bound cost.

## 4. A/B design

Cluster and runtime defaults (all overridable in the generator config):

| Item | Default | Reason |
|---|---|---|
| Cluster | 3 db + 1 app (stress), single DC | Smallest ring with RF=3 that has quorum and `--hosts` subsets; same shape as both real plans. |
| Instances | `i4i.xlarge` db and app (4 vCPU, 32 GiB, local NVMe) | NVMe satisfies the data-disk rule; used by the maintainers' own plans. |
| Version setup | install base and head side by side, `cassandra use` to switch | One cluster, same hardware; switching resets `cassandra.patch.yaml`, so use `use` first, then wipe data. |
| Data reset between arms | `stop`, `exec run -t cassandra bash -c "find /mnt/db1/cassandra -mindepth 1 -delete"` (path from cassandra.md gotchas), verify `find ... \| wc -l` is 0, `start` | Verified order from the plugin: check emptiness before restart. |
| Calibration | 5 min `KeyValue -r .5` on base, run twice | Spread = error bar on every reported delta. Required by the runner's "parallel arms" guidance. |
| Arm order | A B B A (base, head, head, base) | Cancels drift (warm disk, thermal, noisy neighbor). |
| Per-arm timeline | populate (until done) + 5 min warm-up + 20 min measured | Short enough for about 3 h total. |
| Total | about 3 to 3.5 h wall clock for perf scenarios; crash scenario about 1.5 h | Estimate; confirm on first real run. Cost is roughly 4 x i4i.xlarge hours (look up current price). |
| Teardown | final step `$EDB down --auto-approve`; delete per-SHA releases | The runner offers keep or shut down; the plan requests shut down. |

Metrics and how to record them (every step writes to the journal; results go in a table in `results.md`):

| Metric | Source | Command |
|---|---|---|
| Throughput, latency | stress job summary and Grafana | `$EDB cassandra stress logs <arm>`; tag runs `--tags arm=base,pr=N`; optional `--parquet` for percentiles via DuckDB |
| p50/p99/p99.9 | same | read from the final summary of each measured job |
| GC | `nt gcstats` before and after each measured window (resets on read) | `$EDB cassandra nt gcstats` |
| Compaction | pending tasks, bytes | `$EDB cassandra nt compactionstats`, `nt tablestats <ks.table>` |
| Thread pools | blocked/pending | `$EDB cassandra nt tpstats` |
| Errors | `system.log` | `$EDB exec run -t cassandra bash -c "grep -c ERROR /mnt/db1/cassandra/logs/system.log; exit 0"` |
| Disk | data dir size | `$EDB exec run -t cassandra bash -c "du -sh /mnt/db1/cassandra/data; exit 0"` |

Decision rule printed in the plan: a delta counts only if it exceeds 2x the calibration spread and appears in both A-B pairs; otherwise report "no detectable difference". For crash scenarios the rule is: the **base arm must reproduce the failure at least once**, otherwise the result is "inconclusive", not "fixed".

When a plan is **not** useful (return `None` and the report shows "No lab plan: <reason>"):

| Condition | Test |
|---|---|
| docs only | all changed files satisfy `paths.is_doc` |
| tests only | no `paths.is_prod` file changed (tests, `test/resources`, `test/data`) |
| build, CI, packaging | only `paths.is_build` files |
| tooling outside the server | only `pylib/`, `tools/` non-nodetool, `ide/`, `.github/` |
| dependency bump | only `lib/`, `.build/*pom*` (offer smoke at most) |
| generated only | only `paths.is_generated` |
| too large to attribute | more than 300 prod files: refuse (A/B would not isolate anything) |

## 5. plan.md template

The generator fills this deterministically. Placeholders in `<>`; blocks in `[ ]` are included per scenario. The "Artifacts" and "Not run" parts are our additions; the runner ignores unknown headings.

````markdown
# Lab Plan: PR <N> <title>

> **Not run.** Generated by cassandra-pr-review from the PR diff on <date>. No cluster was created,
> no AWS resource touched, no command below was executed. Commands are checked against
> `easy-db-lab commands` only for spelling. Review before running.

## Objective
<one sentence hypothesis from scenario>. Success: <metric and threshold, or restart-success criterion>.

## Cluster Name
pr<N>-<head sha7>

## Datacenters
single

## Environment
3 db + 1 app, i4i.xlarge, Cassandra <base.version> (JDK <n>). Base = <base sha12> on <base branch>; head = <head sha12> from <head repo>.

## Artifacts under test
| | base | head |
|---|---|---|
| repo / ref | apache/cassandra @ <sha> | <fork> @ <sha> |
| build | `gh workflow run ...` | `gh workflow run ...` |
| tarball | <url> | <url> |

## Steps
### 1. Build both refs (on the owner's machine)
### 2. Provision
### 3. Install both builds
### 4. Calibrate (base, 5 min x 2)
### 5..n. Scenario steps (A B B A)
### n+1. Collect results table
### n+2. Teardown

## Results table (fill in)
| arm | run | ops/s | p99 ms | GC ms/s | pending compactions | errors |

## Notes
<changed paths driving this plan; skipped scenarios and why; caveats>
````

### 5.1 Filled: PR 5201 (cassandra-4.0, CASSANDRA-21649, `SSTable.delete` ordering)

Facts: one prod file, `io/sstable/SSTable.java`, +8/-11. Base `3ccf9476`, head `d1095cbdca4173277488e6e93abeb06a35ea0bb8` from `nivykani/cassandra`, `base.version` 4.0.22. The bug is a crash-safety one: after a crash, `LogFile.verifyRecord` compares REMOVE-record timestamps with files on disk; base deletes DATA first, so a partial delete changes the sstable's newest file time. The failing message on 4.0 (`LogFile.java:274`) is `Unexpected files detected for sstable [...]: last update time [...] should have been [...]`. Rule 1 (crash) matches; there is no perf claim, so no throughput A/B.

````markdown
# Lab Plan: PR 5201 CASSANDRA-21649 SSTable files deleted in last-modified order (4.0)

> **Not run.** Generated by cassandra-pr-review from the PR diff on 2026-10-07. No cluster was
> created and no command below was executed. Review before running.

## Objective
Hypothesis: on the base build, `kill -9` during compaction can leave a partially deleted sstable
whose transaction log fails `verifyRecord` at restart (node refuses to start); on the PR build it
never does. Success: head restarts cleanly in N/N cycles; base reproduces the log error at least once.

## Cluster Name
pr5201-d1095cb

## Datacenters
single

## Environment
3 db + 1 app, i4i.xlarge, Cassandra 4.0.22, JDK 11. Base 3ccf9476 (apache/cassandra cassandra-4.0);
head d1095cbdca41 (nivykani/cassandra).

## Steps

### 1. Build both refs (owner's machine)
```bash
BUILDS=rustyrazorblade/cassandra-builds   # or the owner's fork; needs workflow write access
gh workflow run build-cassandra-ref.yml -R $BUILDS -f repo=apache/cassandra -f ref=3ccf9476<full 40-hex sha>
gh workflow run build-cassandra-ref.yml -R $BUILDS -f repo=nivykani/cassandra -f ref=d1095cbdca4173277488e6e93abeb06a35ea0bb8
gh run list -R $BUILDS -w build-cassandra-ref.yml -L 2
```
**Pass:** both runs `success`; `gh release view <sha> -R $BUILDS` lists `apache-cassandra-4.0.22-<sha12>-bin.tar.gz`.

### 2. Provision
```bash
$EDB init pr5201-d1095cb --db.count 3 --app.count 1 --db.instance-type i4i.xlarge --app.instance-type i4i.xlarge --up
$EDB status
```

### 3. Install both builds on all nodes
```bash
$EDB cassandra install pr5201-base --java 11 --url https://github.com/$BUILDS/releases/download/<base sha>/apache-cassandra-4.0.22-<base sha12>-bin.tar.gz
$EDB cassandra install pr5201-head --java 11 --url https://github.com/$BUILDS/releases/download/d1095cbdca4173277488e6e93abeb06a35ea0bb8/apache-cassandra-4.0.22-d1095cbdca41-bin.tar.gz
```
**Pass:** both directories exist on db0, db1, db2 (`ssh -F "$(dirname "$EDB")/sshConfig" dbN ls /usr/local/cassandra`).

### 4. Arm A (base): create schema and start
```bash
$EDB cassandra use pr5201-base
$EDB cassandra start
$EDB cassandra nt status
$EDB cassandra cql "CREATE KEYSPACE IF NOT EXISTS crash WITH replication={'class':'SimpleStrategy','replication_factor':3}"
```
**Pass:** 3 nodes UN.

### 5. Arm A: kill during compaction, 30 cycles
Tiny sstables and aggressive compaction maximize obsolete-sstable deletions per minute.
```bash
$EDB cassandra stress start --name base-load --tags arm=base,pr=5201 -- KeyValue -d 40m -t 64 --rate 30k -r .1 --compaction "{'class':'SizeTieredCompactionStrategy','min_threshold':2}"
for i in $(seq 1 30); do
  $EDB cassandra nt --hosts db1 flush
  $EDB cassandra nt --hosts db1 compact
  sleep $((RANDOM % 8))
  $EDB exec run -t cassandra --hosts db1 bash -c "sudo systemctl kill -s KILL cassandra; exit 0"
  $EDB cassandra start --hosts db1
  $EDB exec run -t cassandra --hosts db1 bash -c "grep -c 'Unexpected files detected for sstable' /mnt/db1/cassandra/logs/system.log; exit 0"
done
```
**Record:** cycles where db1 did not reach UN, and the count of `Unexpected files detected` lines.
**Unverified until run:** the unit name `cassandra` for `systemctl kill`, whether `start --hosts` waits for UN, and the log path (taken from the plugin's cassandra.md).

### 6. Switch to head and repeat step 5 (arm B), then A again if base never failed
```bash
$EDB cassandra stop
$EDB exec run -t cassandra bash -c "find /mnt/db1/cassandra -mindepth 1 -delete; exit 0"
$EDB exec run -t cassandra bash -c "find /mnt/db1/cassandra -mindepth 1 | wc -l; exit 0"   # expect 0 on every node
$EDB cassandra use pr5201-head
$EDB cassandra start
```
Then rerun the schema statement and the step 5 loop with `--tags arm=head`.
**Pass:** head restarts in 30/30 cycles with 0 matching log lines.
**Fail:** any `Unexpected files detected` on head. **Inconclusive:** base shows 0 failures in 30 cycles (control cannot fail); extend to 100 cycles or mark the result not informative.

### 7. Sanity check on data, then collect
```bash
$EDB cassandra nt status
$EDB cassandra stress stop --all --force
$EDB cassandra nt compactionstats
```

### 8. Teardown
```bash
$EDB down --auto-approve
gh release delete <base sha> -R $BUILDS --cleanup-tag --yes
gh release delete d1095cbdca4173277488e6e93abeb06a35ea0bb8 -R $BUILDS --cleanup-tag --yes
```

## Notes
Only `io/sstable/SSTable.java` changed. The diff also swaps `deleteWithConfirm` for `delete`, so a
failed deletion is no longer an error: compare file-count leftovers in `data/` after the head arm.
The failure window is small; an inconclusive base arm is an expected outcome, not a plan defect.
````

### 5.2 Filled: PR 4967 (trunk, "Executor QoS", Accord cache/executor)

Facts (from `gh pr view`, read-only): trunk, head `f72d4f0e6f7be1c281b8b456b51bebc5ccc79ca9` from `belliottsmith/cassandra`, base/merge-base `8cfc3a67`, `base.version` 7.0 (JDK 21 auto-mapped). 173 files; of 85 under `src/java/org/apache/cassandra`, 64 are in `service/accord` (new `service/accord/execution/` package replacing `AccordExecutor`, `AccordTask`, `AccordCacheEntry`), plus new `metrics/Accord{Executor,Cache,Replica}Metrics`, 2 `db/memtable`, repair and StorageService touches, and a `build.xml` change. Rule 10 (Accord) matches with the LWT comparator; rule 15 (metrics) adds a smoke check; the rest is dropped by the two-scenario cap. The PR changes Accord internals only, so compat risk is low; it is a performance and stability question.

````markdown
# Lab Plan: PR 4967 Executor QoS (trunk, Accord executor and cache)

> **Not run.** Generated by cassandra-pr-review from the PR diff on 2026-10-07. Nothing below was executed.

## Objective
Hypothesis: the reworked Accord executor and cache (`service/accord/execution/*`) keeps or improves
`TxnCounter` throughput and p99 versus the merge-base, without more errors or GC. Success: head
p99 <= base p99 + 2x calibration spread and ops/s >= base - 2x spread, in both A-B pairs.

## Cluster Name
pr4967-f72d4f0

## Datacenters
single

## Environment
3 db + 1 app, i4i.xlarge, trunk (7.0), JDK 21. Base 8cfc3a67 (apache/cassandra); head f72d4f0e6f7b
(belliottsmith/cassandra). Accord enabled via patch file.

## Steps

### 1. Build both refs (owner's machine)
```bash
BUILDS=rustyrazorblade/cassandra-builds
gh workflow run build-cassandra-ref.yml -R $BUILDS -f repo=apache/cassandra -f ref=8cfc3a67<full sha>
gh workflow run build-cassandra-ref.yml -R $BUILDS -f repo=belliottsmith/cassandra -f ref=f72d4f0e6f7be1c281b8b456b51bebc5ccc79ca9
```

### 2. Provision
```bash
$EDB init pr4967-f72d4f0 --db.count 3 --app.count 1 --db.instance-type i4i.xlarge --app.instance-type i4i.xlarge --up
```

### 3. Install both builds
```bash
$EDB cassandra install pr4967-base --java 21 --url https://github.com/$BUILDS/releases/download/<base sha>/apache-cassandra-7.0-<base sha12>-bin.tar.gz
$EDB cassandra install pr4967-head --java 21 --url https://github.com/$BUILDS/releases/download/f72d4f0e6f7be1c281b8b456b51bebc5ccc79ca9/apache-cassandra-7.0-f72d4f0e6f7b-bin.tar.gz
```

### 4. Enable Accord in the patch file (complete file, never a stub)
```bash
$EDB cassandra use pr4967-base
$EDB cassandra write-config            # writes cassandra.patch.yaml
# append to cassandra.patch.yaml (keep every existing key):
#   accord:
#     enabled: true
$EDB cassandra update-config cassandra.patch.yaml
for h in db0 db1 db2; do ssh -F "$(dirname "$EDB")/sshConfig" $h "grep -E 'seeds:|cluster_name:|enabled: true' /usr/local/cassandra/current/conf/cassandra.yaml"; done
$EDB cassandra start
$EDB cassandra nt status
```
**Pass:** every node shows seeds, cluster_name and `enabled: true`; 3 nodes UN.
**Unverified until run:** that `accord.enabled` is the only switch needed on this commit (taken from `conf/cassandra.yaml` on trunk, lines 2866+). Also set the keyspace for `TxnCounter` (stress creates it); Accord needs `transactional_mode='full'`, which the workload sets.

### 5. Calibrate on base (2 x 5 min)
```bash
$EDB cassandra stress start --name cal1 --tags arm=base,phase=cal -- TxnCounter --workload.impl=ACCORD -d 5m -t 64 -p 100k --populate 1m
$EDB cassandra stress logs cal1 --tail 40
```
Repeat as `cal2`. Spread between cal1 and cal2 is the error bar.

### 6. Measured run, order A B B A
Per arm (warm 5 min is part of the 25 min job; discard first 5 min):
```bash
$EDB cassandra stress start --name acc-<arm>-<k> --tags arm=<arm>,pr=4967 -- TxnCounter --workload.impl=ACCORD -d 25m -t 64 -p 100k
$EDB cassandra stress start --name lwt-<arm>-<k>  --tags arm=<arm>,pr=4967 -- TxnCounter --workload.impl=LWT    -d 25m -t 64 -p 100k   # control workload: path the PR does not touch
$EDB cassandra nt gcstats
$EDB cassandra nt tpstats
```
Switch arm: `stop`, wipe data and verify 0 files (see PR 5201 step 6), `use pr4967-<arm>`, re-apply the same patch file (`use` re-applies `cassandra.patch.yaml`, so the Accord setting survives), `start`.
**Pass:** ACCORD ops/s and p99 within 2x calibration spread, no new `ERROR` lines mentioning `accord`, LWT control within spread on both arms.
**Fail:** ACCORD p99 or ops/s outside spread in both pairs, or head errors/timeouts.
Run the ACCORD and LWT jobs back to back (not together) if client capacity is the limit.

### 7. Smoke the new metrics
```bash
$EDB cassandra nt gcstats
```
Check that `AccordExecutorMetrics`/`AccordCacheMetrics` appear in Grafana after the head arm (names from the PR's new files; confirm against the metrics dashboard).

### 8. Teardown
```bash
$EDB down --auto-approve
gh release delete <base sha> -R $BUILDS --cleanup-tag --yes
gh release delete f72d4f0e6f7be1c281b8b456b51bebc5ccc79ca9 -R $BUILDS --cleanup-tag --yes
```

## Notes
Dropped scenarios (cap of two): memtable (2 files), repair (3 files). 173 files, with a new
`service/accord/execution` package: a regression here may be real or may be one executor tuning knob; the
plan measures, it does not attribute. `formalise/` and `modules/accord` changes are not exercised.
````

## 6. Embedding in the report

| Piece | Design |
|---|---|
| Generation | New `cpr/labplan.py`: `build_plan(bundle) -> {scenario, skipped, markdown}`. Pure function of the bundle (paths, title, body, base/head SHAs, head repo, `triage`, `compat.touched_surfaces`). Rules and defaults in `cpr/config/labplan.json`, same pattern as `triage.json`. No AI call. |
| Model | `model["lab_plan"] = {"markdown": "...", "scenario": [...], "skipped": null, "generated": "<date>"}` or `{"skipped": "docs only"}`. |
| Section | New aspect doc `docs/report/labplan.md` and a "Lab plan" section after "Testing" (before votes). It is informational: it has no gate, never affects the verdict. |
| Render | The report page already has `renderMarkdown` (fences, tables, lists, no network). Show the banner first, then the rendered plan, then a `<details>` with the raw markdown. |
| Buttons | **Copy**: `navigator.clipboard.writeText(md)` with a `textarea` + `execCommand("copy")` fallback (pages are also opened from `file://`). **Download**: `Blob` + `<a download="plan-pr<N>-<sha7>.md">`. Both operate on the model string, not the rendered HTML. |
| Banner text (fixed, not model-generated) | "Not run. This plan was generated from the diff. No cluster was created and no command was executed. Run it with `/easy-db-lab:run plan.md <cluster-dir>` only after reading it." |
| Skip text | "No lab plan: docs-only change" (or the reason from section 4). |
| Printing | Section follows the existing print rules (every section expanded); buttons hidden in `@media print`. |

## 7. Safety and verification of the generator

| Risk | Control |
|---|---|
| Wrong flag or subcommand in a plan | Generator test parses every `$EDB ...` line and checks the subcommand path and flags against a committed snapshot of `easy-db-lab commands` output (`tests/fixtures/edb-commands.txt`, refreshed manually; capture with `JAVA_HOME=/opt/homebrew/opt/openjdk@21 easy-db-lab commands`). The test never calls the binary. |
| `stress start` without `--` | Same test: any `stress start` line must contain ` -- `. |
| Plan implies we ran it | Fixed banner; steps are plain markdown, no executable hooks; nothing in `cpr/` shells out to `easy-db-lab`. |
| Untrusted PR text in plan | Title, branch and repo names are interpolated into shell lines. Validate with `^[A-Za-z0-9._/-]+$` (repos, refs, SHAs 40-hex); put anything else (title) only in prose, never in a code block. The Cluster Name uses `pr<N>-<sha7>` only. |
| Unverified runtime details | Each plan lists "Unverified until run" items (systemd unit name, log path, `start --hosts` waiting) so a runner double-checks them. |
| Cost surprise | Environment section states node count and type; estimated duration printed; teardown is a step. |

## Open decisions for the owner

1. **Who owns the build repo.** `pmcfadin` cannot dispatch workflows on `rustyrazorblade/cassandra-builds`. Options: fork it to `pmcfadin/cassandra-builds` (workflows run on the fork, tarballs land there, `BUILDS` changes), or ask the owner for a workflow-dispatch grant. Config key `builds_repo` in `labplan.json` either way.
2. **One cluster or two.** Default here is one cluster, sequential arms. Two parallel clusters finish faster but need a calibration run to compare hardware and double the cost.
3. **Cap and tiers.** Default: perf scenario 3 h, crash scenario 1.5 h, at most two scenarios, refuse above 300 prod files. Adjust once someone has run one plan for real.
4. **Fork SHA reachability.** Confirm `build-cassandra-ref.yml` checks out a SHA that exists only in a contributor fork (it should, via `repo=`), and decide the fallback if the fork is deleted.
5. **Validation pass.** The first real run should produce an `issues.md` that updates this doc's "Unverified until run" lists; no plan has been executed by us yet.
