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
| 4 | **agentic-text-chat** | [pending] | Browser text chat at `:4321/chat` — same brain dispatcher, no audio I/O. Fastest UI to ship. **Absorbs the mobile-operator UX layer** (formerly `moussey-mobile-operator/PLAN.md`; merged 2026-05-24 per M-R3 decision) as Phases 3-8 + Phase R rework gate. | `~/Development/vidux/projects/agentic-text-chat/PLAN.md` [NOTE: post-M-R3b execution, mobile-operator content lives here] |
| 5 | **vidux-browse-action** | [pending] | Turn vidux-browse anchored comments into agent triggers. "Pick up this comment and act on it." | needs creation |
| 6 | **imessage-bridge** | [pending] | iMessage to a known contact routes to agent. Reply via iMessage MCP (read-only currently — write needs investigation). | needs creation |
| 7 | **gmail-bridge** | [pending] | Forward an email to a known address → agent reads + drafts reply with full context, leaves in Drafts for review. | needs creation |
| 8 | **screen-action-bridge** | [pending] | vidux-browse annotation + computer-use MCP → agent takes screen action ("click this button", "fill this form"). | needs creation |
| 9 | **autonomous-trigger-bus** | [pending] | LaunchAgent file-drop / cron-tick / Sentry-webhook routes through the same dispatcher. Already partial: moussey-ping-watch cron. | needs creation |
| 10 | **moussey-gui-tabs** | [pending] | Unified moussey GUI: tabs for /triggers /voice /chat /annotations /imessage /gmail /sessions /audit. Tiles per surface on the home grid. | needs creation |
| 11 | **agentic-coding-workbench** | active | Local coding/test harness execution from Moussey: worktree/port-isolated Resplit Web Autobot lanes first, then Codex/Claude/local-agent lanes. | `~/Development/vidux/projects/agentic-coding-workbench/PLAN.md` |

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
- Sub-project #11: agentic-coding-workbench (text/chat/plan → isolated coding lane). Useful to validate Leo's actual dev loop: run build/test/autobot locally, stream output, then route the next action to Codex/Claude/local models.

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
- [HARD-NEVER] No commercial-property voice (Snowcubes / Resplit / StrongYes) using Voxtral. License inherited from voxtral-reader-addon.
- [HARD-NEVER] No always-on remote-mic listening with `bypassPermissions` Claude active. Hold-to-talk OR explicit wake-word with visible state ONLY.
- [HARD-NEVER] No cross-Mac write endpoints beyond `/api/lan/trigger-claude` (which is a sanctioned exception — spawns a LOCAL Claude session on receiver, receiver retains authority).
- [HARD-NEVER] No real-money / production-credential / force-push actions via voice/text/iMessage/Gmail input. Same allowlist that gates trigger-claude.
- [DIRECTION] [2026-05-24] Coding/test harness control is part of the command-center MVP, not a later polish layer. Reason: Leo clarified the #1 goal is to run `/autobot-resplit-web` and grow toward multiplexed coding agents/IDE controls from Moussey.

## Claims board (mega-level)

