# Leo's Agentic Command Center — Mega Plan

## The shape of the win (one paragraph)

You press a button on iPhone OR open moussey on any Mac OR speak out loud OR drop an annotation into vidux-browse OR forward an iMessage OR forward an email. The system parses intent, picks the right brain (Claude with full MCP / Codex / local Ollama), routes to the right Mac in your fleet, executes with FULL access to every Leo skill (/vidux, /captain, /moussey, /snowcubes, /shopper, /maily, /tim, etc.) and every MCP (iMessage, Gmail x3, computer-use, nia, figma), then responds in whatever form fits the task — voice (Voxtral TTS), repo commit, vidux PLAN.md update, Gmail draft, iMessage reply, screen action, cross-Mac dispatch. Everything LAN-only, subscription-billed, kill-switched, visible in moussey GUI dashboards.

ChatGPT voice mode is the FRONT DOOR for one input modality. The actual product is the **command-center brain** behind it.

## The Goal Prompt (paste into any agent at session start)

```text
You are an agent in Leo's fleet. The mega-goal, shared with Claude and Codex
agents across Studio, M4 Pro, and Nicole MBA:

Unified agentic command center for Leo's home Mac fleet. Any input modality
(voice / text / vidux-browse annotation / iMessage / Gmail / cron) routes
through a brain dispatcher (Claude with full MCP via cross-Mac trigger /
Codex / local Ollama) with full skill + MCP coverage, responds in whatever
form fits (TTS / text / repo commit / vidux update / Gmail / iMessage /
screen action / cross-Mac dispatch). LAN-only. Subscription-billed.
Kill-switched. Visible in moussey GUI.

Voice is ONE input modality. Text chat, vidux-browse-action, iMessage bridge,
Gmail bridge, autonomous-trigger bus are siblings — they all share the SAME
brain dispatcher, intent router, audit log, kill switch, rate limit.

Architecture + sub-project list:
    ~/Development/vidux/projects/agentic-command-center/PLAN.md

Pick a [pending] task atom from any active child PLAN.md that matches your
strengths (Claude = JS/UI/MCP integration/plan curation; Codex = TS/Node
server, Python subprocess, dispatcher abstraction, indexed reads). Atomic
claim: edit [pending] → [in_progress] [owner: <claude|codex>] and push.
First-pusher wins.

Reuse every shipped piece. Do not rebuild any of these:
  • Voxtral 4B-TTS LaunchAgent  :8000 per Mac
  • Cross-Mac Claude trigger    :4321/api/lan/trigger-claude
  • Moussey GUI dashboard       :4321  (Triggers tile live)
  • HMAC + kill switch + rate limit  lib/lan-trigger-auth.ts
  • Audit log  ~/.moussey/claude-triggers.jsonl
  • MCP toolkit (iMessage, Gmail x3, computer-use, nia, figma)
  • /vidux project discipline + two-agent atomic claim protocol

Win condition: Leo wakes up, says "what came in overnight?" — the system
reads Gmail + iMessage + Sentry + PR comments + vidux annotations aloud,
asks "want me to draft replies?" — on yes, drafts them, shows in moussey
GUI for review, sends on approve. Same flow accessible by voice, text,
or anchored vidux-browse comment.
```

## Five layers of the stack

