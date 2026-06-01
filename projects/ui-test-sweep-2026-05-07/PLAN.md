# Resplit 2.0 — iOS UI Sweep on Build 2429

> Sibling of `../resplit-2-0-1/PLAN.md` (post-launch punch-list) and `../resplit-2-0-localized-screenshots/PLAN.md` (ASC screenshots). This plan is the post-ship visual-proof harness.
> HISTORICAL / DO NOT CLAIM 2026-05-24: this Build 2429 sweep is superseded by the current T48 investigation and 2026-05-24 root plan. Current UI-test truth is `187/188` with only `ResplitUITestsLaunchTests/testLaunch()` needing focused repro; do not resume old T1-T10 rows without fresh evidence.

**Status:** [in_progress — sim-walker active for T1-T5]
**Created:** 2026-05-07T14:47Z
**Build under sweep:** 2429 (origin/main HEAD `0e1a0c32`, distributed to Friends & Family at 2026-05-07T14:05:58Z)
**Authority spec:** `firstbitelabsllc/resplit-ios:CLAUDE.md` §Visual Proof Merge Gate + §Bug Fix Discipline

## Purpose

Resplit 2.0 build 2429 shipped to Friends & Family at 10:05 EDT today. Leo's P0 directive (verbatim 2026-05-07): *"10000% clarity on ui testing and automated testing of alll features on ios."* This plan opens a comprehensive iOS UI sweep — every feature surface walked, captured in light + dark, and held against the prior baselines so any regression introduced by the 40+ commits since 2026-04-30 (19 in OCR reconciliation alone, PR #575-#600) gets caught visually before users do.

Localization Phase 2-7 work is demoted to P2 for this launch window. UI sweep is now the only P0. Bug fixes that fall out of this sweep ship under existing §Visual Proof Merge Gate + §MT-5 discipline.

## Evidence

