# V20 Segment Timeline + Click-to-Jump — 2026-05-03

## What shipped

- Added a segment timeline derived from V19's per-segment decoded WAV durations.
- Footer scrub now maps progress across the merged segment timeline instead of blindly using the browser audio duration alone.
- Word spans are annotated with `data-ra-segment-index`, `data-ra-segment-word-index`, `data-ra-segment-word-count`, and `data-ra-segment-id`.
- Word clicks now seek inside the clicked word's segment using local segment word ratio.
- Highlight advancement now chooses the active segment first, then advances within that segment, so it does not jump across unrelated DOM blocks.

## Browser proof

No model weights were downloaded. No real MLX synthesis ran. Verification used stubbed `/health` and `/v1/audio/speech` responses in the local worktree vidux-browse preview at `http://127.0.0.1:7192`.

Stub segment durations:

- Segment 0: `0.12s`
- Segment 1: `0.36s`
- Segment 2: `0.24s`

Readback after merged playback:

```json
{
  "phase": "v20-segment-timeline-readback",
  "speechCalls": 3,
  "currentTime": 0.648,
  "segmentWordCounts": [3, 7, 6],
  "activeWord": "here",
  "activeSegment": "2",
  "status": "Playing generated audio"
}
```

Click proof:

```json
{
  "clickedWord": "segment",
  "clickedWordSegment": "1",
  "clickedWordIndex": "2",
  "currentTime": 0.24,
  "withinSecondSegment": true,
  "activeWord": "segment",
  "activeSegment": "1"
}
```

Screenshot: `evidence/2026-05-03-v20-segment-timeline.png`.

## Verification

- `node --check browser/static/readaloud.js`
- `python3 -m unittest tests.test_browser_server.BrowserReadaloudStaticContractTests`
- `git diff --check`
- `npm test` — 182 tests passed in 88.517s.
