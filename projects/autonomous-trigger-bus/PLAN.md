# Autonomous Trigger Bus — Crons, File-Drops, Webhooks → Brain Dispatch

> **Parent plan:** `~/Development/vidux/projects/agentic-command-center/PLAN.md` — this is **Phase 4 / sub-project #9**. Routes autonomous events (LaunchAgent cron ticks, watched-file drops, Sentry webhooks) through the same `dispatch()` interface every other input modality uses.

## Purpose

Today Leo has scattered LaunchAgents that do one-off work (`moussey-trigger-watchdog`, `moussey-ping-watch`, `captain-daily-sync`, etc.). Each invents its own logging + retry + on-failure handling. This sub-project unifies them: any autonomous event can `POST /api/autonomous-trigger/dispatch` with a payload describing what just happened, and the bus:

1. Logs the event to `~/.moussey/autonomous-events.jsonl` (shared format with brain-events).
2. Routes via `intent-router` + `dispatch()` to the right brain (default claude).
3. Captures the response + writes to a per-trigger output sink (file, follow-up cron config, vidux INBOX.md, etc.).

**Killer use case:** the existing `moussey-ping-watch` cron (10-min, sweeps `~/.moussey/pings.jsonl` for new inbound peer messages) becomes a 5-line LaunchAgent posting `{type: "ping-received", from, message}` to the bus, instead of duplicating the "read JSONL → tail logic → write to vidux inbox" code. Same logic for `captain-daily-sync` reporting failures, Sentry webhook posts, Snowcubes ASC bug alerts, etc.

## Architecture (LOCKED 2026-05-22)

