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

- [completed] **T1**: `/chat` page in moussey/app/chat/page.tsx. Textarea + provider dropdown (claude / codex / local) + submit button + chat-bubble container. [Evidence: `GET http://127.0.0.1:4321/chat` returns 200; page defaults provider selector to `local (ollama)` as of 2026-05-24.]
- [completed] **T2**: `POST /api/chat/ask` route. Body: `{prompt, provider}`. Calls `route()` then `dispatch()` from brain-dispatcher. Streams chunks as SSE. [Evidence: live `POST /api/chat/ask` with `provider:"local"` streamed `meta` → `system_init` → text chunks → `complete` → `[DONE]`.]
- [completed] **T3**: Client-side SSE parser core. Appends `text` chunks to the active bubble, renders `tool_use`, shows duration/cost on `complete`, and marks `error` bubbles red. [Evidence: route smoke returned exact streamed text `local-ok` using the live LaunchAgent.]
- [completed] **T4**: Markdown rendering via a safe local renderer in `app/chat/page.tsx`: paragraphs, headings, bullets, inline code, links, fenced code blocks, and lightweight syntax coloring for common code languages. [Evidence: `npm run build` passes; Playwright snapshot at `http://127.0.0.1:4321/chat` renders the repaired chat shell with zero console errors.]
- [completed] **T4a**: Error-bubble retry/regenerate affordance. [Evidence: assistant error bubbles show a scoped `Retry` button that replays the prior user turn with the same provider/session.]
- **GATE 1**: Type "what's 47 × 23" → submit → see "1081" stream in. Switch provider, same prompt, compare responses. Cost shown. [2026-05-24 status: local provider passes via `qwen2.5:0.5b`; Claude provider reaches the CLI but is blocked by Studio Claude credentials returning an error SSE chunk: 401.]

### Phase 2 — Multi-turn + history

- [completed] **T5**: Conversation history persisted per session to `~/.moussey/chat-sessions/<sessionId>.jsonl`. Each turn records timestamp, role, content, provider, turn id, status, and optional cost/duration/exit metadata. [Evidence: live `codex-final-chat-smoke` session wrote user + assistant turns to JSONL and `GET /api/chat/sessions/codex-final-chat-smoke` returned both turns.]
- [completed] **T6**: Continuation: replies in the same thread include bounded recent context via `buildPromptWithRecentHistory()`. Stable session ID is held in `localStorage`.
- [completed] **T7**: Session list sidebar — `GET /api/chat/sessions` returns recent sessions. Click loads `GET /api/chat/sessions/:id`. [Evidence: Playwright snapshot shows the Sessions sidebar populated from persisted local sessions.]
- **GATE 2**: Passed for local text-chat MVP. Multi-turn session state is durable locally; closing/reopening restores via the sidebar/localStorage. Claude provider remains unavailable on Studio until CLI auth is repaired.

### Phase 3 — Power features (deferred)

- [completed] **T8**: File drop into the textarea — attach a code snippet / image / PDF. Files are persisted on the owner Mac under `~/.moussey/chat-attachments/<session>/<turn>/`, recorded in the JSONL user turn, and injected into the dispatched prompt as saved file paths plus text excerpts for text/code files. [Evidence: `POST /api/chat/ask` route test captured `notes.md` text in the local dispatch prompt and verified the stored file path; Playwright opened `/chat`, attached `moussey-ui-proof.md`, sent the turn, and the UI rendered the attachment chip with zero console warnings/errors.]
- [completed] **T9**: Forked turns — "regenerate with different provider" without losing history. Each assistant bubble can rerun the preceding user prompt through local Ollama, local Codex, this Mac's Claude when authenticated, or an accepting peer Mac's Opus route when `/api/lan/trigger-claude/feed` reports one. [Evidence: Playwright loaded `codex-final-chat-smoke`, clicked `Rerun`, and the same session advanced from 2 to 4 turns with a fresh `final-ok` local response; the bubble route chooser rendered `local fast` + `codex`, and target dropdown showed disabled non-accepting peers.]
- [completed] **T10**: Sharing — generate a read-only LAN URL for a specific session that Nicole MBA can open from her browser. [Evidence: `GET /api/chat/sessions/codex-final-chat-smoke/share` returned `http://leos-mac-studio-10442.local:4321/chat?session=codex-final-chat-smoke&readonly=1`; Playwright opened that URL and showed the loaded session with the composer/sidebar/rerun controls removed.]
- [pending] **T11**: Repair the local Claude provider auth on this Mac, then run a self-Claude attachment smoke that proves the saved attachment path can be inspected by Claude's file/vision tools. This is a credentials/runtime readiness task, not a chat UI/API blocker.
- [pending] **T12**: Chat-to-coding handoff. Let Leo turn the current chat prompt/session into a proposed `/coding` run or isolated coding lane. Execution is owned by `agentic-coding-workbench`; this row owns only the chat affordance and context payload.

