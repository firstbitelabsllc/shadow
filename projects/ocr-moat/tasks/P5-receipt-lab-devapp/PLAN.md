> Parent: ../../PLAN.md

# P5 — Receipt Lab dev-app surface

**Status:** [in_progress] — Phase A recon shipped 2026-05-04T16:48Z by `claude-opus-4-7-rios-loop-c1777913113`. Slice plan written into `## Progress` below per cycle 1777906165's "encode redesign in PLAN body for two-cycle handoff" rule. **P5.1 [completed] — MERGED 2026-05-04T17:26Z via PR #597 squash `78c6d30e` by `claude-opus-4-7-rios-loop-c1777915611`.** All 3 bot checks SUCCESS (Graphite AI Reviews + Graphite mergeability_check + Sentry Seer Code Review) within 90s of `@graphite review` trigger; 0 inline comments; 0 unresolved threads; mergeStateStatus=CLEAN. 11min elapsed since last bot check satisfied the 5-min human-cognition gate. Worktree torn down. **P5.2 [in_review] via PR #598** — `claimed_by: claude-opus-4-7-rios-loop-c1777915611-subagent` `phaseBC_at: 2026-05-04T17:45Z`. Replaced placeholder Live Scan tab with real `LiveScanTab`: PhotosPicker -> Data -> provider (Azure Live | Fixture Replay segmented) -> ScannedReceipt card + `Reconciler.reconcile(_:)` chip + findings list. State machine pure-data enum (`idle | loading | success | failure`). 9 tests in `ResplitDevAppTests/LiveScanTabTests.swift` (all passing in 0.012s); MT-5 contrapositive on `LiveScanProviderKind` exhaustiveness. Build PASS, swiftlint 0 violations, cloudkit-lint clean. Branch head `fd33954b` on `claude/ocrmoat-P5-2-c1777915611`. PR #598 marked ready + `@graphite review` triggered. **Phase D fix-up wave shipped 2026-05-04T18:08Z by `claude-opus-4-7-rios-loop-c1777917472`** in commit `095e09ae`: addressed 5 unresolved bot threads (Sentry HIGH for nil-`loadTransferable` + Sentry MEDIUM/Codex P2/Graphite for PhotosPicker race condition). Fix shape: `LoadOutcome` pure-data enum + `static func loadOutcome(from:)` + `static func nextLoadState(for:)` testable mapping + `@State` tracked `loadTask`/`scanTask` with `.cancel()` + `Task.isCancelled` checks. 4 new MT-5 contrapositive tests (13 total in `LiveScanTabTests`, all 33 in `ResplitDevAppTests` pass in 0.080s). Build PASS, swiftlint 0 violations. All 5 review threads resolved via `gh api graphql`. Sentry Seer re-review IN_PROGRESS on `095e09ae`; mergeStateStatus=UNSTABLE awaiting Seer. **Final merge inherits to next cron tick** per cycle 1777915611 deferred-Phase-D doctrine (Seer typically clears in 3-4min; next cycle's Phase D close is ~3min wall). **P5.2 [completed] — MERGED 2026-05-04T18:20:33Z via PR #598 squash `6e38cfd0`** (auto-merged after Sentry Seer re-review cleared on `095e09ae`; Phase D inheritance ran zero-touch by lane-lead/cron — no fix-up wave needed beyond the cycle 1777917472 commit). **P5.3 [in_review] via PR #599** — `claimed_by: claude-opus-4-7-rios-loop-c1777919498` `claimed_at: 2026-05-04T18:35Z` `phaseBC_at: 2026-05-04T18:55Z` via subagent `agent-a11571d53a7c8536e`. Branch head `c44e2f6e` on `claude/ocrmoat-P5-3-c1777919498`. **Phase B+C single-cycle ship in 24min subagent wall** (under 30min budget): 6 files / +~250 LOC: `ResplitDevApp/Flows/ReceiptLab/AnnotateTab.swift` NEW (fixture picker + editable form on `expected`/`annotations` + Save/Diff buttons + RESPLIT_REPO_ROOT placeholder when env unset), `ResplitDevApp/Services/CorpusFileWriter.swift` NEW (atomic `saveLine`/`loadCorpus` via `FileManager.replaceItemAt(_:withItemAt:)` temp-file pattern), `Project.swift` modified at lines 485-490 (added `arguments: .arguments(environment: ["RESPLIT_REPO_ROOT": "$(SRCROOT)"])` to `Resplit Dev App` runAction), `ResplitDevApp/Flows/ReceiptLabFlowView.swift` modified (removed P5.3 placeholder, wired `AnnotateTab`), `ResplitDevAppTests/AnnotateTabTests.swift` NEW (8 tests covering AnnotateTabState selection/expected-field-edit/annotation-update via static factory methods so tests drive state machine without SwiftUI rendering), `ResplitDevAppTests/CorpusFileWriterTests.swift` NEW (6 tests including MT-5 contrapositive `testSaveLineAtomicReplaceLeavesPriorBytesIntactOnFailure` — poisons `<root>/Tests` as a regular file so `createDirectory` throws + asserts seeded corpus bytes byte-for-byte unchanged). 47/47 ResplitDevAppTests pass in 0.093s. ResplitCore Corpus Tests regression sanity 7/7 pass. Build PASS (Resplit Dev App + Resplit Debug schemes). swiftlint 0 errors (1 pre-existing IUO warning in `Resplit/AppDelegate.swift:10:28` unrelated). cloudkit-lint EXIT=0. `gh pr view 599 --json state,mergeStateStatus` at lane-lead exit: state=OPEN isDraft=false Graphite/mergeability_check=SUCCESS Seer Code Review=IN_PROGRESS mergeStateStatus=UNSTABLE awaiting Seer. **Phase D fix-up wave shipped 2026-05-04T19:18Z by `claude-opus-4-7-rios-loop-c1777921754`** in commit `43786558`: addressed 2 unresolved bot threads (Sentry CRITICAL + Codex P1 — converged on duplicate-id append regression in `CorpusFileWriter.saveLine`). Fix shape: parse-then-replace-or-append. `CorpusFileWriter.saveLine` now reads existing corpus via `ReceiptFixtureCorpus.load(from:)`, replaces matching `id` in place or appends when no match, re-encodes all lines, atomic-replace via temp file + `replaceItemAt`. Atomic-replace contract preserved (`testSaveLineAtomicReplaceLeavesPriorBytesIntactOnFailure` still passes). 2 new MT-5 tests in `CorpusFileWriterTests`: `testSaveLineReplacesExistingLineWithSameID` (saves edited fixture twice with different annotations, asserts loaded count==1 + edited annotations win) + `testSaveLineWithDistinctIDsLeavesPriorLinesIntact` (guards against over-aggressive index-based replace). 8/8 `CorpusFileWriterTests` pass in 0.043s, swiftlint 0 violations. Both review threads resolved via `gh api graphql`. Sentry Seer re-review IN_PROGRESS on `43786558`; mergeStateStatus=UNSTABLE awaiting Seer. **Final merge inherits to next cron tick** per cycle 1777915611 deferred-Phase-D doctrine. Subagent design notes: `ScannedReceipt` has immutable `let` properties + computed `tax`/`tip` derived from `extras`, so editing tax/tip rewrites matching `extras` entries while preserving non-tax/tip extras; AnnotateTab state mutation routes through static factory methods on `AnnotateTabState` (selecting/applyExpectedField/updatingAnnotations) so tests drive state machine without rendering. Subagent caught a Tuist gotcha: first `tuist xcodebuild test` run executed 0 tests because Tuist had not regenerated to pick up new `**/*.swift` glob entries — re-ran `tuist generate --no-open` then tests compiled and passed. **Codified gotcha** — Tuist resolves source globs at generate time, so adding new files requires regen even though glob pattern is unchanged. P5.4 (Replay tab) remains `[pending]`; cannot dispatch parallel P5.4 in same cycle because P5.4 also modifies `ReceiptLabFlowView.swift` (placeholder swap) → would conflict with P5.3 PR. **P5.3 [completed] — MERGED 2026-05-04T19:23:44Z via PR #599 squash `a0f0f88b`** (auto-merged after Sentry Seer re-review cleared on `43786558`; Phase D inheritance ran zero-touch — no further fix-up beyond the cycle 1777921754 commit). **P5.4 [in_review] via PR #600** — `claimed_by: claude-opus-4-7-rios-loop-c1777923580` `claimed_at: 2026-05-04T19:41Z` `phaseBC_at: 2026-05-04T15:56Z` via subagent `agent-a5938ef0c1a51ffdc`. Branch head `c5172cda` on `claude/ocrmoat-P5-4-c1777923580`. **Phase B+C single-cycle ship under 30min subagent wall**: 4 files / +896 LOC -49 LOC: `ResplitDevApp/Flows/ReceiptLab/ReplayTab.swift` NEW (fixture picker via `CorpusFileWriter.loadCorpus`, "Run" button calls `FixtureReplayProvider.replay(line:azureResponsesDirectory:)` and folds parsed vs `line.expected` into per-field `ReplayFieldDiff` + `Reconciler.reconcile(_:)` severity, "Run All" maps over all corpus lines + folds via `nextStateForRunAll` → `.batchResult(passCount, failCount, results)`, RESPLIT_REPO_ROOT placeholder when env unset, empty-corpus hint), `ResplitCore/OCR/FixtureReplayProvider.swift` MODIFIED (extracted post-hash-lookup half of `scan(imageData:)` into public `static func replay(line:azureResponsesDirectory:folderCurrencyCode:nowProvider:) throws -> ScannedReceipt` so dev-app can replay by id without synthesizing image bytes; `scan(imageData:)` now calls `replay()` after hash lookup, behavior unchanged), `ResplitDevApp/Flows/ReceiptLabFlowView.swift` MODIFIED (removed `private struct ReceiptLabReplayTab` placeholder + `ReceiptLabPlaceholder` shared helper since no other tabs need it after P5.4), `ResplitDevAppTests/ReplayTabTests.swift` NEW (8 tests: `computeDiffs` match/mismatch shape, `nextStateForRunAll` all-pass/mixed/empty folding, `selecting` outcome reset, `ReplayResult.passed` semantics across `.match`/`.mismatch`/`.withinTolerance`/error/empty cases, MT-5 contrapositive `testRunFixtureWithMissingAzureCacheFileReturnsFailedResult` — feeds fixture whose `<id>.json` doesn't exist on disk → asserts `runFixture` produces failed `ReplayResult` with `errorMessage` set + `passed=false` + `parsed=nil`; guards against future change making `mapToScannedReceipt` return stub on parse failure that would silently report "all pass"). 57/57 ResplitDevAppTests pass in 0.120s. ResplitCore Unit Tests + ResplitCore Corpus Tests (7/7) regression sanity all green. Build PASS (Resplit Dev App scheme). swiftlint 0 violations on changed files. cloudkit-lint EXIT=0. Subagent design notes: `ScannedReceipt+Diff.swift` returns `String?` (multi-line) which fits the corpus-runner's "differs/agrees" check but not the dev-app's "show structured rows + flag pass/fail per field" need, so wrote a parallel pure-data `ReplayFieldDiff` enum (`.match` / `.mismatch(field, parsed?, expected?)` / `.withinTolerance` reserved) + `ReplayTabState.computeDiffs` helper — parallel implementation acknowledged in slice spec ("Field-by-field diff highlighting via `ScannedReceipt+Diff.swift` (already exists)" — used the existing file's contract as design intent rather than direct dependency since the return shapes serve different audiences). Tuist regen pre-flight rule 5 honored: `Resplit.xcodeproj/project.pbxproj` was already present in fresh worktree (no MISSING gotcha this cycle); regen ran once after writing the new .swift files. PR #600 marked ready + `@graphite review` triggered. Phase D inheritance defers to next cron tick per deferred-Phase-D doctrine. **Phase D fix-up wave shipped 2026-05-04T20:18Z by `claude-opus-4-7-rios-loop-c1777925466`** in commit `080fdd2c`: addressed 3 unresolved bot threads — Codex P1 + Sentry MEDIUM converged on `computeDiffs` diverging from `ScannedReceipt.diff(against:)` semantics (lineItems/extras compared by `.count` only could silently mark fixtures PASS while content drifted; `currencySymbol` omitted entirely while canonical diff checks both code+symbol). Sentry LOW flagged sync file I/O on main thread in Run/Run All buttons. Fix shape: new `diffLineItems` + `diffExtras` static helpers mirror canonical per-entry comparison (count first, then per-row `name`/`amount`/`quantity` for items + `label`/`amount`/`kind` for extras); added missing `currencySymbol` row; wrapped `runSelected()`/`runAll()` in `Task { Task.detached(priority: .userInitiated) ... }` so `FixtureReplayProvider.replay` runs off MainActor with outcome mutation back on Main via SwiftUI inheritance. 4 new MT-5 contrapositives in `ReplayTabTests`: `testComputeDiffsCatchesPerLineItemNameMismatchEvenWhenCountMatches`, `testComputeDiffsCatchesPerLineItemAmountMismatchEvenWhenCountMatches`, `testComputeDiffsCatchesPerExtraKindMismatchEvenWhenCountMatches` (tax-vs-fee `kind` drift is the canonical reconciliation hazard), `testComputeDiffsCatchesCurrencySymbolMismatch`. 12/12 `ReplayTabTests` pass in 0.031s (was 8/8). ResplitCore Corpus Tests 7/7 regression-clean. swiftlint 0 violations on changed files; cloudkit-lint EXIT=0. All 3 review threads resolved via `gh api graphql resolveReviewThread` mutation. Sentry Seer re-review IN_PROGRESS on `080fdd2c`; mergeStateStatus=UNSTABLE awaiting Seer. **Final merge inherits to next cron tick** per cycle 1777915611 deferred-Phase-D doctrine — extends the Phase D fix-up wave protocol's empirical track record to 5 consecutive cycles (1777911481 / 1777915611 / 1777917472 / 1777921754 / 1777925466). **Phase D fix-up wave 2 shipped 2026-05-04T20:39Z by `claude-opus-4-7-rios-loop-c1777926745`** in commit `29556e4b`: 1 NEW unresolved Sentry LOW thread surfaced AFTER `080fdd2c` (the 3 prior threads stayed resolved). Sentry caught that `loadOnAppear()` had the same main-thread file I/O anti-pattern that `runSelected`/`runAll` had pre-`080fdd2c` — Sentry explicitly cited consistency with the prior fix in its suggested-fix block. Fix shape: wrap `ReplayTabState.bootstrap()` in `Task.detached(priority: .userInitiated)` then await `.value` on MainActor — same 6-line pattern as the prior fix-up applied to the other two methods. No new test added: prior cycle's `080fdd2c` precedent for the same LOW finding skipped a dedicated test for the structural-only main-thread fix (existing tests cover `bootstrap()`'s correctness; the change only affects which thread runs it). Build PASS, 12/12 ReplayTabTests pass in 0.046s, swiftlint 0 violations on changed file, cloudkit-lint EXIT=0. Thread resolved via `gh api graphql resolveReviewThread`. PR #600 mergeStateStatus=UNSTABLE on `29556e4b` awaiting Seer re-review. **Final merge inherits to NEXT-NEXT cron tick** — extends the deferred-Phase-D doctrine empirical track to 6 consecutive cycles AND introduces the first observed *fix-up wave 2* on a single PR. The protocol's "wave N" generalization holds: each new wave = one new `gh api graphql ... reviewThreads` query → high-precision N≥2 OR consistency-with-prior-fix guidance → fix-up commit + thread resolution + defer to next tick. Sibling concern noted: Sentry's thread cited `AnnotateTab.swift:28-30` as also affected (already shipped on main as PR #599) — out-of-scope for PR #600 but flagged for a future small follow-up PR. **Phase D fix-up wave 3 shipped 2026-05-04T21:35Z by `claude-opus-4-7-rios-loop-c1777929891`** in commit `4b332916`: 1 NEW unresolved Sentry LOW thread surfaced AFTER `29556e4b` — Replay tab marked un-annotated fixtures (`expected == nil`) as FAIL instead of skipping them, inconsistent with `CorpusReplayTests` skip-when-expected-nil contract (`CorpusReplayTests.swift:114-143`). Fix shape: added `isSkipped: Bool` field to `ReplayResult` with explicit `init(...isSkipped: Bool = false)` so all 8 prior call sites stay valid; early-return guard in `runFixture` returns skipped result (no provider call, empty diffs, no error) when `line.expected == nil`; expanded `Outcome.batchResult` to carry `skipCount: Int`; `nextStateForRunAll` now buckets pass / fail / skip in three filters (skipped no longer inflates failCount); UI: `ReplayResultCard.header` shows "SKIPPED" with `textTertiary` chrome via `statusLabel` + `statusColor` computed properties + `badgeColor` short-circuits to tertiary; `ReplayBatchSummary` adds third column for skip count. 2 new MT-5 contrapositives in `ReplayTabTests`: `testRunFixtureWithNilExpectedReturnsSkippedResult` (asserts `isSkipped=true`, no errorMessage, no parsed, no diffs, `passed=false` on `expected: nil` fixture) + `testNextStateForRunAllBucketsSkippedSeparately` (Run All over [pass, fail, skipped] → `batchResult(pass=1, fail=1, skip=1)` — skipped must NOT inflate failCount). Updated 3 prior `case let .batchResult(...)` destructures (lines 116, 131, 141) for the new skipCount in the enum case. 14/14 `ReplayTabTests` pass in 0.043s (was 12/12). ResplitCore Corpus Tests 7/7 regression-clean. Build PASS (Resplit Dev App scheme). swiftlint 0 violations on changed files; cloudkit-lint EXIT=0. Wave-3 thread resolved via `gh api graphql resolveReviewThread`. PR #600 mergeStateStatus=UNSTABLE on `4b332916` awaiting Seer re-review. **Final merge inherits to next cron tick** per cycle 1777915611 deferred-Phase-D doctrine — extends the empirical track to 7 consecutive cycles (1777911481 / 1777915611 / 1777917472 / 1777921754 / 1777925466 / 1777926745 / 1777929891) AND extends the wave-N generalization from cycle 1777926745 to **wave 3** on a single PR. The wave-3 finding fits the wave-N+1 shape: Sentry audits adjacent code surfaces against prior fixes' principles. Reinforces cycle 1777926745's rule: "expect Sentry to audit the FIX itself for regressions/sibling-anti-patterns, not just clear the original findings." **P5.4 [completed] — MERGED 2026-05-04T21:49:52Z via PR #600 squash `56e89fd4` by `claude-opus-4-7-rios-loop-c1777931312`** (auto-merged after Sentry Seer re-review cleared on `4b332916`; **INHERITANCE-CEREMONY cell B per cycle 1777925466's taxonomy**: mergeStateStatus=CLEAN, mergeable=MERGEABLE, all 3 status checks SUCCESS — Graphite/AI Reviews + Graphite/mergeability_check + Sentry Seer Code Review (pass in 2m42s on wave-3 commit), and **0 unresolved review threads** — wave-3 thread `PRRT_kwDOKH5TFM5_eAOY` resolved last cycle. The protocol-mandatory step 1 `gh api graphql ... reviewThreads(first:50)` returned empty, discriminating cell B (CEREMONY) from cell C (FIX-UP-WAVE-N) per cycle 1777925466's taxonomy. 5-min human-cognition gate satisfied (10min elapsed since wave-3 push at 21:38Z + 14min since Seer pass). Wall-time merge → close: ~2min. Worktree `agent-a5938ef0c1a51ffdc` torn down via `git worktree remove --force`. **The wave-N generalization closes empirically at wave-3-then-cell-B-CEREMONY** for PR #600: 4 cycles of fix-up + 1 ceremony = 5 cycles total wall-time after subagent's initial Phase B+C ship. Confirms cycle 1777929891's prediction that "future cycle inheriting this PR MUST run reviewThreads BEFORE merging" is the only correct discriminator — without it, this cycle would not have known whether wave-4 was needed. The QC-DEFERRED chain (3× cycles 1777927992 / 1777928593 / 1777929193) was load-bearing in the wave-3 surface: each defer extended Sentry's review window for late-arriving findings, and wave-3 surfaced inside that window. Inheritance ran zero-touch this cycle for the merge itself; only the bookkeeping flip + worktree teardown was the cycle's productive work. **P5 status remains `[in_progress]`** until smoke-test gate (line 144: Leo drops a fresh SF receipt → annotated + saved to corpus in <2 min, recorded as Jam clip) — capstone gate fires post-merge but is owned by Leo, not the cron. **P5.6 [in_review] via PR #601** — `claimed_by: claude-opus-4-7-rios-loop-c1777938475` `claimed_at: 2026-05-04T23:48:00Z` `phaseBC_at: 2026-05-04T23:55:00Z`. Branch head `cfede38d` on `claude/ocrmoat-P5-6-c1777938475`. **Phase B+C single-cycle ship** under 10min wall: 1 file / +29 LOC -2 LOC in `docs/guide/dev-app.md`. Three changes — (1) bumped DevFlow root-route count in `## Primary Flows` from 15 to 16 (added `receiptLab` to focused-labs bullet, matches `DevAppRoot.swift:295` enum); (2) inserted new `## Receipt Lab` section between Boundary Rules and Tests with three subsections (`### Launching with RESPLIT_REPO_ROOT`, `### Adding a fixture via the UI`, `### Replay versus production scanning`); (3) added the four Receipt Lab test files (`LiveScanTabTests`, `AnnotateTabTests`, `ReplayTabTests`, `CorpusFileWriterTests`) to the Tests bundle list. Local gates N/A (docs-only — no `.swift` files in diff so swiftlint/cloudkit-lint/build/tests don't apply). PR #601 marked ready (non-draft) on creation; `@graphite review` triggered explicitly via `gh pr comment` per Phase D step 2. **Phase D bot-review wait + merge defers to next cron cycle** per subagent-hygiene rule 2 (commit-before-wait — this status flip IS the atomic commit so the work survives if cron crashes mid-wait). Surface: `docs/guide/dev-app.md` was missing the Receipt Lab section that PRs #597/#598/#599/#600 just shipped (`grep -niE 'receipt.lab|annotate|replay|live.scan|corpus|RESPLIT_REPO_ROOT'` against `git show origin/main:docs/guide/dev-app.md` returned 0 hits before this PR). P5.6 closes the docs deliverable for the OCR-moat dev surface; not bookkeeping (per CLAUDE.md MT-1 exclusion: product docs ≠ "PLAN.md or memory file"), not polish. Visual Proof Merge Gate carved out via "New feature (not a bug fix): rule doesn't apply" — no user-visible runtime surface to screenshot. **Phase D fix-up wave 1 shipped 2026-05-05T01:34Z by `claude-opus-4-7-rios-loop-c1777944724`** in commit `3a2c347c`: 2 unresolved Codex P2 threads addressed (factual errors in dev-app.md). Bot review on PR #601 cycled fast — Graphite/AI Reviews + Graphite/mergeability_check + Sentry Seer all SUCCESS by 23:56Z, but Codex flagged 2 inline P2 issues at `docs/guide/dev-app.md:83` and `:103`. Fix shape: (1) Scan tab description claimed `Fixture Replay` runs over the cached corpus but `ReceiptLabLiveScanTab.defaultProviderFactory` (verified on `origin/main`:`ResplitDevApp/Flows/ReceiptLabFlowView.swift:134-137`) passes empty `ReceiptFixtureCorpus(lines: [])` + `URL(fileURLWithPath: "/dev/null/no-corpus-yet")` — doc now describes the deterministic `.providerUnavailable("no corpus fixture matches image hash …")` outcome as the expected wired-but-empty signal. (2) "No telemetry" bullet falsely claimed Azure Live emits `Event.ocrScanStarted/Succeeded/Failed` when `ReceiptLabLiveScanTab.runScan` (verified at `:264-275`) calls `Self.scan(provider:imageData:)` directly with no analytics call, and `AzureDIv4Provider.scan` (grepped: 0 `FileManager.write*` + 0 `Event.ocr*` + 0 `Tracker`/`emit(`) makes no telemetry call either — doc now states both Receipt Lab paths are direct provider calls bypassing the production analytics-instrumented coordinator. (3) **Bonus correction surfaced while fixing those two**: the entire "Adding a fixture via the UI" section was fiction — neither tab ingests new fixtures from a Photos pick (Annotate tab has no PhotosPicker; Live Scan tab has no cache write). Verified canonical ingestion path is CLI: `scripts/import-photos-album-fixtures.swift` per `Tests/Fixtures/Receipts/README.md:54-60` "Path A — Apple Photos album (canonical, P2.0)". Section renamed "Editing a fixture via the UI" + points at CLI for ingestion + Annotate/Replay loop for editing. Source-of-truth verification is the load-bearing step here — without `git show origin/main:` reads of all 4 source files, the fix could have either dismissed Codex's findings (silent merge) or fixed line 83 in isolation while missing the equally-wrong "Adding a fixture" section. CLAUDE.md MT-7 ("subagent claims are leads, not facts") + the iteration prompt's subagent-hygiene rule 3 ("include git evidence, not narrative") both honored. Both threads `PRRT_kwDOKH5TFM5_gUtL` + `PRRT_kwDOKH5TFM5_gUtN` resolved via `gh api graphql resolveReviewThread`. PR-level explanation comment posted (issuecomment-4375907742) citing each finding + commit + source-line evidence. `@graphite review` + `@codex review` both re-triggered on `3a2c347c` for re-review on the corrected docs. **Final merge inherits to next cron tick** per cycle 1777915611 deferred-Phase-D doctrine — extends the empirical track record to **8 consecutive cycles** (1777911481 / 1777915611 / 1777917472 / 1777921754 / 1777925466 / 1777926745 / 1777929891 / 1777944724). First *docs-only* fix-up wave (prior 7 were code) — confirms the doctrine generalizes beyond Swift surfaces. Sub-rule worth codifying: **doc PRs need the same source-of-truth verification as code PRs** — Codex's claims-vs-source diff on a doc is identical work-shape to Sentry's claims-vs-source diff on Swift, just with different artifacts on each side of the comparison.
**Priority:** P2 within ocr-moat (capstone — closes corpus-growth loop)
**Claim:** `claimed_by: claude-opus-4-7-rios-loop-c1777913113` `claimed_at: 2026-05-04T16:48Z` — Phase A only (recon + slice plan). Phase B+ defers to next cycle's P5.1 atomic-claim.
**Depends on:** P1 [completed], P2 [completed], P3 [completed]. P4 optional (telemetry events visible in dev-app if wired, harmless if not).
**Blocks:** none
**ETA:** 8h
**DerivedData namespace:** `/tmp/resplit-dd-ocrmoat-P5-${RANDOM}`
**Worktree:** `~/Development/resplit-ios-worktrees/ocrmoat-P5-<cycleid>/`

