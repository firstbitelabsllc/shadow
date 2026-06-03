# T8 Owner Review Packet

Date: 2026-06-02
Plan: `projects/team-agent-coordination/PLAN.md`
Task: T8c
Ledger eid: `evt_20260602022928_t8c_owner_review_packet`

## What Changed

- `scripts/vidux-worktree-gc.py` now emits `owner_review_items` in JSON.
- `scripts/vidux-worktree-gc.py --owner-review-markdown` now prints a compact Markdown packet for non-removable worktrees.
- The packet is read-only and excludes `primary` and `merged_clean` worktrees.
- Vidux docs and the shared `/fleet-cleanup` skill now document the owner-review packet.
- The recurring ledger audit now guards the `/fleet-cleanup` skill wording for `owner_review_items` and `--owner-review-markdown`.

## Live T8 Proof

Command:

```bash
python3 scripts/vidux-worktree-gc.py --base origin/main --owner-review-markdown /Users/leokwan/Development/resplit-web | sed -n '1,80p'
```

Observed:

- `Cleanup decision: owner_review_required_before_cleanup`
- `Automated removal allowed: false`
- `Removable merged_clean worktrees: 0`
- `Owner-review worktrees: 8`
- Owner-review buckets: `closed_unmerged=1`, `dirty=3`, `unmerged_no_pr=4`

Command:

```bash
python3 scripts/vidux-worktree-gc.py --base origin/main --json /Users/leokwan/Development/resplit-ios
```

Observed JSON summary:

- `cleanup_decision.automated_removal_allowed=false`
- `cleanup_decision.next_action=owner_review_required_before_cleanup`
- `cleanup_decision.owner_review_required_count=7`
- `len(owner_review_items)=7`
- First owner-review bucket: `open_pr`

## Verification

- `python3 -m unittest tests.test_worktree_gc -v` passed 6 tests.
- `python3 -m py_compile scripts/vidux-worktree-gc.py` passed.
- `bash -n /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh` passed.
- `bash ~/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh` returned 0 failures, 0 warnings.
- `python3 -m unittest tests.test_worktree_gc tests.test_vidux_contracts tests.test_pr_body tests.test_publish_scrutiny tests.test_vidux_claims tests.test_release_script` passed 197 tests.
- `npm run docs:build` passed.
- Scoped `git diff --check` passed for touched Vidux, `/ai`, and `/ai-leo` files.
- `python3 scripts/vidux-publish-scrutiny.py ... --json` returned `ready=true` with invariant, regression, and adversarial review passes.

## Non-Claims

- No cleanup deletion was performed.
- No branch was removed.
- No process was killed.
- No cache, state file, memory file, log, lock, plan GC archive, or worktree mutation was performed.
- T8 remains open until owners resolve, merge, archive, or explicitly abandon the non-removable Resplit buckets.

## Next-Agent Resume

Resume T8 from `projects/team-agent-coordination/PLAN.md`: run `--owner-review-markdown` for `resplit-ios` and `resplit-web`, then work the owner-review rows. Do not delete a worktree unless `cleanup_decision.automated_removal_allowed=true` and the specific row is `merged_clean`, or an owner has explicitly approved manual removal.
