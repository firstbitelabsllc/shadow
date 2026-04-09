---
name: vidux
description: "Plan-first discipline for AI agents. Write down what you're going to build before you build it. Plans live in markdown files in git. Any agent can pick up where the last one left off."
---

# Vidux

Vidux is a discipline for AI agents: write down what you're going to build before you build it. Plans live in markdown files in git. Agents read the plan, do one piece of work, update the plan, and checkpoint. Any agent can pick up where the last one left off because the plan file is the only state that matters.

---

## Five Principles

### 1. Plan first, code second

PLAN.md is the source of truth. Code is derived from it. To change code, update the plan first.

Every plan entry cites evidence -- a codebase grep, a PR comment, a design doc quote, a team chat message. A plan entry without evidence is a guess. Guesses cause rework.

### 2. Design for interruption

Every session ends. Context will be lost. Auth will expire. State lives in files, never in memory. Checkpoints are structured (not freeform summaries). Any agent can resume from the last checkpoint.

After any interruption, re-read PLAN.md and evidence/ from disk. Never trust summaries or memory for plan details.

### 3. Investigate before fixing

Bug tickets are not line items. Before coding, map root cause, related surfaces, and impact. A fix without investigation is a guess.

When 2+ tickets touch the same surface, bundle them into one investigation. The investigation produces a root cause analysis, an impact map, and a fix spec. If the fix spec is missing, the cycle is investigation only -- no code.

### 4. Self-extend with a brake

Agents add tasks they discover. When you fix a bug, log the related bugs you saw. When you add a feature, log the edge cases you spotted.

But a shipped surface that works is done -- stop polishing and move to the next gap. If overall mission has gaps elsewhere, polish on a done surface is procrastination. Only re-extend plans when investigation reveals new surfaces, not when you find one more thing to tweak on a surface you already finished.

### 5. Prove it mechanically

Never assert "it works." Run the build, run the tests, show the screenshot. Definition of done for UI work is a visual proof, never just "the build passes."

After a failure, produce two artifacts: a code fix (the immediate repair) and a process fix (a hook, a test, a constraint, a plan update). The process fix is the valuable output -- it makes the system smarter for next time.

---

## The Cycle

Every work session follows this loop:

```
READ    -> PLAN.md, evidence/, git log since last checkpoint
ASSESS  -> Is the plan ready for code, or does it need more evidence?
ACT     -> Either refine the plan OR execute one task
VERIFY  -> Build, test, gate
CHECKPOINT -> Structured commit: what changed, what's next, blockers
```

### When to plan vs when to code

```
IF plan has [in_progress] task:
  -> Resume it (a prior session died mid-task)
  -> Verify, then set to [completed] or [blocked]

ELIF plan has [pending] tasks with evidence:
  -> Set first [pending] to [in_progress], execute, verify, checkpoint

ELIF plan has [pending] tasks without evidence:
  -> Gather evidence, update plan with citations, checkpoint (no code)

ELIF plan is empty or missing:
  -> Research, synthesize into initial PLAN.md, checkpoint (no code)

ELIF all tasks are [completed]:
  -> Verify final state. Mark mission complete.
```

---

## PLAN.md Template

Every project has a PLAN.md. Required sections:

```markdown
# [Project Name]

## Purpose
Why this exists. One paragraph. User-visible goal.

## Evidence
What we know, cited with sources.
- [Source: codebase grep] file:line pattern
- [Source: GitHub PR #1234] "feedback or constraint"
- [Source: design doc] "architectural decision"

## Constraints
- ALWAYS: [things that must be true]
- NEVER: [things that are forbidden]

## Tasks
Ordered, with status tags and evidence citations.
- [pending] Task 1: description [Evidence: ...]
- [in_progress] Task 2: description [Evidence: ...]
- [completed] Task 3: description [Evidence: ...]
- [blocked] Task 4: description [Blocker: ...]

Status FSM: pending -> in_progress -> completed
                 \-> blocked -> pending

## Decision Log
Intentional choices that future agents must not undo.
- [DELETION] [date] Removed X. Reason: Y. Do not re-add.
- [DIRECTION] [date] Chose X over Y. Reason: Z.

## Open Questions
- Q1: [question] -> Action: [what to research]

## Surprises
Unexpected findings during execution. Timestamped.
- [Date] Found: X. Impact: Y. Plan update: Z.

## Progress
Living log updated each cycle.
- [Date] What happened. Next: what's next. Blocker: if any.
```

---

## Quarter-Sized Projects

Vidux is designed for projects that span days to months. A quarter project has:

- **A top-level PLAN.md** with the mission, phases, and current tasks
- **Sub-plans in `investigations/`** for complex surfaces that need root cause analysis before code
- **Evidence snapshots in `evidence/`** that back plan decisions (named `YYYY-MM-DD-<slug>.md`)
- **A Progress log** that any agent can read to understand where things stand

The plan LIVES -- it gets updated every cycle, not written once and followed blindly.

### Compound tasks

Not every task is atomic. Some need investigation before code. A compound task links to an investigation file:

```markdown
- [pending] Task 3: Fix payment flow [Investigation: investigations/payment-flow.md]
```

The `[Investigation: ...]` marker tells the agent: read the sub-plan before coding. If the investigation has no fix spec yet, the cycle is investigation only. Sub-plans follow the same structure (evidence, root cause, fix spec, tests). Traversal is one level deep.

---

## Course Correction

The plan is a living document. When evidence changes, the plan changes. When the plan changes, the work changes.

When something breaks or changes:

1. **Update the plan FIRST** -- what changed, why, what's the new direction
2. **Then update the code** -- derived from the new plan state
3. **Every failure produces a process fix** -- not just a code fix

### The Decision Log prevents loops

Stateless agents have no memory of WHY a previous agent made a choice. Without a Decision Log, an agent that finds "missing" code will re-add it, undoing a deliberate deletion. The Decision Log is the lock file: agents read it before acting and never contradict an entry.

---

## Writer vs Scanner (short note)

Vidux automations come in two types:

- **Writers** execute tasks from a PLAN.md queue. "Nothing to do" means all tasks are completed or blocked.
- **Scanners** inspect the codebase for issues. "Nothing to do" means no files changed since the last scan and the last N scans found nothing.

The distinction matters because a scanner that checks "are all tasks done?" will exit without ever looking at the codebase it is supposed to scan. Match the gate to the type.

---

## Investigation Template

For complex bugs or surfaces with 2+ tickets, create `investigations/<slug>.md`:

```markdown
# Investigation: [surface name]

## Reporter Says        — exact quote from feedback
## Evidence             — files, related tickets, recent commits, repro steps
## Root Cause           — the specific code path, not symptoms
## Impact Map           — other UI paths, other tickets, state flow
## Fix Spec             — file:line changes with evidence for why
## Tests                — assertions covering this ticket and related tickets
## Gate                 — build passes, tests pass, visual check (for UI)
```

If the Fix Spec is missing, the cycle is investigation only -- no code.

---

## Activation

Vidux activates when:
- User says `/vidux` or describes work spanning multiple sessions
- An existing PLAN.md governs the work
- Pilot routes into it after detecting expedition-scale work

Vidux does NOT activate for:
- Single-file changes with obvious cause
- Anything that takes less than 30 minutes with a clear root cause
