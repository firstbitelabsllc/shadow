# iMessage Bridge — Texts as Agent Input

> **Parent plan:** `~/Development/vidux/projects/agentic-command-center/PLAN.md` — this is **Phase 3 / sub-project #6**. Turns iMessage threads into an input modality for the brain dispatcher.

## Purpose

Read-only MVP first: Leo (or any sender) texts a designated "agent" contact OR sends to a group chat that includes the agent's number. A local cron pulls new messages via the iMessage MCP, dispatches via the brain, and posts the response to **a moussey GUI surface** (NOT back into iMessage — that's Phase 2 once the write path is investigated).

**Killer use case for v1 (read-only):** Leo texts himself at his agent-contact "what's on my plate today?" → next time he opens `:4321/imessage-bridge` in moussey, the agent's structured reply is sitting there with the morning's GitHub PR review queue + Sentry top errors + Snowcubes inventory checks.

**Killer use case for v2 (write path):** Same text → an actual iMessage reply lands in the thread within 60s, indistinguishable from Leo replying to himself except marked with a `🤖` prefix.

The hard part of v2 is sending iMessage from a script. iMessage MCP today is READ-ONLY (`mcp__imessage__*` is all `search`, `get`, `list`, `stats`). Sending requires AppleScript (`tell application "Messages" to send "..." to buddy "..."`) or macOS Shortcuts API — both are macOS-local, not MCP. Reasonable but needs scoped investigation.

## Architecture (LOCKED 2026-05-22)

```
┌──────────────────────────────────────────────────────────────────┐
│ iMessage (macOS Messages.app, syncs to chat.db)                  │
└──────────────────────────────────┬──────────────────────────────┘
                                   │ iMessage MCP read
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ moussey :4321 — imessage-bridge cron (this project)             │
│                                                                  │
│   com.leokwan.moussey-imessage-bridge LaunchAgent (cron 5-min)  │
│      ├─ mcp__imessage__search_messages(after=last_seen_ts,      │
│      │     query="@agent" OR sender=<agent-contact>)            │
│      ├─ for each unprocessed message:                           │
│      │    ├─ thread context via mcp__imessage__get_thread       │
│      │    ├─ route(intent) → claude (always — needs MCP)        │
│      │    ├─ dispatch(req) → AsyncIterable<BrainChunk>           │
│      │    ├─ collect response text                              │
│      │    └─ V1: append to ~/.moussey/imessage-bridge.jsonl     │
│      │         (read-only feedback surface)                     │
│      │       V2: ALSO send via AppleScript bridge (Phase 2)     │
│      └─ update ~/.moussey/imessage-bridge-state.jsonl with the  │
│         last processed message id                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                Browser :4321/imessage-bridge tab
                (renders the JSONL as a chat-style view)
```

## Phases

### Phase 1 — Read + dispatch + GUI surface (no write path yet)

- [pending] **IB1**: Pick trigger surface. Two options:
  - (a) Sender allowlist (e.g. Leo's own number, or Nicole's): any message from these senders gets routed.
  - (b) Body-prefix trigger (`@agent <prompt>`): any message body starting with `@agent` gets routed regardless of sender.
  - Pick **(b)** for v1. Reason: matches vidux-browse-action's `@agent` convention; lets Leo route from any device that can send iMessage; doesn't lock to a contact phone-number scheme.
