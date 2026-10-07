# Roadmap

The full pipeline the owner wants, split into OpenSpec changes, in order. Items 3–8 came from
reviewer feedback on the first published reports (2026-10-07).

1. **review-report-foundation** (done): `cpr review <PR>` fetches the PR, sibling PRs, JIRA ticket,
   and CI summaries; checks merge requirements; rates review difficulty; renders one HTML report.
2. **review-lenses** (done): `/review-pr` runs a parallel panel of AI review lenses and renders
   their findings; verdicts split by who must act.
3. **reviewer-context** (next): related tickets from `git blame` of the changed lines, suggested
   reviewers, and the people most experienced with each file, from `patch by` / `reviewed by` history.
4. **cassandra-lenses**: replace the generic spec-flow lenses with Cassandra-native lenses built from
   apache/cassandra's own `.claude/skills` review methods and bug-pattern catalog (concurrency,
   serialization and versioning, lifecycle and ordering, IO and crash safety); dedupe overlapping
   findings into one list. Removes the spec-flow dependency.
5. **static-analysis**: PMD (cognitive complexity, copy-paste) and the project's real checkstyle on
   changed files, split into introduced-by-this-PR vs already-there; perf commit-structure check
   (benchmark commit first, then the change).
6. **build-and-coverage**: build the branch and run the tests the PR touches or affects with JaCoCo
   (`ant jacoco-run`); report coverage of changed lines.
7. **perf-ab**: for core-path changes, run JMH (`test/microbench`) on the benchmark commit and the
   PR head so reviewers can A/B.
8. **easy-db-lab-plan**: auto-generate an easy-db-lab `plan.md` per PR (branch built with
   rustyrazorblade/cassandra-builds, a workload matched to the change, compared against the base
   branch), embedded in the report.
9. **publish-and-comment**: publishing to GitHub Pages exists (`bin/publish-pages`); add posting the
   report link as a PR comment from the owner's account.
10. **pr-polling**: a scheduled GitHub Action in our repo finds new or updated apache/cassandra PRs
    and runs the pipeline.
