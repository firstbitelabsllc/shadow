# Commands Reference

The repo ships two command specs in `commands/`: `/vidux` and `/vidux-status`. They describe interaction contracts, not shell executables.

## `/vidux`

`commands/vidux.md` defines the main plan-first orchestration flow.

### Stages

The command file requires these stage markers for the main cycle:

- `GATHER`
- `PLAN`
- `EXECUTE`
- `VERIFY`
- `CHECKPOINT`
- `COMPLETE`

### Startup contract

The command spec says `/vidux` should:

1. Load the `vidux` skill.
2. Resolve config with `vidux config check --json`, keeping a missing live
   config distinct from the checked-in example fallback.
3. Resolve the authority plan store.
4. Read the authority `PLAN.md`, recent progress, and current git diff.

### Core cycle

When a plan exists, `/vidux` resumes `in_progress` work first, then decides whether the next step is research, plan refinement, or execution. It also keeps the "evidence changes mid-cycle -> re-sort the queue" rule explicit.

## `/vidux-status`

`commands/vidux-status.md` defines a read-only board for plan health across the machine.

### What it reports

- Task counts by status.
- Progress percentage.
- Remaining AI-hours from `[ETA: Xh]` tags.
- The most recent progress timestamp.

### Output model

Two buckets:

- Plans tied to the current chat.
- Other tracked plans.

It also defines a 10-cell progress bar and rules for hiding stale, inactive plans unless `--all` is passed.

## Source files

- `commands/vidux.md`
- `commands/vidux-status.md`

## Shell CLI note

`bin/vidux` exposes helper subcommands that back the discipline:

- `vidux config path|check|show|init` resolves and validates the local
  `vidux.config.json`, falling back to `vidux.config.example.json` unless
  `--strict` is used. JSON output includes redacted inbox-source metadata for
  operator checks.
- `vidux drift <PLAN.md> ...` records planned-vs-actual deviation in
  `## Drift Log`, appends Progress, and can explicitly block stale tasks, add
  follow-up tasks, or mirror the drift into subplans.
- `vidux signpost emit|summary|trace|wrap|lifecycle-smoke|spawned-subagent-smoke`
  records local helper events and can print ordered call-stack proof for one
  run id.
- `vidux http-smoke --json --timeout 3 <url>...` classifies local HTTP monitor
  probes as `pass`, `warn_partial`, or `fail_budget` with bounded response
  samples, so route smokes do not dump full HTML or huge JSON into evidence.
  JSON `ok` follows the hard-fail exit status, while `strict_ok` is false when
  any warning is present. `--timeout` must be greater than 0, and
  `--max-sample-bytes` must be 0 or greater.
- `vidux doctor` runs local toolchain, auth, stale pidfile, config, and test
  checks as an install/readiness gate. Use `scripts/vidux-doctor.sh --json`
  for hook-safe runtime checks across plans, worktrees, automations, browser
  processes, and Codex state. Exit codes are `0` for pass, `1` for failed
  checks, and `2` for invalid usage.

Signposts are local smoke/profiler events, not product analytics.

## Related references

- Read [PLAN.md Field Reference](/reference/plan-fields) for the state that `/vidux` consumes.
- Read [Prompt Template](/reference/prompt-template) for the prompt shape a lane uses each fire.
- Read [Configuration](/reference/config) for the plan-store settings that affect both commands.