```
┌─────────────────────────────────────────────────────────────────┐
│ INPUT — multimodal, all funnel into one brain                   │
│   • voice          (mic → Whisper)         [moussey-voice-agent]│
│   • text           (browser chat UI)        [agentic-text-chat] │
│   • vidux-browse   (anchored comment)       [vidux-browse-action]│
│   • iMessage       (forwarded to known #)   [imessage-bridge]   │
│   • Gmail          (forwarded to known @)   [gmail-bridge]      │
│   • screen/Figma   (drop file, frame URL)   [screen-bridge]     │
│   • cron / agent   (autonomous trigger)     [autonomous-bus]    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ ROUTING — intent + cost/MCP selector + Mac picker                │
│   • parses text into intent + required-skill set                │
│   • picks brain: claude (full MCP, $) / codex (free, no MCP)    │
│                  / local (offline, no MCP)                      │
│   • picks Mac: which peer has the repo / MCP / GPU              │
│   • [intent-router shared library]                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ BRAIN — one of three providers, common AsyncIterable<text>      │
│   • claude → POST /api/lan/trigger-claude  (full MCP toolkit)   │
│   • codex  → exec ~/.local/bin/codex       (unlimited, no MCP)  │
│   • local  → POST localhost:11434 (Ollama) (offline, no MCP)    │
│   • [brain-dispatcher-shared library]                           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ SKILLS + MCP — the capability surface                            │
│   skills: /vidux  /vidux-browse  /pilot  /pilot-leo  /captain   │
│           /machine-sync  /moussey  /snowcubes  /brand-snowcubes │
│           /imagegen-snowcubes  /shopper  /maily  /browse  /tim  │
│           /bigapple  /blog-builder  /seo  /amp  /nia  /effort   │
│           /fcp-ingest /fcp-qc /fcp-export  /imessage /everything│
│           /disk-clean  /machine-sync  /captain                  │
│   MCPs:   imessage  gmail x3  computer-use  nia(17)  figma      │
│   tools:  Bash Read Edit Write Grep Glob Task TaskCreate +bundled│
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ OUTPUT — multimodal, same brain output to multiple sinks         │
│   • TTS voice            (Voxtral :8000)                        │
│   • streaming chat text  (browser bubble)                       │
│   • repo commit + push                                          │
│   • vidux PLAN.md update / claim board edit                     │
│   • Gmail draft / send                                          │
│   • iMessage reply                                              │
│   • screen action        (computer-use MCP)                     │
│   • cross-Mac dispatch   (trigger-claude → peer Mac)            │
│   • file write           (any path on owner Mac)                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ COORDINATION + VISIBILITY                                        │
│   • moussey audit JSONL  ~/.moussey/*-actions.jsonl             │
│   • moussey GUI tiles    /triggers /voice /chat /annotations    │
│   • vidux project plans  (atomic claim, two-agent protocol)     │
│   • kill switch          touch ~/.moussey/agent-disabled        │
│   • rate limit           per-peer, per-minute, per-hour         │
│   • subscription billing (apiKeySource: "none")                 │
│   • LAN-only             no tunnel, no public DNS               │
└─────────────────────────────────────────────────────────────────┘
```

## Sub-projects (children of this mega-goal)

Each row is its own project with its own PLAN.md. They all import the shared `brain-dispatcher` + `intent-router` libraries and write to the shared `~/.moussey/*-actions.jsonl` audit log.

