# Architecture

Vidux has three layers:

```text
Repository files       PLAN.md, linked evidence, git revision
Deterministic helpers  init, status, doctor, validation and release gates
Local projection       read-mostly loopback browser
```

## Repository files

`PLAN.md` is the durable planning authority. It records the outcome, queue,
constraints, decisions, progress, proof references, and one cold-resume next
move. Git supplies revision and diff identity. Large evidence stays in linked
repository files.

Chat history, provider state, and a scheduler database are not planning
authority.

## Deterministic helpers

The CLI and scripts scaffold or inspect plans, validate bounded contracts, and
check release contents. They do not choose models, dispatch workers, supervise
processes, or authenticate proof.

The coding host owns execution. A host may use one worker or many; Vidux only
requires disjoint write ownership, a real verification gate, and a durable
handoff in the plan.

## Local projection

`vidux browse` starts a loopback server that projects repository plans and
local proof into a browser. Markdown remains authority. The browser is not a
hosted control plane and does not become a worker runtime.

Write routes remain local and bounded. See
[`docs/reference/browser.md`](../reference/browser.md) for the route and safety
contract.

## Interchange contract

The Outcome / Ask / Steer schema is a small provider-neutral status boundary.
Its validator proves only data shape and privacy invariants. The local cockpit
now renders that shape alongside existing plan and steering stores, but it
does not prove shared memory, worker execution, or live Steer application.

## Public boundary

The maintained source and package must not contain private repository links,
personal machine paths, credentials, account/billing data, runtime identifiers,
raw conversations, or private execution receipts.

Historical releases are never silently moved. A wrong surface is corrected by
a new exact release with an honest supersession note.
