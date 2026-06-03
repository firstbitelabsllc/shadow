# T8g Worktree Owner-Review Activity Evidence

Date: 2026-06-02 UTC

Plan: `projects/team-agent-coordination/PLAN.md`

Task: T8g

Ledger: `evt_20260602032811_t8g_owner_review_activity_evidence`

## Change

- `scripts/vidux-worktree-gc.py` now emits `last_commit_date` and `last_commit_age_days` for each worktree row.
- JSON `owner_review_items` carries the same activity evidence.
- Text output prints `last_commit_date=<iso>; last_commit_age_days=<n>`.
- `--owner-review-markdown` adds a `Last activity` column with date plus age.
- Fleet-cleanup verbose Resplit dry-run rows render the same activity fields.
- Vidux docs, fleet-cleanup docs, and the recurring ledger audit now guard these fields.

## Live Packet Proof

Command:

```bash
python3 scripts/vidux-worktree-gc.py --base origin/main --owner-review-markdown /Users/leokwan/Development/resplit-web
```

Observed snapshot:

```text
- Cleanup decision: `run --apply --yes to remove merged_clean only; owner review required for non-removable buckets`
- Automated removal allowed: `true`
- Removable `merged_clean` worktrees: `1`
- Owner-review worktrees: `11`
- `closed_unmerged`: `1`
- `dirty`: `4`
- `merged_clean`: `1`
- `open_pr`: `2`
- `primary`: `1`
- `removable`: `1`
- `total`: `13`
```

Selected normalized owner-review rows:

```text
| Bucket | Branch | PR | Commits not in base | Last activity | Last commit | Path | Reason | Next owner action | Review command |
| closed_unmerged | fix/pricing-support-a11y-2026-05-24 | #747 | 1 | 2026-05-24T02:43:07-04:00 (8d) | ... | /Users/leokwan/Development/resplit-web-worktrees/pricing-support-a11y-2026-05-24 | closed unmerged PR #747 | owner review required; archive, revive, or manually remove the abandoned branch | gh pr view 747 --json number,state,isDraft,mergeStateStatus,mergedAt,closedAt,headRefName,url,title |
| dirty | claude/csp-harden-2026-05-25 |  | 1 | 2026-05-25T14:10:11-04:00 (7d) | ... | /Users/leokwan/Development/resplit-web-worktrees/csp-harden-2026-05-25 | 2 uncommitted file(s) | preserve WIP; ask the owner to commit, stash, or abandon it before cleanup | git -C /Users/leokwan/Development/resplit-web-worktrees/csp-harden-2026-05-25 status --short |
| open_pr | claude/web-FM2-poll-version-guard | #919 | 1 | 2026-06-01T23:25:43-04:00 (0d) | ... | /Users/leokwan/Development/resplit-web-worktrees/fm-race-poll-guard | open PR #919 | review the PR; merge or close it before cleanup | gh pr view 919 --json number,state,isDraft,mergeStateStatus,mergedAt,closedAt,headRefName,url,title |
| unmerged_no_pr | claude/web-FA5-claim-audit |  | 1 | 2026-05-03T18:06:44-04:00 (29d) | ... | /Users/leokwan/Development/resplit-web-worktrees/FA5-claim-audit-1803 | branch has commits not in base and no PR | owner review required; open a PR, merge, or archive the branch | git -C /Users/leokwan/Development/resplit-web-worktrees/FA5-claim-audit-1803 log --oneline --decorate --max-count=20 origin/main..HEAD |
```

## JSON Smoke

Command:

```bash
python3 scripts/vidux-worktree-gc.py --base origin/main --json /Users/leokwan/Development/resplit-web
```

Selected output:

```text
owner_review_keys=branch,bucket,commits_not_in_base,last_commit_age_days,last_commit_date,last_commit_subject,next_owner_action,path,pr_number,pr_url,reason,review_command
sample_activity=2026-05-24T02:43:07-04:00,age=8
```

## Fleet Dry-Run Proof

Command:

```bash
/Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh --dry-run
```

Selected output:

```text
- resplit-ios [dry-run]: total=8, removable=0, open_pr=4, primary=1, unmerged_no_pr=3
  - [open_pr] claude/ocr-key-proxy-attest-ios :: /Users/leokwan/Development/resplit-ios-worktrees/ocr-key-proxy-20260530 -- open PR #802; commits_not_in_base=3; last_commit_date=2026-05-31T04:00:49-04:00; last_commit_age_days=1; next: review the PR; merge or close it before cleanup; review: gh pr view 802 --json number,state,isDraft,mergeStateStatus,mergedAt,closedAt,headRefName,url,title
- resplit-web [dry-run]: total=13, removable=1, closed_unmerged=1, dirty=4, merged_clean=1, open_pr=2, primary=1, unmerged_no_pr=4
  - [closed_unmerged] fix/pricing-support-a11y-2026-05-24 :: /Users/leokwan/Development/resplit-web-worktrees/pricing-support-a11y-2026-05-24 -- closed unmerged PR #747; commits_not_in_base=1; last_commit_date=2026-05-24T02:43:07-04:00; last_commit_age_days=8; next: owner review required; archive, revive, or manually remove the abandoned branch; review: gh pr view 747 --json number,state,isDraft,mergeStateStatus,mergedAt,closedAt,headRefName,url,title
  - [unmerged_no_pr] claude/web-FA5-claim-audit :: /Users/leokwan/Development/resplit-web-worktrees/FA5-claim-audit-1803 -- branch has commits not in base and no PR; commits_not_in_base=1; last_commit_date=2026-05-03T18:06:44-04:00; last_commit_age_days=29; next: owner review required; open a PR, merge, or archive the branch; review: git -C /Users/leokwan/Development/resplit-web-worktrees/FA5-claim-audit-1803 log --oneline --decorate --max-count=20 origin/main..HEAD
```

Note: Resplit worktree state changed during this slice as external lanes moved. The packet records the observed read-only snapshots and does not claim a stable inventory count.

## Verification

- `python3 -m py_compile scripts/vidux-worktree-gc.py`: pass.
- `bash -n /Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh`: pass.
- `bash -n /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh`: pass.
- `git diff --check` across touched Vidux, `/ai`, and `/ai-leo` files: pass.
- `python3 -m unittest tests.test_worktree_gc`: 6 tests, pass.
- `python3 -m unittest tests.test_worktree_gc tests.test_vidux_contracts tests.test_pr_body tests.test_publish_scrutiny tests.test_vidux_claims tests.test_release_script`: 197 tests, pass.
- `npm run docs:build`: pass.
- `bash /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh`: 0 failures, 0 warnings.
- `python3 scripts/vidux-publish-scrutiny.py ... --task T8g ... --json`: `ready=true`.

## Self-Scrutiny

- Invariant: last-activity evidence is read-only metadata derived from git history; it does not change cleanup authority.
- Regression: owner-review buckets remain non-removable, and `merged_clean` is still the only automatic cleanup class.
- Adversarial: age evidence can prioritize review, but it does not prove abandonment or authorize branch/worktree deletion.

## Non-Claims

- No cleanup deletion was performed.
- No branch removal was performed.
- No process kill was performed.
- No cache mutation was performed.
- No state, memory, log, lock, or plan-GC archive write was performed by the dry-run.
- No Resplit worktree mutation or owner decision was performed.

## Next Resume

Resume T8 by running the owner-review packet commands for `resplit-ios` and `resplit-web`; use `last_commit_date`, `last_commit_age_days`, commit count, and `review_command` together to prioritize row-level owner review; delete only `merged_clean` rows when `cleanup_decision` allows and the owner explicitly approves the live destructive cleanup action.
