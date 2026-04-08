# Vidux Quickstart

Get from zero to your first `/vidux` run in 5 minutes.

## 1. Install (60 seconds)

Clone, symlink, done.

```bash
git clone git@github.com:leojkwan/vidux.git
cd vidux

# Symlink to your AI tool(s) -- pick whichever you use
ln -sfn $(pwd) ~/.claude/skills/vidux     # Claude Code
ln -sfn $(pwd) ~/.cursor/skills/vidux     # Cursor
ln -sfn $(pwd) ~/.codex/skills/vidux      # Codex
```

Optional: install enforcement hooks (training wheels, not guardrails):

```bash
bash scripts/install-hooks.sh /path/to/your/project
```

## 2. First Run (3 minutes)

Open your AI tool in your project directory and type:

```
/vidux "add offline caching to the feed"
```

The first cycle is always GATHER. No code is written. The agent fans out research (codebase, team chat, code reviews), synthesizes findings, and writes a `PLAN.md`.

```
/vidux "add offline caching"
        |
        v
   Plan exists? --No--> GATHER phase
        |                    |
       Yes              Fan out research
        |                    |
        v                    v
   Resume from          Write PLAN.md
   last checkpoint      with evidence
        |                    |
        v                    v
   Execute next         Checkpoint commit:
   unchecked task       "vidux: initial plan"
```

When it finishes, you have a PLAN.md with:
- **Purpose** -- one paragraph, user-visible goal, no implementation details
- **Evidence** -- cited sources with `[Source: ...]` markers. Every claim has a receipt.
- **Constraints** -- ALWAYS / ASK FIRST / NEVER rules
- **Tasks** -- ordered, checkboxed, each citing its evidence
- **Open Questions** -- unknowns that need research before tasks can proceed

Read the plan carefully. It is the most important artifact Vidux produces. The code that follows is just the plan rendered into your language.

## 3. Subsequent Runs (repeat)

Every `/vidux` after the first follows the same stateless cycle. The agent wakes up with no memory, reads the files, does one thing, checkpoints, and exits.

```
READ --> ASSESS --> ACT --> VERIFY --> CHECKPOINT --> done
(30s)    (30s)    (bulk)   (gate)     (30s)
```

**READ**: Open PLAN.md. Check git log and git diff for recent state.

**ASSESS**: Score the plan 0-10. Below 7 means refine the plan, not write code.

**ACT**: Either refine the plan or execute the first unchecked task. One task. Never two.

**VERIFY**: Build and test gate. Code that does not compile does not get checkpointed.

**CHECKPOINT**: Structured git commit. Update PLAN.md Progress section. Session ends.

The next `/vidux` reads fresh from files and picks up from the checkpoint. No memory, no databases, no running processes. PLAN.md is the entire state of the world.

## The Quick Check / Deep Work Cycle

This is how Vidux runs unattended (cron loops, overnight work). Two modes:

**Quick check** (under 2 minutes, read-only): The cron fires this. It reads the store (PLAN.md), checks for pending work, and either exits (nothing to do) or fires deep work. Never writes code.

**Deep work** (15+ minutes, real work): Drains the queue. Executes tasks, runs builds, ships code. No upper time bound -- it yields only on queue drain, hard blocker, or context budget.

```
Cron fires quick check (REDUCE gate)
    |
    +--> nothing pending? --> exit
    |
    +--> work pending? --> fire deep work --> drain queue --> exit
```

The mid-zone (3-8 minutes) where agents quit at the first natural milestone is structurally eliminated -- the mode decides the duration, not the agent's judgment.

> **Technical names in scripts:** `vidux-loop.sh` outputs `mode: "reduce"` and fires DISPATCH. These are the script-level identifiers for quick check and deep work.

## Commands

| Command | What it does | When to use |
|---------|-------------|-------------|
| `/vidux "..."` | Full cycle: gather, plan, execute, verify, checkpoint | 90% of the time |
| `/vidux-plan "..."` | Plan-only mode, never writes code | Iterating on plan before execution |
| `/vidux-status` | Read-only one-screen summary | Checking in without triggering a cycle |
| `/vidux-loop` | Set up cron harness for unattended cycles | Running overnight |
| `/vidux-dashboard` | Multi-project overview | Multiple missions in flight |

## The 50/30/20 Rule

The most counterintuitive part, and the most important.

- **50%** plan refinement -- gathering evidence, synthesizing, pruning PLAN.md
- **30%** code -- derived from plan entries, one task per cycle
- **20%** last mile -- build errors, CI, reviewer feedback

If your git history is more than 30% code commits, the plan was not good enough. You were coding on assumptions instead of evidence.

When you find yourself wanting the agent to "just start coding" -- that is the moment to stop and ask what evidence is missing. The plan is doing its job when the code writes itself.

## Running Overnight

```bash
bash scripts/vidux-loop.sh /path/to/your/project
```

Each cron fire is a fresh agent with no memory. It reads PLAN.md, picks the next action, executes it, checkpoints, and exits. The next fire is a completely new agent that has never heard of the previous one.

Kick off the loop before bed. Review Progress in the morning. Each commit tells you what happened, what is next, and what is blocked. The plan file IS the debugger.

## What You Have After Install

```
~/.claude/skills/vidux --+
~/.cursor/skills/vidux  --+--> /path/to/vidux  (one clone, multi-tool symlinks)
~/.codex/skills/vidux   --+
                               |
                               +-- DOCTRINE.md    <-- 14 principles (read this first)
                               +-- SKILL.md       <-- full contract
                               +-- LOOP.md        <-- stateless cycle mechanics
                               +-- commands/      <-- /vidux, /vidux-plan, /vidux-status
                               +-- scripts/       <-- loop, checkpoint, gather, doctor
                               +-- hooks/         <-- optional prompt hooks
                               +-- guides/vidux/  <-- quickstart, architecture, best practices
                               +-- projects/      <-- per-project PLAN.md lives here
                                     +-- <my-mission>/
                                           +-- PLAN.md
                                           +-- evidence/
                                           +-- investigations/
```

One clone, multi-tool symlinks. Plans live in `projects/<mission>/`, never in the target repo's working tree.

## Next Steps

- Read `DOCTRINE.md` for the 14 principles (5 minutes, covers 80% of what you need)
- Read `guides/vidux/architecture.md` for the Redux parallel and system design
- Read `guides/vidux/best-practices.md` for lessons learned from 28+ cycles
