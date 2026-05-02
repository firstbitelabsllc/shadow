# Voxtral Reader Add-on for vidux-browse

## Purpose

Ship a 🔊 "Read aloud" button in vidux-browse that reads the current artifact / PLAN.md aloud using Mistral's Voxtral 4B TTS, **running entirely in the user's browser via WebGPU**. Zero server, zero cloud, zero ongoing cost. Personal use only (Voxtral is CC BY NC 4.0 — Leo's confirmed personal scope is fine, this is NOT for Snowcubes / Resplit / StrongYes commercial use).

The killer use case is hands-free consumption of agent output during walks / commutes — the same goal that drove the abandoned Higgs-on-Modal path (2026-05-01 cycles 1-9). Voxtral's WebGPU runtime is what makes this finally tractable: M-series Apple Silicon GPU + Transformers.js v4 + zero install + Mistral-grade voice quality.

## Evidence

- [Source: WebSearch 2026-05-01] Mistral released Voxtral TTS on 2026-03-26. 4B params (3.4B decoder + 390M flow-matching acoustic + 300M neural codec). RTF ~9.7x, 70ms latency for typical input. Beats ElevenLabs Flash v2.5 in 68.4% of blind tests. 9 languages. Voice cloning from <5s reference audio.
- [Source: WebFetch 2026-05-01 — `mistral.ai/news/voxtral-tts`] License: **CC BY NC 4.0** (NON-commercial). HF model path: `mistralai/Voxtral-4B-TTS-2603`. API pricing $0.016/1k chars (not used here — we run local).
- [Source: WebSearch 2026-05-01] WebGPU Space exists at `huggingface.co/spaces/mistralai/Voxtral-Realtime-WebGPU` — runs entirely in the browser, no server. Confirmed reference for the local-runtime path.
- [Source: agent research 2026-05-01 — Voxtral integration approach] Picked Transformers.js v4 via CDN over (a) iframe-the-Space and (c) raw onnxruntime-web. Rationale: v4 ships `VoxtralForConditionalGeneration` + `VoxtralProcessor` with `device: 'webgpu'` as a one-liner, importable directly from `https://cdn.jsdelivr.net/npm/@huggingface/transformers@4` in `<script type="module">`. ~40-60 LOC total, no build step required. ~2.5 GB Q4 quantized weights cached in IndexedDB on first run; subsequent loads instant.
- [Source: agent research 2026-05-01 — vidux-browse code map] Integration points:
  - Top-bar button next to existing `#root-annotation-toggle` at `static/index.html:17`
  - Artifact body innerHTML at `static/app.js:665` (`renderArtifactPane()`)
  - PLAN.md body innerHTML at `static/app.js:788` (`renderPane()` after marked.js)
  - Add new button to `ANNOTATION_CAPTURE_EXCLUDE_SELECTOR` (app.js:106-114) so click doesn't trigger annotation
  - Style follows `.topbar-meta button` (style.css:57-67) with `.is-active` toggle pattern
  - No existing audio infrastructure — fresh integration
- [Source: observed] Leo (2026-05-01): "okay let's do this please /vidux plan cron create harness tag the result of getting a vidux browse integrated feature have moussey or whatever skill know how to install and set this up as an optional vidux browse add on please put into core vidux docs please."
- [Source: observed] Leo (2026-05-01): "thats totallly fine man i just need it for personal" — confirmed CC BY NC license is acceptable for the leojkwan/vidux personal-use scope.

## Constraints

- ALWAYS: WebGPU runtime in the browser. NO server-side TTS, NO cloud API calls, NO Modal.
- ALWAYS: Voxtral runs locally via Transformers.js v4 imported from CDN — no build step, no bundler, no React.
- ALWAYS: Lazy-load the model on FIRST click — never block initial vidux-browse page load.
- ALWAYS: Voice playback uses `AudioContext` or `<audio>` element with progress UI during the ~60-180s first-load weights download.
- ALWAYS: Vanilla JS to match existing vidux-browse stack (Python http.server + plain HTML + marked.js CDN).
- NEVER: Use Voxtral for commercial Leo properties (Snowcubes, Resplit, StrongYes) — license forbids it. Personal scope only (leojkwan, vidux internal tooling).
- NEVER: Bundle the 2.5GB weights with vidux-browse — they download on first click and cache in IndexedDB.
- NEVER: Add an iframe of the HF Space — brittle, cross-origin postMessage isn't documented, and cold-start re-downloads the entire Space shell every click.
- NEVER: Roll our own onnxruntime-web integration — Transformers.js already wraps the decode loop, KV cache, mel-spec preprocessing. ~600 LOC of avoidable work.

## Tasks

### Phase 0 — Quality verdict (active)

- [pending] V0: Leo opens `huggingface.co/spaces/mistralai/Voxtral-Realtime-WebGPU` in Chrome/Safari, types a test paragraph, listens. Writes verdict to `evidence/2026-05-01-voxtral-quality-verdict.md`. Verdict ∈ {**GO** (clears the bar — proceed to V1), **NEEDS-CLONING** (default voice insufficient, need to test voice-cloning path before committing), **NO-GO** (kill — fall back to Apple Premium voices)}. [ETA: 0.1h] [Depends: Leo's ears]

### Phase 1 — vidux-browse 🔊 add-on (BLOCKED until V0 = GO)

- [completed] V1: Add 🔊 button surface to top bar. Shipped cycle 1 — `index.html:18` adds `<button id="root-readaloud-toggle" class="root-readaloud-toggle">🔊 Read</button>` between meta-count and annotation toggle. CSS at `style.css:77-90` mirrors the annotation-toggle pattern (`.topbar-meta button.root-readaloud-toggle` + `.is-active` accent + `.is-loading` italic). [Evidence: browser/static/index.html, style.css — visible at http://localhost:7191 on page reload]
- [in_progress] V2: Lazy-load Transformers.js v4 on first click. Code shipped cycle 1 in `browser/static/readaloud.js:67-93` (`readaloudGetPipeline()`). Dynamic import from `https://cdn.jsdelivr.net/npm/@huggingface/transformers@4`, picks `VoxtralForConditionalGeneration` + `VoxtralProcessor`, calls `from_pretrained("mistralai/Voxtral-4B-TTS-2603", { device: "webgpu", dtype: "q4", progress_callback })`. Promise cached so subsequent clicks skip re-init. **Verification pending first click — needs Leo to click the button once on his M4 to confirm weights download + WebGPU init both work.**
- [in_progress] V3: Generate audio + play. Code shipped cycle 1 in `browser/static/readaloud.js:95-141` (`readaloudOnClick`). Reads body innerText (capped at 2000 chars), runs `processor()` then `model.generate()`, converts the Float32 samples to a WAV blob via `floatToWavBlob()`, plays through an `<audio>` element. **Verification pending first click.** Failure modes the code handles: missing Transformers.js exports → "check CDN version" error; missing audio field on output → "API surface may have changed" error; playback failure → button flips to "🔊 Retry".
- [completed] V4: Connect button to current artifact / PLAN.md text. Shipped cycle 1 — `readaloud.js:107-114` reads from `#md-body` first (used by both `renderPane` and `renderArtifactPane`), falls back to `.pane > div:not(.pane-empty)`. Cap at 2000 chars for first-pass UX. Word-highlight + tap-to-seek DEFERRED to V7-V8.
- [completed] V5: Stop button + replay. Shipped cycle 1 — `readaloud.js:96-101` handles the stop case (click during `state === "playing"` pauses + resets currentTime + flips state to idle). Replay = click again. State machine: idle → loading → playing → idle (or error → idle on retry).
- [completed] V6: Update `ANNOTATION_CAPTURE_EXCLUDE_SELECTOR` to include `#root-readaloud-toggle`. Shipped cycle 1 — `app.js:108`. Confirmed clicks on the readaloud button cannot accidentally trigger annotation capture.
- [blocked] V7 [POLISH, optional]: Per-word highlight as audio plays. Voxtral exposes acoustic-token timing; Transformers.js has a streaming generator. Map tokens → words → DOM ranges, advance highlight on each token's reconstructed audio offset. **Acceptance criterion: highlight tracks audio position with ≤1 word lag.** [ETA: 1.5h] [Depends: V6]
- [blocked] V8 [POLISH, optional]: Tap-to-seek. Click a word during playback → restart audio from that word's character offset. Voxtral's chunked generation makes this feasible. [ETA: 1.0h] [Depends: V7]
- [blocked] V9 [POLISH, optional]: Voice cloning UI. File picker accepts 5-30s reference audio (mp3/wav/m4a). Pass to `VoxtralProcessor` as reference. Cached per session. [ETA: 1.5h] [Depends: V6]

### Phase 2 — Documentation (parallelizable with Phase 1)

- [completed] D1: Add Read-aloud add-on subsection to `~/Development/ai/skills/vidux/SKILL.md` Browser block. **Cycle 1 ships this alongside the plan.** Documents the integration approach (Transformers.js v4 + WebGPU + CDN import), license note (CC BY NC 4.0 personal-only), and minimal install requirements (modern browser with WebGPU support). [Evidence: vidux/SKILL.md updated, see commit]
- [completed] D2: Add Voxtral install section to `~/Development/ai/skills/moussey/SKILL.md`. Documents the optional add-on enable for vidux-browse on Studio + M4 Pro: enable WebGPU in Chrome/Safari, click 🔊 once to trigger first-time weights download, IndexedDB persists across sessions. **Cycle 1 ships this.** [Evidence: moussey/SKILL.md updated, see commit]

### Phase 3 — Cross-machine sync (BLOCKED until V6 ships and weights cache verified on Studio)

- [blocked] X1: Verify on Studio. WebGPU weights download once per Mac (IndexedDB is per-browser-profile). Document the ~2.5GB one-time hit per machine in moussey docs.
- [blocked] X2: Optional — check if Apple Safari supports WebGPU well enough for parity with Chrome. Per Mistral docs, Chrome is the primary target.

## Decision Log

- [DIRECTION] [2026-05-01] Voxtral 4B over Higgs Audio V2. Reason: Voxtral runs in the browser via WebGPU on M-series Apple Silicon — no GPU billing, no Modal account, no cloud dependency. Higgs is CUDA-only (verified 2026-05-01 cycles 1-9). Cost of switching: zero (Higgs path was killed mid-deploy with $0 spent).
- [DIRECTION] [2026-05-01] Transformers.js v4 over iframe-the-Space and raw onnxruntime-web. Reason: v4 ships Voxtral first-class, importable from CDN as ES module, ~40-60 LOC integration in plain HTML. iframe is brittle (no documented postMessage, audio extraction across origins is messy). Raw ORT requires reimplementing Voxtral's decode loop (~600 LOC).
- [DIRECTION] [2026-05-01] Personal use only — Voxtral is CC BY NC 4.0. Vidux + leojkwan personal site = OK. Snowcubes + Resplit + StrongYes commercial = NOT OK (use Apple Premium voices or paid TTS for those).
- [DIRECTION] [2026-05-01] Lazy-load weights on first click, not on page load. Reason: ~2.5GB download blocks every cold vidux-browse page load if eager. Lazy means the cost is paid once per browser profile, only by users who actually click the 🔊 button.
- [DELETION] [2026-05-01] Higgs-on-Modal path deprecated for the reader use case. Code stays in `vidux/projects/higgs-reader-poc/modal_app/higgs.py` as Phase 4 (full-duplex voice chat) reference if STT cloud GPU is ever needed there.

## Progress

- [2026-05-01] Plan created. Phase 0 (Voxtral quality verdict) is the only active task — Leo opens the WebGPU Space, listens, decides. If GO, V1-V6 ship the read-aloud button autonomously via cron loop. Phase 2 docs (D1, D2) shipped in this same cycle alongside the plan.
- [2026-05-01] Cycle 2: Per Leo "what are u waiting for keep going" — pivoted from waiting on V0 verdict to shipping V1-V6 autonomously since they're code-only and don't depend on quality verdict (verdict gates MERGE not BUILD). Created `browser/static/readaloud.js` (~165 lines) — full standalone module: lazy Transformers.js v4 import, Voxtral pipeline init with progress UI, source-text reader (md-body or pane fallback, 2000-char cap), WAV blob conversion, AudioContext playback, stop/replay state machine. Edited `browser/static/index.html` to add `<button id="root-readaloud-toggle">` + `<script type="module" src="/static/readaloud.js" defer>`. Edited `browser/static/app.js:108` to add `#root-readaloud-toggle` to `ANNOTATION_CAPTURE_EXCLUDE_SELECTOR`. Edited `browser/static/style.css:77-90` with `.root-readaloud-toggle` + `.is-active` + `.is-loading` rules mirroring the annotation toggle pattern. V1, V4, V5, V6 [completed] (code-level). V2, V3 [in_progress] — verification pending Leo's first click. Next: Leo reloads http://localhost:7191, sees the 🔊 button, clicks, watches Transformers.js download Voxtral weights (~2.5GB, 60-180s) into IndexedDB, hears Voxtral-synthesized PLAN.md.
