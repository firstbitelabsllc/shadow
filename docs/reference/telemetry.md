# Local event vocabulary

Shadow has no network transport for these events. This boundary only constructs
an in-memory record; it does not write a file, read environment state, or send
anything. Unknown input fields are omitted when the record is constructed, so
there is no later scrub pass that temporarily holds a wider payload.

This checkpoint guarantees field names only. Values remain untrusted and must
not be persisted or transmitted until later emitter and redaction checkpoints
validate identifiers, types, ranges, vocabularies, and secret/path constraints.

The closed field vocabulary is:

| Field | Meaning |
| --- | --- |
| `schema` | Fixed local event schema identifier. |
| `recorded_at` | Candidate event time. |
| `project` | Candidate project identifier. |
| `entity` | Candidate logical entity identifier. |
| `row` | Checkpoint row identifier. |
| `verb` | Shadow lifecycle verb. |
| `duration_ms` | Candidate elapsed milliseconds. |
| `outcome` | Candidate lifecycle outcome. |

No event is written at this checkpoint. The later local-writer checkpoint owns
that behavior. Endpoint selection and any exact network field subset remain a
person-gated decision; neither exists here.
