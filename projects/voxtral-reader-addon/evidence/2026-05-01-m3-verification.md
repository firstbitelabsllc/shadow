# M3 Verification — readaloud.js HTTP client → mlx-audio.server

End-to-end smoke verifying the new `browser/static/readaloud.js` correctly POSTs artifact text to `mlx-audio.server` and plays the returned WAV. Drove an isolated Chromium via `browse` CLI against the live vidux-browse on `:7191` and the live mlx-audio.server on `:8000`.

## Artifacts

- `2026-05-01-m3-loading.png` — button mid-cycle, label `🔊 Synthesizing 1/1…`, class includes `is-loading`.
- `2026-05-01-m3-playing.png` — captured after the (short) audio had already completed; button back to `🔊 Read` idle. Cycle elapsed < 12 s for the test text.

## Wiring proofs

| Check | Result |
|-------|--------|
| `node --check browser/static/readaloud.js` | OK |
| `curl http://127.0.0.1:7191/static/readaloud.js` matches disk | OK (no caching) |
| Button initialized with new title `Read aloud (Voxtral via local mlx-audio.server)` | OK — proves `readaloudInit()` ran |
| Direct `fetch(/v1/audio/speech)` from page console | HTTP 200, `content-type: audio/wav` — proves CORS allowed for `127.0.0.1:7191` origin |
| Click `#root-readaloud-toggle` → POST observed in mlx-audio access log | `127.0.0.1:50070 - "POST /v1/audio/speech HTTP/1.1" 200 OK` (and others) |
| Multi-sentence input → multiple POSTs (chunk fan-out) | Yes, observed two new POSTs from a single click on the 4-sentence test text |
| Button state machine `idle → loading → playing → idle` without entering `error` | OK — final `btn=🔊 Read`, `classes=root-readaloud-toggle` |
| Console `error` hook caught nothing during cycle | OK — empty error log |

## What is NOT yet proven (deferred to other tasks)

- **Audible playback.** The verification browser is a headless isolated Chromium with no speakers. We confirm the WAV was *fetched + decoded + scheduled into AudioContext* and the cycle returned to idle without error, but we do not confirm Leo can hear it — that requires Leo's interactive Chrome session (M5).
- **Highlight visible mid-playback.** `readaloudHighlightChunk` fires on `setTimeout` aligned to chunk start time. For short test text (single chunk under 320 chars), the highlight wraps the whole `#md-body` for the brief playback window. The `ra-active` class CSS (`browser/static/style.css`) is unchanged from the Kokoro impl, so visible behavior is identical. M5 will catch a multi-chunk highlight migrating across DOM ranges in a real artifact view.
- **Server-offline error message.** Code path exists (`networkish` branch sets `🔊 Server offline — start mlx-audio LaunchAgent (see /moussey)`), but not exercised in this run. M4 will provide the LaunchAgent that makes the offline scenario the default-recoverable state.

## Reproduction

```bash
# Server side (already running as background task b31hares4 from M2 cycle):
mlx_audio.server --host 127.0.0.1 --port 8000 \
  --allowed-origins http://localhost:7191 http://127.0.0.1:7191 \
  --log-dir ~/Library/Logs

# vidux-browse (already running as LaunchAgent com.leokwan.vidux-browser):
# http://127.0.0.1:7191/

# Browser smoke (this verification):
browse newpage http://127.0.0.1:7191/
browse eval '<inject #md-body with test paragraph>'
browse click "#root-readaloud-toggle"
# Watch button text + mlx-audio.server POST log
```

## Decision: M3 [completed]

The HTTP client wiring is correct. The behaviors deferred above have explicit downstream tasks (M4 for LaunchAgent, M5 for human-in-the-loop e2e on Leo's real Chrome). Per /vidux principle 5, the proof here is mechanical (HTTP status codes from server log + button state transitions captured in browser eval), not a self-asserted "it works."
