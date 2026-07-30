# Hooks Reference

Vidux ships three optional, repository-local shell helpers in `hooks/`.
`hooks/hooks-reference.json` is a reference inventory only. No coding host or
plugin loader consumes it automatically.

## Git hooks

| Hook | Behavior |
|---|---|
| `hooks/pre-commit-plan-check.sh` | Blocks a commit when code changes are staged but the repo has no active or pending task in `PLAN.md`. |
| `hooks/post-commit-checkpoint.sh` | Prints a reminder if `PLAN.md` has no progress entry for the current day. |
| `hooks/three-strike-gate.sh` | Manually checks the last ten commit subjects and warns when at least three contain `fix`, `retry`, or `attempt`. |

## Installation

Review the scripts and preserve existing target hooks before copying:

```bash
cp hooks/pre-commit-plan-check.sh /path/to/your/project/.git/hooks/pre-commit
cp hooks/post-commit-checkpoint.sh /path/to/your/project/.git/hooks/post-commit
chmod +x /path/to/your/project/.git/hooks/pre-commit
chmod +x /path/to/your/project/.git/hooks/post-commit
```

Run the advisory helper manually from the Vidux checkout:

```bash
bash hooks/three-strike-gate.sh
```

The coding host owns any lifecycle wiring. Vidux does not install host hooks,
schedule tasks, or translate this inventory into Claude Code, Codex, or Cursor
configuration.

## Behavior notes

- `pre-commit-plan-check.sh` allows Markdown-only changes and repositories
  without a root `PLAN.md`.
- `post-commit-checkpoint.sh` prints a reminder and does not update the plan or
  run `vidux checkpoint`.
- `three-strike-gate.sh` is advisory and exits cleanly.
- None of these scripts pushes, merges, publishes, deploys, or runs workers.

## When to use hooks

Hooks fit when you want a small local nudge:

- Use the pre-commit hook to catch planless code changes.
- Use the post-commit hook to keep progress logging from drifting.
- Run the three-strike helper when recent commit subjects suggest repeated
  low-confidence retries.

## Related references

- Read [PLAN.md Field Reference](/reference/plan-fields) to understand what the pre-commit hook is looking for.
- Read [Scripts](/reference/scripts) for the optional checkpoint and diagnostic
  helpers.
