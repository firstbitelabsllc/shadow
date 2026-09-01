# Source change requests — 2026-08-19

Written, not implemented. This computer does not change Shadow's implementation,
tests, or command surface. Each item below states the failure, the evidence, and
the smallest remedy the owning seat should consider. No patch is attached and no
flag is proposed as a user-facing feature.

Status: all three were reproduced against the installed 1.2.0 CLI and the live
board. An earlier local attempt to implement items 1 and 2 was reverted; the
working tree carries no source or test change.

## 1. A completed row can strand its claim when the owner never returns

**Failure.** A claim survives after its entity row is already `[completed]` with
a PROOF receipt. The work is finished and proven, but the board still shows the
row as owned, so no other seat treats it as reachable. The lease expires and the
claim stays: expiry marks the claim stale, it does not release it.

**Why it matters.** This is the only board state that has ever required a person
to run a command. That makes it an invariant violation, not an inconvenience:
recovery belongs to the system, and any flag added to fix it is a second failure
layered on the first.

**Evidence.** Observed twice on the live board this week. In both cases the
entity plan carried the completed row and its PROOF line, so the truth needed to
release the claim was already written down and already local.

**Remedy to consider (smallest first).**

1. Board refresh drops a claim whose entity row is completed and carries its
   PROOF receipt. The plan is already the authority for row state; refresh only
   stops contradicting it. Nothing new is stored and no owner is impersonated.
2. If that is judged too implicit, expiry itself should close a completed+PROOF
   claim rather than only marking it stale.

**Explicitly rejected.** A recovery verb or an adoption flag on `return`. It
would be typed only by agents, it hides the strand instead of removing it, and
it puts janitor vocabulary in front of the user.

**Regression to pin.** A completed row with PROOF whose owner is gone and whose
lease is overdue must be reachable by the next seat with no command in between.

## 2. `read` and `gate` proofs have no owner-side completion path

**Failure.** A checkpoint proven by `cmd` flips through `accept`, which reruns
the command. A checkpoint proven by `read` or `gate` cannot flip the same way,
because there is nothing mechanical to rerun. The documented practice is to
record the observation in the plan and return the claim, which leaves the row's
completion and its receipt on two different paths.

**Why it matters.** Most high-value checkpoints on the live board are `read` or
`gate` — hosted review state, deploy state, a person's judgment. They are the
rows most likely to sit half-closed, and half-closed rows are what make a cold
resume ambiguous.

**Remedy to consider.** One completion path that accepts a recorded observation
as the receipt for `read` and `gate`, owned by the claim owner and refused for
anyone else, with the same publish-then-release ordering `cmd` already uses. The
open question is whether the observation is supplied at completion time or read
back out of the plan's Progress receipts; the second is smaller and keeps the
plan the only place the observation lives.

**Do not.** Add an observation flag as a user-facing concept. Whatever the seat
types, the user's surface stays: set a goal, read a brief, answer one decision.

## 3. Acceptance times out building its clean worktree

**Failure.** On a large repository, `accept` fails while creating its clean
checkout. The timeout appears to be fixed at roughly 30 seconds internally, and
raising the caller's timeout does not raise it. The checkpoint cannot flip even
though its proof passed moments earlier.

**Evidence.** Recorded in a live entity plan on 2026-08-18: a raised acceptance
timeout still failed on clean-worktree creation, while the same proof commands
passed directly.

**Remedy to consider.** Let the caller's timeout govern the whole acceptance,
including worktree creation, and report which stage exceeded it. Failing that,
scale the internal budget to repository size instead of a constant.

**Cost of leaving it.** Every large-repository checkpoint records its proof by
hand, which is the same split described in item 2 and the main reason receipts
drift away from row state.
