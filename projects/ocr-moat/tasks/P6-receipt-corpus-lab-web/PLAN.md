# P6 — Receipt Corpus Lab (LAN web surface)

> Parent: ../../PLAN.md

**Status:** [in_progress] — MVP completion drive started 2026-05-29 (Leo `/goal` + 20-agent audit `wcu1o3d47`).
**Owner:** the vidux-browse `/receipts/` LAN surface — web sibling of P5 (the iOS dev-app corpus loop).
**Host code:** `~/Development/vidux/browser/receipts/*.py` + `browser/static/receipts.html`, wired in `browser/server.py` (~1109–1383). Served at `http://<mac>.local:7191/receipts/`, exposed via moussey `/receipts`.
**Downstream:** `~/Development/resplit-ios/Tests/Fixtures/Receipts/` (`corpus.jsonl` + `images/` + `azure-v4-responses/`) → `ResplitCore Corpus Tests`.

## Purpose

The "Moussey admin Resplit receipt scanner that stores all images on the LAN." Leo photographs a physical paper receipt → uploads to the lab → it is SHA-256-deduped and stored on the local LAN → tagged / OCR'd (Azure DI v4) → a ground-truth `expected` is captured → exported to the resplit-ios test fixtures → the physical copy is tossed. The payoff: deterministic, replayable **locale-edge-case unit tests on real receipts**, and a path to throw out the paper pile safely.

The plumbing exists and is genuinely simple (stdlib-only, pure functions, append-only JSONL). This sub-plan drives the MVP **all the way complete**: the scan→unit-test loop actually closes, everything is tested, the corpus survives a reboot, and the security/concurrency footguns are closed.

## Evidence

20-agent fan-out `wcu1o3d47` (2026-05-29) ran smoke/chaos/e2e/security/durability tests locally against isolated temp corpora. Findings:

