# API To CLI Pivot

## Scenario
A plan asks for an HTTP API before identifying the actual caller. During implementation the caller turns out to be a local script, so the correct first slice is a CLI helper.

## Command
Run `vidux drift` with `--prevention`, `--cache`, and `--telemetry` to block the stale API row, append CLI follow-up work, and store a reusable hint.

## Expected Files
- `PLAN.md` gains `## Drift Log`.
- `drift-cache.jsonl` receives one cache row.
- `signposts.jsonl` receives one `drift.record` event.

## Pass Condition
A later `vidux drift suggest PLAN.md --cache drift-cache.jsonl` returns the caller/transport prevention hint.
