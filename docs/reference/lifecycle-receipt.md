# Lifecycle receipt

The lifecycle receipt is the small provider-neutral handoff between Vidux's
durable Outcome and the native coding host that Pilot drives. It records a
bounded transition history, not prompts, transcripts, model choices, or a
worker queue.

Canonical schema identifier: `vidux.lifecycle.v1`

| Artifact | Path |
| --- | --- |
| JSON Schema | [`schemas/lifecycle-receipt.v1.json`](../../schemas/lifecycle-receipt.v1.json) |
| Synthetic example | [`examples/lifecycle-receipt/example.json`](../../examples/lifecycle-receipt/example.json) |

## Shape and invariants

The top-level record carries an Outcome ID, the plan revision that was acted
on, and one to 32 ordered events. The first event must enter `planned`; each
later event must name the prior state as its `from_state`. The validator also
enforces the allowed transition graph and rejects events after a terminal state.

The terminal states are `finished_with_proof`, `not_delivered`, and
`handed_off`. Each terminal event requires a bounded `proof_ref`; the receipt
does not embed proof content. A proof reference is resolved by the owning
Outcome document and its host-side evidence checks.

Actors are deliberately small and provider-neutral: `pilot`, `native_host`,
`user`, or `system`. Provider names, model names, credentials, prompts,
transcripts, machine paths, and raw command output do not belong in this public
contract.

Validate a receipt with the read-only standard-library validator:

```bash
python3 scripts/vidux-lifecycle-validate.py \
  --input examples/lifecycle-receipt/example.json
```

The validator emits deterministic JSON: exit `0` valid, `1` invalid, or `2`
invocation/I/O failure. This is a semantic contract and privacy boundary; it is
not a scheduler, provider router, persistence layer, or proof authenticator.