- [Source: shipped] Build 2429 distributed to Friends & Family at 2026-05-07T14:05:58Z (origin/main HEAD `0e1a0c32`, fastlane beta cron run #N+1).
- [Source: prior baseline] `docs/autobot-evidence/baselines/2026-05-01-sim-walk-baseline/` — 12 files (6 surfaces × 2 modes), 6 days stale; covers receipt-detail, settlement, amount-editor, trip-list, folder-detail, profile.
- [Source: rebased baseline] `docs/autobot-evidence/baselines/2026-05-07-post-pr605-rebase/` — 2 files (receipt-detail only), targeted PR #605 thumbnail-fix verification.
- [Source: ASC fixed-but-unverified] AFHQMr3k (PR #605/#547 thumbnail), AD-xnx (PR #553), ABHO_hCd (PR #552), ACHQtix2 (PR #551 unassigned-items assign-blank). All four shipped a code fix; none have a fresh post-2429 visual confirmation.
- [Source: code churn] 40+ commits since 2026-04-30, 19 in OCR reconciliation alone (PR #575-#600). High blast radius across receipt-detail + amount-editor + scan flow. Diff range: `git log --oneline 0e1a0c32...HEAD@{2026-04-30}`.
- [Source: launch-arg harness] `Resplit/AppDelegate.swift` `parseUITestScenario()` + `--uiTestScenario=<scenario>` flag. Existing scenarios usable today: `screenshot-split-hero`, `screenshot-trip-settlement`, `screenshot-amount-editor-matrix`, `screenshot-folder-detail`, `screenshot-profile-walkthrough`. New scenario(s) needed for OCR reconciliation surface (T8) and Live-Split add-people (T6).
- [Source: investigations queue] `.cursor/plans/investigations/asc-pinpad-popover-cut-off-2026-04-19.md` is open; pinpad regression decision pending — T3 covers visual confirmation.
- [Source: profile-opt-in] PR #572 gates Live-Split add-people on profile opt-in flag — T6 must traverse opt-in path or skip with `[blocked]` row.
- [Source: skill stack] `/autobot-resplit` (sim driver), `/bigapple` (worktree+DerivedData isolation), `/picasso` (UI critique), `/xcodebuild-mcp` (snapshot_ui + tap-by-coord). Sweep uses XcodeBuildMCP `screenshot` tool; raw `xcrun simctl io ... screenshot` is banned per /autobot-resplit.

## Constraints

### ALWAYS

- Per CLAUDE.md `§Build Isolation Mandatory`: every sim-walker subagent uses lane-specific `-derivedDataPath /tmp/resplit-dd-uisweep-T<N>-${RANDOM}`. Never `~/Library/Developer/Xcode/DerivedData` (collides with deploy-watcher).
- Capture both **light** and **dark** mode per surface. File naming: `docs/autobot-evidence/2026-05-07-ui-sweep/T<N>-<surface>-<light|dark>.jpg`.
- Per CLAUDE.md `§Visual Proof Merge Gate`: any bug PR that falls out of this sweep ships its own BEFORE/AFTER table. The sweep itself is the BEFORE catalog for any new fix.
- Every walk uses `--uitesting --skipWalkthrough --uiTestScenario=<scenario>` launch args. Same args reused on AFTER captures so the diff is purely the fix.
- Subagents dispatched via `/superpowers:dispatching-parallel-agents` with `isolation: "worktree"` when more than one walks concurrently — per /bigapple multi-agent safety.
- Compare every captured image against the matching `2026-05-01-sim-walk-baseline` file. If no baseline exists (T8 OCR reconciliation), the 2429 capture establishes the new baseline.

### NEVER

- Skip a surface without an explicit `[blocked]` row + concrete reason (e.g., "T6 blocked: profile opt-in repro requires backend session"). Silent omission is forbidden.
- Use raw `xcodebuild`, raw `xcrun simctl io ... screenshot`, or any tool that escapes XcodeBuildMCP — per /autobot-resplit + §Build Isolation.
- Open a fix PR from this sweep without a fresh AFTER capture using the same launch args as the BEFORE.
- Touch resplit-ios in this plan-creation tick. This file (in vidux) is the only artifact written today; resplit-ios fixes ride their own PRs with `Refs: vidux/projects/ui-test-sweep-2026-05-07/PLAN.md#T<N>`.
- Re-run a walk on a surface marked `[completed]` without an MT-4 trigger (Leo report, gate fail, Sentry signal).

## Tasks

- [in_progress] T1: Receipt Detail surface walk + visual proof — verifies PR #605 thumbnail fix on build 2429
  - **Surface:** receipt-detail (item rows, totals, thumbnail, tax/tip)
  - **Why-priority P0:** PR #605 just shipped; thumbnail-fix is the highest-churn UI patch in the last 7 days; only `2026-05-07-post-pr605-rebase` has post-rebase coverage and it's only 2 files (light + dark on receipt-detail alone).
  - **Launch args:** `--uitesting --skipWalkthrough --uiTestScenario=screenshot-split-hero`
  - **Last evidence:** `2026-05-07-post-pr605-rebase/` (2 files, receipt-detail only)
  - **Recent PRs in scope:** #605, #547, #575-#600 (OCR reconciliation), #549 (settlement plumbing affects receipt totals)
  - **Pass gate:** light + dark capture; matches `2026-05-01-sim-walk-baseline/receipt-detail-{light,dark}.jpg` modulo intentional PR #605 deltas.

- [pending] T2: Settlement Sheet walk — verifies PR #549 + #548 settlement plumbing
  - **Surface:** settlement bottom sheet (per-person owed, currency conversion, "settle up" CTA)
  - **Why-priority P0:** PR #549 + #548 changed settlement state flow; FX conversion path co-changed; settlement is core 30-second-promise surface.
  - **Launch args:** `--uitesting --skipWalkthrough --uiTestScenario=screenshot-trip-settlement`
  - **Last evidence:** `2026-05-01-sim-walk-baseline/settlement-{light,dark}.jpg`
  - **Recent PRs:** #549, #548, plus FX worker rate changes via `resplit-currency-api`.
  - **Pass gate:** light + dark capture; per-person amounts unchanged; FX shows correct symbol + rate footnote.

- [pending] T3: Amount Editor / Pinpad walk — pinpad regression decision pending
  - **Surface:** amount-editor popover + pinpad keypad (tax cell, tip cell, item amount edit)
  - **Why-priority P0:** open investigation `asc-pinpad-popover-cut-off-2026-04-19.md`; pinpad has been "fixed" 22+ times historically (CLAUDE.md §Bug Fix Discipline rationale); high revert risk per MT-5 surface list.
  - **Launch args:** `--uitesting --skipWalkthrough --uiTestScenario=screenshot-amount-editor-matrix`
  - **Last evidence:** `2026-05-01-sim-walk-baseline/amount-editor-{light,dark}.jpg`
  - **Recent PRs:** any in OCR reconciliation cluster that touched edited-amount round-trip; needs `git log -- "**/EditAmountPopoverField*"` confirmation.
  - **Pass gate:** popover not clipped on either screen edge; pinpad fully on-screen; light + dark.

- [pending] T4: Trip List (Home) walk
  - **Surface:** root home / trip list view (folder rows, recent activity, FAB to start scan)
  - **Why-priority P1:** entry-point surface; if it regresses no one reaches anything else. Lower churn than T1-T3 in last 7 days but every user lands here.
  - **Launch args:** `--uitesting --skipWalkthrough --uiTestScenario=smoke-trip-folder` (per /autobot-resplit smoke pattern)
  - **Last evidence:** `2026-05-01-sim-walk-baseline/trip-list-{light,dark}.jpg`
  - **Recent PRs:** none directly targeting home, but participant color tokens may have shifted under brand-freeze guardrails.
  - **Pass gate:** light + dark capture; folder thumbnails render; FAB reachable.

- [pending] T5: Folder Detail walk
  - **Surface:** folder detail view (member chips, receipts grid, totals strip, right-column chrome)
  - **Why-priority P1:** open investigation `asc-AJiYtO9nX1Ty-folder-detail-right-column-chrome-2026-04-29.md` covers this surface; want fresh post-2429 capture before deciding whether the right-column issue still repros.
  - **Launch args:** `--uitesting --skipWalkthrough --uiTestScenario=screenshot-folder-detail`
  - **Last evidence:** `2026-05-01-sim-walk-baseline/folder-detail-{light,dark}.jpg`
  - **Recent PRs:** indirect via PR #551 (ACHQtix2 unassigned-items) — folder view is the parent surface for the assignment fix.
  - **Pass gate:** light + dark capture; right-column chrome matches baseline OR investigation gets a `[reproduced]` confirmation.

- [pending] T6: Live-Split Add-People walk — gated behind profile opt-in (PR #572)
  - **Surface:** live-split add-people sheet (contact picker, profile opt-in card, share-link CTA)
  - **Why-priority P1:** PR #572 changed the gate; opt-in flow is high-friction surface; live-split is on the §MT-5 revert-prone list.
  - **Launch args:** `--uitesting --skipWalkthrough --uiTestScenario=screenshot-live-split-add-people` (NEW scenario — needs registration in `parseUITestScenario` if missing; otherwise use closest existing scenario + manual nav)
  - **Last evidence:** none post-PR-572; if no scenario exists today, fall through to `[blocked: needs scenario]` and ride the launch-arg add into a follow-up PR.
  - **Recent PRs:** #572 (opt-in gate), plus any subsequent live-split state-flow patches.
  - **Pass gate:** light + dark capture of opt-in card + post-opt-in add-people sheet. If scenario doesn't exist, document the gap as a fix-it row for resplit-ios.

- [pending] T7: Share Sheet flow (manual)
  - **Surface:** native UIActivityViewController share for trip/receipt link
  - **Why-priority P2:** lower-churn but user-facing for the "share with co-spender" flow; manual capture only (system sheet is hard to drive headlessly).
  - **Launch args:** `--uitesting --skipWalkthrough` + manual tap to share affordance from receipt-detail.
  - **Last evidence:** none in baselines (manual surfaces excluded from sim-walk).
  - **Recent PRs:** none directly; capture establishes new baseline.
  - **Pass gate:** single capture (native sheets render the same in light + dark per system); confirm copy is the 5-word-rule compliant version.

- [pending] T8: OCR Reconciliation UI walk — NEW UITestScenario needed (no prior baseline)
  - **Surface:** OCR reconciliation view shipped via PR #575-#600 cluster (item review, severity badges, accept/edit affordances)
  - **Why-priority P0:** 19 PRs in 7 days into a brand-new UI surface; zero baseline coverage; per /ocr-moat plan this is the "moneymaker, the moat of this fucking app" (Leo verbatim 2026-05-01).
  - **Launch args:** TBD — needs new `--uiTestScenario=screenshot-ocr-reconciliation` registered in `Resplit/AppDelegate.swift` `parseUITestScenario()`. Subagent should register the scenario with a fixture-backed `ScannedReceipt` (use `Tests/Fixtures/Receipts/corpus.jsonl` golden) so the walk is deterministic.
  - **Last evidence:** none (new surface).
  - **Recent PRs:** #575, #576, #577, ..., #600 (range — full list via `git log --oneline --grep="OCR\|reconciliation"` over the 7-day window).
  - **Pass gate:** light + dark capture; new scenario lands as a follow-up PR with the `[completed]` flip on this row + scenario diff in `parseUITestScenario`.

- [pending] T9: FX Display verification (network edge case post-D8 resolve)
  - **Surface:** FX rate footer + converted-amount strip on receipt-detail and settlement
  - **Why-priority P1:** FX is on §MT-5 revert-prone list; D8 resolved a network-edge bug (per /fx skill recent log); want post-resolve capture against pre-resolve baseline.
  - **Launch args:** `--uitesting --skipWalkthrough --uiTestScenario=screenshot-trip-settlement` + `--uiTestForceCurrency=GBP` (or the equivalent currency-override flag if registered)
  - **Last evidence:** `2026-05-01-sim-walk-baseline/settlement-{light,dark}.jpg` shows FX line; capture again with same fixture.
  - **Recent PRs:** D8 fix in resplit-currency-api worker + iOS provider patch (last 7 days).
  - **Pass gate:** rate footnote matches expected, no stale "—" placeholder, light + dark.

- [pending] T10: Profile + Walkthrough walk (entry-point)
  - **Surface:** first-launch walkthrough + profile screen (avatar, display name, opt-in toggles)
  - **Why-priority P2:** entry-point UX; lower-churn but still post-2429 verification, and PR #572 profile opt-in surfaces here too.
  - **Launch args:** `--uitesting --uiTestScenario=screenshot-profile-walkthrough` (NOTE: omit `--skipWalkthrough` for the walkthrough capture; include it for the profile-only capture).
  - **Last evidence:** `2026-05-01-sim-walk-baseline/profile-{light,dark}.jpg` (profile only); walkthrough not in baseline.
  - **Recent PRs:** #572 profile opt-in; CopyTokens namespace `Walkthrough.{Hero,CTA,Setup,Demo}` may have churned.
  - **Pass gate:** four captures total — walkthrough light + dark, profile light + dark.

## Decision Log

- [DIRECTION] 2026-05-07T14:47Z — UI sweep is now P0; localization Phase 2-7 demoted to P2 (per Leo verbatim 2026-05-07: *"10000% clarity on ui testing and automated testing of alll features on ios"* during fastlane beta completion of build 2429).
- [DIRECTION] 2026-05-07T14:47Z — Brand work freezes per `/brand-resplit` skill state (FROZEN until Resplit 2.0 ships; ship occurred today but launch window remains active, brand stays frozen until `/brand-resplit` lifts the gate). Copy/simplicity discipline applies in-flight on bug-fix PRs only.
- [DIRECTION] 2026-05-07T14:47Z — Sweep is captured into `docs/autobot-evidence/2026-05-07-ui-sweep/` in resplit-ios; this plan in vidux is the **anchor**, the captures live in the iOS repo with the code that produced them.
- [DIRECTION] 2026-05-07T14:47Z — Subagents dispatched in parallel for T1-T5 use `/superpowers:dispatching-parallel-agents` with `isolation: "worktree"` per /bigapple multi-agent safety; T6-T10 sequenced after T1-T5 settle (T6 + T8 may need new launch-arg scenarios that require resplit-ios PRs).
- [DIRECTION] 2026-05-07T14:47Z — When a fix falls out of any walk, it ships its own §Visual Proof PR with both BEFORE (this sweep's capture) and AFTER (re-walk same scenario), plus an `MT-5` regression test on UI/auth/Live-Split/FX surfaces.

## Progress

- [2026-05-07T14:47Z] Plan opened post-ship of build 2429 (origin/main HEAD `0e1a0c32`, dist 2026-05-07T14:05:58Z). Sim-walker subagent slot reserved for T1 (receipt-detail walk verifies PR #605 thumbnail fix); T2-T5 queued sequentially. T6-T10 deferred until T1-T5 settle and any new launch-arg scenarios needed (T6, T8) get registered. Audit returned prioritized 10-row walk plan; 5 P0/P1 surfaces lead, 5 P1/P2 surfaces follow. ASC fixed-but-unverified backlog (AFHQMr3k, AD-xnx, ABHO_hCd, ACHQtix2) maps to T1, T2, T5, T5 respectively for fresh visual confirmation.