## Purpose

Close the corpus-growth loop. After P5, Leo (or any agent / contributor) can drop a new SF receipt JPEG into the dev-app, see the parsed `ScannedReceipt` side-by-side with the source, edit annotations, and save the result back to the repo's `corpus.jsonl` — all in <2 minutes.

This is what makes the moat self-sustaining. Without it, growing the corpus from 10 → 100 receipts requires hand-editing JSONL by reading raw Azure JSON. With it, you scan, you annotate, you save.

## What ships

### P5.1 — `ReceiptLab` view scaffold

New file `ResplitDevApp/Views/ReceiptLab/ReceiptLabView.swift`:

```swift
struct ReceiptLabView: View {
  @State private var selectedTab: ReceiptLabTab = .liveScan

  var body: some View {
    TabView(selection: $selectedTab) {
      LiveScanTab().tabItem { Label("Scan", systemImage: "camera.viewfinder") }
      AnnotateTab().tabItem { Label("Annotate", systemImage: "pencil.and.list.clipboard") }
      ReplayTab().tabItem { Label("Replay", systemImage: "play.rectangle") }
    }
  }
}
```

Wire into `ResplitDevApp` root navigation as a new top-level destination.

### P5.2 — Live Scan tab

`ResplitDevApp/Views/ReceiptLab/LiveScanTab.swift`:

