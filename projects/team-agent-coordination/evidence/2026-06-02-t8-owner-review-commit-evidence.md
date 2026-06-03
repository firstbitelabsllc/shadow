# T8e Worktree Owner-Review Commit Evidence

- Date: 2026-06-02
- Plan: `/Users/leokwan/Development/vidux/projects/team-agent-coordination/PLAN.md`
- Task: T8e, under active T8 disk-pressure cleanup
- Publish ledger: `evt_20260602025739_t8e_owner_review_commit_evidence`
- Scope: make read-only owner-review packets show how much branch work exists and the latest commit subject before any cleanup decision.

## What changed

- `scripts/vidux-worktree-gc.py` now records `commits_not_in_base` and `last_commit_subject` for each worktree row.
- JSON `owner_review_items`, text output, and `--owner-review-markdown` include the same commit evidence.
- `/Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh --dry-run` prints the commit evidence in verbose Resplit rows.
- Docs and recurring ledger audit guards were updated so the owner-review commit-evidence contract stays visible.

## Live packet proof

Command:

```bash
python3 scripts/vidux-worktree-gc.py --base origin/main --owner-review-markdown /Users/leokwan/Development/resplit-web
```

Selected normalized output:

```text
# Worktree Owner Review

- Repo: `/Users/leokwan/Development/resplit-web`
- Base: `origin/main`
- Cleanup decision: `owner_review_required_before_cleanup`
- Automated removal allowed: `false`
- Removable `merged_clean` worktrees: `0`
- Owner-review worktrees: `8`

| Bucket | Branch | PR | Commits not in base | Last commit | Path | Reason | Next owner action |
|---|---|---|---|---|---|---|---|
| closed_unmerged | fix/pricing-support-a11y-2026-05-24 | [#747](https://github.com/firstbitelabsllc/resplit-web/pull/747) | 1 | fix(a11y): Pricing h3-before-h2 + Support email-as-h2 (PR #742 follow-up) | /Users/leokwan/Development/resplit-web-worktrees/pricing-support-a11y-2026-05-24 | closed unmerged PR #747 | owner review required; archive, revive, or manually remove the abandoned branch |
| dirty | claude/csp-harden-2026-05-25 |  | 1 | feat(security): drop 'unsafe-inline' from CSP style-src [HALTED - DO NOT MERGE] | /Users/leokwan/Development/resplit-web-worktrees/csp-harden-2026-05-25 | 2 uncommitted file(s) | preserve WIP; ask the owner to commit, stash, or abandon it before cleanup |
| dirty | claude/web-launch-crush-20260529 | [#901](https://github.com/firstbitelabsllc/resplit-web/pull/901) | 4 | perf+chore(launch-lanes): server-SVG dividers + smoke harden + capture 8-lane plan (LN-1..57) | /Users/leokwan/Development/resplit-web-worktrees/web-launch-crush-20260529 | 1 uncommitted file(s) | preserve WIP; ask the owner to commit, stash, or abandon it before cleanup |
```

## JSON smoke

Command:

```bash
python3 scripts/vidux-worktree-gc.py --base origin/main --json /Users/leokwan/Development/resplit-web | python3 -c '...'
```

Output:

```text
owner_review_keys=branch,bucket,commits_not_in_base,last_commit_subject,next_owner_action,path,pr_number,pr_url,reason
sample=pricing-support-a11y-2026-05-24 commits_not_in_base=1 last_commit=fix(a11y): Pricing h3-before-h2 + Support email-as-h2 (PR #742 follow-up)
```

## Fleet-cleanup dry-run proof

Command:

```bash
/Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh --dry-run | sed -n '/### Worktree GC/,/### Plan GC/p' | rg -n "resplit-(ios|web)|commits_not_in_base|owner-review packet|cleanup decision"
```

Selected normalized output:

```text
5:- resplit-ios [dry-run]: total=8, removable=0, open_pr=4, primary=1, unmerged_no_pr=3
6:  - cleanup decision: next=owner_review_required_before_cleanup; automated_removal_allowed=false; removable=0; owner_review_required=7; owner-review buckets: open_pr=4, unmerged_no_pr=3
7:  - owner-review packet: python3 /Users/leokwan/Development/vidux/scripts/vidux-worktree-gc.py --base origin/main --owner-review-markdown /Users/leokwan/Development/resplit-ios
8:  - [open_pr] claude/asc-intake-AAZMm-ADyJj6-2026-05-24 :: /Users/leokwan/Development/resplit-ios-worktrees/aazmm-avatar-fix -- open PR #740; commits_not_in_base=4; last_commit=docs(investigation): asc-AAZMm Phase C partial - MT-5 test compile-verified, runtime deferred (cycle 1779629585); next: review the PR; merge or close it before cleanup
15:- resplit-web [dry-run]: total=9, removable=0, closed_unmerged=1, dirty=3, primary=1, unmerged_no_pr=4
16:  - cleanup decision: next=owner_review_required_before_cleanup; automated_removal_allowed=false; removable=0; owner_review_required=8; owner-review buckets: closed_unmerged=1, dirty=3, unmerged_no_pr=4
17:  - owner-review packet: python3 /Users/leokwan/Development/vidux/scripts/vidux-worktree-gc.py --base origin/main --owner-review-markdown /Users/leokwan/Development/resplit-web
18:  - [closed_unmerged] fix/pricing-support-a11y-2026-05-24 :: /Users/leokwan/Development/resplit-web-worktrees/pricing-support-a11y-2026-05-24 -- closed unmerged PR #747; commits_not_in_base=1; last_commit=fix(a11y): Pricing h3-before-h2 + Support email-as-h2 (PR #742 follow-up); next: owner review required; archive, revive, or manually remove the abandoned branch
19:  - [dirty] claude/csp-harden-2026-05-25 :: /Users/leokwan/Development/resplit-web-worktrees/csp-harden-2026-05-25 -- 2 uncommitted file(s); commits_not_in_base=1; last_commit=feat(security): drop 'unsafe-inline' from CSP style-src [HALTED - DO NOT MERGE]; next: preserve WIP; ask the owner to commit, stash, or abandon it before cleanup
21:  - [dirty] claude/web-launch-crush-20260529 :: /Users/leokwan/Development/resplit-web-worktrees/web-launch-crush-20260529 -- 1 uncommitted file(s); commits_not_in_base=4; last_commit=perf+chore(launch-lanes): server-SVG dividers + smoke harden + capture 8-lane plan (LN-1..57); next: preserve WIP; ask the owner to commit, stash, or abandon it before cleanup
```

## Verification

- `python3 -m py_compile scripts/vidux-worktree-gc.py` passed.
- `bash -n /Users/leokwan/Development/ai/skills/fleet-cleanup/scripts/run-once.sh` passed.
- `bash -n /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh` passed.
- Scoped `git diff --check` passed for touched Vidux files.
- Scoped `git diff --check` passed for touched `/Users/leokwan/Development/ai` files.
- Scoped `git diff --check` passed for touched `/Users/leokwan/Development/ai-leo` files.
- Live owner-review markdown proof passed and showed the new columns.
- Live JSON smoke passed and showed `commits_not_in_base` plus `last_commit_subject`.
- Fleet-cleanup dry-run proof passed and showed Resplit commit evidence plus owner-review packet commands.
- `python3 -m unittest tests.test_worktree_gc` passed: 6 tests.
- `python3 -m unittest tests.test_worktree_gc tests.test_vidux_contracts tests.test_pr_body tests.test_publish_scrutiny tests.test_vidux_claims tests.test_release_script` passed: 197 tests.
- `npm run docs:build` passed.
- `bash /Users/leokwan/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh` passed: 0 failures, 0 warnings.
- `python3 scripts/vidux-publish-scrutiny.py ... --task T8e ... --json` returned `ready=true` with plan, proof, ledger, file claims, resume, and invariant/regression/adversarial review passes present.

## Self-scrutiny

- Invariant: commit evidence is read-only context for owner review. It does not expand automatic removal beyond `merged_clean`.
- Regression: dirty, open PR, closed-unmerged, and unmerged-no-PR rows remain in owner-review buckets with explicit next-owner actions.
- Adversarial: commit subjects can carry policy signals such as "HALTED - DO NOT MERGE"; the packet now surfaces that signal before cleanup, and still leaves the decision with the owner.

## Non-claims

- No cleanup deletion was performed.
- No branch was removed.
- No process was killed.
- No cache, state, memory, log, lock, plan-GC archive, or worktree state was mutated by the dry-run proof.
- No owner decision was made for `resplit-ios` or `resplit-web`; T8 remains open.

## Next resume

Run the owner-review packet commands for `resplit-ios` and `resplit-web`, use `commits_not_in_base` and `last_commit_subject` to prioritize owner decisions, and delete only `merged_clean` rows when `cleanup_decision.automated_removal_allowed=true` or when the owner explicitly approves a manual cleanup path.
