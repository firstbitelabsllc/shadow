# Scripts Reference

The `scripts/` directory contains the executable support layer for vidux. Most files are shell or Python utilities with clear responsibilities documented in their header comments.

## Core cycle and plan scripts

| Script | Purpose |
|---|---|
| `scripts/vidux-loop.sh` | Stateless cycle helper that reads a plan and emits machine-readable next-action state. |
| `scripts/vidux-checkpoint.sh` | Structured checkpoint helper for marking work done, blocked, or archived. |
| `scripts/vidux-status.py` | Read-only status board for every `PLAN.md` under the configured roots. |
| `scripts/vidux-plan-gc.py` | Mechanical plan garbage collection for completed tasks, old investigations, and oversized inboxes. |
| `scripts/vidux-plan-gc-cron.sh` | Scheduled wrapper around `vidux-plan-gc.py`. |
| `scripts/vidux-inbox-sync.py` | Round-trip sync between `PLAN.md` state and external kanban adapters. |

## Health and verification scripts

| Script | Purpose |
|---|---|
| `scripts/vidux-doctor.sh` | Runtime health checks for plans, worktrees, and automation state. |
| `scripts/vidux-test-all.sh` | Comprehensive self-test harness for contract tests and related checks. |
| `scripts/vidux-fleet-quality.sh` | Classifies automation runs into quick, deep, mid, and normal quality buckets. |
| `scripts/vidux-worktree-gc.py` | Read-only by default. Classifies Vidux automation worktrees and, with `--apply --yes`, removes only clean non-primary worktrees that are already merged into the base branch or tied to merged PRs. |

## Codex maintenance scripts

| Script | Purpose |
|---|---|
| `scripts/codex-gc.sh` | Garbage-collect Codex caches, sessions, and archived rollout data. |
| `scripts/codex-gc-cron.sh` | Scheduled wrapper around `codex-gc.sh` with timestamped logging. |
| `scripts/vidux-fleet-rebuild.sh` | Manual Codex fleet rebuild utility that stops processes and rewrites automation DB state. |

## Support libraries in `scripts/lib/`

| Library | Purpose |
|---|---|
| `codex-db.sh` | Safe Codex database read/write helpers. |
| `compat.sh` | Portable wrappers for OS-specific `stat` and `date` behavior. |
| `ledger-config.sh` | Ledger path discovery from env vars and config. |
| `ledger-emit.sh` | Emit vidux events into the shared ledger. |
| `ledger-query.sh` | Fleet analysis queries over ledger data. |
| `queue-jsonl.sh` | Experimental derived JSONL queue helpers alongside `PLAN.md`. |
| `resolve-plan-store.sh` | Resolve the configured plan store path. |

## One-off and migration helpers

| Script | Purpose |
|---|---|
| `scripts/vidux-linear-reconcile.py` | One-shot reconcile for auto-promoted Linear tasks. Removes local `PLAN.md` task lines and `.external-state.json` mappings only when the remote Linear issue state is canceled (including duplicate-style canceled states). |
| `scripts/strip-linear-codec-markers.py` | Clean old vidux metadata markers out of Linear issue descriptions and persist metadata to sidecar state. |

## How to navigate the directory

- Start with the header comment in each script. The repo is disciplined about stating purpose and usage at the top of the file.
- Use [Configuration](/reference/config) when a script reads defaults from `vidux.config.json`.
- Use [Hooks](/reference/hooks) if you want lightweight git-based enforcement instead of a full automation lane.