- [pending] **IB2**: moussey LaunchAgent skeleton — `com.leokwan.moussey-imessage-bridge.plist` firing `scripts/imessage-bridge-tick.ts` every 5 min via `StartInterval=300`. Script: connect to iMessage MCP, search `search_messages(query="@agent", after=last_seen_ts)`, log count.
- [pending] **IB3**: `lib/imessage-bridge.ts` — read the matched thread context via `mcp__imessage__get_thread`. Build `{threadId, sender, contextText (last 5 messages)}`.
- [pending] **IB4**: Wire dispatch — prompt: `"You are reading an iMessage thread for Leo. The trigger comment was: <body>. The recent thread context follows:\n\n<contextText>"`. `dispatch({prompt, provider: "claude", metadata: {sourceModality: "imessage"}})`.
- [pending] **IB5**: V1 output — collected response text appended to `~/.moussey/imessage-bridge.jsonl` with `{ts, threadId, sender, request, response}`. NEVER sends an iMessage.
- [pending] **IB6**: GUI surface — `:4321/imessage-bridge` page renders the JSONL as a chat-style view. Reuse the dark code-block style from `/triggers`. Polls every 10s for new entries.
- [pending] **IB7**: Idempotency. `~/.moussey/imessage-bridge-state.jsonl` records last-processed message id per thread; re-running the cron skips already-handled messages.
- **GATE 1**: Text `@agent what's 47 × 23` to yourself. Open `:4321/imessage-bridge` in moussey. See the agent's "1081" response in the chat view within 6 min.

### Phase 2 — Write path investigation + ship

- [pending] **IB8**: Scope the iMessage send mechanic. Three candidate paths:
  1. **AppleScript bridge.** `osascript -e 'tell application "Messages" to send "..." to participant "..."'`. Works on macOS, but contact identifier is finicky (phone vs Apple ID), Messages.app must be running, requires Accessibility permission.
  2. **macOS Shortcuts API.** Define a `SendMessage` shortcut, invoke via `shortcuts run SendMessage --input "..."`. Cleaner permission model but needs shortcut setup per-Mac.
  3. **Sendblue API or Loop Message API.** External services that proxy SMS/iMessage. Adds cloud dep + cost.
  
  Pick path 1 or 2 for v2 (local-only). Document the chosen path in evidence/.
- [pending] **IB9**: `lib/imessage-send.ts` implementing the chosen path. Returns `Promise<{success: bool, error?: string}>`. Unit-tested with mock subprocess.
- [pending] **IB10**: Wire IB9 into IB5 — when `MOUSSEY_IMESSAGE_BRIDGE_WRITE=on` env is set on the LaunchAgent, ALSO send the response back as an iMessage reply (prefixed with `🤖 `). Default `off` for v1.
- [pending] **IB11**: Sender allowlist for write path. Even in `WRITE=on` mode, ONLY auto-reply to senders in `~/.moussey/imessage-bridge-allowlist.txt`. v2 starts with: just Leo's own number. Adding Nicole requires explicit edit.
- **GATE 2**: With `WRITE=on` and Leo's number on the allowlist, the GATE 1 scenario also produces a real iMessage reply in the thread.

### Phase 3 — Polish (deferred)

- [pending] **IB12**: Per-contact persona — different system hints for thread with Nicole ("you are Leo's assistant. Be brief and warm.") vs thread with himself ("strict technical responses"). Per-sender JSON in `~/.moussey/imessage-bridge-personas.json`.
- [pending] **IB13**: Group chat support. When dispatched to a group thread, the response addresses the group; sender attribution clear.
- [pending] **IB14**: Voice-note transcription — if the trigger message has an attached audio, transcribe via mlx-whisper (already on each Mac for moussey-voice-agent V1) before dispatching.

## Decision Log

- [DIRECTION] [2026-05-22] V1 = read-only with GUI surface. V2 = write path. Reason: iMessage send is the unknown-unknown of this project; isolating it as a Phase 2 task means V1 can ship and prove the read-dispatch loop while write is being investigated.
- [DIRECTION] [2026-05-22] Body-prefix `@agent` over sender-allowlist for v1 trigger. Matches vidux-browse-action convention. Universal across devices.
- [DIRECTION] [2026-05-22] Polling cron at 5 min cadence. Reason: same posture as gmail-bridge — webhooks for iMessage don't exist, and 5-min latency is plenty for the killer use case.
- [DIRECTION] [2026-05-22] Default brain = claude (full MCP). Reason: replies often need access to other tools (calendar, gmail, vidux, etc.). Codex/local can't do that today.
- [DIRECTION] [2026-05-22] Per-Mac cron, not centralized. Each Mac has its own iMessage history (chat.db is per-Mac); each Mac runs its own bridge against its own chat.db. Reason: iMessage doesn't sync chat.db across Macs reliably, and centralizing would need a sync layer that doesn't exist.
- [HARD-NEVER] V1 NEVER sends an iMessage. Read-only.
- [HARD-NEVER] V2 sends only to allowlisted senders. Spam protection.
- [HARD-NEVER] V2 sends without the `🤖 ` prefix on every message. Always visible attribution.
- [HARD-NEVER] V2 auto-replies during quiet hours (10pm–7am local) unless explicitly opted in. Reason: late-night autonomous texting reads as broken.

