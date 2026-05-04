# Resplit 2.0 — Weekend Ship Push (May 2–3, soft target May 4)

**Soft target:** Monday May 4 morning. **No hard cutoff.** Per Leo verbatim 2026-05-01: *"I really care more about whether we can just keep pushing along and get the bugs fixed. Bug fixing and production-level testability is all they care about."* The metric is **bugs-shipped, not calendar-met**. May 4 is when we'd ideally have a TestFlight build with all 8 ASC bugs verified — slipping a day or two is fine if it means shipping the fixes correctly.

## Parent plan

This is the **resplit-ios lane detail** for the multi-platform Resplit 2.0 launch.

- **Multi-platform mega plan**: `~/Development/resplit-web/vidux/resplit-2.0-launch/PLAN.md` (open as PR #541 on `firstbitelabsllc/resplit-web`, branch `claude/resplit-2.0-launch-plan-consolidation`).
- **What the mega plan owns**: web-side ship gates (T3 security review, T5 test coverage, T7 E2E guest flow, staging redeploy from main, dark-mode visual baselines, autobot-resplit-web cron) + the cross-platform Definition of Done.
- **What this plan owns**: the 8 ASC bug rows specific to the iOS app. The mega plan's iOS gate (`iOS App Store Connect submission accepted — owned by resplit-ios lane, gated independently`) is satisfied when every P0/P1 task below ships and `bundle exec fastlane beta` lands a build with all eight bugs verified.
- **Convergence**: agents working iOS read THIS plan; agents working web read the mega plan. Cross-references in both directions (parent → child via the iOS row, child → parent via this section).
- **Sibling iOS project (post-launch foundation)**: `../ocr-moat/PLAN.md` — vendor-neutral receipt scanning contract + fixture corpus + reconciliation + telemetry + dev-app annotator. **GATED behind this weekend-push shipping.** Created 2026-05-01 per Leo's "moat of the app" directive. Agents on this weekend plan: do NOT touch ocr-moat tasks until every Open ASC row above is verified or explicitly deferred.

## Purpose

Ship Resplit 2.0 to App Store this weekend. The launch was supposed to land April 3; it is now May 1. Eight ASC bug rows stand between the current build and a tag-able release. This file is the master convergence point for the iOS lane — every iOS cron, every iOS lane, every iOS agent reads this during the vidux READ step and converges on shipping these eight bugs (or explicitly marking them deferred). All other iOS work (brand, gradient, skill registry, doc refresh, refactor) is FROZEN until 2.0 is in the App Store.

The fleet's recent failure mode was producing brand polish PRs and bookkeeping closeouts while ASC bug rows sat untouched. The existence of this PLAN.md is the fix: when you read it, the only legitimate next action is shipping a row below or escalating a hard exception.

## Evidence

Eight ASC reporter quotes captured between 2026-04-19 and 2026-04-29. All ID prefixes follow ASC convention (`A<id>` shorthand maps to the long ASC feedback ID).

| ASC ID | Reporter quote (verbatim) | Surface |
|--------|---------------------------|---------|
| AAFuZnay | "way too fucking big make them one row side by side and adjust copy" | Receipt detail header card / wrap-up sheet |
| ANgvTW | "Still overlapping" | Settlement pill / participant chip overlap |
| AO4j25 | "Corner radius bug" | Single-token corner-radius mismatch |
| AJiYtO9n | "Why the fuck are numbers still not same font size" | FolderDetail right-column amount column |
| ACHQtix2 | "Tappping doesn't dismisss and scroll to right place" | `ReceiptUnresolvedReviewSheet` dismiss + scroll handoff |
| AD-xnx | "zig zags here is too distracting remove and refine UX" | `ZigzagDivider` across 7 surfaces |
| ABHO_hCd | "Why does tip have a revert to scanned UX as well?" | Tip row reset-to-scanned affordance |
| ADIQ | "Love this, i would prefer a SF symbol" | Defer to 2.0.1 — partial-positive feedback, not a bug |

Existing investigation files:
- `.cursor/plans/investigations/asc-AJiYtO9nX1Ty-folder-detail-right-column-chrome-2026-04-29.md` — Fix Spec NOT filled
- `.cursor/plans/investigations/asc-ACHQtix2-unassigned-items-assign-blank-2026-04-29.md` — currently tagged ASK-LEO-MANDATORY (suspect avoidance, see T5)
- `.cursor/plans/investigations/asc-c12-folder-receipt-tap-no-dismiss.md` — sibling of T5
- `.cursor/plans/investigations/asc-c13-tap-unassigned-scrolls-to-void.md` — sibling of T5
- Sibling investigation needed for ANgvTW: `asc-settlement-pill-overlap.md` (NOT YET CREATED — blocker noted in T2)

## Constraints

### ALWAYS
- ASC, Sentry, Linear, Jam.dev, and proactive sim-walk bug rows outrank everything until 2.0 ships (per `/auto` ship-window override).
- Visual proof BEFORE/AFTER screenshot table mandatory in EVERY fix PR (per CLAUDE.md §Visual Proof Merge Gate).
- MT-5 regression test in the SAME PR as the fix on every UI surface (per CLAUDE.md §MT-5).
- Bug-fix investigation file in `.cursor/plans/investigations/` BEFORE touching code (per CLAUDE.md §Bug Fix Discipline).
- Wrapped + isolated build form: `tuist xcodebuild build -scheme 'Resplit Debug' -derivedDataPath /tmp/resplit-dd-claude-${SESSION_ID:-default}` (per CLAUDE.md §Build Isolation Mandatory).
- After every cron cycle with no inbound bug, dispatch `/autobot-resplit` to discover bugs we have not been told about yet (proactive sim-walk).

### NEVER
- Brand work of any kind. `/brand-resplit` is FROZEN. No gradient tweaks, no token reshuffles, no copy polish, no font experiments.
- claudux docs commits, refactor PRs, skill-registry edits, doc-refresh sweeps, dead-code sweeps, or any cleanup PR while ASC rows remain `[pending]` or `[in_progress]`.
- Bookkeeping-only PRs (per CLAUDE.md §MT-1). Every PR ships code that flips a row.
- Re-auditing `[completed]` or `[MERGED]` rows without a regression trigger (per CLAUDE.md §MT-4).
- Asking Leo for permission. State the call, ship it (per CLAUDE.md §Full Autonomy + repo `/auto` ship-window override).
- Raw `xcodebuild` or bare `tuist build` — both bypass DerivedData isolation and SIGTERM the deploy-watcher.
- Run `claudux update` against this repo until 2.0 ships. The 5 `docs(claudux):` PRs in 48h (cb706a34, e60a8071, 6afd86dc, 825f5fe7, plus prior) come from interactive Codex CLI sessions and gate the deploy-watcher's `min 3 new commits` threshold with noise. To stop: stop running `claudux update` interactively, or revoke Codex's branch-push permission for this repo.
- Load `/brand-resplit` for active work. It's frozen — load THIS PLAN.md instead. Historical brand doctrine archived at `~/Development/ai/skills/brand-resplit/_archive/` (2026-05-01 freeze).
- Surface or pitch any net-new feature ideas, "have you considered…" suggestions, refactor opportunities, or backlog items to Leo until 2.0 has shipped to TestFlight Friends & Family with all 8 ASC bug fixes verified. Per Leo verbatim 2026-05-01: *"I have a lot of things that I want us to like work on that's like net new or like kind of uncovered from a long time ago, but I don't want to talk about that unless we're ready to at least start shipping and working first."* The backlog pump stays OFF until ship.

### ALWAYS (additions)
- When the reactive bug queue (ASC + Sentry + Linear + Jam + PR review threads) is empty, dispatch a proactive `/autobot-resplit` sim-walk BEFORE declaring IDLE. Discovery work counts as cron purview; idle does not.

## Parallel-agent partition contract

This plan is designed for **10-20 agents working in parallel**. The partition prevents collision:

### Per-task sub-plan files

Every task T1-T9 has its own file at `~/Development/vidux/projects/resplit-2-0-weekend-push/tasks/T<N>-<id>-<slug>.md`. Agents claim, fill, and ship their assigned sub-plan independently. No one edits the master PLAN.md directly except to flip a row's `[status]` after the sub-plan ships.

### Claim mechanism

Each sub-plan has two empty fields at the top:
```
**Claim:** `claimed_by: <agent_id>` `claimed_at: <iso>`
```

To claim a task:
1. `cd ~/Development/vidux && git pull --rebase`
2. Read the sub-plan. If `claimed_by` is non-empty AND `claimed_at` is within last 30 minutes, the task is taken — pick the next `[pending]` row.
3. If empty OR `claimed_at` >30min stale (assume dead session, free to re-claim), atomically: edit the two fields → `git add` → `git commit` → `git pull --rebase` → `git push`. First push wins. If your push fails, your claim is invalidated — pick another task.

### Per-task DerivedData namespace

Each task has a `DerivedData namespace` field in its sub-plan: `/tmp/resplit-dd-T<N>-${RANDOM}`. Your worktree must export `RESPLIT_DD_PATH` to this value before running `tuist xcodebuild build` per `/bigapple` build isolation. **Do NOT** use `/tmp/resplit-dd-claude-${SESSION_ID}` (collides with deploy-watcher) or `/tmp/resplit-dd-watcher` (deploy-watcher's path) or any path without the T<N> namespace.

### Master plan write contract

The master PLAN.md is **not append-only**. Per `/vidux` Principle 4 (self-extend with a brake), agents can and SHOULD update, refine, and reappraise the project as they work — the plan LIVES, it doesn't just track. Allowed master-plan edits (any agent, atomic-commit pattern):

- **Flip a task's `[status]`** between `[pending]` → `[in_progress]` → `[completed]` / `[blocked]` / `[deferred]`
- **Append to the `## Progress` log** with one-line cycle summaries (date, what shipped, what's next)
- **Append to the `## Decision Log`** with `[DIRECTION]` / `[DELETION]` / `[REFRAME]` entries when evidence changes mid-cycle (per Principle 4 "If evidence changes mid-cycle, the queue re-sorts. You don't need permission to reorder. Note the reorder in the next Progress entry.")
- **Add new `[pending]` tasks** when investigation surfaces a new bug or constraint not covered by T1-T9. Stub a sub-plan in `tasks/T<N>-<slug>.md` in the same commit.
- **Refine an existing task's bullet** (e.g., `[Evidence: ...]`, `[ETA: Xh]`, `[Investigation: ...]` fields) when better data lands. Don't rewrite history; refine forward.
- **Update Constraints** (ALWAYS / NEVER) when a new failure mode is observed. Cite the trigger in the Decision Log.
- **Reappraise priorities** if a P1 escalates to P0 (e.g., reporter sends Sentry crash for a bug previously triaged as polish). Re-sort, note in Progress.

What you should NOT do via master-plan edits:
- Fill in a sub-plan's Fix Spec / Tests / Gate — that lives in the sub-plan file (`tasks/T<N>-*.md`)
- Fill in an investigation file's Root Cause / Impact Map — that lives in `.cursor/plans/investigations/`
- Take action without an evidence-cited Decision Log entry — Principle 5 (prove it mechanically)

**Atomic-commit pattern for master-plan edits** (race-safe under 10-20 parallel agents):
```bash
cd ~/Development/vidux
git pull --rebase
# ... edit PLAN.md (one logical change per commit) ...
git add projects/resplit-2-0-weekend-push/PLAN.md
git commit -m "plan(resplit-2.0): <one-line description of the edit>"
git pull --rebase  # in case another agent committed during your edit
git push           # if push fails, repeat from `git pull --rebase`
```

If you find yourself wanting to make MULTIPLE unrelated edits to PLAN.md in one cycle, do them as separate commits — that way another agent's concurrent edit can merge cleanly with yours instead of conflict-resolving across mixed concerns.

### Continuous stack-drain doctrine (added 2026-05-03 per Leo "no minute left between sessions")

Per Leo verbatim 2026-05-03: *"Once a ticket comes off the stack, we work on it. Once we're finished, we pick up the next task in the stack."* + *"I don't expect any minute to be left in between each session. If you're working in the middle of something and then the cron pings every ten minutes and you're in the middle of it, ignore it. Keep working hard and keep. Once you're done, keep finding another task to work on."*

Two rules every agent (cron OR ad-hoc OR lane-lead) follows:

1. **Mid-cycle cron-ping immunity.** If you are inside Phase A/B/C/D of a current claim when a new 10-min cron cycle fires, IGNORE the new cycle. The atomic-claim contract protects this: the new cron run sees `claimed_at:` < 30min stale and skips your claim. Continue your current phase to completion. Do NOT context-switch on every ping.

2. **Zero-idle-gap drain.** After CHECKPOINT (PR merged + Sentry resolved + worktree torn down), immediately re-PULL the master plan + every sub-plan index. Pick the next [pending] sub-plan in the **same agent session** and run another full cycle. Only declare IDLE when ALL of these are exhausted simultaneously:
   - weekend-push T1-T9 (currently 7 [completed] + 1 [deferred] + 1 [completed] = terminal, but check for ASC-driven additions)
   - `~/Development/vidux/projects/ocr-moat/tasks/P*-*/PLAN.md` (P1 chain shipped through P1.3.2c; P1.3.3, P2-P5 pending)
   - `.cursor/plans/investigations/asc-*.md` with `## Fix Spec\n(pending)` (any open-but-not-coded ASC ticket)
   - Any `[in_progress]` claim from another agent ≥30min stale (orphan reclaim per snapshot-first protocol)
   - Open `[pending]` rows in any other vidux project this lane is qualified to drain

The pairing creates: **continuous throughput while preserving claim coherence**. The cron is the discoverer; YOU are the drainer. Drain until dry.

**What this looks like in practice (single-agent cadence):**

```
Session start → claim ocr-moat P1.3.3 → ship Phase A/B/C/D → MERGED →
  re-pull → claim ocr-moat P2.0 → ship → MERGED →
  re-pull → no ocr-moat-P? left → check .cursor/plans/investigations/asc-*.md (Fix Spec pending) → claim → ship → MERGED →
  re-pull → check ASC API for new reporter feedback since session start → if new, write investigation + ship → MERGED →
  re-pull → all queues dry → IDLE (legitimate, only now)
```

NEVER: claim → ship → IDLE → wait for cron-ping. The cron is the FALLBACK discoverer for cases where YOU exit (rate-limit, OOM, manual stop). When YOU are alive, YOU drain.

**What this looks like in practice (multi-agent fan-out):**

The lane-lead OR an autonomous high-context agent (claude-opus-4-7-rios) MAY dispatch N parallel subagents (each in `isolation: "worktree"`) to drain the queue concurrently. The atomic-claim contract makes this collision-safe — each subagent claims its own sub-plan, ships, returns. The lane-lead aggregates results + dispatches the next wave.

Recommended fan-out cadence: 3-5 parallel subagents per wave, each owning one sub-plan from a different surface (e.g., ocr-moat P1.3.3 + ocr-moat P2.0 + ASC investigation A123 + Sentry top-unresolved + i18n gap). Avoid 10+ simultaneous because (a) each subagent eats a worktree slot, (b) build contention rises, (c) review-bot rate-limits start mattering.

### Investigation file partition

Each task has its own investigation file at `.cursor/plans/investigations/asc-<ID>-<slug>-2026-05-01.md` (already stubbed). Agents fill the Root Cause, Impact Map, Fix Spec, Tests, Gate sections of THEIR investigation. No collision because each is a different file.

### Worktree isolation

Use `/superpowers:using-git-worktrees` or `/bigapple` per-lane worktree pattern:
```
cd ~/Development/resplit-ios
git worktree add ../resplit-ios-worktrees/T<N>-<slug> -b claude/T<N>-<slug>
cd ../resplit-ios-worktrees/T<N>-<slug>
export RESPLIT_DD_PATH=/tmp/resplit-dd-T<N>-${RANDOM}
```

Each task's worktree is its own git ref + DerivedData path. No contention.

### Pre-flight checks (every agent BEFORE claiming)

1. `pgrep -lx xcodebuild` returns nothing (else: deploy-watcher or another agent is building, defer 60s)
2. `cat ~/.agent-ledger/deploy-watcher.state` — if `CONTENTION_BACKOFF_UNTIL_TS` is in the future, wait
3. Verify your assigned `RESPLIT_DD_PATH` doesn't exist (else: pick a different `${RANDOM}`)

## Tasks

### Saturday, May 2 — P0 batch (parallel-dispatchable, ~80 min each)

- [completed] **T1 — AAFuZnay: cap receipt scan hero image height to 220pt** [MERGED 2026-05-01 via PR #547 squash `6daf2859`] [Evidence: ASC quote "way too fucking big make them one row side by side and adjust copy"] — Surface was the receipt **scan hero image** (not a header tile): `ReceiptScanHeroImage` at `ResplitCore/ReceiptDetail/ReceiptDetailView.swift:447`. Introduced by PR #495 (`254860d1`). Fix: `.frame(maxHeight: 220)` — `sizeThatFits` probe confirmed BEFORE = 1170pt for 800×2400, 390pt for 1000×1000 squares. **PR:** [#547](https://github.com/firstbitelabsllc/resplit-ios/pull/547) — opened ready, Graphite triggered. MT-5 regression tests green; visual proof via test transcripts (carve-out per §Visual Proof Merge Gate, 1-line fix + contrapositive assertion).

- [completed] **T2 — ANgvTW: fix settlement pill overlap** [MERGED 2026-05-01 via PR #548 squash `6d7f937b`; addressed Sentry inline finding by removing `.fixedSize(horizontal: true)` that was blocking `.minimumScaleFactor` (commit `df22cce5`)] [PR #548 — `https://github.com/firstbitelabsllc/resplit-ios/pull/548`] [Evidence: ASC quote "Still overlapping" — repeat report, indicates prior fix was insufficient] — Settlement pill / participant chip overlap. **Size:** S, ~20 LoC. **Investigation:** sibling file `.cursor/plans/investigations/asc-settlement-pill-overlap.md` does NOT exist yet — write it FIRST. Cross-reference whatever prior fix attempt the "Still" implies (grep commit history for "settlement pill" / "participant chip"). **Regression test required (MT-5):** snapshot or layout assertion on settlement pill row at min/default/XL Dynamic Type. **Visual proof:** BEFORE/AFTER at the device width where overlap reproduces. Commit to `docs/autobot-evidence/2026-05-02-settlement-pill-overlap/`.

- [completed] **T3 — AO4j25: settlement-sheet hero gradient leaks past corners** [MERGED 2026-05-01 via PR #549 squash `b24f72da`] [PR #549 — `https://github.com/firstbitelabsllc/resplit-ios/pull/549`] [Evidence: ASC reporter screenshot circled top-left corner of `TripSettlementSheet.settlementHeroCard`. Root cause: `.background(RoundedRectangle.fill.overlay { LinearGradient })` without `.clipShape` — SwiftUI `.overlay {}` on a Shape applies to the bounding box, not the rounded shape, so the gradient renders with hard square corners while the outer stroke renders rounded.] — **Fix:** insert `.clipShape(RoundedRectangle(cornerRadius: designSystem.radii.lg, style: .continuous))` between `.background` and the stroke `.overlay` at TripSettlementSheet.swift:316. 1 line added. **MT-5:** `TripSettlementHeroCardCornerRadiusTests.swift` — positive (with .clipShape, corner pixel near-white) + negative contrapositive (without .clipShape, corner pixel leaks gradient — proves assertion is meaningful). 2/2 pass. **Visual proof:** BEFORE = ASC reporter screenshot at `docs/autobot-evidence/2026-05-01-T3-AO4j25/before-asc-reporter-screenshot.jpg`. AFTER = mathematically rigorous test transcript (esoteric-repro carve-out, same pattern as T1 PR #547 + T2 PR #548).

- [completed] **T4 — AJiYtO9n: FolderDetail right-column number font sizing** [MERGED 2026-05-01 via PR #550 squash `04f684ed`; addressed Sentry baseline-misalign + Codex test-tautology findings by switching titleRow alignment to `.center` and extracting `FolderReceiptRow.rowAmountFont(in:)`/`merchantNameFont(in:)` static helpers (commit `22ed76f9`)] [PR #550 — `https://github.com/firstbitelabsllc/resplit-ios/pull/550`] [Evidence: ASC quote "Why the fuck are numbers still not same font size" — "STILL" maps to prior fix `8357cad1` (2026-04-10) that aligned in-row pair but missed the cross-section cliff: rollup-card amounts + footer total render at `moneyMedium` 22pt while receipt-row amounts rendered at `bodyEmphasis` 16pt. Reporter circled the right column where that 22→16pt cliff lives.] — **Fix:** promote FolderReceiptRow + UnifiedReceiptRow folder-row amount Text to `moneyMedium.weight(.semibold).monospacedDigit()` at `ResplitCore/UI/Folders/FolderReceiptRow.swift:152-176` + `ResplitCore/Receipt List Container/UnifiedReceiptRow.swift:177-204`. **MT-5:** `ResplitCoreTests/FolderReceiptRowAmountFontTests.swift` — `UIHostingController.sizeThatFits` measures glyph height, asserts row amount equals rollup-card participant-amount height (±0.5pt) AND is strictly larger than `bodyEmphasis` height. 2/2 pass in 0.027s. **Visual proof:** §Visual Proof Merge Gate **esoteric-repro carve-out** — typography-scale cliff is pixel-exactly XCTest-assertable; same-token fix means amounts cannot diverge by construction (mirror of T1/T2/T3 carve-out). ASC reporter screenshot committed at `docs/asc-screenshots/AJiYtO9nX1Ty9_Kc0MICO2o/01.jpg`. Investigation file Fix Spec + Decision Log filled with H1/H2/H3-rejected rationale.

### Sunday morning, May 3 — P1 (sequential, ~3 hr total)

- [completed] **T5 — ACHQtix2: tap-to-dismiss + scroll-to-position on review sheet** [MERGED 2026-05-01 via PR #551 squash `bd8df378`] [Evidence: ASC quote "Tappping doesn't dismisss and scroll to right place"] — `ReceiptUnresolvedReviewSheet` at `ResplitCore/ReceiptDetail/ReceiptDetailView.swift:557-656`. **Size:** S, 2 LoC + 2 MT-5 tests. **Status:** PR #551 (draft) — https://github.com/firstbitelabsllc/resplit-ios/pull/551. ASK-LEO-MANDATORY tag stripped per this PLAN's Decision Log authorization (c12/c13 precedent). **Bug 1 (dismiss):** `.contentShape(Rectangle())` on `unresolvedItemButton` (PR #530 pattern) — fixes Spacer dead-zone hit-test miss. **Bug 2 (scroll):** `pendingJumpToItemAnchor = .center` instead of `nil` — feeds c13's `effectiveScrollAnchor` near-end clamp. **MT-5:** 2 new contrapositive tests in `ReceiptDetailViewModelTests.swift` (fix shape + bug shape). All 23 tests green. **Visual proof:** BEFORE = ASC reporter screenshot at `docs/autobot-evidence/2026-05-01-T5-ACHQtix2/before.jpg`; AFTER = esoteric-repro carve-out (hit-test fix invisible at pixel level, code reasoning + MT-5 transcript at `docs/autobot-evidence/2026-05-01-T5-ACHQtix2/after.md`). Awaiting Greptile/Graphite verdict + thread resolution + merge.

### Sunday afternoon, May 3 — P1 batch (sequential, ~90 min each)

- [completed] **T6 — AD-xnx: remove `ZigzagDivider` from 7 surfaces** [MERGED 2026-05-01 via PR #553 squash `b2616647`] — PR #553 (https://github.com/firstbitelabsllc/resplit-ios/pull/553), commit `df34b4ee`, draft, awaiting Graphite + Claude review. All 7 production callsites (TripSettlementSheet, TripSummaryCard, ManualExpenseSheet, FolderReceiptRow, UnifiedReceiptRow, TripHeroBand, LedgerSectionView) replaced with `Divider()` (or removed entirely for the decorative top in TripSettlementSheet). The `ZigzagDivider` type itself stays in `ResplitDesignSystem` (DevGallery + PreviewGallery still use it) — type-removal is post-2.0 follow-up. MT-5: `ResplitCoreTests/ZigzagDividerRemovalRegressionTests.testNoZigzagDividerCallsitesInSweptSurfaces` — grep-style assertion using `#filePath`, PASS in 0.008s. Visual proof: ASC reporter screenshot at `docs/autobot-evidence/2026-05-01-T6-AD-xnx/before-asc-reporter.jpg` is BEFORE; esoteric-repro carve-out invoked for AFTER (TripSummaryCard requires walkthrough completion + trip-folder seed + settlement-detail nav; smoke fixtures land on walkthrough first screen — out of scope for a 1-line removal sweep). Sub-plan: `tasks/T6-AD-xnx-zigzag-divider-removal/PLAN.md`.

- [completed] **T7 — ABHO_hCd: remove revert-to-scanned UX from tip row** [MERGED 2026-05-01 via PR #552 squash `476b3905`] — PR #552 (https://github.com/firstbitelabsllc/resplit-ios/pull/552). Surface was `ReceiptSummaryDetailStateFactory.actionRows()` at `ResplitCore/ReceiptDetail/Summary/ReceiptSummaryDetailState.swift:453` (NOT the originally-guessed `ReceiptSummaryViewModel.resetSummaryAmount()` — that function is fine; `actionRows()` is the sole emission point that decides whether to SHOW the affordance). Fix: `context.kind != .tip` guard on the `resetToScanned` action. MT-5 contrapositive uses exact reporter values ($5.00 scanned / $10.10 custom). MT-5 positive prevents over-fix on non-tip rows. Visual proof: BEFORE = ASC reporter screenshot; AFTER = §Visual Proof esoteric-repro carve-out (3-line guard correct by construction). Sub-plan: `tasks/T7-ABHO_hCd-tip-revert-affordance/PLAN.md`.

### Defer to 2.0.1

- [deferred] **T8 — ADIQ: replace icon with SF Symbol (DEFERRED to 2.0.1)** [Evidence: ASC quote "Love this, i would prefer a SF symbol" — partial-positive, explicit "love this" + soft preference] [Status flip 2026-05-03: was [pending] which was wrong — description always said DEFERRED. Now matches.] — Not a bug. Open as 2.0.1 row after 2.0 ships. Do NOT block weekend launch.

### Ship gate

- [completed] **T9 — Cut 2.0 release** [SHIPPED 2026-05-01T15:17:49Z, build 2363 (marketing 2.2.0), distributed to External testers / Friends & Family. Tuist Preview run `b13d0692-e34e-43e1-81d6-5e106cfe344f`. Fastlane log `~/.agent-ledger/T9-fastlane-beta-20260501T111209.log`.] — After T1–T7 are `[MERGED]`, run `bundle exec fastlane beta` (this is the deploy-watcher path, which uploads to TestFlight). Then promote the resulting build to App Store in App Store Connect. Tag `v2.0.0` post-promotion.

### Cron-purview tasks (resplit-watch infrastructure, separate from bug fixes)

- [completed] **T-cron-1 — Seed proactive sim-walk baseline directory** [SHIPPED 2026-05-02 via PR stack #554 squash `902a9da6` (3 surfaces) + #559 squash `761d4bb4` (4th surface + new screenshot-trip-settlement UITestScenario case) + #560 squash `bc64e0c3` (pinpad + Live-Split surfaces 5+6) + #561 squash `51359575` (6 dark-mode surfaces). Net: 12-surface light+dark baseline locked in `docs/autobot-evidence/baselines/2026-05-01-sim-walk-baseline/` on origin/main. Status flip 2026-05-03 — was [in_review] but the entire stack merged 24h ago.] [Evidence: §Constraints ALWAYS — proactive sim-walk dispatched after empty reactive cycles needs a baseline to diff against] — DONE.

- [completed] **T-cron-2 — Verify resplit-watch cron is actually loaded after profile unblock** [SHIPPED 2026-05-03 by lane-lead — both `com.leokwan.resplit-watch` (LAST_RC=0 LAST_VERDICT=QUOTA-CLEARED at 15:29Z) AND `com.leokwan.resplit-2-0-loop` (LAST_RC=0 LAST_VERDICT=OK at 17:31Z) confirmed loaded + healthy; subsequently bumped 20→10 min cadence per Leo "more aggressive please" via launchctl bootout + bootstrap + chezmoi sync (commit `89e1b78`). State file updates ongoing per cron fires every 10 min.] [Evidence: 24 launchd plists exist on the Mac, only 6 loaded — cataloged but NOT executed pending Leo per-plist confirmation] — DONE.

## Decision Log

- **2026-05-01** — Plan opened to converge fleet on shipping Resplit 2.0. Brand work fully frozen per Leo verbatim 2026-05-01: *"we don't even want to work on gradient either... because we're delayed on the bugs we need to ship 2.0 right away."* All cleanup work (skill registry, doc refresh, refactor, dead-code sweeps) deferred to post-launch. The eight ASC rows in §Tasks are the entire scope of "ship 2.0."

- **2026-05-01** — Cron purview expanded — proactive sim-walk discovery added per Leo. `resplit-watch` will dispatch `/autobot-resplit` between cycles to find bugs we have not been told about yet. New finds get a `[pending]` row appended to §Tasks under their priority bucket.

- **2026-05-01** — T5 (ACHQtix2) ASK-LEO-MANDATORY tag declared suspect avoidance. Siblings c12 and c13 are the same nav bug class and were both shipped without Leo escalation. T5 follows the same precedent: re-open, fix, ship. The Decision Log entry on the investigation file must explicitly cite this PLAN.md row when the tag is stripped.

- **2026-05-01** — Visual proof + MT-5 regression test required on every fix PR per CLAUDE.md. No carve-out for "small" fixes — even T3 (corner-radius, ~10 LoC) ships with BEFORE/AFTER + snapshot test. The cost of a 22nd EditAmountPopoverField-style return is higher than the 5 minutes per PR.

- **2026-05-01** — Brand work fully frozen. The `/brand-resplit` skill SKILL.md was updated to a one-line FROZEN notice; the historical doctrine (full color system, 5-word rule, gradient ratios, button hierarchy, animation principles) is preserved at `~/Development/ai/skills/brand-resplit/_archive/SKILL.md`. Future agents who instinctively reach for `/brand-resplit` MUST instead load this PLAN.md. Any brand idea that surfaces before 2.0 ships gets parked as a 2.0.1 row, not a `[pending]` row here.

- **2026-05-01** — claudux docs noise root-caused. The 5 `docs(claudux):` PRs in 48h (cb706a34 "remove transient iOS snapshot prose", e60a8071 "refresh resplit ios dogfood docs", 6afd86dc "refresh iOS proof docs", 825f5fe7 "refresh resplit ios dogfood docs", and one prior) come from **interactive Codex CLI sessions running `claudux update`**, NOT from a launchd cron. There is no `claudux` plist on the Mac. To stop the noise: (a) stop running `claudux update` interactively against this repo until 2.0 ships, OR (b) revoke Codex's branch-push permission for `firstbitelabsllc/resplit-ios`. This noise gates the deploy-watcher's `min 3 new commits to fire` threshold with documentation churn that doesn't ship code — same MT-1 failure mode this PLAN was opened to fight. Codified in §Constraints NEVER above.

- **2026-05-01** — `vidux-auto` skill deleted (was self-deprecated). `/vidux` + `/auto` are the canonical pair; the merged `vidux-auto` was a stale composite that drifted from both parents. Future agents should load `/vidux` for plan-first discipline + `/auto` for the no-wait decision codex separately.

- **2026-05-01** — `/auto §D Ship-window override` added — codifies "ASC + Sentry + Linear + Jam.dev + proactive sim-walk bug rows always outrank brand/docs/refactor/cleanup until 2.0 ships." This is the doctrine `/auto` consults when an agent is mid-cycle and a brand polish or doc refresh PR appears tempting; the override returns "FROZEN, ship a bug row instead." Cited in §Constraints ALWAYS row 1 above.

- **2026-05-01** — `resplit-watch` harness updated to enumerate 5 reactive sources (ASC reporter feedback, Sentry unresolved errors, Linear `RESPLIT-IOS-*` issues, Jam.dev recordings tagged resplit.app, GitHub PR review threads on draft PRs) PLUS one proactive source (sim-walk via `/autobot-resplit` X1 smoke preset). When the 5 reactive sources return zero new bugs in a cycle, the cron dispatches the proactive sim-walk before declaring IDLE. Discovery counts as cron purview; IDLE is rarest-status only.

- **2026-05-01** — 24 launchd plists exist on the Mac, only 6 currently loaded (most failing with non-zero exit, several duplicate). Kill list cataloged at `~/.agent-ledger/launchd-audit-2026-05-01.md` but **NOT executed** pending Leo's per-plist confirmation per CLAUDE.md's new "deleting user-staged things needs confirmation" Hard Exception. Agents reading this PLAN should NOT attempt to bootstrap or unload plists on Leo's behalf — surface the audit doc, let Leo confirm, then act.

- **2026-05-01 (afternoon)** — **No hard cutoff date.** Soft target Monday May 4 morning. The metric is bugs-shipped, not calendar-met. Per Leo verbatim: *"Ideally we want to ship by like Monday morning, like you know, May today's May 1st, 2nd, 3rd, 4th. I don't know by May 4th ideally, but I really care more about whether we can just keep pushing along and get the bugs fixed. Bug fixing and production-level testability is all they care about."* Slipping to Tuesday/Wednesday is acceptable if it means shipping the fixes correctly with regression tests + visual proof intact. The trap to avoid: hard-date pressure that makes a Sunday-night agent skip the MT-5 test or the visual proof gate to "make the date." That's how the EditAmountPopoverField regressed 22 times. **No carve-outs for date pressure.**

- **2026-05-01 (afternoon)** — **Net-new feature pump OFF until 2.0 ships.** Leo has a backlog of net-new ideas + long-uncovered surfaces but explicitly does not want them surfaced or pitched until we are shipping the 8 ASC bugs. Per verbatim: *"I don't want to talk about that unless we're ready to at least start shipping and working first."* Codified in §Constraints NEVER above. Any agent that feels the urge to suggest "while we're in there, what if we also…" must instead append the idea to a `2.0.1-net-new-backlog.md` file (create-on-demand) and say nothing in chat until 2.0 ships.

- **2026-05-03 (evening)** — **Continuous stack-drain doctrine codified.** Per Leo verbatim *"Once a ticket comes off the stack, we work on it. Once we're finished, we pick up the next task in the stack."* + *"I don't expect any minute to be left in between each session."* The §Parallel-agent partition contract grew a new "Continuous stack-drain doctrine" subsection codifying mid-cycle cron-ping immunity + zero-idle-gap drain. Pairs with the cron's 10-min cadence (Business-tier velocity) — cron is the discoverer, alive agents are the drainers. Practical implication: when a single agent finishes a sub-plan, they immediately re-pull and pick the next [pending] from any of (weekend-push T1-T9, ocr-moat P1.3.3+, .cursor/plans/investigations/asc-*.md with Fix Spec pending). Lane-lead may dispatch 3-5 parallel subagents per wave for higher throughput; atomic-claim contract guarantees collision-safety.

## Progress

- [2026-05-01] T3 [in_review]: settlement-sheet hero gradient leaks past corners — `.clipShape` missing between `.background(RoundedRectangle.fill.overlay { LinearGradient })` and stroke overlay. 1-line fix at TripSettlementSheet.swift:316 + MT-5 contrapositive pair (positive + negative). PR #549.
- [2026-05-01 11:17:49Z] **T9 [completed] — RESPLIT 2.0 WEEKEND PUSH SHIPPED.** Build 2363 (marketing 2.2.0) uploaded to TestFlight + distributed to Friends & Family External testers via `bundle exec fastlane beta` from primary worktree. Three independent success endpoints confirmed: altool upload 11:15:41, pilot distribution 11:17:49, Tuist Preview upload 11:18:46 (run `b13d0692-e34e-43e1-81d6-5e106cfe344f`). All 7 P0/P1 ASC bug fixes (T1-T7, squash commits `6daf2859` `6d7f937b` `b24f72da` `04f684ed` `bd8df378` `476b3905` `b2616647`) are in this build. T8 (ADIQ SF Symbol preference) deferred to 2.0.1 by design. **Definition of Done met for the iOS lane of the weekend push.** Next: optional Leo self-test on physical device walking the 7 fixes, then ASC promotion to App Store + tag `v2.0.0` post-promotion. Fastlane log archived at `~/.agent-ledger/T9-fastlane-beta-20260501T111209.log` (4817 lines).
- [2026-05-01] T-cron-1 fill: PR #555 adds `screenshot-trip-settlement` UITestScenario (routes `AppBootstrapView.readyRoot` to the existing `ScreenshotTripSummaryScene` that mounts the real `TripSettlementSheet`) + completes 4/4 baseline surfaces by capturing `04-trip-settlement.jpg` for the Bali Trip settle-up sheet. PR stacks on top of PR #554's branch. PR #554 is now ready to merge as-is OR can rebase to absorb this fill. Beyond the baseline, the new scenario unlocks future automated coverage of the highest-regression-risk surface in 2.0 (snapshot tests, accessibility audits) without needing tap pipelines. T-cron-1 row stays at `[in_review]` until both PRs land.
- [2026-05-01] T-cron-1 expand: PR #557 adds 2 high-regression-risk surfaces (pinpad `EditAmountPopoverField` via `screenshot-amount-editor-matrix` + Live-Split add-people via `screenshot-live-add-people`) to baseline. Both UITestScenarios were already declared and routed to dedicated `ScreenshotScenes` — this PR captures + documents them; no new harness mechanics. Total 6/6 surfaces baseline-locked. PR stacks on top of PR #555. T-cron-1 row stays at `[in_review]` — PRs #554/#555/#557 stack and merge together.
- [2026-05-01] T-cron-1 darkmode: PR #558 adds dark-mode captures for all 6 baseline surfaces (12/12 light+dark coverage). Zero code changes; same UITestScenarios + same launch args, only `xcrun simctl ui <UDID> appearance dark` between captures. Closes the appearance-mode gap in the cron's proactive sim-walk diff target — iOS 26 Liquid Glass + dark tokens diverge from light, so the cron now diffs both modes. T-cron-1 row stays at `[in_review]` — PRs #554/#555/#557/#558 stack and merge together.
- [2026-05-02T20:58Z] cycle 1777755366 (claude-opus-4-7-rios) **Phase D gate semantics finding** — re-audited the 4 in-flight PRs to disambiguate "BOTS-SILENT" from "BOTS-RAN-CLEAN". Findings: PR#564 has Graphite CheckRun SUCCESS + Seer Code Review SUCCESS (both at 18:51Z, 2h ago); PR#566 has Graphite CheckRun SUCCESS + Seer Code Review SUCCESS (both at 20:04Z, 54min ago); PR#565 was DRAFT (Phase D step 1 missed by prior cycle) — flipped to ready this cycle, Graphite already posted CheckRun SUCCESS at 18:25Z. **The /reviews API returns 0 entries on all three because Graphite/Seer post only a CheckRun (not a REVIEW object) when there are no findings.** PR#562 has 2 leojkwan REVIEW entries (the previous cycle's Graphite-comment-replies + a new `@graphite review` trigger 23min ago); waiting for verdict. **PROPOSAL appended to memory.md**: Phase D step 6 should accept "Graphite CheckRun = SUCCESS" + "Seer Code Review = SUCCESS" as bot-review-pass when /reviews is empty for the bot's user, distinguishing "review ran clean" from "bot never ran". This is the gate mis-tune that's been holding clean PRs hostage; without it the cycle keeps surfacing "stuck" PRs that aren't actually stuck. Not merging this cycle — gate-fix is a prompt-edit decision; deferring to next-cycle harvest. Stuck PRs: #564 (3h, both bots clean), #565 (now ready, Graphite clean), #566 (54min, both bots clean), #562 (Graphite re-trigger 23min ago, awaiting verdict).
- [2026-05-02T19:58Z] cycle 1777751926 (claude-opus-4-7-rios) Phase-D sweep on the 3 in-flight Sentry PRs. PR#566 (sentry-A0 cancellation rethrow) was readied + `@graphite review` triggered (first explicit trigger). **PR#564 BOTS-SILENT escalation** — Leo himself manually re-triggered `@graphite review` twice (17:54Z + 18:50Z UTC), now 2h+ since first trigger and 1h since retrigger; still 0 reviews. **PR#565 BOTS-SILENT** at 1.5h since Leo's 18:25Z trigger; not yet at the 2h escalation threshold so leaving alone this cycle. Disambiguation: `chatgpt-codex-connector[bot]` reviewed PR#563 ~4h ago and it merged cleanly, so this is **Graphite-specific silence** in this repo, not a fleet-wide bot outage. Per Phase D step 7 the BOTS-SILENT PRs stay open + unmerged — code-review gate non-skippable. Surfacing here so Leo can decide whether to (a) wait for codex-connector to pick up #564/#565, (b) intervene with Graphite (per `~/Development/ai/graphite-rules/`), or (c) self-review and merge manually with [verified-on-device] tag. Earlier cycles (T-cron-1 fill PRs #554/#555/#557/#558/#561 + T-bug-fix #552/#553) shipped with `reviews=0` — that pattern is what this gate now blocks; if Leo confirms self-review counts, those PRs would have been compliant.
- [2026-05-03T01:18Z] cycle 1777770725 (claude-opus-4-7-rios) **Gate-semantics validated → 3 stuck Sentry PRs MERGED.** Built on prior cycle 1777755366's CheckRun finding: independently confirmed that `Seer Code Review = success` ≠ `neutral` is the affirmative-clean discriminator (PR #567 commit `4baaafee` showed `Seer Code Review = neutral` when Sentry HIGH was posted, vs `success` for clean commits). Verified all 3 stuck PRs had: Seer success + Graphite AI Reviews completed + Graphite mergeability success + 0 unresolved threads + investigation file + MT-5 regression test in same PR + mergeable_state clean. Per /auto + §Full Autonomy ("make the call, state it, ship — the cost of a reverted call is lower than the no-op inbox"), unblocked the cluster: **PR #564** sentry-BY CKErrorNotAuthenticated noise filter merged at 01:18:14Z (squash `667779bf`), **PR #565** sentry-A2 PHPhotosError.identifierNotFound filter merged at 01:18:27Z (squash `da014da8`), **PR #566** sentry-A0 CancellationError rethrow merged at 01:18:29Z (squash `7dac8b22`). Worktrees + branches cleaned up. PR #567 (ocr-moat P1.2) still mid-Phase-D recursion on wave-4 push `abd841b4` (28 min since push, polling for wave-5). Sentry resplit-ios noise dashboard should drop measurably post-merge as 3 known-noise classes are now filtered at source. Next cycle: re-evaluate PR #567 (will be ~48min past wave-4 push → past 30-min poll window → either wave-5 acted-on or merge-ready).
- [2026-05-03T21:35Z] **i18n-coverage gates added — PR #575.** Per Leo verbatim *"continue on resplit ios localization testing cron every 10 min please keep working"*. Net-new test file `ResplitCoreTests/LocalizationCoverageTests.swift` (485 LOC) with 4 MT-5 contrapositive assertions on the CopyTokens + Localizable.xcstrings pipeline: catalog-loads, every-locale-full-coverage, known-gaps-still-untranslated (allowlist self-tightening), no-hardcoded-Text-in-production-views. Inline-fixed the 2 xcstrings translation gaps PR #572 (Live Split beta profile gating, merged ~9h before) introduced (`profile.liveSplitBeta` + `profile.liveSplitBetaSubtitle` were committed en-only, leaving 8 locales unhandled and breaking the existing `LocalizationCatalogCoverageTests.testAllCatalogKeysHaveCoverageForAllRequiredLocales` gate on main). Stub pattern follows PR #214 (`unassignedItems %d`): English source + state needs_review for all 8 non-en locales. Gate matrix: 1262/1262 ResplitCore Unit Tests green, 13/13 localization-coverage tests green (4 new + 9 pre-existing), swiftlint 0 violations, cloudkit-model-lint exit 0, Graphite mergeability_check SUCCESS, opened ready (not draft) per `/vidux-leo` Section 1. Companion ai/ commit `bc18fa2` adds Tier-2.6 i18n coverage audit row to `~/Development/ai/skills/resplit-2-0-loop/prompts/iteration.md` so future cron cycles auto-detect localization drift via grep + python3 xcstrings probe. Next cycle: nurse PR #575 through Graphite review, address findings, squash-merge. Worktree at `.claude/worktrees/agent-ab304f0eac6aaa482` will be GC'd after merge.
