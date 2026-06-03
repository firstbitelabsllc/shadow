# T8l Fleet-cleanup Worktree Apply Approval Gate

## Summary

`fleet-cleanup` no longer reaches the worktree removal path during ordinary non-dry-run cycles. Worktree GC is now classification-only by default, and the guarded `vidux-worktree-gc.py --json --apply --yes` path is reachable only with `--approve-worktree-gc` after owner approval for the concrete `merged_clean` rows.

## Files Claimed

- `/Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh`
- `/Users/leokwan/Development/ai/skills/fleet-cleanup/SKILL.md`
- `/Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh`
- `/Users/leokwan/Development/vidux/projects/team-agent-coordination/PLAN.md`

## Proof

```text
bash -n /Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh
PASS

/Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh --help | rg -n -- '--approve-worktree-gc|classification-only|Worktree GC'
PASS: help documents --approve-worktree-gc and classification-only Worktree GC.

git -C /Users/leokwan/Development/vidux diff --check -- projects/team-agent-coordination/PLAN.md
git -C /Users/leokwan/Development/ai diff --check -- skills/fleet-cleanup/SKILL.md skills/fleet-cleanup/scripts/run-once.sh
git -C /Users/leokwan/Development/ai-leo diff --check -- skills/ledger/scripts/audit_ledger_quality.sh
PASS

/Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh --dry-run | sed -n '/### Worktree GC/,/### Plan GC/p'
PASS: dry-run still renders Worktree GC and strongyes-web approval status:
safe cleanup rows: count=32; approval_statuses=required_before_apply; approval_required=true; review owner-review packet before apply

rg -n -- 'APPROVE_WORKTREE_GC=false|--approve-worktree-gc|elif \$APPROVE_WORKTREE_GC; then|\[approval-required\]|--json --apply --yes' ...
PASS: default approval is false, approval flag exists, apply branch is gated by APPROVE_WORKTREE_GC, and default non-dry-run classification is labeled [approval-required].

bash /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh
PASS: fleet-cleanup skill documents explicit worktree apply approval flag
PASS: fleet-cleanup defaults worktree apply approval off
PASS: fleet-cleanup exposes explicit worktree apply approval flag
PASS: fleet-cleanup gates worktree apply behind explicit approval
PASS: fleet-cleanup labels default non-dry-run worktree classification
Result: 0 failure(s), 0 warning(s)
```

## Non-claims

- No cleanup deletion was performed.
- No `--approve-worktree-gc` or `--apply --yes` cleanup was run.
- No branch deletion, worktree removal, process kill, cache mutation, state write, memory write, stage, commit, push, or PR was performed.
- This change makes the apply path require explicit approval; it does not grant cleanup approval.

## Resume

Resume from `/Users/leokwan/Development/vidux/projects/team-agent-coordination/PLAN.md` T8. T8l is complete. T8 remains open until owner decisions resolve non-removable rows or a concrete current `merged_clean` cleanup set receives explicit owner approval.
