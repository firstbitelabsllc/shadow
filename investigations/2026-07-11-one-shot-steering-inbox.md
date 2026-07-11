# One-shot steering inbox

## Question

How can an operator steer a goal or loop that is already running—even when a new provider chat turn may be unavailable—without making Vidux a provider client, duplicating plan authority, or creating an unaudited command endpoint?

## Decision

Build a local, plan-scoped one-shot intent inbox with the user-facing label **Steer next turn**.

The inbox carries transient intent only. It does not claim delivery, modify the Authority PLAN, invoke a model, send a chat message, create a goal, schedule a loop, or execute a command. A host runner explicitly leases at most one item at a safe cycle boundary and acknowledges it only after the corresponding user-facing response. If usage or transport is exhausted, the item stays visible and retryable.

## Ownership boundary

- Vidux owns the on-disk event journal, validation, lease/retry/acknowledgement state machine, CLI, loopback HTTP projection, and cockpit UI.
- The Authority PLAN owns durable scope, priority, decisions, task state, proof, and the lasting consequence of accepted steering.
- The host router projects the provider-neutral consumption boundary; it does not own queue storage or provider transport.
- Amp creates compact goal/loop/meta-prompts that point to the Authority PLAN and this generic cycle-boundary contract; it does not duplicate queue mechanics.
- Resplit Loop consumes the same contract after its normal release/authority intake; it does not create a Resplit-specific mailbox or scheduler.
- The host runtime owns actual model/chat execution and the post-response acknowledgement callback.

## State machine

```text
queued --lease--> claimed --ack--> acknowledged
   ^                  |
   |                  +--fail(retryable)--> retryable
   |                                         |
   +----------------------retry--------------+

claimed --fail(terminal)--> failed
claimed --lease-expiry--> retryable
```

- `queued`: visible and available to one eligible consumer.
- `claimed`: visible as being handled; bound to one consumer and a short lease token.
- `retryable`: visible with a safe public failure code such as `usage_exhausted`, `transport_unavailable`, or `lease_expired`; operator or consumer may retry.
- `acknowledged`: omitted from active API/UI after the response callback; a bounded tombstone remains in the journal.
- `failed`: visible until explicitly dismissed; reserved for invalid or policy-blocked handling, never for ordinary usage exhaustion.

One plan may have at most eight active items. A consumer leases at most one item per cycle. Oldest eligible item wins, with UUID identity and UTC timestamps.

## Envelope

Each enqueue event contains only:

- schema version
- opaque item id
- canonical allowed `PLAN.md` path
- UTF-8 intent text, 8 KiB maximum
- creation timestamp
- optional non-secret source label

Lease, fail, retry, acknowledge, and dismiss events reference the item id. Lease tokens are generated locally and are never returned by the list endpoint or cockpit. Active API responses expose status and safe failure code, not filesystem store paths, peer addresses, provider identifiers, hidden prompts, or secrets.

## Security floor

- Store defaults outside repositories under `~/.vidux-browser/steering.jsonl`; tests and operators may override it explicitly.
- All writes use the existing no-follow, single-link regular-file primitives and a cross-process file lock.
- The plan target must resolve to an allowed discovered `PLAN.md` below the configured development root.
- Browser writes are loopback-only, `application/json`, same-origin, bounded, and rejected if the existing sensitive-content detector fires.
- HTTP supports enqueue and operator retry/dismiss only. Lease tokens and consumer mutation stay CLI/local-process only.
- The GUI cannot invoke a provider, shell, arbitrary URL, automation, goal, or loop.
- Journal reads fail closed on malformed state transitions but preserve valid earlier events.
- Acknowledgement and dismissal compact completed bodies immediately into at most 64 bodyless tombstones using the same alias-safe atomic replacement boundary. Active item bodies remain until acknowledged or dismissed.

## Consumer protocol

At every safe cycle boundary:

1. Fresh-read the standing prompt and Authority PLAN.
2. Lease at most one eligible intent for that exact plan.
3. Reconcile it with current plan truth; the plan wins conflicts.
4. Record any lasting scope/status/decision consequence in the Authority PLAN before implementation.
5. Complete the bounded work and return the lease context alongside the normal user-facing response.
6. The outer host callback calls `ack` with the lease token only after that response is accepted; the responding prompt cannot self-certify this ordering.
7. On usage exhaustion or unavailable transport, call `fail --code usage_exhausted` (or allow lease expiry); leave the intent visible and retryable.

This protocol is additive. A loop with no queued item behaves exactly as before.

## CLI contract

```text
vidux steer enqueue --plan <PLAN.md> --message <text> [--json]
vidux steer list --plan <PLAN.md> [--all] [--json]
vidux steer lease --plan <PLAN.md> --consumer <label> [--json]
vidux steer ack --id <id> --lease-token <token> [--json]
vidux steer fail --id <id> --lease-token <token> --code <safe-code> [--json]
vidux steer retry --id <id> [--json]
vidux steer dismiss --id <id> [--json]
```

Human-readable output never prints lease tokens. JSON lease output is intended for the local consuming process.

## Cockpit behavior

- A selected plan shows one compact composer immediately below its mission/control summary.
- Copy: **Steer next turn** / “Queued locally for the next safe loop boundary. This does not send a chat message.”
- `Cmd/Ctrl+Enter` enqueues; the composer clears only after a successful local write.
- Active items render oldest first with queued, being handled, or retry-needed semantics.
- `usage_exhausted` copy says the goal may still be running but the steer was not delivered; Retry leaves user intent intact.
- Acknowledgement removes the item from the active list on the next poll, matching the mental model of a sent chat message after its reply.
- Empty, loading, write-error, claimed, retryable, acknowledged-disappears, narrow mobile, dark, and reduced-motion states receive browser proof.

## Acceptance

- Unit tests cover every valid transition plus stale/wrong lease, two-consumer contention, lease expiry, capacity, malformed journal, sensitive text, target allowlist, symlink/hard-link/lock aliases, and cross-process enqueue without loss.
- HTTP tests prove loopback, Host, same-origin, JSON content type, payload cap, safe response shape, and that lease tokens are never exposed.
- CLI tests prove machine-readable lifecycle and human output redaction.
- Current-source browser proof covers enqueue, claimed, retryable exhaustion, retry, acknowledgement disappearance, desktop, and 320px dark mobile.
- Host prompt, routing, and project-loop adapter contracts all point to this protocol while retaining their existing ownership boundaries.
- Full Vidux verification and public-package scans pass; no provider transport or token-spend claim is introduced.

## Rollback

Remove the cockpit component/routes and stop consumers from leasing. The local journal is inert data and may remain for recovery; no PLAN state, provider state, scheduler, or remote system depends on it.
