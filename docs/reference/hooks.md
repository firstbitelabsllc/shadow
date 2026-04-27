# Hooks Reference

Vidux ships three optional git hooks in `hooks/`. The repo also includes `hooks/hooks.json`, a source-grounded manifest that maps those scripts plus two task-lifecycle helpers into higher-level hook events.

## Git hooks

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

## Hook manifest

`hooks/hooks.json` is the repo's checked-in example for app-level hook wiring. It currently declares five entries:

| Manifest entry | Event | Script |
|---|---|---|
| `vidux-pre-commit` | `pre-commit` | `hooks/pre-commit-plan-check.sh` |
| `vidux-checkpoint` | `post-commit` | `hooks/post-commit-checkpoint.sh` |
| `vidux-three-strike` | `post-build-failure` | `hooks/three-strike-gate.sh` |
| `vidux-before-task` | `beforeTask` | `scripts/vidux-doctor.sh --json` |
| `vidux-after-task` | `afterTask` | `scripts/vidux-checkpoint.sh` |

These entries are examples, not auto-installed defaults. In the shipped manifest, `vidux-before-task` is a non-blocking health check and `vidux-after-task` expects `PLAN_PATH` so it can write a structured post-flight checkpoint.

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
- Read `ENFORCEMENT.md` when you need the prompt-hook examples for Claude Code session wiring.
