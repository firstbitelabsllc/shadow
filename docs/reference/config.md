# Configuration

Vidux reads local defaults from `vidux.config.json` when one exists. That file
is intentionally gitignored so each operator can keep machine-specific paths,
tokens, and adapter choices out of shared source.

The durable checked-in shape is `vidux.config.example.json`. When no live
config exists, `vidux config check` and the doctor use the example as a
validation fallback.

## Primary files

- `vidux.config.json` - local live config, ignored by git.
- `vidux.config.example.json` - checked-in example and schema-like reference.

The example currently includes these top-level areas:

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

## CLI checks

Use the shell CLI before changing config-dependent scripts:

```bash
vidux config path
vidux config check
vidux config show --json
vidux config init
```

`check --strict` fails when only the example file is available. That is useful
for machine-readiness gates where a real local config must exist. `show` is
redacted: it reports source, path, plan-store summary, expanded external root
paths, inbox-source counts, inbox-source config keys, and issues without dumping
adapter credentials.

The JSON report keeps compatibility fields such as `external_plan_roots`,
`inbox_sources_total`, and `inbox_sources_enabled`, then adds detail fields for
operator checks:

- `external_plan_roots_detail` expands each configured root relative to the
  config file and reports whether the path exists.
- `inbox_sources` reports each adapter, enabled state, config keys, redacted
  secret-key names, and token-file metadata.
- `token_file` metadata is path-only: Vidux expands the file path and reports
  existence, but marks it `redacted` and never reads or prints token contents.

## `plan_store`

The README and config files describe three plan-store modes:

- `inline` - use `PLAN.md` in the current repo.
- `local` - use a configured local path, typically under `~/Development/vidux/projects`.
- `external` - use a configured path outside the repo root.

The example config uses `local` mode with `~/Development/vidux/projects`.

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

The example config documents several sections that guide scripts and automation
behavior when copied into a live local config:

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
- `token_file` must be a non-empty string path. Relative paths resolve against
  the config file, `~` expands to the operator home directory, and suspicious
  inline `token` / `secret` / `password` values are reported as warnings.
- `auto_promote_max_new` caps direct PLAN.md appends per source. The default is
  25; use `null` only for a deliberate bulk import.
- Sources with `auto_promote_target` do not create new external items from
  local-only PLAN rows, but they still push status for tasks already linked by
  a `[Source: <adapter>:<id>]` marker.
- Adapter-specific intake, label, and project-guardrail policy belongs in the
  adapter docs or in a local overlay, not in core config reference prose.

A real repo may enable one or more shipped adapters and may add
`auto_promote_target` when external cards should land directly in a named plan
instead of `INBOX.md`. Treat the example file as one minimal shape, not as an
exhaustive mirror of every production config.

## Where config is used

- `/vidux` reads the plan-store settings during startup.
- `vidux config` resolves, validates, initializes, and redacts local config.
- `vidux doctor` runs `vidux config check --json` as part of local readiness.
- `vidux-loop.sh` reads defaults such as archive thresholds and context warning lines.
- `vidux-doctor.sh` reads runtime thresholds such as max worktrees, browser-process caps, Codex automation caps, and the minimum `memory_pressure -Q` free percentage. Runtime doctor JSON also includes source-specific `vm_stat` page counters so raw page-derived MB values are not mistaken for the same metric.
- `resolve-plan-store.sh` resolves the active plan root for scripts.
- `vidux-inbox-sync.py` reads enabled adapters and their state mappings.

## Related references

- Read [Commands](/reference/commands) for the prompt-layer startup flow that consumes this file.
- Read [Scripts](/reference/scripts) for the executables that read config defaults directly.
