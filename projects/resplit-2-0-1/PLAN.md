# Resplit 2.0.1 — Post-Launch Punch-List

**Status:** OPEN (project frame only — every task `[pending]`, no `[in_progress]` allowed until 2.0 fastlane ships AND user-reported regressions clear F&F).

**Created:** 2026-05-07 by `claude-opus-4-7-rios` lane subagent. Cron deferred Tier-2.3 work for ~9 cycles citing "project does not exist yet" — this PLAN is the unblock signal.

## Purpose

Post-launch 2.0.1 punch-list. Tier-2 backlog activated AFTER 2.0 ships. Brand-frozen items unfreeze here. Net-new feature pump turns ON here.

This file is the convergence point for the iOS lane's post-launch follow-on. Every parked row from the 2.0 weekend push, every brand backlog item placed under `/brand-resplit` FROZEN status, every Phase 2+ feature gated on TestFlight stability, and every visual-proof BACKFILL deferred under the esoteric-repro carve-out lands here and waits.

Consuming agents (cron, /resplit-2-0-loop Tier-2.3, lane-leads): claim a `[pending]` row by atomic-claim contract once the activation gate clears. Until activation, this plan is a queue — visible but inert.

## Activation Gate

This plan is **dormant** until ALL of these are true:

1. `bundle exec fastlane beta` from main has shipped Build N+1 (2.0.1-eligible build) AND TestFlight Friends & Family external tester pool has at least 48h of crash-quiet + Sentry-quiet on the 2.0 build (`v2.0.0` tag).
2. App Store promotion of `v2.0.0` (manual ASC step or `fastlane deliver`) has either landed OR Leo has explicitly opened the 2.0.1 lane while 2.0 sits in "Waiting for Review" (whichever comes first).
3. No open ASC bug from 2.0 reporter pool (last 7 days) without a fix-on-the-way investigation.

When 1+2+3 are green, agents may flip rows below from `[pending]` to `[in_progress]`. Until then: hands off.

## Evidence

All parked-2.0.1 rows discovered 2026-05-07 across resplit-ios + vidux plan files. Each task carries [Source: <plan-path>:<line>] or [Source: ASC <id>] citation.

### Inventory (16 rows total across 6 categories)

| # | Row | Category | Source | Size |
|---|-----|----------|--------|------|
| 1 | T8 ADIQ — SF Symbol replace icon | ASC partial-positive | `~/Development/vidux/projects/resplit-2-0-weekend-push/PLAN.md:202` ASC ADIQ | XS |
| 2 | Memories-strip surface decision | Brand FROZEN | `.cursor/plans/investigations/memories-strip-concept-2026-04-25.md:5,220,240` | XL |
| 3 | Gradient v7 token rollout | Brand FROZEN | `~/Development/ai/skills/brand-resplit/_archive/SKILL.md` (v7 doctrine, frozen 2026-05-01) | L |
| 4 | Bold v6 chrome reconciliation | Brand FROZEN | `.cursor/plans/investigations/memories-strip-concept-2026-04-25.md:63` | M |
| 5 | Net-new feature pump turn-ON | Net-new backlog | `~/Development/vidux/projects/resplit-2-0-weekend-push/PLAN.md:238` | — |
| 6 | Photo Thumbnail Badge on receipt list | Receipt-photos Phase 2+ | `.cursor/plans/resplit-receipt-photos-joyful.plan.md:60` | S |
| 7 | Multi-Photo Support (multi-angle uploads) | Receipt-photos Phase 2+ | `.cursor/plans/resplit-receipt-photos-joyful.plan.md:61` | M |
| 8 | Share with Photo (attach to expense share) | Receipt-photos Phase 2+ | `.cursor/plans/resplit-receipt-photos-joyful.plan.md:62` | M |
| 9 | Photo Attachment Metadata (timestamp/location) | Receipt-photos Phase 2+ | `.cursor/plans/resplit-receipt-photos-joyful.plan.md:63` | S |
| 10 | Phase 1.5 pinch-zoom hardening | Receipt-photos Phase 1.5 | `.cursor/plans/resplit-receipt-photos-joyful.plan.md:54` (zoom gesture; ship-gate item) | S |
| 11 | Multi-photo carousel surface | Receipt-photos Phase 2+ | `.cursor/plans/investigations/asc-c407-receipt-photo-hero.md:49` | M |
| 12 | Photo sharing / attachment flow | Receipt-photos Phase 2+ | `.cursor/plans/investigations/asc-c407-receipt-photo-hero.md:48` | M |
| 13 | Apple Intelligence / VisionKit prebuilt receipt extractor research | OCR-moat post-launch | `.cursor/plans/investigations/asc-akig-ocr-key-value-extraction.md:217` ASC ID 656 comment | L |
| 14 | Photos album population gate (entitlement / privacy plan) | OCR-moat / receipt-photos post-launch | `.cursor/plans/resplit-receipt-photos-joyful.plan.md:113-117` (Phase 2b–2d) | L |
| 15 | Visual proof BACKFILL — T1/T2/T3/T4/T5/T6/T7 esoteric-repro carve-outs | Visual proof debt | `~/Development/vidux/projects/resplit-2-0-weekend-push/PLAN.md:182-198` (7 PRs shipped with carve-outs) | M |
| 16 | OCR-moat P3 — v4-aware Reconciler (absorbs asc-akig Phase 2) | OCR-moat post-launch | `~/Development/vidux/projects/ocr-moat/PLAN.md:55,65` | XL |

