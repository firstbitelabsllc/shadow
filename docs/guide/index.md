# What is Vidux?

Vidux is a lightweight orchestration system for AI coding work that spans multiple sessions, agents, or days.

## The Core Problem

Most agent failures are state failures:

- The plan lived in chat instead of files
- Code was written before evidence existed
- A later session could not tell what was intentional
- The same bug got "fixed" three different ways

When an AI session ends, its context is gone. When a new session starts, it has no idea what the previous one was doing, why decisions were made, or what not to touch. This is the root cause of the "agent drift" problem — where each new session makes slightly different decisions, and the codebase slowly becomes incoherent.

## The Solution

Vidux makes documentation the control plane. State lives in markdown files in a git branch — no databases, no daemons, no memory tricks. Any agent can read the files, understand the world, and pick up where the last one stopped.

```
PLAN.md — the only source of truth
├── What to build (tasks with status tags)
├── Why it was decided (Decision Log)
├── What happened (Progress log)
└── What we know (Evidence citations)
```

## How It Works

Every change flows through a four-stage loop:

```
Doc Tree → Work Queue → Fresh Agent → Code Change → Doc Tree
```

Inside each agent run, five steps execute in order. No step is skippable:

1. **READ** — Load PLAN.md, check git log, scan for uncommitted work
2. **ASSESS** — Does the next task have evidence? Code or refine?
3. **ACT** — Execute tasks until queue empty, blocker, or context budget
4. **VERIFY** — Build, test, visual proof
5. **CHECKPOINT** — Structured commit, progress entry in PLAN.md

If the code is wrong, the plan is wrong — fix the plan first. The store persists across sessions; each run dies. Any fresh agent can rehydrate from files and continue.

## How Vidux Compares

|  | Vidux | Raw Claude Code / Cursor | Aider / OpenCode |
|---|---|---|---|
| **State** | `PLAN.md` in git — survives sessions, agents, days | Chat history — dies when the window closes | Session-scoped context |
| **Multi-agent** | Any agent reads the same files and picks up | Single agent per session | Single agent |
| **Verification** | Evidence → plan → execute → verify → checkpoint | Trust the output | Trust the output |
| **Fleet ops** | Ready-PR flow, session-gc, idle detection | N/A | N/A |
| **Agent agnostic** | Claude, Cursor, Codex — anything that reads markdown | Tool-specific | OpenAI / Anthropic |

Vidux doesn't replace your coding agent — it gives your agent a memory that outlasts the session.

## Core Invariants

A few hard rules that prevent the most common stateless-agent failures:

**One project, one `PLAN.md`** — course corrections update the existing plan's Decision Log; they never spawn a sibling plan. The Decision Log is the memory of why a pivot happened.

**Compound tasks + L2 investigations** — messy surfaces get a compound task that links to an `investigations/<slug>.md` sub-plan. The L2 investigation is the work until the Fix Spec is filled.

**Progress is code change** — a PR that only touches `PLAN.md` / `investigations/` / `evidence/` / `INBOX.md` is bookkeeping, not progress. Bundle plan updates into the code PR that ships the fix, or keep notes local. This rule was codified in the repo's 2026-04-17 doctrine update.

**Append-only logs** — `PROGRESS.md` and `memory.md` are strictly append-only. Corrections go in new entries; retroactive rewrites destroy the history future agents need.

**3x stuck rule** — if the same task appears in 3+ consecutive progress entries while still in-progress, force a surface switch; the next cycle finds new evidence or the task stays blocked.

## Next Steps

- [Install Vidux](/guide/installation) — set up the skill in Claude Code
- [Quick Start](/guide/quickstart) — run your first cycle
- [Five Principles](/concepts/principles) — understand the doctrine
