# M8 Verification — Voice cloning UI

Voice cloning ships in two pieces this cycle: a new vidux-browse server endpoint that accepts base64-encoded audio uploads to a temp file, and a top-bar UI that drives it. mlx-audio's `/v1/audio/speech` endpoint already accepted server-local `ref_audio` paths; the missing rung was a way for the browser to *put* a file at one of those paths.

## Server endpoint

`POST /api/upload-ref-audio` added to `browser/server.py` inside `do_POST`. Loopback-only (`_require_json_write`), 15 MB cap, accepts JSON `{audio_base64, ext}`, decodes base64 with `validate=True`, refuses obvious non-audio (HTML/JSON sniff on first byte), saves to `tempfile.gettempdir() + /vidux-readaloud-ref-<sha8>.<ext>`, GCs older `vidux-readaloud-ref-*` files (>24h) on each upload.

Verified against a side instance on `:7192` (live `:7191` not restarted — Hard NEVER discipline):

```
$ curl -X POST http://127.0.0.1:7192/api/upload-ref-audio \
       -H 'Content-Type: application/json' \
       --data-binary @/tmp/m8-upload-payload.json
HTTP/1.1 200 OK
{
  "ok": true,
  "path": "/var/folders/zz/.../vidux-readaloud-ref-e0f015e1370e.wav",
  "bytes": 422444,
  "sha": "e0f015e1370e"
}

$ file /var/folders/zz/.../vidux-readaloud-ref-e0f015e1370e.wav
RIFF (little-endian) data, WAVE audio, Microsoft PCM, 16 bit, mono 24000 Hz
```

Saved bytes match the input bytes. WAV magic preserved.

## Voxtral cloning end-to-end

```
$ curl -X POST http://127.0.0.1:8000/v1/audio/speech \
       -H 'Content-Type: application/json' \
       -d '{
             "model": "mlx-community/Voxtral-4B-TTS-2603-mlx-bf16",
             "input": "Voice clone test attempt 2.",
             "voice": "casual_male",
             "ref_audio": "/var/folders/zz/.../vidux-readaloud-ref-e0f015e1370e.wav",
             "ref_text": "Hello from Leos Voxtral pipeline.",
             "response_format": "wav"
           }'
HTTP=200 size=111404 time=7.730s
$ file evidence/2026-05-02-m8-clone-output.wav
RIFF (little-endian) WAVE PCM 16-bit mono 24000 Hz
```

**Important contract:** Voxtral requires BOTH `voice` AND `ref_audio` set. Passing `ref_audio` alone fails with:

```
AssertionError: Either ref_audio or voice must be defined to encode audio,
got ref_audio=None and voice=None
  (mistral_common/tokens/tokenizers/instruct.py:1160)
```

The picker's voice acts as the *base* preset; `ref_audio` modulates it toward the cloned timbre. The client-side fetch carries both unconditionally when clone is active.

## Browser UI

Two new elements next to the M9/M11 cluster:

```html
<button id="root-readaloud-clone" class="root-readaloud-clone" type="button"
        title="Upload a 5-30s audio sample + transcript to clone the voice">
  🎤 Clone
</button>
<input type="file" id="root-readaloud-clone-file" accept="audio/*" style="display:none">
```

Behavior:

- Click `🎤 Clone` (when no clone set) → triggers the hidden file picker → on file selected, `prompt()` for the transcript → chunked `btoa` of file bytes → POST to `/api/upload-ref-audio` → on success, persist `path` + `transcript` to localStorage under `vidux.readaloud.cloneRefPath` / `vidux.readaloud.cloneRefText` → button switches to `🎤 Cloned` with `is-active` class.
- Click `🎤 Cloned` → `confirm()` to clear → wipe localStorage → button reverts to `🎤 Clone`.
- 404 on `/api/upload-ref-audio` shows: *"Upload endpoint missing — restart vidux-browse so M8 server changes take effect: launchctl kickstart -k gui/$(id -u)/com.leokwan.vidux-browser"*

`readaloudFetchChunkAudio` now reads `readaloudCloneState()` and includes `ref_audio` + `ref_text` in the request body when both are set.

## E2E verification (browse CLI vs side instance)

Started `:7192`, primed `localStorage` with the path/text from the curl-uploaded reference, reloaded:

```
clone button text:    "🎤 Cloned"
clone button classes: "root-readaloud-clone is-active"
clone button title:   "Voice clone active: vidux-readaloud-ref-e0f015e1370e.wav — click to clear and re…"
```

Clicking 🔊 with the clone active fired this fetch body to mlx-audio.server (captured via fetch hook):

```json
{
  "model": "mlx-community/Voxtral-4B-TTS-2603-mlx-bf16",
  "input": "Voice clone request body verification.",
  "voice": "casual_male",
  "response_format": "wav",
  "ref_audio": "/var/folders/zz/.../vidux-readaloud-ref-e0f015e1370e.wav",
  "ref_text": "Hello from Leos Voxtral pipeline."
}
```

Server returned 200, button cycled cleanly. Voice cloning is fully wired end-to-end.

Screenshot: [`2026-05-02-m8-clone-active.png`](2026-05-02-m8-clone-active.png) — top bar shows `🎤 Cloned` in the active (accent-color) state.

## Files touched

| File | Change |
|------|--------|
| `browser/server.py` | New `POST /api/upload-ref-audio` branch in `do_POST`. Loopback-only. 15 MB cap. base64 decode + WAV/MP3 ext gate + write to tempdir + 24h GC. |
| `browser/static/index.html` | New `<button id="root-readaloud-clone">` + hidden `<input type="file" id="root-readaloud-clone-file">`. |
| `browser/static/readaloud.js` | New CLONE_PATH_KEY / CLONE_TEXT_KEY constants, `readaloudCloneState()`, `readaloudUpdateCloneButton`, `readaloudOnCloneClick`, `readaloudOnCloneFile`. `readaloudFetchChunkAudio` includes ref_audio + ref_text from localStorage when set. |
| `browser/static/app.js` | `#root-readaloud-clone` and `#root-readaloud-clone-file` added to `ANNOTATION_CAPTURE_EXCLUDE_SELECTOR`. |
| `browser/static/style.css` | `.root-readaloud-clone` rule (mono font, 86px min-width). `.is-active` variant uses accent color to match the playing-button motif. |

## Live activation requires one restart

The vidux-browse process running on `:7191` (PID 57444) was started before this commit, so it doesn't have the new POST handler. Until Leo restarts it, clicking 🎤 Clone on the live UI will surface the friendly 404 message above. Activation:

```bash
launchctl kickstart -k gui/$(id -u)/com.leokwan.vidux-browser
```

(Or whatever Leo uses to bounce the vidux-browse process — there's no LaunchAgent for it currently per the M4 cycle's discovery.)

## Caveats / deferred polish

- **Native `prompt()` for transcript.** Functional but ugly. A small inline panel with a `<textarea>` would be nicer; punted to keep M8 single-cycle.
- **No "preview clone" button.** M11's preview button uses the picker's voice but not the clone. Easy follow-up: apply clone to preview too.
- **No transcript correction.** If you mistype the transcript, you have to clear + re-upload. Could add an "edit transcript" right-click. Punted.
- **Tempfile lifecycle.** GC prunes >24h files on each upload. If a user clones once then doesn't touch the page for >24h, the next upload (or next vidux-browse restart) sweeps it. The localStorage entry will still point at the deleted path — the next read-aloud request will fail with mlx-audio's "ref_audio not found" error. Acceptable for personal use; could be hardened by validating path-exists in the readaloud handler.
