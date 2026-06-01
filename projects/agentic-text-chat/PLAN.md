# Agentic Text Chat — Browser-Based Chat for Leo's Fleet

> **Parent plan:** `~/Development/vidux/projects/agentic-command-center/PLAN.md` — this is **Phase 2 / sub-project #4**. Sibling of moussey-voice-agent. Same brain dispatcher + intent router, no audio I/O — just text in / text out / markdown rendering.
>
> **Related plans (R-46 reciprocal cross-links, established 2026-05-24):**
> - **Parent**: `~/Development/vidux/projects/agentic-command-center/PLAN.md` sub-project #4
> - **Substrate dependency**: `~/Development/vidux/projects/ai-substrate-1000x/PLAN.md` (Tailscale NET Phase 3, PWA VOX-10, voice pipeline, chat-auth)
> - **Home dashboard**: `~/Development/vidux/projects/moussey/PLAN.md`
> - **Mobile-operator UX layer**: this plan **absorbs** the former `moussey-mobile-operator/PLAN.md` as Phases 3-8 + Phase R rework gate per M-R3 merge decision (`~/Development/vidux/projects/moussey-mobile-operator/evidence/2026-05-24-M-R3-merge-decision.md`). [NOTE: until M-R3b execution lands the migration, the mobile-operator tasks live at `~/Development/vidux/projects/moussey-mobile-operator/PLAN.md`; post-M-R3b they migrate into THIS file as T-A*..T-F* + T-R*.]

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

- [completed] **T1**: `/chat` page in moussey/app/chat/page.tsx. Textarea + provider dropdown (claude / codex / local) + submit button + chat-bubble container. Reuse the dark code-block style from /triggers page.
- [completed] **T2**: `POST /api/chat/ask` route. Body: `{prompt, provider}`. Calls `route()` then `dispatch()` from brain-dispatcher. Streams chunks as SSE.
- [completed] **T3**: Client-side SSE parser. Appends `text` chunks to the active bubble character-by-character. `tool_use` chunks render as a small "🛠 using <tool>" indicator. `complete` event shows total cost + duration. `error` shows red with retry button.
- [completed] **T4**: Markdown rendering via the existing renderer used in vidux-browse (port the relevant CSS + parser if not already shared). Code blocks get syntax highlighting (existing `highlight.js` is fine).
- **GATE 1**: Shipped. Type/send works through `/api/chat/ask` SSE; live local proof returned `OK local chat proof`, showed duration, and rendered in `/chat`.

### Phase 2 — Multi-turn + history

- [completed] **T5**: Conversation history persisted per session to `~/.moussey/chat-sessions/<sessionId>.jsonl`. Each turn = `{ts, role, content, provider, costCents}`.
- [completed] **T6**: Continuation: send prior 3 turns as context when the user replies in the same thread. Stable session ID via cookie/localStorage.
- [completed] **T7**: Session list sidebar — `GET /api/chat/sessions` returns recent sessions. Click loads `GET /api/chat/sessions/:id`.
- **GATE 2**: Shipped. Route tests prove persistence/list/load/context injection; browser proof shows reopened session in sidebar and loaded conversation.

### Phase 3 — Power features (deferred)

- [completed] **T8**: File drop into the textarea — attach a code snippet / image / PDF. Passes through to claude via MCP (read_file / vision).
- [completed] **T9**: Forked turns — "regenerate with different provider" without losing history.
- [completed] **T10**: Sharing — generate a read-only LAN URL for a specific session that Nicole MBA can open from her browser.

### Phase 2.5 — Base-station command controls

