# Agentic Text Chat — Browser-Based Chat for Leo's Fleet

> **Parent plan:** `~/Development/vidux/projects/agentic-command-center/PLAN.md` — this is **Phase 2 / sub-project #4**. Sibling of moussey-voice-agent. Same brain dispatcher + intent router, no audio I/O — just text in / text out / markdown rendering.

## Purpose

The fastest UI to ship for the agentic command center. A browser chat page at `moussey :4321/chat` where Leo types prompts, picks a provider from a dropdown, and watches streaming responses render in chat-style bubbles with markdown + code blocks. Same MCP-toolkit coverage as voice-agent (since both share `dispatch()`).

**Why this matters even though Leo asked for voice:** text chat has NO audio pipeline complexity (no STT, no TTS, no AudioContext scheduling, no barge-in). It validates the brain dispatcher + intent router by exercising them end-to-end through real UI. When voice ships, the brain layer is already battle-tested.

It's also the right surface for tasks where voice is awkward — pasting a long error trace, dropping a code snippet, reviewing a 200-line response.

## Architecture (LOCKED 2026-05-22)

```
┌────────────────────────────────────────────────────────────────┐
│ Browser tab on :4321/chat (any Mac, iPhone, iPad on home WiFi) │
│                                                                  │
│   keyboard → <textarea> ───────┐                                │
│                                ├─▶ POST /api/chat/ask (SSE)     │
│   markdown ◀── chat bubble ◀───┘                                │
└──────────────────────────────────┬─────────────────────────────┘
                                   │ SSE
┌──────────────────────────────────▼─────────────────────────────┐
│ moussey :4321 — chat orchestrator (this project)                │
│                                                                  │
│   POST /api/chat/ask  (SSE response)                            │
│      ├─ route(intent)  → {provider, targetMac, reason}           │
│      ├─ dispatch(req)  → AsyncIterable<BrainChunk>               │
│      └─ stream chunks as `event: chunk\ndata: {...}\n\n`         │
│                                                                  │
│   GET /api/chat/sessions      list past sessions                │
│   GET /api/chat/sessions/:id  load history                      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                  │                              ▲
                  ▼ via brain-dispatcher         │
        (~/Development/moussey/lib/brain-dispatcher.ts)
```

## Phases

### Phase 1 — Single-turn MVP

- [pending] **T1**: `/chat` page in moussey/app/chat/page.tsx. Textarea + provider dropdown (claude / codex / local) + submit button + chat-bubble container. Reuse the dark code-block style from /triggers page.
- [pending] **T2**: `POST /api/chat/ask` route. Body: `{prompt, provider}`. Calls `route()` then `dispatch()` from brain-dispatcher. Streams chunks as SSE.
- [pending] **T3**: Client-side SSE parser. Appends `text` chunks to the active bubble character-by-character. `tool_use` chunks render as a small "🛠 using <tool>" indicator. `complete` event shows total cost + duration. `error` shows red with retry button.
- [pending] **T4**: Markdown rendering via the existing renderer used in vidux-browse (port the relevant CSS + parser if not already shared). Code blocks get syntax highlighting (existing `highlight.js` is fine).
- **GATE 1**: Type "what's 47 × 23" → submit → see "1081" stream in. Switch provider, same prompt, compare responses. Cost shown.

### Phase 2 — Multi-turn + history

- [pending] **T5**: Conversation history persisted per session to `~/.moussey/chat-sessions/<sessionId>.jsonl`. Each turn = `{ts, role, content, provider, costCents}`.
- [pending] **T6**: Continuation: send prior 3 turns as context when the user replies in the same thread. Stable session ID via cookie/localStorage.
- [pending] **T7**: Session list sidebar — `GET /api/chat/sessions` returns recent sessions. Click loads `GET /api/chat/sessions/:id`.
- **GATE 2**: Multi-turn conversation works; closing tab + reopening restores history.

### Phase 3 — Power features (deferred)

- [pending] **T8**: File drop into the textarea — attach a code snippet / image / PDF. Passes through to claude via MCP (read_file / vision).
- [pending] **T9**: Forked turns — "regenerate with different provider" without losing history.
- [pending] **T10**: Sharing — generate a read-only LAN URL for a specific session that Nicole MBA can open from her browser.

## Decision Log

