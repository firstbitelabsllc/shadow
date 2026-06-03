# T8i Fleet-Cleanup Safe Packet Pointer

Date: 2026-06-02
Lane: team-agent-coordination
Plan row: T8i
Ledger eid: evt_20260602034622_t8i_fleet_cleanup_safe_packet_pointer

## Change

- `/Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh --dry-run` now reads classifier `safe_cleanup_items`.
- When safe cleanup rows exist, dry-run prints `safe cleanup rows: count=<n>; review owner-review packet before apply`.
- Fleet-cleanup now prints the `--owner-review-markdown` packet command when either owner-review rows or safe cleanup rows exist.
- `/Users/leokwan/Development/ai/skills/fleet-cleanup/SKILL.md` documents the `safe_cleanup_items` contract.
- `/Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh` guards the shared skill wording and dry-run renderer.

## Proof

- PASS: `bash -n /Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh`
- PASS: `/Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh --dry-run | sed -n '/### Worktree GC/,/### Plan GC/p'`
- PASS: `bash /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh` - 0 failures, 0 warnings.
- PASS: `git diff --check -- skills/fleet-cleanup/scripts/run-once.sh skills/fleet-cleanup/SKILL.md` from `/Users/leokwan/Development/ai`
- PASS: `git diff --check -- skills/ledger/scripts/audit_ledger_quality.sh` from `/Users/leokwan/Development/ai-leo`
- PASS: `git diff --check -- projects/team-agent-coordination/PLAN.md` from `/Users/leokwan/Development/vidux`
- PASS: `python3 scripts/vidux-publish-scrutiny.py ...` - `ready=true`.

## Live Snapshot

Dry-run Worktree GC section showed:

- `resplit-ios`: `removable=0`, `owner_review_required=7`, packet command printed.
- `resplit-web`: `removable=0`, `owner_review_required=11`, packet command printed.
- `strongyes-web`: `removable=31`, `owner_review_required=120`, `safe cleanup rows: count=31; review owner-review packet before apply`, packet command printed.
- `ai`: `removable=0`, `owner_review_required=1`, packet command printed.

The positive live proof came from `strongyes-web` because current Resplit worktrees had no removable `merged_clean` rows at this snapshot.

## Self-Scrutiny

- Invariant: fleet-cleanup consumes `safe_cleanup_items` as row evidence and prints the packet command when safe rows or owner-review rows exist.
- Regression: the non-dry-run apply path remains unchanged and still calls the guarded classifier `--json --apply --yes` path.
- Adversarial: the new line is review evidence only. No cleanup apply, branch removal, process kill, cache mutation, state write, memory write, log write, lock write, plan GC archive, Resplit worktree mutation, StrongYes worktree mutation, cleanup approval, or owner decision was performed.

## Next-Agent Resume

Resume T8 from `projects/team-agent-coordination/PLAN.md`. Run fleet-cleanup dry-run first, then inspect each repo's `--owner-review-markdown` packet before any destructive cleanup approval. T2 remains open for non-deferred Resplit loop proof; T8 remains open until owners resolve non-removable rows or explicitly approve current `merged_clean` cleanup rows.
