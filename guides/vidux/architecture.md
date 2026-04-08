# Vidux Architecture Guide

> **The Redux of planned vibe coding.**
> The plan is the store. Code is the view. Work flows from plan changes.

Vidux is a plan-first orchestration system for AI-assisted coding on multi-day projects. It enforces unidirectional data flow -- evidence feeds the plan, the plan drives the code -- so that agent sessions can crash, restart, and resume without losing progress.

Battle-tested across 28+ cycles building itself, a 10-automation fleet across 2 products (Acme iOS/web and Beacon web), and overnight cron loops that run unsupervised.

---

## 1. The Redux Analogy

This is not a loose metaphor. The structural mapping is load-bearing.

In Redux, a UI store holds application state. Components render views derived from that state. State mutations happen only through dispatched actions, processed by reducers. Vidux does the same thing, but the store is a markdown file and the view is code.

| Redux Concept | Vidux Equivalent | Why the Mapping Holds |
|---------------|-----------------|----------------------|
| Store | PLAN.md | Single source of truth. All state lives here. |
| Actions | Plan amendments (require evidence) | The only legal way to mutate the store. Each carries a payload (evidence). |
| Reducers | Quick check mode (REDUCE in scripts) | Pure function. Reads the current store, decides what happens next. |
| dispatch() | Deep work mode (DISPATCH in scripts) | Fires a long execution. Yields only on completion. |
| View | Code (derived, never independent) | Rendered from the store. If the view is wrong, the store is wrong. |
| DevTools | Git log + Ledger | Append-only. Replay any session. Time-travel debugging. |

The practical consequence is blunt: if the code is wrong, the plan is wrong. Fix the plan first, then fix the code. An agent that edits code without a corresponding plan entry is doing the equivalent of mutating Redux state outside a reducer -- a violation that makes the system unpredictable.

The analogy also explains why Vidux feels heavyweight for small tasks. Redux is overkill for a counter app. Vidux is overkill for a single-file bug fix. Both pay off when state is complex enough that unmanaged mutations create chaos.

---

## 2. The Quick Check / Deep Work Cycle

This is the core runtime model. Understanding it makes everything else obvious.

### The Problem

