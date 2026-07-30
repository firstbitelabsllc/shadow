# PLAN.md Structure

Use one owning `PLAN.md` for an outcome. When an existing plan already owns the
work, update it instead of creating a competing queue. Separate projects may
have separate plans.

## Full Template

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
Boundaries that must survive a handoff.

## Operator Brief
- Status: [watching|working|blocked|complete]
- Outcome: [observable result]
- Next: [one cold-resume move]
- Validation: [real gate]

## Outcome Scorecard
| Metric | Baseline | Current | Target | Status | Proof |
|---|---|---|---|---|---|
| [measure] | [known start] | [current] | [desired result] | unproven | [artifact or command] |

## Tasks
Ordered rows with explicit state.
- [pending] T-1: description
- [in_progress] T-2: description
- [completed] T-3: description [Proof: ...]
- [blocked] T-4: description [Blocker: ...] [Resume: ...]

## Decision Log
Intentional choices that future agents must not undo.
- [DELETION] [date] Removed X. Reason: Y. Do not re-add.
- [DIRECTION] [date] Chose X over Y. Reason: Z.

## Progress
Results and cold-resume handoffs.
- [Date] Outcome and proof. Risk: remaining uncertainty. Next: one move.
```

## Required Sections

`vidux init --here` scaffolds all eight:

| Section | Purpose |
|---|---|
| Purpose | User-visible outcome |
| Evidence | Facts that shape the work |
| Constraints | Durable boundaries |
| Operator Brief | Current status, outcome, next move, and validation |
| Outcome Scorecard | Baseline, target, current result, and proof |
| Tasks | Ordered work rows |
| Decision Log | Deliberate choices |
| Progress | Result, uncertainty, and resume state |

## Task Status FSM

```
pending → in_progress → completed
              ↓
           blocked
```

Status rules:
- Every task starts `[pending]`
- Resume `[in_progress]` before selecting another row
- `[completed]` requires the requested outcome and named proof
- `[blocked]` requires a concrete reason and relation-based resume condition
- When evidence changes a completed outcome, add a new row instead of silently
  rewriting the old result

Some repository-specific hosts may project review state separately. The
portable plan contract uses only the four states above.

## Task Format

```markdown
- [pending] T-1: Short description [Evidence: source:line] [Depends: T-0]
```

- **Status tag** (required) — `[pending]`, `[in_progress]`, `[completed]`, or `[blocked]`
- **Stable id** (recommended) — such as `T-1`, for cross-referencing
- **Description** — short, action-oriented
- **Evidence citation** — include when a fact or dependency needs inspection
- **Depends** (optional) — blocks until the dependency is `[completed]`

## The Decision Log

Record choices that a cold reader might otherwise undo or repeat.

```markdown
## Decision Log
- [DELETION] [2026-04-17] Removed observer lanes. Reason: they added drift without catching bugs the writer could not already see. Do not re-add.
- [DIRECTION] [2026-04-26] Open operational PRs ready-for-review by default. Reason: review bots and CI gates do not reliably run on drafts.
- [CONSTRAINT] [2026-04-12] Deployment requires a maintainer-provided credential; resume only when the named secret is available.
```

Entry types:
- `[DELETION]` — removed intentionally; don't re-add
- `[DIRECTION]` — a deliberate architectural or approach choice
- `[CONSTRAINT]` — a durable boundary or external dependency
- `[PIVOT]` — major direction change; marks obsolete tasks

## Drift Log

Optional. Use it when implementation materially diverges from the recorded
approach. State what was planned, what actually happened, why, and how the plan
changed. Do not create a second authority file merely to log drift.

## Course Correction

Evidence changes → the plan changes. The procedure:

1. Update the owning plan with the new fact and direction.
2. Add a Decision Log or Drift Log entry when the reason matters later.
3. Mark obsolete rows clearly and add a replacement row if work remains.
4. Then extend the implementation.

Create another plan only for a genuinely separate outcome or project, not as a
clean-slate duplicate of active work.

## Compound Tasks and Sub-Plans

A task that needs investigation before code gets a sub-plan:

```markdown
- [pending] Task 3: Fix payment flow [Investigation: investigations/payment-flow.md]
```

The marker tells the reader where the linked root-cause work lives. The owning
task remains incomplete until its requested outcome and gate are proven.

## Investigation Template

For a complex surface with an uncertain root cause:

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

Use this template only when it helps resolve genuine uncertainty.

## Garbage Collection

Vidux performs no automatic plan or session garbage collection. Maintainers may
condense old detail into linked repository evidence while preserving decisions,
proof references, and the current cold-resume state.

## INBOX.md

`INBOX.md` is optional. If the repository already uses one, promote accepted
findings into the owning plan. It does not become a second queue or an automatic
work source.
