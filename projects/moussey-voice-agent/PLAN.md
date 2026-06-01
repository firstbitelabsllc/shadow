# Moussey Voice Agent — Live Agentic Voice Chat for Leo's Fleet

> **Parent plan:** `~/Development/vidux/projects/agentic-command-center/PLAN.md` — this is **Phase 1 / sub-project #3** of the mega-goal. Voice is ONE input modality alongside text chat, vidux-browse-action, iMessage-bridge, Gmail-bridge, etc. All siblings share the brain dispatcher + intent router from Phase 0.

## Sub-project mega-goal

**Speak to one Mac. Command the whole fleet with full agentic capability (every skill, every MCP). Hear streamed audio back. Interrupt at any time.**

ChatGPT-voice-mode-equivalent **agentic** voice interface for Leo's home Mac fleet (Studio, M4 Pro, Nicole MBA). Hold a button (later: wake word), speak, the chosen brain (Claude Code / Codex / local Ollama) executes with **full skill+MCP access** — iMessage, Gmail x3, computer-use, nia, /vidux, /moussey, /captain, /machine-sync, /snowcubes, every Leo skill — Voxtral TTS streams the response back, full barge-in interruption.

LAN-only. Personal use. Built on existing fleet infrastructure that already ships and is proven:

- Voxtral 4B-TTS LaunchAgent on :8000 (per-Mac, verified 2026-05-01)
- Cross-Mac Claude YOLO trigger on :4321/api/lan/trigger-claude (bidirectional M4↔M1 confirmed 2026-05-22)
- Moussey GUI dashboard at :4321/triggers with peer pills, kill switch, audit feed
- HMAC auth, rate limit (3/min, 10/hr), kill switch, audit log in lib/lan-trigger-auth.ts
- MCP toolkit inherited by trigger-claude spawned sessions (subscription billing, apiKeySource: "none")
- /vidux project plan discipline with atomic-claim two-agent coordination

The killer use case: Leo says *"hey check my Gmail for amazon shipments this week and dump the receipts into the Snowcubes tracker"* → mic → STT → trigger-claude with full MCP toolkit → Voxtral reads the structured response back while Claude is actually doing the work in parallel.

## Architecture (LOCKED 2026-05-22)

```
┌─────────────────────────────────────────────────────────────────┐
│ Browser tab on :4321/voice (any Mac, iPhone, iPad on home WiFi) │
│                                                                  │
│   mic → MediaRecorder (opus) ─┐                                  │
│                                ├─▶ WebSocket :4321/api/voice    │
│   speaker ◀── AudioContext ◀──┘                                 │
└──────────────────────────────────┬──────────────────────────────┘
                                   │ ws
┌──────────────────────────────────▼──────────────────────────────┐
│ moussey :4321 — voice orchestrator (this project)               │
│                                                                  │
│   /api/voice (WebSocket)                                        │
│   │                                                              │
│   ├─ inbound: opus chunks ─▶ STT (mlx-whisper) ─▶ text          │
│   │                                                              │
│   ├─ brain dispatcher: text ─▶ {claude|codex|local}             │
│   │   • claude: forward to /api/lan/trigger-claude (SSE) ←PROVEN│
│   │   • codex:  exec ~/.local/bin/codex with prompt (SSE)       │
│   │   • local:  POST localhost:11434 (Ollama, SSE)              │
│   │                                                              │
│   └─ outbound: streamed text ─▶ TTS (Voxtral :8000) ─▶ audio    │
│                                  chunks ─▶ WebSocket ─▶ browser │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                  ▲                              ▲
                  │ HTTP loopback                │ HTTP loopback
┌─────────────────┴────────────────┐  ┌──────────┴───────────────┐
│ Cross-Mac trigger :4321          │  │ Voxtral mlx-audio :8000  │
│ /api/lan/trigger-claude          │  │ POST /v1/audio/speech    │
│ (already shipped, proven)        │  │ (already shipped, proven)│
└──────────────────────────────────┘  └──────────────────────────┘
                  │
                  ▼ spawns
┌──────────────────────────────────┐
│ claude -p --model opus           │
│   --output-format json           │
│   --permission-mode              │
│   bypassPermissions              │
│                                  │
│ FULL MCP ACCESS (auto-inherits): │
│ • imessage (read history)        │
│ • gmail x3 (inbox, fbl, personal)│
│ • computer-use (native apps)     │
│ • nia (indexed search, 17 tools) │
│ • figma                          │
│ • all bundled Claude Code tools  │
│ • every Leo skill (see /captain) │
└──────────────────────────────────┘
```

