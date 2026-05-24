# Commands Reference

The repo ships two command specs in `commands/`: `/vidux` and `/vidux-status`. These files describe interaction contracts, not shell executables.

## `/vidux`

`commands/vidux.md` defines the main plan-first orchestration flow.

### Stages

The command file requires stage markers for the main cycle:

- `GATHER`
- `PLAN`
- `EXECUTE`
- `VERIFY`
- `CHECKPOINT`
- `COMPLETE`

### Startup contract

The command spec says `/vidux` should:

1. Load the `vidux` skill.
2. Read `vidux.config.json`.
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

The command spec renders two buckets:

- Plans tied to the current chat.
- Other tracked plans.

It also defines a 10-cell progress bar and rules for hiding stale, inactive plans unless `--all` is passed.

## Source files

- `commands/vidux.md`
- `commands/vidux-status.md`

## Shell CLI note

The executable `bin/vidux` also exposes helper subcommands that back the
discipline. `vidux drift <PLAN.md> ...` records planned-vs-actual deviation in
`## Drift Log`, appends Progress, and can explicitly block stale tasks, add
follow-up tasks, or mirror the drift into subplans. The drift helper can also
write local feedback-cache rows and emit signposts when those paths are
supplied. Use signpost summaries to verify deep smoke runs without treating
them as product analytics.

## Related references

- Read [PLAN.md Field Reference](/reference/plan-fields) for the state that `/vidux` consumes.
- Read [Prompt Template](/reference/prompt-template) for the prompt shape a lane uses each fire.
- Read [Configuration](/reference/config) for the plan-store settings that affect both commands.