- [completed] **T11**: Provider readiness + local reasoning controls. `/chat` shows local/claude/codex readiness, defaults to a working provider, and lets Leo choose fast/steady/deep for local models without pretending every model supports thinking tokens.
- [completed] **T12**: Coding-lane handoff from chat. A user turn can stage a local coding handoff that opens the `/coding` workbench with session/turn context instead of requiring Leo to copy/paste the prompt.
- [completed] **T13**: Local model inventory + reasoning truth. `/api/chat/providers` reports the selected Ollama model, installed local models, context/output budgets per reasoning level, and whether the current model actually supports Ollama `think`; `/chat` shows that state inline so Leo can see when Deep is bigger-budget versus true thinking tokens.

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
| T1: /chat page UI | [completed] | studio | T3, T4 | nothing | 2026-05-23 (shipped at moussey `fe70bc1` — 314-line app/chat/page.tsx with provider dropdown, prompt textarea, Cmd+Enter send, session ID. Verified rendering HTTP 200 on M1 + Studio.) |
| T2: /api/chat/ask SSE route | [completed] | studio | T3 | — | 2026-05-23 (shipped at moussey `fe70bc1` — 154-line app/api/chat/ask/route.ts. Wires `dispatch({prompt, provider, metadata:{sourceModality:"text"}})` into SSE stream. Verified M1 end-to-end with `provider=claude` returns `meta → system_init → text → complete → [DONE]` in 1968ms, $0.15. Studio's verification ping cf781db7 confirmed Studio's /chat works after moussey `4820d05` Self-loopback fix.) |
| T3: Client SSE parser + bubble append | [completed] | studio | GATE 1 | T1, T2 | 2026-05-23 (shipped at moussey `fe70bc1` — page.tsx uses fetch + getReader + TextDecoder + per-line `data:` prefix parser to append response chunks to UI.) |
| T4: Markdown rendering | [completed] | codex | — | T3 | 2026-05-24 (`/chat` renders markdown/code/link blocks; build + browser proof `/tmp/moussey-chat-proof-final.png`.) |
| T5: Session JSONL persistence | [completed] | codex | — | T2 | 2026-05-24 (`app/api/chat/ask/route.test.ts` + live session `codex-proof-20260524T052320Z` persisted 2 turns.) |
| T6: Multi-turn continuation | [completed] | codex | — | T5 | 2026-05-24 (`POST /api/chat/ask injects recent session context...` regression proves actual dispatch prompt contains prior turns.) |
| T7: Session list sidebar | [completed] | codex | — | T5 | 2026-05-24 (`app/api/chat/sessions/route.test.ts`, `[sessionId]/route.test.ts`, and browser proof show selected session in sidebar after direct `?session=` load.) |
| T8: File drop | [completed] | codex | — | T1 | 2026-05-24 (`lib/chat-attachments.test.ts` + `/api/chat/ask` attachment regression prove local file write + prompt excerpt injection.) |
| T9: Provider re-fork | [completed] | codex | — | T5 | 2026-05-24 (browser proof shows assistant `Rerun` route selector on persisted session.) |
| T10: LAN session sharing | [completed] | codex | — | T7 | 2026-05-24 (`share-route.test.ts` + browser proof `/tmp/moussey-chat-proof-final.png` show `leos-mac-studio-10442.local:4321/chat?session=...&readonly=1`.) |
| T11: Provider readiness + local reasoning controls | [completed] | codex | — | T2 | 2026-05-24 (`/api/chat/providers` reports local ready, codex ready, claude auth warning; browser proof shows Fast/Steady/Deep controls.) |
| T12: Coding-lane handoff from chat | [completed] | codex | — | T1, agentic-coding-workbench C4 | 2026-05-24 (`POST /api/coding/handoffs` test + live handoff `b446c42d-dc7d-4128-9db8-0cba0fedf47c` opened `/coding` with Run Local Smoke controls; proof `/tmp/moussey-chat-coding-handoff-loaded-proof.png`.) |
| T13: Local model inventory + reasoning truth | [completed] | codex | — | T11 | 2026-05-24 (`lib/local-model-runtime.ts`, `/api/chat/providers`, and `/chat` now expose selected model `qwen2.5:0.5b`, installed Ollama models, Fast/Steady/Deep ctx/out budgets, and `thinking unavailable` for qwen2.5; proof `/tmp/moussey-c24-local-model-chat-ui.png`.) |

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
- [2026-05-24] Reconciled the plan with current Moussey code before continuing: `/chat` already contains markdown/code rendering, session persistence/listing, history continuation, file attachments, read-only LAN sharing, provider readiness, local reasoning controls, peer target routing, and a coding-lane handoff button. Holding T4-T12 in `[in_progress]` until this cycle adds the missing route regressions plus local browser/API proof.
- [2026-05-24] Closed T4-T12 for `/chat` and `/api/chat/ask`. Added regressions for session continuation prompt injection, assistant persistence, session list route, and single-session load route. Fixed direct `?session=` loads so the sidebar refreshes instead of showing "No saved sessions." Verification: `npm run test:brain-dispatcher` (80/80), `npx tsc --noEmit`, `npm run build` (passes with known Turbopack NFT warning on `trigger-send`), `scripts/moussey-trigger-doctor --brief` accepting, `bin/vidux-browse health`, live local SSE session `codex-proof-20260524T052320Z`, browser proof `/tmp/moussey-chat-proof-final.png`, share proof embedded there, and coding handoff proof `/tmp/moussey-chat-coding-handoff-loaded-proof.png`.
- [2026-05-24] Closed T13 after Leo asked whether open models can dial up reasoning and whether Qwen/Gemma-style models are truly thinking. Shared `lib/local-model-runtime.ts` now drives both `brain-dispatcher` runtime options and `/api/chat/providers`; live provider API reports only `qwen2.5:0.5b` installed, with Deep = `num_ctx 16384` + `num_predict 2048` but no Ollama `think` field because qwen2.5 is not in the thinking-family allowlist. Verification: focused local-model/chat-provider tests 16/16, `npm run test:brain-dispatcher` 122/122, `npm run test:cleaner` 116/116, TypeScript, standalone rebuild/restart, live `/api/chat/providers`, live `/api/health`, and browser proof `/tmp/moussey-c24-local-model-chat-ui.png`.


---

## PSA — 2026-05-26 — Fleet UX/UI lane split codified

- **Claude Code owns ALL UX/UI work fleet-wide.** Codex agents must stay on backend / logic / lanes / workers / API.
- **Disambiguator:** "is this rendered to a human?" → Claude. "Does this read/write data, run a CLI, or expose an HTTP endpoint?" → Codex.
- **Canonical visualization layer:** [Litty](file:///Users/leokwan/Development/litty) at `http://localhost:4400` (the operator cockpit). Federates moussey's `/api/coding/*` APIs. Replaces the 12,062-line `moussey/app/coding/page.tsx` rot.
- **15 routes shipped 2026-05-26:** `/`, `/lanes`, `/lanes/[laneId]`, `/runs`, `/runs/[runId]`, `/runs/[runId]/patch`, `/runs/[runId]/stream`, `/workers`, `/workers/[workerId]`, `/handoffs`, `/handoffs/[handoffId]`, `/capabilities`, `/api/health`, `/api/proxy/coding/[...path]`, plus sibling-shipped `/api/operating-readout`, `/api/proofs`, `/api/repo-catalog`.
- **Plan:** `~/Development/vidux/projects/litty/PLAN.md` (canonical). Research at `~/Development/vidux/projects/litty/research/` (~30k words, 11 deep-research agents).
- **Codex agents seeing UX/UI work in this project's queue:** redirect to backend tasks (federation contracts, FirstBite lanes, MCP, repo-backed catalog snapshots, the moussey-side PRs documented as Phase 3.5 unblockers).
- **Reference:** `/pilot-leo § Agent lane splits — codify in the project, not here (2026-05-24)` (the disambiguator pattern).
