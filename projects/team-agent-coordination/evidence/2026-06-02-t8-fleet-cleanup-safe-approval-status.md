# T8k Fleet-cleanup Safe Approval Status Propagation

## Summary

`fleet-cleanup --dry-run` now propagates the approval boundary emitted by `vidux-worktree-gc.py`:

- Reads `cleanup_approval_status` from `safe_cleanup_items`.
- Prints `approval_statuses=<values>` on the safe cleanup row count line.
- Prints `approval_required=<values>` so missing or false approval guards are visible.
- The recurring ledger quality audit now fails if fleet-cleanup stops documenting, reading, or rendering this approval status.

## Files Claimed

- `/Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh`
- `/Users/leokwan/Development/ai/skills/fleet-cleanup/SKILL.md`
- `/Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh`
- `/Users/leokwan/Development/vidux/projects/team-agent-coordination/PLAN.md`

## Proof

```text
bash -n /Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh
PASS

git -C /Users/leokwan/Development/vidux diff --check -- projects/team-agent-coordination/PLAN.md
git -C /Users/leokwan/Development/ai diff --check -- skills/fleet-cleanup/SKILL.md skills/fleet-cleanup/scripts/run-once.sh
git -C /Users/leokwan/Development/ai-leo diff --check -- skills/ledger/scripts/audit_ledger_quality.sh
PASS

/Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh --dry-run | sed -n '/### Worktree GC/,/### Plan GC/p'
PASS: strongyes-web Worktree GC rendered:
safe cleanup rows: count=31; approval_statuses=required_before_apply; approval_required=true; review owner-review packet before apply

bash /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh
PASS: fleet-cleanup skill documents safe cleanup approval status
PASS: fleet-cleanup reads safe cleanup approval status
PASS: fleet-cleanup renders safe cleanup approval status
Result: 0 failure(s), 0 warning(s)
```

## Non-claims

- No cleanup deletion was performed.
- No `--apply --yes` cleanup was run against StrongYes, Resplit, Vidux, or any other repo.
- No branch deletion, worktree removal, process kill, cache mutation, state write, memory write, stage, commit, push, or PR was performed.
- This change renders approval status; it does not grant cleanup approval.

## Resume

Resume from `/Users/leokwan/Development/vidux/projects/team-agent-coordination/PLAN.md` T8. T8k is complete. T8 remains open until owner decisions resolve non-removable rows or a concrete current `merged_clean` cleanup set receives explicit owner approval.
