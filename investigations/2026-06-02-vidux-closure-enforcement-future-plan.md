# Vidux Closure Enforcement Plan Bank Audit

## Purpose

Turn the pasted 94-plan retrospective plus a fresh local plan-bank scan into a
small enforcement plan: measure closure drift first, then tighten the parts of
Vidux that let plans look complete before they are mechanically closed.

## Inputs

- User retrospective: Vidux has a closure and enforcement problem, not a
  knowledge problem. The recurring failures are soft gates, fake-complete
  `[completed]` flips, blocker loops, crons with no retirement criteria, and
  doctrine that accretes faster than it is pruned.
- Fresh local scan on 2026-06-02: 94 `PLAN.md` files found. The pasted
  "0 Drift Logs" baseline is now stale: 2 plans have `## Drift Log`; the
  broader closure gap still holds.
- Fresh local scan on 2026-06-02: non-fixture plans have `Progress` in 79/90,
  `Decision Log` in 75/90, `Evidence` in 58/90, `Constraints` in 62/90,
  `Drift Log` in 2/90, `Closeout` in 2/90, and `Terminal Verdict` in 0/90.
- Fresh local scan on 2026-06-02: non-fixture status rows include 1047
  completed, 550 pending, 23 in_progress, 81 blocked, 79 unchecked, and 72 x
  rows. `blocked_since` markers were not found.
- Fresh local scan on 2026-06-02: 69 gate checkboxes were found, 53 unchecked.
  Durable plan text contains 43 `/tmp/` proof references.

## Common Issues

1. Closure is not terminal. Plans can end with pending, blocked, or unchecked
   rows, especially in archived lanes, without a required verdict.
2. Proof gates are descriptive more often than structural. A row can say
   completed while gate checkboxes remain unchecked or evidence sections are
   missing.
3. Blockers have no clock. `[blocked]` rows rarely say when the blocker started,
   so stale human-gated or provider-gated work keeps attracting fresh cycles.
4. Plan shape is inconsistent. Missing Evidence, Constraints, Progress, Drift
   Log, and Closeout sections make fleet-level status hard to compare.
5. Artifacts decay. `/tmp/` references in durable plans make proof disappear
   even when the plan row survives.
6. Research and doctrine can become deliverables by themselves. The plan bank
   has plenty of analysis, but fewer executable stop conditions and smoke loops.

## Future Pre-Mortem

The plan-bank audit can fail in three ways if we treat it as another document
instead of a product surface.

Technical blind spot: the audit flags too much and agents learn to ignore it.
Guardrail: default observe-only, show top issue codes, and use `--fail-on`
only after a lane opts into the signal.

People/system blind spot: blocker-age enforcement becomes a nag instead of a
decision aid. Guardrail: record `blocked_since` and recommend routing, but do
not auto-close human-gated work.

Self blind spot: Vidux keeps improving Vidux while StrongYes and Resplit hot
paths need attention. Guardrail: dogfood the audit on real repos as a read-only
smoke, then choose non-hot plan maintenance or documentation cleanup work.

Five questions we were not asking enough:

1. Which completed rows still have unchecked gates nearby?
2. Which blocked rows are old enough that another cycle is probably waste?
3. Which archived plans are not actually terminal?
4. Which proof links will disappear because they live under `/tmp/`?
5. Which docs or plans describe process improvement but do not ship a runnable
   guard, script, test, or smoke artifact?

## Improvement Plan

1. Ship `scripts/vidux-plan-bank-audit.py`.
   - Read-only by default.
   - Scans one or more real repo roots for `PLAN.md`.
   - Emits human or JSON summaries.
   - Supports `--watch-iterations` and `--watch-interval-seconds` for multi-hour
     smoke runs.
   - Supports `--fail-on` for later gated use, but defaults to no failure.

