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
- **The sinks are owner tooling**: `scripts/dev/shadow-observed-gauntlet.py`
  covers lifecycle events, while `scripts/dev/shadow-routing-gauntlet.py`
  runs the real 12-scenario by four-host model-policy evaluation. Both refuse
  to run without explicit local Langfuse endpoint and project credentials. A
  machine without those values — every ordinary user machine — behaves exactly
  as it does today.
- **The approved field subset** for forwarded events is exactly the closed
  vocabulary above — the forwarder adds job name, exit code, pass/fail,
  duration, and a home-path-redacted output tail for its own test jobs, and
  nothing else.
- **Routing-evaluation summaries use a separate closed schema**: policy
  version, random run ID, host, scenario, semantic class, requested execution
  shape, requested and observed model labels, exit/timeout, bounded usage and
  cost when the native host supplies them, native-child count, one stable error
  code, and pass/fail.
  Raw prompts, transcripts, tool payloads, file contents, repository paths,
  credentials, account/session identifiers, and provider responses are never
  sent. The routing gauntlet refuses non-loopback Langfuse and readback URLs.
  Every write must be followed by exact trace-ID readback; accepted HTTP without
  readback is red.
- The compose file and provisioned keys live outside the repository, on the
  owner's machine only.

## Sink environment contract

Both owner tools refuse to run without the three required values:

| Variable | Meaning |
| --- | --- |
| `SHADOW_LANGFUSE_HOST` | Loopback Langfuse endpoint, e.g. `http://localhost:3000`. |
| `SHADOW_LANGFUSE_PUBLIC_KEY` | The local project's public key. |
| `SHADOW_LANGFUSE_SECRET_KEY` | The local project's secret key. |

Every written trace is verified by exact trace-ID readback; accepted HTTP
without readback is red. The readback path differs by sink major version:
Langfuse v3 serves it from the web API; Langfuse v4 (`events_only` mode)
retires that API, so v4 sinks also set:

| Variable | Meaning |
| --- | --- |
| `SHADOW_LANGFUSE_READBACK_URL` | Loopback ClickHouse HTTP endpoint, e.g. `http://localhost:8123`. |
| `SHADOW_LANGFUSE_PROJECT_ID` | The local project id read back from `default.events_core`. |
| `SHADOW_LANGFUSE_READBACK_USER` | ClickHouse user, when the instance requires auth. |
| `SHADOW_LANGFUSE_READBACK_PASSWORD` | ClickHouse password. |

The observed gauntlet falls back to the v3 web-API readback when the v4
variables are unset. The routing gauntlet requires the v4 variables on any
current sink. `SHADOW_LANGFUSE_EVENTS` optionally forwards a local event
file as spans on the observed path.

## Scheduled owner loop

The sinks earn their keep on a schedule, not by hand. The owner-machine loop
(launchd, systemd timer, or cron — the entry itself lives outside the
repository like the compose file) keeps four properties:

- **One lock, one log, one status file.** A second firing exits immediately;
  the status file is the only read surface, so a missed night is a visible
  state, never silence.
- **Fast-forward-only checkout.** The loop fetches and merges `origin/main`
  with `--ff-only` and fails loudly on a dirty or diverged checkout rather
  than reporting results from a stale tree.
- **A pinned interpreter.** Scheduler environments resolve `python3`
  differently than a login shell; the loop pins its interpreter (or
  `SHADOW_PYTHON`) instead of trusting `PATH`.
- **Health probes before the long run.** Sink host and readback endpoints are
  curled first; a squatted port or a booting stack fails the run in seconds
  with an exact status, instead of turning a full gauntlet into a guaranteed
  red discovered an hour later. Scheduler output is unbuffered so a
  mid-flight run is observable in the log.
