# Vidux Cockpit Benchmark v4

Status: draft integrity preflight, non-runnable. Deterministic schedule and
authenticated-result checks exist; provider transport, adjudication, and
decision commands do not.

Protocol ID: `vidux-cockpit-v4`

## Why V4 Exists

V3 proved useful provider-matching, schedule, budget, no-exclusion, and
deterministic-decision mechanics, but its evidence boundary was not strong
enough for a product claim. Digest-shaped strings were accepted without
resolving their bytes, synthetic evaluator rows could reach a claim-eligible
decision, retry usage was omitted from decision statistics, and a crash-torn
journal could not recover. Those are outcome-determining rules, so v3 was
retired instead of amended.

## Integrity Boundary

Every public fixture is schema-validated JSON. Its stage, scenario class, and
fixture ID must match the release entry; its task prompt is bounded and
non-empty; its workspace snapshot resolves to content-addressed bytes; and its
execution contract names required state transitions, proof requirements, and a
scenario-specific interruption contract.

Provider profiles, evaluator registration, evaluator implementation, public
key, signature, workspace, and future runtime receipts resolve through a
single-link, non-symlink artifact store. A digest is never evidence by itself.

## Evaluator Authentication

An evaluator registration is committed before fixture release. The
registration binds an evaluator ID, Ed25519 OpenSSH public key, evaluator
implementation bytes, and the `vidux-benchmark-v4` signature namespace. The
release receipt binds the exact canonical release core and verifies through
OpenSSH `sshsig`. Evaluator result receipts bind canonical result bytes to the
same preregistered identity, exact schedule, exact runner result, evaluator run,
and resolved check evidence.

Synthetic bundles remain useful harness tests but are permanently ineligible
for product claims. Only a real bundle with an already registered evaluator and
resolved authenticated artifacts may become eligible after a separately
reviewed status transition and runner implementation.

## Recovery And Measurement

Only an unterminated final journal fragment may be recovered. Under an
exclusive sidecar lock, all preceding newline-terminated records must first
pass sequence and hash-chain validation. Recovery atomically replaces the
journal with the committed prefix plus a content-addressed recovery event.
Malformed or hash-invalid terminated records remain fatal. Ambiguous provider
dispatch is reserved under the journal lock before any future provider call.
The reservation binds a schedule-derived run, attempt, and dispatch ID. A
reservation without a receipt is an explicit reconciliation-required state and
cannot be reserved or invoked again. Reconciled receipt metrics are cumulative.

Every attempt, including infrastructure retries, contributes to both budget
accounting and decision statistics. Vidux activation overhead remains included.

## Preserved Experiment Design

V4 embeds v3's exact provider pairs, four arms, scenario classes, budgets,
schedule, measurement, adjudication, exclusion, decision procedure, and
thresholds. Tests compare those blocks field-for-field with the retired frozen
manifest. V4 changes only the evidence and recovery integrity layer; any actual
outcome-rule change requires v5.

## Current Boundary

The current code validates this manifest, exact fixture and artifact schemas,
authenticated release bundles, deterministic 208-run schedules, signed
evaluator results, dispatch reservation/reconciliation, and crash-tail
recovery. Administrative status is still non-runnable and has no registered
external evaluator. No provider transport, pilot result, adjudication,
decision, or verified net-win class exists.
