# Resplit 2.0 Launch Readiness

## Purpose
Ship Resplit 2.0 to TestFlight Friends & Family with all open ASC bugs resolved, full E2E + unit + UI test coverage on the 8 surfaces, Localization Phase 2-7 shipped, Linear EVE round-tripped, and supporting skills (`/autobot-resplit`, `/vidux-leo`, `/frontend-design`, `/brand-resplit` unfreeze-prep) tightened. CC `/goal` is the single execution surface — no /resplit-2-0-loop launchd cron, all coordination through this PLAN.md.

## Evidence
- [Source: codebase] Module map: Resplit / ResplitCore / ReceiptSplitter / ResplitDesignSystem / ResplitPersistence / ResplitPreview
- [Source: CLAUDE.md] Factory DI via `Container+Database.swift`; `@Observable` VMs (NOT `ObservableObject`); Tuist 4.x + per-lane RESPLIT_DD_PATH; `tuist xcodebuild` wrapped form per §Build Isolation Mandatory; /brand-resplit FROZEN until 2.0 ships
- [Source: .cursor/plans/app-store-feedback.plan.md] 8 ASC tracker rows still open
- [Source: linear:resplit-ios e73259aa-9870-4b5e-b80f-e31e517755a4] EVE issue queue — fetch live every cycle via `mcp__plugin_linear_linear__list_issues` or `vidux-inbox-sync.py` adapter
- [Source: investigations/autobot-cron-2026-05-12-systematic-build-hang-xcode26-tuist4-176.md] Xcode 26.4-RC SWBBuildService hang; Path 3 candidate is opening `/Applications/Xcode-26.4.1.app` once for first-launch (Hypothesis B refuted, Hypothesis A primary per fire #16 evidence)
- [Source: investigations/ocr-corpus-cron-2026-05-12-incomplete-corpus-row-missing-azure.md] Path B applied 2026-05-13 in PR #640; corpus row `4c5c125e64b2` set to `expected: null`
- [Source: 2026-05-14] /resplit-2-0-loop launchd cron uninstalled — execution now driven by CC `/goal` against this PLAN.md
- [Source: /resplit-2-0-loop iteration.md] Loop iteration doctrine harvested into "## Loop Learnings (sub-plan)" below; the cron is dead, the doctrine survives

## Constraints
- ALWAYS: Factory DI via `Container+Database.swift`; `@Observable` not `ObservableObject`; per-lane RESPLIT_DD_PATH=/tmp/resplit-dd-<lane>-<id>; wrapped `tuist xcodebuild build` form
- ALWAYS: Visual proof on bug-fix merges per CLAUDE.md §Visual Proof Merge Gate (BEFORE/AFTER table to `docs/autobot-evidence/<date>-<slug>/`)
- ALWAYS: MT-5 regression test on UI/auth/Live-Split/FX surfaces — same PR as the fix
- ALWAYS: investigation-first per CLAUDE.md §Bug Fix Discipline (`.cursor/plans/investigations/asc-<id>-<slug>.md`); no Fix Spec = no code
- ALWAYS: Linear closeout on merge — Path B for P0/P1, Path A for P2/P3 (state file UUID `8e639ee2-0e7f-4687-bfab-33c42a22b9a8`)
- ALWAYS: Append-to-vidux-goal — every new task lands in THIS PLAN.md `## Tasks` section, never chat-only, never TaskCreate-only, never sibling plan
- ALWAYS: Graphite-wait HARD CAP at 15 minutes (Leo 2026-05-14 verbatim: *"i wouldnt' wait on graphite btw after 15 minutes hard rule"*). If no Graphite verdict at +15min after `gh pr ready` / `@graphite review` comment, proceed to direct merge per /vidux-leo §1 Tier A (zero unresolved threads check still required via `gh api graphql reviewThreads`). Overrides /vidux-leo §1 "Stalled Graphite verdict — 60min escalation" — that 60-min rule was for write-and-walk-away mode; in /goal mode we drain.
- ALWAYS: TestFlight cadence is 3h via `com.leokwan.deploy-watcher` (StartInterval=10800s). Updated 2026-05-14 from 2h per Leo. Release notes MUST be clear and specific — derived from `git log <last_tag>..HEAD --oneline` filtered to user-visible commits, not generic `"Build N"` / `"Beta N"` strings. See T26.
- NEVER: brand-copy on hero/CTA without Leo; `/brand-resplit` FROZEN
- NEVER: `gh pr merge --auto` (per `feedback_gh_pr_merge_auto_skips_threads.md` — check inline threads BEFORE direct merge)
- NEVER: `killall xcodebuild` / `killall SWBBuildService` / `pkill -f xcodebuild` (per `feedback_polling_killall_antipattern.md` — use `kill -0 $BUILD_PID` liveness)
- NEVER: force-push to main; skip hooks; `--no-verify`; destructive ops without Leo
- NEVER: ASK-LEO-MANDATORY rows; state the call, execute (per /vidux-leo §2 ZERO-ASK)

## Loop Learnings (sub-plan)

Doctrine harvested from /resplit-2-0-loop's iteration.md (the launchd cron is uninstalled 2026-05-14; the doctrine migrates here). Apply during every cycle of the /goal:

1. **Phase A→E discipline.** Every code-fix task flows through: A=Investigation (read ASC report, grep surface, write Fix Spec) → B=Code (worktree + RESPLIT_DD_PATH + BEFORE screenshot + fix) → C=Proof (AFTER screenshot + MT-5 test + draft PR) → D=Closeout (`gh pr ready` → ack Graphite/Seer threads → merge `--squash --delete-branch` → Sentry resolve → worktree teardown) → E=Pre-ship device walk (T9-class ship-gate tasks only — halt with `AWAITING-DEVICE-WALK`, resume on Leo's `[verified-on-device]` edit).

2. **Esoteric carve-out is PROHIBITED if** wording contains "STILL" OR diff >50 LOC OR >3 files OR revert-prone surface (UI/auth/Live-Split/FX) OR >1 unverified stress dimension. Esoteric carve-out = "no visual proof needed because impossible to repro." Used too liberally; revert-prone surfaces always need proof.

3. **Continuous stack-drain doctrine.** (a) Mid-cycle interruption immunity: if a new prompt arrives while you're in Phase A/B/C/D, IGNORE it and finish the phase. (b) Zero-idle-gap drain: after CHECKPOINT (PR merged + Sentry resolved + worktree torn down), DO NOT exit. Re-PULL PLAN.md and pick the next [pending] in the same cycle. Only declare IDLE when ALL of these are simultaneously empty: `## Tasks` [pending] + open ASC investigations + open Linear EVE issues + recent Sentry unresolved + Jam.dev recordings since session start.

4. **Snapshot-first orphan-reclaim protocol.** Detect orphan when ALL six hold: (a) `claimed_at:` ≥120 min stale, (b) worktree present, (c) branch checked out, (d) `git log <branch> --since='30 minutes ago'` empty, (e) `find <worktree> -name '*.swift' -mmin -30` empty, (f) zero ledger entries from claimant's session ID. When all six positive: `cp` modified files to `/tmp/orphan-snapshots/<slug>-recovered-by-<your-id>-<ts>/` BEFORE `git worktree remove --force`, then flip the row back to `[pending] — ORPHAN-RECLAIMED <ts>`. When any of (b)-(f) fail: append `[FRICTION] orphan-claim partial-signals` to memory + skip past the orphan + look for OTHER work this cycle. Snapshot-first satisfies CLAUDE.md "Executing actions with care" because bytes are preserved before the destructive op.

5. **Subagent dispatch hygiene.** When dispatching a subagent: (a) NEVER use `Monitor` with `until-loop` for indefinite waits — use active-poll-with-timeout (`gh pr checks <N>` every 30s × 30-iteration max); (b) Closeout MUST be commit-able BEFORE any wait — order Phase D as ready→`@graphite review`→flip vidux PLAN to `[in_review]`+commit+push BEFORE the bot-wait, so work is atomic even on subagent crash; (c) Subagent reports must include `git rev-parse HEAD` + `gh pr view <N> --json` output, not narrative claims (per CLAUDE.md MT-7).

6. **Cap meta-work.** If your last 3 memory entries are all `[PROPOSAL]` about the same topic with no `[SHIP]` of user-bug code in between, stop the meta loop — the prompt is already covering it. Treat your own recent memory tail as evidence of meta-drift.

7. **Defer gates that auto-skip a cycle when unsafe.** (a) Active `xcodebuild` process via `pgrep -x xcodebuild` rc=0 → SIGTERM cascade protection per CLAUDE.md §Build Isolation Mandatory; (b) Leo interactive in resplit-ios in last 5 min via agent-ledger jq lookup → live-steering deference; (c) Claude API rate-limit hit → `[ACCESS-ALERT]` + exit cleanly (Hard NEVER: do not retry-loop).

8. **App Store submission is MANUAL.** Do NOT call `bundle exec fastlane beta` or `pilot upload` from the /goal, even if every gate is green. Phase E `AWAITING-DEVICE-WALK` is the stop point. Leo runs fastlane.

9. **Polish / parity / Storybook / brand work stays FROZEN until 2.0 ships.** No exceptions. If the only [pending] row is polish, IDLE is correct. /brand-resplit unfreeze-prep is META work (T22 below) — drafting the procedure, not executing it.

10. **Web port doctrine references for any cross-stack work.** `data-row-mine="sole|multi"` is the canonical row-highlight contract (PR #601, 2026-05-09); attribute-first, never class-based. Action-footer compactness rule: one-action footers drop the explanatory caption; two-action footers go side-by-side, never stacked.

## Linear binding
- Project: resplit-ios (`e73259aa-9870-4b5e-b80f-e31e517755a4`)
- Team: FirstBite (`EVE`, `2f745857-a4df-4f99-93a9-6ac89f9991a2`)
- Done state: `8e639ee2-0e7f-4687-bfab-33c42a22b9a8`
- READ adapter: `python3 ~/Development/vidux/scripts/vidux-inbox-sync.py --config ~/Development/resplit-ios/vidux.config.json --only-adapter linear --direction=pull --dry-run --json`
- WRITE on merge (Path B for P0/P1): `mcp__plugin_linear_linear__update_issue(id=<uuid>, stateId='8e639ee2-...')` + `create_comment(issueId=<uuid>, body='Fixed in <sha> (PR #N).')` + flip PLAN.md row to `[completed]`. Per `/linear` § Closeout pattern.

## 4-cron coexistence contract
The /goal is the EXECUTION surface (single long-running session). Sibling crons survive as DETECTION + NURSE inputs:
- `/resplit-watch` (10-min launchd) — pulls ASC/Sentry/Jam findings into `## Tasks` as new [pending] rows. Does NOT execute fixes.
- `/autobot-resplit-cron` (20-min CronCreate, session-scoped) — files investigations to `.cursor/plans/investigations/` as inputs.
- `/ocr-corpus-cron` (30-min CronCreate, session-scoped) — files OCR-BUG / KEY-VALUE-MISS rows.
- Coordinator cron (30-min CronCreate, session-scoped) — verifies open PRs + Graphite acks; can co-merge if /goal is busy. Same PLAN.md.

KILLED 2026-05-14: `com.leokwan.resplit-2-0-loop` launchd cron (this /goal supersedes it).

## Tasks

### Tech Excellence (Factory + @Observable + Tuist)
- [pending] T1: Audit `Container+Database.swift` for missing Factory registrations; assert every Manager / Repository wired through DI [Evidence: ResplitCore DI architecture per CLAUDE.md] [ETA: 2h]
- [completed] T2: Convert any remaining `ObservableObject` ViewModels to `@Observable`; assert via `grep -rn 'ObservableObject' ResplitCore/ ReceiptSplitter/` returns zero [Evidence: per CLAUDE.md §Code Style] [Verified: /goal cycle 2 grep ran `grep -rn ObservableObject ResplitCore/ ReceiptSplitter/ --include='*.swift'` returned ZERO violations; 42 files use `@Observable`. Migration is fully complete — no code change needed, plan-flip only.]
- [pending] T3: Tuist binary cache audit — `tuist cache warm` on Resplit Debug + Dev App; record cache hit rate baseline; commit `.tuist-cache-baseline.md` to repo [ETA: 0.5h]
- [pending] T4: DevGallery storybook coverage — every shipped surface (8 from autobot rotation) has a story; backfill missing ones [Evidence: ResplitDesignSystem + ResplitPreview module map] [ETA: 4h]

### E2E Testing (autobot-resplit + autobot-resplit-web)
- [pending] T5: Per-surface autobot-resplit walks — 8 surfaces × BEFORE/AFTER screenshots committed to `docs/autobot-evidence/2026-05-14-launch-readiness/` [Evidence: per CLAUDE.md §Visual Proof Merge Gate] [Blocked: T23 systematic-build-hang] [ETA: 3h]
- [pending] T6: ObservabilityBus event presence assertions — every wired present/action emits one event in DEBUG console; assertion via `events.jsonl` capture per surface [Evidence: feedback_observability_vendor_agnostic.md] [ETA: 2h]
- [pending] T7: autobot-resplit-web Playwright flows for landing/guest surfaces — fixture states + visual proof + anti-slop PRs per `/autobot-resplit-web` skill [ETA: 4h]

### Unit + UI Testing
- [pending] T8: ResplitCore Unit Tests — gap analysis vs ViewModels/Managers; backfill to ≥80% on critical paths (Live-Split, FX, OCR, ReceiptList) [ETA: 6h]
- [pending] T9: ReceiptSplitter Unit Tests — split calculator + DTOs + SwiftData models [ETA: 3h]
- [pending] T10: Resplit UI Tests — 8-surface XCUITest coverage with reusable robot helpers (no inline orchestration per CLAUDE.md §Test Structure) [ETA: 5h]
- [pending] T11: ResplitCore Corpus Tests — wire 5+ Photos-album fixtures via P2.0 importer post-Azure-pairing; resolves OCR-moat ocr-corpus-cron blocker [ETA: 3h]

### Localization Phase 2-7 (was task #6 [pending])
- [completed] T12: Phase 2 — sweep remaining hardcoded `Text("...")` violations; convert to CopyTokens; grep gate `grep -rn 'Text("' ResplitCore/UI/ ReceiptSplitter/UI/` returns zero non-CopyTokens hits [Verified: /goal cycle 3 grep `grep -rnE 'Text\("[^"]*"\)' ResplitCore/UI/ --include='*.swift'` returned 6 hits in production code; ALL 6 are legitimately non-localizable (typographic glyphs `•`/`—`, pure numeric interpolations `\(count)`, emoji `🎉`). DevGallery has more hits but those are dev-only surfaces (not shipped to TestFlight per CLAUDE.md). ReceiptSplitter has no `UI/` subdirectory (Calculators/DTOs/Models only). Phase 2 sweep is functionally complete — plan-flip only, no code change needed. 6 audited hits: RatesAttributionFooter.swift:21 `Text("•")`, ConversionWorkbenchSheet.swift:398+1069 `Text("—")` ×2, AddPeopleSheet.swift:567 `Text("\(viewModel.pendingSelectionCount)")`, LiveSessionClaimBadge.swift:49 `Text("+\(claimants.count - 3)")`, WrapUpSheet.swift:60 `Text("🎉")`.]
- [pending] T13: Phase 3-4 — translation parity audit across 8 target locales (en, es, fr, de, ja, ko, zh-Hans, pt-BR, th) [ETA: 6h]
- [pending] T14: Phase 5-6 — String Catalog plural variations + interpolation audit per `Localizable.xcstrings` [ETA: 4h]
- [pending] T15: Phase 7 — XCTestPlan locale matrix per CLAUDE.md §Localization (one test run per `AppleLanguages` value) [ETA: 3h]

### Bug Triage (Linear EVE + Jam.dev + ASC)
- [pending] T16: Read every open Linear EVE issue; ack with comment + file Fix Spec investigation per CLAUDE.md §Bug Fix Discipline [Evidence: per /linear playbook] [ETA: 2h, recurring per /resplit-watch tick]
- [pending] T17: Read every recent Jam.dev recording; convert to investigation per /jam skill workflow [ETA: 2h, recurring]
- [pending] T18: Resolve all 8 ASC tracker rows in `.cursor/plans/app-store-feedback.plan.md` per investigation-first discipline [Evidence: per row Fix Spec]

### Skill Improvements (Self)
- [completed] T19: `/autobot-resplit` + `/autobot-resplit-web` — codify the 4-layer lock pattern (sheet+detents + banned constants + source-grep MT-5 + UI test) as standard playbook [Fix: ~/Development/ai/skills/autobot-resplit/SKILL.md § "Regression-Prevention Discipline — 4-Layer Lock Pattern" (iOS-specific) + ~/Development/ai/skills/autobot-resplit-web/SKILL.md § same (web analogue, Radix/Tailwind/eslint/Playwright)] [Shipped: ~/Development/ai commit `37ee490` direct-to-main per /captain skill discipline; 186 lines added across two SKILL.md files] [Evidence: includes Lock-status badge template for auditable per-surface tracking + cross-stack iOS↔web parity]
- [completed] T20: `/vidux-leo` — codify "Append-to-vidux-goal" binding rule (this /goal's enforcement mechanism) as a section in `~/Development/ai/skills/vidux-leo/SKILL.md` [Fix: ~/Development/ai/skills/vidux-leo/SKILL.md § "Append-to-vidux-goal (2026-05-14, binding for all Claude-goal writes)"] [Shipped: pre-cycle-1 (section already present in loaded skill, verified during /goal cycle 1 READ)] [Evidence: skill section enforces 5-step discipline including PLAN.md hooking + forbidden-pattern enumeration]
- [completed] T21: `/frontend-design` — Resplit-side dark-mode + Liquid Glass token reference for cross-stack consistency with web [Fix: ~/Development/ai/skills/frontend-design/SKILL.md § "Resplit Cross-Stack Token Parity (iOS ↔ Web)" — 9-row color parity table (iOS Swift token → CSS var → Tailwind utility → light hex → dark hex), dark-mode mechanism comparison, Liquid Glass iOS 26 → web backdrop-blur mapping (4 surface treatments), spacing/radius/typography parity, 5-step iOS-port workflow citing /vidux-leo iOS-port verification gate] [Shipped: ~/Development/ai commit `3d23d62` direct-to-main per /captain. 72 lines added.]
- [completed] T22: `/brand-resplit` unfreeze-prep doctrine — draft post-2.0-ship restoration procedure (do NOT unfreeze yet) [Fix: ~/Development/ai/skills/brand-resplit/SKILL.md § "Unfreeze procedure (post-2.0)" expanded from 4 terse steps to 6-phase doctrine (Verification gates / Leo-auth gate / Active layer pick / Phased restoration from archive / Audit hooks / First-post-unfreeze cycle is NOT brand work)] [Shipped: ~/Development/ai commit `7433ac0` direct-to-main per /captain. 76 lines added. Skill REMAINS FROZEN — this codifies the procedure for future readiness, NOT for current execution. Includes compliance self-check for future agents.]

### Reality-Proof Ship Gate
- [pending] T23: Resolve systematic-build-hang — Leo opens `/Applications/Xcode-26.4.1.app` once for first-launch + license accept (Path 3 from investigation) — UNBLOCKS T5/T6/T8/T10/T11 + all sim verification [Leo step, ~5min] [ETA: 0.25h]
- [pending] T24: Pre-2.0-tag full gate matrix per CLAUDE.md §Cross-Platform Gate Matrix (iOS build + 4 test schemes + web lint/test/build/e2e) [ETA: 2h]
- [pending] T25: Phase E pre-ship device walk — post checklist to ## Progress, halt with `AWAITING-DEVICE-WALK`, Leo verifies on device, edits row to `[verified-on-device]`, then 2.0 tag + Leo runs `bundle exec fastlane beta` (per Loop Learning #8: NEVER cron-fire fastlane) [ETA: 1h Leo + 0.5h orchestration]
- [completed] T26: TestFlight release-notes clarity — patch `fastlane/Fastfile:340` + `:558-560` + `:599` + `:611` to derive changelog from `git log <last-tag>..HEAD --oneline` filtered to user-visible commits (`feat`/`fix` prefixes, exclude `chore`/`docs`/`test`/`refactor`/`ci`). Cap at 80 chars × 8 lines per TestFlight What-to-Test field limits. Replace generic `"Build N"` / `"Beta N"` strings. Update CLAUDE.md §Automated shipping cadence note 2h→3h to match deploy-watcher StartInterval=10800. [Evidence: Leo 2026-05-14 verbatim "ensure that the test flgiht submissions have claer release notes and we do it evrey 3 hours"] [Fix: fastlane/Fastfile:59-101 (new auto_changelog helper) + :349 + :569; CLAUDE.md:429 + :466-475] [PR: firstbitelabsllc/resplit-ios#641] [Shipped: merge commit `b499ff8c` on main] [Codex P2 caught + YAY-acked + fixed in `a7a34e9c` (skip tags pointing at HEAD via `--exclude`)]

### Cycle-1 discoveries (appended mid-cycle per /vidux-leo § Append-to-vidux-goal)
- [completed] T27: Whitelist `projects/resplit-2-0-readiness/` in `~/Development/vidux/.gitignore` so this PLAN.md syncs across Leo's Studio + M4 Pro machines [Evidence: `~/Development/vidux/.gitignore:15` `projects/*` blanket ignore + whitelist exceptions for resplit-2-0-weekend-push / resplit-2-0-localized-screenshots / resplit-2-0-1 — readiness/ was missed when this plan was scaffolded 2026-05-14; PLAN.md currently local-only, single-machine fragility violates /goal "done-done" invariant] [Fix: ~/Development/vidux/.gitignore:41-44 (new `!projects/resplit-2-0-readiness/` exception) + initial commit of `projects/resplit-2-0-readiness/PLAN.md`] [PR: leojkwan/vidux#106] [Shipped: merge commit `7aa7409` on main]
- [pending] T28: Bundle ASC tracker `AFEPIcFQkCzNgXA2gzmkd0Y` plan-flip into next code PR — status `triaged`→`fixed`, fix_commit `3b3ffad6` (PR #632 merged 2026-05-09 iOS-native infinite scroll), handled_at `2026-05-14`, note "Plan-flip catch-up by /goal cycle 1 — fix shipped 2026-05-09 in PR #632, plan row was stale; harness-rule-9 carry-into-next-code-PR." [Evidence: `.cursor/plans/app-store-feedback.plan.md:243-254` `status: triaged` vs commit `3b3ffad6` shipped 2026-05-09; per CLAUDE.md MT-1 bundle plan updates into next code PR not standalone bookkeeping] [ETA: 0.1h, bundle into next code PR]

## Decision Log
- [DELETION] [2026-05-14] Uninstalled `com.leokwan.resplit-2-0-loop` launchd cron. Replaced by CC `/goal` against this PLAN.md. Doctrine migrated to "## Loop Learnings" sub-plan above. Reason: /goal supersedes loop constructs — single long-running session beats 10-min cron firings + claude-opus-4-7 -p invocations + atomic-claim race-safety overhead. Sibling crons (/resplit-watch, /autobot-resplit-cron, /ocr-corpus-cron, coordinator) survive as DETECTION inputs.
- [DIRECTION] [2026-05-14] /goal owns SYNTHESIS + skill-self work + 2.0 ship orchestration; sibling crons drain pending rows + surface findings. /goal does not spawn new crons.
- [DIRECTION] [2026-05-14] Ship Phase D (Closeout) BEFORE bot-wait. Order: ready → `@graphite review` → flip PLAN.md `[in_review]` + commit + push → THEN poll. Per Loop Learning #5 (subagent dispatch hygiene).
- [DIRECTION] [2026-05-14] Graphite-wait HARD CAP at 15 minutes. Per Leo verbatim *"i wouldnt' wait on graphite btw after 15 minutes hard rule"*. Overrides /vidux-leo §1's prior 60-min stalled-Graphite escalation rule for /goal-mode operation. Threads must still be checked via `gh api graphql reviewThreads` before merge — only the wait-for-verdict timer is capped.
- [DIRECTION] [2026-05-14] TestFlight cadence 2h→3h via `com.leokwan.deploy-watcher` (StartInterval 7200→10800s, plist updated + reloaded). Release notes MUST be clear and specific — see T26 for the Fastfile changelog patch. Per Leo verbatim *"do it evrey 3 hours please"*.

## Progress
- [2026-05-14T05:00:00Z] PLAN.md scaffolded. /resplit-2-0-loop launchd cron uninstalled. Loop doctrine migrated. Cycle 0. ETA-remaining: ~58.75h. Tasks: 25 pending, 0 in_progress, 0 done.
- [2026-05-14 cycle 1] T26 + T27 SHIPPED. **T26** TestFlight release-notes: Fastfile `auto_changelog` helper (8 lines × 80 chars cap, `feat:`/`fix:` filter, strip-prefix, fallback to "Build N") + CLAUDE.md 2h→3h cadence note → firstbitelabsllc/resplit-ios#641 merged `b499ff8c`. Codex P2 caught the `release` lane tag-at-HEAD scenario; YAY-acked + fixed via `--exclude` in `a7a34e9c` + thread resolved. Graphite re-reviewed PASS post-fix in ~2min (well under 15-min cap). **T27** vidux .gitignore whitelist: added `!projects/resplit-2-0-readiness/` + initial commit of PLAN.md (130 lines) → leojkwan/vidux#106 merged `7aa7409` (Tier B OWNER-merge). **T20** already shipped pre-cycle (skill section present). Mid-cycle discoveries: **T27** (resolved this cycle), **T28** (AFEPIcFQ ASC plan-flip, bundle into next code PR). ETA-remaining: ~55.75h on 25 unblocked pending (T23 still blocks T5/T6/T8/T10/T11/T24/T25). Tasks: 25 pending, 0 in_progress, 3 completed.
- [2026-05-14 cycle 2] T2 + T19 SHIPPED. **T2** ObservableObject → @Observable: grep audit returned ZERO violations across ResplitCore/ + ReceiptSplitter/ (42 files use @Observable). Migration was already structurally complete — plan-flip only, no code change needed. **T19** /autobot-resplit + /autobot-resplit-web 4-layer lock pattern codification: added "Regression-Prevention Discipline" section to both skills (iOS-specific sheet+detents/banned-constants/source-grep MT-5/XCUITest + web analogue Radix-primitives/Tailwind-tokens/eslint-rule/Playwright) with Lock-status badge templates for auditable per-surface tracking → ~/Development/ai commit `37ee490` direct-to-main per /captain. 186 lines across two SKILL.md files. ETA-remaining: ~53.25h on 23 unblocked pending. Tasks: 23 pending, 0 in_progress, 5 completed.
- [2026-05-14 cycle 3] T12 + T22 SHIPPED. **T12** Localization Phase 2 sweep: grep audit found 6 `Text("...")` hits in production ResplitCore/UI/ but ALL 6 are non-localizable (typographic glyphs `•`/`—`, numeric interpolations, emoji `🎉`); DevGallery is dev-only; ReceiptSplitter has no UI/ subdir. Phase 2 functionally complete — plan-flip with full audit notes. **T22** /brand-resplit unfreeze-prep doctrine: expanded terse 4-step procedure to 6-phase doctrine (5 verification gates, explicit Leo-auth trigger phrase, single-active-layer pick, pare-then-restore archive discipline, regression-prevention audit hooks, post-unfreeze cycle 1 is NOT brand work). Skill REMAINS FROZEN — codifies procedure for future readiness, not current execution → ~/Development/ai commit `7433ac0` direct-to-main per /captain. 76 lines added. ETA-remaining: ~48.25h on 21 unblocked pending. Tasks: 21 pending, 0 in_progress, 7 completed.
- [2026-05-14 cycle 4] T21 SHIPPED. **T21** /frontend-design Resplit cross-stack token parity: added "Resplit Cross-Stack Token Parity (iOS ↔ Web)" section with 9-row color parity table (iOS Swift token → CSS var → Tailwind utility → light hex → dark hex), dark-mode mechanism comparison, Liquid Glass iOS 26 → web backdrop-blur mapping for 4 surface treatments (sheet/FAB/nav-bar/popover), spacing/radius/typography parity, 5-step iOS-port workflow → ~/Development/ai commit `3d23d62` direct-to-main per /captain. 72 lines added. iOS @ResplitDesignSystem is canonical source of truth; web tokens.css mirrors. ETA-remaining: ~46.75h on 20 unblocked pending. Tasks: 20 pending, 0 in_progress, 8 completed.
