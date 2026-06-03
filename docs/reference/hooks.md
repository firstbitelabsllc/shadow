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
- non-empty `--summary` naming the hook install/change.
- `--task-id` set to the owning plan row/task id, matching a checkbox/FSM row in `--plan-path`.
- `--plan-path` set to the target repo's existing owning `PLAN.md`.
- `--proof` naming the syntax check, dry-run, or install verification.
- `--handoff-status done` for a complete install, or `needs_review` when the
  hook is copied but not yet verified.
- `--resume` with the next command, repo, or blocker for the next agent.
- `--file` for each changed path, using path-like values that exist or are git-known deletions. For the pre-copy packet, the updated `PLAN.md` is the changed file; final `done` packets can name `.git/hooks/...` paths after they exist.
- `--claim` for every `--file` entry plus any owning plan or hook wiring file the next agent must inspect; claims must also be path-like and resolve to existing paths or git-known deletions.

```bash
~/Development/ai/hooks/ledger-emit.sh \
  --event publish \
  --repo-path /path/to/your/project \
  --lane hook-install \
  --task-id hook-install \
  --plan-path /path/to/your/project/PLAN.md \
  --proof "hook install dry-run / shell syntax passed" \
  --handoff-status needs_review \
  --resume "copy hooks, verify installed hook paths exist, then emit final done row" \
  --file /path/to/your/project/PLAN.md \
  --claim /path/to/your/project/PLAN.md \
  --skills vidux \
  --summary "Planned Vidux planning hook install"

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

These entries are examples, not auto-installed defaults. In the shipped manifest, `vidux-before-task` is a non-blocking runtime health check that intentionally runs `scripts/vidux-doctor.sh --json`, not `vidux doctor`. The runtime doctor is read-only by default and JSON-friendly for hook probes; `vidux doctor` is the terminal install/readiness doctor and may be slow when it runs `npm test`. `vidux-after-task` is illustrative rather than plug-and-play: the raw `scripts/vidux-checkpoint.sh` CLI exits with usage unless it receives either `--archive` or `<plan-path> <task> <summary>` (plus optional flags), so a real app hook needs a wrapper that supplies those arguments.

## Behavior notes

- `pre-commit-plan-check.sh` allows doc-only and plan-only commits through.
- `post-commit-checkpoint.sh` is advisory. It prints a reminder and does not block.
- `three-strike-gate.sh` is also advisory. It prints escalation guidance and exits cleanly.
- `hooks/hooks.json` is a source-grounded example manifest, not an auto-installer or full hook runner.

## Signposted lifecycle trace

Use `vidux signpost trace` when you need mechanical proof that pre-task,
during-task, spawned-subagent, and post-task hooks ran in the intended order.
Give the whole lane one `VIDUX_SIGNPOST_RUN_ID`, then emit each phase:

```bash
export VIDUX_SIGNPOST_RUN_ID=run-example

vidux signpost emit --feature hook --action beforeTask --called "scripts/vidux-doctor.sh --json"
vidux signpost emit --feature subagent --action spawn --called "worker-plan"
vidux signpost emit --feature hook --action afterTask --called "vidux checkpoint"

vidux signpost trace --run-id run-example
```

For a disposable local smoke that does not require real spawned runtimes, use:

```bash
vidux signpost lifecycle-smoke --run-id run-example --json
vidux signpost spawned-subagent-smoke --run-id run-example-env --json
```

`lifecycle-smoke` emits `hook.beforeTask`, `subagent.spawn`, `task.verify`, and
`hook.afterTask` into one run id with Codex, Claude, Cursor, and Codex runtime
attribution respectively. `spawned-subagent-smoke` uses temporary local
environment overlays to simulate a Codex parent thread inherited by Claude and
Cursor workers, then restores the ambient environment. Both are local smokes,
not proof that those external tools actually ran.

Runtime attribution comes from `VIDUX_RUNTIME` when it is set, otherwise from
local session environment variables such as `CLAUDE_SESSION_ID`,
`CURSOR_SESSION_ID`, and `CODEX_SESSION_ID`. Use `VIDUX_RUNTIME=claude` or
`VIDUX_RUNTIME=cursor` for spawned workers that inherit an ambient Codex thread
environment. The trace is local JSONL proof, so it is safe for smoke runs but
should not be treated as a central analytics source.

## When to use hooks

Hooks are a good fit when you want a local nudge without running a scheduled lane:

- Use the pre-commit hook to catch planless code changes.
- Use the post-commit hook to keep progress logging from drifting.
- Use the three-strike helper when a surface is attracting repeated low-confidence retries.

## Related references

- Read [PLAN.md Field Reference](/reference/plan-fields) to understand what the pre-commit hook is looking for.
- Read [Scripts](/reference/scripts) for the heavier command-line helpers that complement these hooks.
- Read `ENFORCEMENT.md` when you need the prompt-hook examples for Claude Code session wiring.