## What's already shipped (reuse, do not rebuild)

| Component | Status | Where | Proven |
|---|---|---|---|
| Voxtral 4B-TTS server | LIVE per-Mac | LaunchAgent `com.leokwan.mlx-audio` :8000 | M4 Pro 2026-05-01 |
| Cross-Mac Claude trigger | LIVE bidirectional | moussey `:4321/api/lan/trigger-claude` | M4↔M1 2026-05-22 |
| Moussey GUI Triggers page | LIVE | `:4321/triggers` (AI Bridge tile) | 2026-05-22 |
| HMAC auth + kill switch + rate limit | LIVE | `moussey/lib/lan-trigger-auth.ts` | shipped 2026-05-22 |
| Audit log + cost capture | LIVE | `~/.moussey/claude-triggers.jsonl` | per-trigger cost cents |
| moussey-trigger-doctor + watchdog | LIVE | 15-min self-heal LaunchAgent | M4 Pro 2026-05-22 |
| MCP toolkit | LIVE | `~/.claude/.config.json` — inherited by spawned trigger-claude | every session-init |
| /vidux project discipline | LIVE | this PLAN.md format | every vidux project |

## What's missing (this project ships it)

| Component | Phase | Owner suggestion |
|---|---|---|
| Browser mic capture UI | P1 | Claude (JS/HTML) |
| Local Whisper STT install | P1 | Claude (mlx-whisper) |
| WebSocket relay route `/api/voice` | P2 | Codex (TS/Node) |
| Brain dispatcher (claude/codex/local) | P2 | Codex (TS/Node) |
| Streaming TTS playback (sentence chunked) | P3 | Claude (audio scheduling) |
| Word-highlight migration during playback | P3 | Claude (reuse readaloud-addon M13/M16) |
| VAD + barge-in interruption | P4 | Codex (ONNX runtime in browser + server abort) |
| Wake word "hey moussey" | P5 | deferred |
| Conversation history + memory | P5 | deferred |

## Phases (with task atoms)

### Phase 1 — Local Whisper STT + browser mic capture (foundation)

- [completed] [owner: codex] **V1**: Install mlx-whisper on this Mac (`Leos-Mac-Studio-10442.local`, arm64). `uv tool install mlx-whisper`. Smoke test a 3-5 second WAV, then document transcript, warm RTF, CLI process latency, RAM, and buffering semantics in evidence. Cross-Mac: separately install on M4 Pro after the Studio path is proven. [Done: 2026-05-24; evidence: `evidence/2026-05-24-v1-stt-install-smoke.md`]
- [pending] **V2**: Browser `/voice` page (new route in moussey/app/voice/page.tsx). Button: hold-to-talk OR click-to-toggle. MediaRecorder captures opus codec at 48kHz mono. On release, posts opus blob to `POST /api/voice/transcribe`. Show transcript in chat-style bubble. Reuse the dark `code-block` style from /triggers page.
- [pending] **V3**: `POST /api/voice/transcribe` route in moussey. Receives opus blob, transcodes to 16kHz WAV via ffmpeg (system bin, no npm wrapper needed), spawns the `mlx_whisper` subprocess for v0, parses JSON output, returns `{text, durationMs, modelLoadMs}`. Audit log entry to `~/.moussey/voice-sessions.jsonl`. If per-request CLI latency feels too buffered, upgrade V3 to a persistent local STT worker that keeps the model loaded.
- **GATE 1**: Hold button → say "hello moussey" → see transcript appear in browser within 3s end-to-end. Evidence: screenshot + JSONL entry.

### Phase 2 — Brain dispatcher (route transcript to LLM, return text)

- [pending] **V4**: Brain dispatcher in `moussey/lib/voice-brain.ts`. Three provider implementations behind a common `AsyncIterable<string>` interface:
  - `claude`: POST to local `/api/lan/trigger-claude` with peer=Self (loopback HMAC-signed), parse SSE, yield text chunks.
  - `codex`: spawn `~/.local/bin/codex exec --model gpt-5.4 -` piping prompt to stdin, parse stdout, yield text chunks.
  - `local`: POST to `http://localhost:11434/api/generate` with model from env (default `qwen2.5:14b`), parse JSONL stream, yield text chunks.