| # | Sub-project | Status | Owns | PLAN.md |
|---|---|---|---|---|
| 1 | **brain-dispatcher-shared** | [pending] | The 3-provider AsyncIterable abstraction — claude/codex/local. Used by every other sub-project. Foundational. | needs creation |
| 2 | **intent-router-shared** | [pending] | Classifier that maps free-text intent → required skills/MCP → brain pick → Mac pick. | needs creation |
| 3 | **moussey-voice-agent** | active | Voice in/out — mic → Whisper → brain → Voxtral → audio. Push-to-talk first, barge-in next. | `~/Development/vidux/projects/moussey-voice-agent/PLAN.md` |
| 4 | **agentic-text-chat** | active | Browser text chat at `:4321/chat` — same brain dispatcher, no audio I/O. Fastest UI to ship. | `~/Development/vidux/projects/agentic-text-chat/PLAN.md` |
| 5 | **agentic-coding-workbench** | active | Local coding/test harness control: run `/autobot-resplit-web`, stream terminal output, then grow into worktree-isolated Claude/Codex/local agent lanes. | `~/Development/vidux/projects/agentic-coding-workbench/PLAN.md` |
| 6 | **vidux-browse-action** | [pending] | Turn vidux-browse anchored comments into agent triggers. "Pick up this comment and act on it." | needs creation |
| 7 | **imessage-bridge** | [pending] | iMessage to a known contact routes to agent. Reply via iMessage MCP (read-only currently — write needs investigation). | needs creation |
| 8 | **gmail-bridge** | [pending] | Forward an email to a known address → agent reads + drafts reply with full context, leaves in Drafts for review. | needs creation |
| 9 | **screen-action-bridge** | [pending] | vidux-browse annotation + computer-use MCP → agent takes screen action ("click this button", "fill this form"). | needs creation |
| 10 | **autonomous-trigger-bus** | [pending] | LaunchAgent file-drop / cron-tick / Sentry-webhook routes through the same dispatcher. Already partial: moussey-ping-watch cron. | needs creation |
| 11 | **moussey-gui-tabs** | [pending] | Unified moussey GUI: tabs for /triggers /voice /chat /coding /annotations /imessage /gmail /sessions /audit. Tiles per surface on the home grid. | needs creation |
| 12 | **mac-material-cleaner** | v0 shipped | Moussey-native disk/material cleanup intelligence: read-only scanner, Leo-aware policy labels, Downloads/Desktop review, media/FCP guardrails. | `~/Development/vidux/projects/mac-material-cleaner/PLAN.md` |

**Already shipped (do not rebuild):**

- moussey :4321 dashboard + cross-Mac trigger + GUI Triggers tile
- vidux-browse :7191 + anchored comments
- Voxtral 4B-TTS at :8000 via voxtral-reader-addon
- moussey-trigger-doctor + watchdog (15-min self-heal)
- HMAC auth + audit log + rate limit + kill switch
- AI-to-AI ping conduit (notification, NOT secret transport)
- /vidux project plan discipline + two-agent atomic claim

## Strategic order (phases of the mega-goal)

### Phase 0 — Foundations (parallelizable, ship first)

- Sub-project #1: brain-dispatcher-shared. THIS IS THE KEYSTONE. Everything else depends on it.
- Sub-project #2: intent-router-shared (stub OK for v1 — just passes everything to claude).

Without these, every sibling re-implements the same provider abstraction badly.

### Phase 1 — First input modality (already in flight)

- Sub-project #3: moussey-voice-agent (voice → brain → voice). Active plan. Consumes Phase 0.

### Phase 2 — Fastest UI to ship (do this in parallel with Phase 1 if Codex has bandwidth)

- Sub-project #4: agentic-text-chat (text → brain → text). Same dispatcher as voice but no audio I/O complexity. Useful to validate brain abstraction works without the STT/TTS bottleneck.
- Sub-project #5: agentic-coding-workbench (text/plan → local harness → terminal output/evidence → optional Claude/Codex/local agent lane). This is now the priority MVP wedge for dev-time use.

### Phase 3 — Existing-surface integrations

- Sub-project #5: vidux-browse-action (turn comments into triggers).
- Sub-project #6: imessage-bridge (one-direction first: read incoming, route to agent).
- Sub-project #7: gmail-bridge (read incoming, draft reply).

### Phase 4 — Action capabilities

- Sub-project #8: screen-action-bridge (computer-use MCP from agent).
- Sub-project #9: autonomous-trigger-bus (Sentry / cron / file-drop routing).

### Phase 5 — Polish

- Sub-project #10: moussey-gui-tabs (unified dashboard).
- moussey-voice-agent Phase 4-5 (barge-in, wake word, history).

## Decision Log

