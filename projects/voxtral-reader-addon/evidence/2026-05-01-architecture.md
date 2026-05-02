# Architecture Lock — 2026-05-01

Locks the runtime shape that M3 (vidux-browse client), M4 (LaunchAgent), M6 (vidux SKILL.md), and M7 (moussey SKILL.md) all build against. Any deviation from these decisions in downstream tasks must be justified with a Decision Log entry that supersedes this doc.

## Topology

```
┌────────────────────────────┐         ┌──────────────────────────────────┐
│  vidux-browse              │  HTTP   │  mlx-audio.server                │
│  Python http.server        │ ──────▶ │  uvicorn / FastAPI               │
│  127.0.0.1:7191            │  POST   │  127.0.0.1:8000                  │
│  static/readaloud.js       │ /v1/    │  loads model lazily on 1st req   │
│  (HTTP client, M3)         │ audio/  │  ~9.3 GB peak RAM, ~8 GB weights │
└────────────────────────────┘ speech  └──────────────────────────────────┘
                                                      │
                                                      ▼
                                       ~/.cache/huggingface/hub/
                                       models--mlx-community--
                                       Voxtral-4B-TTS-2603-mlx-bf16/
```

Two LaunchAgents per Mac (mirroring shape):

- `com.leokwan.vidux-browser` — already exists (PID 57444 today).
- `com.leokwan.mlx-audio` — M4 ships this. `RunAtLoad=true`, `KeepAlive=true`, log to `~/Library/Logs/mlx-audio.log`.

## Locked decisions

### D1 — Port = 8000

mlx-audio.server's default. Verified free on Leo's M4 Pro today (`lsof -nP -i:8000` returned empty before launch). vidux-browse already owns 7191; the two-port split keeps responsibilities clean.

Rejected: 7192 (sequential with vidux-browse). Reason: would force a `--port` flag in the LaunchAgent and diverge from upstream defaults. Fewer surprises is worth the non-sequential port.

### D2 — Endpoint = `POST /v1/audio/speech` (OpenAI-compatible)

Request schema (verified against `http://127.0.0.1:8000/openapi.json` 2026-05-01):

```jsonc
{
  "model": "mlx-community/Voxtral-4B-TTS-2603-mlx-bf16",  // required
  "input": "Hello world.",                                  // required
  "voice": "casual_male",                                   // 20 Voxtral presets available
  "speed": 1.0,
  "response_format": "wav",                                 // default "mp3"; pick wav for browser AudioContext
  "stream": false,                                          // M10 may flip true
  "streaming_interval": 2.0,                                // chunk seconds when stream=true
  "ref_audio": "",                                          // M8 voice cloning path (file or URL)
  "ref_text": "",                                           // M8 voice cloning paired transcript
  "temperature": 0.7,
  "top_p": 0.95,
  "top_k": 40,
  "repetition_penalty": 1.0,
  "max_tokens": 1200,
  "verbose": false
}
```

Response: binary audio body with `Content-Type: audio/wav` (or `audio/mpeg` when `response_format: "mp3"`).

Verification today (`evidence/2026-05-01-m2-curl-test.wav`):

```
HTTP=200 size=303404 time=13.292459s     # 5s of speech in 13.3s on first hit (cold model)
file: RIFF (little-endian) WAVE PCM 16-bit mono 24000 Hz
```

Subsequent requests (warm model) should land closer to the CLI smoke-test RTF of 0.80× (~10s synthesis for ~12s of audio).

Rejected: a custom `/api/readaloud` proxy on the vidux-browse Python process. Reason: makes vidux-browse responsible for the model lifecycle and re-implements what mlx-audio's FastAPI already gives us. The thin-client/thick-server split keeps both processes single-purpose.

### D3 — CORS allowlist = `http://localhost:7191` + `http://127.0.0.1:7191`

mlx-audio.server's `--allowed-origins` flag wires this. Preflight verified today:

```
> OPTIONS /v1/audio/speech  Origin: http://localhost:7191
< HTTP/1.1 200 OK
< access-control-allow-origin: http://localhost:7191
< access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
< access-control-allow-headers: content-type
```

LaunchAgent (M4) MUST pass both `http://localhost:7191` and `http://127.0.0.1:7191`. Operator-by-operator overrides (e.g. allowing `http://<mac-name>.local:7191` for Wi-Fi reading from iPhone) are encouraged when the use case appears, but the default ships loopback only.