## Decision Log

- [DIRECTION] [2026-05-22] SSE over WebSocket. Reason: text chat is one-direction streaming (request → stream-of-chunks). WebSocket is overkill. SSE is one less moving part and natively supported by `fetch` + `EventSource` in browsers.
- [DIRECTION] [2026-05-22] No audio I/O ever. Voice agent owns the audio pipeline. Text chat stays text. Reuse markdown/code rendering; never reach for TTS/STT.
- [DIRECTION] [2026-05-22] Same `lib/brain-dispatcher.ts` and `lib/intent-router.ts` as voice-agent. Reason: validates the abstraction by having a second consumer. If text-chat needs something dispatcher doesn't expose, the gap is in the dispatcher, not the consumer.
- [DIRECTION] [2026-05-22] Session storage per-Mac at `~/.moussey/chat-sessions/`. Not synced across Macs in v1. Reason: cross-Mac sync requires conflict resolution + makes the audit log harder. Defer until a real need emerges. The cross-Mac brain dispatch (trigger-claude) STILL routes to peer Macs; only the session METADATA stays local.
- [DIRECTION] [2026-05-24] Chat attachments are owner-Mac local in v1. Reason: this matches session JSONL locality and avoids cross-Mac file write bridges. Peer Opus routes receive the prompt/excerpt context, but a saved file path is only guaranteed readable by brains running on the owner Mac.
- [DIRECTION] [2026-05-24] Chat remains the conversation front door, while `agentic-coding-workbench` owns local harness execution. Reason: Leo's dev-time MVP is to chat with Moussey, listen/read plans, then run coding harnesses and agents from a dedicated execution surface.
- [HARD-NEVER] LAN-only. Same posture as voice-agent and moussey itself.
- [HARD-NEVER] No commercial-property text-chat surfacing (Snowcubes / Resplit / StrongYes) — same boundary as voice-agent. This is the personal command center.

## Claims board