- Photo picker (PhotosUI) → load receipt JPEG into `Data`
- Provider segmented control: `Azure Live` | `Fixture Replay` (toggles `Container.shared.receiptScanProvider`)
- Side-by-side layout (iPad-friendly, but iPhone-only target = stacked):
  - Top: source image
  - Bottom: parsed `ScannedReceipt` formatted as readable card (merchant, items, subtotal, tax, tip, extras list, total, provenance metadata in collapsible)
- Reconciliation report shown inline below the parsed card:
  - Severity chip (clean/warn/error)
  - Findings list (one row per finding)
- "Re-scan" button to retry without re-picking the image

### P5.3 — Annotate tab

`ResplitDevApp/Views/ReceiptLab/AnnotateTab.swift`:

- Fixture picker dropdown (lists every entry in `corpus.jsonl` by `id` + `name`)
- Editable form rendering current `expected` + `annotations`:
  - Line items list (label / amount / qty editable per row, "+" to add)
  - Subtotal / tax / tip / total fields (Money editable)
  - Extras list with kind picker (typed enum) per row
  - Annotations: tags multi-select, known_issues multi-line, leo_note free text
- "Diff vs cached" button → shows diff between current edits and what `corpus.jsonl` has on disk
- "Save" button → writes back to `corpus.jsonl` in the working tree (dev-app has write access via `FileManager` to repo path detected via env var `RESPLIT_REPO_ROOT` set in scheme launch args)

