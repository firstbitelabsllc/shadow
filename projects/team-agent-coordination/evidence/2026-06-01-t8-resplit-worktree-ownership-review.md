# T8 Resplit Worktree Ownership Review - 2026-06-01

Scope: read-only ownership review for T8 disk-pressure cleanup. No worktrees, branches, caches, logs, LaunchAgents, or plans were deleted by this review.

## Commands

- `python3 scripts/vidux-worktree-gc.py --base origin/main --json /Users/leokwan/Development/resplit-ios`
- `python3 scripts/vidux-worktree-gc.py --base origin/main --json /Users/leokwan/Development/resplit-web`
- `/Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh --dry-run | sed -n '1,130p'`

## Current Decision

No Resplit worktree is approved for automated cleanup.

Both Resplit repos report `removable=0`. Every non-primary path is either an open PR, dirty WIP, closed-unmerged branch, or unmerged branch with no PR. T8 therefore remains an ownership-routing task, not a deletion task.

## resplit-ios

Summary: `total=8`, `removable=0`, `open_pr=4`, `primary=1`, `unmerged_no_pr=3`.

Open PRs, review/merge/close before cleanup:

- PR #740 `claude/asc-intake-AAZMm-ADyJj6-2026-05-24` at `/Users/leokwan/Development/resplit-ios-worktrees/aazmm-avatar-fix`
- PR #743 `claude/asc-AHYCouf6-fixspec-2026-05-24` at `/Users/leokwan/Development/resplit-ios-worktrees/asc-AHYC-fixspec`
- PR #803 `claude/ocr-i18n-currency-disambiguation` at `/Users/leokwan/Development/resplit-ios-worktrees/ocr-i18n-currency-20260530`
- PR #802 `claude/ocr-key-proxy-attest-ios` at `/Users/leokwan/Development/resplit-ios-worktrees/ocr-key-proxy-20260530`

Unmerged branches with no PR, owner review required before archive/open-PR/merge:

- `codex/local-ci-locale-snapshot-refresh-20260526` at `/Users/leokwan/Development/resplit-ios-worktrees/local-ci-locale-snapshot-refresh-20260526`
- `codex/settlement-flow-density-cap-20260526` at `/Users/leokwan/Development/resplit-ios-worktrees/settlement-flow-density-cap-20260526`
- `claude/asc-c42-archive-clean` at `/Users/leokwan/Development/resplit-ios/.claude/worktrees/agent-a2186177bcb7b08d5`

## resplit-web

Summary: `total=9`, `removable=0`, `closed_unmerged=1`, `dirty=3`, `primary=1`, `unmerged_no_pr=4`.

Closed-unmerged branch, owner review required before archive/revive/manual remove:

- PR #747 `fix/pricing-support-a11y-2026-05-24` at `/Users/leokwan/Development/resplit-web-worktrees/pricing-support-a11y-2026-05-24`

Dirty WIP, preserve until owner commits, stashes, or abandons:

- `claude/csp-harden-2026-05-25` at `/Users/leokwan/Development/resplit-web-worktrees/csp-harden-2026-05-25`
- `claude/nameselect-a11y-2026-05-25` at `/Users/leokwan/Development/resplit-web-worktrees/nameselect-a11y-2026-05-25`
- `claude/web-launch-crush-20260529` at `/Users/leokwan/Development/resplit-web-worktrees/web-launch-crush-20260529`

Unmerged branches with no PR, owner review required before archive/open-PR/merge:

- `claude/web-FA5-claim-audit` at `/Users/leokwan/Development/resplit-web-worktrees/FA5-claim-audit-1803`
- `codex/local-ci-token-vars` at `/Users/leokwan/Development/resplit-web-worktrees/local-ci-token-vars`
- `claude/web-T10-launch-checklist` at `/Users/leokwan/Development/resplit-web-worktrees/t10-launch-checklist-1132`
- `codex/web-promote-reviewed-patch-current-main-20260525T184547Z-tuug6r` at `/Users/leokwan/Development/resplit-web-worktrees/web-promote-reviewed-patch-current-main-20260525T184547Z-tuug6r`

## Fleet-Cleanup Dry-Run Notes

Disk remains pressured: `/System/Volumes/Data` is `97%` used with `31Gi` available.

Read-only cleanup inventory:

- Xcode DerivedData: `2.7G`, `0.0MiB` older-than-24h reclaimable candidate
- `/private/tmp/resplit-dd-*`: `2` dirs, `0.0MiB` older-than-6h reclaimable candidate
- Tuist caches/runs: `80K`, `80K`, and `614M`
- Resplit top-level sibling dirs: `4`, about `10209.8MiB`
- Oversized ledger logs: none

Lane-staleness after the T2 reinstall:

- `resplit-watch`: `OK`, `LaunchAgent=loaded`
- `resplit-2-0-loop`: `OK`, `LaunchAgent=loaded`
- `linear-health-watch`: `DEAD`, `LaunchAgent=enabled-not-loaded`
- `strongyes-watch`: `DEAD`, `LaunchAgent=not-installed-or-not-loaded`

Perf-sentinel non-actionable warning for this slice: `fseventsd` is at about `17GB` RSS with `2610` worktree feeders. Per fleet-cleanup dry-run policy, this is detect-only; no process kill or cleanup action was performed.

## Resume

Next owner should review the named open PRs and unmerged branches. T8 can only move from review to cleanup after a specific owner decision class exists for a bucket, or after `vidux-worktree-gc.py --json` reports `removable>0` for Resplit paths.
