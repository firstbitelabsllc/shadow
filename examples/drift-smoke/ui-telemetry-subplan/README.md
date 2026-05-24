# UI Telemetry Subplan

## Scenario
A plan bundles signpost capture, aggregation, and sidebar rendering into one row. Implementation evidence shows capture can land first, while rendering needs a child investigation.

## Command
Run `vidux drift` with `--subplan`, `--prevention`, `--cache`, and `--telemetry`.

## Expected Files
- Parent `PLAN.md` gains a `## Drift Log` entry with the subplan path.
- `investigations/telemetry-render.md` gets a mirrored drift entry.
- The telemetry log summarizes one successful `drift.record` event.

## Pass Condition
The parent and subplan agree on the same drift id, and `vidux signpost summary` reports the drift event.
