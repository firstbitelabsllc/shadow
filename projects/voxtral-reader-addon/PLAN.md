# Voxtral Reader Add-on for vidux-browse

## Purpose

Ship a 🔊 "Read aloud" button in vidux-browse that reads the current artifact / PLAN.md aloud using **Mistral Voxtral 4B TTS running locally on Apple Silicon via mlx-audio**. vidux-browse is a thin HTTP client; mlx-audio.server (`localhost:8000`, OpenAI-compatible REST) owns model + GPU. Fully local, no cloud, no API billing. Leo's M-series Macs only.

The killer use case is hands-free consumption of agent output during walks / commutes / dog-walks. Personal use only — Voxtral 4B-TTS is CC-BY-NC-4.0 (Leo confirmed personal scope). Commercial Leo properties (Snowcubes, Resplit, StrongYes) MUST NOT use this — substitute Apple Premium voices or Apache-2.0 Kokoro for those.

**Two-agent coordination (2026-05-01).** Codex is joining this plan. Both agents (Claude + Codex) read PLAN.md, claim a `[pending]` task by setting it `[in_progress] [owner: <agent>]`, ship, then flip `[completed]`. Coordination rules in `## Two-Agent Coordination` below.

## Evidence

- [Source: shell verify 2026-05-01] `mlx-audio` installed via `uv tool install --with mlx-audio mlx-audio` → 5 binaries at `/Users/leokwan/.local/bin/`: `mlx_audio.server`, `mlx_audio.tts.generate`, `mlx_audio.stt.generate`, `mlx_audio.sts.generate`, `mlx_audio.convert`.
- [Source: WebFetch 2026-05-01 — github.com/Blaizzy/mlx-audio README] mlx-audio supports `mlx-community/Voxtral-4B-TTS-2603-mlx-bf16` natively. Other supported TTS: Kokoro, Qwen3-TTS, Higgs Audio v2, Chatterbox, OuteTTS, Spark, Dia, MeloTTS, MOSS-TTS, CSM, KugelAudio, LongCat-AudioDiT, Soprano, Ming Omni TTS. MIT license on the library itself.
- [Source: WebFetch 2026-05-01 — `mlx-community/Voxtral-4B-TTS-2603-mlx-bf16`] Confirmed: ~8GB MLX bf16 quantization, ungated public download, 9 languages, 20 voice presets. RTF 6.50× short / 6.32× long on Apple Silicon (faster than real-time). 1,362 downloads last month.
- [Source: WebFetch 2026-05-01 — mistralai/Voxtral-4B-TTS-2603 file tree] Original BF16 model has NO ONNX export, only `consolidated.safetensors` (8GB). This is why browser/WebGPU paths fail — Transformers.js needs ONNX, which doesn't exist.
- [Source: WebFetch 2026-05-01 — mistralai/Voxtral-Realtime-WebGPU Space] Browser-WebGPU Space exists but uses Voxtral-Mini-3B-2507 (audio understanding / ASR, wrong direction for read-aloud).
- [Source: observed] Leo (2026-05-01): "im happy to create huggingface account" + "thats totallly fine man im happy to create huggingface account" + "be absoletely sure voxtral can't be used" — drove the mlx-audio discovery this cycle.
- [Source: shell check 2026-05-01] vidux-browse running on `:7191` via Python http.server (`browser/server.py` PID 57444 owned by leokwan). LaunchAgent: `com.leokwan.vidux-browser`. Studio + M4 Pro both run their own.
- [Source: agent research cycle 1] vidux-browse code map — top-bar button slot at `static/index.html:17`, `ANNOTATION_CAPTURE_EXCLUDE_SELECTOR` at `static/app.js:106-114`. Existing `static/readaloud.js` (cycle 4 Kokoro pivot) gets rewritten as HTTP client.

## Constraints

- ALWAYS: Voxtral 4B-TTS via mlx-audio is the primary TTS path. Browser-side TTS (Kokoro Transformers.js) stays in repo as `readaloud-kokoro.js` (renamed from `readaloud.js`) for offline / lower-RAM machines. Default `readaloud.js` is the HTTP client.
- ALWAYS: mlx-audio server runs on `localhost:8000` (default port). vidux-browse calls `POST http://localhost:8000/v1/audio/speech` (OpenAI-compatible).
- ALWAYS: mlx-audio.server lives as a per-Mac LaunchAgent (`com.leokwan.mlx-audio`) so it auto-starts at login alongside vidux-browse.
- NEVER: Push the mlx-audio server to LAN/external. Loopback only — same discipline as vidux-browse's `:7191` default. Voxtral weights are NC-licensed and must not be served beyond Leo's personal devices.
- NEVER: Commercial Leo property (Snowcubes / Resplit / StrongYes) calls into mlx-audio Voxtral. License forbids it. Those use Web Speech API or Kokoro.
- NEVER: Bundle Voxtral weights with the vidux repo. They're ~8GB; lives at `~/.cache/huggingface/hub/models--mlx-community--Voxtral-4B-TTS-2603-mlx-bf16/`.
- NEVER: Ship a vidux-browse change that crashes the existing surface. Test reload + render before declaring [completed].

