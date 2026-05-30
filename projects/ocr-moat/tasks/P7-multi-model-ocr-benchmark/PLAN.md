# P7 — Multi-Model Receipt-Extraction Benchmark

> Parent: ../../PLAN.md

**Status:** [in_progress] — started 2026-05-30 (Leo: "run codex claude opencode qwen inference on them all and figure out the plan"). Builds on P6 (the corpus lab) + P6.15 (azure-vs-claude compare).

## Purpose

Use flagship/general-reasoning models as a **ground-truth oracle** to find where Resplit's shipped **prebuilt Azure Document Intelligence** OCR gets real receipts wrong — then, **in aggregate (later, not per-receipt)**, feed those learnings into improving Resplit's on-device scan + **last-mile reconciliation** logic (`ResplitCore/OCR/*`, `Reconciler`, `OCRSnapshotMapper`).

Leo's vision (2026-05-30): upload a photo → it auto-stores + auto-runs every extractor → compare against prebuilt → over time aggregate the divergences → improve the app's scan/reconcile code. *"eventually we take learnings (in aggregate not now) and develop improvements to the resplit scan local processing logic or the last mile logic."*

## Evidence

- [Source: live] First real receipt `d49d7331c4d0` (MARATHON CAFE, Little Neck): Azure prebuilt → USD, subtotal 49.45, total 53.84, 4 items, extras tax+tip, valid, 5.9s. **Claude TIMED OUT at 180s** on the raw 4032×3024 / 2.4MB photo.
- [Source: live] Root cause of the timeout: the raw photo is 12MP. Downscaling to 1568px long-edge (Claude's optimal vision size) → 310KB. LLM providers MUST resize first; Azure keeps full res.
- [Source: env] CLIs installed: `claude`, `codex`, `opencode`, `ollama`. No `qwen` CLI. ollama models: `gemma3:12b` (vision-capable), `qwen3:8b`/`qwen3-coder:30b` (text), `deepseek-r1:8b`, `gemma4:e4b`. Local vision = gemma3 (or pull `qwen2.5-vl`).
- [Source: P6.15] `receipts/extract.py` already runs azure (mapped) + claude + codex against the SAME `ScannedReceipt` contract; `compare.py --store` writes `annotations.extractions`; moussey UI renders the diff + one-click promote.
- [Source: code-review woafkb2vt] 52 findings; **P0**: fractional `quantity` (produce/weighted) passes the Python gate but reds the iOS corpus (Swift `Int?`). Must fix `contract.py` + `azure_to_scanned` before any export.

## Constraints

### ALWAYS
- LLM providers resize the image to ≤1568px long-edge before inference (speed + cost). Azure gets full res.
- All providers emit the SAME `ScannedReceipt` contract (`receipts/contract.py`) so results are diffable.
- Providers run CONCURRENTLY (thread pool) — cloud CLIs (claude/codex/opencode) parallelize; ollama serializes on the GPU.
- Leo explicitly authorized model spend on upload (overrides the moussey "no spend from always-on server" default for THIS surface) — but it's user-triggered per upload, not a background cron. Log spend visibly.
- Aggregate analysis is the goal, per-receipt is the input. Don't change resplit-ios scan code yet — collect divergences first.

### NEVER
- Auto-run a background cron that spends model usage. Spend is per explicit upload/analyze only.
- Export a fixture that fails the Swift contract (P0 quantity fix gates this).
- Change `ScannedReceipt` Swift schema during the 2.0 freeze.

## Tasks

- [pending] P7.1: Image resize for vision — `receipts/extract.py` downscales to ≤1568px before any LLM call (fixes the Claude 180s timeout). Azure unchanged. [P0 — unblocks claude on real receipts]
- [pending] P7.2: Fix `claude` provider — resized image + `--max-turns`/leaner invocation so a real receipt completes in <30s. [P0]
- [pending] P7.3: `opencode` provider — figure out the non-interactive invocation + structured output, wire into extract.py.
- [pending] P7.4: `codex` provider — resolve the exit-1/answer-file quirk (structured output) so it returns a ScannedReceipt.
- [pending] P7.5: ollama local-vision provider — `gemma3:12b` (and pull `qwen2.5-vl` if useful) via `:11434/api/generate` with the image, structured JSON. Local, free, private.
- [pending] P7.6: Concurrent execution — run all providers in a thread pool in `compare_image`; cloud parallel, ollama serialized.
- [pending] P7.7: Auto-analyze on upload — after upload, the lab kicks the full extractor set + compare automatically (Leo: "claude/codex just take it from there once i upload"). User-triggered spend; visible "analyzing…" state.
- [pending] P7.8: Aggregate-divergence report — a CLI/artifact that scans the corpus's stored `extractions`, computes per-field model-vs-prebuilt divergence, and ranks where Azure prebuilt is weakest (the input to resplit scan improvements).
- [pending] P7.9: Apply P0/P1 code-review fixes (fractional quantity, missing contract type-checks, export-without-azure gate, proxy SSRF) before any export to resplit-ios. [Source: woafkb2vt]

## Decision Log

- [DIRECTION] 2026-05-30 — Models are an ORACLE to improve prebuilt OCR, not a replacement. Resplit ships Azure prebuilt; the LLMs find its blind spots in aggregate. The deliverable is the divergence report → resplit scan/reconcile improvements, not "swap to an LLM."
- [DIRECTION] 2026-05-30 — Resize-before-LLM is mandatory: the 180s claude timeout was a 12MP image, not a model limit. 1568px is the standard.
- [DIRECTION] 2026-05-30 — Leo authorized model spend on upload for this surface (scoped override of moussey no-spend-from-server). Per-upload explicit, never a background cron.

## Progress

- [2026-05-30] Created from Leo's multi-model directive + the first real receipt (Marathon Cafe) where Azure succeeded but claude timed out on the raw 12MP image. Resized to 1568px (/tmp/receipt-d49d.jpg). Discovery: claude/codex/opencode/ollama available; gemma3:12b is the local vision model. Firing a concurrent workflow to figure out each model's invocation + run inference on the real receipt in parallel, then wire the working providers into extract.py.
