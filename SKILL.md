---
name: vidux
description: "Thin plan, proof, and resume discipline for work that must survive sessions, agents, and tools."
---

# Vidux

Vidux is a repository-owned plan/proof/resume contract. It is not a model
router, scheduler, worker runtime, or provider transport.

Use it when work crosses sessions, workers, releases, or interruptions and a
cold reader must be able to continue without reconstructing a chat. Skip it for
a factual answer or an obvious small repair that needs no durable handoff.

## Read

Before acting:

1. Read repository instructions and the canonical `PLAN.md`.
2. Inspect the current revision and working tree.
3. Read only the proof named by the active row.
4. Resume `[in_progress]`; otherwise take the highest unblocked row.

Never overwrite or absorb unexplained work merely to make the tree clean.

## Cycle

```text
READ       plan, revision, working tree, named proof
ASSESS     active row first; otherwise highest unblocked row
ACT        one bounded, reversible change
VERIFY     the repository's real gate
CHECKPOINT result, proof, uncertainty, and one cold-resume next move
```

A row is complete only when its requested outcome exists and its named gate
passes. A commit, pull request, chat message, or activity count alone is not
proof.

`vidux checkpoint <plan> <task> <summary> --proof <text>` is an optional helper
for updating the plan and, when configured, appending a local ledger row.
Completion requires explicit proof text. Changes remain uncommitted unless
`--commit` is supplied. The plan remains authority; a ledger row never grants
permission to push, merge, deploy, spend, or communicate externally.

## Plan contract

`vidux init --here` creates a plan with:

- Purpose
- Evidence
- Constraints
- Operator Brief
- Outcome Scorecard
- Tasks
- Decision Log
- Progress

Use `pending -> in_progress -> completed`. Use `blocked` only with a concrete
reason and resume condition. Keep decision-relevant facts and cold-resume state
in the plan; put large evidence in linked repository files.

Do not make a second queue when an existing plan already owns the outcome.

## Ownership and delegation

One worker owns a writable surface at a time. Parallel work is safe only when
write surfaces are disjoint.

Give a worker:

- one observable outcome;
- bounded read and write paths;
- a verification gate;
- hard safety boundaries; and
- the required proof and cold-resume handoff.

Treat worker output as a draft until the owner reviews the diff and reproduces
important claims. The coding host owns dispatch, authentication, provider
selection, retries, and process lifecycle.

## Recovery

Before creating a branch or worktree, inspect existing branches, worktrees,
pull requests, and uncommitted changes with Git's normal commands. Resume or
preserve existing work before creating a duplicate lane.

Vidux ships no worktree cleanup automation and never removes another worker's
checkout.

## Public-data boundary

Public plans and examples must not store:

- credentials or private account data;
- billing, quota, or usage snapshots;
- runtime/session identifiers or raw conversation logs;
- private repository links or machine-specific paths; or
- worker execution receipts presented as product documentation.

Use synthetic examples. Keep provider routing and execution in the coding host.

## Local cockpit

`vidux browse` is a loopback, read-mostly projection of repository plans and
proof. Markdown remains authority. The browser does not make Vidux a hosted
control plane or worker runtime.

The Outcome / Ask / Steer schema and read-only validator are interchange
contracts only; they do not prove a GUI, persistence, execution, or live
steering.

## References

- [`docs/doctrine/DOCTRINE.md`](docs/doctrine/DOCTRINE.md)
- [`docs/doctrine/ARCHITECTURE.md`](docs/doctrine/ARCHITECTURE.md)
- [`docs/doctrine/LOOP.md`](docs/doctrine/LOOP.md)
- [`docs/CORE-CUT.md`](docs/CORE-CUT.md)
- [`docs/reference/outcome-ask-steer.md`](docs/reference/outcome-ask-steer.md)