## Two-Agent Coordination

This plan is being executed by **Claude** (this agent) AND **Codex** (parallel agent). Coordination protocol:

1. **Atomic claim:** Before starting work on a `[pending]` task, edit the row to `[in_progress] [owner: <claude|codex>]` and commit immediately (`git add PLAN.md && git commit -m "vidux: claim <task>" && git push`). The push is the lock — first-pusher wins; second-pusher pulls + picks a different task.
2. **Read fresh:** Always `cd ~/Development/vidux && git pull --rebase` before reading PLAN.md. Stale state causes claim-collisions.
3. **Pick highest-priority unblocked task whose deps are met.** If two tasks are equally unblocked, prefer the one matching your strengths (Codex: Python/server work; Claude: vidux-browse JS + research/writing).
4. **Ship code BEFORE marking [completed].** Per vidux principle 5: only commit `PLAN.md → [completed]` alongside the actual code change. No bookkeeping-only commits.
5. **Conflict resolution:** If you pull and find another agent claimed your task, pick a different task from the queue. Don't argue.
6. **Hand-off:** When you finish a task that unblocks another agent's task, the unblocked task automatically becomes claimable (no DM needed). The plan file is the only state.
7. **Deadlock breakers:** If you've been blocked >2 cycles waiting on the other agent's claim, comment `[BLOCKED-CHECK: <date>]` in INBOX.md. The other agent picks up the comment on their next READ.

## Tasks

### Phase 1 — mlx-audio + vidux-browse integration (active)

- [completed] [owner: claude] M1: Smoke test mlx-audio Voxtral. Background task ran `mlx_audio.tts.generate --model mlx-community/Voxtral-4B-TTS-2603-mlx-bf16 --text "Hello from Leo's Voxtral pipeline..." --voice casual_male --file_prefix evidence/2026-05-01-mlx-voxtral-smoke --audio_format wav --verbose`. Downloaded ~8 GB weights to `~/.cache/huggingface/`. Synthesized 8.8s of mono 24 kHz speech in 10.98s (RTF 0.80×, peak 9.26 GB RAM). [Evidence: evidence/2026-05-01-mlx-voxtral-smoke_000.wav, evidence/2026-05-01-mlx-voxtral-smoke.log]
- [completed] [owner: claude] M2: Architecture decision lock. Locked: port 8000, endpoint `POST /v1/audio/speech` (OpenAI-compatible), CORS allowlist `http://localhost:7191` + `http://127.0.0.1:7191`, LaunchAgent `com.leokwan.mlx-audio` per Mac. Verified server starts (after adding 7 missing deps to the uv tool venv: `uvicorn`, `fastapi`, `python-multipart`, `webrtcvad`, `websockets`, `setuptools<81`, `mistral-common[audio]>=1.10.0`), `/openapi.json` reachable, `POST /v1/audio/speech` returns HTTP 200 with valid WAV in 13.3s cold-load. Full architecture + rejected alternatives in `evidence/2026-05-01-architecture.md`. [Evidence: evidence/2026-05-01-architecture.md, evidence/2026-05-01-m2-curl-test.wav]
- [in_progress] [owner: claude] M3: Rewrite `browser/static/readaloud.js` as HTTP client per locked architecture. Rename existing Kokoro implementation to `readaloud-kokoro.js` (offline fallback). New flow: button click → `fetch('http://127.0.0.1:8000/v1/audio/speech', { method: POST, body: JSON.stringify({ model: 'mlx-community/Voxtral-4B-TTS-2603-mlx-bf16', input: text, voice: 'casual_male', response_format: 'wav' }) })` → blob URL → `<audio>.play()`. Highlight active chunk via the existing `readaloudHighlightChunk()` pattern (chunk-level only — split text on sentence/paragraph boundaries client-side). Graceful fallback when mlx-audio.server is unreachable (display "🔊 Server offline — start mlx-audio LaunchAgent"). [Depends: M2] [ETA: 1.0h]
- [pending] M4: LaunchAgent for mlx-audio.server. Create `~/Library/LaunchAgents/com.leokwan.mlx-audio.plist` per the ProgramArguments block in `evidence/2026-05-01-architecture.md` §D4 (host=127.0.0.1, port=8000, allowed-origins=loopback-only, log-dir=~/Library/Logs). `RunAtLoad=true`, `KeepAlive=true`. Save plist to repo at `scripts/launchd/com.leokwan.mlx-audio.plist` for cross-Mac install. [Depends: M2] [ETA: 0.5h]
- [pending] M5: End-to-end smoke. Reload http://localhost:7191, click 🔊 on a real PLAN.md / artifact, verify audio plays + chunk highlights track. Capture `evidence/2026-05-01-m5-screenshot.png` showing a chunk highlighted mid-playback. Capture timing: button-click → first-audio latency. [Depends: M3, M4]
- [pending] M6: Update `~/Development/ai/skills/vidux/SKILL.md` Browser block — replace the cycle-1 "Read-aloud add-on (Voxtral, optional)" subsection with the corrected mlx-audio architecture. Document: prereq is mlx-audio + LaunchAgent, vidux-browse is the HTTP client, port 8000 default, license is CC-BY-NC-4.0 (personal-only). [Depends: M2] [ETA: 0.5h] [Note: parallel with M3, M4]
- [pending] M7: Update `~/Development/ai/skills/moussey/SKILL.md` "Voxtral Reader add-on (optional)" section — replace browser-only install steps with: `pip install mlx-audio` → first run downloads 8GB → `launchctl load ~/Library/LaunchAgents/com.leokwan.mlx-audio.plist` → reload vidux-browse. Per-Mac (Studio + M4 Pro both need install). [Depends: M2] [ETA: 0.3h] [Note: parallel with M3, M4]