- [DIRECTION] [2026-05-22] One mega-plan + sub-project plans (not one monolithic plan). Reason: lets agents claim work at sub-project granularity, lets us ship voice without blocking text chat, lets us retire sub-projects independently. Risk: shared abstractions (brain-dispatcher, intent-router) need careful contract definition. Mitigation: Phase 0 ships those first as standalone library plans.
- [DIRECTION] [2026-05-22] Brain dispatcher is the keystone. Every input modality is just a different way to produce text+context. Every output modality is just a different way to consume streamed text+actions. The brain dispatcher is the only shared core.
- [DIRECTION] [2026-05-22] Claude (via trigger-claude) is the default brain. Reason: full MCP toolkit, subscription billing, proven. Codex + local are degraded modes today (no MCP). Routing becomes "auto-pick by cost+MCP-requirement" only after Codex has MCP shims.
- [DIRECTION] [2026-05-22] One audit log file pattern, many surfaces. `~/.moussey/{trigger|voice|chat|imessage|gmail|action}-events.jsonl`. moussey GUI reads them all. Easy to add a new modality without changing the audit schema.
- [DIRECTION] [2026-05-22] LAN-only. Same hard rule as moussey. No tunnels, no public DNS. iPhone/iPad access via `<mac>.local:4321` on home Wi-Fi only.
- [DIRECTION] [2026-05-22] Voice agent is Phase 1, not Phase 0. Text chat is Phase 2. Reason: voice is what Leo asked for first; text is faster to ship but harder to demo "ChatGPT voice mode parity." Voice forces the streaming + audio-pipeline rigor that text chat can later borrow.
- [DIRECTION] [2026-05-24] Coding/test harness control is the highest-priority MVP wedge while Leo is actively devving. Voice remains a modality, but the immediate loop is text/chat plus `/coding`: run `/autobot-resplit-web`, inspect terminal output, capture evidence, and then route to Claude/Codex/local agents.
- [DIRECTION] [2026-05-24] The command center may run allowlisted local harnesses, but it must not become a browser-exposed arbitrary shell. The first safe surface is `resplit-web-autobot` with fixed `--status`, `--dry-run`, and `--public-only` args.
- [HARD-NEVER] No commercial-property voice (Snowcubes / Resplit / StrongYes) using Voxtral. License inherited from voxtral-reader-addon.
- [HARD-NEVER] No always-on remote-mic listening with `bypassPermissions` Claude active. Hold-to-talk OR explicit wake-word with visible state ONLY.
- [HARD-NEVER] No cross-Mac write endpoints beyond `/api/lan/trigger-claude` (which is a sanctioned exception — spawns a LOCAL Claude session on receiver, receiver retains authority).
- [HARD-NEVER] No real-money / production-credential / force-push actions via voice/text/iMessage/Gmail input. Same allowlist that gates trigger-claude.

## Claims board (mega-level)

| Sub-project | Phase | Status | Owner | Updated |
|---|---|---|---|---|
| brain-dispatcher-shared | 0 | **DONE** (B1/B2/B3/B4/B5/B6/B7 [completed]; only B2.0 stream-json refactor remains for true mid-stream text) | claude | 2026-05-22 |
| intent-router-shared | 0 | **DONE for v1** (R1/R2/R3 [completed]; R4-R7 deferred to v2/v3 heuristics + LLM classifier — not blocking any downstream sub-project) | claude | 2026-05-22 |
| moussey-voice-agent | 1 | active (has own claims board; V4 unblocked by B1+R1) | mixed | 2026-05-22 |
| agentic-text-chat | 2 | local MVP live (text/file attachments → brain-dispatcher → local model or accepting peer Opus; markdown/retry/history/session sidebar/reasoning depth/target selector/assistant-bubble re-fork/read-only LAN sharing/chat-to-coding handoff shipped; Studio Self Claude auth still gates self-Claude file-tool smoke) | Studio Codex | 2026-05-24 |
| agentic-coding-workbench | 2 | local MVP live (`/coding` runs allowlisted Resplit Web Autobot modes, worktree/port-isolated lane status, and chat-originated handoff preflights; next is local-server build/start/Playwright stage) | Studio Codex | 2026-05-24 |
| vidux-browse-action | 3 | active (PLAN.md scaffolded; VA1+VA3 claimable in parallel) | — | 2026-05-22 |
| imessage-bridge | 3 | active (PLAN.md scaffolded; V1 read-only with GUI, V2 write path = research first) | — | 2026-05-22 |
| gmail-bridge | 3 | active (PLAN.md scaffolded; label-triggered, always-draft-never-send) | — | 2026-05-22 |
| screen-action-bridge | 4 | [pending] | — | 2026-05-22 |
| autonomous-trigger-bus | 4 | active (PLAN.md scaffolded; config-driven trigger registry + 3 sink types; gates on brain-dispatcher B2 [shipped]) | — | 2026-05-22 |
| moussey-gui-tabs | 5 | [pending] | — | 2026-05-22 |
| mac-material-cleaner | 4 | v0 shipped (read-only scanner + `/api/cleaner/scan` + `/cleaner`; media metadata/local inference/photo-video judgment queued) | codex | 2026-05-23 |

