# Local event vocabulary

Shadow has no network transport for these events. With
`SHADOW_TELEMETRY=local`, a successful `shadow throw` appends one bounded JSON
line to `.shadow/evidence/shadow-events.jsonl` in that exact project. Every
other value, including an unset variable, leaves the writer off. The event file
is mode `0600`; its parent directories and destination are opened without
following symlinks.

Unknown input fields are omitted when the record is constructed, so there is
no later scrub pass that temporarily holds a wider payload. Values remain
untrusted at construction. The local writer accepts only a lowercase project slug, a
64-hex logical entity id, a four-character row id, fixed verb and outcome
vocabularies, a bounded integer duration, and a UTC timestamp. It records no
seat, plan text, proof command or output, environment value, repository path,
provider, or account.

The local file is optional observation, never authority. Failure to append it
does not undo or contradict a durable claim; `shadow throw` reports that fixed
condition without exposing the failed path. Nothing reads the file to choose,
claim, accept, or resume work.

The closed field vocabulary is:

| Field | Meaning |
| --- | --- |
| `schema` | Fixed local event schema identifier. |
| `recorded_at` | UTC event time. |
| `project` | Lowercase project slug. |
| `entity` | Logical entity identifier. |
| `row` | Checkpoint row identifier. |
| `verb` | Shadow lifecycle verb. |
| `duration_ms` | Bounded elapsed milliseconds. |
| `outcome` | Lifecycle outcome. |

Endpoint selection and any exact network field subset remain a person-gated
decision; neither exists here.
