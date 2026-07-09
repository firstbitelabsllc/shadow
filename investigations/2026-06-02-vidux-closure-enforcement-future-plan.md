# Vidux Closure Enforcement Plan Bank Audit

## Purpose

Turn the 94-plan retrospective plus a local plan-bank scan into a small
enforcement plan: measure closure drift first, then tighten the parts of Vidux
that let plans look complete before they are mechanically closed.

## Thesis

Vidux has a closure and enforcement problem, not a knowledge problem. Recurring
failures: soft gates, fake-complete `[completed]` flips, blocker loops, crons
with no retirement criteria, and doctrine that accretes faster than it is pruned.

## Common Issues

1. Closure is not terminal. Plans can end with pending, blocked, or unchecked
   rows (especially in archived lanes) without a required verdict.
2. Proof gates are descriptive more often than structural. A row can say
   completed while gate checkboxes remain unchecked or evidence is missing.
3. Blockers have no clock. `[blocked]` rows rarely say when the blocker started,
   so stale human/provider-gated work keeps attracting fresh cycles.
4. Plan shape is inconsistent. Missing Evidence, Constraints, Progress, Drift
   Log, and Closeout sections make fleet-level status hard to compare.
5. Artifacts decay. `/tmp/` references in durable plans make proof disappear
   even when the plan row survives.
6. Research and doctrine can become deliverables by themselves. Plenty of
   analysis, fewer executable stop conditions and smoke loops.

## Improvement Plan

1. Ship `scripts/vidux-plan-bank-audit.py`.
   - Read-only by default; scans repo roots for `PLAN.md`; emits human/JSON.
   - `--watch-iterations` / `--watch-interval-seconds` for multi-hour smoke runs.
   - `--fail-on` for later gated use, but defaults to no failure.

2. Use the audit to define closure tiers.
   - Critical: archived plan has non-terminal rows.
   - High: blocked row lacks `blocked_since`, gate checkbox unchecked, or
     required Evidence/Progress missing.
   - Medium: missing Constraints, Decision Log, Drift Log, Closeout, or durable
     proof references `/tmp/`.

3. Connect single-lane closeout to bank-level signals.
   - Keep `scripts/vidux-lane-closeout.py` as the lane closer.
   - Run plan-bank audit before closeout to catch missing sections, stale
     blockers, unchecked gates, and decaying proof paths.

4. Add blocker-age discipline after the signal is calibrated.
   - New blocked rows carry `blocked_since=YYYY-MM-DD`.
   - Old blockers route to owner decision, deferral, cancellation, or a new
     non-hot adjacent task.

5. Add doctrine garbage collection after the bank has a baseline.
   - Plans/docs that only restate policy without runnable proof get marked for
     consolidation.
   - Archived lanes must be terminal or explicitly marked historical
     non-terminal debt.

## Pre-Mortem Guardrails

- Audit flags too much → default observe-only; show top issue codes; `--fail-on`
  only after a lane opts in.
- Blocker-age enforcement becomes a nag → record `blocked_since` and recommend
  routing, but do not auto-close human-gated work.
- Vidux keeps improving Vidux → dogfood the audit on real repos as a read-only
  smoke, then choose non-hot plan maintenance over hot-path churn.

## Multi-Hour Smoke Plan

Run observe-only across real projects first, single iteration, then the watch run:

```bash
python3 scripts/vidux-plan-bank-audit.py \
  ~/Development/vidux \
  ~/Development/strongyes-web \
  ~/Development/resplit-web \
  ~/Development/resplit-ios \
  --watch-iterations 9 \
  --watch-interval-seconds 900 \
  --issue-limit 0 \
  --output-jsonl evidence/2026-06-02-plan-bank-audit-smoke.jsonl
```

Smoke invariants:

- No writes to StrongYes web, Resplit web, or Resplit iOS. The only allowed
  write is the Vidux-owned JSONL passed with `--output-jsonl`.
- No stage, commit, push, PR, external board mutation, browser auth flow,
  local-CI execute, TestFlight, or App Attest work.
- Record each iteration's totals (plan count, severity counts, top issue codes,
  runtime, false-positive notes). Use `--output-jsonl` so snapshots survive
  session interruption.
- Non-hot follow-up only: plan-shape cleanup, archived-lane terminal verdicts,
  durable proof relocation from `/tmp/`, stale blocker triage.
- Stop if an iteration exceeds 5 minutes, traverses dependency/cache trees, or
  flags a hot-path lane where enforcing would block active release work.

## Long-Run Artifact Contract

One JSON envelope per iteration:

- `iteration`: 1-based index.
- `snapshot.audit_at`: UTC scan timestamp.
- `snapshot.duration_seconds`: elapsed scan time.
- `snapshot.plans_total`, `archived_plans`, `status_counts`, `severity_counts`,
  `issue_code_counts`: trend fields.
- `snapshot.issues`: ordered issue rows. Treat as leads, not enforcement facts,
  until one row from each top issue code is manually spot-checked.

Summarize after the run:

```bash
python3 scripts/vidux-plan-bank-audit.py \
  --summarize-jsonl evidence/2026-06-02-plan-bank-audit-smoke.jsonl
```

## Lesson: agent-mirror over-count (corrected)

First long smoke mixed repo-owned plans with agent-substrate plans under
`.claude/worktrees` and `.agents/skills/vidux` (460 of 574 product-root
`PLAN.md` files were under `.claude/`, 2 under `.agents/`). Fix: the audit now
skips `.claude`, `.agents`, and `.codex` mirrors by default and exposes
`--include-agent-mirrors` for deliberate substrate audits. Use corrected smoke
numbers (not the original over-counted artifact) for real trend decisions.

A second false positive was fixed: bracketed Progress / Decision Log bullets
(`[2026-06-02]`, `[Direction]`) are not checkbox-FSM statuses; the scanner now
only counts known plan statuses.

## Final Corrected Long Smoke

Corrected observe-only long smoke completed 9/9 rows
`2026-06-02T22:42:15Z` → `2026-06-03T00:42:39Z`. Summary
`evidence/2026-06-02-plan-bank-audit-smoke-summary.md`, raw JSONL
`evidence/2026-06-02-plan-bank-audit-smoke-corrected.jsonl`.

- Plans: `202 -> 202`, delta `0`.
- Severities: critical `141`, high `333`, medium `874`, low `0`; all deltas `0`.
- Runtime per iteration: min `2.838s`, max `3.491s`.
- Root split: Vidux `90`, StrongYes web `77`, Resplit web `31`, Resplit iOS `4`.
- Product status fingerprints unchanged for the three product repos, so the run
  stayed observe-only.

Non-hot follow-up: archived plan terminal-state cleanup, durable-proof path
relocation away from `/tmp`, StrongYes content-lane plan-shape normalization,
`blocked_since` metadata on old blocked rows. Avoid app runtime code, local-CI
execute, TestFlight/App Attest, AASA, GitHub PR mutation, external boards, and
StrongYes launch mutation.

## Non-Claims

- Does not mark any StrongYes, Resplit web, Resplit iOS, or local-CI lane complete.
- Does not mutate project plans outside Vidux.
- Does not enforce closure in CI yet.
- Does not solve the existing Resplit `gh pr create` overlap blocker.
