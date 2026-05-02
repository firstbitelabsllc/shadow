# M9 Verification — Voice picker dropdown

Adds a 20-voice picker `<select>` to the vidux-browse top bar. Selection is persisted per-browser in `localStorage` and snapshotted at click-time so mid-playback voice changes can't desync chunks.

## Voice list (sourced from Voxtral cache)

```bash
ls ~/.cache/huggingface/hub/models--mlx-community--Voxtral-4B-TTS-2603-mlx-bf16/snapshots/*/voice_embedding/
```

Returned 20 `.safetensors` files, grouped in the picker as:

- **English (default group):** `casual_male`, `casual_female`, `neutral_male`, `neutral_female`, `cheerful_female` (5)
- **Other languages:** Arabic, German (×2), Spanish (×2), French (×2), Hindi (×2), Italian (×2), Dutch (×2), Portuguese (×2) — 15 voices

These ARE the actual presets the model ships — no guessing or hard-coded list from a doc. The names map 1:1 to the voice argument the OpenAI-compatible endpoint expects.

## Files touched

| File | Change |
|------|--------|
| `browser/static/index.html` | Added `<select id="root-readaloud-voice">` between the 🔊 button and Annotate, with two `<optgroup>` sections. Title attribute on the existing 🔊 button updated to reflect mlx-audio (was stale "Voxtral, WebGPU"). |
| `browser/static/readaloud.js` | New `READALOUD.voiceSelect` field, `DEFAULT_VOICE`/`VOICE_STORAGE_KEY` constants, `readaloudCurrentVoice()` helper. Init reads `localStorage`, validates against the option list, and wires a `change` listener that writes back. Per-click voice snapshot prevents mid-playback desync. `readaloudFetchChunkAudio` now takes `voice` as a parameter. |
| `browser/static/app.js` | `ANNOTATION_CAPTURE_EXCLUDE_SELECTOR` now includes `#root-readaloud-voice` and `#root-readaloud-voice *` so dropdown clicks don't trigger annotation capture. |
| `browser/static/style.css` | New `.topbar-meta select.root-readaloud-voice` rule matching the existing button styling (paper bg, rule border, mono font, 12px). Hover + focus states. `max-width: 140px` keeps long option names from blowing out the top bar. |

## Verification (isolated Chromium via browse CLI)

```
selectExists: true
defaultValue: "casual_male"
optionCount: 20
```

Setting the dropdown to `es_male` and dispatching the `change` event:

```
persisted: "es_male"   // localStorage.getItem("vidux.readaloud.voice")
selValue:  "es_male"
```

Clicking 🔊 with `es_male` selected, fetch hook captures the request body sent to mlx-audio.server:

```json
{
  "model": "mlx-community/Voxtral-4B-TTS-2603-mlx-bf16",
  "input": "Voice picker test, this should use Spanish male voice for synthesis.",
  "voice": "es_male",
  "response_format": "wav"
}
```

Server returned 200, button cycled back to `🔊 Read` cleanly. The end-to-end path uses the user-selected voice — no hard-coded `casual_male` fallback in the request body.

Screenshot: [`2026-05-02-m9-voice-picker.png`](2026-05-02-m9-voice-picker.png) — top bar showing the picker collapsed to "Spanish male" (the human-readable label for `es_male`) after selection persisted.

## Caveats / deferred polish

- **No "preview voice" button.** Picking a voice doesn't audition it on a sample sentence; you only hear the new voice when you next click 🔊 on real content. M9 punted on a preview button — out of scope for the picker MVP. Add one later if Leo finds the picker friction unworkable.
- **No language auto-detect.** Picking `fr_male` to read English text still works (Voxtral handles it), but the model is more natural when voice and content language match. Not the picker's job to auto-route.
- **localStorage is per-origin.** A swap from `localhost:7191` to `127.0.0.1:7191` would lose the saved voice — same as how the Read-aloud server's CORS allowlist enumerates both. Negligible for normal use.
