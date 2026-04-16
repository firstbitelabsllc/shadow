# The Cycle

Every agent session — human-triggered or cron — runs the same five steps. No step is skippable.

```
READ → ASSESS → ACT → VERIFY → CHECKPOINT → (next session) → READ → ...
```

## Step 1: READ

Load the current state of the world.

**What to read:**
- `PLAN.md` — source of truth for tasks, decisions, and progress
- `INBOX.md` — unprocessed findings from humans or external tools
- `git log --oneline -10` — what happened recently
- `git diff` — uncommitted work from a crashed session

**Crash recovery:** If `git diff` shows uncommitted work from a dead session, commit it first:
```
vidux: recover uncommitted work from crashed session
```

**Time budget:** 60-90 seconds. If reading takes longer, the plan is too large — add a GC task.

## Step 2: ASSESS

Decide what to do based on what you read.

```
IF plan has [in_progress] task:
  → Resume it (a prior session died mid-task)
  → Verify, then set to [completed] or [blocked]

ELIF plan has [pending] tasks WITH evidence:
  → Set first [pending] to [in_progress], execute, verify, checkpoint

ELIF plan has [pending] tasks WITHOUT evidence:
  → Gather evidence, update plan with citations, checkpoint (no code)

ELIF plan is empty or missing:
  → Research, synthesize into initial PLAN.md, checkpoint (no code)

ELIF all tasks are [completed]:
  → Verify final state. Mark mission complete.
```

**Assess readiness (7/10 threshold):** Before coding, score the evidence:
- Root cause identified? (+2)
- Impact map complete? (+2)
- Fix spec has file:line locations? (+2)
- Test cases defined? (+2)
- Known unknowns documented? (+2)

Score ≥ 7 → code. Score < 7 → gather more evidence first.

## Step 3: ACT

Execute tasks until the queue is empty, a blocker is hit, or the context budget runs out.

**Queue order:**
1. `[in_progress]` always resumes first — a prior session died mid-task
2. Dependencies resolve before dependents — `[Depends: Task N]` blocks until N is `[completed]`
3. `[pending]` tasks run top-to-bottom — first eligible task wins
4. `[P]` tasks may run in parallel — up to 4 concurrent agents, one point guard
5. No reordering mid-cycle — to change priority, update the plan with a Decision Log entry

**Mid-zone kill:** If 3+ minutes pass with no file write, exit. This catches agents stuck in plan-reading loops.

**Every agent is a worker:** When the queue is empty, don't exit — scan for work:
1. Check INBOX.md for unprocessed findings
2. Scan the codebase for issues in owned paths
3. Check git log for recent changes needing follow-up
4. Recheck blocked tasks for resolved blockers

If any scan finds work: add it as a `[pending]` task, then execute it. If all scans come up clean: checkpoint and exit with proof of what was scanned.

## Step 4: VERIFY

Never assert "it works." Prove it.

**Required for all work:**
- Build must pass
- Tests must pass
- No regressions in related areas

**Required for UI work:**
- Screenshot showing the feature working
- Screenshot showing the before state (if available)
- Simulator or browser proof — "the build passes" is not sufficient

**Gate on compound tasks:** Before marking an investigation `[completed]`, confirm:
- Fix Spec is filled (not `(pending)`)
- All seven investigation sections are complete
- The parent task in PLAN.md can flip to `[completed]`

## Step 5: CHECKPOINT

Every cycle ends with a checkpoint commit and a Progress entry.

**Commit format:**
```
vidux: [what you did]
```

Examples:
```
vidux: add rate limiting to login endpoint
vidux: investigation — root cause for checkout double-charge
vidux: recover uncommitted work from crashed session
```

**Progress entry:**
```
- [DATE] What happened. Next: what's next. Blocker: if any.
```

**Reconcile planned vs actual:** Compare what the plan SAID with what the git diff SHOWS. If they diverge, update the plan and add a Surprise entry. The plan always reflects truth.

**Surprises format:**
```markdown
## Surprises
- [2026-04-15] Found: auth/login.ts has a second rate limiter we didn't know about.
  Impact: our new rate limiter will double-count requests.
  Plan update: Task 1 updated to configure both limiters in sync.
```

## Stuck Detection

If the same task appears in 3+ Progress entries while still `[in_progress]`, it is stuck. Mark it `[blocked]` with a Decision Log entry. Only a human can unblock it.

```markdown
## Decision Log
- [BLOCKED] [2026-04-15] Task 3 stuck 3 cycles. Root cause unknown. Requires human review.
```

## Push Authorization Tiers

Not all pushes carry the same risk:

| Tier | What | Authorization needed |
|---|---|---|
| 1. Draft PRs | Push to feature branch + `gh pr create --draft` | Always safe — no ask needed |
| 2. Direct-to-main | Push directly to main branch | Explicit authorization per lane or session |
| 3. Destructive | Force push, branch delete, `git reset --hard` | Per-action authorization |

If the lane prompt says "NEVER push" with no tier distinction, treat it as tier 2+3 blocked but tier 1 (draft PRs) still allowed.

## Escalation Statuses

When a cycle ends, it exits with one of four statuses:

| Status | Meaning |
|---|---|
| `DONE` | All tasks complete, build passes, tests pass, checkpoint committed |
| `DONE_WITH_CONCERNS` | Work complete but something smells wrong — flagged for human review |
| `NEEDS_CONTEXT` | Blocked by missing information that only a human can provide |
| `BLOCKED` | Hard blocker — same task failed 3 times or external dependency missing |
