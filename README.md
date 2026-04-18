<p align="center">
  <img src="assets/vidux-banner.svg" alt="vidux — plan first, code second" width="100%" />
</p>

<p align="center">
  <a href="https://github.com/leojkwan/vidux/stargazers"><img src="https://img.shields.io/github/stars/leojkwan/vidux?style=flat&color=3b82f6" alt="GitHub stars" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/leojkwan/vidux?style=flat" alt="License" /></a>
  <a href="https://github.com/leojkwan/vidux/commits/main"><img src="https://img.shields.io/github/last-commit/leojkwan/vidux?style=flat" alt="Last commit" /></a>
</p>

# Vidux

**Plan first, code second.** Vidux is a lightweight orchestration system for AI coding work that spans multiple sessions, agents, or days.

- **One source of truth** — every project has a single `PLAN.md`. All decisions, pivots, and progress live there.
- **Stateless agents** — each run starts fresh, reads the plan, does one task, checkpoints, and exits. No memory tricks.
- **Works everywhere** — Claude Code, Cursor, Codex. Any agent that can read markdown can pick up where the last one stopped.

<p align="center">
  <img src="assets/vidux-terminal-demo.svg" alt="vidux terminal session — READ, ASSESS, ACT, VERIFY, CHECKPOINT" width="780">
</p>

## Quick Start

```bash
git clone https://github.com/leojkwan/vidux.git
ln -sfn /path/to/vidux ~/.claude/skills/vidux
```

Then run `/vidux "your project description"` in Claude Code. The first cycle gathers evidence and writes a `PLAN.md`. No code is written until the plan is ready.

Optional enforcement hooks for a target repo (copy from `hooks/`):

```bash
cp hooks/pre-commit-plan-check.sh /path/to/your/project/.git/hooks/pre-commit
cp hooks/post-commit-checkpoint.sh /path/to/your/project/.git/hooks/post-commit
cp hooks/three-strike-gate.sh /path/to/your/project/.git/hooks/
```

## How It Works

Every change flows through a four-stage loop. Documentation is the control plane — not chat, not memory.

```mermaid
flowchart LR
    DOC["<b>Doc Tree</b><br/>PLAN.md + evidence/"]
    QUEUE["<b>Work Queue</b><br/>FIFO sliding window"]
    AGENT["<b>Fresh Agent</b><br/>stateless cycle"]
    CODE["<b>Code Change</b><br/>verified + checkpointed"]

    DOC -->|"doc edit creates"| QUEUE
    QUEUE -->|"agent pops item"| AGENT
    AGENT -->|"executes one task"| CODE
    CODE -->|"results feed back"| DOC

    style DOC fill:#2d333b,stroke:#539bf5,stroke-width:2px,color:#adbac7
    style QUEUE fill:#2d333b,stroke:#c69026,stroke-width:2px,color:#adbac7
    style AGENT fill:#2d333b,stroke:#57ab5a,stroke-width:2px,color:#adbac7
    style CODE fill:#2d333b,stroke:#986ee2,stroke-width:2px,color:#adbac7
```

Inside each agent run, five steps execute in order. No step is skippable:

```mermaid
flowchart LR
    R["READ<br/><i>PLAN.md, git log,<br/>git diff</i>"]
    A["ASSESS<br/><i>evidence exists?<br/>code or refine?</i>"]
    E["ACT<br/><i>execute tasks<br/>until queue empty</i>"]
    V["VERIFY<br/><i>build, test,<br/>gate</i>"]
    C["CHECKPOINT<br/><i>structured commit,<br/>progress entry</i>"]

    R --> A --> E --> V --> C
    C -.->|"next cycle"| R

    style R fill:#2d333b,stroke:#539bf5,stroke-width:2px,color:#adbac7
    style A fill:#2d333b,stroke:#c69026,stroke-width:2px,color:#adbac7
    style E fill:#2d333b,stroke:#57ab5a,stroke-width:2px,color:#adbac7
    style V fill:#2d333b,stroke:#986ee2,stroke-width:2px,color:#adbac7
    style C fill:#2d333b,stroke:#e5534b,stroke-width:2px,color:#adbac7
```

If the code is wrong, the plan is wrong — fix the plan first. The store persists across sessions; each run dies. Any fresh agent can rehydrate from files and continue.