**Phase 0 status (2026-05-22, END OF DAY):** ALL PROVIDERS SHIPPED end-to-end.
- `claude` (B2, moussey `d123f14`) — verified live via smoke: `✓ Hi 4441ms $0.20`. Uses loopback HMAC → `/api/lan/trigger-claude` → buffered text. Subscription billing (`apiKeySource: "none"`).
- `codex` (B3, moussey `e7874a3`) — spawns `codex exec` subprocess. KNOWN GAP: codex requires trusted-git-repo cwd; needs argv-passing followup tick to bypass via flag.
- `local` (B4, moussey `2cb8abc`) — POSTs Ollama `:11434/api/generate` JSONL stream. Verified: yields error chunk correctly when ollama unreachable, no false-positive ✓.
- 5 helpers in `moussey/lib/` (`brain-dispatcher.ts` + `intent-router.ts` + `brain-audit.ts` + `loopback-sign.ts` + `sse-parse.ts`) + 29 passing unit tests via `npm run test:brain-dispatcher` + tri-provider smoke at `scripts/brain-dispatch-smoke.ts`.
- Voice-agent V4 + agentic-text-chat T2 fully unblocked. They import `dispatch()` directly.
- B2.0 stream-json refactor remains as the single Phase 0 followup for true mid-stream text (currently buffered for claude).

## Two-agent coordination (across all sub-projects)

Same atomic-claim protocol everywhere. Each sub-project has its own PLAN.md with its own claims board. Pull → claim → push → ship → mark completed. First-pusher wins.

**Cross-sub-project rule:** if you finish a Phase 0 task (brain-dispatcher or intent-router) that unblocks Phase 1+ work, the unblocked tasks become claimable immediately. No handoff DM needed — every agent's next cycle starts with `git pull --rebase`.

**Strength alignment, fleet-wide:**

| Agent | Best at |
|---|---|
| Claude (this) | JS/UI, audio scheduling, MCP integration, plan curation, evidence/screenshots |
| Codex | TS/Node server, Python subprocess, library abstractions, indexed reads via /nia |
| Local Ollama | (degraded — no MCP yet, no skill access) |

## Open questions for Leo (do not block on these)

- **Brain default**: claude (full MCP) vs auto-pick by cost. Plan defaults to claude. Reconsider after Phase 3 when we see real cost data.
- **Default Mac for cross-input dispatch**: the Mac the user is touching, or always Studio? Default v1: the Mac you're on.
- **iMessage write capability**: the current iMessage MCP is read-only (`mcp__imessage__*` are all read tools). Sending iMessage from agent would need a separate write surface — investigate AppleScript bridge or Shortcuts API.
- **Wake word**: `"hey moussey"` (default per voice-agent plan) vs `"hey claude"` vs custom. P5 problem.
- **iPhone client**: should it be a Safari PWA against `<mac>.local:4321/voice`, or a SwiftUI native app? Default v1: Safari PWA. Native app deferred.

## Progress

