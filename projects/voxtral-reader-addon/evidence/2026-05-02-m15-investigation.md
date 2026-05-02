# M15 Investigation — Voice clone + M11 preview button

Claimed M15 to fix what the M8 verification doc described as a real product gap:

> **From `2026-05-02-m8-verification.md` (Caveats / deferred polish):**
> No "preview clone" button. M11's preview button uses the picker's voice but not the clone. Easy follow-up: apply clone to preview too.

Investigation revealed the gap **no longer exists** — it was true at M8-doc-write time but became false later in the same cycle.

## Chronology that explains the stale claim

```
9300a36 vidux-browse(readaloud): M11 — voice preview button
291eaab vidux-browse(readaloud): M8 — voice cloning end-to-end
```

M11 shipped FIRST. At that time, `readaloudFetchChunkAudio` was the voice-only version, so M11's preview was correctly noted as "voice only, no clone."

M8 then shipped clone-awareness INTO `readaloudFetchChunkAudio` itself (lines 365-369):

```js
const clone = readaloudCloneState();
if (clone.path && clone.text) {
  body.ref_audio = clone.path;
  body.ref_text = clone.text;
}
```

Since `readaloudOnPreviewClick` calls `readaloudFetchChunkAudio(PREVIEW_TEXT, voice, signal)` (line 223), it inherited clone-awareness automatically. The M8 verification doc was authored from the M8-author's mental model of M11 as it existed BEFORE M8, not as it existed AFTER M8 shipped.

## End-to-end verification (browse CLI on isolated Chromium :7191)

1. Created a test ref audio via mlx-audio's own /v1/audio/speech (so we know the WAV is well-formed).
2. Uploaded it via the M8 endpoint:

```
$ curl -X POST http://127.0.0.1:7191/api/upload-ref-audio \
    -d '{"audio_base64": "<base64 of /tmp/m15-ref.wav>", "ext": "wav"}'
{"ok":true, "path":"/var/folders/zz/.../vidux-readaloud-ref-93736fbb5f30.wav",
 "bytes":199724, "sha":"93736fbb5f30"}
```

3. Primed localStorage in the browser:

```js
localStorage.setItem('vidux.readaloud.cloneRefPath', '/var/folders/zz/.../vidux-readaloud-ref-93736fbb5f30.wav');
localStorage.setItem('vidux.readaloud.cloneRefText', 'Hello this is a clone reference audio sample.');
```

4. Reloaded. Clone button text confirmed `🎤 Cloned` (clone state persisted + UI honored it).

5. Installed a fetch hook to capture outgoing bodies:

```js
window.__capturedBodies = [];
const origFetch = window.fetch;
window.fetch = function(...args) {
  if (args[1] && args[1].body) {
    try { window.__capturedBodies.push(JSON.parse(args[1].body)); } catch(_) {}
  }
  return origFetch.apply(this, args);
};
```

6. Clicked the `▶` preview button. Captured fetch body:

```json
{
  "model": "mlx-community/Voxtral-4B-TTS-2603-mlx-bf16",
  "input": "This is a sample of the selected voice.",
  "voice": "casual_male",
  "response_format": "wav",
  "speed": 1.25,
  "ref_audio": "/var/folders/zz/.../vidux-readaloud-ref-93736fbb5f30.wav",
  "ref_text": "Hello this is a clone reference audio sample."
}
```

All four clone-relevant fields are present:

- `voice: "casual_male"` — base preset (Voxtral requires this AND ref_audio per M8's `mistral_common` assertion at instruct.py:1160)
- `ref_audio` — the uploaded sample's server-local path
- `ref_text` — the transcript Leo provided at upload time
- `speed: 1.25` — M12 cadence (preview also benefits from speed-up)

mlx-audio returned 200, audio decoded + scheduled in the preview AudioContext, button cycled `▶ → … → ■ → ▶` cleanly.

## What this means

The M11 preview button has ALWAYS used the clone (since M8 shipped). Leo can:
- Pick a voice from the M9 dropdown
- Click 🎤 Clone, upload his own WAV + transcript
- Click ▶ — hears HIS voice (modulated by the picker preset) on the sample sentence
- Click 🔊 — hears HIS voice reading the actual plan content

No code change required. M15 is a documentation correction, not a bug fix.

## Cleanup

- `/tmp/m15-ref.wav` (input WAV) — deleted
- The uploaded `vidux-readaloud-ref-93736fbb5f30.wav` will be GC'd by the upload endpoint's 24h sweeper on the next upload (or on vidux-browse restart whichever sweeps first)
- `/tmp/m15-upload-resp.json` — deleted

## Process fix from this investigation

The M8 verification doc's "deferred polish" list should be marked obsolete for the preview-clone item. The other deferred items remain:
- Native `prompt()` for transcript (functional but ugly) — still real
- No "edit transcript" right-click — still real
- Tempfile lifecycle / 24h GC stale-pointer edge case — still real

Adding a brief note to that doc next cycle (not this one — bookkeeping commits without code change are prohibited per /vidux principle 5).
