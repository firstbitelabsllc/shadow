# What is Pilot Puppy?

Pilot Puppy keeps AI coding work recoverable across sessions, agents, or days by making the plan, proof, decisions, and resume point explicit on disk. Vidux remains the compatibility core that stores that durable truth.

## The Core Problem

A common failure mode is state loss:

- The plan lived in chat instead of files
- Code was written before evidence existed
- A later session could not tell what was intentional
- The same bug got "fixed" three different ways

When prior context is unavailable, a new reader can miss what was intentional,
why a choice was made, or what not to touch. Repository authority makes those
facts inspectable.

## The Solution

Vidux keeps the recovery packet in the repository. The owning `PLAN.md` records
the outcome, queue, decisions, progress, proof references, and one next move.
Linked evidence and Git identify what was actually checked and changed.

```
PLAN.md — planning authority
├── What to build (tasks with status tags)
├── Why it was decided (Decision Log)
├── What passed (proof references)
└── Where to resume (Progress)

Git — revision and diff identity
└── What changed and where the checked revision lives
```

## How It Works

One bounded row flows through five steps:

1. **READ** — Load PLAN.md, check git log, scan for uncommitted work
2. **ASSESS** — Resume `[in_progress]`, otherwise choose the highest unblocked row
3. **ACT** — Make one bounded, reversible change
4. **VERIFY** — Run the row's named build, test, or interaction gate
5. **CHECKPOINT** — Record result, proof, uncertainty, and one cold-resume move

Repository files and Git are sufficient for this loop. The coding host decides
how to execute the row, which model or worker to use, and when to retry.

## Optional Local Checkpoint Helper

`vidux checkpoint` is a shipped convenience command for a plan that already
contains the matching task:

```bash
vidux checkpoint PLAN.md "Task text" "verified result" \
  --proof "named gate passed"
```

Completion requires `--proof`; a blocked checkpoint requires a concrete
`--blocker`. The helper updates the task and Progress entry and leaves those
changes uncommitted by default. `--commit` stages the plan and asks Git to
create a commit; review the existing index first.

If a local ledger is configured, the helper may also append a checkpoint row.
Local `done` maps to `needs_review`, not an open pull request or shipped state.
The row is not planning authority, proof by itself, or a prerequisite for push,
review, merge, release, or deployment.

## Core Invariants

- Reuse the existing plan when it already owns the outcome.
- Resume an active row before starting another.
- One worker owns a writable surface at a time.
- Treat worker output as a draft until the owner reproduces important proof.
- A row is complete only when the outcome exists and the named gate passes.
- Keep provider routing, scheduling, credentials, and process lifecycle in the
  coding host.

## Next Steps

- [Install Pilot Puppy](/guide/installation) — set up the Vidux compatibility CLI or tested Claude Code skill
- [Quick Start](/guide/quickstart) — run your first cycle
- [Five Principles](/concepts/principles) — understand the doctrine
