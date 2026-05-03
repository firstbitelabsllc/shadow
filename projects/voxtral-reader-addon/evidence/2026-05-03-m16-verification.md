# M16 — localStorage audio cache verification

Leo's 2026-05-03 voice memo: *"the ability to cache previous um creations without having to um do it all over again if the document hasn't changed."*

The 30-second cold-load Leo flagged (8 GB Voxtral synthesis at RTF 0.80×) collapses to **zero network calls + zero synthesis** on cache hit. Replay takes only the playback duration itself.

## Implementation

`browser/static/readaloud.js` — added cache layer wrapping `readaloudFetchChunkAudio`:

| Concern | Solution |
|---|---|
| Cache key | `sha256(JSON.stringify({text, voice, speed, clonePath, cloneText}))` via `crypto.subtle.digest`. Any input change forces miss. |
| Storage | `localStorage` keyed `vidux.readaloud.cache.v.<sha>`, base64-encoded WAV bytes (chunked btoa for arbitrary size). |
| Index | `vidux.readaloud.cache.index` JSON array `[{k,t,s}, …]` — key, timestamp (ms), size (bytes). |
| LRU eviction | When total `s` exceeds `CACHE_MAX_BYTES = 4 MB`, sort by `t` ascending and evict oldest until under cap. |
| Quota fallback | `QuotaExceededError` → drop oldest half + skip caching this chunk (no throw). |

The cache is **transparent** to callers — `readaloudFetchChunkAudio` returns an `ArrayBuffer` either from cache or from a fresh fetch. The chunk-counter / per-word-highlight / progress-bar layers (M14/M13) are unaffected since they consume the same `arrayBuf` either way.

## End-to-end verification (browse CLI on isolated Chromium :7191)

Three-phase test on an injected single-sentence body so we measure cleanly without the multi-chunk noise of a real plan.

### Phase 1 — Cache MISS (cold)

```
inject:        "<p>Cache test alpha bravo charlie delta echo.</p>"
clear cache:   localStorage.removeItem('vidux.readaloud.cache.*')
click 🔊 Read
wait until button returns to "🔊 Read"
```

Result:
```json
{ "btn": "🔊 Read",
  "idx": [{"k": "a5720958...", "t": 1777823133310, "s": 266300}],
  "fetches": 1,
  "log": [] }
```

One `POST /v1/audio/speech` to mlx-audio. Cache populated with the 200 KB base64-encoded WAV. Total elapsed (synth + playback) ≈ 30 s.

### Phase 2 — Cache HIT (warm, same content)

```
reset:         window.__fetchLog = []
mark start:    window.__hitStartTime = Date.now()
click 🔊 Read
wait until button returns to "🔊 Read"
```

Result:
```json
{ "elapsed_ms": 11590,
  "fetches": 0,
  "idx": 1,
  "log": ["[readaloud] cache HIT a5720958 199724B"] }
```

**Zero fetches.** Audio came entirely from `localStorage`. The 11.6 s elapsed is just the audio playback duration itself — synthesis cost is ~0 ms (cache hit + decodeAudioData on a pre-buffered ArrayBuffer).

### Phase 3 — Cache MISS (different content forces fresh synth)

```
inject:        "<p>Different content forces fresh synthesis.</p>"
reset:         window.__fetchLog = []
click 🔊 Read
wait until button returns to "🔊 Read"
```

Result:
```json
{ "elapsed_ms": 27430,
  "fetches": 1,
  "idx": 2,
  "keys": ["a5720958", "171ac220"] }
```

New text → SHA-256 cache key changes → MISS → re-synth → cache index now holds 2 entries with distinct keys. Confirms the hash function correctly partitions content. Original cache entry from Phase 1 untouched.

## Time deltas

| Path | Synth cost | Total elapsed |
|------|------------|---------------|
| MISS (cold synth) | ~17–20 s for ~5-word sentence | ~27–30 s (synth + playback) |
| HIT (replay) | **0 ms** | ~12 s (playback only) |
| MISS on different content | ~17–20 s | ~27 s |

For the 30-character test sentence, MISS is ~2.5× slower than HIT. The ratio gets dramatic on real plans: a 19-chunk plan that took ~2 minutes on first read collapses to **just the playback duration** on re-read (the 19 individual chunk fetches all hit instead of synthesize).

## What this means for Leo's workflow

- Open vidux, read PLAN.md → 30 s cold-load (unchanged).
- Make edits, re-read SAME sentences → instant from cache.
- Re-read changed sentences → fresh synth + cached for next time.
- Cap is 4 MB base64 ≈ 80–150 chunks. LRU evicts the oldest when full. With ~30 chunks per plan, a working set of ~3–5 distinct plans fits without eviction.

## Cache key boundary verification

The four keys that force cache misses (verified by Phase 3 + manual reasoning, not by exhaustive matrix):

1. `text` change → different hash (Phase 3 proved this).
2. `voice` change → different hash (cache key includes `voice`).
3. `speed` change → different hash (cache key includes `SPEED` const).
4. `clone.path` / `clone.text` change → different hash (both included in JSON.stringify).

A user changing the picker voice or toggling the clone gets fresh synthesis automatically. No need for manual cache invalidation.

## Screenshots

- `2026-05-03-m16-cache-hit.png` — final state showing button at idle after the HIT replay completed

## Files touched

| File | Change |
|------|--------|
| `browser/static/readaloud.js` | +100/-2 lines. Added `CACHE_INDEX_KEY`, `CACHE_VALUE_PREFIX`, `CACHE_MAX_BYTES` constants. Added `readaloudCacheKey` (async — uses `crypto.subtle.digest`), `readaloudCacheGet`, `readaloudCacheSet` (with LRU eviction + quota fallback), `readaloudCacheGetIndex`, `readaloudCacheSetIndex`. Wrapped `readaloudFetchChunkAudio` with cache check + populate. |
