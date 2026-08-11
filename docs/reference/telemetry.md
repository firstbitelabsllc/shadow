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

## Local sink — the owner's endpoint decision (2026-08-11)

The owner decided the endpoint: a **Langfuse instance on the owner's own
machine** (`http://localhost:3000`), for debugging and observability while
long test jobs run against Shadow. The decision's scope, in plain terms:

- **The product still sends nothing, ever.** The ~obsv verdict — Langfuse
  KILLED as a product dependency, because Shadow makes zero network calls —
  stands untouched. No product verb gains network code.
- **The sink is owner tooling**: `scripts/dev/shadow-observed-gauntlet.py`
  runs long test jobs and ships their traces (and, optionally, the already
  allowlisted local event file) to the local Langfuse over OTLP. It refuses
  to run unless `SHADOW_LANGFUSE_HOST`, `SHADOW_LANGFUSE_PUBLIC_KEY`, and
  `SHADOW_LANGFUSE_SECRET_KEY` are all set. A machine without those set —
  every user machine — behaves exactly as it does today.
- **The approved field subset** for forwarded events is exactly the closed
  vocabulary above — the forwarder adds job name, exit code, pass/fail,
  duration, and a home-path-redacted output tail for its own test jobs, and
  nothing else.
- The compose file and provisioned keys live outside the repository, on the
  owner's machine only.
