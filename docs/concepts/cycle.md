# The Cycle

One Vidux cycle advances one bounded plan row, then leaves a cold-resume
handoff and exits.

```
READ → ASSESS → ACT → VERIFY → CHECKPOINT
```

Vidux defines the plan/proof/resume discipline. The coding host owns execution,
scheduling, routing, authentication, retries, and worker lifecycle.

## Step 1: READ

Read:
- `PLAN.md` — queue/planning authority: tasks, decisions, constraints, progress
- the current Git revision and working tree
- only the proof named by the active row
- repository instructions that govern the selected surface

An interruption is not recovered automatically. If the working tree contains
unexplained changes, inspect and preserve them before editing. Repository files
and Git are enough to reconstruct the next safe move.

## Step 2: ASSESS

```
IF plan has [in_progress] task:
  → Resume it

ELIF plan has unblocked [pending] tasks:
  → Choose the highest-impact row

ELSE:
  → Record the concrete blocker or verified completion state and stop
```

If no plan exists, `vidux init --here` can scaffold one. Replace its unproven
starter row with a concrete outcome and gate before editing code.

## Step 3: ACT

Make one bounded, reversible change for the selected row.

**Queue order:**
1. `[in_progress]` resumes first
2. Dependencies before dependents — `[Depends: Task N]` blocks until N is `[completed]`
3. Otherwise pick the highest-impact unblocked row

Parallel writers need disjoint file ownership. Worker output remains a draft
until the owner reviews the diff and reproduces important proof.

## Step 4: VERIFY

Never assert "it works." Prove it.

Run the cheapest real gate that proves the row's requested outcome. Depending
on the work, that may be a focused test, build, static check, screenshot,
interaction trace, or exact release receipt.

**UI work:**
- Screenshot of the feature working
- Screenshot of the before state (if available)
- Simulator or browser proof — "the build passes" is NOT sufficient

A row is complete only when its requested outcome exists and its named gate
passes. A commit, pull request, review comment, or activity count alone is not
proof.

## Step 5: CHECKPOINT

Record the result, proof, uncertainty, and one cold-resume next move in
`PLAN.md` or a linked repository evidence file. Reconcile that record with the
actual Git diff and revision.

**Progress entry:**
```
- [DATE] Outcome and proof. Risk: remaining uncertainty. Next: one resume move.
```

### Optional `vidux checkpoint`

The shipped helper can update a matching task and Progress entry:

```bash
vidux checkpoint PLAN.md "T-1: Task text" "verified result" \
  --proof "named gate passed"
```

Completion requires `--proof`; `--status blocked` requires a concrete
`--blocker`. Plan changes remain uncommitted unless `--commit` is supplied.

When a local ledger is configured, the helper may append a row. Local `done`
maps to `needs_review`, not an open pull request or shipped state. The row is an
optional projection: it does not outrank repository files, prove the result by
itself, or grant authority to push, merge, release, deploy, or send anything
externally.

Then exit. The next cycle begins by reading the repository again.