### Phase 2 — Polish (deferred until Phase 1 ships)

- [blocked] M8: Voice cloning UI. mlx-audio supports `--ref_audio` for several models (verify Voxtral). UI: file picker accepts 5-30s audio sample, sent as form-data to `/v1/audio/speech`. [Blocker: M5 ships]
- [blocked] M9: Voice picker. 20 Voxtral presets exist (`casual_male`, etc.) — sidebar dropdown to pick. [Blocker: M5 ships]
- [blocked] M10: True per-word highlight via mlx-audio streaming events. Currently chunk-level only. Investigate whether mlx-audio.server emits per-word timing in the SSE stream. [Blocker: M5 ships]

### Phase 3 — Cross-machine sync (deferred)

- [blocked] X1: Verify on Studio. Repeat M1+M4 install. Document any per-machine gotchas (M1 vs M4 Pro RAM, MLX version differences). [Blocker: M5 ships]
- [blocked] X2: iOS reader (Phase 3 of original plan). Calls the same Mac mlx-audio server when iPhone is on home Wi-Fi. SwiftUI app. AVAudioPlayer + lock-screen controls. [Blocker: X1 ships]

### Phase 4 — Full-duplex voice chat (long-term)

- [blocked] P4-T1: Full voice loop = STT (whisper.cpp / Voxtral-Mini-3B-ASR via same mlx-audio.server) + VAD (silero-vad on-device) + Claude API + TTS (Voxtral via this same mlx-audio.server). Sub-300ms latency target. [Blocker: Phase 3 ships AND multi-week budget approved]

### Archive — Browser TTS path (deferred per PIVOT-3)

- [completed] V1-V6: Cycle 1-4 work shipped the in-browser button + Kokoro-via-Transformers.js. Code is at `browser/static/readaloud.js` (current Kokoro implementation). Will be renamed `readaloud-kokoro.js` in M3 as the offline-fallback path. NOT deleted — useful when mlx-audio.server isn't running, or for machines with insufficient RAM for 8GB Voxtral weights.
- [completed] D1, D2: Cycle 1 docs in vidux + moussey SKILL.md. Will be REWRITTEN in M6, M7 to reflect mlx-audio architecture.

## Decision Log

