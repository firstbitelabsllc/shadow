# Source change requests — 2026-09-01 (lane liveness, churn signal)

Written, not implemented. Each item states the failure, the evidence, and the
smallest remedy the owning seat should consider. Host- and model-agnostic:
the evidence patterns below come from heavy multi-week use of agent lanes
coordinated through a Shadow board, but nothing here depends on any one host,
model, or vendor.

## 1. A claim can die silently and look parked (lane liveness)

**Failure.** A claimed checkpoint whose worker dies outside Shadow's view
(spend cap, provider rejection, crashed process) keeps its claimed state
indefinitely. Nothing distinguishes "worker is mid-flight" from "worker has
been dead for hours"; seats resume past the row assuming it is occupied.

**Evidence pattern.** In one 3-week window, lanes died silently when an
external spend cap tripped: the harness recorded the deaths as ordinary
completions with null output, and the board still showed the claims as
active. Discovery happened by accident, hours later.

**Smallest remedy.** Give claims an optional liveness cadence at throw time
(`shadow throw --heartbeat <interval>` or an entity-level default). A claim
with no board-visible receipt (progress line, status flip, or explicit
`shadow ping`) inside its cadence surfaces in `shadow status` as
`stale/presumed-dead` — advisory, not auto-returned. Probing a stale claim
stays one exact command, matching the existing "a mid-flight reading is not
a death certificate" rule: the signal prompts a proof probe, never a silent
reclaim.

## 2. A claim can burn without moving (churn signal)

**Failure.** A claimed checkpoint can accumulate large amounts of activity —
dozens of context compactions, thousands of tool calls — while making no
checkpoint movement, and the board has no way to distinguish that from
productive work. The cost is real (one observed lane: 25 hours wall-clock,
29 compactions, ~350M cumulative tokens, repeatedly re-deriving decisions it
had already made).

**Evidence pattern.** Multi-week transcript review: the dominant waste mode
was not failure but churn — long lanes re-litigating settled decisions after
each compaction, and poll loops repeating identical calls dozens of times
with no new information.

**Smallest remedy.** An advisory churn heuristic in `shadow lint` or
`shadow status`: flag a claim whose receipts show high activity markers
(e.g., many progress lines, or a configurable age threshold) with no
milestone/checkpoint flip since the last flag. The remedy is a nudge to
re-scope or split the checkpoint — output only, no automatic state change.
Both remedies keep Shadow's rule that probes are explicit and state changes
are claimed by seats, never inferred by the tool.
