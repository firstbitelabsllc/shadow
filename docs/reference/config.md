# Configuration

Vidux reads local defaults from `vidux.config.json` when one exists. The file
is gitignored so each operator keeps machine-specific paths and tokens out of
shared source.

The checked-in shape is `vidux.config.example.json`. When no live config exists,
`vidux config check` and the doctor use the example as a validation fallback.

## Primary files

- `vidux.config.json` - local live config, ignored by git.
- `vidux.config.example.json` - checked-in example and schema-like reference.

The example includes these top-level areas:

- `version`
- `plan_store`
- `defaults`
- `external_plan_roots`
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

`check --strict` fails when only the example file is available — useful for
machine-readiness gates that require a real local config. `show` is redacted: it
reports source, path, plan-store summary, expanded external root paths,
and issues.

The JSON report keeps compatibility field `external_plan_roots`, plus detail
fields:

- `external_plan_roots_detail` expands each configured root relative to the
  config file and reports whether the path exists.

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

Sections that guide scripts and automation behavior when copied into a live config:

- `defaults` covers archive thresholds, context warnings, worktree limits, and system pressure limits.
- `pruning` covers stale blocked-task age, worktree age thresholds, and plan size warnings.
- `backpressure` defines warning and critical thresholds for bimodal pressure plus circuit-breaker windows.

## External plan roots

`external_plan_roots` lists additional plan roots. External intake, labels, and
board sync are out of core scope; keep that logic in a private overlay instead
of the shared config reference.

Treat the example file as one minimal shape, not an exhaustive mirror of every production config.

## Where config is used

- `/vidux` reads the plan-store settings during startup.
- `vidux config` resolves, validates, initializes, and redacts local config.
- `vidux doctor` runs `vidux config check --json` as part of local readiness.
- `vidux-loop.sh` reads defaults such as archive thresholds and context warning lines.
- `vidux-doctor.sh` reads runtime thresholds such as max worktrees, browser-process caps, Codex automation caps, and the minimum `memory_pressure -Q` free percentage. Runtime doctor JSON also includes source-specific `vm_stat` page counters so raw page-derived MB values are not mistaken for the same metric.
- `resolve-plan-store.sh` resolves the active plan root for scripts.

## Related references

- Read [Commands](/reference/commands) for the prompt-layer startup flow that consumes this file.
- Read [Scripts](/reference/scripts) for the executables that read config defaults directly.