- [DIRECTION] [2026-05-22] SSE over WebSocket. Reason: text chat is one-direction streaming (request → stream-of-chunks). WebSocket is overkill. SSE is one less moving part and natively supported by `fetch` + `EventSource` in browsers.
- [DIRECTION] [2026-05-22] No audio I/O ever. Voice agent owns the audio pipeline. Text chat stays text. Reuse markdown/code rendering; never reach for TTS/STT.
- [DIRECTION] [2026-05-22] Same `lib/brain-dispatcher.ts` and `lib/intent-router.ts` as voice-agent. Reason: validates the abstraction by having a second consumer. If text-chat needs something dispatcher doesn't expose, the gap is in the dispatcher, not the consumer.
- [DIRECTION] [2026-05-22] Session storage per-Mac at `~/.moussey/chat-sessions/`. Not synced across Macs in v1. Reason: cross-Mac sync requires conflict resolution + makes the audit log harder. Defer until a real need emerges. The cross-Mac brain dispatch (trigger-claude) STILL routes to peer Macs; only the session METADATA stays local.
- [HARD-NEVER] LAN-only. Same posture as voice-agent and moussey itself.
- [HARD-NEVER] No commercial-property text-chat surfacing (Snowcubes / Resplit / StrongYes) — same boundary as voice-agent. This is the personal command center.

## Claims board

| Task | Status | Owner | Blocking | Depends on | Updated |
|---|---|---|---|---|---|
| T1: /chat page UI | [pending] | — | T3, T4 | nothing | 2026-05-22 |
| T2: /api/chat/ask SSE route | [pending] | — | T3 | **brain-dispatcher B2 SHIPPED + verified live (`✓ Hi 4441ms $0.20`)** — just wire `dispatch({prompt, provider, metadata:{sourceModality:"text"}})` into the route + stream BrainChunks as SSE. Use intent-router `route()` to pick provider when UI doesn't override. | 2026-05-22 |
| T3: Client SSE parser + bubble append | [pending] | — | GATE 1 | T1, T2 | 2026-05-22 |
| T4: Markdown rendering | [pending] | — | (polish) | T3 | 2026-05-22 |
| T5: Session JSONL persistence | [pending] | — | T6 | T2 | 2026-05-22 |
| T6: Multi-turn continuation | [pending] | — | GATE 2 | T5 | 2026-05-22 |
| T7: Session list sidebar | [pending] | — | (polish) | T5 | 2026-05-22 |
| T8: File drop | [pending] | — | (Phase 3) | T1 | 2026-05-22 |
| T9: Provider re-fork | [pending] | — | (Phase 3) | T5 | 2026-05-22 |
| T10: LAN session sharing | [pending] | — | (Phase 3) | T7 | 2026-05-22 |

## Two-agent coordination

Same atomic-claim protocol as parent. **Recommended first claim: T1 (page UI) by Claude** — pure JSX/CSS, no server dependencies, can ship immediately. **T2 (server route) by Codex** — straightforward TS API route + SSE streaming, gates on `brain-dispatcher B2` shipping.

T1 + T2 can ship in parallel; T3 needs both to land before integration.

## Why ship text chat alongside voice (not after)

The two surfaces are intentionally siblings, not phases of the same product:

1. **Text chat validates the brain dispatcher abstraction.** A second consumer is the cheapest way to prove the interface is right. If text-chat needs to dispatch differently than voice-agent, the gap is real and the dispatcher needs to grow before BOTH consumers ship broken.
2. **Text is the right surface for some tasks.** Pasting a 200-line stack trace, attaching a screenshot, reading long agent output — voice is bad for all of these. Text chat covers what voice can't.
3. **No audio pipeline complexity.** Ships faster, fewer moving parts, more time-efficient validation of Phase 0.
4. **Different latency profile.** Voice has aggressive latency goals (sub-second first chunk). Text is allowed to take 5s for first chunk if the response is high-quality. This lets the brain dispatcher prove out at relaxed latency before voice tightens the screws.

## Progress

- [2026-05-22] Plan created. Architecture locked. Phase 0 stubs already shipped (brain-dispatcher B1+R1 [completed], 12 tests passing) so T2 is interface-ready as soon as brain-dispatcher B2 (claude provider) lands. T1 (page UI) is unblocked NOW since it only needs the textarea + SSE consumer pattern.
