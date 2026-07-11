# Live-agent coordination and failover

## Question

How can several chats work on one project at the same time, see who owns each slice, and recover when one chat loses its usage window without duplicating work or turning Vidux into a provider scheduler?

## Decision

Extend Vidux's existing local claims bus into a short, provider-neutral work lease and show its sanitized state in the cockpit for the selected `PLAN.md`.

The selected PLAN remains the durable authority. Coordination state is disposable presence: owner label, task, claimed work surface, heartbeat, compact checkpoint, exact resume pointer, expiry, and final handoff status. Vidux never launches, resumes, messages, or bills a provider. Claude, Codex, a local runner, or any future host uses the same CLI contract.

## One shared control room

Each concurrent chat does this before editing:

1. Fresh-read the selected PLAN and current coordination snapshot.
2. Choose one unclaimed task/work surface.
3. Acquire a short lease using a stable local session label supplied by its host.
4. Record the claim id in its own loop context.
5. Refuse overlapping work while another unexpired owner holds the surface.

During work, the chat heartbeats at safe boundaries and writes a compact checkpoint plus an exact disk resume pointer. Lasting scope, decisions, row state, proof, and next work still belong in the PLAN; the heartbeat is only a fast index back to those durable facts.

## Lifecycle

```text
unowned --claim--> active --heartbeat--> active
   ^                  |                    |
   |                  +--release(done)-----+
   |                  +--release(handoff/usage_exhausted/blocked)
   +------------------+--lease expiry
```

- `active`: one owner holds one exact repo/work-surface key until its current expiry.
- `heartbeat`: same owner extends the lease and may replace the compact checkpoint/resume pointer.
- `release`: same owner ends the lease with `done`, `handoff`, `usage_exhausted`, `blocked`, or `cancelled`.
- `expired`: no heartbeat arrived before expiry. The claim stops blocking another owner; its last checkpoint remains visible as recent handoff context.
- `takeover`: a fresh owner must re-read PLAN, checkpoint, git/worktree state, and proof before claiming. Takeover never means blindly continuing an old process or resetting its files.

There is no active-lease preemption button. An operator may queue a plan-scoped one-shot steer, but ownership changes only by same-owner release or clock expiry.

## Identity and scope

- `owner`: a non-secret stable session label supplied by the host, not inferred from a provider.
- `repo`: local project label.
- `plan_path`: exact allowed Authority `PLAN.md`.
- `task_id`: existing plan row or durable work identifier.
- `claim`: exact work surface, normally a plan row, file path, or named lane.
- `lane`: human-readable lane label.

One host may own disjoint claims. Two owners cannot hold the same `repo + claim` while the first lease is live. Repeating the same claim by the same owner is idempotent. Heartbeat and release require the same owner.

## Usage-window behavior

- A host that receives a real usage-exhausted response immediately releases with status `usage_exhausted` and the latest resume pointer.
- A host that cannot run a callback simply stops heartbeating; normal expiry makes the surface available.
- A one-shot steer that failed for usage remains separately visible and retryable. Work ownership and steer delivery are distinct truths.
- A new chat never assumes expiry means the old source branch, build, PR, or deploy completed. It verifies each surface from disk/runtime.

## Cockpit

The selected plan shows a compact **Live work** panel adjacent to **Steer next turn**:

- active owner count and lease freshness;
- owner, task/lane, claimed surface, last checkpoint, resume pointer, and expiry;
- recent `usage_exhausted`, `handoff`, `blocked`, and `expired` entries under **Ready to resume**;
- honest empty state: “No live owner. Claim a slice before editing.”

The panel is read-only. It does not expose hostnames, process ids, filesystem journal paths, tokens, hidden prompts, or provider/account identifiers. Claim, heartbeat, and release remain local CLI operations so a browser page cannot impersonate a chat.

## CLI contract

```text
vidux coordinate claim --repo <repo> --claim <surface> --owner <session> \
  --lane <lane> --plan-path <PLAN.md> --task-id <row> [--ttl-hours <n>]
vidux coordinate heartbeat --claim-id <id> --owner <session> [--ttl-hours <n>]
vidux coordinate checkpoint --claim-id <id> --owner <session> \
  --summary <text> --resume <pointer> [--proof <receipt>] [--ttl-hours <n>]
vidux coordinate release --claim-id <id> --owner <session> \
  --status <done|handoff|usage_exhausted|blocked|cancelled> [--resume <pointer>]
vidux coordinate active [--repo <repo>]
vidux coordinate snapshot [--repo <repo>] [--handoff-limit <n>]
```

The historical `scripts/vidux-claims.py claim|active|release` forms remain compatible.

## Security and failure floor

- Local append-only JSONL with a cross-process lock; reject symlink, hard-link, and non-regular journal aliases.
- Strict UTF-8 and bounded rows/fields/read window.
- Reject duplicate claim ids, wrong-owner heartbeat/release, time reversal, invalid expiry, and unknown event/state values.
- Browser read is loopback-only, exact-plan-filtered, bounded, and fail-closed on malformed state.
- HTTP returns only sanitized coordination fields. There is no coordination write route.
- Clock expiry uses parsed UTC timestamps and never deletes PLAN or worktree state.

## Resplit Loop adapter

At every cycle, Resplit Loop fresh-reads the release plan and coordination snapshot before choosing work. It claims one exact plan row/work surface, heartbeats after meaningful proof or at a bounded interval, and writes its latest durable consequence to the release plan. When its host detects usage exhaustion it releases immediately; otherwise expiry is the fallback. Another Resplit chat can then verify the plan, worktree, PR, simulator/build, and proof state before takeover.

This adds awareness and recovery; it does not create more workers, duplicate the existing loop, or choose providers.

## Acceptance

- Four simulated owners can hold four disjoint Resplit slices and appear together for one plan.
- A fifth owner conflicts on an active surface.
- Same-owner claim and callbacks are replay-safe.
- Heartbeat extends expiry and updates only bounded checkpoint/resume metadata.
- Wrong-owner heartbeat/release fails without journal mutation.
- Explicit `usage_exhausted` release stops blocking immediately and appears as resumable.
- Silent expiry stops blocking and the next owner can claim after re-read.
- Browser/API omit host, pid, journal path, and any hidden/runtime token.
- Desktop, narrow mobile, dark, empty, four-owner, exhausted-handoff, and expired states render without overflow.

## Rollback

Remove the read-only cockpit projection and stop host adapters from emitting heartbeats. Existing claim rows are inert local metadata; PLAN, branches, worktrees, chats, providers, and the one-shot steering inbox continue independently.
