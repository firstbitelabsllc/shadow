# T8n Worktree Cleanup Guarded-Removal Wording

Date: 2026-06-02

## Change

T8n makes the worktree cleanup decision surface approval-safe:

- `scripts/vidux-worktree-gc.py` now emits `cleanup_decision.guarded_removal_available` and `cleanup_decision.owner_approval_required_before_apply`.
- The legacy `cleanup_decision.automated_removal_allowed` field remains for machine compatibility.
- Owner-review Markdown now renders guarded-removal and owner-approval fields instead of `Automated removal allowed`.
- Positive `merged_clean` next actions now say guarded removal is available after owner approval.
- `fleet-cleanup --dry-run` renders `guarded_removal_available=` and `owner_approval_required_before_apply=` on the cleanup-decision line.
- The recurring ledger audit now guards the fleet-cleanup skill and runner for those approval-safe fields.

## Live Read-Only Proof

`python3 scripts/vidux-worktree-gc.py --base origin/main --json /Users/leokwan/Development/strongyes-web`

```text
next_action=owner_approval_required_before_apply; owner review required for non-removable buckets guarded_removal_available=True owner_approval_required_before_apply=True cleanup_approval_status=required_before_apply legacy_automated_removal_allowed=True safe_cleanup_count=32
```

`python3 scripts/vidux-worktree-gc.py --base origin/main --owner-review-markdown /Users/leokwan/Development/strongyes-web | rg 'Guarded removal available|Owner approval required before apply|Automated removal allowed|Guarded Cleanup Candidates'`

```text
- Guarded removal available: `true`
- Owner approval required before apply: `true`
## Guarded Cleanup Candidates
```

`python3 scripts/vidux-worktree-gc.py --base origin/main /Users/leokwan/Development/strongyes-web | rg 'cleanup decision|eligible for guarded removal|eligible for automated removal'`

```text
cleanup decision: owner approval required before applying 32 merged_clean worktree(s); owner review required for 120 non-removable worktree(s)
    next: eligible for guarded removal after owner approval with --apply --yes
```

`/Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh --dry-run | rg 'strongyes-web|cleanup decision: next=.*guarded_removal_available|owner_approval_required_before_apply|safe cleanup rows:'`

```text
- strongyes-web [dry-run]: total=153, removable=32, closed_unmerged=4, dirty=11, merged_clean=32, open_pr=15, primary=1, unknown=3, unmerged_no_pr=87
  - cleanup decision: next=owner_approval_required_before_apply; owner review required for non-removable buckets; guarded_removal_available=true; owner_approval_required_before_apply=true; cleanup_approval_status=required_before_apply; removable=32; owner_review_required=120; owner-review buckets: closed_unmerged=4, dirty=11, open_pr=15, unknown=3, unmerged_no_pr=87
  - safe cleanup rows: count=32; approval_statuses=required_before_apply; approval_required=true; review owner-review packet before apply
```

## Verification

```text
python3 -m py_compile scripts/vidux-worktree-gc.py
bash -n /Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh
git diff --check -- scripts/vidux-worktree-gc.py tests/test_worktree_gc.py docs/reference/scripts.md guides/fleet-ops.md SKILL.md projects/team-agent-coordination/PLAN.md
git -C /Users/leokwan/Development/ai diff --check -- skills/fleet-cleanup/scripts/run-once.sh skills/fleet-cleanup/SKILL.md
git -C /Users/leokwan/Development/ai-leo diff --check -- skills/ledger/scripts/audit_ledger_quality.sh
python3 -m unittest tests.test_worktree_gc
python3 -m unittest tests.test_worktree_gc tests.test_vidux_contracts tests.test_pr_body tests.test_publish_scrutiny tests.test_vidux_claims tests.test_release_script
npm run docs:build
bash /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh
scripts/vidux-publish-scrutiny.py --json --lane vidux-self-improvement --task T8n --plan-path /Users/leokwan/Development/vidux/projects/team-agent-coordination/PLAN.md --proof /Users/leokwan/Development/vidux/projects/team-agent-coordination/evidence/2026-06-02-t8-worktree-cleanup-guarded-removal-wording.md --ledger evt_e6d549e0 --handoff-status done --resume 'T8 remains open for owner decisions or explicit cleanup approval; T8n is complete and no destructive cleanup was performed.' --file-claimed ... --claim T8n/worktree-cleanup-guarded-removal-wording --review-pass invariant:pass:plan-row-evidence-ledger-resume-linked --review-pass regression:pass:py-compile-bash-n-focused-6-broad-197-docs-ledger-audit --review-pass adversarial:pass:positive-automated-removal-wording-removed-from-human-surfaces
```

Results:

- Focused worktree tests: 6/6 pass.
- Broad Vidux publish suite: 197/197 pass.
- Docs build: pass.
- Ledger audit: 0 failures, 0 warnings.
- Scoped diff checks: pass across Vidux, `/Users/leokwan/Development/ai`, and `/Users/leokwan/Development/ai-leo`.
- Publish scrutiny: `ready=true`.

## Publish

- Plan row: `projects/team-agent-coordination/PLAN.md` T8n.
- Publish ledger: `evt_e6d549e0` (repairs bare emit row `evt_89e6ccd6`).
- Handoff status: done.
- Resume: T8 remains open for actual owner decisions and any explicitly approved cleanup; no cleanup approval or destructive apply happened in this slice.

## Non-Claims

No cleanup deletion, cleanup approval, `--approve-worktree-gc`, `--apply --yes`, branch removal, worktree mutation, cache mutation, state write, memory write, stage, commit, push, or PR was performed.
