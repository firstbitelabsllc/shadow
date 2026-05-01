> Parent: ../../PLAN.md

# T9 — Ship gate: manual `bundle exec fastlane beta` to push build 1012

**Status:** [completed] — SHIPPED 2026-05-01T15:17:49Z (build 2363, marketing 2.2.0, distributed to External testers / Friends & Family)
**Priority:** Final ship action (Sunday PM after weekend bug PRs land)
**Claim:** `claimed_by: claude-opus-4-7-rios-T9ship` `claimed_at: 2026-04-30T15:10:00Z`
**Depends on:** T1, T2, T3, T4, T5, T6, T7 all `[completed]` AND merged to main — VERIFIED 2026-04-30 (all 7 squash commits live on origin/main HEAD `b2616647`, sub-plans flipped via vidux commit `f5f8436`)
**Ship artifact:** build 2363 (CURRENT_PROJECT_VERSION) for MARKETING_VERSION 2.2.0, prior latest was 2361 (skip-by-2 increment pattern). Tuist Preview build run: `b13d0692-e34e-43e1-81d6-5e106cfe344f`. Fastlane log: `~/.agent-ledger/T9-fastlane-beta-20260501T111209.log` (4817 lines). Three success markers: altool upload @ 11:15:41, pilot Friends & Family distribution @ 11:17:49, Tuist Preview upload @ 11:18:46.

## What this task is

Run `bundle exec fastlane beta` from the resplit-ios primary worktree to:
1. Bump build number from 1011 → 1012
2. Archive Release configuration
3. Export IPA
4. Upload to App Store Connect TestFlight via altool
5. Submit to Friends & Family group for review

## Pre-flight checks (claimer MUST verify ALL before running fastlane)

- [ ] `git -C ~/Development/resplit-ios log --oneline e60a8071..origin/main | wc -l` shows >= 7 (5 bug fix commits + 2 prior docs commits already on main)
- [ ] `git -C ~/Development/resplit-ios log --oneline e60a8071..origin/main | grep -i 'fix(' | wc -l` shows >= 5 (the 5 bug-fix commits from T1-T7 — note T2 + T6 + T7 are 3 more after T1/T3/T4/T5)
- [ ] All 7 task sub-plans show `[completed]` status
- [ ] `gh pr list --repo firstbitelabsllc/resplit-ios --state open` returns empty (no in-flight bug PRs)
- [ ] `~/.agent-ledger/deploy-watcher.state` shows `LAST_UPLOAD_BUILD=1011` (we're not racing the deploy-watcher)
- [ ] Local time is daytime (not 23:00-08:00 — fastlane works any time but the autonomous deploy-watcher is gated; this is a MANUAL invocation so the gate doesn't apply, but it's a courtesy check)
- [ ] `pgrep -lx xcodebuild` returns nothing (no concurrent builds)

## Procedure

```bash
cd ~/Development/resplit-ios
killall xcodebuild SWBBuildService 2>/dev/null  # safety: clear any stragglers
bundle exec fastlane beta
```

Expected: build 1012 uploaded to TestFlight, Friends & Family invited automatically.

## Post-ship

- [x] Confirm TestFlight build 2363 appears in App Store Connect (altool returned success @ 11:15:41Z; ASC binary processing typically takes 5-15 min before visible in Friends & Family TestFlight UI)
- [x] Update master PLAN.md `## Progress` log with build SHA + ASC build ID + timestamp (this commit)
- [x] Flip T9 status to `[completed]` (this commit)
- [ ] (Optional) Self-test build 2363 in TestFlight on physical device — Leo's call. Verify T1 (receipt hero ≤220pt), T2 (settlement pill no overlap on long FX amounts), T3 (settlement card corner radius clean), T4 (folder receipt amounts at 22pt moneyMedium), T5 (tap unresolved item dismisses + scrolls), T6 (no zigzag dividers), T7 (tip row has no revert-to-scanned)
- [ ] Comment on web mega plan PR #541: "iOS lane shipped build 2363 (2.2.0) with all 7 ASC bug fixes" + Tuist Preview run b13d0692
- [ ] Tag `v2.0.0` post-ASC promotion (separate operational step, owner: Leo or interactive session — not autonomous-cron territory)

## If something goes wrong

- Build fails: surface log, do NOT retry blindly. Investigate failure (likely signing or fastlane config drift since last successful build).
- Upload fails (App Store Connect API down): wait 30 min, retry. If still failing, surface ACCESS-ALERT to Leo.
- TestFlight processing fails (Apple-side rejection): triage rejection reason, may require code change → flips back to a new task.

## Cross-references

- Master: T9 row
- Mega: PR #541
- Last ship: build 1011 at 2026-04-30T13:30:41Z on commit e60a8071
- `bundle exec fastlane beta` lane defined in `~/Development/resplit-ios/fastlane/Fastfile`
