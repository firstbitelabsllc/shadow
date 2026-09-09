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

## Observe native delegation

The same `SHADOW_TELEMETRY=local` opt-in makes an ordinary `shadow host run`
retain controller observations in that repository's existing event file.
The run needs an admitted v2 claim and a separate `--out` file beneath
`.shadow/evidence/`. Authority-proposal runs are outside this observation
path. With telemetry unset, host execution creates no observation stream.

After admission, the controller appends `host_start` immediately before the
launch attempt. After the host returns and the controller checks its source
changes, it writes the existing attempt receipt and appends `host_finish`
with the digest of those exact bytes. A process that fails or times out is
still an attempt. Pre-admission refusals do not enter this stream.

These records use the closed `shadow.host-observation.v1` schema:

- Both phases contain schema, recorded_at, event, run_id, entity, row,
  claim_revision, owner_sha256, worktree_sha256, task_sha256, host and
  work_class. The random run identity and opaque hashes distinguish launches,
  owners, source worktrees and frozen tasks without retaining their text.
- The finish phase additionally contains receipt_sha256,
  receipt_path_sha256, status and duration_ms. The receipt locator is hashed;
  the record contains no absolute path. Duration is total runner elapsed time,
  including its checks, and does not measure a person's attention.

Each host event is limited to 2 KiB and uses the same mode-0600, locked,
non-symlink append path as the legacy event. No prompt, model message, tool
payload, source content, session ID, credential or account value enters these
records. The controller excludes only its exact pre-launch log append from
the source-change check: a worker append, even a valid event, invalidates the
execution candidate. A launch-observation failure prevents execution. A
terminal-write failure leaves the start visible, marks the attempt
`observation_incomplete`, and grants no contribution credit.

This evidence trusts the local controller, its selected executable and its
storage, within the same cooperative single-user boundary as the board. It
does not authenticate a provider or protect against a hostile process running
as the same user. Host names describe the selected adapter; requested model
labels are separate from native observations.

Read the selected repository's retained observations against current
canonical acceptance:

```sh
scripts/shadow-python.sh scripts/dev/shadow-efficiency-acceptance.py \
  --observed-repo /path/to/worktree
```

Repeat `--observed-repo` for up to 16 worktrees. Each stream is bounded to
4 MiB and 4,096 records; receipt discovery stays within that worktree's
evidence directory and refuses more than 256 JSON files. The read checks the
board, plan and stream again before returning, so concurrent movement requires
a new read. Exact duplicate records count once. Conflicting identities,
missing terminals, modified receipts, copied worktree evidence, partial logs
and reopened acceptances cannot retain successful contribution credit.
Malformed records make attribution and usage totals unavailable for the
selected report, rather than silently dropping data.

One root means one entity/checkpoint pair. Retries and failures remain visible
in the attempt denominator. An observed committed candidate earns credit only
when its repository and final source head exactly match that root's current
command acceptance. A review-only attempt, an uncommitted change, or a later
lead-modified head does not establish that code contribution. The legacy
`--attempt FILE` mode still compares supplied receipts without ever granting
actor credit or joining usage.

### Native usage and interpretation

Usage comes only from top-level structured stdout of the launched CLI. The
parser never recursively extracts usage from model or tool text. It reads
complete JSONL records as stdout arrives, discards message payloads and session
IDs, and retains only the transport metadata needed by the usage parser. This
allows the diagnostic stdout tail to truncate without discarding usage.
The in-memory reader permits at most 1 MiB per line, 32 MiB per stream, 10,000
nonempty records, and 64 KiB of selected metadata. Incomplete processes or
streams, malformed or duplicate-key records, and exceeded bounds leave usage
unknown; zero is not a substitute. Earlier attempts with truncated captures
are not retroactively repaired by this reader.

- Codex and codex-zai require one ordered thread/start/completed-turn sequence.
  The counters cover the native parent turn. Cached input and reasoning output
  are optional; absent fields remain null. Model and provider identities,
  child usage and monetary cost remain unknown.
- Claude Code requires one successful result with valid `modelUsage` and
  `total_cost_usd`. The model-usage totals cover the native whole tree,
  including helpers; the separate parent `usage` field is not substituted.
  The cost is a native estimate, not billed subscription spend. Native model
  labels do not establish which provider served the request.
- Other adapters retain unknown usage until their transport has its own
  verified parser. A parser fixture alone does not prove a live host works.