- [Source: simplicity verdict] 792 LOC, 7 stdlib-only files, **7/10 simple** — module split warranted; no structural over-engineering. Slop = comment-cruft + 1 speculative fn (`iter_rows`) + unused `locale` kwarg.
- [Source: test:smoke PASS] upload→list→tag→dedupe all correct (27/27 assertions). [Source: test:e2e-http PASS] full HTTP lifecycle; image landed in LAN `images/`, stored SHA == uploaded SHA.
- [Source: test:chaos] all malformed uploads → clean 4xx, BUT a single corrupt `corpus.jsonl` line → uncaught `ValueError` → HTTP 500 on **all 4 endpoints** (`storage.py:42/58` re-raise; `server.py:1144/1361/1377/1383` have no try/except).
- [Source: test:security + test:chaos] `handle_ocr` (`handler.py:164`) and `toss.py:64` resolve `corpus.parent / image_path` with **no containment check** — crafted `image_path` (`../../etc/passwd`) escapes the jail (proven: read /etc/passwd; arbitrary `unlink()` in toss). Not reachable via public upload today (`image_path` is machine-generated `images/<id>.<ext>`), but one hand-edited / bulk_ingest / round-trip row away. Write-gate (loopback + JSON CT + same-origin via `_require_json_write`) verified firing on all 3 write routes.
- [Source: test:durability FAIL] `corpus.jsonl` + `images/` are **local-only, untracked AND ungitignored** (`git ls-files` shows only the 7 `.py`). `git clean -fd` / disk-clean / fresh-Mac wipes everything; since `toss.py` deletes the paper, the LAN copy is the ONLY copy → **data-fatal**. Concurrency race proven: shared `corpus.jsonl.tmp` (`storage.py:100`) → 1/5 distinct concurrent `replace_row` survived, 3 `FileNotFoundError` crashes.
- [Source: map:export + ios-parity + synth] **The scan→unit-test loop does not close.** `export.py:84-86` copies only the JSONL line — NOT image bytes, NOT the Azure response. `handle_ocr` stores Azure JSON in `annotations.azure_response` but the iOS runner reads `azure-v4-responses/<id>.json` (`CorpusTestSupport.swift:36-39`). `image_path` is vidux-relative (`images/<id>.png`), README requires repo-relative dated (`Tests/Fixtures/Receipts/images/<id>-<yyyyMMdd>.jpg`). Every exported row lands unrunnable.
- [Source: ios-parity + synth] `make_row` hardcodes `expected: null` (`storage.py:129`); **no code path ever sets `expected`**. `handle_tag` patches annotations only. Every fixture hits the iOS nil-expected skip guard (`CorpusReplayTests.swift:114`) → the corpus test is structurally green but asserts on ZERO receipts. `expected.provenance` is REQUIRED (omitting → `keyNotFound` reds the whole corpus); `provenance.scannedAt` MUST be an ISO-8601 **string**; `extras.kind` ∈ 9 `ScannedExtraKind` rawValues.
- [Source: synth + design:test-harness] **Zero Python tests** on the package. Repo uses stdlib `unittest`, explicit module list in `package.json` `test:py` (no auto-discovery — new modules must be appended), flat `tests/` dir; isolate via reassigning `handler.DEFAULT_CORPUS_PATH`/`DEFAULT_IMAGES_DIR` module globals (proven pattern).
- [Source: moussey-route FAIL] `:4321/receipts` is a hard **404** — no moussey edge route exists (`next.config.ts` has no `redirects()`/`rewrites()`, no `app/receipts/page.tsx`). Backend `:7191/receipts/` is healthy (200). Fix = mirror `app/vidux/page.tsx` `LanAutoRedirect`.
- [Source: plan-home] The authority store cited in `receipts/__init__.py:3-4` (`resplit-ios/vidux/receipt-math-fortress/T9-receipt-corpus-lab/PLAN.md`) is **fictional** — exists in no plan store. The real adjacent plan is THIS ocr-moat tree (P2 corpus runner + P5 dev-app loop); the downstream README already cites `ocr-moat/tasks/P2-fixture-corpus-runner`. → this P6 is the canonical home; do NOT create a top-level sibling.
- [Source: map:frontend] UI exposes only upload/list/tag — OCR/delete/export/toss have no surface; no way to view the stored image; `known_issues`/`leo_note` not editable from UI.
- [Source: test:locale] schema CAN represent locale cases via the `extras` bag; concrete 12-fixture seed matrix produced. Money is `Double` (no minor-unit) — `Reconciler.matchThreshold=0.01` wrong for JPY/KRW — flagged to reconciler owner, not a P6 schema change.

## Constraints

### ALWAYS
- LAN-only. Writes stay loopback-gated via `_require_json_write` (loopback + JSON CT + same-origin). New routes inherit the same gate.
- stdlib-only, zero pip deps (vidux-browse policy). Keep it dead-simple JSONL — the simplicity is the feature.
- Every code slice ships with a test in the same commit. Tests reassign `handler.DEFAULT_CORPUS_PATH`/`DEFAULT_IMAGES_DIR` to a tempdir — NEVER touch the real corpus.
- New `unittest` modules MUST be appended to `package.json` `test:py` or they never gate.
- PII guard: `private: true` rows have `image_path: null` and no bytes on disk; export/track/snapshot never leak private rows.
- `git add` only P6-owned paths — `browser/server.py` is dirty with another session's coding-handoff work; partial-stage (`git add -p`) only receipts hunks.

### NEVER
- Add a DB / index. `replace_row` whole-file rewrite is correct to ~10K rows (currently ~1).
- Spawn a sibling top-level plan — this surface belongs under ocr-moat (P6).
- Commit another session's dirty `server.py`/`test_browser_server.py` hunks.
- Let `toss.py` delete image bytes for a row that isn't capture-complete (image+azure+expected) without an explicit `--force`.
- Change `ScannedReceipt` Swift schema during the 2.0 freeze (e.g. RTL/minor-unit fields) — carry locale nuance in tags/known_issues.

## Tasks

Status FSM: pending → in_progress → completed. `[blocked]` orthogonal.

