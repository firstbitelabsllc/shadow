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
- [pending] P6.1: Python test suite — `tests/test_receipts_storage.py` + `tests/test_receipts_handler.py` (smoke happy-path, chaos malformed-input, schema-parity, dedupe, PII guard); wire both into `package.json` `test:py`. [Evidence: design:test-harness; smoke/chaos lanes] [ETA: 2h] **P0**
- [pending] P6.2: Corrupt-line resilience — handler functions catch `storage` ValueError and return a clean `(500, {error})` with the line-number message instead of an unhandled traceback. Test: corrupt line → 500 JSON, not crash. [Evidence: test:chaos gap-1] [ETA: 0.5h] **P1**
- [pending] P6.3: Path-traversal jail — add `storage.resolve_image_path(corpus, image_path)` that fails closed when the resolved path escapes the images dir; call from `handle_ocr` (`handler.py:164`) and `toss.py:64`. Test: `../../etc/passwd` rejected. [Evidence: test:security gap-1/2] [ETA: 0.5h] **P1**
- [pending] P6.4: Concurrency safety — unique per-write tmp (`.<pid>.<uuid>.tmp`) + `fcntl.flock` (or module `threading.Lock`) around append/replace read-modify-write. Test: N concurrent distinct `replace_row` all survive. [Evidence: test:durability gap-2] [ETA: 1h] **P1**
- [pending] P6.5: Close the export seam — `export.py` copies image bytes (skip `private`) to `Tests/Fixtures/Receipts/images/<id>-<yyyyMMdd>.jpg`, rewrites `image_path` repo-relative, writes `annotations.azure_response` → `azure-v4-responses/<id>.json`, reports stub vs ground-truthed counts, skip+warn on missing image. Test: export round-trip into temp repo dir lands image+azure+rewritten path. [Evidence: map:export gaps; synth P0] [ETA: 1.5h] **P0**
- [pending] P6.6: `expected` ground-truth promotion — `handler.handle_set_expected(id, payload)` validates ScannedReceipt shape (required `provenance`, `scannedAt` ISO-8601 string, `extras.kind` ∈ 9 kinds) + `storage.replace_row`; `POST /api/receipts/<id>/expected` route (loopback-gated); `receipts/promote.py` CLI. Test: valid expected persists; missing provenance / bad scannedAt / bad kind → 400. [Evidence: ios-parity gap-1/2; synth P0] [ETA: 1.5h] **P0**
- [pending] P6.7: `toss.py` safety — honor `RECEIPT_CORPUS_PATH`, capture-completeness guard (skip un-OCR'd / no-`expected` rows unless `--force`, report `held_uncaptured`), path jail (P6.3 helper), require `--yes` for real deletes. Test: un-OCR'd row held; `--force` overrides. [Evidence: map:toss gaps; security gap-2] [ETA: 1h] **P1**
- [pending] P6.8: Durability — `.gitignore` rules + track `corpus.jsonl` + non-PII `images/*.jpg` in the vidux repo (mirror the resplit-ios committed-fixture pattern); `.gitkeep` the images dir; document the commit cadence. Private rows (no bytes) are safe; add a guard that PII images never get added. [Evidence: test:durability gap-1] [ETA: 0.5h] **P0**
- [pending] P6.9: Delete/undo — `storage.delete_row` (atomic rewrite) + `handler.handle_delete` (unlink non-private image) + `DELETE /api/receipts/<id>` (loopback-gated) + per-card delete button w/ confirm. Test: delete removes row + image. [Evidence: synth P1] [ETA: 1h] **P1**
- [pending] P6.10: UI wiring — `GET /api/receipts/<id>/image` (jailed, 404 on private) + `<img>` per card; per-card "Run OCR" button; `expected` editor after OCR; `known_issues`/`leo_note` inputs; "Export to iOS (dry-run)" + "Toss (dry-run)" preview panels; drag-drop + paste capture. [Evidence: map:frontend gaps] [ETA: 2h] **P2**
- [pending] P6.11: moussey `/receipts` edge route — `app/receipts/page.tsx` → `peerPortUrl(..., "7191", "/receipts/")` + `LanAutoRedirect`, mirroring `app/vidux/page.tsx`. Verify `:4321/receipts` → 307 → `:7191/receipts/`. [Evidence: moussey-route gap-1] [ETA: 0.5h] **P1**
- [pending] P6.12: Locale fixture matrix — seed ≥8 (de-DE comma-decimal, JPY no-decimal, SF multi-mandate, service-charge-vs-tip, discount/credit, low-confidence thermal, explicit-zero-tax, Polish-thermal) with tags + (where representable) hand-authored `expected`; prove one runnable round-trip into the repo fixture. [Evidence: test:locale seed-list] [ETA: 2h] **P1**
- [pending] P6.13: Anti-slop — strip fake `math fortress T9.x` plan-IDs + Leo-verbatim + YAGNI comments across `__init__.py`/`toss.py`/`export.py`/`bulk_ingest.py`/`receipts.html`; repoint `__init__.py` authority to THIS P6 plan; delete `iter_rows` (fold into `find_by_id`); move `import os` to top; resolve the unused `locale` kwarg. [Evidence: verdict:simplicity gaps] [ETA: 0.5h] **P2**
- [pending] P6.14: Minor hardening — `ocr.analyze_receipt` Content-Type from stored ext (png vs jpeg); `bulk_ingest` warns on skipped HEIC (`sips` hint). [Evidence: map:bulk gap-1; synth P3] [ETA: 0.5h] **P3**

**Headline: 1/15 done.** P0 = {P6.1, P6.5, P6.6, P6.8}. Loop closes when P6.5 + P6.6 land with a green round-trip test.

## Decision Log

- [DIRECTION] 2026-05-29 — Plan home is `ocr-moat/tasks/P6-receipt-corpus-lab-web/` (sub-plan under the ocr-moat parent), NOT a new top-level project. Reason: the web lab produces the SAME `corpus.jsonl` schema as P2 and is the web sibling of P5's dev-app loop; the downstream README already cites ocr-moat. Per /vidux "never create a sibling if a plan covers the surface." Fixes the fictional `receipt-math-fortress/T9` citation the code points at.
- [DIRECTION] 2026-05-29 — MVP-complete bar = the scan→store→OCR→promote-`expected`→export-runnable-fixture→toss loop closes end-to-end AND is covered by a green local test suite (smoke/chaos/unit + export round-trip + toss safety) AND the corpus survives reboot (tracked/snapshotted) AND the path-traversal + concurrency footguns are closed. iOS `tuist test "ResplitCore Corpus Tests"` execution with ≥1 real ground-truthed locale fixture is the final acceptance gate.
- [DIRECTION] 2026-05-29 — Keep it stdlib-JSONL simple (verdict 7/10). Fixes are missing pieces, not bloat. No DB, no async OCR rework, no schema expansion for RTL/minor-units (carry in tags). Strip AI comment-cruft on the first pass per CLAUDE.md.
- [DIRECTION] 2026-05-29 — `expected` validation lives Python-side mirroring the Swift decode contract (provenance required, scannedAt ISO-8601 string, 9 `ScannedExtraKind`) so a malformed `expected` is rejected at the lab/export boundary and never reds the whole iOS corpus.

## Progress

- [2026-05-29] Created from 20-agent audit `wcu1o3d47`. Code is live but the MVP is not complete: zero tests, broken export seam, no `expected` promotion, data-fatal durability gap, latent path-traversal, corrupt-line 500, moussey edge 404. Seeded P6.1–P6.14, prioritized P0={tests, export seam, expected promotion, durability}. Next: P6.1 test suite (TDD the fixes), then P6.2–P6.4 safety, P6.5/P6.6 to close the loop.
