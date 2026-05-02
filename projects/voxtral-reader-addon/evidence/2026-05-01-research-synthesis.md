# Research Synthesis — Voxtral Reader Add-on (2026-05-01)

Three parallel research streams ran on cycle 1 to inform the integration plan. Captured here for future cycles to reference without re-running the research.

## Stream 1 — vidux-browse code map (Explore subagent)

Integration points in `~/Development/vidux/browser/`:

| Concern | File:Line |
|---|---|
| Artifact body innerHTML injection | `static/app.js:665` (`renderArtifactPane()`) |
| PLAN.md body innerHTML injection | `static/app.js:788` (`renderPane()` after `marked.parse(md)`) |
| Existing top-bar Annotate button | `static/index.html:17` (`#root-annotation-toggle`) |
| Annotate event listener | `static/app.js:1249-1253` |
| Annotation UI state manager | `static/app.js:864-876` (`updateAnnotationUI()`) |
| `.topbar-meta button` styling | `static/style.css:57-67` |
| `.is-active` toggle pattern | (used throughout — e.g. annotation toggle) |
| Annotation-target exclusion list | `static/app.js:106-114` (`ANNOTATION_CAPTURE_EXCLUDE_SELECTOR`) |
| Annotation anchor selector | `static/app.js:86-105` (`APP_ANCHOR_SELECTOR`) |
| Top-bar sticky positioning | z-index 10, scroll listener at app.js:1286 |

**Existing audio infrastructure: NONE.** No `<audio>`, `HTMLAudioElement`, `AudioContext`, or TTS references. Fresh integration.

**Gotchas:**
- New button MUST be added to `ANNOTATION_CAPTURE_EXCLUDE_SELECTOR` so its clicks don't accidentally trigger annotation capture mode.
- Disabled state should follow `updateAnnotationUI()` pattern — disable when no content loaded.
- Top-bar scroll listener exists for popover positioning; no conflict expected with a stateless button.

## Stream 2 — Voxtral integration approach (general-purpose subagent)

Three candidate approaches evaluated. Picked: **Transformers.js v4 via CDN.**

### Why not (a) iframe the HF Space

- No documented postMessage protocol from `mistralai/Voxtral-Realtime-WebGPU` Space
- Cross-origin audio extraction is messy (no MediaStream handoff, would need to scrape `<audio>` srcs)
- Each "Read aloud" click re-downloads the full Space shell
- One UI rev on Mistral's end breaks the integration
- LOC: ~30, but maintenance is unbounded
- **Reject**

### Why not (c) raw onnxruntime-web

- Voxtral is a multimodal LLM-style TTS — would need to reimplement: VoxtralProcessor tokenization, mel-spectrogram preprocessing, KV-cache management, streaming decoder loop, audio post-processing
- ~600+ LOC
- Only worth it if (b) blocks
- **Reject**

### Why (b) Transformers.js v4 wins

- v4 release (NPM, March 2026) ships `VoxtralForConditionalGeneration` + `VoxtralProcessor` with `device: 'webgpu'` as a one-liner
- **No build step required** — published as ES module, importable directly from `https://cdn.jsdelivr.net/npm/@huggingface/transformers@4` in plain `<script type="module">`
- Drops cleanly into vanilla-JS http.server setup
- LOC: ~40-60 to wire button → pipeline → `AudioContext` playback, plus loading UI
- Cold start: ~2.5 GB Q4 quantized weights from HF CDN on first use, IndexedDB-cached by ORT, 60-180s on home broadband, instant subsequently
- Voice cloning supported (Voxtral-4B-TTS-2603 from <5s reference audio via `VoxtralProcessor`)
- M-series WebGPU is the supported happy path
- **Pick**

Sources:
- [Transformers.js v4 / Voxtral support — npm](https://www.npmjs.com/package/@huggingface/transformers)
- [Transformers.js WebGPU guide](https://huggingface.co/docs/transformers.js/guides/webgpu)
- [mistralai/Voxtral-4B-TTS-2603 model card](https://huggingface.co/mistralai/Voxtral-4B-TTS-2603)
- [Speaking of Voxtral — Mistral blog](https://mistral.ai/news/voxtral-tts)

## Stream 3 — Skill doc placement (inline)

| Doc surface | Where | What goes there |
|---|---|---|
| Core vidux skill | `~/Development/ai/skills/vidux/SKILL.md` Browser section (after "Local plan notes") | New subsection: "Read-aloud add-on (Voxtral, optional)". Integration approach summary, license note (CC BY NC 4.0 personal-only), minimal install (modern browser with WebGPU). |
| Moussey skill | `~/Development/ai/skills/moussey/SKILL.md` (new section before Hard Rules or after vidux-browse mention) | "Voxtral Reader add-on enable" — per-Mac steps to enable WebGPU + first-click weights download, IndexedDB caches per browser profile, ~2.5GB one-time per machine. |
| Recipe (overkill, skipped) | `~/Development/ai/skills/vidux/guides/recipes/voxtral-reader-addon.md` | Not creating — SKILL.md sections suffice for an optional add-on. |

## Cron prompt for the new loop

The cron from the abandoned higgs-reader-poc was deleted (cycle 10 of that plan). New loop should target this plan with calibrated cycle prompt — see PLAN.md Tasks section for the V0-V9 task list.