- [2026-05-22] Mega-plan created. Phase 0 + Phase 1 unblocked. moussey-voice-agent already has its own active claims board. Phase 0 brain-dispatcher-shared and intent-router-shared still need their own PLAN.md files — next claimable work after this one is "write brain-dispatcher-shared/PLAN.md" since voice-agent V4 depends on it.
- [2026-05-24] Studio continued the base-station implementation locally per Leo's correction, without cross-Mac Vidux writes or remote plan mutation. Agentic text chat now has a usable local happy path: Moussey home dashboard links to `/chat`, `/chat` defaults to `local (ollama)`, Ollama has `qwen2.5:0.5b`, and live `POST /api/chat/ask` streams `local-ok` through brain-dispatcher. Health evidence: `moussey-trigger-doctor --brief` accepts with `secret=ok`, `GET :7191/api/health` returns ok, `npm run test:brain-dispatcher` passes 32/32, and `npm run build` passes with the pre-existing Turbopack NFT warning. Claude fallback is routed but not complete on Studio because the Claude CLI returns an `error` SSE chunk: `401 Invalid authentication credentials`.
- [2026-05-24] Advanced agentic-text-chat from single-turn to local command-center MVP: `/chat` now has provider health, disables unavailable Claude when Studio CLI auth is bad, defaults to ready `local (ollama)`, streams via `/api/chat/ask`, persists JSONL sessions under `~/.moussey/chat-sessions`, restores sessions through `/api/chat/sessions`, sends bounded recent context on continuation, renders markdown/code safely, and offers retry on error bubbles. Verification on Studio: Moussey health ok at `http://127.0.0.1:4321/api/health`; provider status ok at `http://127.0.0.1:4321/api/chat/providers`; live local SSE returned `final-ok`; Playwright opened `http://127.0.0.1:4321/chat` with zero console errors and showed `claude (unavailable)` disabled; `npm run test:brain-dispatcher` passes 34/34; `npx tsc --noEmit` passes; `npm run build` passes with the existing Turbopack NFT warning. Next mega-lane choice: either repair Studio Claude CLI auth for provider comparison, add Codex/local model affordances, or move to voice now that text dispatch is proven.
- [2026-05-24] Confirmed and exposed cross-agent delegation from `/chat` using the existing Moussey trigger bus rather than a new bridge. The chat API now accepts `targetMac`, brain-dispatcher honors peer targets for Claude by calling `/api/lan/trigger-send`, and the UI shows trigger readiness from `/api/lan/trigger-claude/feed`. Live peer evidence: M4 Pro is dashboard/Vidux healthy but not trigger-accepting because its endpoint reports `peers: []`; M1 Max is trigger-accepting and a read-only delegated smoke returned `m1-peer-chat-ok` through `/api/chat/ask` with `targetMac:"M1 Max"`. This proves the chat can ask another local Mac to run an Opus agent session and stream the answer back. Also added local reasoning depth (Fast/Steady/Deep) for Ollama; installed local model remains `qwen2.5:0.5b`, so true local thinking requires pulling a reasoning-capable model next.
- [2026-05-24] Closed the visible re-fork loop for agentic text chat. Assistant bubbles now expose `Rerun route` + `Rerun`, so Leo can take any prior answer and re-ask it through local fast/steady/deep, Codex, Studio Claude when authenticated, or an accepting peer Opus route. The chat session log preserves `targetMac`, `/api/chat/ask` carries provider/target/reasoning overrides, and LAN probes now prefer IPv4 for `.local` hosts so Node fetch does not falsely hang on an IPv6 path. Verification on Studio: `npm run test:brain-dispatcher` passes 45/45, `npx tsc --noEmit` passes, `npm run build` passes with the known Turbopack NFT warning, `moussey-trigger-doctor --brief` reports `endpoint=accepting secret=ok selfname=Studio peers_configured=3`, `vidux-browse health` is live at `http://127.0.0.1:7191`, and Playwright opened `http://127.0.0.1:4321/chat` with zero console errors, reran a loaded session, and saw the turn count advance from 2 to 4. Final peer reality for this pass: Studio is accepting locally; M4 Pro previously returned not accepting (`peers: []`) and the current trigger feed marks it offline/not accepting; Nicole has no trigger endpoint; M1 Max previously proved delegated Opus but was offline during the final feed check.
- [2026-05-24] Closed read-only LAN sharing for agentic text chat. `/chat` can now copy a session-specific LAN URL such as `http://leos-mac-studio-10442.local:4321/chat?session=codex-final-chat-smoke&readonly=1`; that shared mode loads the owner Mac's persisted JSONL session and removes composer/sidebar/re-fork/new/share controls so it cannot mutate the session. This complements, but does not replace, cross-agent delegation: sharing lets another browser inspect the thread, while delegation still requires an accepting peer in `/api/lan/trigger-claude/feed`. Verification on Studio: `npm run test:brain-dispatcher` passes 51/51, `npx tsc --noEmit` passes, `npm run build` passes with the existing Turbopack NFT warning, `moussey-trigger-doctor --brief` reports `listener=ok endpoint=accepting secret=ok selfname=Studio peers_configured=3`, `vidux-browse health` is live at `http://127.0.0.1:7191`, and Playwright opened both the normal chat Share flow and the `.local` read-only URL with four persisted turns and zero console errors. Current peer reality at the capability check: M4 Pro is configured but not accepting (`secretConfigured: true`, `peers: []`, status offline/not accepting), M1 Max is offline, and Nicole returns `404`.
- [2026-05-24] Closed the `/chat` file-attachment slice on Studio without adding any cross-Mac file bridge. Attachments are owner-Mac local under `~/.moussey/chat-attachments/<session>/<turn>/`; `/api/chat/ask` records metadata into the JSONL session and injects saved file paths plus text/code excerpts into the dispatched prompt. This gives local/Codex/self-Claude routes an inspectable file path once the provider is available, while peer Opus routes only get the prompt/excerpt context unless the file is otherwise shared. Verification on Studio: `npm run test:brain-dispatcher` passes 55/55, `npx tsc --noEmit` passes, `npm run build` passes with the existing Turbopack NFT warning, `moussey-trigger-doctor --brief` reports `listener=ok endpoint=accepting secret=ok selfname=Studio peers_configured=3`, `vidux-browse health` is live at `http://127.0.0.1:7191`, and Playwright CLI proved the visible Attach flow with `moussey-ui-proof.md`, request-body base64 attachment, user attachment chip, assistant response, and zero console warnings/errors. Remaining text-chat done-done gate: repair this Mac's Claude CLI auth and run the self-Claude file/vision smoke.
- [2026-05-24] Added the first coding/test-harness execution surface for Leo's revised MVP priority. New child plan: `~/Development/vidux/projects/agentic-coding-workbench/PLAN.md`. Moussey now exposes `/coding`, `GET /api/coding/jobs`, and `POST /api/coding/run` for the allowlisted `resplit-web-autobot` job only. Modes are fixed to `--status`, `--dry-run`, and `--public-only`; arbitrary shell/cwd/env is not accepted. Verification on Studio: `npm run test:brain-dispatcher` passes 62/62, `npx tsc --noEmit` passes, `npm run build` passes with the known Turbopack NFT warning, `moussey-trigger-doctor --brief` reports `endpoint=accepting secret=ok selfname=Studio`, `vidux-browse health` reports `http://127.0.0.1:7191`, live `/api/coding/jobs` reports ready, live `/api/coding/run` status exits 0, and Playwright opened `http://127.0.0.1:4321/coding`, clicked `Status`, rendered terminal output, and saw zero console errors. Next finish line: worktree/port-isolated coding lanes so Claude/Codex/local agents can run real Resplit Web work without touching Leo's primary checkout.
- [2026-05-24] Advanced the coding workbench toward the multi-agent IDE loop with a no-mutation lane preflight. `/coding` now has `Lane Preflight`, backed by `POST /api/coding/lanes/preflight`, which checks ports `3110..3119`, lock files, the Resplit Web repo, and the worktree root before showing the exact worktree path, `codex/web-*` branch, build/start/test commands, and cleanup command. Verification on Studio: `npm run test:brain-dispatcher` passes 68/68, `npx tsc --noEmit` passes, `npm run build` passes with the known Turbopack NFT warning, `scripts/moussey-trigger-doctor --brief` reports `endpoint=accepting secret=ok selfname=Studio`, `bin/vidux-browse health` reports `http://127.0.0.1:7191`, live preflight selected port `3110` with `ready:true`, and Playwright clicked `Lane Preflight` in `http://127.0.0.1:4321/coding` with zero console warnings/errors. Next finish line: convert preflight into gated lane prepare/run/teardown plus chat-to-coding handoff.
- [2026-05-24] Converted the coding lane from preflight-only into a real gated worktree runner. `/coding` now has `Run Lane Status`, backed by `POST /api/coding/lanes/run`, which claims a `3110..3119` port lock, creates a throwaway Resplit Web worktree and `codex/web-*` branch, runs the allowlisted Autobot mode inside that worktree, and tears everything down. Verification on Studio: `npm run test:brain-dispatcher` passes 71/71, `npx tsc --noEmit` passes, `npm run build` passes with the known Turbopack NFT warning, `scripts/moussey-trigger-doctor --brief` reports accepting, `bin/vidux-browse health` reports `http://127.0.0.1:7191`, live lane run returned `exitCode:0` and `teardownOk:true`, post-run checks found no leftover worktree/branch/lock, and Playwright clicked `Run Lane Status` with zero console warnings/errors. Next finish line: either C6c local server build/start/Playwright lanes or C7 chat-to-coding handoff.
- [2026-05-24] Closed the chat-to-coding loop for the local command-center MVP. `/chat` user turns now have `Code lane`, which persists a local handoff packet through `POST /api/coding/handoffs` and opens `/coding?handoff=<id>`; `/coding` displays the source prompt and can preflight or run the allowlisted Resplit Web lane with a `chat-*` lane label. This keeps chat as intent/context and coding as execution. Verification on Studio: `npm run test:brain-dispatcher` passes 76/76, `npx tsc --noEmit` passes, `npm run build` passes with the known Turbopack NFT warning, `scripts/moussey-trigger-doctor --brief` reports accepting, `bin/vidux-browse health` reports `http://127.0.0.1:7191`, live handoff API created `/coding?handoff=20f1821e-e127-4a5b-9e38-1dfe29b32b97`, live preflight returned `ready:true` on port `3110`, and Playwright clicked `/chat?session=codex-c7-ui` → `Code lane` → `/coding?handoff=469e116c-5be9-4a89-a72d-46d701a0b0b2` → `Preflight` with zero console warnings/errors. Screenshot: `/tmp/moussey-c7-chat-to-coding.png`. Next finish line: C6c local `npm run build` + `next start -- --port $PW_PORT` + targeted Playwright inside the isolated worktree.

## Where things live

- This mega-plan: `~/Development/vidux/projects/agentic-command-center/PLAN.md`
- Sub-project plans: `~/Development/vidux/projects/<name>/PLAN.md`
- Cross-Mac infra: `~/Development/moussey/` (TypeScript/Next.js)
- Voxtral TTS: `~/.local/bin/mlx_audio.server` (per-Mac LaunchAgent)
- Skill index: `~/.claude/skills/` → `~/Development/ai/skills/` (shared) + `~/Development/ai-leo/skills/` (private overlay)
- Audit logs: `~/.moussey/*-events.jsonl`
- Kill switches: `~/.moussey/agent-disabled` (master), `~/.moussey/lan-triggers-disabled` (trigger-claude only)