## Constraints

### ALWAYS
- Every row is `[pending]` until activation gate (see above) clears. Cron and lane-leads MUST check the activation gate before claiming any row.
- Every fix PR follows CLAUDE.md `§Visual Proof Merge Gate` + `§MT-5` + `§Build Isolation Mandatory` + `§Bug Fix Discipline`. The 2.0 weekend push relaxed visual proof to "esoteric-repro carve-out" for 7/7 fixes; 2.0.1 work has full sim-fixture access (smoke harness shipped in PRs #554/555/557) so the carve-out should be much rarer here.
- Any brand row (v7 gradient rollout, v6 Bold chrome, memories-strip) requires Leo's explicit unfreeze ACK before flipping `[pending]` → `[in_progress]`. No agent flips brand work autonomously.
- Net-new feature pump (row 5) requires Leo's explicit "pump ON" call. Until then, only post-launch FOLLOW-ON tasks (rows that were already half-shipped or directly extend a shipped 2.0 row) are eligible.
- After flipping a row to `[completed]`, append a `## Progress` line + a `## Decision Log` entry citing the squash SHA and PR URL.

### NEVER
- Do NOT promote any row to `[in_progress]` while 2.0 has open ASC reporter bugs without a fix-on-the-way investigation file.
- Do NOT unfreeze `/brand-resplit` autonomously. The skill's `_archive/SKILL.md` stays archived until Leo says go.
- Do NOT pitch any new net-new feature into Leo's chat queue while 2.0 still has live tester regressions. Append the idea to row 5's growing list, stay silent.
- Do NOT close any 2.0.1 row by claiming "absorbed into 2.0" without a squash-SHA citation that proves the absorption.
- Do NOT reorder this PLAN's rows without a `## Decision Log` entry. The plan is append-only for evidence, mutable for status flips per `/vidux` Principle 4.

## Tasks

All rows below are `[pending]`. They activate per the §Activation Gate above.

### Category 1 — ASC carry-over from 2.0 weekend push

- `[pending]` **R1 — ADIQ: replace icon with SF Symbol** [Source: ASC ID ADIQ, quote "Love this, i would prefer a SF symbol indicating more trust and less talk, copy cut down get brand Resplit on this"] [Original deferral: `~/Development/vidux/projects/resplit-2-0-weekend-push/PLAN.md:202` (T8 deferred 2026-05-01)] [Sub-plan: `~/Development/vidux/projects/resplit-2-0-weekend-push/tasks/T8-ADIQ-sf-symbol-deferred/PLAN.md`] [ETA: 0.5h–1h] — Partial-positive feedback ("love this" + soft preference). Surface = the icon the reporter referenced (need to confirm via the ASC screenshot before code). Fix = swap to SF Symbol, copy cut, brand-resplit pass on the surrounding text. Visual proof BEFORE/AFTER required (real screenshots — fixture exists post-2.0). MT-5 = snapshot test on the new icon-bearing view.

### Category 2 — Brand-resplit FROZEN backlog (requires Leo unfreeze ACK)

- `[pending]` **R2 — Memories-strip surface decision (BoldV1 vs Gradient variants)** [Source: `.cursor/plans/investigations/memories-strip-concept-2026-04-25.md:5,220,240` — 6 concept JPGs at `docs/autobot-evidence/2026-04-25-memories-strip-concept/`] [ETA: 4h–8h once unfrozen — design call + nav placement + implementation slice] — Concept work shipped 2026-04-25 (6 mock variants). FROZEN under 2.0 push. Decision: pick a variant, pick a host surface (TripDetail? Profile? Settle Up?), implement smallest slice. ASK-LEO-MANDATORY for variant pick + surface placement.

- `[pending]` **R3 — Gradient v7 token rollout (named tokens — gradientSpoon/Fork/Mouth/CoralHero)** [Source: `~/Development/ai/skills/brand-resplit/_archive/SKILL.md` v7 doctrine 2026-04-22; frozen 2026-05-01 per `~/Development/vidux/projects/resplit-2-0-weekend-push/PLAN.md:224`] [ETA: 2h–4h once unfrozen] — v7 reverses v6 flat-3-token diet: teal back, gradients are named tokens, photo-avatar pattern + gradient-ring fallback. Rollout = grep + audit existing surfaces, propose surface-by-surface diff. Likely to land as 3–5 small PRs not one mega-PR. ASK-LEO-MANDATORY on the per-surface diff list before any code.

- `[pending]` **R4 — Bold v6 chrome reconciliation** [Source: `.cursor/plans/investigations/memories-strip-concept-2026-04-25.md:63` — "Bold receipt-chrome is restricted to 'literal receipt / bill / settle surfaces'"; ReceiptDetail still qualifies] [ETA: 1h–2h once unfrozen] — Tighten Bold v6 chrome boundaries. Audit current Bold usage, confirm it's only on literal-receipt surfaces, propose removal from any drift surface. ASK-LEO-MANDATORY on the kept-vs-removed list.

### Category 3 — Net-new feature backlog (pump OFF until 2.0 ships clean)

- `[pending]` **R5 — Net-new feature pump turn-ON ceremony** [Source: `~/Development/vidux/projects/resplit-2-0-weekend-push/PLAN.md:238` Constraint NEVER section, Leo verbatim 2026-05-01: *"I have a lot of things that I want us to like work on that's like net new or like kind of uncovered from a long time ago, but I don't want to talk about that unless we're ready to at least start shipping and working first."*] [ETA: 1h structured Leo conversation] — Once 2.0 ships F&F clean, schedule a structured net-new-feature unlock conversation with Leo. Bring: (a) accumulated ideas appended to this row's sub-rows over the dormant period, (b) prioritization frame (XS effort + max brand-fit + clearest user value), (c) one-row-at-a-time proposal not a 10-row firehose. ASK-LEO-MANDATORY on the unlock.

  - **Sub-row R5.a (placeholder for accumulated ideas):** when an agent feels the urge to pitch a net-new idea before activation, append the idea here as a one-line bullet with date stamp. Do NOT chat-pitch it. This is the "say nothing in chat until 2.0 ships" doctrine codified at the row level.

### Category 4 — Receipt-photos joyful Phase 2+ (post-2.0 fixture-ready)

- `[pending]` **R6 — Photo Thumbnail Badge on receipt list cell** [Source: `.cursor/plans/resplit-receipt-photos-joyful.plan.md:60`] [ETA: 1h–2h] — S effort. Improves scannability. Wires to the same `Receipt.receiptImageData` source as the detail hero. Already shipped: row-level stored-scan thumbnail in `UnifiedReceiptRow.swift` (PR #496 + Phase 4 stored-scan thumbnail per Decision Log 2026-04-26). Confirm whether this row is already absorbed into shipped Phase 4 — if YES, flip to `[completed]` with PR #496 squash citation; if NO, ship the badge variant.

- `[pending]` **R7 — Multi-Photo Support (multi-angle uploads)** [Source: `.cursor/plans/resplit-receipt-photos-joyful.plan.md:61`] [ETA: 4h–8h] — Future camera flow change. Requires camera UI redesign + storage model update. Open Question for Leo (joyful plan §Open Q1) on whether single receipts are ever photographed from multiple angles.

- `[pending]` **R8 — Share with Photo (attach photo to expense share)** [Source: `.cursor/plans/resplit-receipt-photos-joyful.plan.md:62`] [ETA: 2h–4h] — Adds photo attachment to the share/expense flow. Touches both share UI and the message/email payload. Visual proof on the share-sheet output.

- `[pending]` **R9 — Photo Attachment Metadata (capture timestamp + location)** [Source: `.cursor/plans/resplit-receipt-photos-joyful.plan.md:63`] [ETA: 1h–2h] — Surface metadata on the photo display. Plumb through existing `PHAsset` metadata (Phase 2b read-only fetcher already does this — see joyful plan Phase 2b shipped 2026-04-26). Likely a small UI slice.

- `[pending]` **R10 — Phase 1.5 pinch-zoom hardening** [Source: `.cursor/plans/resplit-receipt-photos-joyful.plan.md:54` (zoom gesture in Phase 1 ship-gate)] [ETA: 1h] — Confirm pinch-zoom in receipt-detail hero is jank-free on iPhone 14 + doesn't interfere with scroll. Snapshot test + manual sim verification.

- `[pending]` **R11 — Multi-photo carousel surface (when multiple matches exist)** [Source: `.cursor/plans/investigations/asc-c407-receipt-photo-hero.md:49`] [ETA: 4h–8h] — Production multi-photo carousel for state #1 of the joyful-plan state matrix (≥1 ML/Photos match). Currently the candidate-fetcher proof + scorer ships only metadata; this row builds the production carousel UI. Gates on R14 (Photos album population gate) clearing.

- `[pending]` **R12 — Photo sharing / attachment flow (production)** [Source: `.cursor/plans/investigations/asc-c407-receipt-photo-hero.md:48`] [ETA: 2h–4h] — Same surface family as R8. May absorb R8 — TBD when activation hits, depending on which lands first.

### Category 5 — OCR-moat post-launch enhancements

- `[pending]` **R13 — Apple Intelligence / VisionKit prebuilt receipt extractor research** [Source: `.cursor/plans/investigations/asc-akig-ocr-key-value-extraction.md:217` (Phase 3 — Prebuilt receipt API evaluation) + reporter ASC ID 656 comment referencing "Microsoft" extractor] [ETA: 8h–16h research + writeup; no production code in this row] — eng-design research task. Compare Apple Intelligence / VisionKit prebuilt receipt extractors vs Microsoft Azure Form Recognizer vs current pipeline on accuracy, latency, cost, offline capability. Output = decision doc landing in `.cursor/plans/investigations/asc-akig-ocr-key-value-extraction.md` Phase 3 section. NOT a migration row — that's R13.x post-decision.

- `[pending]` **R14 — Photos album population gate (entitlement + privacy plan)** [Source: `.cursor/plans/resplit-receipt-photos-joyful.plan.md:113-117` Phase 2b–2d] [ETA: 4h–8h doc + auth flow + entitlement plist + Sentry monitoring] — Phase 2b/2c/2d shipped as proof-only Dev Gallery surfaces (no entitlements, no privacy copy edits, no production UI wiring). This row is the production gate: write the privacy plan, request `NSPhotoLibraryUsageDescription` plist entry, plumb auth into production hero, add Sentry tracking on auth-denial paths. Blocking on this clears: R11 carousel, future R6 photo-fetcher integration into the detail hero. ASK-LEO-MANDATORY on the privacy copy.

- `[pending]` **R15 — OCR-moat P3 — v4-aware Reconciler (absorbs asc-akig Phase 2)** [Source: `~/Development/vidux/projects/ocr-moat/PLAN.md:55,65` — P3 absorbs `asc-akig` Phase 2; P3 is currently `[pending]` and gated behind 2.0 ship per ocr-moat PLAN line 13] [ETA: 6h+ — already estimated in ocr-moat] — Replaces v3-only `ReceiptItemsFixer` with v4-aware `Reconciler`. UI warning chip on receipt detail when `severity ≥ .warn`. Visual proof BEFORE/AFTER. **Note:** this row IS the ocr-moat P3 row; it is mirrored here so 2.0.1 cron can see it as a 2.0.1 deliverable instead of treating ocr-moat as a separate convergence tree. Single source of truth = `~/Development/vidux/projects/ocr-moat/tasks/P3-reconciliation-engine/PLAN.md`. This row flips when ocr-moat P3 ships; do NOT double-claim.

### Category 6 — Visual proof BACKFILL (esoteric-repro debt from 2.0)

- `[pending]` **R16 — Visual proof BACKFILL: T1/T2/T3/T4/T5/T6/T7 esoteric-repro carve-outs** [Source: `~/Development/vidux/projects/resplit-2-0-weekend-push/PLAN.md:182-198` — 7/7 fixes shipped with esoteric-repro carve-outs because no sim fixture existed; PRs #547, #548, #549, #550, #551, #552, #553] [ETA: 1h–2h per fix × 7 = 8h–16h total, but parallelizable — likely 3 PRs of 3 fixes each] — The 2.0 weekend push relaxed visual proof on 7/7 PRs because of fixture gaps. PRs #554/555/557 (T-cron-1) shipped 6/6 baseline-locked sim fixtures (`screenshot-trip-settlement`, `screenshot-amount-editor-matrix`, `screenshot-live-add-people`, `screenshot-receipt-detail`, `screenshot-folder-detail`, `screenshot-receipt-summary`). Now that fixtures exist: backfill BEFORE/AFTER screenshots for each of the 7 fixes. Land as a single PR: "docs(visual-proof): backfill BEFORE/AFTER for T1-T7 weekend-push fixes" — does NOT touch source code. **MT-1 carve-out justification:** this PR ships visual artifacts that are themselves the closeout proof for prior code shipped without proof; without the artifacts, the next regression on any of these 7 surfaces has to re-derive what the BEFORE state was. The PR IS the durability mechanism for the 2.0 fixes.

  Per-fix breakdown:
  - T1 AAFuZnay (PR #547) — receipt scan hero image height
  - T2 ANgvTW (PR #548) — settlement pill overlap
  - T3 AO4j25 (PR #549) — settlement-sheet hero gradient corner radius
  - T4 AJiYtO9n (PR #550) — FolderDetail right-column number font sizing
  - T5 ACHQtix2 (PR #551) — review-sheet tap dismiss + scroll handoff
  - T6 AD-xnx (PR #553) — ZigzagDivider sweep
  - T7 ABHO_hCd (PR #552) — tip row revert-to-scanned affordance

## Progress

(empty — plan opened 2026-05-07, dormant until activation gate clears)

## Decision Log

- **[DIRECTION] 2026-05-07** — **2.0.1 plan opened.** Cron deferred Tier-2.3 work for ~9 cycles citing *"Tier-2.3 2.0.1 punch-list: project does not exist yet"*. The plan's existence IS the unblock signal — once it exists, cron Tier-2.3 can claim a `[pending]` row (subject to the §Activation Gate above). 16 rows discovered across 6 categories. All `[pending]`. Activation gate has 3 clauses (fastlane ship + F&F quiet 48h + no open ASC bug). Lane-lead `claude-opus-4-7-rios` dispatched this subagent for plan-creation; PR opens on the vidux repo not resplit-ios per dispatch contract (vidux plan-creation tasks live on the vidux repo).

- **[DIRECTION] 2026-05-07** — **Plan-creation PR is NOT MT-1-violating bookkeeping.** Per `/vidux` Principle 5: bookkeeping-only PRs are banned BUT plan creation that itself unblocks dependent agents is the code-equivalent change for the fleet. Cron's Tier-2.3 fall-through has been a no-op for 9 cycles because this file did not exist. The PR opens cron's drain path. Justification compatible with /vidux-leo + repo CLAUDE.md §MT-1.

- **[DIRECTION] 2026-05-07** — **Single-source-of-truth on R15 (OCR-moat P3).** Mirrored P3 here so 2.0.1 cron sees it in scope, but the canonical sub-plan stays at `~/Development/vidux/projects/ocr-moat/tasks/P3-reconciliation-engine/PLAN.md`. Agents who claim this row claim it via the ocr-moat sub-plan; do NOT open a parallel sub-plan tree under `projects/resplit-2-0-1/tasks/`. R15's status here mirrors the ocr-moat P3 status; flip on confirmed P3 squash.

- **[DIRECTION] 2026-05-07** — **R5 net-new pump must stay silent until activation.** Per Leo verbatim 2026-05-01 (see weekend-push PLAN.md:238). Agents who feel the urge to pitch a net-new idea append a sub-row R5.a bullet on this PLAN, then say nothing in chat. The chat-silence rule is doctrinal — pitching net-new ideas before 2.0 ships clean is the failure mode this row exists to prevent.

- **[DIRECTION] 2026-05-07** — **R16 visual-proof backfill PR justified under MT-1 carve-out.** The fixture gap that forced the 2.0 weekend push into 7/7 esoteric-repro carve-outs is closed by PRs #554/555/557. Backfilling visual proof now produces the durability mechanism that prevents a 22nd-EditAmountPopoverField-style regression on each of the 7 fixed surfaces. Without the BEFORE/AFTER pair, the next agent who hits a related bug has to re-derive what the buggy state looked like — that's the MT-1-carve-out-eligible artifact.