- [completed] P6.0: 20-agent audit + this plan [Evidence: workflow wcu1o3d47, 20/20 lanes; this PLAN.md] [2026-05-29]
- [completed] P6.1: Python test suite — `tests/test_receipts_storage.py` + `tests/test_receipts_handler.py` wired into `package.json` `test:py`. [Evidence: 34→64 receipts tests green; commit 8b92a88]
- [completed] P6.2: Corrupt-line resilience — `storage.CorpusError` + `@_corpus_safe` decorator → clean `(500, {error})` on all 4 handlers. [Evidence: test_handler corrupt-500 test; commit 783a1c0]
- [completed] P6.3: Path-traversal jail — `storage.safe_image_abs(parent, images_dir, path)` fails closed; used by `handle_ocr`, `handle_delete`, `handle_image`, `toss`. [Evidence: SafeImageAbsTests + jail-400 + toss escaped-skip tests; 783a1c0/b752673]
- [completed] P6.4: Concurrency safety — `fcntl.flock` + unique `.<pid>.<uuid>.tmp` around append/replace/delete. [Evidence: 5-thread concurrent-replace-all-survive test; commit 783a1c0]
- [completed] P6.5: Close the export seam — `export.export_corpus()` copies image (dated, repo-relative), writes `azure-v4-responses/<id>.json`, strips azure from corpus row, validates `expected`, reports stub/grounded counts. [Evidence: test_receipts_export round-trip green; commit 043aea6]
- [completed] P6.6: `expected` promotion — `handler.handle_set_expected` + `contract.validate_expected` (provenance/scannedAt-ISO8601/9-kinds) + `POST /<id>/expected` route + `promote.py` CLI. [Evidence: SetExpectedTests + HTTP 200/400 proof + loop test; 043aea6/f6470ab/8764c1d]
- [completed] P6.7: `toss.py` safety — `RECEIPT_CORPUS_PATH`, capture-completeness guard (`held_uncaptured` unless `--force`), images jail. [Evidence: 6 toss tests incl. escaped-path-never-unlinked; commit b752673]
- [completed] P6.8: Durability — `.gitignore` shields `corpus.jsonl` + `images/*` from `git clean -fd`; `.gitkeep` tracked; durable home = exported resplit-ios fixture. [Evidence: git check-ignore verified; commits a68d349/c51d4ee]
- [completed] P6.9: Delete/undo — `storage.delete_row` + `handler.handle_delete` (unlinks non-private image) + `POST /<id>/delete` route. [Evidence: DeleteTests + HTTP delete→count-0 proof; 043aea6/8764c1d]
- [in_progress] P6.10: UI wiring — routes DONE (`GET /<id>/image` jailed, `POST /<id>/expected`, `POST /<id>/delete`, all loopback-gated; verified over HTTP). REMAINING: `receipts.html` buttons (image `<img>`, Run OCR, expected editor, known_issues/leo_note, delete, drag-drop). [Evidence: handle_image 7c24ae8; routes 8764c1d] **P2**
- [completed] P6.11: moussey `/receipts` edge route — `app/receipts/page.tsx` + `receipts` service; `:4321/receipts` was 404, now serves redirect → `:7191/receipts/` (verified live, parity with `/vidux`). [Evidence: moussey commit 05c012a; build + curl proof]
- [pending] P6.12: Locale fixture matrix — capability PROVEN (loop test seeds a de-DE comma-decimal fixture → runnable export). REMAINING (Leo-gated): acquire ≥8 real receipt images (Photos album / folder → `bulk_ingest`), OCR (needs Azure key), promote `expected`, export. Matrix documented in Decision Log. [Evidence: test:locale 12-fixture seed-list; loop proof] **P1**
- [completed] P6.13: Anti-slop — stripped fake `T9.x`/Leo-verbatim/YAGNI comments; repointed `__init__.py` authority to this plan; deleted `iter_rows`; moved `import os`. [Evidence: commit a68d349]
- [completed] P6.14: Minor hardening — `ocr` Content-Type png-vs-jpeg; `bulk_ingest` HEIC warning. [Evidence: commit a68d349]

**Headline: 12/15 done (+1 in_progress).** All P0 + P1 safety/loop work shipped & tested. Remaining: P6.10 UI buttons (cosmetic — routes live), P6.12 real-image seeding (Leo-gated: needs photos + Azure key).

## Decision Log