- [pending] **V5**: `POST /api/voice/ask` route (SSE response). Body: `{transcript, provider}`. Calls the dispatcher, streams text chunks as SSE `event: chunk\ndata: {...}\n\n`. Final event: `event: complete\ndata: {totalText, durationMs, costCents}\n\n`. Audit log entry per request.
- [pending] **V6**: UI `/voice` page wires V2 → V5: after transcript appears, immediately POST to /ask with selected provider, render streaming response in second chat bubble character-by-character. Provider dropdown above the mic button (default: claude).
- **GATE 2**: Full TEXT round-trip. Speak → see transcript → see Claude streaming text response. Cost shown per turn. Switch provider, ask same question, compare outputs. Evidence: screenshots of all three providers responding to "what's 47×23".

### Phase 3 — Streaming TTS playback

- [pending] **V7**: Sentence chunker (port from voxtral-reader-addon `readaloud.js` ~320-char boundary logic). As streaming text arrives, group into sentences; emit each completed sentence to the TTS queue.
- [pending] **V8**: TTS playback queue. Per sentence: POST Voxtral `:8765/v1/audio/speech` with `voice=cheerful_female`, decode WAV via `AudioContext.decodeAudioData`, schedule on a contiguous AudioContext queue (same pattern as the proven voxtral-reader-addon footer). Do not use `:8000 /v1/models` as readiness unless speech playback is separately proven.
- [pending] **V9**: Word-highlight migration during playback. Reuse the M13 heuristic from voxtral-reader-addon: `audioBuf.duration / wordCount` per-word `setTimeout`. Highlight migrates across the response bubble.
- [pending] **V9b**: localStorage cache reuse from voxtral-reader-addon M16 — if the same response text + voice + speed was already synthesized, replay instantly. (Probably rare for voice agent since responses are unique, but free win.)
- **GATE 3**: Full VOICE round-trip. Speak → transcript → streaming text → TTS speaks the response while text is still arriving. Word highlight migrates with audio. Provider switchable.

### Phase 4 — VAD + barge-in interruption

- [pending] **V10**: silero-vad ONNX in browser via `onnxruntime-web`. Continuously monitor mic input even while TTS is playing. VAD threshold tuned to ignore TTS playback bleed-through (the TTS audio is going to the SPEAKER not the mic, but consumer Mac mics pick up speaker output — investigate echo cancellation via `getUserMedia({audio: {echoCancellation: true}})`).
- [pending] **V11**: Client-side barge-in. When VAD fires during TTS playback: `audioContext.suspend()` immediately, abort any in-flight Voxtral fetches via AbortController, close the AudioContext, start fresh turn (new MediaRecorder).
- [pending] **V12**: Server-side abort. New WebSocket message kind `{type: "abort", turnId}`. Server kills the in-flight brain stream: trigger-claude → SIGTERM the child claude process by PID; codex → SIGTERM the subprocess; ollama → fetch().abort().
- **GATE 4**: Mid-sentence barge-in works cleanly. Leo says "tell me a long story about Pickles" → Voxtral starts reading → Leo says "actually no, what's the weather" → first response stops, new turn starts within 500ms.

### Phase 5 — Wake word + conversation history (deferred)

- [pending] **V13**: openwakeword via ONNX in browser. "hey moussey" trigger. Replaces hold-to-talk with always-listening.
- [pending] **V14**: Per-session conversation history persisted to `~/.moussey/voice-sessions/<sessionId>.jsonl`. Replayable in UI.
- [pending] **V15**: Continuation prompts: "and also check ..." reuses prior turn's context by prepending last 3 turns to the brain prompt.

## Two-agent coordination

Same protocol as voxtral-reader-addon. Atomic claim: edit `[pending]` → `[in_progress] [owner: <claude|codex>]`, `git add PLAN.md && git commit -m "voice-agent: claim <V#>" && git push`. First-pusher wins; second-pusher pulls + picks a different unblocked task.

**Strength alignment:**
- **Claude (this agent on M4 Pro)**: JS/HTML/CSS UI, browser audio scheduling, MediaRecorder + AudioContext, MCP integration smoke tests, plan curation, evidence screenshots.
- **Codex**: TypeScript moussey server routes (Next.js 16 App Router), Python subprocess management (mlx-whisper), WebSocket relays, ONNX runtime integration, brain dispatcher with provider abstraction.

**Suggested first claims:**
- Claude: V1 (install mlx-whisper on M4 Pro + smoke), V2 (browser mic UI).
- Codex: V3 (server transcribe route — Python+TS bridge), V4 (brain dispatcher abstraction).

V3 + V4 can ship in parallel with V1 + V2 since their interfaces are locked above.

## Decision Log

