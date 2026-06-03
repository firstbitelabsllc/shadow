# T8h Safe Cleanup Row Evidence

Date: 2026-06-02
Lane: team-agent-coordination
Plan row: T8h
Ledger eid: evt_20260602034148_t8h_safe_cleanup_row_evidence

## Change

- `scripts/vidux-worktree-gc.py` now emits `safe_cleanup_items` in JSON for exact removable `merged_clean` rows.
- `--owner-review-markdown` now keeps `owner_review_items` as non-removable-only and adds a `Safe Automated Cleanup` table only when removable rows exist.
- Vidux docs now describe the owner-review packet as both non-removable review evidence and guarded-cleanup row evidence.

## Proof

- PASS: `python3 -m py_compile scripts/vidux-worktree-gc.py`
- PASS: `git diff --check -- scripts/vidux-worktree-gc.py tests/test_worktree_gc.py docs/reference/scripts.md guides/fleet-ops.md SKILL.md projects/team-agent-coordination/PLAN.md`
- PASS: `python3 -m unittest tests.test_worktree_gc` - 6 tests.
- PASS: `python3 -m unittest tests.test_worktree_gc tests.test_vidux_contracts tests.test_pr_body tests.test_publish_scrutiny tests.test_vidux_claims tests.test_release_script` - 197 tests.
- PASS: `npm run docs:build`
- PASS: `bash ~/Development/ai-leo/skills/ledger/scripts/audit_ledger_quality.sh` - 0 failures, 0 warnings.
- PASS: `python3 scripts/vidux-publish-scrutiny.py ...` - `ready=true`.

## Live Snapshot

Command:

```bash
python3 scripts/vidux-worktree-gc.py --base origin/main --json /Users/leokwan/Development/resplit-web
```

Result snapshot:

- `total=12`
- `removable=0`
- `safe_cleanup_items=[]`
- `owner_review_required_count=11`
- `blocked_by_buckets={"closed_unmerged":1,"dirty":3,"open_pr":3,"unmerged_no_pr":4}`
- `cleanup_decision.next_action=owner_review_required_before_cleanup`

Command:

```bash
python3 scripts/vidux-worktree-gc.py --base origin/main --owner-review-markdown /Users/leokwan/Development/resplit-web
```

Result snapshot:

- Packet listed 11 owner-review rows.
- Packet did not print `## Safe Automated Cleanup` because no Resplit Web `merged_clean` worktree was currently removable.
- Focused fixture tests covered the positive case where one `merged_clean` row appears in `safe_cleanup_items` and the Markdown safe-cleanup table.

## Self-Scrutiny

- Invariant: `owner_review_items` remains non-removable-only; `safe_cleanup_items` contains only rows where `worktree.removable` is true.
- Regression: apply behavior is unchanged; `--apply --yes` still removes only `merged_clean` worktrees and protects primary/invocation checkouts.
- Adversarial: a removable count or safe-cleanup table is still read-only evidence, not approval to delete. No cleanup apply, branch removal, process kill, cache mutation, state write, memory write, log write, lock write, plan GC archive, Resplit worktree mutation, or owner decision was performed.

## Next-Agent Resume

Resume T8 from `projects/team-agent-coordination/PLAN.md`. Use `--owner-review-markdown` or JSON `owner_review_items` plus `safe_cleanup_items` to inspect concrete worktree paths before any destructive cleanup approval. T2 remains open for non-deferred Resplit loop proof; T8 remains open until owners resolve non-removable rows or explicitly approve cleanup for current `merged_clean` rows.