## Why It Exists

Most agent failures are state failures:

- the plan lived in chat instead of files
- code was written before evidence existed
- a later session could not tell what was intentional
- the same bug got "fixed" three different ways

Vidux solves that by making documentation the control plane. State lives in markdown files in a git branch — no databases, no daemons, no memory tricks. Any agent can read the files, understand the world, and pick up where the last one stopped.

## How Vidux Compares

| | Vidux | Raw Claude Code / Cursor | Aider / OpenCode |
|---|---|---|---|
| **State** | `PLAN.md` in git — survives sessions, agents, days | Chat history — dies when the window closes | Session-scoped context |
| **Multi-agent** | Any agent reads the same files and picks up | Single agent per session | Single agent |
| **Verification** | Evidence → plan → execute → verify → checkpoint | Trust the output | Trust the output |
| **Fleet ops** | Draft-PR flow, session-gc, idle detection | N/A | N/A |
| **Agent agnostic** | Claude, Cursor, Codex — anything that reads markdown | Tool-specific | OpenAI / Anthropic |

Vidux doesn't replace your coding agent — it gives your agent a memory that outlasts the session.

## Core Invariants

A few hard rules that prevent the most common stateless-agent failures:

**One project, one `PLAN.md`** — course corrections update the existing plan's Decision Log, they never spawn a sibling plan. The Decision Log is the memory of why a pivot happened.

**Compound tasks + L2 investigations** — messy surfaces get a compound task that links to an `investigations/<slug>.md` sub-plan with seven sections. The L2 investigation is the work until the Fix Spec is filled.

**Append-only logs** — `PROGRESS.md` and `memory.md` are strictly append-only. Corrections go in new entries, not rewrites.

**3x stuck rule** — same task in 3+ consecutive progress entries while in-progress = auto-exit. Brake, not kill.

## What Ships Here

| Path | What |
|------|------|
| `SKILL.md` | Full contract: architecture, doctrine, loop, PLAN.md template, compound tasks |
| `CHANGELOG.md` | Release notes — latest doctrine changes and migration notes |
| `DOCTRINE.md` | The short doctrine (~5 min read) |
| `LOOP.md` | Stateless cycle mechanics |
| `ENFORCEMENT.md` | Claude Code hook configuration |
| `INGREDIENTS.md` | Design lineage (10 patterns from 26 surveyed tools) |
| `commands/` | `/vidux` (single entry point — discipline + automation) |
| `references/` | `automation.md` — deep doctrine (session-gc internals, Codex shim gotchas, PR lifecycle) |
| `scripts/` | vidux-loop, vidux-checkpoint, vidux-doctor, vidux-fleet-quality, vidux-fleet-rebuild, vidux-test-all |
| `scripts/lib/` | compat.sh, codex-db.sh, ledger-config.sh, ledger-emit.sh, ledger-query.sh, queue-jsonl.sh, resolve-plan-store.sh |
| `hooks/` | Prompt-hook nudges for plan discipline |
| `guides/` | draft-pr-flow, evidence-format, fleet-ops, harness, investigation, recipes |
| `tests/` | 144 contract tests (scripts, commands, doctrine, SKILL.md structure) |
| `examples/` | Worked examples (bug fix lifecycle, fleet reference) |

## Ecosystem

Vidux is the core discipline. It has **one entry point** — `/vidux` — that covers both planning and automation. Previously separate companion skills (`/vidux-plan`, `/vidux-auto`, `/vidux-claude`, `/vidux-codex`, `/vidux-fleet`, `/vidux-dashboard`, `/vidux-manager`) were merged or deprecated on 2026-04-17 to eliminate the "which command do I use?" friction.

| Skill | What it does | Ships in this repo? |
|---|---|---|
| `/vidux` | Full plan-first cycle (Part 1) + automation patterns (Part 2) — read, assess, act, verify, checkpoint; plus lane bootstrap, delegation modes, session-gc | Yes |
| `/pilot` | Universal project lead — detects stack and stage, routes into `/vidux` when needed | No (separate) |
| `/ledger` | Append-only JSONL activity log for multi-agent coordination across tools | No (separate) |

For deep automation details (session-gc internals, Codex shim registration, PR lifecycle nursing, cross-fleet coordination), `/vidux` reads [`references/automation.md`](references/automation.md) on demand — it is not loaded upfront.

