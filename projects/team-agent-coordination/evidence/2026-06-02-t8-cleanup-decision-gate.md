# T8 Cleanup Decision Gate

Date: 2026-06-02
Plan: `projects/team-agent-coordination/PLAN.md`
Task: T8b
Ledger eid: `evt_20260602021744_t8b_cleanup_decision_gate`

## What Changed

- `scripts/vidux-worktree-gc.py` now emits a top-level `cleanup_decision` in JSON and text output.
- `cleanup_decision.automated_removal_allowed` is true only when at least one `merged_clean` worktree is removable.
- `cleanup_decision.owner_review_required_count` counts non-removable owner buckets: `dirty`, `open_pr`, `closed_unmerged`, `unmerged_no_pr`, and `unknown`.
- `/Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh --dry-run` now renders a per-repo cleanup decision line before verbose Resplit worktree details.
- `/Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh` now guards the `cleanup_decision` documentation and fleet-cleanup report wording.

## Current Dry-Run Decision Output

Command:

```bash
/Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh --dry-run | sed -n '/### Worktree GC/,/### Plan GC/p'
```

Observed Worktree GC decision summary:

- `vidux`: `removable=0`, `owner_review_required=3`, `next=owner_review_required_before_cleanup`.
- `resplit-ios`: `removable=0`, `owner_review_required=7`, `owner-review buckets: open_pr=4, unmerged_no_pr=3`.
- `resplit-web`: `removable=0`, `owner_review_required=8`, `owner-review buckets: closed_unmerged=1, dirty=3, unmerged_no_pr=4`.
- `strongyes-web`: `removable=22`, `automated_removal_allowed=true`, but owner review remains required for `119` non-removable buckets.
- `ai`: `removable=0`, `owner_review_required=1`, `owner-review buckets: open_pr=1`.

Direct JSON proof for the T8 Resplit web surface:

```bash
python3 scripts/vidux-worktree-gc.py --base origin/main --json /Users/leokwan/Development/resplit-web | python3 -m json.tool | sed -n '1,80p'
```

Key fields:

- `cleanup_decision.automated_removal_allowed=false`
- `cleanup_decision.next_action=owner_review_required_before_cleanup`
- `cleanup_decision.owner_review_required_count=8`
- `cleanup_decision.blocked_by_buckets.closed_unmerged=1`
- `cleanup_decision.blocked_by_buckets.dirty=3`
- `cleanup_decision.blocked_by_buckets.unmerged_no_pr=4`

## Verification

- `python3 -m unittest tests.test_worktree_gc -v` passed 5 tests.
- `bash -n /Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh` passed.
- `bash ~/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh` returned 0 failures, 0 warnings.
- `python3 -m unittest tests.test_worktree_gc tests.test_vidux_contracts tests.test_pr_body tests.test_publish_scrutiny tests.test_vidux_claims tests.test_release_script` passed 196 tests.
- `npm run docs:build` passed.
- Scoped `git diff --check` passed for touched Vidux, `/ai`, and `/ai-leo` files.
- `python3 scripts/vidux-publish-scrutiny.py ... --json` returned `ready=true` with invariant, regression, and adversarial review passes.

## Non-Claims

- No cleanup deletion was performed.
- No branch was removed.
- No process was killed.
- No cache, state file, memory file, log, lock, plan GC archive, or worktree mutation was performed by the dry-run proof.
- T8 remains open until Resplit worktree owners resolve or explicitly archive the non-removable buckets.

## Next-Agent Resume

Resume T8 from `projects/team-agent-coordination/PLAN.md`: use `cleanup_decision` first, then work the owner-review buckets. For the Resplit worktrees, `resplit-ios` and `resplit-web` are still `automated_removal_allowed=false`; do not delete those worktrees without owner approval.