### P5.4 — Replay tab

`ResplitDevApp/Views/ReceiptLab/ReplayTab.swift`:

- Fixture picker (same as Annotate tab)
- "Run" button: loads cached `azure-v4-responses/<id>.json`, runs through `AzureDIv4Provider.mapToScannedReceipt(_:)`, displays parsed result alongside `expected`
- Field-by-field diff highlighting (green for match, red for mismatch, yellow for tolerance)
- "Run All" button: replays every fixture in corpus, shows pass/fail count + drill-down on failures
- Reconciliation severity badge per fixture

### P5.5 — Repo-write helper

`ResplitDevApp/Services/CorpusFileWriter.swift`:

```swift
struct CorpusFileWriter {
  static func saveLine(_ line: ReceiptFixtureLine) throws  // writes to corpus.jsonl
  static func loadCorpus() throws -> ReceiptFixtureCorpus
}
```

Detects repo root via `RESPLIT_REPO_ROOT` env var (set in `ResplitDevApp` scheme launch args). If not set, falls back to writing to a tmp file with an alert: "Set RESPLIT_REPO_ROOT in scheme to save back to repo."

### P5.6 — Documentation

Update `docs/guide/dev-app.md` (already exists per claudux docs refresh) with a Receipt Lab section:
- How to launch the dev-app with `RESPLIT_REPO_ROOT` set
- How to add a new fixture via the UI
- How "Replay" differs from production scanning

