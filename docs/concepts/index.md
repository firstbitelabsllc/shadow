# Core Concepts

Vidux is built on a small set of ideas, each chosen to solve a specific failure mode of stateless AI agents.

## The Three Layers

```
┌─────────────────────────────────────────────┐
│                  DOCTRINE                   │
│  5 principles + gate patterns + stuck detect│
└──────────────────────┬──────────────────────┘
                       │ governs
┌──────────────────────▼──────────────────────┐
│                  THE CYCLE                  │
│  Read → Assess → Act → Verify → Checkpoint  │
└──────────────────────┬──────────────────────┘
                       │ reads/writes
┌──────────────────────▼──────────────────────┐
│                  THE STORE                  │
│  PLAN.md + ledger + evidence/ + git         │
└─────────────────────────────────────────────┘
```

- **Doctrine** — the rules. Five principles and gate patterns that govern how agents behave.
- **The Cycle** — the loop. Five steps that every agent session follows, in order, without skipping.
- **The Store** — the files plus ledger rows. Where queue state, evidence, investigations, shipped-cycle proof, and git transport evidence live.

## Why These Three Layers?

**Without doctrine**, agents make different decisions each session and gradually drift apart. Two agents working the same project will eventually contradict each other.

**Without the cycle**, agents skip steps under time pressure. Evidence gathering gets skipped when there's "obvious" work. Verification gets skipped when the diff "looks right." Checkpointing gets skipped when the session ends abruptly.

**Without the store**, state lives in chat history or agent memory -- both of which die when the session ends. Repo files plus matching publish ledger rows are the reliable recovery packet; git transports the diff when code changed, but it does not replace a missing plan/ledger packet.

## Key Concepts

- [Five Principles](/concepts/principles) — the doctrine that governs agent behavior
- [The Cycle](/concepts/cycle) — READ → ASSESS → ACT → VERIFY → CHECKPOINT mechanics
- [PLAN.md Structure](/concepts/plan-structure) — the full template with all required sections
- [The Store](/concepts/store) — how state persists across sessions and agents
