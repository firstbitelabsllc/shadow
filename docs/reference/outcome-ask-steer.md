# Outcome Ask Steer Interchange

Provider-neutral document shape for one durable Outcome, an optional Ask, zero
or more Steers, and proof references. The contract validates bounded semantic
state only. It does not execute work, route models, persist state, read plans,
contact a provider, or synchronize another product.

Canonical schema identifier: `vidux.outcome.v1`

| Artifact | Path |
| --- | --- |
| JSON Schema | [`schemas/outcome-ask-steer.v1.json`](../../schemas/outcome-ask-steer.v1.json) |
| Synthetic example | [`examples/outcome-ask-steer/example.json`](../../examples/outcome-ask-steer/example.json) |

## Top-level document

The top-level object is closed (`additionalProperties: false`) and requires:

| Field | Rule |
| --- | --- |
| `schema` | Exactly `vidux.outcome.v1` |
| `revision` | Integer from `0` through `2147483647` |
| `updated_at` | RFC 3339 UTC timestamp ending in `Z` |
| `outcome` | One Outcome object |
| `ask` | One Ask object or `null` |
| `steers` | Array of Steer objects, maximum 64 |
| `proof` | Array of proof-reference objects, maximum 64 |

Identifiers use `^[a-z][a-z0-9_-]{2,63}$`. IDs are unique across the whole
document, not only within each collection.

## Outcome

Closed object requiring:

| Field | Rule |
| --- | --- |
| `id` | Identifier |
| `summary` | Nonblank string, maximum 280 Unicode characters |
| `state` | `working`, `needs_input`, `blocked`, `finished_with_proof`, or `not_delivered` |
| `current_move` | Nonblank string up to 280 characters, or `null` |

## Ask

When present, a closed object requiring:

| Field | Rule |
| --- | --- |
| `id` | Identifier |
| `category` | `product_choice`, `security`, `money`, `external_communication`, or `irreversible_action` |
| `question` | Nonblank string up to 280 characters |
| `options` | 2 through 5 closed option objects with unique option IDs |
| `state` | `open`, `answered`, or `superseded` |
| `answer_option_id` | Option identifier or `null` |

Each option requires `id`, `label` (1–80 characters), and `consequence`
(1–280 characters).

An Ask is a genuine decision interrupt. It is never a disguised run control.

## Steer

Each closed Steer object requires:

| Field | Rule |
| --- | --- |
| `id` | Identifier |
| `outcome_id` | Identifier of the enclosing Outcome |
| `summary` | Nonblank string up to 280 characters |
| `state` | `received`, `applied`, `working`, `blocked`, `finished_with_proof`, `not_delivered`, or `superseded` |
| `proof_ref` | Proof identifier or `null` |

A Steer describes an update to one Outcome. A document may record at most one
Steer in a nonterminal state (`received`, `applied`, `working`, or `blocked`).
A host must stop or supersede stale live work according to its own queue policy;
Vidux only validates the recorded states and does not stop workers or mutate
queues.

## Proof reference

Each closed proof-reference object requires:

| Field | Rule |
| --- | --- |
| `id` | Identifier |
| `type` | `test`, `runtime`, `ui`, `release`, `document`, or `other` |
| `locator` | Repository-relative path with no `..` segment, or an HTTPS URL without userinfo, query, or fragment; maximum 512 characters |
| `verification_summary` | Nonblank string up to 500 characters |
| `delivery` | `delivered` or `not_delivered` |

A proof reference is a locator plus summary. Schema validity is not proof
authentication, execution evidence, or a claim that a Steer stopped a worker.
The coding host and current lead own those claims.

## Semantic invariants

Hosts that accept this document must enforce:

- Every `steer.outcome_id` equals `outcome.id`.
- Every non-null `steer.proof_ref` resolves to a proof ID.
- `outcome.state == needs_input` if and only if `ask.state == open`.
- An answered Ask has a non-null `answer_option_id` that resolves to one of its
  options. Open or superseded Asks have a null answer.
- `outcome.state == finished_with_proof` requires at least one
  `delivery == delivered` proof.
- `outcome.state == not_delivered` requires at least one
  `delivery == not_delivered` proof.
- A Steer in `finished_with_proof` or `not_delivered` requires a proof
  reference with the matching delivery value.
- At most one Steer may have a nonterminal state.
- Document-wide ID uniqueness across Outcome, Ask, options, Steers, and proof.

The JSON Schema encodes structural shape and enums. Cross-field invariants are
enforced by a host validator that uses only the language standard library and
never writes files, uses the network, inspects Git, reads a plan, or executes a
command.

## Privacy and trust boundary

Reject recursively:

- unknown fields;
- keys containing `prompt`, `transcript`, `secret`, `password`, `credential`,
  `provider`, `model`, `host`, `account`, `quota`, `command`, `shell`, or
  `raw`;
- string values containing absolute POSIX, drive, or UNC paths; `$HOME`,
  `${HOME}`, `file://`, or `~/` paths; NUL/control characters; Unicode format
  or bidirectional controls; non-NFC text; or common secret-token prefixes;
- non-finite numbers.

Raw transcripts, provider prompts, secrets, and untrusted retrieved text never
belong in this state. A coding host may derive a bounded semantic summary; the
durable plan and audit receipt remain the authority for work claims.

## Non-goals

- Adapters, provider SDKs, or model routing
- Persistence, plan reading, or product synchronization
- A second ledger, transcript archive, or shared-memory claim
- Authenticating proof references or asserting live execution
