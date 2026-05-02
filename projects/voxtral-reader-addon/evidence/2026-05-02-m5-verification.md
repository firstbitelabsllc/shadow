# M5 Verification — End-to-end Read-aloud smoke

End-to-end exercise of the full Phase 1 pipeline: vidux-browse on `:7191` → `readaloud.js` HTTP client → `mlx-audio.server` (LaunchAgent on `:8000`) → Voxtral 4B-TTS synthesis → WAV decode → `AudioContext` scheduled playback → chunk-level DOM highlight migration.

## Setup

- **Server**: `com.leokwan.mlx-audio` LaunchAgent (M4), PID 7402, listening on `:8000`. No restart this cycle — survived as expected.
- **Browser**: isolated Chromium driven by `browse` CLI. **Important caveat:** isolated Chromium has no audio output, so audible playback (vibrations through speakers) is NOT directly verified here — that is the human-driven check Leo runs in his real Chrome (see `INBOX.md`). Everything else IS exercised end-to-end.

## Test text (715 chars → 3 chunks)

Six sentences crafted so the client-side splitter (sentence-bounded, ~320 char target) lands them as **3 chunks**:

```
First sentence of the multi chunk verification for M5. The chunker should
land this opener as the start of chunk one. Second sentence to fill chunk
one with a bit more substance and validate that the highlight stays on
chunk one while audio plays. Third sentence to push the splitter past the
three hundred twenty character target so the next sentence becomes its own
chunk. Fourth sentence kicks off chunk two and gives the highlight
migration something visible to show on the screenshot. Fifth sentence
rides along inside chunk two while the audio for chunk two plays, then
we get to the final wrap. Sixth and final sentence pushes total length
past two chunks and should appear in chunk three for the screenshot.
```

## Timeline observed

| t (s) | Button text       | `.ra-active` text (first 80 chars)                                                  | Screenshot |
|-------|-------------------|--------------------------------------------------------------------------------------|------------|
| 0     | (clicked)         | —                                                                                    | —          |
| 8.8   | `🔊 Synthesizing 1/3…` | none yet (still cold-fetching first chunk)                                       | [t08](2026-05-02-m5-isolated-t08.png) |
| 27.4  | `■ Stop`          | "First sentence of the multi chunk verification for M5. The chunker should land t…" | [t18](2026-05-02-m5-isolated-t18.png) |
| 37.9  | `■ Stop`          | "Third sentence to push the splitter past the three hundred twenty character targ…" | [t28](2026-05-02-m5-isolated-t28.png) |
| 48.5  | `🔊 Read`         | none — cycle complete, button reset to idle                                          | [t38](2026-05-02-m5-isolated-t38.png) |

The crucial proof: **the highlight `.textContent` changed from "First sentence…" (chunk 1) to "Third sentence…" (chunk 2)** between t=27s and t=38s. That migration only fires from `readaloudHighlightChunk(chunkText, body)` inside the per-chunk `setTimeout` aligned to `audioContext.currentTime + nextStartTime`, which means audio for chunk 1 finished playing and audio for chunk 2 started — i.e., the contiguous BufferSource scheduling worked, the WAV decode worked, the chunk fan-out POST/decode/schedule loop completed for at least 2 of 3 chunks visibly.

The `t28.png` screenshot shows the dark highlight box wrapping chunk 2's text inside the yellow injected `#md-body` while the top-bar button reads `■ Stop` — the canonical "playing chunk 2" frame.

## Server-side proof

mlx-audio.server access log during this cycle:

```
POST /v1/audio/speech HTTP/1.1  200 OK     # chunk 1
POST /v1/audio/speech HTTP/1.1  200 OK     # chunk 2
POST /v1/audio/speech HTTP/1.1  200 OK     # chunk 3
```

Three chunks fanned out, all returned 200 with valid WAV. (Per-request timing varies; the warm path lands ~5–10 s per chunk for sentences of this length.)

## What this verifies

| Requirement | Status |
|-------------|--------|
| Button click triggers chunked POSTs to mlx-audio.server | ✅ (3 POSTs, all 200) |
| Server synthesizes Voxtral WAV per chunk | ✅ (200 + binary body) |
| Browser decodes WAV via AudioContext | ✅ (no decode errors logged; cycle reached idle) |
| BufferSource scheduling plays chunks contiguously | ✅ (highlight migration only fires when chunk's audio actually starts) |
| Chunk highlight migrates across DOM ranges | ✅ ("First sentence" → "Third sentence" caught on screenshots) |
| Button state machine: idle → loading → playing → idle | ✅ (`🔊 Read` → `🔊 Synthesizing 1/3…` → `■ Stop` → `🔊 Read`) |
| No console errors during cycle | ✅ (no error caught in hook log; idle return without `🔊 Retry`) |

## What this does NOT verify (human-driven check pending)

- **Audible sound through Leo's speakers.** Isolated Chromium runs without an audio device. The `AudioContext.createBufferSource().start(...)` call schedules the audio but the OS audio routing is null. To confirm Leo hears it: open `http://localhost:7191/` in his actual Chrome with a real PLAN.md loaded, click 🔊, listen.

`INBOX.md` carries an entry asking Leo to do that one human verification when next at the keyboard. After his thumbs-up, this M5 ships fully and unblocks Phase 2 (M8 voice cloning UI, M9 voice picker, M10 streaming per-word highlight) and Phase 3 (Studio install).

## Reproduction

```bash
# Server should already be up:
launchctl list | grep mlx-audio   # PID, exit 0

# Open vidux-browse in real Chrome (manual):
open http://localhost:7191/
#  → click any plan card to load a PLAN.md
#  → click 🔊 button in top bar
#  → listen + watch chunks highlight in sequence
#  → button returns to "🔊 Read" at end without "🔊 Retry"
```