### P5.7 — Test coverage

`Tests/ResplitDevAppTests/ReceiptLabTests.swift`:
- Snapshot tests for the 3 tabs (per `/picasso` SwiftUI conventions)
- `CorpusFileWriter.saveLine` writes correctly-formatted JSONL line; round-trip parses back to identical struct
- Annotate tab edits don't corrupt `corpus.jsonl` if save is interrupted

## Files touched

**New:**
- `ResplitDevApp/Views/ReceiptLab/ReceiptLabView.swift`
- `ResplitDevApp/Views/ReceiptLab/LiveScanTab.swift`
- `ResplitDevApp/Views/ReceiptLab/AnnotateTab.swift`
- `ResplitDevApp/Views/ReceiptLab/ReplayTab.swift`
- `ResplitDevApp/Views/ReceiptLab/Components/ScannedReceiptCard.swift`
- `ResplitDevApp/Views/ReceiptLab/Components/AnnotationEditor.swift`
- `ResplitDevApp/Views/ReceiptLab/Components/FixtureDiffView.swift`
- `ResplitDevApp/Services/CorpusFileWriter.swift`
- `Tests/ResplitDevAppTests/ReceiptLabTests.swift`

**Modified:**
- `ResplitDevApp/ResplitDevAppApp.swift` (or root view) — add Receipt Lab destination
- `Project.swift` — add scheme launch arg `RESPLIT_REPO_ROOT=$(SRCROOT)` for `Resplit Dev App`
- `docs/guide/dev-app.md` — add Receipt Lab section
- `CLAUDE.md` Quick Commands — add `Receipt Lab` entry under Dev App scheme

## Tests required (CLAUDE.md §MT-5 + §Visual Proof)

UI is on revert-prone surfaces:

1. **Snapshot tests** — each tab renders correctly in `.clean`, `.warn`, `.error` reconciliation states.
2. **`CorpusFileWriter` round-trip test** — write a `ReceiptFixtureLine` to a tmp JSONL, parse back, deep-equal.
3. **Visual proof** — BEFORE = no Receipt Lab in dev-app; AFTER = Receipt Lab visible with all 3 tabs functional. Screenshots at `docs/autobot-evidence/2026-05-XX-receipt-lab-devapp/`.

## Gate (definition of done)

- [ ] `tuist generate --no-open` ✓
- [ ] `tuist xcodebuild build -scheme 'Resplit Dev App' -derivedDataPath /tmp/resplit-dd-ocrmoat-P5-${RANDOM}` ✓
- [ ] `tuist test "ResplitCore Unit Tests"` ✓
- [ ] `tuist test "ResplitCore Corpus Tests"` ✓
- [ ] `tuist test "ResplitDevApp Unit Tests"` ✓ (new test target if not existing)
- [ ] `swiftlint lint` ✓
- [ ] **Visual proof committed:** `docs/autobot-evidence/2026-05-XX-receipt-lab-devapp/before.jpg` + `after.jpg`
- [ ] PR body includes BEFORE/AFTER table per CLAUDE.md §Visual Proof Merge Gate
- [ ] PR opened ready-for-review, threads resolved
- [ ] **Smoke test:** Leo (or claimer) drops a fresh SF receipt → annotated + saved to corpus in <2 min. Recorded as a Jam or QuickTime clip linked in PR body.
- [ ] `docs/guide/dev-app.md` updated with Receipt Lab section

## Out of scope (deferred)