Agents have a learned closure bias (Claude Code #34238). After completing any task, they hit the first natural milestone -- a commit, a sub-task completion, a passing build -- and invent reasons to quit. "Context is getting tight." "This is a good stopping point." The result: 3-8 minute runs that do real work but stop before draining the queue. Wasted context window bootstrapping, half-finished surfaces, and a cron loop that churns without converging.

### The Solution: Two Modes, No Middle

```
Cron fires every 30 minutes
     |
     v
QUICK CHECK / REDUCE (<2 min, read-only)
     |
     +--> Read PLAN.md, git log, git diff
     |
     +--> Nothing pending?
     |         |
     |         v
     |    Checkpoint "quick check: nothing pending", exit
     |
     +--> Work pending?
              |
              v
         Fire DEEP WORK
              |
              v
         DEEP WORK / DISPATCH (15+ min)
              |
              +--> Execute first unchecked task
              +--> SCAN QUEUE (mandatory -- closure bias defense)
              +--> More work? Execute next task
              +--> Repeat until:
              |      - queue drained
              |      - hard external blocker
              |      - context budget exhausted
              |
              v
         Checkpoint with structured commit, exit
```

**Quick check** (REDUCE in scripts) is the cron entry point. It reads the store, evaluates state, and either exits (nothing to do) or fires deep work (work pending). A quick check never writes code, never modifies the plan beyond updating timestamps.

**Deep work** (DISPATCH in scripts) is the real work mode. It pops tasks from the queue, executes them, verifies with build/test gates, and keeps going until the queue is drained or a hard blocker stops it. No upper time bound. No "one task and exit." The harness says: "keep working until the queue is empty or something external stops you."

### Why Mid-Zone Is Structurally Impossible

In a naive setup, the agent decides when to stop. This is the root of the problem -- an agent's "I am done" feeling is unreliable (closure bias). The quick check / deep work model eliminates this decision:

```
Duration spectrum:

  QUICK CHECK     Mid-zone (eliminated)       DEEP WORK
  |<-- <2 min -->|                           |<-- 15+ min -------->|
  [read, decide] [agents used to quit here]  [drain queue, real work]
                  ^
                  This zone cannot exist because:
                  - Quick check exits in <2 min (read-only, no work)
                  - Deep work has no exit until queue drain/blocker
                  - There is no third mode
```

The agent never has to decide "should I keep going?" because the mode already decided. Quick check always exits fast. Deep work never exits until the work is done. The 3-8 minute mid-zone where stuck agents masquerade as polite ones is structurally gone.

### The Closure Bias Defense

After completing any task inside a deep work run, the agent MUST scan the queue before checkpointing. This is not optional. The "I am done" feeling after a successful commit is the exact moment closure bias strikes.

```
Task completed successfully
     |
     v
DO NOT CHECKPOINT YET
     |
     v
Scan PLAN.md for unchecked tasks
     |
     +--> More tasks? --> Execute next task
     |
     +--> Queue empty? --> NOW checkpoint and exit
     |
     +--> Hard blocker? --> Checkpoint with blocker noted, exit
```

The queue is truth. The feeling is not.

### Real Example: Acme Fleet

Before the quick check / deep work model, the Acme iOS automation averaged 4.2 minutes per run. After: bimodal -- either 1.1 minutes (quick check, nothing to do) or 22 minutes (deep work, real tasks). Mid-zone runs dropped from 40% to under 5%. Net tasks completed per day increased because context window bootstrapping (the expensive part) happened less often.

---

## 3. Two Data Structures

Vidux has exactly two data structures. Everything else is derived.

```
+---------------------------+         +---------------------------+
|  DOC TREE (the store)     |         |  WORK QUEUE (FIFO)        |
|                           |         |                           |
|  PLAN.md                  | --edit->|  +---+---+---+---+        |
|  evidence/                |         |  | 1 | 2 | 3 |...|  hot   |
|  constraints/             |         |  +---+---+---+---+        |
|  decisions/               |         |  (last 30 items)          |
|  investigations/          |         |  ----------------         |
|                           |<--pop-- |  cold: git history        |
+---------------------------+  result +---------------------------+
        ^                                     |
        |                                     v
        |                          +---------------------------+
        +--- results write back ---|  Agent executes one       |
                                   |  item, verifies, exits    |
                                   +---------------------------+
```

### Documentation Tree (the store)

A markdown-based tree. Single source of truth. All knowledge, plans, evidence, and decisions live here.

```
projects/<mission>/
  PLAN.md              -- purpose, tasks, constraints, decisions
  evidence/            -- cached MCP queries, codebase analysis
  constraints/         -- reviewer preferences, team conventions
  decisions/           -- what was decided, alternatives, rationale
  investigations/      -- compound task deep-dives
```

Changes to the doc tree are the PRIMARY work product. Code changes are SECONDARY. A cycle that improves the plan but writes zero code is productive. A cycle that writes 500 lines without updating the plan is a liability.

### Work Queue (FIFO, sliding window)

Tasks in PLAN.md form the queue. Hot window: last 30 items (in context). Cold storage: item 31+ (in git history, retrievable on demand).

Why FIFO: tasks have dependencies. A stack (LIFO) would work on the newest item first, which is almost never right. FIFO aligns with dependency ordering.

Why 30: token budget. Thirty task entries with evidence citations fit in a single context window. Beyond 30, items move to cold storage.

### Unidirectional Flow

```
Agents update docs --> Doc changes create queue items --> Agents pop and execute
       ^                                                          |
       +------------------ results feed back into docs -----------+
```

Agents never "just code." They either update docs (which creates queue items) or pop queue items (which were created by doc updates). Every code change has a provenance chain: evidence -> plan entry -> queue item -> code. If you cannot trace a code change back through this chain, it is an unmanaged mutation.

---

## 4. The Six Core Principles

Non-negotiable doctrine. Each exists because a specific failure was observed. Full text with examples in `DOCTRINE.md` (14 doctrines); extended set with implementation details in `SKILL.md` (14 principles).

**1. Plan is the store.** PLAN.md is truth. Code is derived. Fix the plan first.

**2. Unidirectional flow.** Gather -> Plan -> Execute -> Verify -> Checkpoint -> Gather. No step is skippable.

**3. 50/30/20 split.** 50% plan refinement. 30% code. 20% last mile. If you are coding more than planning, you are doing it wrong.

**4. Evidence over instinct.** Every plan entry cites a source. No source = no entry. Gathering costs 2-5 minutes. A wrong assumption costs 15-60 minutes plus ripple effects.

**5. Design for completion.** Dispatches end. Context is lost. The store persists. State in files, not memory.

**6. Process fixes > code fixes.** Every failure produces a code fix (table stakes) and a process fix (the valuable one). The drift detection hook, checkpoint enforcement, and three-strike gate all came from analyzed failures.

---

## 5. The Stateless Cycle

Every cron fire runs a fresh, stateless agent through five steps. The agent knows nothing except what is in the files.

```
Quick check (REDUCE):
  Cron fires --> READ (30s) --> ASSESS (30s) --> work pending?
                                                      |
                     +----------No----> checkpoint, exit (<2 min total)
                     |
                    Yes
                     |
                     v
Deep work (DISPATCH):
  ACT (15+ min) --> VERIFY (gate) --> CHECKPOINT (30s) --> exit
  ^                                        |
  +--- more tasks? scan queue, loop -------+
```

### Read (30 seconds)

Read PLAN.md, `git log --oneline -10`, `git diff --stat`. If uncommitted work exists from a crashed session, commit it first as crash recovery.

### Assess (30 seconds)

Score the plan on a 10-point readiness checklist. Five required items (purpose filled, 3+ cited evidence, at least one ALWAYS and NEVER constraint, at least one task with evidence, no open questions blocking the next task). Five quality items add one point each. Score 7+ to code; below 7, spend the cycle refining.

The decision tree:

```
Start
  |
  +--> Plan exists? --No--> GATHER: fan out research, create PLAN.md
  |
  +--> Yes
        |
        +--> Open questions blocking tasks? --Yes--> Research first question
        |
        +--> Tasks without evidence? --Yes--> Gather evidence
        |
        +--> Unchecked tasks with evidence? --Yes--> Execute first task
        |
        +--> All tasks complete --> Verify final state
```

Notice the ordering. Open questions before unevidenced tasks before code execution. The system biases toward understanding over action.

### Act (15+ minutes in DISPATCH)

Execute one task. Verify it passes the build/test gate. Then -- critically -- scan the queue. If more work is pending, execute the next task. Do not checkpoint and exit after one task. The queue is truth.

### Checkpoint (30 seconds)

Structured commit: what changed, which task, what is next, blockers. Update PLAN.md Progress. Git commit is the checkpoint, not push. Push when ready.

---

## 6. The Fan-Out Pattern

A single agent querying team chat, then code reviews, then the codebase serially would burn its entire cycle on evidence gathering. Fan-out parallelizes this.

```
          +----------+  +----------+  +----------+  +----------+
TIER 1    | Agent A  |  | Agent B  |  | Agent C  |  | Agent D  |
(parallel)| team chat|  | codebase |  | rules    |  | issues   |
          +----+-----+  +----+-----+  +----+-----+  +----+-----+
               |              |              |              |
               v              v              v              v
          evidence/A.md  arch/B.md   constraints/  tasks/D.md
               |              |           C.md         |
               +-----+-------+-----------+------------+
                     |
                     v
              +-----------+
TIER 2        | Synthesizer|  reads all 4, writes one PLAN.md
(serial)      +-----------+
                     |
                     v
              +-----------+
TIER 3        |   Critic   |  challenges assumptions
(serial)      +-----------+
```

**Tier 1**: 4 research groups, all parallel. Each writes to its own file. No shared files, no coordination overhead.

**Tier 2**: One synthesizer reads all 4 and writes unified PLAN.md. Single merge point.

**Tier 3**: One critic reads PLAN.md and challenges assumptions. Checks consistency, identifies missing evidence, flags oversized tasks.

Why not 20 agents on one file: coordination gains plateau at approximately 4. Beyond that, 17x error amplification without hierarchy. The three-tier hierarchy bounds this by funneling all output through a single synthesis point.

---

## 7. Compound Tasks and Investigations

Most tasks are atomic: one fix, one cycle. Some problems resist atomic treatment.

**When to use a compound investigation:**
- 2+ tickets touch the same surface (same file, module, or API)
- Unclear root cause -- symptom known, fix unknown
- Three-strike escalation -- 3+ prior atomic fixes on the same surface without resolution

Mark compound tasks with `[Investigation: investigations/<slug>.md]` in PLAN.md. The investigation file contains:

1. **Tickets** -- which issues are bundled
2. **Evidence** -- gathered data, MCP queries, codebase analysis
3. **Root Cause** -- the underlying problem, not the symptom
4. **Impact Map** -- what else this root cause affects
5. **Fix Spec** -- proposed fix scoped to the root cause
6. **Tests** -- what must pass
7. **Gate** -- Q-gate criteria specific to this investigation

The investigation file prevents the failure mode where Agent A applies a surface fix to one ticket, Agent B applies a contradictory fix to a related ticket, and Agent C reverts both.

---

## 8. Layer Separation

Vidux core is company-agnostic. Zero references to any internal tooling, build system, or team convention.

```
+-------------------------------------------+
| Layer 2: Project Wiring (per-team)        |
|  MCP tools, build system, team            |
|  conventions, companion skills            |
+-------------------------------------------+
            |  imports
            v
+-------------------------------------------+
| Layer 1: Vidux Core (open-sourceable)     |
|  Doctrine (14 principles), data            |
|  structures, loop mechanics, failure      |
|  protocol, PLAN.md template               |
+-------------------------------------------+
```

**Layer 1** ships as open source: doctrine, data structures, loop mechanics, failure protocol, PLAN.md template.

**Layer 2** is team-specific: MCP tools, build commands, conventions, companion skills. Replace yours. The core loop and doctrine remain unchanged. PLAN.md is the interface contract -- any Layer 2 that can read and write a conformant PLAN.md is compatible.

---

## 9. The Enforcement Gradient

Four Claude Code hooks, all prompt-type (nudge, not block). Plan compliance is a judgment call -- a command hook parsing PLAN.md for file paths is brittle. A prompt hook that reminds the agent to check is flexible and effective.

```
SessionStart ----> PreToolUse ----> PostToolUse ----> Stop
(GENTLE)           (MEDIUM)         (MEDIUM)          (FIRM)
"Read the plan"    "Is this edit    "Did this edit    "Did you
                    in the plan?"    match the plan?"  checkpoint?"
```

Each hook catches what the previous one missed. If the agent follows SessionStart (reads the plan), it rarely triggers PreToolUse. If it follows PreToolUse, it rarely triggers PostToolUse. If all three hold, Stop is a formality.

---

## 10. Fleet Topology

The Acme/Beacon fleet runs 10 automations across 2 products. All automations share the same shape:

- **Deep work mode**: every automation does real work, not just monitoring
- **Self-extending plans**: every automation adds tasks it discovers (Doctrine 11)
- **30-minute cron cadence**: quick check fires every 30 min, deep work when work is pending
- **Work-stream scoped**: each automation owns one concern (payments, onboarding, UI polish, etc.)

Fleet-wide quality is measured by `scripts/vidux-fleet-quality.sh`, which scans all active automations for stale plans, stuck loops, mid-zone violations, and un-checkpointed work.

The default topology is flat. Each automation reads its own PLAN.md and makes its own quick check / deep work decision. Coordination happens through the shared git history -- if Automation A fixes a file that Automation B planned to touch, B sees the change in its next quick check and adapts. For fleets of 4+ automations, a coordinator automation is an optional pattern (see SKILL.md Principle 9 and `vidux-recipes.md` coordinator harness template). The coordinator does not override individual mode decisions; it sequences cross-lane dependencies and resolves conflicts that git history alone cannot catch.

---

## Tradeoffs

**Overhead vs safety.** The 50/30/20 split means half the agent's time goes to planning. Vidux bets that plans are rarely right from the start, so front-loading refinement prevents rework that costs more than the overhead.

**Rigidity vs flexibility.** Unidirectional flow is inflexible by design. Drive-by edits to unrelated files accumulate untracked changes that interact in surprising ways three sessions later.

**Queue drain vs throughput.** Half-finished tasks leave the codebase in an intermediate state the next agent must diagnose. The deep work model says: keep working through the queue until it drains, each task completed fully before the next, codebase always in a known-good state at each checkpoint.

**Solo computer workflow.** Vidux is designed for one human operating one or more AI agents on a local machine. Tool state lives outside the repo. The repo is the shared surface; tool configuration is per-operator.
