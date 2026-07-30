# Core Concepts

A small set of ideas for keeping long-running coding work inspectable and
resumable.

## The Three Layers

```
┌─────────────────────────────────────────────┐
│                  CONTRACT                   │
│  repository plan + proof + resume boundary  │
└──────────────────────┬──────────────────────┘
                       │ governs
┌──────────────────────▼──────────────────────┐
│                  THE CYCLE                  │
│  Read → Assess → Act → Verify → Checkpoint  │
└──────────────────────┬──────────────────────┘
                       │ reads/writes
┌──────────────────────▼──────────────────────┐
│             REPOSITORY AUTHORITY            │
│  PLAN.md + linked proof + Git revision      │
└─────────────────────────────────────────────┘
```

- **Contract** — the boundary. Vidux owns repository plan/proof/resume state;
  the coding host owns execution.
- **The Cycle** — one bounded row through read, assess, act, verify, checkpoint.
- **Repository authority** — the plan, linked proof, current revision, and
  working tree.

## Why These Three Layers?

**Without the contract**, a plan tool can quietly become a scheduler, router,
or second source of truth.

**Without the cycle**, a worker can act before reading current state or claim
completion before running the named gate.

**Without repository authority**, the next reader must reconstruct mutable state
from chat, provider history, or private runtime data. `PLAN.md`, linked proof,
and Git are sufficient; an optional local ledger is only a projection.

## Key Concepts

- [Five Principles](/concepts/principles) — the doctrine that governs agent behavior
- [The Cycle](/concepts/cycle) — READ → ASSESS → ACT → VERIFY → CHECKPOINT mechanics
- [PLAN.md Structure](/concepts/plan-structure) — the full template with all required sections
- [Repository Authority](/concepts/store) — how state persists across sessions and workers
- [No External Integrations](/concepts/extensions) — why Vidux does not sync
  with external boards or issue trackers