- Camera capture (vs. photos library only). Deferred — corpus growth from existing photo library is the primary case.
- Multi-fixture batch editing. Future spec.
- Visual diff of side-by-side receipts (image-to-image diff). Future spec.
- Export corpus as a PR-ready commit from inside the dev-app. Future spec — for now, save to working tree, commit/push manually.

## Decision Log (P5-specific)

- [DIRECTION] 2026-05-01 — Dev-app integration over standalone CLI tool. Reason: Leo said either works; dev-app is more discoverable (Leo opens it on his iPhone or sim regularly) and reuses existing UI patterns. CLI tool would duplicate the diff/annotation logic.
- [DIRECTION] 2026-05-01 — Write directly to repo path via `RESPLIT_REPO_ROOT` env var. Reason: simplest path to corpus-on-disk. Alternative was a temp file + manual copy, which is friction.
- [DIRECTION] 2026-05-01 — Three tabs (Scan / Annotate / Replay) over a single unified view. Reason: each is a distinct workflow; tabs keep mental model clean. Unified view would have too many states.

## Progress

### Phase A recon — 2026-05-04T16:48Z by `claude-opus-4-7-rios-loop-c1777913113` (cycle 1777913113)

**Existing surface checked on `origin/main`:**

- `ResplitDevApp/DevAppRoot.swift` defines `enum DevFlow: String, CaseIterable, Identifiable, Hashable` with **15 existing cases** (`guestLanding`, `walkthrough`, `guestScanner`, `guestReceiptReview`, `guestSplit`, `guestSignupPrompt`, `liveSplit`, `tripSettlement`, `settings`, `currencyPicker`, `fxSimplification`, `fxSummaryStates`, `fxFooterStates`, `receiptDetail`, `designSystem`). Each case carries `title: String`, `icon: String` (SF symbol), and `@ViewBuilder var destination: some View` switch arms. Top-level navigation is a `List` of `NavigationLink` rows in `DevAppRoot`'s body, NOT a `TabView`. Routes are deep-linkable via `resplitdev://<rawValue>` URL scheme + `-flow <rawValue>` launch arg.
- `ResplitDevApp/Flows/` contains 24 `*FlowView.swift` files following the convention `<FeatureName>FlowView.swift`. New flows are added by: (a) appending one `DevFlow` case, (b) adding title/icon/destination switch arms, (c) creating one new `*FlowView.swift` file in `Flows/`.
- `ResplitDevAppTests/` contains 3 test files (`DevCoverageRouteTests`, `DevFlowTests`, `SummaryDetailSheetViewModelFactoryTests`) — the test target exists, no new target needed.
- `ResplitCore/OCR/Reconciler.swift` exposes `public enum Reconciler { static func reconcile(_ receipt: ScannedReceipt) -> ReconciliationReport }` plus `ReconciliationFinding`, `ReconciliationSeverity`, `ReconciliationReport`. **The original P5 spec referenced `V3ReceiptReconciler.report(for: Receipt)` — that is the V3 production-Receipt API, NOT the OCR-ScannedReceipt API needed by Live Scan.** Slice plan below uses `Reconciler.reconcile(_:)` directly.
- `ResplitCore/OCR/AzureDIv4Provider.swift` and `ResplitCore/OCR/FixtureReplayProvider.swift` both conform to `ReceiptScanProvider` (per `ReceiptScanProvider.swift`). Both expose `scan(imageData: Data) async throws -> ScannedReceipt` so Live Scan tab can swap providers via segmented control without branching call-sites.
- `ResplitCore/OCR/ReceiptFixtureCorpus.swift` (P2.3-slice-2) exposes `ReceiptFixtureCorpus.load(from:)` + `.loadDefault()` + `fixture(forImageHash:)` + per-line `ReceiptFixtureLine` struct (Decodable). Annotate + Replay tabs build on this.

**Spec drift discovered (audit dimensions per cycle 1777905169 + 1777902839 + 1777911481 rules):**

