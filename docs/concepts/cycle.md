# The Cycle

Every agent session — human-triggered or cron — runs the same five steps. No step is skippable.

```
READ → ASSESS → ACT → VERIFY → CHECKPOINT → (next session) → READ → ...
```

## Step 1: READ

Load the current state of the world.

**What to read:**
- `PLAN.md` — queue/planning authority for tasks, decisions, constraints, and progress
- `INBOX.md` — unprocessed findings from humans or external tools
- Latest publish ledger rows — shipped-cycle proof and resume metadata
- `git log --oneline -10` — what happened recently
- `git diff` — uncommitted work from a crashed session

**Crash recovery:** If `git diff` shows uncommitted work from a dead session,
inspect it first, resume the owning plan row, and checkpoint through the plan.
Create a commit only when code changed, and emit the publish ledger row before
any branch/PR/release publish leaves the machine.

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
  → Gather evidence locally, update plan in place — no commit until code ships

ELIF plan is empty or missing:
  → Research locally, draft initial PLAN.md — no commit until code ships

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
3. Pick the highest-impact unblocked task. Re-sort when new observed evidence arrives. Note the reorder in the next Progress entry.

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

Every cycle ends with a plan/progress checkpoint. Publishable branch, PR, or
release work also emits a publish ledger row carrying the task id, proof,
handoff status, files claimed, and next-agent resume point before transport.

**Commit format when code changed:**
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

**Reconcile planned vs actual:** Compare what the plan SAID with what the git diff SHOWS. If they diverge, update the plan and note the divergence in the Progress entry. The plan remains the queue/planning authority, and the matching publish ledger row records what shipped.

## Stuck Detection

If the same task appears in 3+ Progress entries while still `[in_progress]`, force a surface switch. In default read mode, `vidux-loop.sh` reports `action: "stuck"` and a `surface_switch` candidate when another runnable task exists; auto-blocking and Decision Log mutation require `VIDUX_LOOP_AUTO_BLOCK=1`. The next cycle either finds new evidence or the task stays blocked.

```markdown
## Decision Log
- [BLOCKED] [2026-04-15] Task 3 stuck 3 cycles. Tried: X, Y. Moving on.
```

## Push Authorization

Operational PR branch pushes are safe without asking only after the owning
`PLAN.md` Progress/Tasks/Drift Log is updated and a `ledger-emit.sh --event
publish` row records the task id, plan path, proof, handoff status, files
claimed, path-like claims, and next-agent resume point. Open PRs
ready-for-review by default so configured review bots can run; use draft only
for true WIP with a missing gate. Direct-to-main or destructive operations
(force push, branch delete, `git reset --hard`) require explicit authorization
and the same publish propagation before transport.

## Escalation Statuses

When a cycle ends, it exits with one of four statuses:

| Status | Meaning |
|---|---|
| `DONE` | All tasks complete, build passes, tests pass, plan/proof checkpoint recorded |
| `DONE_WITH_CONCERNS` | Work complete but something smells wrong — flagged for human review |
| `NEEDS_CONTEXT` | Blocked by missing information that only a human can provide |
| `BLOCKED` | Hard blocker — same task failed 3 times or external dependency missing |