Rejected: `--allowed-origins '*'`. Reason: Voxtral is CC-BY-NC-4.0; opening the server to any origin is a license + privacy footgun. Loopback default matches vidux-browse's posture.

### D4 — Server lifecycle = LaunchAgent `com.leokwan.mlx-audio` per Mac

Mirrors `com.leokwan.vidux-browser`. Default args (M4 will codify):

```
ProgramArguments:
  - /Users/leokwan/.local/bin/mlx_audio.server
  - --host=127.0.0.1
  - --port=8000
  - --allowed-origins=http://localhost:7191
  - --allowed-origins=http://127.0.0.1:7191
  - --log-dir=/Users/leokwan/Library/Logs
RunAtLoad: true
KeepAlive: true
StandardOutPath: /Users/leokwan/Library/Logs/mlx-audio.stdout.log
StandardErrorPath: /Users/leokwan/Library/Logs/mlx-audio.stderr.log
```

Memory/RAM caveat: peak ~9.3 GB during synthesis (verified M1). On a 16 GB Mac this is borderline; on Leo's 64 GB M4 Pro it's a non-issue. Studio (X1) install will need a re-verify of peak memory under whatever `--tts-max-batch-size` setting we land on.

### D5 — Dependency manifest (uv tool install)

mlx-audio's PyPI metadata is incomplete — running `uv tool install mlx-audio` alone leaves the `mlx_audio.server` binary unable to import. The minimal working install command (verified today, 5 install rounds to converge):

```bash
uv tool install --force \
  --with 'mlx-audio[tts]' \
  --with 'mistral-common[audio]>=1.10.0' \
  --with uvicorn \
  --with fastapi \
  --with python-multipart \
  --with webrtcvad \
  --with websockets \
  --with 'setuptools<81' \
  mlx-audio
```

Why each `--with`:

- `mlx-audio[tts]` — core TTS extra.
- `mistral-common[audio]>=1.10.0` — Voxtral 4B-TTS needs the AudioConfig added in 1.10. mlx-audio pins something older, hence the explicit floor.
- `uvicorn`, `fastapi`, `python-multipart` — server runtime; not in mlx-audio's deps.
- `webrtcvad` — imported at server startup even when not using realtime VAD; ImportError otherwise.
- `websockets` — `/v1/realtime` peer dep; imported eagerly.
- `setuptools<81` — pkg_resources was removed from setuptools 81 (2025-11). webrtcvad still imports it. Pin until webrtcvad ships a fix or we drop that import path.

This list goes verbatim into M7 (moussey SKILL.md install steps) so other operators don't repeat the 5-round dependency dance.

## What this unblocks

| Task | What it now has |
|------|-----------------|
| M3 (readaloud.js HTTP client) | Endpoint URL + JSON shape locked. Can write `fetch('http://127.0.0.1:8000/v1/audio/speech', { method: 'POST', body: JSON.stringify({ model, input, voice, response_format: 'wav' }) })` against this contract. |
| M4 (LaunchAgent) | ProgramArguments + log paths spelled out above. Plist is mechanical. |
| M5 (e2e smoke) | Has both ends of the contract — can drive the real flow. |
| M6 (vidux SKILL.md) | Architecture diagram + ports + license posture all sourced from this doc. |
| M7 (moussey SKILL.md) | Install command in §D5 is the body of the install section. |

## What stays open

- Streaming (`stream: true`) — M10 problem. Today the curl test used `stream: false` and got the whole WAV in one body. Streaming would let M3 start playback before synthesis finishes; not required for the MVP read-aloud.
- Voice cloning (`ref_audio`) — M8 problem. Endpoint exposes the field; UI piping is deferred.
- Multi-Mac LaunchAgent install — X1 problem. Same plist should work on Studio if RAM allows.
- Resilience when mlx-audio.server is down — M3 should fall back to either Web Speech API or the Kokoro `readaloud-kokoro.js` path (whichever proves least jarring). Pick during M3 implementation.

## Reproducibility

Every value above came from one of:

- `curl http://127.0.0.1:8000/openapi.json` — schema and required fields
- `curl -X OPTIONS http://127.0.0.1:8000/v1/audio/speech -H 'Origin: ...'` — CORS preflight
- `curl -X POST .../v1/audio/speech -d '{...}'` — saved at `evidence/2026-05-01-m2-curl-test.wav`
- M1 smoke log: `evidence/2026-05-01-mlx-voxtral-smoke.log`
