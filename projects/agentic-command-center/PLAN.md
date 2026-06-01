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
| 10 | **moussey-slack-suite** | active | **Slack = 6th input/output modality.** Slack as the universal front-end (chat / file upload / approvals / digests / fleet awareness) over the same `brain-dispatcher` + `intent-router` spine. ONE Socket-Mode app (1 of 10 Free slots), superset of slash-commands + bots + automations, all dispatch gated through `#fb-approvals`. Reuses firstbite-slack-ops channels + dry-run bridge. | `~/Development/vidux/projects/moussey-slack-suite/PLAN.md` |
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
| agentic-text-chat | 2 | **DONE for MVP** (T1-T13 completed: `/chat`, `/api/chat/ask`, sessions, share, local reasoning, local model inventory/truth, coding handoff; future work starts from new rows) | Codex | 2026-05-24 |
| vidux-browse-action | 3 | active (PLAN.md scaffolded; VA1+VA3 claimable in parallel) | — | 2026-05-22 |
| imessage-bridge | 3 | active (PLAN.md scaffolded; V1 read-only with GUI, V2 write path = research first) | — | 2026-05-22 |
| gmail-bridge | 3 | active (PLAN.md scaffolded; label-triggered, always-draft-never-send) | — | 2026-05-22 |
| screen-action-bridge | 4 | [pending] | — | 2026-05-22 |
| autonomous-trigger-bus | 4 | active (PLAN.md scaffolded; config-driven trigger registry + 3 sink types; gates on brain-dispatcher B2 [shipped]) | — | 2026-05-22 |
| moussey-gui-tabs | 5 | [pending] | — | 2026-05-22 |
| agentic-coding-workbench | 2 | active (C1-C7 + C6d/C6e + C8 + C9 + C10 + C11 + C12 + C13a/C13b/C13c/C13d/C14/C14b/C14c/C15/C16/C17/C18/C19/C20/C21/C22/C23/C24/C25/C26 shipped; no recurring harmony heartbeat is active; Vidux can now open local Moussey `/coding` handoffs from a plan `Code` button without remote plan mutation; `/coding` can spawn isolated Codex agents, run linked-deps build/start/Playwright on `resplit-web`, prove skill/MCP/web/cloud capability surfaces, preserve final Codex answers, detect active Cleaner neighbor work, run allowlisted tool actions for Captain audit, read-only Codex tool-call proof, `/autobot-resplit-web --public-only`, Skill/MCP/cloud routing, source-id-aware Nia routing, cached source registry routing, current-session public-matrix reproofs, failed-run-to-verifier handoffs, explicit `codex-editor` runs that save disposable-worktree patches to `~/.moussey/coding-patches/<run>.patch`, and guarded read-only patch preview from `/coding`; list recent coding runs from local JSONL; run detached log-backed Codex workers for heavier tool actions; report first-class Routing Readiness from `/api/coding/capabilities`; and report/fix the real stale `#globe` smoke failure with clean teardown. Live editor run `adb960ae-1805-4695-8c78-6dd1fbed4d2a` patched only `e2e/landing-smoke.spec.ts` inside a disposable `resplit-web` worktree, reran the targeted Playwright smoke to `5 passed`, saved patch `/Users/leokwan/.moussey/coding-patches/adb960ae-1805-4695-8c78-6dd1fbed4d2a.patch`, and removed worktree/branch/lock without touching primary checkouts. The same run's patch is now inspectable through `GET /api/coding/runs/adb960ae-1805-4695-8c78-6dd1fbed4d2a/patch` and the `/coding` `Preview Patch` button before any primary checkout apply. Spawned Nia MCP can now discover exact docs sources and run source-scoped search from worker `f34a43c5-f519-4220-a6d7-302991cbc71c`; Moussey now caches verified Nia docs source `db056160-1ab8-4d11-95da-dfeda2496fa5` plus duplicate `d61759bb-6cc1-4cd6-ae21-1d906a6ddf23` in the capability API/UI. Current public-matrix reproof run `acb0f3aa-fea5-48d7-be56-67f90ef59151` passed 26/26; failed-run handoff `ef47b4c5-ef9d-462e-8aec-a1a52fef8d63` opens the older failed run `6aca4a4b-8b36-4b65-ac6b-9037c8d914b2` as a bounded `codex-verifier` follow-up; Routing Readiness remains warning-only because Cleaner is active-neighbor.) | Studio Codex | 2026-05-24 |

**2026-05-24 C27 command-center update:** `agentic-coding-workbench` now has skill-spine operational contracts in Moussey `/coding`: skill cards expose operation mode, actual tool-call surface, and safety gate, and the new allowlisted `Skill Spine Runbook Probe` launches read-only Codex with `/vidux`, `/pilot-leo`, `/captain`, `/nia`, `/autobot-resplit-web`, Nia/OpenAI docs MCP approval overrides, and web discovery. Live run `20e844bb-120f-4ca6-8263-510c849e40c5` completed `exitCode:0` and returned the runbook, keeping delegation local and explicit while Cleaner remains a read-only neighboring surface.

**2026-05-24 C29 command-center update:** `agentic-coding-workbench` now has a hard 100+ scenario local gate in Moussey `/coding`. The new allowlisted `Agentic Workbench 100+ Scenario Gate` wraps the Vidux Browser historical smoke, proves live Vidux health plus 204 Python tests and 30 Playwright Browser scenarios, prints `scenario-count: python=204 playwright=30 total=234`, and fails below 100 scenarios. Live run `1dd77a30-23d3-440e-abf2-265bfa4a9565` completed `exitCode:0`, so the current MVP proof is real agentic test execution, not documentation.

**2026-05-24 C34 local-CI command-center update:** `agentic-coding-workbench`
now treats FirstBite local CI as a first-class lifecycle/debugger surface, not
an ad hoc `/local-ci` ritual. The operating readout command
`bash ~/Development/ai-leo/skills/local-ci/scripts/firstbite-operating-readout.sh`
captures ledger quality, fleet health, Vidux PLAN/INBOX, git state, MCP
`latest_lane_proof`, Cursor MCP visibility, and Moussey local-CI/LAN status in a
single local artifact. Verified report:
`/Users/leokwan/.agent-ledger/firstbite-operating-readout/20260524T211923Z-63931/report.json`
with `12/12` latest MCP lanes passing and `12/12` repo-declared lanes across
Resplit Web, Resplit iOS, StrongYes Web, and Moussey.

**2026-05-24 C34b repo-lifecycle update:** the local-CI manifest PRs are merged
on repo main: Resplit Web #810 (`35acd55`), Resplit iOS #752 (`a230409`),
StrongYes #994 (`bcead89`), and Moussey #7 (`c0d6d1e`). The local command
center should now treat `.firstbite/local-ci.json` as repo-owned lifecycle/CD
metadata, while keeping the active dirty checkouts' untracked mirrors until a
safe sync can replace them with tracked files.

**2026-05-25 C80 command-center update:** the stale claims-board row above is
superseded by the child plan's C79/C80 truth. `agentic-coding-workbench` now
has a retained Resplit Web source-ref branch
`codex/web-promote-reviewed-patch-current-main-20260525T184547Z-tuug6r` at
`65f654f0fbc3`, and FirstBite report
`/Users/leokwan/.agent-ledger/firstbite-local-ci-mcp/mcp-20260525T190002Z-94270/report.json`
passes `3/3` Resplit Web lanes from that branch. This is branch/source-ref
proof on Mac Studio, not fresh-main portability. UX owns the `/coding` first
viewport makeover; safe parallel work is backend/API/test/evidence, runtime
readiness, artifact normalization, and lane/source reservation semantics.
C80a also split local-CI run truth into latest run, latest completed run,
latest passing run, and active runs, so a newer detached StrongYes result no
longer erases the Resplit Web source-ref proof from the command-center API.
C80b then added runtime readiness facts to the same API: runner identity,
durable run-root freshness, Playwright browser revision/cache checks with an
`inspectionScope` that distinguishes exact source paths from primary-repo
approximations, and read-only active lane/source reservations. Live proof:
`http://127.0.0.1:4321/coding?fresh=c80b-runtime-readiness-2` loaded with zero
console/page errors after rebuild/restart; screenshot
`/tmp/moussey-c80b-runtime-readiness-2.png`.
C80d now turns that read-only model into server-side protection: local-CI
execute launches reject overlapping active lane/source reservations and atomic
lock conflicts with `409 reservation_conflict`, dry-runs and read-only inspect
remain available, and duplicate non-stale detached worker starts reject with
`409 worker_reserved` plus active owner/status metadata. C80e makes ownership
visible in the first queue strip, C80f/C80g add typed artifact metadata plus the
same duplicate-owner guard to live `/api/coding/tool-actions/run` streams, and
C80h adds backend source-proof comparison at
`/api/coding/local-ci.sourceProofComparison`. Live proof: `GET
http://127.0.0.1:4321/api/coding/local-ci` returned typed local-CI report
artifacts plus `source-proof fresh_main latest_passing
mega-resplit-ios-origin-main-integration-ui-retained-20260525T2050`; `GET
/api/coding/local-ci/artifact?...` returned `artifact.kind:"local-ci-report"` /
`overview`; a synthetic live stream lock made `POST
http://127.0.0.1:4321/api/coding/tool-actions/run` return `409
worker_reserved` / `conflictKind:"tool_action"` before execution; and
`http://127.0.0.1:4321/coding?fresh=c80h-source-proof` returned HTTP 200.

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

- [2026-05-25] `agentic-coding-workbench` completed C86 on the local base station while coordinating around parallel Moussey UX work. The `/coding` first viewport now includes `Action Locks` explaining primary command disabled/readiness reasons, and the latest FirstBite run inspector includes `Run Control` rows for terminal state, resume eligibility, cancel scope, and read-only report availability. Verification passed focused Moussey local-CI tests 28/28, `npx tsc --noEmit --pretty false`, targeted `git diff --check`, `npm run build`, LaunchAgent restart, HTTP 200 for `/coding?fresh=c86-action-locks`, and Playwright CLI desktop/mobile screenshots. Remaining child-plan work is a coherent completed-run/resumable-run/active-reservation/replay-proof pipeline plus mobile operator sequencing.

- [2026-05-25] `agentic-coding-workbench` completed C85 on the local base station. FirstBite local-CI MCP now exposes scoped `cancel_run` and `resume_run`; cancel validates current-host owned process-group metadata before signaling, and resume creates a new report/run id with `resumed_from` instead of rewriting old proof. Moussey adds capability-gated `POST /api/coding/local-ci/resume`, and live `/api/coding/local-ci` now reports `control_capabilities.cancel_run=true` and `resume_run=true`. Verification passed FirstBite MCP lint/probe, focused Moussey local-CI API tests 39/39, `npx tsc --noEmit --pretty false`, live cancel/resume smokes, Moussey build/restart, live capability proof, and live resume API proof. Remaining child-plan work is UX-owned completed-run/resume controls plus disabled-state explanation audit.

- [2026-05-25] `agentic-coding-workbench` completed C80h on the local base station. Moussey now exposes `/api/coding/local-ci.sourceProofComparison` so source-ref green, fresh-main portable, remote-main portable, dirty primary checkout, failing proof, and same-repo mixed source states are separate API facts. Verification passed local-CI route/status tests 19/19, expanded coding backend tests 52/52, `npx tsc --noEmit --pretty false`, `git diff --check`, standalone build/restart, live `/api/coding/local-ci` source-proof output, live artifact fetch `local-ci-report` / `overview`, and `/coding?fresh=c80h-source-proof` HTTP proof. Remaining child-plan work is UX-owned source-proof rendering, run-history redaction, and cancel/stop policy before the Studio control-tower pivot.

- [2026-05-25] `agentic-coding-workbench` completed C80f/C80g on the local base station. Moussey now normalizes local-CI reports/logs/xcresults and saved patch previews into typed artifact summaries/tabs, and live `/api/coding/tool-actions/run` streams now reject duplicate active owners with the same `409 worker_reserved` shape as detached workers. Verification passed focused artifact/local-CI/run/worker/tool-action tests 47/47, `npx tsc --noEmit --pretty false`, `git diff --check`, standalone build/restart, live `/api/coding/local-ci`, live artifact fetch `local-ci-report` / `overview`, `/coding?fresh=c80e-artifacts-reservations` HTTP proof, and synthetic live `409 worker_reserved` / `tool_action` proof with cleanup. Next child-plan work is productizing the typed artifact inspector, source-ref/fresh-main/remote-main comparison, run-history redaction, and cancel/stop policy before the Studio control-tower pivot.

- [2026-05-25] `agentic-coding-workbench` completed C80d on the local base station. Moussey now enforces lane/source reservations before launching local-CI execute work and rejects duplicate non-stale detached workers before spawning another agent, while keeping dry-run/status/artifact reads available for operators. Verification passed focused reservation/local-CI/worker tests 34/34, `npx tsc --noEmit --pretty false`, `git diff --check`, standalone build/restart, live `/api/coding/local-ci`, synthetic live `409 reservation_conflict`, and `/coding?fresh=c80c-reservations` HTTP proof. Next child-plan work stays on the UX/product queue strip, artifact normalization, and Studio control-tower pivot.

- [2026-05-25] `agentic-coding-workbench` completed C53 on the local base station. Ollama upgraded to `0.24.0`, `gemma4:e4b` is installed, `qwen3:8b` is now the default local chat/coding model for thinking-capable requests, and Aider is wrapped as a detached probe-only worker before edit authority. Live proof: `http://127.0.0.1:4321/coding?fresh=c53-aider-gemma4-qwen3`, worker `http://127.0.0.1:4321/api/coding/workers/5f9e07f8-be45-4443-a657-5906b25efc68`, and owning evidence `projects/agentic-coding-workbench/evidence/2026-05-25-c53-aider-gemma4-qwen3.md`. Next finish-line step is the Aider disposable-worktree patch worker wired to local-CI/autobot failed-run handoffs.
- [2026-05-24] `agentic-coding-workbench` completed C33 Active Work Map on the local base station. Moussey `/coding` now uses `/ledger` health/brief scripts to show cross-repo activity for Moussey, Vidux, Resplit Web, Resplit iOS, and StrongYes before Leo fires local CI or Codex workers. Live proof: `http://127.0.0.1:4321/coding?fresh=20260524-active-work-map` renders `Active Work Map`, `Agent Ledger`, repo cards, and `12/12 pass` with zero browser console/page errors; `/api/coding/capabilities` reports `4/5 repo ledgers healthy` and keeps Resplit iOS warning visible instead of flattening it. Boundary remains local-only: Ledger is activity, while owning PLAN.md files, tests, PRs, local-CI reports, and run artifacts remain authority.
- [2026-05-24] `agentic-coding-workbench` completed C34 Agent Worker Monitor on the local base station. Moussey `/coding` now has a visible detached-agent queue above Recent runs, backed by `GET :4321/api/coding/workers?limit=8`, with running/completed/failed/stale status, status URLs, log bytes, duration, and Codex LB route hints. Live proof: `http://127.0.0.1:4321/coding?fresh=20260524-worker-queue` shows `Agent workers`, Codex LB hints, Active Work Map, and `12/12 pass` with zero browser console/page errors; `/api/coding/local-ci` reports `12/12` passing and `0` active Xcode processes.
- [2026-05-24] `agentic-coding-workbench` completed C35 Worker Final Message Inspector on the local base station. Worker status now exposes the Codex `--output-last-message` artifact as bounded `finalMessage` data, and `/coding` displays the agent conclusion before raw log tails when Leo clicks a worker. Live proof: `GET :4321/api/coding/workers/891c5548-41de-4737-bf2a-7128a159aad3` returns `finalBytes: 2144` with `Probe result...`, and `http://127.0.0.1:4321/coding?fresh=20260524-worker-final-message` shows `final message:` plus `log tail:` with zero browser console/page errors.
- [2026-05-24] `agentic-coding-workbench` completed C36 HF Inference Provider Routing Probe on the local base station. Moussey `/coding` now has a ready `HF Inference Provider Routing Probe` action that launches a bounded spawned Codex session, verifies Hugging Face's OpenAI-compatible router endpoint, checks only the `HF_TOKEN` env-key boundary, and refuses token-backed inference. Live worker `63671234-f9bb-4d98-a35b-97b1670b2d8f` completed `exitCode:0` after 79257ms and returned `https://router.huggingface.co/v1`, `HF_TOKEN configured: no/unknown`, and source-backed provider/model candidates. Live proof: `http://127.0.0.1:4321/coding?fresh=20260524-hf-routing` plus `GET :4321/api/coding/workers/63671234-f9bb-4d98-a35b-97b1670b2d8f`; browser proof screenshot `/tmp/moussey-c36-hf-routing-final-message-ui.png` had zero console/page errors.
- [2026-05-24] `agentic-coding-workbench` completed C37 HF Nia Source Registry on the local base station. Nia indexed the official Hugging Face Inference Providers docs as source `236b33f1-f264-440d-84d4-cb903650090e` with 74 pages, and Moussey now exposes that route as a verified source before any HF token-backed inference. Live worker `9917c38f-fe5c-4bd8-a858-83f1801fc969` rechecked the cached source from inside Codex, ran source-scoped Nia search for the router and `HF_TOKEN` boundary, completed `exitCode:0`, and refused model calls. Live proof: `http://127.0.0.1:4321/coding?fresh=20260524-hf-nia-source` plus `GET :4321/api/coding/workers/9917c38f-fe5c-4bd8-a858-83f1801fc969`; browser proof screenshot `/tmp/moussey-c37-hf-nia-source-ui.png` had zero console errors. Aggregate Routing Readiness remains honest: HF-specific route is ready, but the global panel is still blocked by an older generic failed worker that should be rerun or scoped separately.
- [2026-05-24] `agentic-coding-workbench` completed C38 fresh Skill/MCP/cloud routing reproof on the local base station. Codex usage recovered to `3 usable · 0 rate limited`, so Moussey launched worker `40e386ae-f4df-4784-b9f4-a574761b694f` for the generic routing probe. It completed `exitCode:0` and proved the full spawned-agent route: Nia source-scoped search, official OpenAI docs MCP config facts, Hugging Face router docs, configured provider/MCP surface names, and a routing table. Live `/api/coding/capabilities` now reports `10 ready · 2 warning · 0 blocked · 0 unknown`; remaining warnings are Ledger active-work/neighbor state, not routing failure. Live proof: `http://127.0.0.1:4321/coding?fresh=20260524-routing-reproof` plus `GET :4321/api/coding/workers/40e386ae-f4df-4784-b9f4-a574761b694f`; screenshot `/tmp/moussey-c38-routing-reproof-ui.png` had zero console errors. The worker's recommended next slice is a first-class read-only `/coding/routing` panel for skill owner, MCP server, source id, approval mode, and allowed next action.
- [2026-05-24] `agentic-coding-workbench` completed C39 Routing Map cockpit panel on the local base station. Moussey `/coding` now shows a first-class read-only `Routing Map` panel that explains, per route, the owning skill/persona, where it runs, the execution surface, source ids, approval mode, allowed action, safety gate, and next action. Live proof: `http://127.0.0.1:4321/coding?fresh=20260524-routing-map` plus `GET :4321/api/coding/capabilities` reporting `mapCount: 9`, HF source `huggingface-inference-providers:236b33f1-f264-440d-84d4-cb903650090e`, Resplit owner `/autobot-resplit-web`, and Vidux handoff surface `Vidux loopback handoff into Moussey`; screenshot `/tmp/moussey-c39-routing-map-ui.png` had zero console errors.
- [2026-05-24] `agentic-coding-workbench` completed C40 Model Routes planner on the local base station. Moussey `/coding` now shows local model/debugger state beside the routing map: live Ollama inventory, current selected model, Qwen/Gemma local install candidates, HF-router Qwen3 Coder/DeepSeek/Kimi candidates, token/install gates, and the explanation that current `qwen2.5:0.5b` cannot use Ollama `think`, so deeper local reasoning needs a thinking-capable model such as Qwen3. Live proof: `http://127.0.0.1:4321/coding?fresh=20260524-model-routes`; `GET :4321/api/coding/capabilities` reports installed local models `["qwen2.5:0.5b"]`, `local-qwen3` install-needed, `local-gemma3` install-needed, HF candidates token-needed, and source `nia:huggingface-inference-providers:236b33f1-f264-440d-84d4-cb903650090e`; screenshot `/tmp/moussey-c40-model-routes-ui.png` had zero console errors.
- [2026-05-24] `agentic-coding-workbench` completed C42 HF Model Dry-Run Gate on the local base station. Moussey `/coding` now has a ready no-spend `HF Model Dry-Run Gate` action that reports `https://router.huggingface.co/v1`, verified source `huggingface-inference-providers:236b33f1-f264-440d-84d4-cb903650090e`, top route candidates Qwen/Qwen3 Coder, Gemma 3, DeepSeek V3.1, and Kimi K2, and exits without passing `HF_TOKEN` or making provider calls. Live proof: `http://127.0.0.1:4321/coding?fresh=20260524-hf-dry-run`; `POST :4321/api/coding/tool-actions/run` with `hf-router-model-dry-run` returns `status: token-needed` and `exitCode:0`; screenshot `/tmp/moussey-c41-hf-model-dry-run-ui.png` had zero console errors.
- [2026-05-24] `agentic-coding-workbench` completed C41 Manifest-backed local-CI lane launcher matrix on the local base station. Moussey `/coding` now ingests the FirstBite MCP `list_lanes` manifest catalog correctly, shows all 12 repo-declared lanes with host/executor, latest proof, report/log paths, Xcode lock state, and requirements, and can dry-run a FirstBite group from the browser/API without redefining lane contracts. Live proof: `http://127.0.0.1:4321/coding?fresh=20260524-local-ci-matrix`; `GET :4321/api/coding/local-ci` reports `12/12` latest lanes passing, `laneCatalogLength: 12`, clear Xcode lock, and host `Leos-Mac-Studio-10442.local`; dry-run group `critical_fast` produced report `/Users/leokwan/.agent-ledger/firstbite-local-ci-mcp/mcp-20260524T223426Z-90171/report.json`.
- [2026-05-25] `agentic-coding-workbench` completed C50 IDE cockpit clarity pass on the local base station. Moussey `/coding` now starts with the current base-station goal, debugger/usage state, and four primary actions for FirstBite local CI, Resplit autobot, Nia/Codex delegation, and the 100+ scenario gate before the detailed local-CI, worker, run-history, handoff, model-route, and advanced substrate panels. Live proof: `http://127.0.0.1:4321/coding?fresh=c50-ide-cockpit-final`; screenshot `/tmp/moussey-c50-ide-cockpit-ui.png`; verification passed brain-dispatcher 161/161, TypeScript, build/restart, live health, and browser proof. Cleaner-owned files were not edited.
- [2026-05-25] `agentic-coding-workbench` completed C52 local coding-agent toolchain inventory on the local base station. Installed/surfaced aider, opencode, Goose, Continue, and Cline; pulled Qwen3/Gemma/DeepSeek local Ollama candidates; and proved Qwen3 `think:true` API plumbing. Moussey `/coding` now shows `Local Agent Toolchain` as capability truth, while edit authority remains blocked until an allowlisted disposable-worktree worker wrapper exists. Live proof: `http://127.0.0.1:4321/coding?fresh=c51-agent-toolchain`; screenshot `/tmp/moussey-c51-agent-toolchain-verified.png`; evidence `projects/agentic-coding-workbench/evidence/2026-05-25-local-toolchain-install.md`.

- [2026-05-22] Mega-plan created. Phase 0 + Phase 1 unblocked. moussey-voice-agent already has its own active claims board. Phase 0 brain-dispatcher-shared and intent-router-shared still need their own PLAN.md files — next claimable work after this one is "write brain-dispatcher-shared/PLAN.md" since voice-agent V4 depends on it.
- [2026-05-24] Added `agentic-coding-workbench` as the coding/test execution child plan for Leo's clarified MVP. Moussey now has `/coding` local-smoke lane mode: fetches `origin/main`, creates a `resplit-web` worktree, claims `PW_PORT`, runs isolated `npm ci --include=dev`, builds Next, starts Next, runs targeted Playwright, and tears down server/worktree/branch/lock. Verification passed in Moussey unit/build/UI proof; live run `5eae7ddc-5afd-496a-b355-c9159df0097f` reached Playwright on `resplit-web` `a7aa458`, surfaced `#globe` missing from landing smoke, and cleaned up with `teardownOk:true`.
- [2026-05-24] Added coding capability substrate proof. Moussey `/coding` now shows a read-only catalog for active skill symlinks, owned skill source paths, and Codex MCP server config names/commands/env-key names only. Live proof found 8/8 target skills (`autobot-resplit-web`, `vidux`, `pilot-leo`, `amp`, `auto`, `captain`, `nia`, `moussey`) and 5 MCP servers (`everything`, `figma`, `nia`, `node_repl`, `openaiDeveloperDocs`); Playwright saw the panel and `nia-mcp-server` at `http://127.0.0.1:4321/coding` with zero console/page errors.
- [2026-05-24] Started the Vidux/Moussey harmony audit for `agentic-coding-workbench` C12. It checked Moussey pings, LAN health, provider readiness, capability substrate, git heads, and child-plan status until both sides had current evidence of synced/adapted/refreshed workflows.
- [2026-05-24] `agentic-text-chat` is done for the local MVP: `/chat` streams `/api/chat/ask`, persists/reopens sessions, injects recent context, handles attachments, produces LAN read-only share links, surfaces provider health/local reasoning, and stages chat turns into `/coding` handoffs. Verification in child plan: 80 brain-dispatcher/chat/coding tests, Moussey build, health, Vidux health, live local SSE, and Playwright screenshots.
- [2026-05-24] `agentic-text-chat` completed T13 as a small local-model truth hardening pass. `/api/chat/providers` now reports selected Ollama model, installed local model inventory, reasoning budgets, and whether Ollama `think` is actually sent; live Studio state is `qwen2.5:0.5b` only, so Deep increases context/output budget but still shows `thinking unavailable` until a thinking-capable model is installed. Verification passed `npm run test:brain-dispatcher` 122/122, Cleaner 116/116, TypeScript, live provider/health APIs, and browser proof at `http://127.0.0.1:4321/chat`.
- [2026-05-24] `agentic-coding-workbench` completed C9: `/coding` now has a `codex-skills-probe` mode that launches `codex exec --ephemeral --sandbox read-only` against an isolated `resplit-web` worktree. Live run `d2c80ba8-8a9b-4bdb-a530-8c06178f4844` used Codex v0.130.0 / `gpt-5.5` / `xhigh`, loaded `/vidux`, `/pilot-leo`, `/captain`, `/nia`, and `/autobot-resplit-web`, confirmed `e2e/landing-smoke.spec.ts`, returned the next action, and completed teardown with `exitCode:0`, `teardownOk:true`. Next frontier is a bounded verifier/edit lane, not arbitrary browser shell execution.
- [2026-05-24] C12 harmony pass saved the Moussey implementation and Vidux plan state together. Moussey pushed `5fa955a` with the read-only Codex skill probe lane, harmony run `cb733047-486a-4f3e-97b8-91a943e5f739` repeated the live lane at `PW_PORT=3111` with `exitCode:0` and `teardownOk:true`, and agreement ping `bae1843a-5e4d-4631-92e4-bd5b0e564bdf` records the shared state in Moussey's cross-Mac feed. A later disk check found no active Codex automation for the listener.
- [2026-05-24] `agentic-coding-workbench` completed C13a: Moussey `60160e7` adds a bounded `codex-verifier` scaffold that prepares the local-server lane, then runs `codex exec` with workspace-write limited to the disposable worktree and instructions to keep tracked source clean. Follow-ups `0e7461e`, `d1b0a37`, and `971fcae` expose the `Codex Verifier` button in `/coding`, serialize lane-run tests, and set literal `maxDuration = 1800` for long build/verifier sessions. Verified with focused coding tests 14/14, route tests 7/7, full brain-dispatcher suite 90/90, TypeScript, diff checks, standalone rebuild/restart, and Playwright proof at `/coding`. Live verifier run proof and any source-edit gate remain separate follow-ups.
- [2026-05-24] `agentic-coding-workbench` completed C13b live verifier proof: Moussey commit `44f4fae` preserves coding env overrides in the LaunchAgent, can link primary `node_modules` for fast isolated proofs, builds with `npx next build --webpack`, pins background Codex provider to `openai`, and uses a browser-capable sandbox for nested Playwright. Live run `c8212526-7f44-4f38-b778-7b413646a3fc` started `resplit-web` at `http://127.0.0.1:3110`, nested Codex ran the landing smoke, found the stale `#globe` assertion (4 passed / 1 failed), kept tracked source clean, and returned `teardownOk:true`.
- [2026-05-24] `agentic-coding-workbench` started C14 for Leo's next frontier: spawned agents should prove `/captain`, `/pilot-leo`, `/nia`, skill symlinks, configured MCP servers, web/docs lookup, and cloud-provider readiness from inside the lane. Foreground evidence: Nia can be called but has no indexed resource for this local surface yet; OpenAI Codex config supports `mcp_servers`, `model_provider`, `features.multi_agent`, and `web_search`; Hugging Face Inference Providers can be reached through an OpenAI-compatible router when a token is present.
- [2026-05-24] `agentic-coding-workbench` completed C14: Moussey commits `3994f53`, `90717a2`, and `5339f62` add the `Tool Capability Probe` lane, transient `git fetch` retry, bounded prompt, 24 KB SSE cap, and `--output-last-message`. Live proof `dca465f4-b944-4791-947e-d179c767effb` launched nested Codex read-only from an isolated `resplit-web` worktree, emitted `stream-truncated`, appended `[codex:last-message]`, reported skill/MCP/web/cloud readiness names without secrets, preserved the Nia `user cancelled MCP tool call` boundary, and cleaned branch/worktree/port lock with `exitCode:0` and `teardownOk:true`.
- [2026-05-24T08:12Z] `agentic-coding-workbench` completed C14c: Moussey `/coding` now includes a Cleaner-aware capability coordination signal. The live capability API resolves the real repo root from the standalone server, reports Cleaner as `active-neighbor` with 7 tracked and 10 untracked dirty paths, and keeps coding-workbench edits away from `app/cleaner`, `lib/cleaner`, and `app/api/cleaner` while that lane is active.
- [2026-05-24T09:02Z] `agentic-coding-workbench` completed C15: Moussey `/coding` now shows a tool/action readiness matrix rather than a vague MCP inventory. Live `/api/coding/capabilities` reports Codex model/provider/reasoning/web-search/multi-agent config, provider metadata without secrets, Captain audit as a ready local command, Nia/OpenAI docs as foreground Codex MCP actions, spawned Codex probe reuse, Codex web-search configuration, and the existing Cleaner `active-neighbor` warning. Verification passed focused tests 6/6, `npm run test:brain-dispatcher` 97/97, `npm run test:cleaner` 96/96, TypeScript, Captain audit, standalone build/restart, and live health/API checks.
- [2026-05-24] `agentic-coding-workbench` completed C16 and cooperated with Cleaner. `/coding` now has runnable `Run Action` controls backed by `POST /api/coding/tool-actions/run`; live Captain audit and read-only Codex session tool-call probe both completed `exitCode:0`. The shared build was restored by a tiny Cleaner review-memory bridge fix, verified by Cleaner tests 97/97, brain-dispatcher tests 105/105, TypeScript, standalone build/restart, live `:4321` health, and live capabilities/API proof.
- [2026-05-24] `agentic-coding-workbench` completed C17/C18. The Nia child-session retry proved `mcp_servers.nia.default_tools_approval_mode="auto"` reaches spawned Codex but does not clear the `user cancelled MCP tool call` blocker. The useful product step landed: `/coding` can now run `resplit-web-autobot-public-matrix`, and live run `99331276-c266-490d-a7cf-deb35880238a` passed 26/26 Resplit public-surface cells through `/autobot-resplit-web --public-only`. Local inspection link: `http://127.0.0.1:4321/coding`.
- [2026-05-24] `agentic-coding-workbench` completed C8. Moussey now folds `~/.moussey/coding-runs.jsonl` into `GET /api/coding/runs?limit=N` and a visible `/coding` `Recent runs` dashboard. Live Safari proof showed 12 recent runs and clicking the latest Resplit public-matrix run loaded its command, cwd, `exit: 0`, duration, and 26/26 stdout tail into the terminal. Local inspection links: `http://127.0.0.1:4321/coding` and `http://127.0.0.1:4321/api/coding/runs?limit=5`.
- [2026-05-24] `agentic-coding-workbench` completed C10 while cooperating with Cleaner. Vidux plan pages now have a local `Code` button backed by loopback-only `POST /api/coding-handoff`, which stages a `source: "vidux"` Moussey handoff and opens `/coding?handoff=<id>`. Live proof created handoff `5d77ae10-877f-4087-b866-b245161f62b9`; browser proof verified `VIDUX HANDOFF` plus `Run Status Lane` at `http://127.0.0.1:4321/coding?handoff=5d77ae10-877f-4087-b866-b245161f62b9` and the Vidux `Code` button at `http://127.0.0.1:7191/?plan=vidux%2Fprojects%2Fagentic-coding-workbench%2FPLAN.md`. Verification passed Moussey handoff tests 7/7, brain-dispatcher tests 112/112, TypeScript, Vidux browser-server tests 32/32, standalone rebuild/restart, Vidux restart, and live health checks.
- [2026-05-24] `agentic-coding-workbench` completed C14b while working alongside Cleaner. Moussey `/coding` now has detached log-backed workers for allowlisted tool actions: `POST /api/coding/workers` starts a worker, `GET /api/coding/workers/<id>` returns bounded status/log tail, and completed workers fold back into `GET /api/coding/runs?limit=N`. Live worker `c64bd3d3-8d17-462a-a1d9-b0e0656b3500` ran the Codex session tool-call probe to `exitCode:0` after 148678ms, preserved a 132577-byte log, confirmed the current Nia child-session cancellation boundary, and left Cleaner-owned files untouched. Local links: `http://127.0.0.1:4321/coding`, `http://127.0.0.1:4321/api/coding/workers?limit=5`, and `http://127.0.0.1:4321/api/coding/workers/c64bd3d3-8d17-462a-a1d9-b0e0656b3500`.
- [2026-05-24] `agentic-coding-workbench` completed C19 while working alongside Cleaner. `/coding` now has a detached Skill/MCP/cloud routing worker that loads `/captain`, `/pilot-leo`, `/nia`, and `/vidux`, checks Nia/OpenAI docs/web/provider surfaces in order, and returns a routing table for future command-center work. Foreground Nia verified scoped MCP docs from `https://docs.trynia.ai`; live worker `af1aa03f-7ad9-4af2-a85c-15d847c15e11` completed `exitCode:0` after 216279ms and preserved the spawned Nia blocker as `user cancelled MCP tool call`. Verification passed focused tests 17/17, brain-dispatcher 115/115, Cleaner 109/109, TypeScript, diff checks, standalone rebuild/restart, live `/api/health`, live capabilities, worker status, and UI proof at `http://127.0.0.1:4321/coding`.
- [2026-05-24] `agentic-coding-workbench` completed C20 while working alongside Cleaner. The Skill/MCP/cloud routing worker now launches child Codex with explicit per-tool MCP approval overrides for Nia and OpenAI docs instead of broad `auto`; live worker `8daa6fd7-c110-4a19-83ae-60305d98bb6f` completed `exitCode:0` after 149606ms and returned `Nia MCP: callable`. The remaining follow-up is source-id-aware Nia search/indexing, not approval cancellation. Verification passed focused tests 17/17, TypeScript, brain-dispatcher 115/115, Cleaner 116/116, diff checks, standalone rebuild/restart, live `/api/health`, live capabilities, live worker/run-history APIs, and UI proof at `http://127.0.0.1:4321/coding`.
- [2026-05-24] `agentic-coding-workbench` completed C21 while working alongside Cleaner. `/api/coding/capabilities` and `/coding` now expose Routing Readiness for skills, MCP, Codex routing, allowlisted actions, latest routing probe, and Cleaner state from the shared capability catalog. Live readiness is `5 ready · 1 warning · 0 blocked · 0 unknown`; the only warning is Cleaner `active-neighbor`, so the command-center path is ready for the next bounded coding/tool action without crossing Cleaner ownership. Verification passed focused tests 6/6, TypeScript, brain-dispatcher 115/115, Cleaner 116/116, diff checks, standalone rebuild/restart, live `/api/health`, live capabilities, and Playwright UI proof at `http://127.0.0.1:4321/coding`.
- [2026-05-24] `agentic-coding-workbench` completed C22 while working alongside Cleaner. `/coding` now has a detached `Nia Source Routing Probe` that discovers exact Nia docs source ids and runs source-scoped search from inside the spawned Codex worker; live worker `f34a43c5-f519-4220-a6d7-302991cbc71c` selected `https://docs.trynia.ai` source `db056160-1ab8-4d11-95da-dfeda2496fa5`, reported duplicate source `d61759bb-6cc1-4cd6-ae21-1d906a6ddf23`, and completed `exitCode:0`. Live readiness is now `6 ready · 1 warning · 0 blocked · 0 unknown`; the warning remains Cleaner `active-neighbor`. Verification passed focused tests 19/19, TypeScript, brain-dispatcher 117/117, Cleaner 116/116, diff checks, standalone rebuild/restart, live health/capabilities, live worker status, and browser proof at `http://127.0.0.1:4321/coding`.
- [2026-05-24] `agentic-coding-workbench` completed C23 while working alongside Cleaner. `/coding` and `/api/coding/capabilities` now expose a cached Source Registry: verified Nia Docs source `db056160-1ab8-4d11-95da-dfeda2496fa5`, duplicate `d61759bb-6cc1-4cd6-ae21-1d906a6ddf23`, OpenAI docs MCP route, and Hugging Face Inference Providers as `discovery-needed`. Live readiness is now `7 ready · 1 warning · 0 blocked · 0 unknown`; the warning remains Cleaner `active-neighbor`. Verification passed focused tests 22/22, TypeScript, brain-dispatcher 117/117, Cleaner 116/116, diff checks, standalone rebuild/restart, live health/capabilities, and browser proof at `http://127.0.0.1:4321/coding`.
- [2026-05-24] `agentic-coding-workbench` completed C24 current-session reproof while working alongside Cleaner. Live run `acb0f3aa-fea5-48d7-be56-67f90ef59151` executed `/Users/leokwan/bin/autobot-resplit-web --public-only` through Moussey's ready `resplit-web-autobot-public-matrix` tool action, passed 26/26 public-surface cells, and is visible through `http://127.0.0.1:4321/api/coding/runs?limit=5`. Cleaner-owned files were not edited.
- [2026-05-24] `agentic-coding-workbench` completed C6e/C25 while working alongside Cleaner. Failed local coding runs now stage run-sourced `/coding` handoffs through `POST /api/coding/runs/handoff`; live handoff `ef47b4c5-ef9d-462e-8aec-a1a52fef8d63` wraps failed run `6aca4a4b-8b36-4b65-ac6b-9037c8d914b2` with command/cwd/status/exit/stdout/stderr tails and a proposed `codex-verifier` follow-up. Verification passed focused tests 11/11, TypeScript, brain-dispatcher 126/126, Cleaner 116/116, standalone build/restart, live health, live handoff POST, and browser proof at `http://127.0.0.1:4321/coding?handoff=ef47b4c5-ef9d-462e-8aec-a1a52fef8d63`.
- [2026-05-24] `agentic-coding-workbench` completed C13c scaffold, not yet live editor-run proof. Moussey now has a separate `codex-editor` button/mode that prepares the same isolated Resplit Web build/start/Playwright lane, permits minimal source edits only inside the disposable worktree, forbids primary-checkout/Cleaner/cross-Mac/prod/money/human mutation, then runs `git diff --check`, captures patch stats, saves `git diff --binary` to `~/.moussey/coding-patches/<run>.patch`, stores patch metadata in local run history, and tears down the lane. Verification passed focused tests 26/26, TypeScript, brain-dispatcher 128/128, Cleaner 116/116, build/restart, live health, live `/coding` HTML containing `Codex Editor`, and live editor preflight; live C13d remains the next proof.
- [2026-05-24] `agentic-coding-workbench` completed C13d live editor-run proof while working alongside Cleaner. Moussey run `adb960ae-1805-4695-8c78-6dd1fbed4d2a` built and served `resplit-web` from disposable worktree `web-c13d-live-editor-20260524T180814Z-fhy9pj`, launched nested Codex, reproduced the stale `#globe` landing-smoke failure, patched only `e2e/landing-smoke.spec.ts`, reran the exact smoke to `5 passed`, saved `/Users/leokwan/.moussey/coding-patches/adb960ae-1805-4695-8c78-6dd1fbed4d2a.patch`, recorded patch metadata in `GET http://127.0.0.1:4321/api/coding/runs?limit=3`, and tore down the server/worktree/branch/port lock with `teardownOk:true`. Primary checkouts and Cleaner files were not edited; applying the patch to primary `resplit-web` is deferred because that checkout is currently a dirty gone branch and `git apply --check` does not apply there.
- [2026-05-24] `agentic-coding-workbench` completed C26 while working alongside Cleaner. `/coding` now has guarded read-only patch preview for patch-bearing editor runs: `GET http://127.0.0.1:4321/api/coding/runs/adb960ae-1805-4695-8c78-6dd1fbed4d2a/patch` returns the saved `1673` byte `e2e/landing-smoke.spec.ts` diff, and selecting the recent `codex-editor` run shows a `Preview Patch` button. Verification passed focused patch/workbench route tests 9/9, TypeScript, brain-dispatcher 132/132, Cleaner 116/116, diff checks, build/restart, live health/API checks, and Chrome UI proof `/tmp/moussey-c26-patch-preview-ui.png` with zero console/page errors.
- [2026-05-24] `agentic-coding-workbench` completed C27 while working alongside Cleaner. `/coding` now exposes skill operational contracts (`operationMode`, `toolCallSurface`, `safetyGate`) and an allowlisted `Skill Spine Runbook Probe` that fired a read-only Codex session with the local skill spine plus Nia/OpenAI docs/web routing. Live run `20e844bb-120f-4ca6-8263-510c849e40c5` completed `exitCode:0` after 187232ms and returned the skill/source/tool-surface runbook. Verification passed focused tests 21/21, TypeScript, brain-dispatcher 134/134, Cleaner 116/116, diff checks, build/restart, live `/api/health`, live `/api/coding/capabilities` at `7 ready · 1 warning · 0 blocked · 0 unknown`, and Playwright UI proof `/tmp/moussey-c27-skill-spine-ui.png` with zero console/page errors.
- [2026-05-24] `agentic-coding-workbench` completed C28 while working alongside Cleaner. `/coding` now has a real Vidux Browser historical smoke action, not just docs: `vidux-browser-historical-smoke` runs live Vidux health, 204 Python contract/browser-server tests, and 30 Playwright Browser scenarios from a fixed local script. First proof caught and fixed the iPhone auto-refresh artifact selection path in `browser/tests/e2e/smoke.spec.ts`; final live Moussey endpoint run `ec2607f0-77f5-41a0-99fb-6538d0b25320` completed `exitCode:0` after 137305ms. Verification passed focused Moussey tests 23/23, TypeScript, brain-dispatcher 136/136, Cleaner 116/116, diff checks, build/restart, live health/capabilities, direct bundled smoke, live `/api/coding/tool-actions/run` SSE path, and UI proof `/tmp/moussey-c28-vidux-browser-smoke-ui.png` with zero console/page errors. Local links: `http://127.0.0.1:4321/coding`, `http://127.0.0.1:4321/api/coding/runs?limit=5`, `http://127.0.0.1:7191`.
- [2026-05-24] `agentic-coding-workbench` completed C29 while working alongside Cleaner. `/coding` now exposes `Agentic Workbench 100+ Scenario Gate`, a local allowlisted action that wraps the Vidux Browser historical smoke and fails unless it executes at least 100 scenarios. Direct and live endpoint proof both passed with `scenario-count: python=204 playwright=30 total=234`; live run `1dd77a30-23d3-440e-abf2-265bfa4a9565` completed `exitCode:0` after 101923ms and is visible through `http://127.0.0.1:4321/api/coding/runs?limit=5`. Verification passed focused Moussey tests 25/25, TypeScript, brain-dispatcher 138/138, Cleaner 124/124, diff checks, build/restart, live `/api/health`, live `/api/coding/capabilities`, direct gate script, and UI proof `/tmp/moussey-c29-agentic-workbench-gate-ui.png` with zero console/page errors.
- [2026-05-24] `agentic-coding-workbench` completed C30 cockpit/ledger UX pass while working alongside Cleaner. Leo called the `/coding` UX confusing, so Moussey now foregrounds the local command-center MVP as a cockpit: mission, Run Now, Debugger, Local Usage, Agent Ledger, and primary coding actions are visible before the collapsed advanced substrate. The capability API now exposes read-only Agent Ledger health/brief data, and Routing Readiness can show the latest detached worker as blocked by a real Codex usage-limit failure. The scoped Nia prompt was tightened to discover `docs.trynia.ai` first and perform source-scoped search; direct Codex proved Nia MCP can be called with explicit approval overrides, but live worker `1aa06b50-49f8-473a-961d-c6a46fef3463` hit Codex account/quota limits before completing. Verification: focused Moussey tests 23/23, TypeScript, Moussey diff check, standalone build/restart, live `/api/health`, live `/api/coding/capabilities`, and Safari proof at `http://127.0.0.1:4321/coding?fresh=20260524-1645`.
- [2026-05-24] `agentic-coding-workbench` completed C31 Codex usage/debugger pass while working alongside Cleaner. Moussey `/coding` now shows local Codex LB usage next to the debugger and run history: live `/api/coding/capabilities` reports `2 usable · 1 rate limited · best firstbitelabs@gmail.com 75% 5h remaining`, while `/api/coding/local-ci` reports `12` passing lanes, `0` failing lanes, `0` stale lanes, and `0` outside Xcode jobs. This closes the immediate "why did the worker fail so fast?" visibility gap: C30's latest worker was usage-blocked, and C31 makes account/quota state visible before Leo fires another local coding agent. Verification: focused capability tests 7/7, TypeScript, Moussey diff check, cleared stale `.next` after a false Turbopack cache typecheck failure, standalone build/restart, live health/capabilities/local-CI APIs, and Safari proof at `http://127.0.0.1:4321/coding?fresh=20260524-usage2`.
- [2026-05-24] `agentic-coding-workbench` completed C32 Codex LB worker route hint. Detached Codex workers now store/log a sanitized `codexRoute` with recommended account, usable/rate-limited counts, and `hardPinned:false`; the local Moussey LaunchAgent now persists `MOUSSEY_CODEX_MODEL_PROVIDER=codex-lb`; current live proof reports `2 usable · 1 rate limited · best firstbitelabs@gmail.com 72% 5h remaining`, local CI `12` passing lanes, and browser proof at `http://127.0.0.1:4321/coding?fresh=20260524-route-hint`. Live workers `891c5548-41de-4737-bf2a-7128a159aad3` and `48f6bb5a-0607-475d-ac60-43cc06a8ab9e` both completed `exitCode:0` through `codex-lb`. The hard boundary remains honest: `codex-lb` final account selection is observed/recommended from Moussey, not guaranteed pinned by a supported CLI control.
- [2026-05-24] `agentic-coding-workbench` completed C43 FirstBite run artifact inspector. `/coding` now turns a local-CI run into a debugger panel: latest run summary, per-lane result cards, and report/log buttons backed by guarded artifact reads under `~/.agent-ledger/firstbite-local-ci-mcp`. Live proof: `http://127.0.0.1:4321/coding?fresh=20260524-local-ci-artifact`; dry-run `resplit_web_unit` wrote report `/Users/leokwan/.agent-ledger/firstbite-local-ci-mcp/mcp-20260524T224414Z-24023/report.json`, and `GET :4321/api/coding/local-ci/artifact?path=...` returned the report with `bytesRead:1129`, `truncated:false`. Verification passed artifact route tests 3/3, brain-dispatcher 155/155, diff check, standalone build/restart, live health/artifact APIs, and Playwright proof with zero console errors. Screenshot: `/tmp/moussey-c43-local-ci-artifact-inspector-ui.png`. Cleaner-owned files were not edited.
- [2026-05-24] `agentic-coding-workbench` completed C44 FirstBite lane-to-verifier handoff. `/coding` can now turn a FirstBite local-CI lane result into a bounded local verifier handoff before edit authority: `POST :4321/api/coding/local-ci/handoff` validates run/lane ids and FirstBite report/log paths, then creates a `source:"run"` handoff with `proposedAction:"codex-verifier"`. Live proof: browser dry-ran `resplit_web_unit`, clicked `Handoff`, and opened `http://127.0.0.1:4321/coding?handoff=d4d6800a-838a-40a8-8418-f4de8407e835`; route smoke also created `local-ci-resplit_web_unit` handoff `d01deeb4-9898-4551-a85c-1f3765cd3b7e`. Verification passed local-CI route tests 5/5, brain-dispatcher 157/157, diff check, standalone build/restart, live health/handoff APIs, and Playwright proof with zero console errors. Screenshot: `/tmp/moussey-c44-local-ci-handoff-ui.png`. Cleaner-owned files were not edited.

## Where things live

- This mega-plan: `~/Development/vidux/projects/agentic-command-center/PLAN.md`
- Sub-project plans: `~/Development/vidux/projects/<name>/PLAN.md`
- Cross-Mac infra: `~/Development/moussey/` (TypeScript/Next.js)
- Voxtral TTS: `~/.local/bin/mlx_audio.server` (per-Mac LaunchAgent)
- Skill index: `~/.claude/skills/` → `~/Development/ai/skills/` (shared) + `~/Development/ai-leo/skills/` (private overlay)
- Audit logs: `~/.moussey/*-events.jsonl`
- Kill switches: `~/.moussey/agent-disabled` (master), `~/.moussey/lan-triggers-disabled` (trigger-claude only)


---

## PSA — 2026-05-26 — Fleet UX/UI lane split codified

- **Claude Code owns ALL UX/UI work fleet-wide.** Codex agents must stay on backend / logic / lanes / workers / API.
- **Disambiguator:** "is this rendered to a human?" → Claude. "Does this read/write data, run a CLI, or expose an HTTP endpoint?" → Codex.
- **Canonical visualization layer:** [Litty](file:///Users/leokwan/Development/litty) at `http://localhost:4400` (the operator cockpit). Federates moussey's `/api/coding/*` APIs. Replaces the 12,062-line `moussey/app/coding/page.tsx` rot.
- **15 routes shipped 2026-05-26:** `/`, `/lanes`, `/lanes/[laneId]`, `/runs`, `/runs/[runId]`, `/runs/[runId]/patch`, `/runs/[runId]/stream`, `/workers`, `/workers/[workerId]`, `/handoffs`, `/handoffs/[handoffId]`, `/capabilities`, `/api/health`, `/api/proxy/coding/[...path]`, plus sibling-shipped `/api/operating-readout`, `/api/proofs`, `/api/repo-catalog`.
- **Plan:** `~/Development/vidux/projects/litty/PLAN.md` (canonical). Research at `~/Development/vidux/projects/litty/research/` (~30k words, 11 deep-research agents).
- **Codex agents seeing UX/UI work in this project's queue:** redirect to backend tasks (federation contracts, FirstBite lanes, MCP, repo-backed catalog snapshots, the moussey-side PRs documented as Phase 3.5 unblockers).
- **Reference:** `/pilot-leo § Agent lane splits — codify in the project, not here (2026-05-24)` (the disambiguator pattern).