- [DIRECTION] [2026-05-01] mlx-audio + Voxtral 4B-TTS over browser-WebGPU TTS. Reason: Voxtral 4B-TTS has no ONNX export (only safetensors); the browser-runnable Voxtral is Mini-3B (ASR, wrong direction). mlx-audio is the canonical Apple-Silicon-native path that actually exposes Voxtral 4B for inference. RTF 6.5× on M-series.
- [DIRECTION] [2026-05-01] Architecture: vidux-browse → HTTP → mlx-audio.server. Reason: separation of concerns. vidux-browse stays a thin static-file server; the heavy GPU+model state lives in a dedicated Python process. Allows other tools (CLI, future iOS Wi-Fi caller, vidux-leo overlays) to use the same TTS service without re-implementing.
- [DIRECTION] [2026-05-01] Personal use only — CC-BY-NC-4.0 inherited from Voxtral weights. Vidux + leojkwan.com personal site = OK. Snowcubes / Resplit / StrongYes = NOT OK (use Web Speech API or Apache-2.0 Kokoro).
- [DIRECTION] [2026-05-01] LaunchAgent for mlx-audio.server, mirroring `com.leokwan.vidux-browser`. Reason: Leo's Macs already follow the LaunchAgent pattern for local services; one more is consistent.
- [PIVOT] [2026-05-01 cycle 4] Voxtral 4B-TTS browser → Kokoro 82M browser. Trigger: 404 on `mistralai/Voxtral-4B-TTS-2603/resolve/main/config.json`. Root cause: I conflated Voxtral-4B-TTS (no ONNX) with Voxtral-Mini-3B (has ONNX). **Reverted by PIVOT-3.**
- [PIVOT-3] [2026-05-01 cycle 5+] Kokoro browser → mlx-audio Voxtral local server. Trigger: Leo's "be absolutely sure voxtral can't be used" pushed me to find `mlx-audio` (Blaizzy), which DOES support Voxtral 4B-TTS via the mlx-community fp16 conversion. Architecture changes from in-browser inference to localhost HTTP, but quality goes from Kokoro 82M → real Voxtral 4B (3-4× the params, native voice cloning, 20 presets). Kokoro code retained as offline fallback.
- [DELETION] [2026-05-01] Cron job `f2d150cf` (10-min Kokoro debug loop) deleted alongside PIVOT-3. New cron will fire after M5 ships and the architecture is verified end-to-end.

## Progress

- [2026-05-01] Plan created (cycle 1). Phase 0 = Voxtral quality verdict via WebGPU Space.
- [2026-05-01] Cycle 2: V1-V6 shipped — 🔊 button + lazy-load + chunk highlight. Code-level done; runtime verification pending Leo's first click.
- [2026-05-01] Cycle 3: idle on V0 verdict.
- [2026-05-01] Cycle 4: Leo's first click → 404 on `Voxtral-4B-TTS-2603/config.json`. PIVOT to Kokoro 82M browser-runtime via kokoro-js@1.2.0. Apache 2.0 license bonus.
- [2026-05-01] Cycle 5+: Leo invoked /effort max + /nia, demanded "be absolutely sure voxtral can't be used." Found `mlx-audio` library (Blaizzy/MIT) that supports `mlx-community/Voxtral-4B-TTS-2603-mlx-bf16` natively on Apple Silicon, exposes OpenAI-compatible REST server. PIVOT-3: Kokoro browser → mlx-audio Voxtral local server. mlx-audio installed (`uv tool install`). Smoke test running in background (downloads ~8GB Voxtral weights, then synthesizes). Plan rewritten with M1-M7 task atoms + Two-Agent Coordination protocol for Codex parallelism. Cron `f2d150cf` deleted. **Next: smoke test result determines whether to ship M2-M7 or pivot again.**
- [2026-05-01 23:16] M1 [completed]. Smoke test ran with mistral-common 1.11.1 (force-upgraded for AudioConfig). 8.8s of mono 24 kHz speech in 10.98s on M4 Pro (RTF 0.80×, peak 9.26 GB RAM). Output: `evidence/2026-05-01-mlx-voxtral-smoke_000.wav`. Voxtral path confirmed on Apple Silicon end-to-end.
- [2026-05-01 23:22] M2 [completed]. Architecture lock shipped at `evidence/2026-05-01-architecture.md`. Locked port 8000, OpenAI-compatible `POST /v1/audio/speech`, CORS allowlist `localhost:7191` + `127.0.0.1:7191`, LaunchAgent `com.leokwan.mlx-audio`. Discovered + fixed: mlx-audio's PyPI metadata is missing 7 server-runtime deps (`uvicorn`, `fastapi`, `python-multipart`, `webrtcvad`, `websockets`, `setuptools<81`, `mistral-common[audio]>=1.10.0`). Curl-tested: HTTP 200, valid WAV, 13.3s cold-load. CORS preflight verified for `Origin: http://localhost:7191`. Dependency manifest will land verbatim in M7 install steps so this isn't repeated. Server now running in background (task `b31hares4`). **Next: M3 (vidux-browse readaloud.js HTTP-client rewrite) is unblocked.**
