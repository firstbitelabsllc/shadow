# M12 + M13 + M14 — Speech speed, word highlight, loading UX

Shipped together this cycle because all three live in `browser/static/readaloud.js` + `browser/static/style.css`. Triggered by Leo's morning M5 audible verdict (2026-05-02 ~9:54am: *"I hear it now nice... it talks a bit slow and i would like word highlighting and better loading indicators"*). Atomic claim commit `2c6f599`.

## M12 — Default speech speed 1.25× (server-side)

mlx-audio's OpenAI-compatible `/v1/audio/speech` endpoint accepts a `speed` parameter (server-side resample, NOT a client-side `playbackRate` chipmunk hack). Probed before shipping:

```
$ curl -X POST http://127.0.0.1:8000/v1/audio/speech \
    -d '{"model":"...","input":"This is a one second test sentence.","voice":"casual_female","response_format":"wav","speed":1.25}' \
    -o /tmp/m12-test.wav -w "%{size_download}\n"
195884    # speed=1.25
299564    # speed=1.0  (same input)
```

195884 / 299564 ≈ 0.65 — about 35% shorter audio at speed 1.25, with pitch preserved (server resamples in time domain, not just playback rate).

Wired into `readaloudFetchChunkAudio` as a top-level `const SPEED = 1.25` included unconditionally in every request body alongside `voice` and `response_format`. Applies to both the main read-aloud loop AND the M11 preview button (both flow through the same fetch).

## M13 — Per-word highlight (heuristic even-distribution = M10 path 3)

The M10 probe ruled out per-word highlight via mlx-audio streaming (no per-word timing in the SSE stream) and ruled out path 2 (mlx-whisper alignment, missing HF processor). Path 1 (whisperx CPU pre-compute) costs ~10s extra latency per chunk. Path 3 — heuristic even-distribution — is free and zero-latency. Picked path 3 here as the v1 ship; can upgrade to whisperx alignment later if Leo wants more accuracy.

**Approach:**
1. When a chunk's audio starts playing, find the chunk's text in the DOM (with progressive needle-shortening fallback for chunks that span multiple paragraphs/headings).
2. Replace the matched range with a `<span class="ra-active">` wrapper whose children are per-word `<span class="ra-word">…</span>` spans, separated by their original whitespace.
3. Fire `setTimeout` per word at `audioBuf.duration / wordCount` intervals to migrate the `.ra-word-active` class.

**The DOM matching gotcha — and the fix:** real markdown bodies split text across `<p>`, `<h2>`, `<li>`, etc. The original `readaloudHighlightChunk` searched for the FULL chunk text (~320 chars) in a single text node and silently failed when none matched. The pre-existing M5 evidence used a flat plain-text injection (`#md-body.innerText = "First sentence…"`), so the bug was masked. New `readaloudFindChunkRange()` walks candidate needles in order: full chunk → first sentence → first line → first 80 chars → first 30 chars → return null. The wrapper covers as much as the longest matching candidate.

**Cleanup:** `readaloudClearHighlights()` now flattens all `.ra-word` children to plain text BEFORE unwrapping the `.ra-active` wrapper, then `parent.normalize()` coalesces adjacent text nodes. Verified: after abort, `document.querySelectorAll('.ra-word').length === 0`.

## M14 — Loading-indicator clarity

Old behavior: button showed `🔊 Synthesizing 1/N…` for the cold-fetch of chunk 1 (~5–10 s), then jumped to `■ Stop` and stayed frozen for the rest of playback. On a 19-chunk plan (Leo's morning test) that's ~95 s of "is it stuck?"

New behavior:
1. Initial click → `🔊 Synthesizing 1/N…`
2. Chunk 1 audio starts → `■ 1/N` + thin progress bar fills 1/N % at the bottom of the button (CSS `::after` driven by `--ra-progress`).
3. Each subsequent chunk start → label increments to `■ 2/N`, `■ 3/N`, …, progress bar advances.
4. Final chunk ends → button reverts to `🔊 Read`, `--ra-progress` removed.

`readaloudUpdatePlayingLabel(idx, total)` runs in the same `setTimeout(..., startsInMs)` that fires the highlight migration, so counter and highlight stay in lockstep.

## End-to-end verification (browse CLI on isolated Chromium :7191)

Restarted vidux-browse to pick up M8 endpoint (PID 57444 → 47267, 14 h elapsed → 0 s). M8 endpoint live: `POST /api/upload-ref-audio` with empty body returns 400 (not 404).

Drove the browse CLI on a 30-sentence injected test body (15 chunks). Captured state at multiple `t` checkpoints:

| t | Button label | Progress | `.ra-word` count | `.ra-word-active` count |
|---|---|---|---|---|
| 5 s | `🔊 Synthesizing 1/15…` | (none) | 0 | 0 |
| 10 s | `🔊 Synthesizing 1/15…` | (none) | 0 | 0 |
| 15 s | `■ 1/15` | 6.67% | 20 | 1 |
| 20 s | `■ 1/15` | 6.67% | 20 | 1 |
| 25 s | `■ 2/15` | 13.33% | 20 | 1 |
| 35 s | `■ 3/15` | 20% | 20 | 1 |
| post-abort | `🔊 Read` | (none) | 0 | 0 |

Every transition matches the spec. Counter advances as chunks start playing. Word highlight wraps the chunk's first ~20 words and migrates `.ra-word-active` across them at `audioBuf.duration / 20` intervals. Cleanup leaves no orphaned spans.

## Files touched

| File | Change |
|------|--------|
| `browser/static/readaloud.js` | `SPEED = 1.25` const + included in fetch body. New `readaloudFindChunkRange` (progressive needle shortening). New `readaloudHighlightChunkWords` (per-word wrapping + setTimeout migration). New `readaloudUpdatePlayingLabel` (chunk counter + `--ra-progress` CSS var). `readaloudClearHighlights` now flattens `.ra-word` children before unwrapping. Play loop calls the new helpers. |
| `browser/static/style.css` | `.root-readaloud-toggle.is-active::after` thin progress bar driven by `--ra-progress`. `.ra-word` + `.ra-word-active` styles (subtle inversion + accent-color outline so the active word pops against the chunk's `.ra-active` background). `.root-readaloud-toggle` made `position: relative; overflow: hidden;` to anchor the bar. |

## Live activation note

vidux-browse PID was restarted from 57444 (~14 h elapsed = pre-M3/M8) → 47267 (fresh, has the M8 `/api/upload-ref-audio` endpoint). M8 voice cloning is now live on `:7191` for Leo's next test, in addition to M12/M13/M14.

## Screenshots

- `2026-05-02-m12-m14-t5s.png` / `t10s.png` — initial loading state
- `2026-05-02-m12-m14-t15s.png` — first chunk playing, counter at 1/15, words wrapped
- `2026-05-02-m12-m14-t25s.png` — chunk 2/15
- `2026-05-02-m12-m14-t35s.png` — chunk 3/15
- `2026-05-02-m12-m14-cleanup.png` — post-abort idle, no leaked spans
