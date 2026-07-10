# Vidux Cockpit Benchmark v3

Status: retired and non-runnable. This document preserves the frozen design as
an inspectable negative artifact; `STATUS.json` is the administrative truth.

Protocol ID: `vidux-cockpit-v3`

## Question

Does activating the read-only Vidux cockpit improve outcomes enough to repay its
activation cost when the provider, model, runtime, permissions, base prompt,
tool surface, fixture, and hard budget are held constant?

This protocol compares two provider-matched pairs:

- direct-native Claude vs the same Claude profile with a read-only Vidux packet;
- direct-native Codex vs the same Codex profile with a read-only Vidux packet.

It does not compare different providers as if they were interchangeable. It
does not score plan aesthetics as task success. All Vidux activation work counts
against treatment tokens, dollars, and wall time.

## Frozen Scenarios

The four scenario classes are durable state, interruption recovery,
cross-project prioritization, and proof inspection. One evaluator release
freezes both stages before the pilot: exactly one pilot fixture and twelve
disjoint full fixtures per class. Every released fixture runs once through all
four arms. Pilot fixtures and bytes cannot reappear in the full stage.

The pilot is directional only. It cannot establish a product win, promote a
default, or change the scorecard's verified net-win count.

## External Evaluator Release

An evaluator who cannot see arm outcomes publishes a public release containing:

- the frozen protocol digest and explicit `pilot` or `full` stage per fixture;
- one exact provider profile for each matched pair;
- a 256-bit randomization seed;
- every public fixture path and SHA-256 digest;
- a content-addressed evaluator receipt.

The public release and arm packets contain no hidden-oracle path, bytes,
commitment, check identifiers, or adjudication hints. Hidden evaluator material
stays outside the arm workspace and is applied only after a runner terminates.

## Deterministic Schedule

The scheduler builds the complete stage-by-fixture-by-arm Cartesian product. It derives
opaque run IDs and ordering from SHA-256 over the release seed and canonical run
key. No Python PRNG state, clock, or filesystem ordering affects the schedule.
Validation regenerates the expected schedule byte-for-byte, so omitted,
duplicated, reordered, or reassigned runs fail closed.

Each run packet binds the protocol, release, schedule, public fixture, exact
provider profile, intervention mode, and hard budget. The native and Vidux arms
inside a pair differ only by the declared read-only Vidux intervention. Every
run receives a fresh copy of the frozen workspace snapshot.

## Hard Budgets

The manifest freezes per-run, per-stage, and whole-protocol elapsed-millisecond,
token, micro-USD, operator-touch, and infrastructure-attempt ceilings. Journal claims
reserve per-run ceilings before work starts. Completion receipts must remain
within both the per-run ceiling and global observed totals. A budget stop is a
scored result, not an infrastructure exclusion.

Provider spending remains impossible from this repository state because
`STATUS.json` keeps transport disabled. Enabling transport is a separate,
code-reviewed security slice and cannot amend these experimental rules.

## Durable Attempt Journal

Every schedule has one append-only JSONL journal. Events are hash-chained,
sequence-numbered, locked across processes, flushed, and fsynced. An
`operation_id` is idempotent: replaying the same intent returns the existing
event; reusing it for different content fails.

Attempt IDs are derived from the opaque run ID and monotonic attempt number, so
a recovered worker cannot reuse or invent an attempt identity. Allowed attempt
transitions are:

1. pending or retryable to claimed;
2. claimed to started;
3. started to runner-completed, runner-failed, budget-exhausted, or retryable;
4. runner-completed to adjudicated.

Only documented infrastructure failure may retry, and the frozen attempt limit
applies. Runner failure, budget exhaustion, and adjudication are terminal.
Provider transport remains disabled until a reviewed runner adds a persisted
dispatch reservation and receipt reconciliation; an ambiguous dispatch may
never be automatically re-invoked.

## Deterministic Adjudication

The public adjudicator consumes a content-addressed runner result and a
post-run evaluator result that names the exact runner-result digest. Success
equals one only when the runner completed, every required hidden check passed,
and no forbidden action occurred. Resume loss is exactly the sum of missed,
repeated, and invented required state transitions. The output binds both
inputs and contains no model-written score.

No run or paired block may be excluded after release, and fixtures may not be
replaced. Slow, expensive, over-planned, provider-failed, budget-exhausted,
infrastructure-exhausted, or unfavorable runs remain in the denominator with
zero success. An evaluator defect makes the protocol inconclusive and requires
a new protocol ID; it never opens a discretionary exclusion path.

## Decision Rule

Full-matrix decisions use the frozen paired SHA-256-index bootstrap procedure,
statistic formulas, undefined-ratio rule, confidence interval, and thresholds
in `manifest.json`. The output is an integer/rational, byte-deterministic
decision receipt. An observed zero denominator is a non-win; a zero-denominator
bootstrap draw is positive infinity and therefore remains in the upper-tail
interval. Each Vidux arm is compared only with its provider-matched
native control. A class can count
as a verified net win only after twelve complete matched pairs and the frozen
confidence, success, cost, token, wall, touch, and resume thresholds all pass.
At least three verified classes are required before Vidux may claim a broad net
win. A valid loss routes that class to direct-native by default.

## Current Boundary

No evaluator release, schedule, runner transport, raw row, pilot result, or net
win exists. V3 cannot issue any of them. Its integrity, cumulative-measurement,
and crash-recovery corrections require the new `vidux-cockpit-v4` protocol ID.
