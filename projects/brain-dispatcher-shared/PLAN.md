# brain-dispatcher-shared — Phase 0 Keystone

> **Parent:** `~/Development/vidux/projects/agentic-command-center/PLAN.md` — this is **Phase 0 / sub-project #1**, the keystone every other sub-project imports.

## Purpose

A single TypeScript library that exposes ONE function signature mapping an intent (prompt + context + provider hint + Mac hint) to a streaming text response. Three concrete provider implementations behind a common `AsyncIterable<BrainChunk>` interface:

- **claude** — POST to local `/api/lan/trigger-claude` with `peer=Self` (loopback HMAC-signed), parse SSE, yield text chunks. FULL MCP toolkit (subscription billing).
- **codex** — spawn `~/.local/bin/codex exec --model gpt-5.4 -`, pipe prompt to stdin, parse stdout, yield text chunks. UNLIMITED, NO MCP.
- **local** — POST to `http://localhost:11434/api/generate` (Ollama) with model from env, parse JSONL stream, yield text chunks. OFFLINE, NO MCP.

Every other sub-project (moussey-voice-agent, agentic-text-chat, vidux-browse-action, imessage-bridge, gmail-bridge, screen-action-bridge, autonomous-trigger-bus) imports this. Do not let any sub-project re-implement provider abstraction badly.

## Interface contract (locked 2026-05-22)

```typescript
// moussey/lib/brain-dispatcher.ts (canonical home — colocated with trigger-claude)

export type BrainProvider = "claude" | "codex" | "local";

export type BrainRequest = {
  prompt: string;                  // the actual ask
  provider: BrainProvider;         // explicit pick
  systemHint?: string;             // optional system-prompt prefix
  cwd?: string;                    // working directory for the spawned brain
  model?: string;                  // override default model per-provider
  abortSignal?: AbortSignal;       // caller-controlled cancellation
  metadata?: {                     // for audit log + future intent routing
    sourceModality: "voice" | "text" | "vidux-browse" | "imessage"
                  | "gmail" | "screen" | "cron";
    sessionId?: string;
    turnId?: string;
  };
};

export type BrainChunk =
  | { type: "text"; text: string }                // streamed text
  | { type: "tool_use"; name: string; input?: unknown }   // MCP tool call
  | { type: "tool_result"; name: string; output?: unknown }
  | { type: "system_init"; model: string; apiKeySource: string }
  | { type: "complete"; totalText: string; durationMs: number; costCents?: number; exitCode?: number }
  | { type: "error"; reason: string; recoverable: boolean };

export async function* dispatch(req: BrainRequest): AsyncIterable<BrainChunk>;
```

Every consumer awaits `for-await-of dispatch(req)` and emits the chunks to whichever sink fits (TTS queue for voice, browser SSE for chat, Gmail draft for email-bridge, etc.).

## Tasks

### Phase 0 — Library scaffolding

- [pending] **B1**: Create `moussey/lib/brain-dispatcher.ts` with the type definitions above + provider-stub implementations that throw `not-implemented`. Export `dispatch()`, `BrainProvider`, `BrainRequest`, `BrainChunk`.
- [pending] **B2**: `claude` provider implementation. Loopback HMAC-signed POST to `http://localhost:4321/api/lan/trigger-claude` (same code path as moussey-trigger-claude CLI uses, but in-process). Parse the existing SSE protocol — `event: chunk`, `event: result`, `event: error`. Map each to a `BrainChunk`. Reuse cost-extraction logic from `lib/trigger-feed.ts` lines 100-115. Audit log entry to `~/.moussey/brain-events.jsonl` with `sourceModality` + `provider:"claude"`.
- [pending] **B3**: `codex` provider implementation. Spawn `~/.local/bin/codex exec --model gpt-5.4 -` (binary path discovery via `which codex` fallback). Pipe prompt to stdin via `child_process.spawn`. Parse stdout line-by-line; each line emits a `text` chunk. No MCP support yet (Codex MCP shim is a separate future project). Track child PID for `abortSignal` cancellation via `process.kill(pid, "SIGTERM")`.
- [pending] **B4**: `local` provider implementation. POST to `http://localhost:11434/api/generate` with `{model: req.model || "qwen2.5:14b", prompt, stream: true}`. Parse the JSONL response stream; each `response` field emits a `text` chunk. Final `done:true` line emits `complete`. Hook `abortSignal` to `AbortController.abort()` on the fetch.
- [pending] **B5**: Unit tests in `moussey/tests/brain-dispatcher.test.ts`. Mock each provider's downstream call (mock fetch for claude/local, mock spawn for codex). Verify: signature stability, chunk ordering (system_init → text* → complete), abort behavior, audit-log write.
- [pending] **B6**: README at `lib/brain-dispatcher.README.md` covering: the interface contract verbatim, per-provider gotchas (claude needs trigger-claude running locally, codex needs CLI installed, local needs Ollama running), how to add a fourth provider, audit-log format.