```
┌──────────────────────────────────────────────────────────────────┐
│ Many autonomous sources                                           │
│                                                                    │
│   moussey-ping-watch cron (10-min)                                │
│   captain-daily-sync (3am)                                        │
│   resplit-2.0 ASC-bug monitor                                     │
│   Sentry webhook (PR comment / new error)                         │
│   chokidar file-drop watcher (~/Downloads/agent-inbox/)           │
│   moussey-trigger-doctor failures                                 │
│                                                                    │
│   Each POSTs {triggerKind, payload} → /api/autonomous-trigger     │
└────────────────────────┬─────────────────────────────────────────┘
                         │ HTTP loopback (HMAC-signed)
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ moussey :4321 — bus orchestrator (this project)                   │
│                                                                    │
│   POST /api/autonomous-trigger/dispatch                            │
│      ├─ verify HMAC (loopback only — same secret as trigger-claude)│
│      ├─ load matching trigger handler from registry                │
│      ├─ build prompt from payload + handler's prompt template      │
│      ├─ route(intent) → dispatch(req) → AsyncIterable<BrainChunk>  │
│      ├─ collect response text                                      │
│      ├─ apply handler's sink: file write / vidux inbox append /    │
│      │   trigger-claude follow-up / etc.                           │
│      └─ append event to ~/.moussey/autonomous-events.jsonl         │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

## Trigger registry (config-driven)

Triggers are registered in `~/.moussey/autonomous-triggers.json`:

```json
{
  "triggers": [
    {
      "kind": "ping-received",
      "prompt": "A peer just pinged us: {{from}}: {{message}}. Should I act on this?",
      "provider": "claude",
      "sink": { "type": "vidux-inbox", "project": "moussey-ping-watch" }
    },
    {
      "kind": "asc-bug",
      "prompt": "App Store Connect just surfaced a new crash: {{title}}\n{{trace}}\nClassify: P0/P1/P2 + suggested action.",
      "provider": "claude",
      "sink": { "type": "file", "path": "~/Development/resplit-ios/.cursor/inbox/asc-classifier.md" }
    },
    {
      "kind": "agent-inbox-drop",
      "prompt": "A file landed in ~/Downloads/agent-inbox/: {{path}} ({{kind}}). Summarize + classify intent.",
      "provider": "claude",
      "sink": { "type": "follow-up-trigger-claude", "peer": "Studio" }
    }
  ]
}
```

The registry pattern keeps the bus generic — adding a new autonomous event = add a JSON entry + the source-side LaunchAgent. No code change in moussey.

## Phases

### Phase 1 — Bus skeleton + 1 trigger end-to-end

- [pending] **AB1**: `POST /api/autonomous-trigger/dispatch` route in moussey. Validates HMAC (reuse `lib/lan-trigger-auth.ts`), validates body has `triggerKind`, loads registry, returns 404 if unknown kind. Appends to `~/.moussey/autonomous-events.jsonl`. Streams SSE response.
- [pending] **AB2**: `lib/autonomous-registry.ts` — read + parse `~/.moussey/autonomous-triggers.json`, validate against a schema, return matching handler or null. Reload on each request (no caching for v1).
- [pending] **AB3**: `lib/autonomous-sinks.ts` — implement 3 sink types: `file` (append to path), `vidux-inbox` (append to `~/Development/vidux/projects/<project>/inbox.md`), `follow-up-trigger-claude` (POST to /api/lan/trigger-claude with payload).
- [pending] **AB4**: First real trigger: migrate `moussey-ping-watch` cron to POST events to the bus instead of doing its own JSONL→inbox logic. Existing cron stays; just swap the action.
- **GATE 1**: Send a ping from another Mac; cron picks it up; bus dispatches; claude classifies; sink appends to moussey-ping-watch inbox.md. Same end-result as today but routed through the unified bus.

### Phase 2 — More triggers

- [pending] **AB5**: ASC bug classifier — when resplit-ios's existing Sentry webhook fires, POST to the bus instead of directly writing.
- [pending] **AB6**: Agent inbox drops — chokidar watcher on `~/Downloads/agent-inbox/` posts on every file landing.
- [pending] **AB7**: moussey-trigger-doctor failures — when the watchdog detects a real problem (not just self-heal), POST to the bus with the diagnosis.

### Phase 3 — Polish (deferred)

- [pending] **AB8**: GUI surface at `:4321/autonomous-bus` — chronological feed of all dispatched events with cost + duration + sink outcome.
- [pending] **AB9**: Per-trigger cost ceilings + rate limits (reuse `lib/lan-trigger-auth.ts` rate-limit Map).
- [pending] **AB10**: Replay — re-dispatch a past event from the audit log (useful for debugging a sink that didn't fire correctly).

## Decision Log

- [DIRECTION] [2026-05-22] Config-driven trigger registry instead of code-defined handlers. Reason: adding "yet another autonomous source" should be one JSON entry + one LaunchAgent, not a code change with a PR. Lowers the friction for Leo to wire up new flows.
- [DIRECTION] [2026-05-22] Reuse the trigger-claude HMAC secret. Reason: same loopback-only posture, same trust model, one secret to manage. The autonomous bus runs on the same Mac that hosts trigger-claude.
- [DIRECTION] [2026-05-22] Default brain = claude. Same rationale as gmail-bridge/imessage-bridge — full MCP toolkit for context-dependent reasoning.
- [DIRECTION] [2026-05-22] Sinks are pluggable but limited to 3 v1 types. file / vidux-inbox / follow-up-trigger-claude covers ~90% of envisioned flows. A 4th sink type (e.g. "send-as-iMessage") waits for imessage-bridge V2.
- [HARD-NEVER] Auto-execute code or modify repos via the bus. Sinks write to files or trigger downstream agents that themselves operate under their own discipline.
- [HARD-NEVER] LAN-exposed `/api/autonomous-trigger/dispatch`. Loopback HMAC only.
- [HARD-NEVER] Replay a past event without explicit confirmation. AB10 is human-triggered, not automatic.

## Claims board

| Task | Status | Owner | Blocking | Depends on | Updated |
|---|---|---|---|---|---|
| AB1: /api/autonomous-trigger route | [pending] | — | GATE 1 | brain-dispatcher B2 [completed], HMAC auth (shipped) | 2026-05-22 |
| AB2: autonomous-registry.ts | [pending] | — | AB1 → live | AB1 | 2026-05-22 |
| AB3: autonomous-sinks.ts (3 types) | [pending] | — | AB1 → live | AB1 | 2026-05-22 |
| AB4: migrate moussey-ping-watch | [pending] | — | GATE 1 | AB1, AB2, AB3 | 2026-05-22 |
| AB5: ASC bug classifier integration | [pending] | — | (Phase 2) | AB4, Sentry webhook | 2026-05-22 |
| AB6: agent-inbox drops | [pending] | — | (Phase 2) | AB4, chokidar | 2026-05-22 |
| AB7: doctor-failure routing | [pending] | — | (Phase 2) | AB4 | 2026-05-22 |
| AB8: /autonomous-bus GUI | [pending] | — | (Phase 3) | AB4 | 2026-05-22 |
| AB9: per-trigger cost + rate | [pending] | — | (Phase 3) | AB4 | 2026-05-22 |
| AB10: replay tool | [pending] | — | (Phase 3) | AB4 | 2026-05-22 |

## Two-agent coordination

**Recommended first claims:** Codex on AB1 (TS server route, similar shape to `/api/lan/trigger-claude`). Claude on AB3 (sinks library — file IO + HTTP loopback, easy to test in isolation).

## Progress

- [2026-05-22] Plan created. Architecture locked: bus = HMAC-loopback POST endpoint + JSON-config-driven trigger registry + 3 sink types (file / vidux-inbox / follow-up-trigger-claude). Phase 1 ships the skeleton + migrates the existing moussey-ping-watch cron as the first real trigger. Gates on brain-dispatcher B2 (already [completed]).


---

## PSA — 2026-05-26 — Fleet UX/UI lane split codified

- **Claude Code owns ALL UX/UI work fleet-wide.** Codex agents must stay on backend / logic / lanes / workers / API.
- **Disambiguator:** "is this rendered to a human?" → Claude. "Does this read/write data, run a CLI, or expose an HTTP endpoint?" → Codex.
- **Canonical visualization layer:** [Litty](file:///Users/leokwan/Development/litty) at `http://localhost:4400` (the operator cockpit). Federates moussey's `/api/coding/*` APIs. Replaces the 12,062-line `moussey/app/coding/page.tsx` rot.
- **15 routes shipped 2026-05-26:** `/`, `/lanes`, `/lanes/[laneId]`, `/runs`, `/runs/[runId]`, `/runs/[runId]/patch`, `/runs/[runId]/stream`, `/workers`, `/workers/[workerId]`, `/handoffs`, `/handoffs/[handoffId]`, `/capabilities`, `/api/health`, `/api/proxy/coding/[...path]`, plus sibling-shipped `/api/operating-readout`, `/api/proofs`, `/api/repo-catalog`.
- **Plan:** `~/Development/vidux/projects/litty/PLAN.md` (canonical). Research at `~/Development/vidux/projects/litty/research/` (~30k words, 11 deep-research agents).
- **Codex agents seeing UX/UI work in this project's queue:** redirect to backend tasks (federation contracts, FirstBite lanes, MCP, repo-backed catalog snapshots, the moussey-side PRs documented as Phase 3.5 unblockers).
- **Reference:** `/pilot-leo § Agent lane splits — codify in the project, not here (2026-05-24)` (the disambiguator pattern).
