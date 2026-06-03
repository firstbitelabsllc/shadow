# T8d Fleet-Cleanup Owner-Review Packet Command

Date: 2026-06-02
Plan: `/Users/leokwan/Development/vidux/projects/team-agent-coordination/PLAN.md`
Ledger eid: `evt_20260602024349_t8d_owner_review_packet_command`

## Change

- `/Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh` now prints an `owner-review packet` command whenever `vidux-worktree-gc.py --json` reports `cleanup_decision.owner_review_required_count > 0`.
- `/Users/leokwan/Development/ai/skills/fleet-cleanup/SKILL.md` documents that fleet-cleanup dry-run exposes the packet command.
- `/Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh` now fails if the fleet-cleanup runner stops rendering the packet line or stops using `--owner-review-markdown`.

## Live Dry-Run Proof

Command:

```sh
/Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh --dry-run | sed -n '/### Worktree GC/,/### Plan GC/p'
```

Relevant output:

```text
### Worktree GC
- vidux [dry-run]: total=4, removable=0, dirty=1, primary=1, unmerged_no_pr=2
  - cleanup decision: next=owner_review_required_before_cleanup; automated_removal_allowed=false; removable=0; owner_review_required=3; owner-review buckets: dirty=1, unmerged_no_pr=2
  - owner-review packet: python3 /Users/leokwan/Development/vidux/scripts/vidux-worktree-gc.py --base origin/main --owner-review-markdown /Users/leokwan/Development/vidux
- resplit-ios [dry-run]: total=8, removable=0, open_pr=4, primary=1, unmerged_no_pr=3
  - cleanup decision: next=owner_review_required_before_cleanup; automated_removal_allowed=false; removable=0; owner_review_required=7; owner-review buckets: open_pr=4, unmerged_no_pr=3
  - owner-review packet: python3 /Users/leokwan/Development/vidux/scripts/vidux-worktree-gc.py --base origin/main --owner-review-markdown /Users/leokwan/Development/resplit-ios
- resplit-web [dry-run]: total=9, removable=0, closed_unmerged=1, dirty=3, primary=1, unmerged_no_pr=4
  - cleanup decision: next=owner_review_required_before_cleanup; automated_removal_allowed=false; removable=0; owner_review_required=8; owner-review buckets: closed_unmerged=1, dirty=3, unmerged_no_pr=4
  - owner-review packet: python3 /Users/leokwan/Development/vidux/scripts/vidux-worktree-gc.py --base origin/main --owner-review-markdown /Users/leokwan/Development/resplit-web
- strongyes-web [dry-run]: total=143, removable=23, closed_unmerged=4, dirty=10, merged_clean=23, open_pr=15, primary=1, unknown=3, unmerged_no_pr=87
  - cleanup decision: next=run --apply --yes to remove merged_clean only; owner review required for non-removable buckets; automated_removal_allowed=true; removable=23; owner_review_required=119; owner-review buckets: closed_unmerged=4, dirty=10, open_pr=15, unknown=3, unmerged_no_pr=87
  - owner-review packet: python3 /Users/leokwan/Development/vidux/scripts/vidux-worktree-gc.py --base origin/main --owner-review-markdown /Users/leokwan/Development/strongyes-web
- ai [dry-run]: total=2, removable=0, open_pr=1, primary=1
  - cleanup decision: next=owner_review_required_before_cleanup; automated_removal_allowed=false; removable=0; owner_review_required=1; owner-review buckets: open_pr=1
  - owner-review packet: python3 /Users/leokwan/Development/vidux/scripts/vidux-worktree-gc.py --base origin/main --owner-review-markdown /Users/leokwan/Development/ai

### Plan GC
```

## Verification

```text
PASS bash -n /Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh
PASS bash -n /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh
PASS git diff --check -- skills/fleet-cleanup/scripts/run-once.sh skills/fleet-cleanup/SKILL.md (cwd=/Users/leokwan/Development/ai)
PASS git diff --check -- skills/ledger/scripts/audit_ledger_quality.sh (cwd=/Users/leokwan/Development/ai-leo)
PASS python3 -m unittest tests.test_worktree_gc (6 tests)
PASS python3 -m unittest tests.test_worktree_gc tests.test_vidux_contracts tests.test_pr_body tests.test_publish_scrutiny tests.test_vidux_claims tests.test_release_script (197 tests)
PASS bash /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh (0 failures, 0 warnings)
PASS python3 scripts/vidux-publish-scrutiny.py ... --json (ready=true)
```

## Self-Scrutiny

- Initial audit rerun failed because the new guard expected `owner-review packet:` and `--owner-review-markdown` on the same source line while the runner builds the command as a Python list. The guard was split into two checks, then the audit passed at 0/0.
- The dry-run was read-only. No cleanup deletion, branch removal, process kill, cache mutation, state write, memory write, log write, lock write, plan GC archive, or worktree mutation was performed.
- Resplit cleanup is still closed: `resplit-ios automated_removal_allowed=false owner_review_required=7`; `resplit-web automated_removal_allowed=false owner_review_required=8`.

## Next Resume

Run the printed owner-review packet commands for `/Users/leokwan/Development/resplit-ios` and `/Users/leokwan/Development/resplit-web`, then resolve each non-removable bucket with the owner. Do not delete a worktree unless `cleanup_decision.automated_removal_allowed=true` and the row is `merged_clean`, or the owner explicitly approves archival/removal.