- [DIRECTION] 2026-05-29 — Plan home is `ocr-moat/tasks/P6-receipt-corpus-lab-web/` (sub-plan under the ocr-moat parent), NOT a new top-level project. Reason: the web lab produces the SAME `corpus.jsonl` schema as P2 and is the web sibling of P5's dev-app loop; the downstream README already cites ocr-moat. Per /vidux "never create a sibling if a plan covers the surface." Fixes the fictional `receipt-math-fortress/T9` citation the code points at.
- [DIRECTION] 2026-05-29 — MVP-complete bar = the scan→store→OCR→promote-`expected`→export-runnable-fixture→toss loop closes end-to-end AND is covered by a green local test suite (smoke/chaos/unit + export round-trip + toss safety) AND the corpus survives reboot (tracked/snapshotted) AND the path-traversal + concurrency footguns are closed. iOS `tuist test "ResplitCore Corpus Tests"` execution with ≥1 real ground-truthed locale fixture is the final acceptance gate.
- [DIRECTION] 2026-05-29 — Keep it stdlib-JSONL simple (verdict 7/10). Fixes are missing pieces, not bloat. No DB, no async OCR rework, no schema expansion for RTL/minor-units (carry in tags). Strip AI comment-cruft on the first pass per CLAUDE.md.
- [DIRECTION] 2026-05-29 — `expected` validation lives Python-side mirroring the Swift decode contract (provenance required, scannedAt ISO-8601 string, 9 `ScannedExtraKind`) so a malformed `expected` is rejected at the lab/export boundary and never reds the whole iOS corpus.
- [DIRECTION] 2026-05-30 — `server.py` routes (`/image`, `/expected`, `/delete`) were added by path-scoped-stashing an unrelated session's uncommitted `server.py` coding-handoff work, committing only my routes, then `stash pop` to restore theirs intact. Reason: never sweep another lane's uncommitted work (per /pilot-leo cross-lane contamination). Verified: my routes committed at 8764c1d, their 144-line diff fully restored, server.py parses.
- [REFERENCE] 2026-05-30 — Locale fixture matrix (from fan-out test:locale lane), the P6.12 acquisition target: (1) JPY no-decimal, (2) KRW grouping, (3) de-DE comma-decimal, (4) fr-FR service-compris, (5) SF multi-mandate, (6) US auto-gratuity, (7) Thai script, (8) Arabic RTL, (9) discount/credit negative, (10) thermal low-confidence, (11) explicit-zero-tax, (12) Swiss apostrophe-grouping. Min viable ≥8: #1,#3,#5,#6,#9,#10,#11 + existing Biedronka(PLN). Each starts `expected=null` (image-only) until a paired `azure-v4-responses/<id>.json` is captured, then `promote.py --from-json`. Highest-value: no-decimal (#1) + comma-decimal (#3) pin Double float-drift; SF multi-mandate (#5) pins the home-turf `extras.kind` taxonomy.

## Progress

- [2026-05-29] Created from 20-agent audit `wcu1o3d47`. Code is live but the MVP is not complete: zero tests, broken export seam, no `expected` promotion, data-fatal durability gap, latent path-traversal, corrupt-line 500, moussey edge 404. Seeded P6.1–P6.14, prioritized P0={tests, export seam, expected promotion, durability}.
- [2026-05-30] MVP loop CLOSED + hardened. Shipped P6.1–P6.9 + P6.11 + P6.13 + P6.14 (12 tasks) + P6.10 routes. 65 receipts tests green (storage/handler/export/toss/loop), wired into `npm run test:py` (full suite 238+ green). End-to-end loop proof passes: ingest→OCR(mock)→promote→export→toss produces a runnable iOS fixture (image+azure+non-null expected land correctly). Security: corrupt-line→500, image jail, loopback+origin gates verified over HTTP. Durability: corpus shielded from `git clean -fd`. moussey `/receipts` 404→live. Commits 216fede→8764c1d (vidux), 05c012a (moussey). Remaining: P6.10 `receipts.html` buttons (routes already live), P6.12 real-image seeding (Leo-gated: needs receipt photos + Azure key — capability already proven by the loop test). Next: wire the UI buttons.
