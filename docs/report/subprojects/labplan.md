# Lab plan

## What is checked

Nothing. For Cassandra Sidecar and Cassandra Analytics there is no lab plan: the section summary reads "No lab plan: no lab plan for Cassandra Sidecar: the plans build and load a Cassandra server cluster" (or Cassandra Analytics), and it never affects the verdict.

## Why

The lab plans try a Cassandra server change on a real cluster with [easy-db-lab](https://github.com/rustyrazorblade/easy-db-lab): they build two Cassandra commits, install both on the same nodes, and compare a stress workload. A Sidecar or Analytics change does not change the Cassandra server, so that comparison does not apply. A plan for these projects would need different steps, which the plan rules do not have.

## How each status is decided

The section has no checks. Its status badge is always **not-applicable**, with the reason above. The project profile turns plans off (`labplan: false`), so the diff is not read.

## How to fix

There is nothing to fix. To try a change on a cluster, use the project's integration tests (see the Testing aspect), or set up a cluster by hand.

## Limits

- No plan is produced for any PR of these projects, including performance changes to the bulk writer or reader.
