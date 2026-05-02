# M11 Verification — Voice preview button

Discovered UX gap shipped this cycle: the M9 picker exposed 20 voices but the only way to audition one was to pick a real artifact and click 🔊. The preview button gives a one-click sample of the currently-selected voice on a fixed test sentence ("This is a sample of the selected voice.").

## Files touched

| File | Change |
|------|--------|
| `browser/static/index.html` | New `<button id="root-readaloud-preview" class="root-readaloud-preview">▶</button>` between the voice picker and Annotate. |
| `browser/static/readaloud.js` | New `READALOUD.previewButton`, `READALOUD.previewAbort`, `READALOUD.previewContext` fields. New `PREVIEW_TEXT` constant. New `readaloudOnPreviewClick()` async handler that calls the existing `readaloudFetchChunkAudio` with the picker's current voice + the preview text, decodes via a dedicated `AudioContext`, plays once, and resets the button on `source.onended`. Click while playing aborts + resets. Reuses the same fetch + decode plumbing as the main 🔊 path. |
| `browser/static/app.js` | `#root-readaloud-preview` added to `ANNOTATION_CAPTURE_EXCLUDE_SELECTOR` so clicks don't trigger annotation capture. |
| `browser/static/style.css` | Tight rule (`min-width: 28px; padding: 4px 8px;`) so the button is icon-sized and sits flush against the picker. |

## Verification

```
voice changed to: fr_female
preview button clicked
fetch body sent to mlx-audio.server:
  {
    "model": "mlx-community/Voxtral-4B-TTS-2603-mlx-bf16",
    "input": "This is a sample of the selected voice.",
    "voice": "fr_female",     ← matches picker selection
    "response_format": "wav"
  }
button transitions: ▶ → … (synthesizing) → ■ (playing) → ▶ (idle)
total cycle: ~6s for the 40-char preview text
```

Picker selection flows into preview voice. No console errors. Button correctly returns to idle after `source.onended` fires.

Screenshot: [`2026-05-02-m11-preview-button.png`](2026-05-02-m11-preview-button.png).

## Caveats

- **Independent AudioContext.** The preview uses its own `AudioContext` separate from the main 🔊 path so the two can't desync. Trade-off: clicking 🔊 while preview is playing won't auto-stop the preview (the user has to click the preview's ■ first). Acceptable for an audition button.
- **Single test sentence.** All 20 voices preview the same English text, including the non-English voices. Voxtral handles cross-language input fine (text → phoneme → speech) but a French-male preview reading English with a French accent isn't the most natural showcase. Per-language preview text was deferred — single sentence keeps the preview path single-fetch and dependency-free.
