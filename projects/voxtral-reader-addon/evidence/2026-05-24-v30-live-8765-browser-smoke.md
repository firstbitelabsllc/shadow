# V30 Live 8765 Browser Smoke

Date: 2026-05-24
Host: `Leos-Mac-Studio-10442.local`
Live browser: `http://127.0.0.1:7191`
TTS runtime: `com.leokwan.vidux-voxtral-mlx` on `127.0.0.1:8765`

## Why this exists

Leo's screenshot showed the footer still saying the server was offline. The
first attempted repair over-trusted `com.leokwan.mlx-audio` on `127.0.0.1:8000`
because `/v1/models` answered, but speech was not actually proven. Direct and
browser speech requests against 8000 could hang or fail after headers.

The active browser read-aloud path is therefore the proven redseaplume script
server:

```bash
browser/scripts/start-voxtral-mlx-server.sh
```

For this Mac, that script is now installed as:

```bash
~/Library/LaunchAgents/com.leokwan.vidux-voxtral-mlx.plist
```

## Runtime checks

Health after LaunchAgent install:

```text
GET http://127.0.0.1:8765/health
ok=true
model=redseaplume/Voxtral-4B-TTS-2603-MLX-4bit
loaded=true
```

Direct speech after LaunchAgent install:

```text
POST http://127.0.0.1:8765/v1/audio/speech
200 48.999524 334124 audio/wav
```

The ~49s direct smoke included first model load in the LaunchAgent process.

## Live browser proof

Playwright opened the live Vidux browser at `127.0.0.1:7191`, injected one
short `#md-body` paragraph into the app shell, and clicked the real footer
`#root-readaloud-toggle`. The browser posted to the installed 8765 server and
played the returned audio through the production footer player.

Observed browser state:

```json
{
  "response": {
    "url": "http://127.0.0.1:8765/v1/audio/speech",
    "status": 200,
    "contentType": "audio/wav"
  },
  "browserBlobBytes": 2027564,
  "engine": "MLX on",
  "status": "Playing generated audio",
  "button": "Stop",
  "command": "browser/scripts/start-voxtral-mlx-server.sh",
  "audio": {
    "currentTime": 8.14326,
    "duration": 21.12,
    "readyState": 4,
    "paused": false,
    "playbackRate": 1.12
  }
}
```

Saved artifacts:

- `evidence/2026-05-24-v30-launchagent-8765-browser-smoke.png`
- `evidence/2026-05-24-v30-launchagent-8765-browser-smoke.wav`
- `evidence/2026-05-24-v30-live-8765-browser-smoke.png`
- `evidence/2026-05-24-v30-live-8765-browser-smoke.wav`

The LaunchAgent browser WAV is a valid `audio/wav` file:

```text
1 channel, 48000 Hz, Int16
estimated duration: 21.120000 sec
audio bytes: 2027520
```

## App performance repair

The live `/api/plans` path was slow enough to make browser proof flaky during
deep links. Raw curl before caching took about 27s. After adding a short
server-side plan-discovery cache and restarting 7191:

```text
first  200 0.054457 3472605
second 200 0.023574 3472605
```

## Validation

```text
node --check browser/static/readaloud.js
python3 -m unittest tests.test_browser_server
git diff --check
```

Results:

- Worktree: 30 tests passed.
- Canonical live checkout: 39 tests passed.
- Live static asset contains only the 8765 script-server candidate for
  read-aloud.
- Playwright Chromium was installed with `npx playwright install chromium` so
  future local browser smoke tests can run on this Mac.
