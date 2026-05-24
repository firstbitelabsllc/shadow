# V19 Per-Segment Cache Scheduler — 2026-05-03

## What shipped

- Replaced whole-pane synthesis/cache with a per-segment scheduler in `browser/static/readaloud.js`.
- Each rendered segment now gets its own cache key based on model, voice, kind, text, and stable segment hash.
- Playback checks IndexedDB segment rows first, synthesizes only cache misses, stores per-segment WAV blobs with metadata, then merges ordered segment audio into one WAV for the existing footer player.
- Footer status now exposes queue states such as `Checking segment N/M`, `3 cached, 2 synthesizing`, and `Merging segment audio`.
- The merged playback metadata keeps `currentSegments` and `currentSegmentDurations` ready for V20 timeline/click-to-jump work.

## Browser proof

No model weights were downloaded. No real MLX synthesis ran. Browser verification used a stubbed local `/health` and `/v1/audio/speech` response inside the worktree vidux-browse preview at `http://127.0.0.1:7192`.

First pass:

```json
{
  "phase": "first-pass",
  "healthCalls": 1,
  "speechCalls": 3,
  "speechInputs": [
    "Segment one title",
    "Segment two paragraph has several words.",
    "Segment three paragraph stays separate."
  ],
  "cacheCount": 3,
  "status": "Playing generated audio",
  "wordCount": 14
}
```

Reload/cache pass:

```json
{
  "phase": "reload-cache-pass",
  "healthCalls": 1,
  "speechCalls": 0,
  "speechInputs": [],
  "cacheCount": 3,
  "status": "Playing cached audio",
  "wordCount": 14
}
```

Screenshot: `evidence/2026-05-03-v19-segment-cache.png`.

## Automation

Updated Codex heartbeat automation `voxtral-reader-iterate` to run every 20 minutes. The prompt continues PR #87 against this plan, with V20 as the next task after V19 and the same guardrail: do not download model weights or run real synthesis unless the cycle is explicitly doing first-synthesis verification.

## Verification

- `node --check browser/static/readaloud.js`
- `python3 -m unittest tests.test_browser_server.BrowserReadaloudStaticContractTests`
- `git diff --check`

Full `npm test` should run after the evidence/plan checkpoint and before push.
