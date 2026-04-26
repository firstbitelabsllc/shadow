# Configuration

Vidux reads repo-level defaults from `vidux.config.json`. The repo also ships `vidux.config.example.json` as a documented example with external inbox sync enabled.

## Primary file

The checked-in `vidux.config.json` currently includes these top-level areas:

- `version`
- `plan_store`
- `defaults`
- `guidelines`
- `external_plan_roots`
- `inbox_sources`
- `dashboard`
- `ledger`
- `pruning`
- `backpressure`

## `plan_store`

The README and config files describe three plan-store modes:

- `inline` - use `PLAN.md` in the current repo.
- `local` - use a configured local path, typically under `~/Development/vidux/projects`.
- `external` - use a configured path outside the repo root.

The repo's live config uses `local` mode with `~/Development/vidux/projects`.

## Example minimal config

This is the smallest documented shape from the README:

```json
{
  "plan_store": {
    "mode": "local",
    "path": "~/Development/vidux/projects"
  }
}
```

## Operational defaults

The live config uses several sections to guide scripts and automation behavior:

- `defaults` covers archive thresholds, context warnings, worktree limits, and system pressure limits.
- `guidelines` stores advisory values such as `cron_interval_minutes` and `max_parallel_agents`.
- `pruning` covers stale blocked-task age, worktree age thresholds, and plan size warnings.
- `backpressure` defines warning and critical thresholds for bimodal pressure plus circuit-breaker windows.
- `dashboard` and `ledger` configure dashboard refresh behavior and shared ledger discovery.

## External inbox sync

`vidux.config.example.json` demonstrates how external inbox sync is represented:

- `external_plan_roots` lists additional plan roots.
- `inbox_sources` enables adapters such as `gh_projects`.
- Adapter config can map task states, evidence fields, and auto-promotion targets.

The live `vidux.config.json` also includes a disabled `linear` adapter entry with an inline comment explaining why it is turned off.

## Where config is used

- `/vidux` reads the plan-store settings during startup.
- `vidux-loop.sh` reads defaults such as archive thresholds and context warning lines.
- `resolve-plan-store.sh` resolves the active plan root for scripts.
- `vidux-inbox-sync.py` reads enabled adapters and their state mappings.

## Related references

- Read [Commands](/reference/commands) for the prompt-layer startup flow that consumes this file.
- Read [Scripts](/reference/scripts) for the executables that read config defaults directly.