| Sub-project | Phase | Status | Owner | Updated |
|---|---|---|---|---|
| brain-dispatcher-shared | 0 | **DONE** (B1/B2/B3/B4/B5/B6/B7 [completed]; only B2.0 stream-json refactor remains for true mid-stream text) | claude | 2026-05-22 |
| intent-router-shared | 0 | **DONE for v1** (R1/R2/R3 [completed]; R4-R7 deferred to v2/v3 heuristics + LLM classifier — not blocking any downstream sub-project) | claude | 2026-05-22 |
| moussey-voice-agent | 1 | active (has own claims board; V4 unblocked by B1+R1) | mixed | 2026-05-22 |
| agentic-text-chat | 2 | **DONE for MVP** (T1-T12 completed: `/chat`, `/api/chat/ask`, sessions, share, local reasoning, coding handoff; future work starts from new rows) | Codex | 2026-05-24 |
| vidux-browse-action | 3 | active (PLAN.md scaffolded; VA1+VA3 claimable in parallel) | — | 2026-05-22 |
| imessage-bridge | 3 | active (PLAN.md scaffolded; V1 read-only with GUI, V2 write path = research first) | — | 2026-05-22 |
| gmail-bridge | 3 | active (PLAN.md scaffolded; label-triggered, always-draft-never-send) | — | 2026-05-22 |
| screen-action-bridge | 4 | [pending] | — | 2026-05-22 |
| autonomous-trigger-bus | 4 | active (PLAN.md scaffolded; config-driven trigger registry + 3 sink types; gates on brain-dispatcher B2 [shipped]) | — | 2026-05-22 |
| moussey-gui-tabs | 5 | [pending] | — | 2026-05-22 |
| agentic-coding-workbench | 2 | active (C1-C7 + C6d + C9 + C11 shipped; C12 harmony listener active; live local-smoke reaches build/start/Playwright and reports target `resplit-web` smoke failure `#globe` missing; `/coding` can now spawn a read-only Codex skill probe inside an isolated worktree and inventories skills/MCP capability substrate; Moussey `5fa955a` and ping `5c77229d` are synced back into Vidux) | Studio Codex | 2026-05-24 |

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
- [2026-05-24] Added `agentic-coding-workbench` as the coding/test execution child plan for Leo's clarified MVP. Moussey now has `/coding` local-smoke lane mode: fetches `origin/main`, creates a `resplit-web` worktree, claims `PW_PORT`, runs isolated `npm ci --include=dev`, builds Next, starts Next, runs targeted Playwright, and tears down server/worktree/branch/lock. Verification passed in Moussey unit/build/UI proof; live run `5eae7ddc-5afd-496a-b355-c9159df0097f` reached Playwright on `resplit-web` `a7aa458`, surfaced `#globe` missing from landing smoke, and cleaned up with `teardownOk:true`.
- [2026-05-24] Added coding capability substrate proof. Moussey `/coding` now shows a read-only catalog for active skill symlinks, owned skill source paths, and Codex MCP server config names/commands/env-key names only. Live proof found 8/8 target skills (`autobot-resplit-web`, `vidux`, `pilot-leo`, `amp`, `auto`, `captain`, `nia`, `moussey`) and 5 MCP servers (`everything`, `figma`, `nia`, `node_repl`, `openaiDeveloperDocs`); Playwright saw the panel and `nia-mcp-server` at `http://127.0.0.1:4321/coding` with zero console/page errors.
- [2026-05-24] Started the Vidux/Moussey harmony listener for `agentic-coding-workbench` C12. It polls Moussey pings, LAN health, provider readiness, capability substrate, git heads, and child-plan status until both sides have current evidence of synced/adapted/refreshed workflows.
- [2026-05-24] `agentic-text-chat` is done for the local MVP: `/chat` streams `/api/chat/ask`, persists/reopens sessions, injects recent context, handles attachments, produces LAN read-only share links, surfaces provider health/local reasoning, and stages chat turns into `/coding` handoffs. Verification in child plan: 80 brain-dispatcher/chat/coding tests, Moussey build, health, Vidux health, live local SSE, and Playwright screenshots.
- [2026-05-24] `agentic-coding-workbench` completed C9: `/coding` now has a `codex-skills-probe` mode that launches `codex exec --ephemeral --sandbox read-only` against an isolated `resplit-web` worktree. Live run `d2c80ba8-8a9b-4bdb-a530-8c06178f4844` used Codex v0.130.0 / `gpt-5.5` / `xhigh`, loaded `/vidux`, `/pilot-leo`, `/captain`, `/nia`, and `/autobot-resplit-web`, confirmed `e2e/landing-smoke.spec.ts`, returned the next action, and completed teardown with `exitCode:0`, `teardownOk:true`. Next frontier is a bounded verifier/edit lane, not arbitrary browser shell execution.
- [2026-05-24] C12 harmony pass saved the Moussey implementation and Vidux plan state together. Moussey pushed `5fa955a` with the read-only Codex skill probe lane, harmony run `cb733047-486a-4f3e-97b8-91a943e5f739` repeated the live lane at `PW_PORT=3111` with `exitCode:0` and `teardownOk:true`, and ping `5c77229d-31e8-4902-85cf-852a74129456` records the shared state in Moussey's cross-Mac feed.

## Where things live

- This mega-plan: `~/Development/vidux/projects/agentic-command-center/PLAN.md`
- Sub-project plans: `~/Development/vidux/projects/<name>/PLAN.md`
- Cross-Mac infra: `~/Development/moussey/` (TypeScript/Next.js)
- Voxtral TTS: `~/.local/bin/mlx_audio.server` (per-Mac LaunchAgent)
- Skill index: `~/.claude/skills/` → `~/Development/ai/skills/` (shared) + `~/Development/ai-leo/skills/` (private overlay)
- Audit logs: `~/.moussey/*-events.jsonl`
- Kill switches: `~/.moussey/agent-disabled` (master), `~/.moussey/lan-triggers-disabled` (trigger-claude only)
