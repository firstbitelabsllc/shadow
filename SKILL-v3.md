---
name: vidux
description: "Plan-first discipline for AI agents. Write down what you'll build, do one piece, update the plan, checkpoint. Any agent picks up where the last left off."
---

# Vidux

A discipline for AI agents: write down what you're going to build before you build it.

Plans live in markdown files in git. Agents read the plan, do one piece of work,
update the plan, and checkpoint. Any agent can pick up where the last one left off
because the plan file is the only state that matters.

---

## Six Principles

### 1. Plan first, code second

PLAN.md is the source of truth. Code is derived from it. If the code is wrong,
the plan is wrong -- fix the plan, then fix the code. Every plan entry cites
evidence: a codebase grep, a design doc quote, a ticket. No evidence = a guess.

### 2. Design for interruption

State lives in files, never in memory. Every cycle reads fresh from disk.
Checkpoints are structured. Any agent resumes from the last checkpoint. Sessions
end without warning -- the plan survives because it is a file in git, not state
in someone's head.

### 3. Investigate before fixing

Bug tickets are not line items. Before writing code for a bug, map root cause,
related surfaces, and impact. Produce an investigation file before touching code.
(See the Compound Tasks section below for the template.)

Required when: 2+ tickets on the same surface, UI bugs needing visual verification,
unclear root cause, or 3+ prior fixes on the same area. Optional for pure logic
bugs with obvious single-file fixes.

### 4. Self-extend with a brake

Agents add tasks they discover -- related bugs, edge cases, follow-up work. If you
are not extending the plan, you are not paying attention. But a shipped surface
that works is done. Stop polishing and move to the next gap. If the mission has
gaps elsewhere, polish on a done surface is procrastination.

### 5. Prove it mechanically

Never assert "it works." Run the build, run the tests, show proof. After failure,
produce two artifacts: a code fix and a process fix (update constraints, add a
hook, add a test). The process fix is the valuable output.

### 6. Clean up after yourself

Merge branches or delete them. Archive completed tasks. Prune orphan worktrees.
Every completed task leaves main cleaner than it found it.

---

## PLAN.md Template

Every vidux project has a PLAN.md. Required sections:

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
What we must respect.
- ALWAYS: [things that must be true]
- ASK FIRST: [things that need human approval]
- NEVER: [things that are forbidden]

## Decisions
What we decided and why.
- [Date] Decision: X. Alternatives: A, B. Rationale: Y.

## Decision Log
Intentional choices that agents must not undo. (See explanation below.)
- [DELETION] [date] Removed X. Reason: Y. Do not re-add.
- [DIRECTION] [date] Chose X over Y. Reason: Z. Do not revisit unless evidence changes.

## Tasks
Ordered, with status tags and evidence citations.
- [pending] Task 1: description [Evidence: ...]
- [in_progress] Task 2: description [Evidence: ...]
- [completed] Task 3: description [Evidence: ...]
- [blocked] Task 4: description [Blocker: ...]

Status flow: pending -> in_progress -> completed (or pending -> blocked -> pending).

## Progress
Living log updated each cycle.
- [Date] Cycle N: what happened. Next: what's next. Blocker: if any.
```

Optional sections: Open Questions, Surprises, Exit Criteria.

---

## Decision Log: Why It Exists

Scheduled agents are stateless -- they have no memory of WHY a previous agent made
a choice. Without the Decision Log, an agent that finds "missing" code will re-add
it, undoing a deliberate deletion. This creates an endless undo/redo loop.

The Decision Log is the lock file. Agents read it before acting and never contradict
an entry. Three categories: **DELETION** (do not re-add), **DIRECTION** (do not
revisit unless new evidence), **RATE-LIMIT** (do not exceed).

---

## Quarter-Sized Projects

Vidux is for multi-day and multi-week work with phases and sub-plans. Not quick
fixes. Large projects break into phases, each shipping something verifiable.

```
project/
  PLAN.md              -- the expedition plan
  ARCHIVE.md           -- completed tasks moved here
  evidence/            -- research snapshots (YYYY-MM-DD-slug.md)
  investigations/      -- sub-plans for compound tasks
```

### Compound tasks

**Atomic tasks** have self-contained descriptions. Pop, execute, checkpoint.

**Compound tasks** link to an investigation file:
```markdown
- [pending] Task 2: Fix popover system [Investigation: investigations/popover-amount-editor.md]
```

The investigation follows a structured template: Reporter Says, Evidence, Root
Cause, Impact Map, Fix Spec, Tests, Gate. If Fix Spec is missing, the cycle is
investigation only -- no code yet. When tickets share a surface, bundle them into
one investigation to prevent the pattern where fix A breaks ticket B.

---

## Writer vs Scanner

Every automation is either a **writer** (executes tasks from a plan queue) or a
**scanner** (inspects the codebase for issues and reports findings).

Scanners append findings to INBOX.md. Writers promote actionable findings into
PLAN.md tasks.

---

## The Cycle

Every work cycle is stateless. The agent reads state from files, never from memory.

```
READ       PLAN.md, Decision Log, git log since last checkpoint
ASSESS     Plan ready for code, or needs more evidence?
ACT        Refine the plan OR execute one task
VERIFY     Build, test, prove it works
CHECKPOINT Structured commit: what changed, what's next, any blockers
```

### What to do next

1. **[in_progress] task exists** -- resume it (prior session died mid-task), verify, complete or block.
2. **[pending] tasks with evidence** -- mark first as [in_progress], execute, verify, complete or block.
3. **[pending] tasks without evidence** -- gather evidence, update plan with citations. No code this cycle.
4. **All tasks [completed]** -- check INBOX.md for findings, verify final state, mark mission complete.
5. **All tasks [blocked]** -- recheck blockers, unblock if resolved, escalate if not.

---

## INBOX.md

Scanners append findings to INBOX.md. Writers check it before looking at PLAN.md
tasks, promote actionable entries, and annotate the rest with `[SKIP: reason]`.

---

## Failure Protocol

When a build or test fails:

1. Retry once with a targeted fix.
2. If still failing: ask why the error happened AND why the agent made the mistake.
3. Three-strike check: 3+ fixes on the same surface means move up one abstraction layer.
4. Produce a code fix and a process fix. Update PLAN.md with both.

---

## When Vidux Applies

**Activate when:**
- User says `/vidux` or "plan first"
- Work spans multiple days or sessions
- An existing PLAN.md governs the work
- Bug tickets touch a surface with 2+ prior tickets or unclear root cause

**Do not activate for:**
- Single-file changes with obvious cause
- Anything under 30 minutes with a clear fix
- PR review and merge (use Pilot)

---

## Portability

PLAN.md is a markdown file in a git branch. That is the whole stack. No databases,
no running processes, no external state. Git is the state layer. Any agent, any tool,
any machine can pick up where the last one left off by reading the plan file.
