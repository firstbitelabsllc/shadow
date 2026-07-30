# Scripts Reference

The `scripts/` directory contains the CLI implementation, read-only
projections, optional local state helpers, and release gates. The coding host
still owns scheduling, worker execution, provider access, and process
lifecycle.

Prefer the `vidux` CLI when it exposes the operation you need.

## CLI and public-contract scripts

| Script | Purpose |
|---|---|
| `scripts/vidux-init.sh` | Implements `vidux init`; creates a `PLAN.md` without overwriting an existing plan. |
| `scripts/vidux-status.py` | Implements `vidux status`; reads operational plans and renders their current task state. |
| `scripts/vidux-config.py` | Resolves, validates, initializes, and redacts local configuration. |
| `scripts/vidux-checkpoint.sh` | Implements the optional `vidux checkpoint` plan update described below. |
| `scripts/vidux-doctor-cli.sh` | Implements `vidux doctor`, the install/readiness check. |
| `scripts/vidux-outcome-validate.py` | Validates Outcome / Ask / Steer interchange JSON without executing work. |
| `scripts/vidux-public-ready-grep-gate.py` | Scans the maintained public surface and commit metadata for disallowed data shapes. |
| `scripts/vidux-release-package.py` | Builds the npm candidate twice and verifies byte identity, versions, tracked contents, required files, modes, and size bounds. |

## Optional checkpoint

Normal mode accepts:

```text
vidux checkpoint <plan-path> <exact-task-text> <summary>
  [--proof <text>]
  [--blocker <text>]
  [--status done|done_with_concerns|blocked]
  [--outcome useful|busy|blocked_clarified]
  [--commit]
```

The task must already exist in the plan as pending or in progress. The helper
updates the row and `## Progress`. Completion requires `--proof`; a blocked
checkpoint requires a concrete `--blocker`. Changes remain uncommitted unless
`--commit` is explicit. When local ledger discovery succeeds, the helper
appends a bounded checkpoint entry; `VIDUX_LEDGER_FILE` can select an existing
readable local ledger. Otherwise ledger emission is a no-op.

Archive mode is explicit:

```text
vidux checkpoint <plan-path> --archive [--commit]
```

Checkpointing is not mandatory authority, automatic recovery, a worker
lifecycle hook, or permission to push, merge, publish, or deploy. `PLAN.md`
remains authority.

## Advanced local helpers

These scripts are explicit local tools, not a scheduler or agent runtime:

| Script | Purpose |
|---|---|
| `scripts/vidux-loop.sh` | Reads one plan and prints next-action state. Read-only by default; it does not execute the selected row. |
| `scripts/vidux-doctor.sh` | Reads optional local plan, worktree, browser, and host-health surfaces. Its compatibility `--fix` flag is report-only and performs no destructive cleanup. |
| `scripts/vidux-claims.py` | Maintains local JSONL work-surface leases so cooperating hosts can avoid overlapping writes. It does not dispatch workers. |
| `scripts/vidux-steer.py` | Queues and leases one-shot local intent scoped to an authority plan. It never invokes a provider, shell, goal, loop, or scheduler. |
| `scripts/vidux-plan-guard.sh` | Snapshots and verifies plan task counts to surface unexpected task loss. |
| `scripts/vidux-step-journal.sh` | Maintains an optional local intra-row JSONL journal. The owning plan remains the cold-resume authority. |

## Support libraries in `scripts/lib/`

| Library | Purpose |
|---|---|
| `scripts/lib/ledger-config.sh` | Sourced-only local ledger discovery. |
| `scripts/lib/ledger-emit.sh` | Sourced-only bounded event emission when a local ledger is available. |

## How to navigate the directory

- Start with the header comment in each script.
- GitHub Actions CI runs `npm test` (Vitest plus Python unittest) and
  `npm run release:verify` on Node 22 with Python 3.9, 3.12, and 3.14. The
  separate secret-scan workflow runs gitleaks plus the public-ready content and
  commit-metadata gate.
- Use [Configuration](/reference/config) for local settings.
- Use [Hooks](/reference/hooks) for optional repository-local nudges.
