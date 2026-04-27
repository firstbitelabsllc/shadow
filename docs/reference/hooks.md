# Hooks Reference

Vidux ships two hook surfaces:

- three shell hook scripts in `hooks/`
- a hook registry in `hooks/hooks.json`

Together they cover both plain git hooks and runtime-level task hooks such as `beforeTask` and `afterTask`.

## Available hooks

| Hook | Event | Behavior |
|---|---|
| `hooks/pre-commit-plan-check.sh` | `pre-commit` | Blocks a commit when code changes are staged but the repo has no active or pending task in `PLAN.md`. |
| `hooks/post-commit-checkpoint.sh` | `post-commit` | Prints a reminder if `PLAN.md` has no progress entry for the current day. |
| `hooks/three-strike-gate.sh` | `post-build-failure` | Warns after repeated `fix` or `retry` commits so the operator can step up an abstraction level. |
| `scripts/vidux-doctor.sh` | `beforeTask` | Runs a pre-flight health check for merges, stale worktrees, pressure, and low disk. |
| `scripts/vidux-checkpoint.sh` | `afterTask` | Records a structured outcome after a scheduled task and can emit ledger-aware checkpoint data. |

## Git Hook Installation

The README shows the intended copy-based install flow for the three shell hooks:

```bash
cp hooks/pre-commit-plan-check.sh /path/to/your/project/.git/hooks/pre-commit
cp hooks/post-commit-checkpoint.sh /path/to/your/project/.git/hooks/post-commit
cp hooks/three-strike-gate.sh /path/to/your/project/.git/hooks/
```

## Runtime Hook Wiring

`hooks/hooks.json` is the repo's machine-readable hook registry. It records the intended event name, enabled flag, script path, and notes for each hook entry.

Use it when your host runtime supports lifecycle hooks beyond git itself. The checked-in registry currently enables:

- `beforeTask` → `scripts/vidux-doctor.sh --json`
- `afterTask` → `scripts/vidux-checkpoint.sh`

## Behavior notes

- `pre-commit-plan-check.sh` allows doc-only and plan-only commits through.
- `post-commit-checkpoint.sh` is advisory. It prints a reminder and does not block.
- `three-strike-gate.sh` is also advisory. It prints escalation guidance and exits cleanly.
- `vidux-doctor.sh` is a non-blocking runtime health check unless the caller chooses to treat warnings as a gate.
- `vidux-checkpoint.sh` supports `done`, `done_with_concerns`, and `blocked` outcomes.

## When to use hooks

Hooks are a good fit when you want a local nudge without running a scheduled lane:

- Use the pre-commit hook to catch planless code changes.
- Use the post-commit hook to keep progress logging from drifting.
- Use the three-strike helper when a surface is attracting repeated low-confidence retries.
- Use `beforeTask` / `afterTask` when your runtime can invoke health checks and structured checkpoints around scheduled work.

## Related references

- Read [PLAN.md Field Reference](/reference/plan-fields) to understand what the pre-commit hook is looking for.
- Read [Scripts](/reference/scripts) for the heavier command-line helpers that complement these hooks.