2. Use the audit to define closure tiers.
   - Critical: archived plan has non-terminal rows.
   - High: blocked row lacks `blocked_since`, gate checkbox is unchecked, or
     required Evidence/Progress is missing.
   - Medium: missing Constraints, Decision Log, Drift Log, Closeout, or durable
     proof references `/tmp/`.

3. Connect single-lane closeout to bank-level signals.
   - Keep `scripts/vidux-lane-closeout.py` as the lane closer.
   - Use plan-bank audit before closeout to catch missing sections, stale
     blockers, unchecked gates, and decaying proof paths.

4. Add blocker-age discipline after the signal is calibrated.
   - New blocked rows should carry `blocked_since=YYYY-MM-DD`.
   - Old blockers should route to owner decision, deferral, cancellation, or a
     new non-hot adjacent task.

5. Add doctrine garbage collection after the bank has a baseline.
   - Plans and docs that only restate policy without runnable proof get marked
     for consolidation.
   - Existing historical plans remain evidence, but archived lanes must be
     terminal or explicitly marked as historical non-terminal debt.

## Multi-Hour Smoke Plan

Run the audit in observe-only mode across real projects first:

```bash
python3 scripts/vidux-plan-bank-audit.py \
  /Users/leokwan/Development/vidux \
  /Users/leokwan/Development/strongyes-web \
  /Users/leokwan/Development/resplit-web \
  /Users/leokwan/Development/resplit-ios \
  --watch-iterations 9 \
  --watch-interval-seconds 900 \
  --issue-limit 0 \
  --output-jsonl evidence/2026-06-02-plan-bank-audit-smoke.jsonl
```

Smoke invariants:

- No writes to StrongYes web, Resplit web, or Resplit iOS. The only allowed
  write is the explicit Vidux-owned JSONL output file passed with
  `--output-jsonl`.
- No stage, commit, push, PR, external board mutation, browser auth flow, local-CI
  execute, TestFlight, or App Attest work.
- Record each iteration's totals: plan count, severity counts, top issue codes,
  runtime, and any false positive notes. Use `--output-jsonl` so the raw
  iteration snapshots survive terminal/session interruption.
- Use non-hot follow-up work only: plan-shape cleanup, archived-lane terminal
  verdicts, durable proof relocation from `/tmp/`, and stale blocker triage.
- Stop if the audit takes longer than 5 minutes per iteration, traverses obvious
  dependency/cache trees, or flags a hot-path lane where enforcing the signal
  would block active release work.

Initial real-project smoke should run one single iteration first. Only after
that passes should the multi-hour watch run.

## Initial Smoke Results

Single-root Vidux observe-only scan, corrected parser:

- Command: `python3 scripts/vidux-plan-bank-audit.py . --issue-limit 8`
- Result at 2026-06-02T22:15:30Z: 90 plans, 22 archived, 87 critical issues,
  179 high issues, 465 medium issues.
- Status counts: completed=1119, pending=550, blocked=81, unchecked=79, done=73,
  in_progress=24.
- Top issue codes: temporary_proof_path=190,
  missing_terminal_closeout_section=90, missing_drift_log_section=88,
  archived_non_terminal_row=87, blocked_without_since=81,
  unchecked_gate_checkbox=53.

Real-project observe-only scan:

- Command: `python3 scripts/vidux-plan-bank-audit.py /Users/leokwan/Development/vidux /Users/leokwan/Development/strongyes-web /Users/leokwan/Development/resplit-web /Users/leokwan/Development/resplit-ios --issue-limit 6`
- Result at 2026-06-02T22:16:05Z: 664 plans, 49 archived, 141 critical issues,
  1077 high issues, 2763 medium issues.
- Status counts: completed=7529, pending=2078, unchecked=1331,
  in_progress=359, blocked=306, done=73.
- Top issue codes: missing_terminal_closeout_section=664,
  missing_drift_log_section=662, missing_evidence_section=320,
  temporary_proof_path=311, blocked_without_since=306,
  missing_tasks_section=291, missing_constraints_section=289,
  missing_decision_log_section=284, missing_progress_section=279,
  missing_purpose_section=262, unchecked_gate_checkbox=172,
  archived_non_terminal_row=141.

