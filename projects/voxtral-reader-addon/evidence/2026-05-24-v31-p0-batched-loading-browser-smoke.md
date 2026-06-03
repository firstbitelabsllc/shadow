# V31 P0 Batched Loading Browser Smoke

## Scope

Leo called out two remaining P0s after the V30 runtime fix:

- Performance cannot waste time on avoidable sequential MLX calls.
- The footer must make long local waits obvious, not ambiguous.

This cycle keeps the proven `127.0.0.1:8765` Voxtral MLX script server path and changes the browser client to batch adjacent uncached short sections into one TTS request. The returned WAV is split back into per-section cache entries, so repeat plays still use the section cache.

## What Changed

- `browser/static/readaloud.js`
  - Added `READALOUD_SYNTH_BATCH_TARGET_CHARS = 700` and `READALOUD_SYNTH_BATCH_MAX_SEGMENTS = 6`.
  - Added adjacent-miss batching with `readaloudBuildSynthesisBatches`.
  - Added post-response splitting via `readaloudSplitBatchAudio` so one fast MLX call still preserves per-section replay cache.
  - Added explicit loading states: `generating audio batch`, elapsed seconds, first-run MLX load hint, WAV buffering, splitting/decoding, browser audio buffering, and confirmed playback.
- `browser/static/readaloud-fixture.html` / manifest
  - Added batch-progress and batch-splitting fixture states.
- `scripts/install-voxtral-launchagent.sh`
  - Added repo-owned install/repair path for `com.leokwan.vidux-voxtral-mlx` on `127.0.0.1:8765`.
- `SKILL.md` and `SETUP_NEW_MACHINE.md`
  - Added the LaunchAgent installer and explicit buffering/performance semantics.

## Live Browser Proof

Live target: `http://127.0.0.1:7191`

Smoke text had three rendered sections (`h1`, `p`, `p`). The browser cleared IndexedDB first, then clicked the real footer `Read` button.

Observed:

- Speech request count: `1`
- Request URL: `http://127.0.0.1:8765/v1/audio/speech`
- Request body joined all three sections into one `input`.
- Wall time to confirmed playback: `66597 ms`
- Final status: `Playing generated audio`
- Final audio state: `currentTime=1.144837`, `duration=29.28`, `readyState=4`, `paused=false`, `playbackRate=1.12`
- WAV artifact: `2810924` bytes, mono PCM, `48000 Hz`, `29.28s`

Representative status transitions:

```text
Checking segment 1/3: V31 P0 batched loading proof
0 cached, generating audio batch 1/1: 3 segments 1-3: V31 P0 batched loading proof
0 cached, generating audio batch 1/1: 3 segments 1-3: V31 P0 batched loading proof (8s elapsed) First run can load MLX weights; this is still working.
...
0 cached, generating audio batch 1/1: 3 segments 1-3: V31 P0 batched loading proof (63s elapsed) First run can load MLX weights; this is still working.
Buffered 1.3 MB WAV for batch 1/1; splitting 3 cached segments
Playing generated audio
```

Before batching, the same three-section shape made three sequential `/v1/audio/speech` calls and took about `89s` to reach playback in the previous V31 smoke. This run reached playback with one speech call in about `66.6s`. The remaining time is Voxtral generation cost, not the browser issuing avoidable extra calls.

Artifacts:

- `evidence/2026-05-24-v31-p0-batched-loading-browser-smoke.png`
- `evidence/2026-05-24-v31-p0-batched-loading-browser-smoke.wav`

## Validation

Canonical checkout:

```text
node --check browser/static/readaloud.js
python3 -m unittest tests.test_browser_server
Ran 39 tests in 6.751s
OK
bash -n scripts/install-voxtral-launchagent.sh
bash -n scripts/smoke-local-transcription.sh
git diff --check
```

Worktree checkout:

```text
node --check browser/static/readaloud.js
python3 -m unittest tests.test_browser_server
Ran 30 tests in 6.701s
OK
bash -n scripts/install-voxtral-launchagent.sh
bash -n scripts/smoke-local-transcription.sh
git diff --check
```
