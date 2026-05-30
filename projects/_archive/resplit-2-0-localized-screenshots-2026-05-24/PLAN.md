# Resplit 2.0 — Localized App Store screenshots + computer-use verification

## Purpose

Ship marketing-quality App Store screenshots in 9 locales (en + de/es/fr/ja/ko/pt-BR/th/zh-Hans) for the Resplit 2.0 App Store Connect listing. Add Anthropic computer-use agent verification to catch locale-specific UI defects (clipping, truncation, font failures, untranslated strings) before submission. Extend autobot-resplit + autobot-resplit-web crons to sweep locales on every cycle.

This plan is the multi-day expedition that takes the current en-only 12-surface autobot baseline (`docs/autobot-evidence/baselines/2026-05-01-sim-walk-baseline/MANIFEST.md`) and grows it into a 9-locale ASC-uploadable bundle, with an automated verification loop that doesn't depend on Leo eyeballing 216 screenshots by hand.

## Parent plan

Sibling Resplit 2.0 expedition plans:

- **Bug-fix lane**: `~/Development/vidux/projects/resplit-2-0-weekend-push/PLAN.md` — 8 ASC bug rows blocking the 2.0 ship. **GATE**: this localized-screenshots plan does NOT promote to `[in_progress]` until weekend-push T1–T9 lands a TestFlight build with all eight bugs verified. Phase 1 capture pipeline can be built (it's plumbing, not surface work) but Phase 6/7 ASC submission waits for the bug-fix lane.
- **Punch-list lane**: `~/Development/vidux/projects/resplit-2-0-1/PLAN.md` — post-launch polish queue.
- **Web lane mirror**: `~/Development/resplit-web/vidux/resplit-2.0-launch/PLAN.md` — multi-platform mega plan; Phase 5 of THIS plan extends `/autobot-resplit-web` cron to sweep web locales the same way Phase 4 extends iOS.

## Evidence

- **[Source: codebase]** `CLAUDE.md` §Localization — 9 locales: en (source) + de/es/fr/ja/ko/pt-BR/th/zh-Hans. CopyTokens API (`ResplitCore/Localization/CopyTokens.swift`) + `ResplitCore/Resources/Localizable.xcstrings`. `AppleLanguages` launch arg overrides per-process.
- **[Source: codebase]** `docs/autobot-evidence/baselines/2026-05-01-sim-walk-baseline/MANIFEST.md` — 12 surfaces × 2 modes (light + dark) = 24 baseline screenshots, all en only. This is the surface set Phase 1 multiplies by 9 locales.
- **[Source: ASC requirement]** App Store Connect requires localized screenshots per supported locale OR English-fallback flag set per locale. We can ship Phase 1 with 4 locales + English-fallback flag on the other 5; Phase 2-3 close the gap before public launch.
- **[Source: codebase]** PR #575 i18n coverage tests + `LocalizationCoverageTests` assert 0 hardcoded `Text()` literals + 0 xcstrings gaps across 9 locales — meaning if a key is missing translation, the build fails. This Phase 2 computer-use verification catches the runtime layer (clipping, font, truncation) that the test layer can't see.
- **[Source: codebase]** `ResplitDevApp` + `/autobot-resplit` X1 smoke preset + `UITestScenarios` already route to deterministic surface state. Locale sweep needs locale launch-arg variation, not new test infrastructure. Surface coverage stays at the 12 listed in the baseline MANIFEST.
- **[Source: skill]** `~/Development/ai/skills/autobot-resplit/SKILL.md` — global iOS sim driver. Cron extension in Phase 4 lives here.
- **[Source: skill]** `~/Development/ai/skills/autobot-resplit-web/SKILL.md` — web-side mirror. Cron extension in Phase 5 lives here.
- **[Source: Anthropic]** Computer Use API (claude-opus-4-7 with `computer_20251023` tool) — the verification agent in Phase 2. Input: screenshot + locale + surface name. Output: per-screenshot defect list (clipping, truncation, font failure, untranslated string visible, RTL/wrap issue).
- **[Source: Leo verbatim 2026-05-07]** *"big things like screeneshots loclaization @computer use see and localize and /autobot-resplit /autobot-resplit-web cron and amp /pilot u know we need to do /vidux"* — the directive that opened this plan.

## Constraints

### ALWAYS

- Use launch-arg `-AppleLanguages "(<locale>)"` per locale per CLAUDE.md §Localization. AppleLanguages launch arg is the only correct way; `.environment(\.locale)` does not affect static-let CopyTokens (they resolve at process launch).
- Capture both light + dark mode per locale (24 captures × 9 locales = 216 surface captures for full baseline; Phase 1 partial = 24 × 4 = 96).
- Save Phase 1+ captures to `docs/asc-screenshots/<YYYY-MM-DD>/<locale>/<surface>-<mode>.jpg` (NOT `docs/autobot-evidence/` — that path is for bug-fix BEFORE/AFTER pairs per CLAUDE.md §Visual Proof Merge Gate, not ASC marketing screenshots).
- Wrapped + isolated build form per CLAUDE.md §Build Isolation Mandatory: `tuist xcodebuild build -scheme 'Resplit Debug' -derivedDataPath /tmp/resplit-dd-T<N>-${RANDOM}` — never collide with deploy-watcher's `~/Library/Developer/Xcode/DerivedData`.
- Computer-use verification agent runs against EVERY locale capture, not just non-en. en captures must also pass — catches font/wrap regressions from the source language.
- Defects flagged by Phase 2 surface as `[pending]` rows under "## Locale defects" in this plan, with `<locale>/<surface>/<mode>` path + defect class + screenshot link. Each row becomes a CopyTokens or layout fix in resplit-ios in a follow-up PR.
- Phase 1 ships 4 locales: en + es + ja + fr (the highest-volume non-en App Store markets per ASC analytics). Phase 2-3 add the remaining 5 (de/ko/pt-BR/th/zh-Hans) before public launch.

### NEVER

- Use machine translation for xcstrings missing translations. If a key has no translation, surface it as a P0 ASC follow-up (open a row in `.cursor/plans/app-store-feedback.plan.md`), do NOT auto-fill via Google Translate / DeepL / equivalent.
- Ship screenshots with visible English fallback strings on non-en locales. The computer-use agent's primary job is catching this — if the agent sees an English string in a `ja` capture, it's a P0 defect, not a "ship anyway" row.
- Gate the public launch on full 9-locale coverage. Phase 1 (4 locales) + ASC English-fallback flag on the remaining 5 is acceptable for the 2.0 submission. Phase 2-3 close the gap as a fast-follow.
- Promote any task in this plan to `[in_progress]` until the 2.0 weekend-push lane lands a TestFlight build with all eight ASC bugs verified. Per `/auto` ship-window override: 2.0 fastlane ships first, screenshot expedition follows.
- Touch resplit-ios source in this plan-creation PR. This is a vidux plan-creation task only. Code lands in resplit-ios via Phase 1+ subagent dispatches AFTER plan merges.
- Brand work. `/brand-resplit` is FROZEN. Phase 6 ASC submission uses existing brand assets; no gradient/token/copy polish is in scope here.
- Run computer-use against arbitrary internet URLs. The verification loop is sandboxed to local screenshot files only — agent reads PNG bytes, no network egress.

## Tasks

- [pending] **P1** Capture pipeline foundation. Extend `/autobot-resplit` X1 smoke preset to accept `--locale <code>` flag. Loop drives 4 locales (en/es/ja/fr for Phase 1) × 12 surfaces × 2 modes = 96 captures. Saves to `docs/asc-screenshots/<YYYY-MM-DD>/<locale>/<surface>-<mode>.jpg`. Implementation: extend `~/Development/ai/skills/autobot-resplit/scripts/sim-walk.sh` (or equivalent) to accept the flag, set `AppleLanguages` launch arg, run the surface sweep. [Evidence: docs/autobot-evidence/baselines/2026-05-01-sim-walk-baseline/MANIFEST.md] [DerivedData namespace: `/tmp/resplit-dd-T1-${RANDOM}`] [ETA: 2h]
- [pending] **P2** Computer-use verification loop. Build a verification harness that takes a directory of locale captures and asks claude-opus-4-7 (with `computer_20251023` tool) per-screenshot: "is any text clipped, truncated, wrapped wrong, untranslated, or font-broken?" Returns a JSON defect list per (locale, surface, mode). Implementation: Anthropic SDK Python or TypeScript harness in `~/Development/ai/skills/autobot-resplit/scripts/locale-verify.{py,ts}`. Cache hits across re-runs (prompt caching for the system prompt + locale spec). [Evidence: Anthropic Computer Use API doc; `/claude-api` skill] [ETA: 4h]
- [pending] **P3** Defect triage feedback loop. Defects flagged by P2 become `[pending]` rows in the "## Locale defects" section of THIS plan, each with screenshot path + locale + surface + mode + defect class (clipping / truncation / font / untranslated / wrap / contrast). Each row becomes a CopyTokens key fix or a SwiftUI layout fix in a follow-up resplit-ios PR. P3 closes when "## Locale defects" has zero `[pending]` rows. [ETA: 2h to wire the harness; defect-triage time scales with defect count]
- [pending] **P4** `/autobot-resplit` cron extension. Every cycle picks 1 locale (round-robin across 9), runs full 12-surface sweep, diffs against last-cycle baseline. Defect-positive cycles dispatch a fix lane (per `/vidux` + `/auto` ship-don't-ask); clean cycles append a `[CLEAN] <locale>` memory entry. Persist round-robin state in `~/.agent-ledger/autobot-resplit-locale-cursor`. [Evidence: ~/Development/ai/skills/autobot-resplit/SKILL.md] [ETA: 3h]
- [pending] **P5** `/autobot-resplit-web` cron mirror. Same pattern for resplit-web (Playwright + 9 locale headers via `Accept-Language` + i18n routing). Surfaces: landing, splitter, settle, share, FAQ. Defect-triage feedback loop same as P3 but writes to a "## Web locale defects" section and dispatches resplit-web PRs instead of resplit-ios. [Evidence: ~/Development/ai/skills/autobot-resplit-web/SKILL.md] [ETA: 4h]
- [pending] **P6** ASC screenshot pipeline. Assemble Phase-1 captures (4 locales × 12 surfaces × 2 modes) into App Store Connect-uploadable bundles per device size class (iPhone 14 Pro 6.7", iPhone 14 6.1", iPhone SE 5.5"). Run through Fastlane `frameit` if framing is needed. Output: `output/asc-bundle-<YYYY-MM-DD>/<locale>/<size-class>/<screenshot-N>.png` ready for `fastlane deliver` or manual ASC upload. [Evidence: fastlane deliver doc; existing screenshot conventions in `fastlane/screenshots/`] [ETA: 2h]
- [pending] **P7** ASC submission. Upload Phase-1 bundle to ASC via `fastlane deliver --skip_metadata false --screenshots true` or manual upload. Flag the 5 non-Phase-1 locales (de/ko/pt-BR/th/zh-Hans) as English-fallback to avoid ASC rejection. Confirm ASC processing succeeds (no rejected screenshots — wrong size, transparent pixels, white-frame issues). [Evidence: ASC API; fastlane deliver; existing 2.0 listing draft] [ETA: 1h]

**ETA total**: 2 + 4 + 2 + 3 + 4 + 2 + 1 = **18h** of compute-shaped work, spread across multiple cron cycles. P1+P2 are blocking and serial (P2 depends on P1's captures). P3 is a continuous loop. P4+P5 are independent and parallelizable. P6+P7 are serial and depend on P1-P3 closing.

## Decision Log

- **[DIRECTION] 2026-05-07** — Phase 1 ships en + es + ja + fr (4 locales), not full 9. Reason: ASC accepts English-fallback flag for unsupported locales without rejection. Full 9 across 12 surfaces × 2 modes = 216 captures = 4-6h of compute time per full sweep. Phase 2 adds the remaining 5 locales (de/ko/pt-BR/th/zh-Hans) after Phase 1 ships and computer-use agent verifies Phase 1 quality. Source: ASC documentation on language-fallback behavior; surface-count math.
- **[DIRECTION] 2026-05-07** — Computer-use agent over manual review. Reason: 216 screenshots × manual eyeball = 6+ hours of human time per full sweep, repeated every cycle. Computer-use does it in ~30min compute time. Cost: per-screenshot API spend, but cheaper than launch delay or human-time burn. Anthropic prompt caching brings the per-screenshot cost down ~5x for the system prompt + locale spec.
- **[DIRECTION] 2026-05-07** — Save ASC marketing screenshots to `docs/asc-screenshots/`, NOT `docs/autobot-evidence/`. Reason: `docs/autobot-evidence/` is reserved for bug-fix BEFORE/AFTER pairs per CLAUDE.md §Visual Proof Merge Gate. Mixing ASC marketing captures into that path conflates two different artifact classes and breaks merge-gate auditing. Existing `docs/asc-screenshots/<receipt-id>/` pattern (already in repo for ASC investigations) extends naturally to `docs/asc-screenshots/<YYYY-MM-DD>/<locale>/<surface>-<mode>.jpg`.
- **[DIRECTION] 2026-05-07** — Phase 1 capture pipeline (P1) can start IMMEDIATELY once this plan merges. Phases 2-7 sequence per the gate: 2.0 weekend-push must land a TestFlight build with all eight ASC bugs verified before P6/P7 submit ASC bundles. P2 (computer-use verification) and P3 (defect triage) can run on Phase 1 captures in parallel with the bug-fix lane shipping — they surface defects to fix, they don't gate the bug-fix work.
- **[DIRECTION] 2026-05-07** — Computer-use verification target = claude-opus-4-7 via `~/Development/ai/skills/claude-api/SKILL.md` patterns. Use Anthropic prompt caching for the system prompt (locale spec + defect rubric) — cache hit rate >95% expected since the system prompt is identical across all 216 captures.

## Progress

(empty — first cycle)

## Locale defects

(empty — populated by P3 once P2 starts surfacing defects)

## Web locale defects

(empty — populated by P5 once /autobot-resplit-web cron extension lands)
