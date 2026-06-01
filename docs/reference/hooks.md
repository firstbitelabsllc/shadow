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

Hook installs and hook wiring changes are publish/change cycles. Before copying
or enabling a hook in a target repo, update that repo's owning `PLAN.md` and
emit a `ledger-emit.sh --event publish` row with:

- `--repo-path` set to the target repo.
- `--plan-path` set to the target repo's owning `PLAN.md`.
- `--proof` naming the syntax check, dry-run, or install verification.
- `--handoff-status done` for a complete install, or `needs_review` when the
  hook is copied but not yet verified.
- `--file` for each hook path changed, including `.git/hooks/...` paths.
- `--claim` for the owning plan or hook wiring file the next agent must inspect.

```bash
~/Development/ai/hooks/ledger-emit.sh \
  --event publish \
  --repo-path /path/to/your/project \
  --lane hook-install \
  --plan-path /path/to/your/project/PLAN.md \
  --proof "hook install dry-run / shell syntax passed" \
  --handoff-status done \
  --file /path/to/your/project/.git/hooks/pre-commit \
  --claim /path/to/your/project/PLAN.md \
  --skills vidux \
  --summary "Installed Vidux planning hooks"

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

These entries are examples, not auto-installed defaults. In the shipped manifest, `vidux-before-task` is a non-blocking health check. `vidux-after-task` is illustrative rather than plug-and-play: the raw `scripts/vidux-checkpoint.sh` CLI exits with usage unless it receives either `--archive` or `<plan-path> <task> <summary>` (plus optional flags), so a real app hook needs a wrapper that supplies those arguments.

## Behavior notes

- `pre-commit-plan-check.sh` allows doc-only and plan-only commits through.
- `post-commit-checkpoint.sh` is advisory. It prints a reminder and does not block.
- `three-strike-gate.sh` is also advisory. It prints escalation guidance and exits cleanly.
- `hooks/hooks.json` is a source-grounded example manifest, not an auto-installer or full hook runner.

## When to use hooks

Hooks are a good fit when you want a local nudge without running a scheduled lane:

- Use the pre-commit hook to catch planless code changes.
- Use the post-commit hook to keep progress logging from drifting.
- Use the three-strike helper when a surface is attracting repeated low-confidence retries.

## Related references

- Read [PLAN.md Field Reference](/reference/plan-fields) to understand what the pre-commit hook is looking for.
- Read [Scripts](/reference/scripts) for the heavier command-line helpers that complement these hooks.
- Read `ENFORCEMENT.md` when you need the prompt-hook examples for Claude Code session wiring.
