# Source change requests — 2026-09-01 (claim liveness, churn signal)

Written, not implemented. Each item states the failure, the evidence, and the
smallest remedy the owning seat should consider. Host- and model-agnostic: the
patterns below come from heavy multi-week use of agent lanes coordinated
through a Shadow board, but nothing here depends on one host, model, or vendor.

Both items were narrowed after review against current source. The first
originally claimed a dead claim is indistinguishable from active work, which is
false: claims already carry an eight-hour `return_by`, `claim_is_stale()`
derives expiry at read time, and `shadow status --in-flight` already prints
`STALE — probe proof, then adopt, park, or close`. The second originally asked
for a churn heuristic over activity markers the board does not store.

## 1. The stale bit exists but the ordinary seat view does not show it

**Failure.** `shadow status --by <seat>` renders a seat's own claims and their
`Continue:` line without any staleness marker, while `--in-flight` renders the
same claims with `STALE` and its recovery. A seat that reads its ordinary view
sees an expired claim as ongoing work.

**Evidence pattern.** Three claims owned by one seat sat expired for three days
and were only noticed through the in-flight view. Nothing was broken: the data
was correct and the ordinary view simply did not carry it.

**Smallest remedy.** Render the existing stale bit and its existing recovery
text in the seat view before the `Continue:` line, and sort stale owned claims
first. No new predicate, no new wording, no new command. This is one renderer
change over shipped state.

**Related, separate ask.** The eight-hour lease is fixed. A long-running lane
and a five-minute lane want different cadences, so an optional per-throw or
per-entity cadence would make the existing stale bit meaningful sooner. That is
a real gap, unlike the detection itself, and it stays advisory: a stale claim is
surfaced, never auto-returned, because a mid-flight reading is not a death
certificate.

## 2. A churn signal needs an observable it does not have

**Failure.** A claimed checkpoint can accumulate very large amounts of activity
while making no checkpoint movement, and the board cannot distinguish that from
productive work.

**Evidence pattern.** In one observed lane: twenty-five hours of wall clock,
twenty-nine context compactions, and repeated re-derivation of decisions the
plan had already recorded. The dominant waste mode across the window was churn
rather than failure.

**Why this is not yet a request.** The board stores only claim identity, owner,
and lease. Progress lines are durable plan evidence, not runtime telemetry, so
nothing on the board counts tool calls or compactions. An age threshold would
flag a churning lane and a legitimately long lane identically, which is not the
promised distinction.

**What would make it one.** Either an observable host-side activity signal a
seat reports voluntarily, or a narrower ask: flag a claim whose plan has gained
no new receipt since its last flag, which is plan-observable today and is
honestly age-based staleness rather than churn detection.

**Meanwhile, the cheaper fix is upstream of the tool.** Re-deriving settled
decisions after a context reset is addressed by the resume packet already
carrying the plan's latest LESSON and DECISION lines, and by a law that tells a
resumed seat to read them first.