## Claims board

| Task | Status | Owner | Blocking | Depends on | Updated |
|---|---|---|---|---|---|
| IB1: Pick trigger surface (prefix vs allowlist) | [completed] | claude | IB2 | nothing | 2026-05-22 (resolved in plan: prefix) |
| IB2: Cron skeleton + LaunchAgent | [pending] | — | IB3+ | iMessage MCP available | 2026-05-22 |
| IB3: Thread context reader | [pending] | — | IB4 | IB2 | 2026-05-22 |
| IB4: Wire dispatch | [pending] | — | IB5 | IB3, brain-dispatcher B2 | 2026-05-22 |
| IB5: Append response to JSONL | [pending] | — | GATE 1 | IB4 | 2026-05-22 |
| IB6: GUI surface at :4321/imessage-bridge | [pending] | — | GATE 1 | IB5 | 2026-05-22 |
| IB7: Idempotency state | [pending] | — | GATE 1 | IB5 | 2026-05-22 |
| IB8: Scope write mechanic (AppleScript vs Shortcuts vs API) | [pending] | — | IB9 | (Phase 2) | 2026-05-22 |
| IB9: `lib/imessage-send.ts` | [pending] | — | IB10 | IB8 | 2026-05-22 |
| IB10: Wire write path into dispatch flow | [pending] | — | GATE 2 | IB9 | 2026-05-22 |
| IB11: Sender allowlist for writes | [pending] | — | GATE 2 | IB10 | 2026-05-22 |
| IB12: Per-contact personas | [pending] | — | (Phase 3) | IB10 | 2026-05-22 |
| IB13: Group chat support | [pending] | — | (Phase 3) | IB10 | 2026-05-22 |
| IB14: Voice-note transcription | [pending] | — | (Phase 3) | IB10, voice-agent V1 mlx-whisper | 2026-05-22 |

## Two-agent coordination

**Recommended first claims:** Codex on IB2 (LaunchAgent + MCP cron) + IB3 (thread reader). Claude on IB6 (GUI surface — JSX + chat-style rendering, reuse /triggers pattern).

IB8 (write-mechanic scope) is a research task — should be claimed by whoever has the bandwidth to actually test AppleScript + Shortcuts on a real Mac. Output: a written decision doc in evidence/.

## Open questions for Leo

- **v1 audience**: just Leo's own number, or also Nicole's? Defaults to "open" for v1 read-only since there's no send risk. v2 must allowlist.
- **Quiet-hours window**: default 10pm–7am — adjust?
- **Contact identifier**: when v2 ships, what's Leo's preferred "agent" handle? Could be Leo's own iPhone number (texts to self), a separate Apple ID, or a Google Voice number.
- **Cross-Mac**: if Leo's M4 Pro and Studio both run the bridge against their own chat.db, do we risk double-replies? Need per-message dedupe across the fleet. Plan defers to v2 + sender allowlist (if only one Mac is allowlisted as a sender, only that Mac auto-replies).

## Progress

- [2026-05-22] Plan created. Architecture locked: per-Mac 5-min polling cron, body-prefix `@agent` trigger, v1 read-only with GUI surface, v2 write path after research. IB1 [completed] in plan: prefix over sender allowlist. Gates on brain-dispatcher B2.