| Task | Status | Owner | Blocking | Depends on | Updated |
|---|---|---|---|---|---|
| T1: /chat page UI | [completed] | Studio Codex | none | nothing | 2026-05-24 |
| T2: /api/chat/ask SSE route | [completed] | Studio Claude/Codex | none | brain-dispatcher B2/B4 | 2026-05-24 |
| T3: Client SSE parser + bubble append | [completed] | Studio Claude | none | T1, T2 | 2026-05-24 |
| T4: Markdown rendering | [completed] | Studio Codex | none | T3 | 2026-05-24 |
| T4a: Error retry/regenerate | [completed] | Studio Codex | none | T3 | 2026-05-24 |
| T5: Session JSONL persistence | [completed] | Studio Codex | none | T2 | 2026-05-24 |
| T6: Multi-turn continuation | [completed] | Studio Codex | none | T5 | 2026-05-24 |
| T7: Session list sidebar | [completed] | Studio Codex | none | T5 | 2026-05-24 |
| T8: File drop | [completed] | Studio Codex | none | T1 | 2026-05-24 |
| T9: Provider re-fork | [completed] | Studio Codex | none | T5 | 2026-05-24 |
| T10: LAN session sharing | [completed] | Studio Codex | none | T7 | 2026-05-24 |
| T11: Claude attachment smoke | [pending] | — | Studio Claude CLI auth 401 | T8 | 2026-05-24 |
| T12: Chat-to-coding handoff | [pending] | — | needs payload/API design | agentic-coding-workbench C6/C7 | 2026-05-24 |

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
- [2026-05-24] Studio continued the local command-center MVP instead of bouncing ownership to another Mac. Reconciled shipped code with this plan: `/chat` and `POST /api/chat/ask` already existed from moussey commit `fe70bc1`; this pass added the home-dashboard Chat tile, changed `/chat` to default to `local (ollama)`, changed the default local model to `qwen2.5:0.5b`, pulled that model into Ollama, and fixed loopback auth so `X-Moussey-From: Self` can call `/api/lan/trigger-claude` without requiring `Self` in `MOUSSEY_LAN_PEERS`. Verification: `moussey-trigger-doctor --brief` reports `endpoint=accepting secret=ok`; `GET http://127.0.0.1:7191/api/health` returns `{"ok":true}`; `npm run test:brain-dispatcher` passes 32/32; `npm run build` passes with the existing Turbopack NFT warning; live `POST /api/chat/ask` with `provider:"local"` streams `local-ok` from `qwen2.5:0.5b`. Claude loopback now reaches the provider but Studio's Claude CLI returns an `error` SSE chunk: `401 Invalid authentication credentials`, so provider comparison remains a credentials follow-up rather than an SSE/router blocker.
- [2026-05-24] Closed the Phase 1 polish and Phase 2 local-history rows. Moussey now has `lib/chat-sessions.ts`, `/api/chat/sessions`, `/api/chat/sessions/:sessionId`, provider health at `/api/chat/providers`, session-aware `/api/chat/ask`, safe markdown/code rendering, retry on assistant error bubbles, and a sessions sidebar in `/chat`. Bug from Leo's screenshot is fixed at the UI boundary: the Claude option is disabled when recent audit logs show Studio Claude CLI auth returning 401, while `local (ollama)` remains selected and ready. Verification: `/Users/leokwan/Development/moussey/scripts/moussey-trigger-doctor --brief` reports `endpoint=accepting secret=ok`; `/Users/leokwan/Development/vidux/bin/vidux-browse health` reports `http://127.0.0.1:7191`; `npm run test:brain-dispatcher` passes 34/34; `npx tsc --noEmit` passes; `npm run build` passes with the existing Turbopack NFT warning; Playwright opened `http://127.0.0.1:4321/chat` with zero console errors and showed `claude (unavailable)` disabled, `local (ollama)` selected, and persisted sessions in the sidebar; live local SSE smoke returned `final-ok` and persisted both turns in `codex-final-chat-smoke`.
- [2026-05-24] Added the two missing operator controls Leo asked about live: local reasoning depth and peer delegation. `/chat` now has Fast/Steady/Deep for local Ollama requests; the dispatcher maps those modes to larger Ollama runtime budgets and sends `think: true` for reasoning-capable models such as Qwen3/DeepSeek-R1/GPT-OSS families. Current installed local model is still only `qwen2.5:0.5b`, so Deep improves budget but not the model class; a larger thinking model remains the next local-model gap. `/chat` also now has a target-Mac selector backed by `/api/lan/trigger-claude/feed`; unavailable trigger peers are visible but disabled. Evidence: M4 Pro dashboard/Vidux is healthy but its trigger endpoint is not accepting (`peers: []`), so the UI labels it not accepting; M1 Max is accepting and a live `/api/chat/ask` smoke with `{provider:"claude", targetMac:"M1 Max"}` returned `m1-peer-chat-ok` from Opus in 3259ms at 17c and persisted the session in `codex-m1-peer-smoke`. Verification: `npm run test:brain-dispatcher` passes 39/39, including new tests for peer delegation and local deep-reasoning payloads; `npx tsc --noEmit` passes; `npm run build` passes with the existing Turbopack NFT warning; Playwright snapshot shows Fast/Steady/Deep plus target options Self, M4 Pro (not accepting), Nicole (not accepting), and M1 Max.
- [2026-05-24] Closed T9 provider re-fork. Assistant bubbles now derive the preceding user prompt even for reloaded JSONL sessions and expose a route chooser + `Rerun` button, so Leo can ask another brain without leaving the thread. The re-fork body carries provider, targetMac, and localReasoning overrides into `/api/chat/ask`; chat-session JSONL now persists `targetMac` on user and assistant turns. Also fixed a LAN fetch reliability gap discovered during verification: Node fetch can hang on `.local` IPv6 addresses, so `lib/lan-url.ts` rewrites Bonjour `.local` URLs to IPv4 for trigger feed, trigger-send, and LAN status probes. Current final peer state: M4 Pro previously returned not accepting (`peers: []`) and the current trigger feed marks it offline/not accepting, Nicole has no trigger endpoint (`404`), and M1 Max is currently offline to the trigger feed; when any peer reports `accepting`, `/chat` adds it as a `peer Opus` re-fork route. Verification: `npm run test:brain-dispatcher` passes 45/45 including `lib/chat-sessions.test.ts` and `lib/lan-url.test.ts`; `npx tsc --noEmit` passes; `npm run build` passes with the known Turbopack NFT warning; `moussey-trigger-doctor --brief` reports `listener=ok endpoint=accepting secret=ok peers_configured=3`; `/Users/leokwan/Development/vidux/bin/vidux-browse health` reports `http://127.0.0.1:7191`; Playwright opened `http://127.0.0.1:4321/chat`, loaded `codex-final-chat-smoke`, clicked `Rerun`, and observed the same session advance from 2 to 4 turns with a fresh `final-ok` response plus visible `local fast` / `codex` re-fork options.
- [2026-05-24] Closed T10 read-only LAN session sharing. Added `lib/chat-share.ts`, `GET /api/chat/sessions/:sessionId/share`, and `/chat?session=<id>&readonly=1` mode. Share links upgrade loopback hosts to this Mac's Bonjour host, so Leo can copy a LAN URL from the owner Mac; read-only mode loads the JSONL session but hides the session sidebar, Share/New buttons, re-fork controls, textarea, and Send button so a peer browser cannot mutate the owner session. Verification: `npm run test:brain-dispatcher` passes 51/51; `npx tsc --noEmit` passes; `npm run build` passes with the existing Turbopack NFT warning; `moussey-trigger-doctor --brief` reports `listener=ok endpoint=accepting secret=ok selfname=Studio peers_configured=3`; `/Users/leokwan/Development/vidux/bin/vidux-browse health` reports `http://127.0.0.1:7191`; live share API returned `http://leos-mac-studio-10442.local:4321/chat?session=codex-final-chat-smoke&readonly=1`; Playwright opened the normal chat, copied the Share link, opened the `.local` read-only URL, and saw four persisted turns with zero console errors and no mutating controls.
- [2026-05-24] Closed T8 file-drop attachments for the `/chat` → `/api/chat/ask` path. The browser composer now has an Attach button plus drag/drop shell for text, code, image, and PDF files; the client sends base64 `dataUrl` payloads with the prompt; the API validates count/size, writes files into `~/.moussey/chat-attachments/<session>/<turn>/`, records attachment metadata in `~/.moussey/chat-sessions/*.jsonl`, and injects saved paths plus text excerpts into the dispatched prompt. Verification: `npm run test:brain-dispatcher` passes 55/55 including `lib/chat-attachments.test.ts` and `app/api/chat/ask/route.test.ts`; `npx tsc --noEmit` passes; `npm run build` passes with the existing Turbopack NFT warning; `moussey-trigger-doctor --brief` reports `listener=ok endpoint=accepting secret=ok selfname=Studio peers_configured=3`; `/Users/leokwan/Development/vidux/bin/vidux-browse health` reports `http://127.0.0.1:7191`; Playwright CLI opened `http://127.0.0.1:4321/chat`, attached `/tmp/moussey-ui-proof.md`, sent a prompt through the composer, confirmed the request body contained a base64 attachment named `moussey-ui-proof.md`, saw the user-turn attachment chip and `ui-attachment-ok` assistant bubble, and reported `Total messages: 0 (Errors: 0, Warnings: 0)`. Live self-Claude attachment proof remains pending behind this Mac's Claude CLI auth 401, so T11 tracks that runtime credential gate.
- [2026-05-24] Split the next dev-time MVP out of chat and into `agentic-coding-workbench`. `/chat` remains the place Leo talks to Moussey and routes brains; `/coding` is the place the system runs allowlisted local harnesses and, next, worktree-isolated agent lanes. New chat follow-up is T12: send current prompt/session/evidence to `/coding` as a proposed run or lane spawn.
