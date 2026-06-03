# T8f Worktree Owner-Review Row Commands

Date: 2026-06-02 UTC

Plan: `projects/team-agent-coordination/PLAN.md`

Task: T8f

Ledger: `evt_20260602031630_t8f_owner_review_row_commands`

## Change

- `scripts/vidux-worktree-gc.py` now emits a safe per-row `review_command` for worktree rows.
- `owner_review_items` carries `review_command` in JSON.
- Text output prints `review: <command>` next to each worktree row.
- `--owner-review-markdown` adds a `Review command` column to the owner-review packet.
- Fleet-cleanup verbose Resplit dry-run rows render the same `review:` command.
- Vidux docs, fleet-cleanup docs, and the ledger quality audit now guard the field.

## Live Packet Proof

Command:

```bash
python3 scripts/vidux-worktree-gc.py --base origin/main --owner-review-markdown /Users/leokwan/Development/resplit-web
```

Selected output:

```text
- Cleanup decision: `run --apply --yes to remove merged_clean only; owner review required for non-removable buckets`
- Removable `merged_clean` worktrees: `1`
- Owner-review worktrees: `9`
| Bucket | Branch | PR | Commits not in base | Last commit | Path | Reason | Next owner action | Review command |
| closed_unmerged | fix/pricing-support-a11y-2026-05-24 | [#747](https://github.com/firstbitelabsllc/resplit-web/pull/747) | 1 | fix(a11y): Pricing h3-before-h2 + Support email-as-h2 (PR #742 follow-up) | /Users/leokwan/Development/resplit-web-worktrees/pricing-support-a11y-2026-05-24 | closed unmerged PR #747 | owner review required; archive, revive, or manually remove the abandoned branch | gh pr view 747 --json number,state,isDraft,mergeStateStatus,mergedAt,closedAt,headRefName,url,title |
| dirty | claude/csp-harden-2026-05-25 |  | 1 | feat(security): drop 'unsafe-inline' from CSP style-src [HALTED - DO NOT MERGE] | /Users/leokwan/Development/resplit-web-worktrees/csp-harden-2026-05-25 | 2 uncommitted file(s) | preserve WIP; ask the owner to commit, stash, or abandon it before cleanup | git -C /Users/leokwan/Development/resplit-web-worktrees/csp-harden-2026-05-25 status --short |
| unmerged_no_pr | codex/local-ci-token-vars |  | 1 | fix(local-ci): restore token and locale parity | /Users/leokwan/Development/resplit-web-worktrees/local-ci-token-vars | branch has commits not in base and no PR | owner review required; open a PR, merge, or archive the branch | git -C /Users/leokwan/Development/resplit-web-worktrees/local-ci-token-vars log --oneline --decorate --max-count=20 origin/main..HEAD |
```

## JSON Smoke

Command:

```bash
python3 scripts/vidux-worktree-gc.py --base origin/main --json /Users/leokwan/Development/resplit-web
```

Selected output:

```text
owner_review_keys=branch,bucket,commits_not_in_base,last_commit_subject,next_owner_action,path,pr_number,pr_url,reason,review_command
sample_review=gh pr view 747 --json number,state,isDraft,mergeStateStatus,mergedAt,closedAt,headRefName,url,title
```

## Fleet Dry-Run Proof

Command:

```bash
/Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh --dry-run
```

Selected output:

```text
- resplit-ios [dry-run]: total=8, removable=0, open_pr=4, primary=1, unmerged_no_pr=3
  - owner-review packet: python3 /Users/leokwan/Development/vidux/scripts/vidux-worktree-gc.py --base origin/main --owner-review-markdown /Users/leokwan/Development/resplit-ios
  - [open_pr] claude/ocr-key-proxy-attest-ios :: /Users/leokwan/Development/resplit-ios-worktrees/ocr-key-proxy-20260530 -- open PR #802; commits_not_in_base=3; next: review the PR; merge or close it before cleanup; review: gh pr view 802 --json number,state,isDraft,mergeStateStatus,mergedAt,closedAt,headRefName,url,title
- resplit-web [dry-run]: total=11, removable=1, closed_unmerged=1, dirty=3, merged_clean=1, open_pr=1, primary=1, unmerged_no_pr=4
  - owner-review packet: python3 /Users/leokwan/Development/vidux/scripts/vidux-worktree-gc.py --base origin/main --owner-review-markdown /Users/leokwan/Development/resplit-web
  - [closed_unmerged] fix/pricing-support-a11y-2026-05-24 :: /Users/leokwan/Development/resplit-web-worktrees/pricing-support-a11y-2026-05-24 -- closed unmerged PR #747; commits_not_in_base=1; next: owner review required; archive, revive, or manually remove the abandoned branch; review: gh pr view 747 --json number,state,isDraft,mergeStateStatus,mergedAt,closedAt,headRefName,url,title
  - [dirty] claude/csp-harden-2026-05-25 :: /Users/leokwan/Development/resplit-web-worktrees/csp-harden-2026-05-25 -- 2 uncommitted file(s); commits_not_in_base=1; next: preserve WIP; ask the owner to commit, stash, or abandon it before cleanup; review: git -C /Users/leokwan/Development/resplit-web-worktrees/csp-harden-2026-05-25 status --short
```

## Verification

- `python3 -m py_compile scripts/vidux-worktree-gc.py`: pass.
- `bash -n /Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh`: pass.
- `bash -n /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh`: pass.
- `git diff --check` across touched Vidux, `/ai`, and `/ai-leo` files: pass.
- `python3 -m unittest tests.test_worktree_gc`: 6 tests, pass.
- `python3 -m unittest tests.test_worktree_gc tests.test_vidux_contracts tests.test_pr_body tests.test_publish_scrutiny tests.test_vidux_claims tests.test_release_script`: 197 tests, pass.
- `npm run docs:build`: pass.
- `bash /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh`: 0 failures, 0 warnings.
- `python3 scripts/vidux-publish-scrutiny.py ... --task T8f ... --json`: `ready=true`.

## Self-Scrutiny

- Invariant: review commands are read-only row inspection commands; they do not expand cleanup authority.
- Regression: owner-review buckets remain non-removable; only `merged_clean` remains eligible for automatic cleanup.
- Adversarial: command text is generated with quoted argv-style command rendering and contains no branch deletion, reset, stash, or worktree removal command for non-removable rows.

## Non-Claims

- No cleanup deletion was performed.
- No branch removal was performed.
- No process kill was performed.
- No cache mutation was performed.
- No state, memory, log, lock, or plan-GC archive write was performed by the dry-run.
- No Resplit worktree mutation or owner decision was performed.

## Next Resume

Resume T8 by running the owner-review packet commands for `resplit-ios` and `resplit-web`, using each row's `review_command` to inspect PR/WIP/no-PR rows before owner decisions, and deleting only `merged_clean` rows when `cleanup_decision` allows or the owner explicitly approves.
