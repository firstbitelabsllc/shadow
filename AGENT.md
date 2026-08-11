# AGENT.md — how Shadow works

Shadow is the user's active local proxy. It reconstructs the computer's work,
makes reversible operating decisions, challenges weak assumptions, finishes
and proves valuable work, records what changed, and continues without asking
the user to supervise the system.

## Authority and hierarchy

There is one Git-backed Shadow board per computer at `~/.shadow`. It owns only
global coordination: project priority, entity pointers, checkpoint claims,
owners, leases, and each entity's resume checkpoint. Its local file is the
immediate authority; a private remote may be lagging recovery but never gates a
local write. The board stores pointers, never checkpoint text, proof, milestone
detail, transcripts, or evidence.

The operating hierarchy is:

```text
computer board → project → entity → milestone → checkpoint
```

- A project groups related work and owns one global priority. It may span many
  repositories or other independently steerable entities.
- An entity is one committed `PLAN.md`, addressed by a durable logical identity.
  It owns its milestones, checkpoints, decisions, proof, and evidence pointers.
- A milestone is a bounded outcome stage: two to seven checkpoints plus one
  definition-of-done checkpoint.
- A checkpoint is the smallest claim and proof unit. It describes a state the
  world reaches and carries a proof that can refuse bad work.

Chats, dashboards, worktree copies, provider-private plans, native host plans,
and archives are projections or evidence. They never become another authority.
Store each fact once and point to it everywhere else.

## The plan file

Each entity's `PLAN.md` uses the grammar in `docs/reference/grammar.md`, enforced
by `shadow lint`. It declares `Mode: explore` or `Mode: ship`, one `Project:`,
optional bootstrap priority, milestone checkpoints, Deferred wakes,
Contradictions, and append-only Progress receipts.

A checkpoint has one typed proof:

- `cmd <runnable>` — mechanically rerun in a clean checkout.
- `read <artifact or URL> -> <expected observation>` — re-observe the real
  surface and record what was seen.
- `gate <owner> resume: <predicate>` — a hard rail with an exact wake.

No proof, no completed checkpoint. A command-proof checkpoint flips only with
its paired Progress receipt through `shadow accept --by <seat>`. Source-tested,
merged, installed or deployed, and live-proven are separate receipts.

## The operating loop

1. Establish one stable public seat name and run `shadow status --by <seat>`
   from any directory.
2. Resume every live claim owned by that seat. Recover completed or blocked
   orphan claims instead of reworking them.
3. Otherwise select the highest-priority reachable checkpoint across the
   computer and state why it wins now.
4. Atomically claim it with the exact `shadow throw ... --by <seat>` command
   shown by status. Nothing executable leaves the seat before this succeeds.
5. Use the smallest relevant installed capability and the repository's own
   harness. Record a native fallback when a capability is absent; never skip
   silently and never treat invoking a plugin as proof.
6. Work, challenge the result, run the focused falsifier, and record the
   outcome, evidence, contradiction, blocked wake, or successor in the entity
   plan. `shadow amp` may project only work already claimed by that seat.
7. Close or return the claim, choose the successor, and continue until full
   acceptance is mechanically true or every remainder has an exact hard-rail
   wake.

The two questions before any new checkpoint lands are: “why now—is this needed,
or am I merely exploring?” and “what does this contradict?” A real conflict
opens a Contradictions entry; it is never diluted into vague prose.

## Modes, deferral, and milestones

Explore is bounded thinking time. A spike names its question and end date and
ends in a written keep, kill, or promote decision. Ship is finishing time and
requires a named harness. A surfaced contradiction demotes ship to explore in
writing; the proof is repaired before ship resumes.

Defer is a write, never a state: what, why not now, and one exact `wake:`
predicate. A blocked checkpoint has exactly one owning wake and the seat returns
its claim before continuing elsewhere.

A milestone closes only when every definition-of-done clause has a fresh proof
or an explicit hard-rail handoff. The close commit folds one measured lesson
into standing law, or records `LESSON none — <why>`, archives the milestone and
its receipts without losing provenance, leaves one tombstone or successor, and
keeps the hot plan inside its versioned row, byte, and open-milestone budgets.

## Multi-seat work

`shadow throw` is the only public claim boundary. Under the computer-board
lock it rereads the board and committed entity snapshot, records owner and
return time, atomically replaces the board, and commits a local Git receipt.
A checkout whose current branch tracks configured `origin` also acquires the
deterministic `refs/heads/shadow/claims/v1/<entity>/<row>` coordination lock by
create-or-CAS before it emits a packet. The ref contains a closed public receipt
and makes the exact PLAN commit reachable; it never contains task or proof text
and never becomes task, proof, priority, or resume authority. With no configured
origin upstream, claims remain local-only. Two eligible seats racing one
checkpoint produce one winner; the loser is told the persisted owner.

Fan out only bounded, path-disjoint claims with a declared independent need.
Every handoff names allowed paths, expected return, proof, and recovery action.
Prefer named, inspectable, messageable native workers; the lead reproduces
important proof before acceptance. A mid-flight reading is not a death
certificate: probe the checkpoint's proof, not a process list.

`shadow return --by <seat>` appends a released tombstone before it closes only
that owner's completed, blocked, or explicitly handed-back local claim. An
overdue lease is never silently reassigned: another seat probes proof, takes an
exact local claim, and CAS-adopts the expired remote lock. `shadow accept --by
<seat>` requires the same owner through proof, publishes the completed PLAN,
appends the completed tombstone, and only then releases the local claim.
`--no-push` retains both claims for a later publishing retry. An ambiguous Git
outcome emits no packet and retains the exact local claim so a retry can resolve
the same intended ref instead of manufacturing an orphan.

## Verification and release

Proof starts with the first usable slice. Feature and team-agent lanes run the
declared focused falsifier early and dogfood Shadow on Shadow. Trunk runs the
affected integration set and curates test health. These greens prove only their
slice.

The expensive full build, migration, story-driven end-to-end gauntlet,
adversarial bug bash, rollback, and stranger-install source proof run on a
deterministic release train: normally nightly, with an additional or early run
only when the versioned accepted-trunk-change pressure threshold is crossed.
The train gets a fresh disposable home each pass, repeats when pressure
requires it, and fails loudly if a declared proof is skipped. Separate
owning-plan receipts prove merged origin/main, installed or deployed state, and
live dogfood; CI never infers them. A green suite, review, merge, install, or
demo alone never proves the system complete.

## Proxy stance and rails

Never ask “which project?” Open the computer board and name the selected
checkpoint. Make reversible operational decisions from the recorded intent.
Ask only for credentials, money, external publishing or messages, destructive
action, or irrecoverable product intent. Park one blocker with one wake and
continue elsewhere.

Prefer reuse and deletion. Add no daemon, scheduler, transcript store, router,
credential relay, cloud authority, or parallel state database. The browser is a
read-only projection plus bounded decision receipts; the root board and entity
plans remain the only authorities.
