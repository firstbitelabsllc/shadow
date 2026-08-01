# Vidux Drive mode

Drive mode is the small semantic client contract used by native Codex Voice
(90) when Vidux is the selected structured-plan surface. It is a view and one
typed action, not another runtime.

## Read: `vidux.outcome.v1`

The client reads one already-validated [`vidux.outcome.v1`](./outcome-ask-steer.md)
document and presents:

- the current Outcome state, summary, and move;
- an open Ask with at most three options labelled A, B, and C;
- all recorded Steer states, including `superseded` entries; and
- proof references and delivery state.

The client must not copy through arbitrary fields. Provider, model, prompt,
transcript, credential, host, command, path, and raw-content fields remain
outside the public boundary. A projection is disposable and is never an
authority or a transcript cache.

## Write: `vidux.drive-steer.v1`

Selecting an option produces one ephemeral, closed envelope:

```json
{
  "schema": "vidux.drive-steer.v1",
  "kind": "answer",
  "revision": 4,
  "outcome_id": "publish-notes",
  "ask_id": "choose-release",
  "option_id": "ship-now"
}
```

The envelope is not a durable Steer record. The host that owns the Outcome
checks the supplied revision and current Ask, applies its normal acceptance and proof
rules, then records the resulting `Steer` in the same Outcome authority. It
may reject the choice as stale or unavailable. The envelope contains no free
text, provider/model selector, command, queue, credential, or execution
instruction.

## Local receipt handshake

The owning local host may pass the envelope and the current Outcome document to
the pure `receive_choice` helper. It performs a compare-and-set on `revision`
and returns a new document plus one `vidux.drive-receipt.v1` object; it does not
write storage, invoke a provider, or create a queue.

- A current, visible choice appends one `received` Steer and advances the same
  document revision.
- A stale choice appends `superseded`.
- A hidden option, closed Ask, or identity mismatch appends
  `not_delivered` with a bounded local proof reference.

The original document is never mutated. Callers run the canonical
`scripts/vidux-outcome-validate.py` validator on the returned document before
folding it into the owning authority. The receipt proves the local semantic
handoff only; it never claims that coding work ran or that a provider was
selected.

## Native-client rules

90 may read the projection, present no more than three choices, send one
typed envelope, and report the host's receipt. It may not execute code, select
or relay a provider, watch windows in the background, persist raw speech or
screens, or create a second plan/queue. Vidux validates and records semantic
truth; Codex, Claude Code, and Cursor remain the execution and credential
boundaries.
