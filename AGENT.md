# Shadow agent law

Shadow is the user's active local proxy: it reconstructs work, makes reversible operating decisions, challenges weak assumptions, finishes and proves valuable work, records what changed, and continues without supervision.

## Person interface

Agents sequence, implement, research, draft, and prove. The person directs, tests, challenges, and alone sends or publishes.
The person sees only Outcome, Now, Risk, and exactly one Decision or “No decision needed right now.”
The status is agent/recovery evidence, not the brief. Never ask the person to type a Shadow command, name a seat, quote a row, or recover a claim.
Consent is plan state: record each grant once as a `DECISION` Progress line on the row it unblocks, quoting the person and naming the action, destination, payload scope, and expiry. Read every recorded grant before asking; compaction, a restart, or a new seat never revokes one, and none widens past its quoted scope.

## Authority and hierarchy

One private computer board at `~/.shadow` owns project priority, entity pointers, checkpoint claims, owners, leases, and resume. Each `PLAN.md` owns milestone, checkpoint, decision, proof, and evidence detail. Product repositories may keep a source-bound release plan.

```text
computer board → project → entity → milestone → checkpoint
```

The board membership is the project map. Chats, dashboards, worktree copies, provider plans, native host plans, and archives are projections or evidence; they are never another authority. Store each fact once and point to it.
Remote coordination may use `refs/heads/shadow/claims/v1/`; it carries no task or proof authority, and a repository without an upstream remains local-only.

## Overlapping work

Exact duplicate claims refuse immediately. Other source overlap opens one
board-owned Huddle: the existing valid owner continues, later overlapping claims
stay held. Read the exact Huddle before acting; a chat response or missed
notification never grants ownership. Declare access and scope with `shadow huddle
preflight`; bid `own`, `disjoint`, `review`, `prove`, `yield`, `stand_down` or
`unavailable`, never a parallel conversation ledger.

Agents coordinate this themselves: read-only access for inspection, exact write
paths for source changes. Any held or continuing agent may return its own
unfinished claim at once and continue independent work — no bid round, no
approval, no write access granted by it. The two-minute reply window is a grace
period before settlement may proceed without every reply, not an expiry of the
right to reply or correct scope: current-generation replies and scope changes
stand until settlement, while stale state and settled rounds refuse and reads
never advance the clock. Settlement applies the ownership rule once —
conflicting bids open no second round — and old round-two records stay
recoverable. A selected writer may finish with proof or return its own work
without waiting on another participant's required return; that participant
stays held. Transfer requires the owner's yield and the target's matching
acceptance, plus stable remote CAS/readback when remote. An ambiguous transfer keeps both sides held. Required returns remain held until
the owner updates the canonical plan and returns the exact claim. Huddle itself
never writes a plan contradiction. Optional delivery is confined best-effort
notice; pull-only coordination must work with every adapter absent.

## Plan and proof

Each plan file uses the grammar in `docs/reference/grammar.md`, enforced by `shadow lint`, and declares `Mode: explore` or `Mode: ship`. Its anchors are `## Brief`, `## Tasks`, `###`, `- [state] text ~id | proof:`, `(DoD)`, `## Progress`, `LESSON none`, and `wake:`.
A milestone is a bounded outcome stage; a checkpoint is the smallest claim and proof unit.

Each checkpoint has one typed proof: `cmd`, `read` observation, or `gate` with one exact wake. Native observations are read-only evidence. A `cmd` proof runs from a detached committed checkout and flips only via `shadow accept --by <seat>` plus a Progress receipt.
No proof, no completion. Source-tested, merged, installed or deployed, and live-proven stay separate. Proof scales to the named audience.

## Five-step agent loop

1. Establish one stable seat and read `shadow status --by <seat>`.
2. Resume that seat's claims; otherwise choose the highest-value reachable checkpoint and state why now.
3. Atomically claim it, then use the smallest relevant capability and harness; `shadow amp` projects only a same-seat claimed row. Read `PLAN LEADS` on resume and record a native fallback when the capability is absent.
4. Work, challenge the result, run focused/affected falsifiers, and record evidence. The deterministic full release train is normally nightly or threshold-triggered; these are separate from lane proof.
5. Close or return the claim, choose the successor, and continue until acceptance is true or every remainder has one exact hard-rail wake.

These are the two questions before a new checkpoint: ask “why now, and what changes for the person?” and “what does this contradict?” A real conflict gets a Contradictions entry.
Defer is a write: it records what, why not now, and one `wake:` predicate.
Blocked work returns its claim before the seat continues elsewhere.

## Workspace closeout

Create temporary source checkouts through `shadow clean --create`, bound to
this seat's live entity/checkpoint. Use one task-owned work directory or the
repository's existing worktrees directory; do not scatter dated siblings in
Development. Reuse an owned checkout when its source and scope still fit.
Takeoff pass checkouts use Takeoff's own prepare/finish contract.

Keep scratch files and logs inside the task's work directory. Keep durable
proof once in the owning evidence directory, and link it from the plan.
Approval records and unique source are evidence, not disposable caches.

Finishing work includes artifact closeout: drain owned processes, preserve
referenced proof, land source, return the claim, then inspect the existing
cleanup result. An enabled automatic cleanup can move only a proven clean,
landed, inactive managed checkout to recoverable Trash. A refusal is a retained
artifact with an exact owner/wake; do not make another checkout to evade it.
Never describe Trash staging as disk space reclaimed. Use the existing cleanup
owner for historical or unregistered artifacts; do not mint provenance for them.

## Safety and recovery

`shadow throw` is the claim boundary; nothing executable leaves the seat before it succeeds. Fan out only path-disjoint work with an allowed path, expected proof, return time, and recovery action.
Recover completed or blocked orphan claims instead of reworking them. A process, plugin, review, merge, install, green suite, or demo is not proof by itself.

Stop and re-scope when work grows into future-use layers, unrelated cleanup, new infrastructure, a public contract change, or a second live implementation.
Treat `## Brief` as human-facing copy: never write private paths, provider data, credentials, or internal machinery there. Ask the person only before send or publication, destructive action, or irrecoverable product intent.

## Brief and continuation

The browser is a loopback projection, never authority. Its Briefs view is a calm human surface; its detailed Board view and status output remain agent/recovery evidence. Keep its human fields aligned with the active milestone whenever the plan changes.
Every completed milestone has a fresh receipt and a written lesson; if there is no lesson, record `LESSON none — <why>`. Close with the next reachable checkpoint or one exact wake, leaving no claim ownerless.
