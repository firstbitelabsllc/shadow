# Resplit 2.0 — Weekend Ship Push (May 2–3, soft target May 4)

**Soft target:** Monday May 4 morning. **No hard cutoff.** Per Leo verbatim 2026-05-01: *"I really care more about whether we can just keep pushing along and get the bugs fixed. Bug fixing and production-level testability is all they care about."* The metric is **bugs-shipped, not calendar-met**. May 4 is when we'd ideally have a TestFlight build with all 8 ASC bugs verified — slipping a day or two is fine if it means shipping the fixes correctly.

## Parent plan

This is the **resplit-ios lane detail** for the multi-platform Resplit 2.0 launch.

- **Multi-platform mega plan**: `~/Development/resplit-web/vidux/resplit-2.0-launch/PLAN.md` (open as PR #541 on `firstbitelabsllc/resplit-web`, branch `claude/resplit-2.0-launch-plan-consolidation`).
- **What the mega plan owns**: web-side ship gates (T3 security review, T5 test coverage, T7 E2E guest flow, staging redeploy from main, dark-mode visual baselines, autobot-resplit-web cron) + the cross-platform Definition of Done.
- **What this plan owns**: the 8 ASC bug rows specific to the iOS app. The mega plan's iOS gate (`iOS App Store Connect submission accepted — owned by resplit-ios lane, gated independently`) is satisfied when every P0/P1 task below ships and `bundle exec fastlane beta` lands a build with all eight bugs verified.
- **Convergence**: agents working iOS read THIS plan; agents working web read the mega plan. Cross-references in both directions (parent → child via the iOS row, child → parent via this section).

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

Only ONE agent at a time edits the master PLAN.md, and only to:
- Flip a task's `[status]` from `[pending]` → `[in_progress]` → `[completed]`
- Append to the `## Progress` log

All other plan content lives in sub-plans. If you need to add/remove tasks, do it via a sub-plan + a single coordinated master-plan edit at the end of your cycle.

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

- [pending] **T1 — AAFuZnay: shrink receipt detail header to one row** [Evidence: ASC quote "way too fucking big make them one row side by side and adjust copy"] — Receipt detail header card or wrap-up sheet. **Size:** S, ~30 LoC. **Investigation:** create `.cursor/plans/investigations/asc-AAFuZnay-receipt-header-too-big-2026-05-02.md` BEFORE touching code. **Regression test required (MT-5):** snapshot test on `ReceiptDetailView` header at default content size + accessibility XL. **Visual proof:** BEFORE shows oversized two-row card; AFTER shows single side-by-side row. Commit screenshots to `docs/autobot-evidence/2026-05-02-receipt-header-shrink/`.

- [pending] **T2 — ANgvTW: fix settlement pill overlap** [Evidence: ASC quote "Still overlapping" — repeat report, indicates prior fix was insufficient] — Settlement pill / participant chip overlap. **Size:** S, ~20 LoC. **Investigation:** sibling file `.cursor/plans/investigations/asc-settlement-pill-overlap.md` does NOT exist yet — write it FIRST. Cross-reference whatever prior fix attempt the "Still" implies (grep commit history for "settlement pill" / "participant chip"). **Regression test required (MT-5):** snapshot or layout assertion on settlement pill row at min/default/XL Dynamic Type. **Visual proof:** BEFORE/AFTER at the device width where overlap reproduces. Commit to `docs/autobot-evidence/2026-05-02-settlement-pill-overlap/`.

- [pending] **T3 — AO4j25: corner-radius single-token fix** [Evidence: ASC quote "Corner radius bug"] — Likely a single design-system token mismatch. **Size:** S, ~10 LoC. **Investigation:** create `.cursor/plans/investigations/asc-AO4j25-corner-radius-bug-2026-05-02.md`; grep for the surface the reporter screenshotted (use ASC attachment if present in `docs/asc-screenshots/`). **Regression test required (MT-5):** snapshot test on the affected component. **Visual proof:** BEFORE/AFTER pair showing the corner. Commit to `docs/autobot-evidence/2026-05-02-corner-radius-fix/`.

- [pending] **T4 — AJiYtO9n: FolderDetail right-column number font sizing** [Evidence: ASC quote "Why the fuck are numbers still not same font size" — repeat report, "still" indicates prior fix did not stick] — FolderDetail right-column amounts. **Size:** S–M, ~40 LoC. **Investigation file EXISTS:** `.cursor/plans/investigations/asc-AJiYtO9nX1Ty-folder-detail-right-column-chrome-2026-04-29.md` — Fix Spec NOT filled. Fill the Fix Spec FIRST before code. Cross-reference any prior FolderDetail font-size attempt in commit history. **Regression test required (MT-5):** snapshot test on `FolderDetailView` right column at multiple Dynamic Type sizes asserting all amount labels share the same `Font` instance. **Visual proof:** BEFORE/AFTER pair at the size where mismatch reproduces. Commit to `docs/autobot-evidence/2026-05-02-folder-detail-font-size/`.

### Sunday morning, May 3 — P1 (sequential, ~3 hr total)

- [pending] **T5 — ACHQtix2: tap-to-dismiss + scroll-to-position on review sheet** [Evidence: ASC quote "Tappping doesn't dismisss and scroll to right place"] — Likely `ReceiptUnresolvedReviewSheet` at `ResplitCore/ReceiptDetail/ReceiptDetailView.swift:557-589`. **Size:** M, ~80 LoC. **Investigation file EXISTS but flagged ASK-LEO-MANDATORY:** `.cursor/plans/investigations/asc-ACHQtix2-unassigned-items-assign-blank-2026-04-29.md`. **Action:** RE-OPEN the investigation. The ASK-LEO tag was suspect avoidance — siblings `asc-c12-folder-receipt-tap-no-dismiss.md` and `asc-c13-tap-unassigned-scrolls-to-void.md` describe the same nav bug pattern and were resolved without escalation. Cross-reference c12 + c13 fixes, apply the same dismiss-then-scroll handoff to ACHQtix2. Strip the ASK-LEO tag in the same PR with a Decision Log entry citing this PLAN row. **Regression test required (MT-5):** UI test that drives tap → asserts sheet dismissed → asserts scroll position lands on the expected anchor row. **Visual proof:** BEFORE shows tap with no dismiss / wrong scroll target; AFTER shows clean dismiss + correct scroll. Commit to `docs/autobot-evidence/2026-05-03-review-sheet-dismiss-scroll/`.

### Sunday afternoon, May 3 — P1 batch (sequential, ~90 min each)

- [pending] **T6 — AD-xnx: remove `ZigzagDivider` from all 7 surfaces** [Evidence: ASC quote "zig zags here is too distracting remove and refine UX"] — `ZigzagDivider` callsites: TripSettlementSheet, TripSummaryCard, ManualExpenseSheet, FolderReceiptRow, UnifiedReceiptRow, TripHeroBand, LedgerSectionView (per AG6aB triaged note). **Size:** M, ~50 LoC across the 7 callsites. **Investigation:** create `.cursor/plans/investigations/asc-AD-xnx-zigzag-divider-removal-2026-05-03.md` enumerating every callsite + the replacement (likely flat divider or none). **Regression test required (MT-5):** snapshot tests on all 7 surfaces asserting ZigzagDivider is gone. After removal, verify the ZigzagDivider component itself has zero callers (`grep -rn ZigzagDivider`) and either delete or mark deprecated in the same PR. **Visual proof:** BEFORE/AFTER pairs for the 3 most prominent surfaces (TripSettlementSheet, FolderReceiptRow, TripHeroBand). Commit to `docs/autobot-evidence/2026-05-03-zigzag-divider-removal/`.

- [pending] **T7 — ABHO_hCd: remove revert-to-scanned UX from tip row** [Evidence: ASC quote "Why does tip have a revert to scanned UX as well?"] — `ReceiptSummaryViewModel.resetSummaryAmount()` for the tip row. The reporter is questioning why tip has the same affordance as subtotal — likely the answer is "it should not." **Size:** S, ~20 LoC. **Investigation:** create `.cursor/plans/investigations/asc-ABHO_hCd-tip-revert-affordance-2026-05-03.md` first; confirm the design intent (only subtotal should have revert, tip should not) before deletion. **Regression test required (MT-5):** unit test on `ReceiptSummaryViewModel` asserting tip row has no `resetSummaryAmount()` affordance OR the affordance is wired only when explicitly relevant. **Visual proof:** BEFORE shows tip row with revert button; AFTER shows tip row clean. Commit to `docs/autobot-evidence/2026-05-03-tip-revert-removal/`.

### Defer to 2.0.1

- [pending] **T8 — ADIQ: replace icon with SF Symbol (DEFERRED to 2.0.1)** [Evidence: ASC quote "Love this, i would prefer a SF symbol" — partial-positive, explicit "love this" + soft preference] — Not a bug. Open as 2.0.1 row after 2.0 ships. Do NOT block weekend launch.

### Ship gate

- [pending] **T9 — Cut 2.0 release** — After T1–T7 are `[MERGED]`, run `bundle exec fastlane beta` (this is the deploy-watcher path, which uploads to TestFlight). Then promote the resulting build to App Store in App Store Connect. Tag `v2.0.0` post-promotion.

### Cron-purview tasks (resplit-watch infrastructure, separate from bug fixes)

- [pending] **T-cron-1 — Seed proactive sim-walk baseline directory** [Evidence: §Constraints ALWAYS — proactive sim-walk dispatched after empty reactive cycles needs a baseline to diff against] — Create `docs/autobot-evidence/baselines/` in `resplit-ios`. Run `/autobot-resplit` once interactively against the X1 smoke preset (Trip + Folder + Receipt detail + Settlement). Save the resulting screenshots to `docs/autobot-evidence/baselines/2026-05-01-sim-walk-baseline/` with a `MANIFEST.md` listing every screen captured + the launch args used. **ETA:** ~20 min. **Owner:** first cron firing OR an interactive Leo session, whichever comes first. **Done when:** baseline directory committed to `main` so subsequent cron sim-walks have a visual diff target.

- [pending] **T-cron-2 — Verify resplit-watch cron is actually loaded after profile unblock** [Evidence: 24 launchd plists exist on the Mac, only 6 loaded — cataloged but NOT executed pending Leo per-plist confirmation] — Run `launchctl list | grep com.leokwan.resplit-watch` and confirm a non-zero PID OR an exit-status-0 most-recent run. If the plist is unloaded, run `launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.leokwan.resplit-watch.plist` and re-verify. If the plist is missing entirely, regenerate via `resplit-watch --install` (per the resplit-watch skill SKILL.md). **ETA:** ~5 min. **Done when:** `launchctl print gui/$UID/com.leokwan.resplit-watch | grep -E '(state|last exit code)'` shows running or last-exit 0.

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

## Progress

(Empty — agents append `[YYYY-MM-DD HH:MM] T<n> <status>: <one-line note + PR link>` rows here as they pick up tasks.)
