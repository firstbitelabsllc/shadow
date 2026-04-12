# Draft-PR Flow — Fleet Push Behavior Audit

**Date:** 2026-04-11
**Source:** grep of `~/.claude/automations/*/prompt.md` and `~/.codex/automations/*/automation.toml`

## Summary

| Metric | Count |
|---|---|
| Total Claude lanes | 35 |
| Total Codex observers | 2 |
| Lanes mentioning push/PR/origin patterns | 20 |
| Lanes explicitly prohibiting push ("NEVER push") | 5 |
| Lanes silent on pushing | 15 |
| Lanes currently using `gh pr create` | **0** |
| Active CronCreate schedules | **0** (no scheduled_tasks.json) |

**Key finding:** Zero lanes currently create draft PRs. The fleet either pushes to branches (without PRs) or doesn't push at all. Phase 5 introduces `gh pr create --draft` as a net-new operation.

**Scope correction:** PLAN.md said "14 fleet automations." The real count is **35 Claude lanes + 2 Codex observers = 37 total.** Of these, ~20 are push-capable (the Phase 5 migration scope).

## Lanes with push-related patterns (20)

These mention `git push`, `gh pr create`, `origin/main`, `push.*remote`, or `push.*origin` in their prompt.md.

| Lane | Project |
|---|---|
| resplit-2-cloudkit-lint | resplit |
| resplit-2-fleet-watch | resplit |
| resplit-2-ocr-actor | resplit |
| resplit-2-orchestrator | resplit |
| resplit-2-receipts-repo | resplit |
| resplit-bug-fixer | resplit |
| resplit-deploy-watcher | resplit |
| resplit-fleet-watch | resplit |
| resplit-revamp-executor | resplit |
| resplit-web-executor | resplit |
| strongyes-backend-trust | strongyes |
| strongyes-blog-pipeline | strongyes |
| strongyes-coach-p0 | strongyes |
| strongyes-creative-direction | strongyes |
| strongyes-deploy-sweep | strongyes |
| strongyes-feature-audit | strongyes |
| strongyes-fleet-watch | strongyes |
| vidux-codex-experiment | vidux |
| vidux-core-test | vidux |
| vidux-draft-pr | vidux |

## Lanes explicitly prohibiting push (5)

| Lane | Type |
|---|---|
| vidux-draft-pr | Writer (new — has "NEVER push without Leo authorization") |
| strongyes-fleet-watch | Fleet watch |
| resplit-revamp-director | Director |
| strongyes-deploy-sweep | Deploy sweep |
| strongyes-backend-trust | Backend |

## Lanes silent on pushing (15)

| Lane | Project |
|---|---|
| resplit-2-codex-migration | resplit |
| resplit-2-photo-labels | resplit |
| resplit-2-r2-backend | resplit |
| resplit-2-sideload-auth | resplit |
| resplit-2-sideload-ui | resplit |
| resplit-r2-sideload | resplit |
| resplit-revamp-a11y | resplit |
| resplit-revamp-brand | resplit |
| resplit-revamp-research | resplit |
| resplit-revamp-visual | resplit |
| resplit-sidecar-rotation | resplit |
| resplit-web-director | resplit |
| resplit-web-visual | resplit |
| strongyes-research | strongyes |
| vidux-codex-experiment | vidux |

## Codex DB (2 observers, both read-only)

| ID | Status |
|---|---|
| vidux-core-test-observer | ACTIVE |
| vidux-codex-experiment-observer | ACTIVE |

## Implications for Phase 5

1. **No lane currently creates PRs.** `gh pr create --draft` is a net-new operation across the entire fleet.
2. **~20 lanes are push-capable.** These are the Phase 5 migration candidates.
3. **~15 lanes never push.** These can be skipped in Waves 1-3 (they don't need draft-PR mechanics because they don't push).
4. **5 lanes already prohibit pushing.** These may need the prohibition updated to "push to branch + draft PR" instead of "NEVER push."
5. **Zero active CronCreate schedules.** The fleet is dormant — lanes have prompt.md files but no recurring schedule. Phase 5 Wave 1 needs to ALSO schedule the pilot lane (via CronCreate) for it to actually fire.
6. **The Codex-to-Claude migration is effectively complete.** Only 2 Codex observers remain; all 35 writer/scanner/executor lanes are Claude automations.