- [DIRECTION] [2026-05-22] WebSocket over WebRTC for v1. Reason: LAN-only + push-to-talk doesn't need WebRTC's TURN/STUN/jitter complexity. Plain WebSocket + MediaRecorder API ships faster. Reconsider if always-on listening (P4+) reveals jitter or echo issues.
- [DIRECTION] [2026-05-22] Brain dispatcher with three providers, not one. Claude is the proven path (trigger-claude shipped, full MCP access, subscription billing). Codex for cost-sensitive heavy reads (Codex is unlimited per /captain). Local Ollama for offline/private prompts where MCP isn't needed.
- [DIRECTION] [2026-05-22] Reuse trigger-claude as the Claude brain. Already has HMAC auth, rate limit, kill switch, audit log, MCP toolkit, subscription billing (apiKeySource: "none"). No need to fork.
- [DIRECTION] [2026-05-22] Voxtral 4B-TTS (now installed as `com.leokwan.vidux-voxtral-mlx` on `127.0.0.1:8765`) as v1 TTS. CC-BY-NC-4.0 personal-use OK. If commercial Snowcubes voice ever needed, swap to bundled Kokoro Apache-2.0 fallback (already in voxtral-reader-addon as readaloud-kokoro.js).
- [DIRECTION] [2026-05-22] Whisper for STT, not Voxtral STT. mlx-whisper is more mature, smaller (~140 MB base.en vs 8 GB Voxtral), faster (RTF <0.1× on M4), Apache-2.0. Voxtral STT exists in the 8GB bundle but the marginal benefit isn't worth the GPU cycles when Whisper is excellent.
- [DIRECTION] [2026-05-22] Default brain = Claude (trigger-claude). User can switch via UI dropdown. Reason: only Claude has the full MCP skill toolkit wired up; codex + local are degraded modes until we add MCP shims for them. Once Codex has nia + iMessage + Gmail integration parity, default becomes "auto-pick cheapest path."
- [DIRECTION] [2026-05-22] Voice orchestrator lives in moussey (TypeScript Next.js :4321), not vidux-browse (Python static-file :7191). Reason: moussey already runs HMAC auth, audit log, kill switch, rate limit, and SSE streaming — all of which voice needs. vidux-browse is intentionally thin.
- [DIRECTION] [2026-05-22] Each Mac runs its own voice orchestrator. Browser tab connects to whichever Mac's :4321 the user opened. No cross-Mac voice routing in v1. Cross-Mac IS available — the user opens M4 Pro's :4321/voice and asks Claude to do something; Claude (via trigger-claude) can already trigger other Macs' Claude sessions for sub-tasks. The voice layer just talks to one Mac.
- [HARD-NEVER] LAN-only. No tunnel, no public DNS, no port forward. Same posture as moussey itself.
- [HARD-NEVER] Voice transcripts and brain responses must NOT travel via Moussey Ping or any cross-Mac write endpoint. Audit log stays in `~/.moussey/voice-sessions.jsonl`, local-only.
- [HARD-NEVER] No commercial-property voice (Snowcubes / Resplit / StrongYes) using Voxtral. License inherited from voxtral-reader-addon project.
- [HARD-NEVER] No always-on remote-mic listening with `bypassPermissions` Claude active. v1 ships push-to-talk only. P4 wake-word ships only after barge-in + clear visible state.

## Claims board (live — claim atomically and push)

