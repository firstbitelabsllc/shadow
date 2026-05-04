# M19 — Per-Section Playback Verification (2026-05-03)

## Summary

Per-section play buttons (▶) inject before every `<p>/<h*>/<li>` in `#md-body`, click → fetch + decode + play just that section's text via the existing `readaloudFetchChunkAudio` plumbing. Cache-aware (M16) so re-clicks of the same section are instant (cache replay, no server fetch).

## Test setup

- Driver: `browse` CLI in isolated-Chromium local mode
- Target: `http://127.0.0.1:7191/?plan=vidux/projects/voxtral-reader-addon/PLAN.md`
- Servers: vidux-browse (`:7191`), mlx-audio (`:8000`) both LaunchAgent-managed

## Verifications

### 1. Section button injection (idempotent, all section types)

```
buttonCount: 101
hostCount: 101
firstButtonHTML: <button class="ra-section-play" type="button" title="Read this section aloud" aria-label="Read this section aloud">▶</bu...
sampleHostFirstChild: BUTTON
sampleHostFirstChildClass: ra-section-play
hasNoOrphanButtons: true
cssLoaded: true
```

101 sections in the rendered PLAN.md (mix of `<p>`, `<h2>`, `<h3>`, `<li>`). Each got exactly one `.ra-section-play` button as `firstChild`. No orphan buttons (every button has a `.ra-section-host` parent). CSS loaded — `getBoundingClientRect().width > 0`.

### 2. Click fires fetch with correct section text (no ▶ prefix leaked)

Click first H3 ("Phase 1 — mlx-audio + vidux-browse integration (active)") with a `window.fetch` hook installed:

```
window.__fetches[0]:
  input: "Phase 1 — mlx-audio + vidux-browse integration (active)"
  voice: "casual_male"
  speed: 1.25
```

The `▶` button text was correctly stripped by `readaloudExtractSectionText` (clones the section, removes `.ra-section-play` and `.ra-word` spans before extracting text).

### 3. State machine: idle → is-loading → is-playing → idle

After click:
- ~0s: button class = `ra-section-play is-loading`, text = `…`, title = "Synthesizing…"
- ~10–12s: button class = `ra-section-play is-playing`, text = `■`, title = "Stop section playback" — synth + decode complete, AudioBufferSource scheduled
- Click stop: class resets to `ra-section-play`, text reverts to `▶`

### 4. M16 cache hit on re-click (KEY VERIFICATION)

Cleared cache + reset fetch counter, then:
- Click 1 on H3 (Phase 2) → fetch fires (count: 1), waits ~12s for synth, transitions to `is-playing`, cache index = 1 entry written
- Click stop → state resets, sectionPlayback cleared
- Click 2 on SAME H3 → no new fetch (count stays at 1), button transitions to `is-playing` in ~3s (cache replay only, no server roundtrip)

```
Before second click: 1:ra-section-play:1
After second click:  1:ra-section-play is-playing:1
                     ^                                ^
                     fetch count                       cache size
                     (unchanged — cache HIT)
```

### 5. Stop click resets cleanly from is-playing OR is-loading

Verified the toggle pattern works from both intermediate states. `readaloudStopSectionPlayback` aborts the AbortController, closes the AudioContext, and resets button classes.

## Server log corroboration

```
INFO:     127.0.0.1:53479 - "OPTIONS /v1/audio/speech HTTP/1.1" 200 OK
INFO:     127.0.0.1:53479 - "POST /v1/audio/speech HTTP/1.1" 200 OK    ← click 1 (cache miss, server hit)
INFO:     127.0.0.1:53757 - "POST /v1/audio/speech HTTP/1.1" 200 OK    ← (earlier, separate test)
```

Cache hits show NO server log entry — confirming the fetch was short-circuited at the localStorage layer, not just deduped at the response level.

## Files

- `browser/static/readaloud.js` — +153 lines: `READALOUD.sectionPlayback`, `readaloudInjectSectionButtons`, `readaloudExtractSectionText`, `readaloudStopSectionPlayback`, `readaloudOnSectionPlay`, `readaloudWatchMarkdownBody` (MutationObserver on `#pane`)
- `browser/static/style.css` — +66 lines: `.ra-section-host`, `.ra-section-play` (default + hover + focus + is-loading + is-playing), mobile fallback inside `@media (max-width: 900px)`

## Audible verdict gate

Isolated Chromium has no audio device, so audible playback is NOT verified here. The fetch + decode + cache + state-machine layers are verified end-to-end, but Leo will need to hear it in real Chrome to confirm sound. M5's pattern applies — this is a downstream confirmation.

## Screenshot

`evidence/2026-05-03-m19-section-cache-hit.png` — section button in `is-playing` state after cache-hit re-click (fetch count unchanged from previous play).
