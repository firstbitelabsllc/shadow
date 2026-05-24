# V28 Reader Cache Quota Guard - 2026-05-04

## What shipped

- IndexedDB read-aloud cache records now include `created_at`, `last_used_at`, `bytes`, `type`, `model`, and `voice`.
- Cache hits refresh `last_used_at`, so stale records age out before recently reused docs.
- After segment cache checks/generation, the client prunes oldest current-model segment blobs above a conservative 160MB / 120-entry cap.
- Current playback segment keys are protected during pruning.
- The player/console can report the cleanup as `Pruned N old cached segments (...)`.
- The visual fixture gained a `cache-pruned` state.

## Browser Proof

Worktree preview:

```text
http://127.0.0.1:7296/?plan=codex-voxtral-mlx-reader-20260502%2Fprojects%2Fvoxtral-reader-addon%2FPLAN.md
```

Setup:

- Started vidux-browse with `VIDUX_DEV_ROOT=/Users/leokwan/Development/vidux-worktrees` on port `7296`.
- Seeded 12 stale current-model segment records into IndexedDB, each with `bytes = 20 * 1024 * 1024`.
- Stubbed `/health` and `/v1/audio/speech` in the browser to avoid real MLX calls.
- Replaced `#md-body` with 3 short paragraphs and clicked the read-aloud control.

Observed result:

```json
{
  "status": "Finished",
  "requests": 3,
  "stale": 7,
  "currentModelSegments": 10,
  "currentModelBytes": 146815172
}
```

Interpretation:

- The 3 short paragraphs made 3 fake speech requests.
- The prune pass removed 5 stale rows, reducing stale rows from 12 to 7.
- Current-model cached segment bytes ended below the 160MB cap.
- No model weights were downloaded and no real audio was synthesized.

Screenshot:

- `evidence/2026-05-04-v28-cache-quota.png`

## Verification

```text
node --check browser/static/readaloud.js
python3 -m unittest tests.test_browser_server.BrowserReadaloudStaticContractTests
git diff --check
npm test
```