| Task | Status | Owner | Blocking | Updated |
|---|---|---|---|---|
| V1: mlx-whisper install + smoke (Studio) | [completed] | codex | nothing | 2026-05-24 |
| V2: Browser /voice mic UI | [pending] | — | nothing | 2026-05-22 |
| V3: /api/voice/transcribe route | [pending] | — | V1 (Whisper bin must exist) | 2026-05-22 |
| V4: Brain dispatcher (3 providers) | [pending] | — | **ALL THREE PROVIDERS SHIPPED** — `moussey/lib/brain-dispatcher.ts` `dispatch()` is real. claude verified live (`✓ Hi 4441ms $0.20`). V4 = wire `dispatch({provider, sourceModality:"voice"})` into the WebSocket relay + map BrainChunks to SSE frames. No more abstraction work needed. | 2026-05-22 |
| V5: /api/voice/ask SSE route | [pending] | — | V4, intent-router R1 [completed] (use `route()` to pick provider when UI doesn't override) | 2026-05-22 |
| V6: /voice page wires V2→V5 | [pending] | — | V2, V5 | 2026-05-22 |
| V7: Sentence chunker | [pending] | — | nothing (port from readaloud.js) | 2026-05-22 |
| V8: TTS playback queue | [pending] | — | V7 | 2026-05-22 |
| V9: Word-highlight migration | [pending] | — | V8 | 2026-05-22 |
| V9b: localStorage TTS cache | [pending] | — | V8 | 2026-05-22 |
| V10: silero-vad ONNX in browser | [pending] | — | nothing | 2026-05-22 |
| V11: Client barge-in | [pending] | — | V10, V8 | 2026-05-22 |
| V12: Server abort | [pending] | — | V5 | 2026-05-22 |
| V13: Wake word | [pending] | — | Phase 4 ships | 2026-05-22 |
| V14: Conversation history | [pending] | — | Phase 4 ships | 2026-05-22 |
| V15: Continuation prompts | [pending] | — | V14 | 2026-05-22 |

## Related projects + skills

- **connect-the-fleet** (`~/Development/vidux/projects/connect-the-fleet/PLAN.md`) — **2026-05-26 unified fleet parent plan.** Owns Mac × surface matrix, authority-store canonicalization, and the moussey-mobile critical path. This voice-agent plan stays the canonical owner of audio init, but connect-the-fleet sequences when AudioContext gesture work lands relative to NET-1..NET-4 + Bundle C auth enforce flip.
- **voxtral-reader-addon** (`~/Development/vidux/projects/voxtral-reader-addon/PLAN.md`) — sibling project. Already shipped TTS for reading artifacts. This project consumes its Voxtral server. **Phase 4 P4-T1 of voxtral-reader-addon should be marked superseded by this project** once V11-V12 land.
- **moussey-mobile-operator** (`~/Development/vidux/projects/moussey-mobile-operator/PLAN.md`) — **sibling project (added 2026-05-24 per M-R65 reciprocal cross-link).** Mobile-operator's Phase 4 (M-E1/M-E2/M-E3) is the iOS-Safari `/chat` consumer for voice-agent's mic-capture (Phase 1) + Voxtral-TTS (Phase 3) + VAD/barge-in (Phase 4) pipeline. **Cross-plan contract per M-R82**: voice-agent V8 (Voxtral TTS SSE producer) MUST NOT emit audio_chunk frames until consumer signals `audioContext.state === 'running'` via first SSE frame ACK — iOS treats AudioContext as gesture-locked. Without ACK gate, first burst drops silently on iOS Safari. See `moussey-mobile-operator/PLAN.md` M-E2 task body for consumer-side AudioContext.resume() ritual in push-to-talk handler.
- **moussey** (`~/Development/ai-leo/skills/moussey/SKILL.md`) — the host. Cross-Mac trigger and dashboard live here.
- **vidux** (`/vidux`) — project discipline + browse + plan format.
- **captain** (`/captain`) — fleet sync. Will pick up the new voice route, mic permissions, mlx-whisper install when shipped.
- **machine-sync** — captures mlx-whisper as a new tool (`~/Development/ai/dotfiles/scripts/install-...`).

## Progress

- [2026-05-22] Plan created. Architecture locked. Phase 1 unblocked. Cross-Mac Claude trigger + Voxtral TTS already proven and live, so the surface area to ship is just the audio I/O glue (V1-V3), brain dispatcher (V4-V5), UI wiring (V6), TTS playback (V7-V9), barge-in (V10-V12). Phases 1-3 are MVP (push-to-talk voice agent). Phase 4 brings ChatGPT-voice-mode parity. Phase 5 is polish.
- [2026-05-24] V1 completed on `Leos-Mac-Studio-10442.local`. Installed `mlx-whisper` via `uv tool install mlx-whisper`; executable is `mlx_whisper`. Corrected the stale model name from `mlx-community/whisper-base.en` to `mlx-community/whisper-base.en-mlx`. Added `scripts/smoke-local-transcription.sh`, SETUP/SKILL instructions, and evidence at `evidence/2026-05-24-v1-stt-install-smoke.md`. Warm smoke: 3.35s WAV -> transcript in 2.11s best observed total, RTF 0.63, transcript `Hello local transcription smoke test number 472`; repeat CLI runs varied up to 3.85s because process/model-load overhead dominates. Note: per-request CLI buffers until the clip is decoded; UI must show recording/converting/model-load/transcribing states unless a persistent/streaming STT worker replaces the subprocess path.
- [2026-05-22] V4 interface NOW AVAILABLE — brain-dispatcher-shared Phase 0 stubs shipped (B1/B5/B6 [completed]) at `moussey/lib/brain-dispatcher.ts` + README + 6 passing tests. intent-router (R1/R2/R3 [completed]) at `moussey/lib/intent-router.ts`. V4 work can begin against the stable interface — wire `dispatch()` into the WebSocket relay; the three provider implementations (B2/B3/B4) ship as drop-in replacements for the `NotImplemented`-throwing stubs without changing the call site.
