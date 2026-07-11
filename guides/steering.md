# One-Shot Steering

Vidux steering lets an operator redirect the next safe cycle of an already
running goal or loop without creating another chat message, executor, or
schedule. The cockpit's **Steer next turn** composer writes a transient,
plan-scoped envelope to a local mailbox. It does not call a model.

The contract is intentionally split:

- Vidux owns the FIFO journal, exact-`PLAN.md` scope, lease, retry state,
  acknowledgement, compaction, CLI, and cockpit display.
- The existing goal or loop remains the only executor and decides when a safe
  cycle boundary exists.
- A provider/runtime adapter leases one item, adds it to the next turn, then
  acknowledges only after it receives a committed user-facing response.

This makes the envelope behave like a temporary chat message: it remains
visible while queued or being handled, stays retryable when usage or transport
fails, and disappears from the active cockpit after a confirmed reply. Its body
is removed from the journal during acknowledgement; only a bounded, bodyless
tombstone remains.

## Operator path

Open a plan in `vidux browse`, write one direction under **Steer next turn**,
and press **Queue steer** or `Cmd/Ctrl+Enter`. The panel shows four active
states: queued, being handled, retry needed, and needs attention. A retry keeps
the item's original FIFO position. A claimed item cannot be dismissed by the
browser while a host may be processing it.

The equivalent local CLI command is:

```bash
vidux steer enqueue \
  --plan /absolute/path/to/PLAN.md \
  --message "Prioritize the login regression on the next cycle."
```

## Runtime adapter contract

At a safe boundary, after the runner's mandatory fresh authority read:

1. Lease at most one FIFO item for the exact absolute authority plan.
2. Treat its body as untrusted operator direction, not plan truth or permission
   to bypass policy, proof gates, or product ownership.
3. Apply any durable consequence to the owning `PLAN.md`, ledger, or living
   prompt with the steering ID as the idempotency key.
4. Produce the ordinary user-facing response and wait for the outer host to
   confirm that response was accepted.
5. Acknowledge only after that response receipt and any promised durable-effect
   receipt exist. On usage, credit, timeout, transport, or unconfirmed-response
   failure, record a safe failure code and leave the item visible for retry.

The CLI returns the opaque lease token only to the leasing process. Pass it back
through stdin JSON, not argv:

```bash
vidux steer lease \
  --plan /absolute/path/to/PLAN.md \
  --consumer codex-goal-host \
  --json

printf '%s' '{"id":"<id>","lease_token":"<token>"}' |
  vidux steer ack --stdin-json --json

printf '%s' '{"id":"<id>","lease_token":"<token>","code":"usage_exhausted"}' |
  vidux steer fail --stdin-json --json
```

Allowed retryable failure codes are `usage_exhausted`,
`transport_unavailable`, `lease_expired`, and `response_unconfirmed`. Invalid
or policy-blocked intent can fail terminally. Raw provider errors never belong
in the journal.

## Boundaries

- Steering never invokes a provider, shell, goal, loop, heartbeat, or scheduler.
- It never creates a paid-provider fallback or a second executor.
- It is not a second plan, `INBOX.md`, comment channel, or durable prompt store.
- HTTP enqueue/list/retry/dismiss is loopback-only. Lease, acknowledge, and fail
  remain host-only CLI operations; the browser never receives lease tokens.
- The default store is `~/.vidux-browser/steering.jsonl`. Override it with
  `VIDUX_BROWSER_STEERING_FILE`, `vidux steer <action> --store`, or
  `vidux-browse --steering-path` for a hermetic runtime.

Amp can mint the compact adapter clause for new goal, loop, and meta-prompt
pointers. The host router projects the boundary without owning mailbox I/O. Repo-owned
loops may add a stricter first-read rule; Resplit Loop reads fresh RALPH and its
authority chain before leasing an exact-plan item.