### Phase 0.5 — Smoke (gates downstream work)

- [pending] **B7**: One-shot Node script `moussey/scripts/brain-dispatch-smoke.ts` that runs the same prompt ("what's 47 × 23") through all three providers and prints the streamed output + total duration + cost. Useful as a sanity check before any sub-project (voice-agent V4, text-chat) wires the dispatcher into a UI.
- **GATE 0**: B7 smoke prints "1081" from claude provider AND codex provider AND local provider (if local is running). voice-agent V4 and agentic-text-chat both unblocked after this.

## Decision Log

- [DIRECTION] [2026-05-22] Library lives in `moussey/lib/brain-dispatcher.ts`, not a separate npm package. Reason: moussey is already the TypeScript host for trigger-claude, audit log, HMAC auth. Avoiding workspace/monorepo complexity for v1. Promote to a published `@leokwan/brain-dispatcher` only if a non-moussey consumer ever needs it.
- [DIRECTION] [2026-05-22] `AsyncIterable<BrainChunk>` instead of `EventEmitter` or a callback API. Reason: idiomatic modern TypeScript, plays cleanly with for-await loops, easy to wrap in `ReadableStream` for browser SSE, easy to `Promise.race` against an abort signal.
- [DIRECTION] [2026-05-22] Provider is an EXPLICIT field, not auto-routed. Reason: routing logic (cost-aware brain pick + Mac pick) lives in `intent-router-shared` (sub-project #2). This library only knows how to TALK to each provider, not which to pick. Separation of concerns.
- [DIRECTION] [2026-05-22] Audit log shared across modalities at `~/.moussey/brain-events.jsonl`, not split per-source. Reason: moussey GUI tabs (sub-project #10) need a single time-ordered feed to render the unified history. Per-source files would need a merging step.
- [DIRECTION] [2026-05-22] `claude` provider uses the existing `/api/lan/trigger-claude` even on loopback. Reason: free reuse of HMAC auth, rate limit, kill switch, audit log, MCP toolkit. The "self-call over LAN" overhead is negligible (<1ms loopback) compared to the duplication cost of a parallel direct-spawn code path.
- [DIRECTION] [2026-05-22] Codex provider has NO MCP support in v1. Reason: Codex CLI invocation doesn't currently know about Leo's MCP servers (figma, gmail, computer-use, etc.). A separate "Codex MCP shim" sub-project is needed before codex becomes a first-class brain for skill-heavy tasks. For now, codex is the right pick for cost-sensitive plain-text reads (summarize this doc, write boilerplate code).
- [HARD-NEVER] No `eval`-style dynamic provider loading. Three known providers, named explicitly. Adding a fourth is a code change with a PR.
- [HARD-NEVER] No persistence of `BrainRequest.prompt` beyond the audit log. The prompt is the user's intent and stays as-is; the library does not transform it.

## Claims board

| Task | Status | Owner | Blocking | Depends on | Updated |
|---|---|---|---|---|---|
| B1: Type definitions + stubs | [completed] | claude | every other B-task | — | 2026-05-22 |
| B2: claude provider | [pending] | — | voice-agent V4, text-chat V4 | B1, trigger-claude (shipped) | 2026-05-22 |
| B3: codex provider | [pending] | — | (alternate brain for voice/text) | B1, codex CLI installed | 2026-05-22 |
| B4: local provider | [pending] | — | (alternate brain for voice/text) | B1, Ollama installed | 2026-05-22 |
| B5: Unit tests | [completed] | claude | (quality gate) | B2, B3, B4 | 2026-05-22 |
| B6: README | [completed] | claude | onboarding | B2-B4 | 2026-05-22 |
| B7: Tri-provider smoke script | [pending] | — | GATE 0 | B2, B3, B4 | 2026-05-22 |

## Two-agent coordination

Same atomic-claim protocol as parent. **Recommended first claims:**

- **Codex**: B1 (type definitions + stubs) — pure TypeScript design work, no runtime dependencies. After B1, B2 is the natural follow-up.
- **Claude**: B7 (smoke script) — can be drafted in parallel with B2-B4 since it's a thin wrapper around the public API.

If B1 lands before B2-B4, the three providers can ship in parallel (B2/B3/B4 independent of each other).

## Progress

- [2026-05-22] Plan created as Phase 0 keystone. Interface contract locked. Library home decided (moussey/lib). B1 is the unblocking task — all other B-tasks depend on its type exports.
- [2026-05-22] B1 [completed]. `moussey/lib/brain-dispatcher.ts` shipped: `BrainProvider`, `BrainSourceModality`, `BrainRequest`, `BrainChunk` type exports + `dispatch()` async-generator entry point + three provider stubs (`dispatchClaude`, `dispatchCodex`, `dispatchLocal`) that throw `NotImplemented` with pointers to B2/B3/B4. Exhaustive switch with `never` check on `provider` for compile-time safety. B2-B4 unblocked — three providers can ship in parallel now.