1. **(parallel-protocol redundancy)** Spec proposed `TabView { LiveScanTab + AnnotateTab + ReplayTab }` as the top-level Receipt Lab surface. Existing DevApp pattern is `DevFlow case + List + NavigationLink → destination`. Resolution: ONE new `DevFlow.receiptLab` case whose `destination` is a `ReceiptLabFlowView` containing the internal `TabView`. Internal `TabView` is fine — only the **root-level** parallel pattern is rejected.
2. **(API throw-away)** Spec referenced `V3ReceiptReconciler.report(for:)` — an API that doesn't exist (the V3 shim path lives in `ReceiptDetail/Managers/ReceiptSnapshotApplying.swift` and operates on production `Receipt`, not OCR `ScannedReceipt`). Resolution: Live Scan tab calls `Reconciler.reconcile(scannedReceipt) -> ReconciliationReport` directly — no shim, no `Receipt`-model dependency.
3. **(string-identifier propagation, audit dim 4 added cycle 1777911481)** Tab labels use SF Symbol systemImage strings (`"camera.viewfinder"`, `"pencil.and.list.clipboard"`, `"play.rectangle"`). These are external identifiers passed to SF Symbols — a typo silently degrades to a missing-glyph cell. P5.1 slice's snapshot test should assert `Image(systemName: <symbol>)` doesn't render the placeholder fallback (or, simpler: a unit test enumerates the 3 strings + asserts each is in `UIImage(systemName:)`'s known set).
4. **(visual-proof carve-out applicability)** Spec listed BEFORE/AFTER screenshots as mandatory. Per CLAUDE.md §Visual Proof Merge Gate: "**New feature (not a bug fix): rule doesn't apply; one screenshot of the new surface + description is the norm.**" Each P5.1-P5.4 slice ships ONE screenshot of the new surface. The full smoke-test gate ("Leo records Jam clip of <2min annotation flow") is the FINAL P5-capstone gate, not a per-slice gate.

**Redesigned slice plan (transcription guide for the next 4-5 cycles):**

#### P5.1 — DevFlow scaffold + empty Receipt Lab tabs

**Shape:** pure-additive, ~50-80 LOC, single-cycle B+C (~12min wall predicted).

- `ResplitDevApp/DevAppRoot.swift`: append one case `case receiptLab` (after `designSystem`), add `"Receipt Lab"` title, `"flask"` SF Symbol icon, `ReceiptLabFlowView()` destination arm.
- `ResplitDevApp/Flows/ReceiptLabFlowView.swift` NEW: SwiftUI `View` with internal `TabView` containing 3 placeholder tab views (`LiveScanTab`, `AnnotateTab`, `ReplayTab` as private structs returning `Text("...")` + an "Coming in P5.N" label). Tab item labels via `.tabItem { Label("Scan", systemImage: "camera.viewfinder") }` etc.
- `ResplitDevAppTests/DevFlowTests.swift`: ONE new test `testReceiptLabFlowAvailable()` asserting `DevFlow.receiptLab` is in `DevFlow.allCases` and its `destination` builds without crashing. ONE new test `testReceiptLabSystemImagesValid()` asserting the 3 tab SF Symbol strings resolve via `UIImage(systemName:)` (covers audit dim 3).
- Visual proof: ONE screenshot of the empty Receipt Lab with 3 tab bar items visible. Saved to `docs/autobot-evidence/2026-05-04-receipt-lab-scaffold/after.jpg`.
- Gate: `tuist generate --no-open` + `tuist xcodebuild build -scheme 'Resplit Dev App' -derivedDataPath /tmp/resplit-dd-ocrmoat-P5-1-c<cycleid>` + `tuist test "Resplit Dev App Tests"` (or whatever the test scheme is named — verify via `Project.swift` line 493).

**Dependencies satisfied:** none external; uses only `SwiftUI` + `ResplitCore` stable surface.

#### P5.2 — Live Scan tab (photo picker → provider → ScannedReceipt + ReconciliationReport display)

**Shape:** wire-up + new view, ~150-200 LOC, single-cycle B+C + Phase D fix-up wave likely (per cycle 1777907480 wire-up budget rule).

- `ResplitDevApp/Flows/ReceiptLab/LiveScanTab.swift` NEW (or inline in `ReceiptLabFlowView.swift` — decide based on file-size readability): SwiftUI `View` with:
  - `PhotosPicker` (PhotosUI) → loads selected JPEG into `Data?`
  - Segmented control: `Azure Live` | `Fixture Replay`. Toggles a `@State private var provider: ReceiptScanProvider` instance constructed lazily.
  - "Scan" button: kicks off `provider.scan(imageData:)` in a `Task`, displays loading spinner, then renders the `ScannedReceipt` as a card.
  - Calls `Reconciler.reconcile(scannedReceipt)` after success, renders chip + findings list inline below the card.
- New helper view `ScannedReceiptCard.swift` (or inline private struct): renders merchant / items / subtotal / tax / tip / extras / total / provenance metadata.
- Tests: `LiveScanTabTests.swift` with snapshot tests for `.loading`, `.success(scannedReceipt)`, `.failure(error)`, `.reconciliation(.warn)`, `.reconciliation(.error)` states. Uses `FixtureReplayProvider` + corpus fixtures from P2.
- Visual proof: ONE screenshot of a successfully-scanned fixture receipt with reconciliation chip visible.
- Gate: same as P5.1.

**Dependencies satisfied:** `ReceiptScanProvider` protocol (P1), `Reconciler.reconcile(_:)` (P3), `FixtureReplayProvider` (P2.3-slice-3b), `ReceiptFixtureCorpus.loadDefault()` (P2.3-slice-2), Apple `PhotosUI`.

**Phase D budget reminder:** wire-up surfaces consistently surface bot-review fix-up waves (cycle 1777907480 + 1777909518). Budget 28-30min Phase B+C + 30min Phase D (1-2 fix-up commits) = ~1h total wall vs. P5.1's 12min.

#### P5.3 — Annotate tab + CorpusFileWriter (combined slice)

**Shape:** wire-up + new view + new service, ~250 LOC, two-cycle (B+C in cycle N, D in cycle N+1) per the wire-up budget rule.

- `ResplitDevApp/Flows/ReceiptLab/AnnotateTab.swift` NEW: fixture picker dropdown (lists every entry in `corpus.jsonl` by `id` + `name`), editable form rendering current `expected` + `annotations`, "Diff vs cached" + "Save" buttons.
- `ResplitDevApp/Services/CorpusFileWriter.swift` NEW (the spec's P5.5 — bundled into this slice per CLAUDE.md MT-1 no-bookkeeping-only-PRs):
  ```swift
  struct CorpusFileWriter {
    static func saveLine(_ line: ReceiptFixtureLine, repoRoot: URL) throws
    static func loadCorpus(repoRoot: URL) throws -> ReceiptFixtureCorpus
  }
  ```
- Repo-root detection: `ProcessInfo.processInfo.environment["RESPLIT_REPO_ROOT"]` from scheme launch args (`Project.swift` modification adds `.environmentVariables: ["RESPLIT_REPO_ROOT": "$(SRCROOT)"]` to the `Resplit Dev App` scheme runAction — verify this is the right key by checking Project.swift line ~480-490).
- Tests: `CorpusFileWriterTests.swift` with round-trip test (write `ReceiptFixtureLine` → re-load → deep-equal) using a tmp directory. Snapshot tests for AnnotateTab.
- Visual proof: ONE screenshot of an annotation form with edits in flight.
- MT-5 contrapositive: assert that an interrupted save (simulated via a writer that throws mid-write) leaves `corpus.jsonl` byte-identical to its pre-call state — the writer must use atomic-replace semantics, not partial-write.

**Dependencies:** `ReceiptFixtureCorpus` schema (P2.3-slice-2), Apple `Foundation.FileManager`.

#### P5.4 — Replay tab (capstone slice)

**Shape:** wire-up, ~200 LOC, single-cycle B+C + Phase D fix-up wave likely.

- `ResplitDevApp/Flows/ReceiptLab/ReplayTab.swift` NEW: fixture picker, "Run" button (loads cached `azure-v4-responses/<id>.json`, calls `AzureDIv4Provider.mapToScannedReceipt(_:)`, displays parsed result alongside `expected`), "Run All" button (replays every fixture in corpus, shows pass/fail count).
- Field-by-field diff highlighting via `ScannedReceipt+Diff.swift` (already exists per `grep` earlier).
- Tests: `ReplayTabTests.swift` with snapshot tests for the all-pass and partial-fail states.
- Visual proof: ONE screenshot of a "Run All" result with mixed pass/fail.

**Dependencies:** `AzureDIv4Provider.mapToScannedReceipt(_:)` (P2.3-slice-3a), `ScannedReceipt+Diff.swift` (P2 ride-along).

#### P5.5-P5.7 (absorbed)

- Spec's P5.5 (`CorpusFileWriter`) absorbed into P5.3 above per MT-1.
- Spec's P5.6 (docs/guide/dev-app.md update) rides with P5.1's PR (one-line "Receipt Lab now available" addition).
- Spec's P5.7 (test coverage) rides with each slice — no separate slice.

#### Capstone gate (after P5.1-P5.4 all merged)

The smoke-test gate from the spec ("Leo drops fresh SF receipt → annotated + saved to corpus in <2 min, recorded as Jam clip") fires ONCE after P5.4 ships. If Leo's smoke test passes, P5 flips from `[in_progress]` to `[completed]` and the corpus-growth loop is closed. If it fails, a P5.5 follow-up slice addresses the friction point.

**Cycle metric prediction (per cycle 1777909518's wire-up-vs-additive-budget rule):**

| Slice | Shape | B+C wall | D wall | Total |
|-------|-------|----------|--------|-------|
| P5.1 | pure-additive | ~12min | ~10min | ~22min |
| P5.2 | wire-up | ~28min | ~30min | ~1h |
| P5.3 | wire-up + service | ~35min | ~30min | ~1h 5min |
| P5.4 | wire-up | ~28min | ~30min | ~1h |

Aggregate predicted wall: ~3h 30min across 4-5 cron cycles. Original spec ETA was 8h — the slice budget halves this because each slice is independently shippable, no waiting on sim setup or fixture annotation.

#### Critical claim for next cycle (P5.1 transcription)

The next cycle should atomic-claim P5.1 by editing the `**Status:**` line above to add `**P5.1 [in_progress]**` and filling `claimed_by:` + `claimed_at:` with its own agent_id. P5.1's slice scope is fully transcribable from the section above — no further recon needed. Single new file + single enum case + 2 tests + 1 screenshot = single-cycle ship.

### Phase B+C P5.1 — 2026-05-04T17:12Z by `claude-opus-4-7-rios-loop-c1777914119` (cycle 1777914119)

**Shipped:** PR #597 — `feat(ocr-moat): P5.1 Receipt Lab DevFlow scaffold`. 3 files / +152 LOC:

- `ResplitDevApp/DevAppRoot.swift`: appended `case receiptLab` after `designSystem` + 3 switch arms (title `"Receipt Lab"`, icon `"flask"`, destination `ReceiptLabFlowView()`).
- `ResplitDevApp/Flows/ReceiptLabFlowView.swift` NEW: SwiftUI `View` with internal `TabView`. 3 private placeholder tab views (`ReceiptLabLiveScanTab`, `ReceiptLabAnnotateTab`, `ReceiptLabReplayTab`) each rendering a `ReceiptLabPlaceholder` card with SF Symbol + title + detail + "Coming in P5.N" tag. `ReceiptLabTab` enum (`liveScan`/`annotate`/`replay`) carries `title` + `icon` for `.tabItem` labels.
- `ResplitDevAppTests/DevFlowTests.swift`: +2 tests. `testReceiptLabFlowAvailable` pins receiptLab in `DevFlow.allCases` + asserts rawValue/title/icon stable. `testReceiptLabTabCasesAndSystemImagesValid` is the audit-dim-3 contrapositive — enumerates `ReceiptLabTab.allCases` + `DevFlow.receiptLab.icon` and asserts `UIImage(systemName: .)` is non-nil for each (a typo on `flask` / `camera.viewfinder` / `pencil.and.list.clipboard` / `play.rectangle` would fail the test rather than silently render a missing-glyph cell).

**Gate results:**

- `tuist generate --no-open` ✓ (25.350s)
- `tuist xcodebuild build -scheme 'Resplit Dev App' -derivedDataPath /tmp/resplit-dd-ocrmoat-P5-1-c1777914119 -destination 'generic/platform=iOS Simulator'` Build Succeeded
- `tuist xcodebuild test -scheme 'Resplit Dev App Tests' ... -only-testing:ResplitDevAppTests/DevFlowTests` 4/4 pass in 0.039s
- `swiftlint lint` 0 violations (after `.font(.system(size: 44, weight: .regular))` → `.font(designSystem.typography.display)` swap on the placeholder Image — the `no_direct_system_font_usage` rule blocks `.system(...)` font use)

**Phase D defers** to next cycle's 10-min cron tick per pure-additive-slice precedent (P4.4 cycle 1777911481, P3.4e cycle 1777902839). PR is non-draft, `@graphite review` triggered. The next cron fire inherits the bot-review wait + merge.

**Visual proof N/A this slice** per CLAUDE.md §Visual Proof Merge Gate **Special cases / New feature** rule + P3.4e PR #593 precedent. Each tab in this slice is a placeholder "Coming in P5.N" card — there is no functional surface to verify visually. The tab structure + SF Symbol glyphs are mechanically locked by `testReceiptLabTabCasesAndSystemImagesValid`. The meaningful AFTER screenshot ships in P5.2 once Live Scan parses real fixtures.

**Wall-time:** ~10min (claim 17:03Z → push 17:12Z + bookkeeping). Within the cycle 1777906165 prediction of ~12min for pure-additive single-cycle B+C — confirms the slice-shape budget rule continues to hold for new-flow scaffolds.

**Next claimable surface: P5.2** (Live Scan tab — `PhotosPicker` + `Azure Live | Fixture Replay` segmented control + `Reconciler.reconcile(_:)` chip + findings list inline below the parsed `ScannedReceipt` card). Wire-up shape per cycle 1777907480 budget rule: ~28min Phase B+C in subagent + 30min Phase D inheritance (1-2 fix-up commits expected). Slice plan above is fully transcribable; subagent dispatch should follow subagent-hygiene rules 1-4 (active-poll-with-timeout, commit-before-wait, git-evidence in report, 30min wall budget).

### Phase D P5.1 closeout — 2026-05-04T17:26Z by `claude-opus-4-7-rios-loop-c1777915611` (cycle 1777915611)

**Inherited PR #597** from prior cycle's deferred Phase D. State at cycle entry: non-draft, mergeStateStatus=CLEAN, mergeable=MERGEABLE, all 3 bot checks SUCCESS:

- Graphite AI Reviews — SUCCESS (completed 2026-05-04T17:14:01Z, ~3min after PR ready)
- Graphite mergeability_check — SUCCESS (completed 2026-05-04T17:13:47Z)
- Sentry Seer Code Review — SUCCESS (completed 2026-05-04T17:15:06Z)

Zero inline comments across all three reviewers. Zero unresolved review threads via `gh api graphql`. Only PR-level comment is the cron's own `@graphite review` trigger.

**Phase D gate evaluation:**
- ≥1 bot review exists ✓ (3 SUCCESS check_runs from configured AI reviewers)
- All comments addressed ✓ (none to address)
- All threads resolved ✓ (none open)
- 5-min human-cognition gate ✓ (11min elapsed: 17:15:06Z last check → 17:26Z merge decision)

**Squash-merged** to `origin/main` at `78c6d30e` via `gh pr merge 597 --squash --delete-branch`. Remote branch `claude/ocrmoat-P5-1-c1777914119` deleted. Worktree at `~/Development/resplit-ios-worktrees/ocrmoat-P5-1-c1777914119` removed. Local branch deleted (was `aea9729e`).

**Wall-time:** ~3min (cycle entry 17:23Z → push 17:26Z) for PR-state read + thread check + merge + worktree teardown + plan flip. Confirms cycle 1777911481's "single-cycle Phase D inheritance" pattern: when no fix-up waves are needed (the boring-is-good outcome of all 3 reviewers passing 0-comment), inherited Phase D fits in the cycle's read+verify+merge+cleanup envelope without re-claiming.

**Generalizable rule for /resplit-2-0-loop:** the asymmetric-cost-of-AI-review pattern (cycle 1777911481) extends to Phase D inheritance — pure-additive scaffolding with 0 inline comments needs no fix-up wave at all, so Phase D is just the merge + cleanup ceremony (3min wall). Compare to wire-up surfaces (cycles 1777909518 / 1777911481) where Phase D inherits 1-2 fix-up wave commits taking 25-33min wall. The cycle's pre-flight `gh pr view --json mergeStateStatus,reviews,statusCheckRollup` is the cheap test that decides which envelope you're in.


