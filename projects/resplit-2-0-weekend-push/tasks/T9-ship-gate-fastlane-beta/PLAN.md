> Parent: ../../PLAN.md

# T9 — Ship gate: manual `bundle exec fastlane beta` to push build 1012

**Status:** [in_progress] — fastlane beta firing
**Priority:** Final ship action (Sunday PM after weekend bug PRs land)
**Claim:** `claimed_by: claude-opus-4-7-rios-T9ship` `claimed_at: 2026-04-30T15:10:00Z`
**Depends on:** T1, T2, T3, T4, T5, T6, T7 all `[completed]` AND merged to main — VERIFIED 2026-04-30 (all 7 squash commits live on origin/main HEAD `b2616647`, sub-plans flipped via vidux commit `f5f8436`)

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

- [ ] Confirm TestFlight build 1012 appears in App Store Connect
- [ ] Update master PLAN.md `## Progress` log with build SHA + ASC build ID + timestamp
- [ ] Flip T9 status to `[completed]`
- [ ] (Optional) Self-test build 1012 in TestFlight on physical device — verify each of T1-T7 fixes are present
- [ ] Comment on web mega plan PR #541: "iOS lane shipped build 1012 with all 8 ASC bug fixes" + ASC build ID

## If something goes wrong

- Build fails: surface log, do NOT retry blindly. Investigate failure (likely signing or fastlane config drift since last successful build).
- Upload fails (App Store Connect API down): wait 30 min, retry. If still failing, surface ACCESS-ALERT to Leo.
- TestFlight processing fails (Apple-side rejection): triage rejection reason, may require code change → flips back to a new task.

## Cross-references

- Master: T9 row
- Mega: PR #541
- Last ship: build 1011 at 2026-04-30T13:30:41Z on commit e60a8071
- `bundle exec fastlane beta` lane defined in `~/Development/resplit-ios/fastlane/Fastfile`
