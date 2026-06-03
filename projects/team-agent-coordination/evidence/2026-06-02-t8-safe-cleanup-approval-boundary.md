# T8j Safe Cleanup Approval Boundary Field

## Summary

`scripts/vidux-worktree-gc.py` now makes the cleanup approval boundary machine-readable and visible in the owner-review packet:

- `safe_cleanup_items[]` includes `cleanup_approval_required=true`.
- `safe_cleanup_items[]` includes `cleanup_approval_status=required_before_apply`.
- `--owner-review-markdown` prints safe cleanup rows with an `Approval` column set to `required before apply`.
- The Markdown packet states that safe cleanup rows are read-only evidence and the apply command should run only after owner approval for the concrete paths.

## Files Claimed

- `/Users/leokwan/Development/vidux/scripts/vidux-worktree-gc.py`
- `/Users/leokwan/Development/vidux/tests/test_worktree_gc.py`
- `/Users/leokwan/Development/vidux/SKILL.md`
- `/Users/leokwan/Development/vidux/docs/reference/scripts.md`
- `/Users/leokwan/Development/vidux/guides/fleet-ops.md`
- `/Users/leokwan/Development/vidux/projects/team-agent-coordination/PLAN.md`

## Proof

```text
python3 -m py_compile scripts/vidux-worktree-gc.py
PASS

git diff --check -- scripts/vidux-worktree-gc.py tests/test_worktree_gc.py docs/reference/scripts.md guides/fleet-ops.md SKILL.md projects/team-agent-coordination/PLAN.md
PASS

python3 -m unittest tests.test_worktree_gc
Ran 6 tests in 4.444s
OK

python3 scripts/vidux-worktree-gc.py --base origin/main --json /Users/leokwan/Development/strongyes-web | python3 -c '...'
safe_cleanup_count=30
approval_statuses=required_before_apply
approval_required=true

python3 scripts/vidux-worktree-gc.py --base origin/main --owner-review-markdown /Users/leokwan/Development/strongyes-web | sed -n '/## Safe Automated Cleanup/,+14p'
PASS: packet includes "These rows are read-only evidence; run the apply command only after owner approval for these concrete paths."
PASS: packet includes "| Branch | Approval | Commits not in base | Last activity | Last commit | Path | Reason |"
PASS: safe rows render "| <branch> | required before apply | ..."

python3 -m unittest tests.test_worktree_gc tests.test_vidux_contracts tests.test_pr_body tests.test_publish_scrutiny tests.test_vidux_claims tests.test_release_script
Ran 197 tests in 118.867s
OK

npm run docs:build
PASS

bash /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh
Result: 0 failure(s), 0 warning(s)

python3 scripts/vidux-publish-scrutiny.py --json ... --task T8j ...
ready=true
```

## Non-claims

- No cleanup deletion was performed.
- No `--apply --yes` cleanup was run against StrongYes, Resplit, Vidux, or any other repo.
- No branch deletion, worktree removal, process kill, cache mutation, plan GC archive, stage, commit, push, or PR was performed.
- The new approval field is not cleanup approval; it records that owner approval is still required before applying the guarded cleanup command.

## Resume

Resume from `/Users/leokwan/Development/vidux/projects/team-agent-coordination/PLAN.md` T8. T8j is complete. T8 remains open until owner decisions resolve non-removable rows or a concrete current `merged_clean` cleanup set receives explicit owner approval.