The report separates resource totals by work class and usage scope and shows
known-usage and known-cost coverage. It excludes unobserved work, including
this caller's lead/review work. Therefore overall worker share, cost per
accepted task and attention per accepted task remain null. Allocation counts
alone do not establish benefit: a comparable direct/delegated sample with the
same starting source, independent acceptance and complete effort coverage is
required. Routing remains unchanged. No daemon, sink forwarding, scheduler or
second task store is introduced by this read path.

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

## Huddle lifecycle observation

An owner can opt into one local, disposable Huddle lifecycle check with:

```sh
scripts/shadow-python.sh scripts/dev/shadow-observed-gauntlet.py --jobs huddle-lifecycle
```

This selection is deliberately not part of the observed gauntlet's default
job list, so existing generic and v3 invocations retain their current
contract. It cannot be mixed with generic jobs and requires at least one
round. It requires the three sink values above plus a loopback, credential-
free OTLP HTTP endpoint and a loopback
`SHADOW_LANGFUSE_READBACK_URL` and a safely shaped
`SHADOW_LANGFUSE_PROJECT_ID`; it refuses before the lifecycle or network work
begins if those predicates are absent. It also refuses
`SHADOW_LANGFUSE_EVENTS`: forwarded generic events are not Huddle evidence.

The job builds and discards a real local Git repository and board. It opens a
two-claim shared-scope Huddle, records the selected `own` and held
`stand_down` bids, settles it, proves the held host write is refused without a
durable change, returns the held plan as blocked with a Deferred wake, and
returns the remaining disposable claim. The five emitted `huddle.lifecycle`
spans have only these attributes: `shadow.huddle_id`,
`shadow.huddle_generation`, `shadow.lifecycle_step`, `shadow.huddle_state`,
`shadow.opened_revision`, `shadow.settled_revision`, and
`shadow.compliance_revision`. Their closed steps are `hold_observed`,
`bids_recorded`, `settled`, `held_write_refused`, and
`compliance_satisfied`.

Green means the exact five JSONEachRow rows were read back from the named
local ClickHouse project and trace; accepted OTLP alone remains red. This is
source-only owner-tool proof, not a claim that a host is installed, that a
service is live, or that any customer-facing runtime used the result. A later
owner can reproduce it without this chat by setting the documented local
variables and running the command above; use the local sink's own health and
deployment receipts for those separate claims.

## Scheduled owner loop

The sinks earn their keep on a schedule, not by hand. The owner-machine loop
(launchd, systemd timer, or cron — the entry itself lives outside the
repository like the compose file) keeps five properties:

- **One lock, one log, one status file.** A second firing exits immediately;
  the status file is the only read surface, so a missed night is a visible
  state, never silence.
- **Fast-forward-only checkout.** The loop fetches and merges `origin/main`
  with `--ff-only` and fails loudly on a dirty or diverged checkout rather
  than reporting results from a stale tree.
- **A pinned interpreter.** Scheduler environments resolve `python3`
  differently than a login shell; the loop pins its interpreter (or
  `SHADOW_PYTHON`) instead of trusting `PATH`.
- **A sane PATH for the whole subtree.** The pin covers the top-level call,
  but test jobs spawn grandchildren that resolve `python3` from `PATH` by
  design (the two-seat harness seals its seat environment and strips
  `SHADOW_PYTHON`). A scheduler's bare PATH finds only the system python, so
  scheduler-fired runs need a modern directory prepended — otherwise seats
  never boot and the suite mass-fails in seconds.
- **Health probes before the long run.** Sink host and readback endpoints are
  curled first; a squatted port or a booting stack fails the run in seconds
  with an exact status, instead of turning a full gauntlet into a guaranteed
  red discovered an hour later. Scheduler output is unbuffered so a
  mid-flight run is observable in the log.

The baseline schedule is nightly. On top of it, the documented pressure
trigger — `shadow-ci`'s `PRESSURE_WINDOW` probe — fires an early run when the
repo's own accepted-change pressure crosses the checked-in threshold. The
probe keeps the same five properties and adds one of its own: **a recency
gate**, skipping honestly when the last completed run is fresher than the
probe window, so a high-pressure stretch costs a bounded number of runs
instead of every firing. Its decision (run or skip, with the reason) lands in
the same log; a skipped probe is visible, never silent.