Observed false positive fixed during this slice: bracketed Progress and Decision
Log bullets such as `[2026-06-02]` or `[Direction]` are not checkbox-FSM task
statuses. The scanner now only counts known plan statuses.

## Long-Run Artifact Contract

The multi-hour smoke writes one JSON envelope per iteration:

- `iteration`: 1-based iteration index.
- `snapshot.audit_at`: UTC timestamp for the scan.
- `snapshot.duration_seconds`: elapsed scan time for that iteration.
- `snapshot.plans_total`, `snapshot.archived_plans`, `snapshot.status_counts`,
  `snapshot.severity_counts`, and `snapshot.issue_code_counts`: trend fields.
- `snapshot.issues`: ordered issue rows for spot-checking. Treat these as leads,
  not enforcement facts, until at least one row from each top issue code is
  manually spot-checked.

Summarize the run after it finishes:

```bash
python3 scripts/vidux-plan-bank-audit.py \
  --summarize-jsonl evidence/2026-06-02-plan-bank-audit-smoke.jsonl
```

## Long-Run Finding

The first two iterations of the initial long smoke were stable, but the sample
issues exposed a category problem: the scanner was mixing repo-owned plans with
agent substrate plans under `.claude/worktrees` and `.agents/skills/vidux`.

Receipt:

- `find /Users/leokwan/Development/strongyes-web /Users/leokwan/Development/resplit-web /Users/leokwan/Development/resplit-ios -path '*/PLAN.md'` found 574 product-root `PLAN.md` files.
- 460 of those were under `.claude/`, and 2 were under `.agents/`.
- Sample top-code hits included `strongyes-web/.claude/worktrees/.../PLAN.md`
  and `resplit-ios/.agents/skills/vidux/PLAN.md`, while real archived plan debt
  also appeared under `resplit-web/_archive/vidux/mega-plan/PLAN.md`.

Core response: the audit now skips `.claude`, `.agents`, and `.codex` plan
mirrors by default and exposes `--include-agent-mirrors` for deliberate substrate
audits. The original long-smoke artifact remains useful as evidence that the
first tool version over-counted agent mirrors; the corrected smoke should be
used for real project-plan trend decisions.

## Final Corrected Long Smoke

The corrected observe-only long smoke completed 9/9 rows from
`2026-06-02T22:42:15Z` to `2026-06-03T00:42:39Z`; full summary is
`evidence/2026-06-02-plan-bank-audit-smoke-summary.md` and raw JSONL is
`evidence/2026-06-02-plan-bank-audit-smoke-corrected.jsonl`.

Final-row facts:

- Plans: `202 -> 202`, delta `0`.
- Severities: critical `141`, high `333`, medium `874`, low `0`; all deltas
  `0`.
- Runtime per iteration: min `2.838s`, max `3.491s`.
- Root split: Vidux `90` plans, StrongYes web `77`, Resplit web `31`, Resplit
  iOS `4`.
- Product repo status fingerprints were unchanged for StrongYes web, Resplit
  web, and Resplit iOS, so the run stayed observe-only.

Non-hot follow-up should start with archived plan terminal-state cleanup,
durable-proof path relocation away from `/tmp`, StrongYes content-lane
plan-shape normalization, and `blocked_since` metadata on old blocked rows.
Avoid app runtime code, local-CI execute, TestFlight/App Attest, AASA, GitHub
PR mutation, external boards, and StrongYes launch mutation.

## Non-Claims

- This does not mark any StrongYes, Resplit web, Resplit iOS, or local-CI lane
  complete.
- This does not mutate project plans outside Vidux.
- This does not enforce closure in CI yet.
- This does not solve the existing Resplit `gh pr create` overlap blocker.
