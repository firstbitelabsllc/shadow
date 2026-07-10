# Vidux Cockpit Benchmark v2

Status: protocol rules frozen; fixture and hidden-oracle seal still pending.

This benchmark asks a narrow product question: does Vidux's derived
plan/proof/decision/resume cockpit create a net-positive outcome compared with
using native Claude or Codex directly? It does not retest the retired
planner-executor kernel.

## Fair Arms

All arms receive the same fixture workspace and the same tool-permission
profile. Native Claude and Codex retain ordinary filesystem access; they are
not handicapped by hiding `PLAN.md`, evidence, or source files. The Vidux arm
has that same access plus one read-only cockpit packet derived from the same
fixture state. No arm may inspect a hidden oracle.

## Scenario Classes

- `durable_state`: recover the correct next move from persistent project state.
- `interruption_recovery`: resume after a bounded interruption without repeating,
  discarding, or inventing work.
- `cross_project_prioritization`: select and justify the best next move across
  multiple active projects.
- `proof_inspection`: distinguish verified, missing, stale, and contradictory
  evidence before making a recommendation.

Each class needs at least 12 complete paired fixture blocks. A block has the
same scenario, fixture id, and replica across all three arms. Infrastructure
failures may be excluded only when they affect the full paired block under the
frozen rule in `manifest.json`.

## Measurement And Decision

Every completed run records hidden-oracle success, wall time, total provider
tokens and dollars, operator touches, and resume loss. The deterministic scorer
uses 5,000 paired-block bootstrap samples and percentile 95% confidence
intervals. Each raw row records the provider model, runtime version, and
provider, runner, and transcript receipt identifiers. This binds the outcome to
the real runtime rather than a hand-written summary.

Every provider token and dollar charge attributable to an arm counts, including
cockpit packet generation and routing overhead. Wall time runs from the
standardized launch to a terminal runner receipt. A human touch is a message,
approval, click, command, or recovery action after the standardized launch;
the launch itself is excluded for all arms. The sealed oracle measures resume
loss as missed, repeated, or invented required state transitions.

For each native comparison, the scorer uses mean paired success difference,
total tokens per resolved task ratio, total dollars per resolved task ratio,
median wall-time ratio, and mean paired deltas for operator touches and resume
loss. A class is a net-value win only when Vidux wins against both native
controls on the pre-registered success threshold without exceeding the
registered token, dollar, wall-time, operator-touch, or resume-loss guardrails.

No raw rows exist yet. This protocol therefore proves no product advantage and
must remain `unproven` until a sealed fixture release, raw paired rows, and a
decision receipt are available.

## Oracle Boundary

The actual oracle payloads live outside each arm workspace. Before transport,
an independent sealed fixture release must provide each class's SHA-256
commitment and reference this protocol digest. The validator refuses to emit a
run packet while any oracle is pending seal.
