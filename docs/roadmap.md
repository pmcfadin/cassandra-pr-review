# Roadmap

The full pipeline the owner wants, split into OpenSpec changes, in order.

1. **review-report-foundation** (in progress): run `cpr review <PR>` locally. It fetches the PR,
   its sibling PRs, the JIRA ticket and the CI summaries; checks the merge requirements; rates how
   hard the PR is to review; and renders one HTML report with left-hand navigation, the
   recommendation on the first page, and the ide-explain diff view embedded.
2. **review-lenses**: AI review lenses (from the rustyrazorblade spec-flow reviewers, plus
   Cassandra-specific ones for compatibility, test regime and performance) run locally. Their
   findings fill the report's Code review section and let a PR reach `ready`.
3. **deeper-tests**: a further set of tests, still to be defined, which adds new check categories
   to the report.
4. **publish-and-comment**: commit reports to the public repo pmcfadin/cassandra-pr-review, serve
   them through GitHub Pages, and post the link as a comment on the PR from the owner's account.
5. **pr-polling**: a scheduled GitHub Action in our repo finds new or updated apache/cassandra PRs
   and runs the pipeline.
