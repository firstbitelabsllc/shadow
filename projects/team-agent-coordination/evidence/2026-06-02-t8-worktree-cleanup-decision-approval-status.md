# T8m Worktree Cleanup Decision Approval Status

Date: 2026-06-02
Lane: team-agent-coordination / T8 disk-pressure cleanup

## Change

- `scripts/vidux-worktree-gc.py` now adds top-level `cleanup_decision.cleanup_approval_required` and `cleanup_decision.cleanup_approval_status`.
- When removable `merged_clean` rows exist, `cleanup_decision.next_action` is now `owner_approval_required_before_apply` instead of telling agents to run `--apply --yes`.
- Text and Markdown owner-review output now render the decision-level approval status.
- `fleet-cleanup --dry-run` renders `cleanup_approval_status=` on the cleanup decision line.
- The fleet-cleanup skill docs and recurring ledger audit now guard this decision-level approval status.

## Live Proof

StrongYes classifier JSON smoke:

```text
next_action=owner_approval_required_before_apply; owner review required for non-removable buckets
cleanup_approval_status=required_before_apply
cleanup_approval_required=true
safe_cleanup_count=31
safe_statuses=required_before_apply
```

StrongYes text smoke:

```text
cleanup decision: owner approval required before applying 31 merged_clean worktree(s); owner review required for 121 non-removable worktree(s)
```

Fleet-cleanup dry-run smoke:

```text
- strongyes-web [dry-run]: total=153, removable=31, closed_unmerged=4, dirty=11, merged_clean=31, open_pr=16, primary=1, unknown=3, unmerged_no_pr=87
  - cleanup decision: next=owner_approval_required_before_apply; owner review required for non-removable buckets; automated_removal_allowed=true; cleanup_approval_status=required_before_apply; removable=31; owner_review_required=121; owner-review buckets: closed_unmerged=4, dirty=11, open_pr=16, unknown=3, unmerged_no_pr=87
  - safe cleanup rows: count=31; approval_statuses=required_before_apply; approval_required=true; review owner-review packet before apply
```

## Verification

- `python3 -m py_compile scripts/vidux-worktree-gc.py` PASS.
- `bash -n /Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh` PASS.
- `git diff --check -- scripts/vidux-worktree-gc.py tests/test_worktree_gc.py docs/reference/scripts.md guides/fleet-ops.md SKILL.md projects/team-agent-coordination/PLAN.md` PASS.
- `git -C /Users/leokwan/Development/ai diff --check -- skills/fleet-cleanup/scripts/run-once.sh skills/fleet-cleanup/SKILL.md` PASS.
- `git -C /Users/leokwan/Development/ai-leo diff --check -- skills/ledger/scripts/audit_ledger_quality.sh` PASS.
- `python3 -m unittest tests.test_worktree_gc` PASS, 6 tests.
- `python3 -m unittest tests.test_worktree_gc tests.test_vidux_contracts tests.test_pr_body tests.test_publish_scrutiny tests.test_vidux_claims tests.test_release_script` PASS, 197 tests.
- `npm run docs:build` PASS.
- `bash /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh` PASS, 0 failures / 0 warnings.

## Non-Claims

- No cleanup deletion was performed.
- No cleanup approval was granted.
- Did not run `--approve-worktree-gc`.
- Did not run `--apply --yes`.
- No branch removal, worktree mutation, cache mutation, state write, memory write, stage, commit, push, or PR was performed.

## Resume

T8 remains open. Next owner should continue with read-only evidence until concrete owner decisions resolve non-removable rows or explicitly approve current `merged_clean` cleanup rows.
