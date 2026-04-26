# Hooks Reference

Vidux ships three optional git hooks in `hooks/`. They are lightweight local enforcement helpers, not a replacement for the main planning discipline.

## Available hooks

| Hook | Behavior |
|---|---|
| `hooks/pre-commit-plan-check.sh` | Blocks a commit when code changes are staged but the repo has no active or pending task in `PLAN.md`. |
| `hooks/post-commit-checkpoint.sh` | Prints a reminder if `PLAN.md` has no progress entry for the current day. |
| `hooks/three-strike-gate.sh` | Warns after repeated `fix` or `retry` commits so the operator can step up an abstraction level. |

## Installation

The README shows the intended install flow:

```bash
cp hooks/pre-commit-plan-check.sh /path/to/your/project/.git/hooks/pre-commit
cp hooks/post-commit-checkpoint.sh /path/to/your/project/.git/hooks/post-commit
cp hooks/three-strike-gate.sh /path/to/your/project/.git/hooks/
```

## Behavior notes

- `pre-commit-plan-check.sh` allows doc-only and plan-only commits through.
- `post-commit-checkpoint.sh` is advisory. It prints a reminder and does not block.
- `three-strike-gate.sh` is also advisory. It prints escalation guidance and exits cleanly.

## When to use hooks

Hooks are a good fit when you want a local nudge without running a scheduled lane:

- Use the pre-commit hook to catch planless code changes.
- Use the post-commit hook to keep progress logging from drifting.
- Use the three-strike helper when a surface is attracting repeated low-confidence retries.

## Related references

- Read [PLAN.md Field Reference](/reference/plan-fields) to understand what the pre-commit hook is looking for.
- Read [Scripts](/reference/scripts) for the heavier command-line helpers that complement these hooks.