## Platform Automation

Vidux is platform-agnostic — the cycle works for humans, one-shot sessions, and cron-scheduled fleets. The automation layer is **Part 2** of the single `/vidux` skill (`commands/vidux.md`), with the deep doctrine in [`references/automation.md`](references/automation.md):

- **Session management** — CronCreate lanes, session-gc, JSONL growth control
- **Lane operations** — coordinator pattern, decision tree, 6-lane hard cap
- **Delegation modes** — Mode A (research, compressed summary) and Mode B (implementation, diff review)
- **Lane bootstrap recipe** — decision tree (Claude-local vs Codex-local), role picker (coordinator/burst/radar), file templates, registration steps
- **Fleet ops** — discover, prescribe, validate, audit across automation fleets
- **PR lifecycle** — PR Nurse pattern, triage at cycle start, self-review before push

See [guides/fleet-ops.md](guides/fleet-ops.md) and [guides/recipes.md](guides/recipes.md) for full lifecycle docs and setup guides.

## Fleet Patterns

Patterns for autonomous multi-lane fleets. See `/vidux` Part 2 and [`references/automation.md`](references/automation.md) for mechanics, plus the [recipe catalog](guides/recipes.md) for 8 ready-to-deploy patterns with prompt templates.

- **Draft-PR-first** — automation pushes go through `gh pr create --draft`, never direct-to-main ([guide](guides/draft-pr-flow.md))
- **Progress is code change** — PRs that only touch `PLAN.md` / `investigations/` / `evidence/` / `INBOX.md` are bookkeeping, not progress. Bundle plan updates into the code PR, or keep notes local ([CHANGELOG](CHANGELOG.md#290--2026-04-17))
- **`observed` evidence type** — user-observed app behavior is first-class plan evidence alongside grep hits and PR comments
- **3x stuck rule** — same task in 3+ consecutive progress entries = auto-exit

## Lessons from Production (Apr 2026 fleet run)

Three findings from running 35+ Claude lanes and Codex agents across 5 repos for 48 hours:

**1. Stuck crons need exit conditions.** A verification cron confirmed PR #9 was live, then re-verified it 300+ times over 2 hours. Fix: after success, mark done and stop. The 3x stuck rule catches *failing* loops; *succeeding* loops that don't exit are a different bug.

**2. Ledger noise drowns signal.** The vidux-loop cron produced 395K empty `vidux_loop_start` entries in 2 days — 99.7% of all ledger volume. Fix: log once when idle, not per-PID per-fire. The ledger is only useful if real events are findable.

**3. Workspace-write flips the cost model.** When Codex writes code (`--sandbox workspace-write`) and Claude only reviews the diff, per-cycle Claude cost drops from ~10K tokens to ~2-3K. The expensive part (code generation) shifts to the unlimited Codex budget. This is now Mode B in `/vidux` Part 2.

## Documentation

- [Architecture](ARCHITECTURE.md) — three-layer overview with diagrams
- [Harness Setup](guides/harness.md) — writing automation prompts
- [Evidence Format](guides/evidence-format.md) — how to structure evidence files
- [Fleet Operations](guides/fleet-ops.md) — automation fleet management
- [Investigation Lifecycle](guides/investigation.md) — compound task L2 format
- [Draft PR Flow](guides/draft-pr-flow.md) — how automation lanes push code
- [Automation Recipes](guides/recipes.md) — 8 ready-to-deploy fleet patterns with prompt templates
- [Examples](examples/) — worked examples (start with [bug fix lifecycle](examples/bug-fix-lifecycle/))

## Sibling Project

**[claudux](https://github.com/leojkwan/claudux)** — documentation generator with multi-backend AI support (Claude + Codex). If vidux is "plan before code," claudux is "docs before code." Same philosophy, different surface. Both skills let you pick between Claude (metered, taste) and Codex (unlimited, grunt work) for the heavy lifting.

## Contributing

This repo is public because the core ideas are meant to be reused and pressure-tested. Feedback is welcome through [GitHub Issues](https://github.com/leojkwan/vidux/issues). The public repo ships the portable Layer 1 core, not private Layer 2 project wiring.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines and [SECURITY.md](SECURITY.md) for the vulnerability reporting policy.
