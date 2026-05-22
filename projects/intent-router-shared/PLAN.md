# intent-router-shared — Phase 0 Keystone (2 of 2)

> **Parent:** `~/Development/vidux/projects/agentic-command-center/PLAN.md` — this is **Phase 0 / sub-project #2**. Sibling of `brain-dispatcher-shared`. The dispatcher knows how to TALK to providers; this router knows which provider + Mac to PICK for a given free-text intent.

## Purpose

A pure TypeScript library that takes a free-text intent + source-modality + caller hints and returns `(provider, targetMac, systemHint)` — the routing decision. The brain dispatcher then executes that decision.

```text
User intent:  "what came in overnight on Gmail and iMessage?"
Modality:     "voice" (came via mic)
Routing:      provider=claude (needs Gmail + iMessage MCP), targetMac=Self
              (where the MCPs are wired), systemHint="You are reading
              overnight inbound for Leo. Be concise.".
```

v1 ships a **stub** that hard-codes `provider=claude` for everything (since claude is the only brain with full MCP today). v2 adds heuristics. v3 lifts to an LLM-classified intent (small local Qwen) when latency budget allows.

The point of shipping v1 as a stub: every input modality can WIRE the router into its pipeline immediately, then heuristics improve transparently behind a stable interface.

## Interface contract (locked 2026-05-22)

```typescript
// moussey/lib/intent-router.ts

import type { BrainProvider } from "./brain-dispatcher";

export type RouterInput = {
  prompt: string;                  // free-text user intent
  sourceModality: "voice" | "text" | "vidux-browse" | "imessage"
                | "gmail" | "screen" | "cron";
  callerHints?: {
    preferProvider?: BrainProvider;    // explicit caller override
    preferMac?: string;                // explicit Mac override (e.g. "Studio")
    requiredSkills?: string[];         // e.g. ["imessage", "gmail"]
    requiredMcps?: string[];           // e.g. ["mcp__imessage", "mcp__gmail"]
  };
  fleetStatus?: {                  // snapshot of which Macs are accepting
    self: { name: string; accepting: boolean };
    peers: { name: string; accepting: boolean }[];
  };
};

export type RouterOutput = {
  provider: BrainProvider;         // which brain
  targetMac: "Self" | string;      // which Mac to dispatch to ("Self" = loopback)
  systemHint?: string;             // optional prepend to the prompt
  reason: string;                  // human-readable routing decision (audit)
};

export function route(input: RouterInput): RouterOutput;
```

Synchronous + pure for v1. v2 may need async (e.g. probe fleet liveness mid-call) — interface gets `routeAsync` then, leaving `route` as the always-sync default.

## Tasks

### Phase 0 — v1 stub (unblocks everything downstream)

- [pending] **R1**: Create `moussey/lib/intent-router.ts` with type definitions + the v1 stub: returns `{provider: callerHints?.preferProvider ?? "claude", targetMac: callerHints?.preferMac ?? "Self", reason: "v1 stub: defaults to claude on Self unless caller overrode"}`. Export `route`, `RouterInput`, `RouterOutput`.
- [pending] **R2**: Unit tests in `moussey/tests/intent-router.test.ts`. Verify: caller override wins (both provider + Mac), default behavior, reason string is non-empty + descriptive.
- [pending] **R3**: README at `lib/intent-router.README.md` covering: interface contract, the v1→v2→v3 plan, what each modality is expected to pass as `callerHints`, the relationship with `brain-dispatcher`.

### Phase 1 — v2 heuristics (deferred until 2+ providers have real MCP coverage)

- [pending] **R4**: Skill/MCP requirement detection. Regex + keyword bag for: "gmail|email" → requires `mcp__gmail`; "imessage|text|messages" → requires `mcp__imessage`; "screenshot|click|fill|form" → requires `mcp__computer-use`; etc. If `requiredMcps` is non-empty and the chosen provider can't satisfy them → fall back to claude.
- [pending] **R5**: Mac picker. If `requiredSkills` includes a repo-specific skill (`/bigapple` → resplit-ios; `/snowcubes` → snowcubes-web), pick the Mac that has that repo cloned. Otherwise `Self`.
- [pending] **R6**: Cost-aware routing. If the prompt is "summarize this 50-page PDF" (heavy read) and `claude` is the default, route to `codex` instead (Codex is unlimited). Heuristic: prompt length × estimated context fetch > N tokens → codex.

### Phase 2 — v3 LLM classification (deferred)

- [pending] **R7**: Local Qwen2.5-0.5B as the intent classifier. ~10ms per call on M-series, runs entirely local. Outputs `{provider, mac, reason}` JSON. Falls back to v2 heuristics if the local model is unavailable.

## Decision Log

- [DIRECTION] [2026-05-22] Ship v1 as a stub. Reason: every input modality (voice-agent V4, text-chat V5, vidux-browse-action, etc.) needs the routing interface NOW so the brain dispatcher call site doesn't have to be rewritten later. The stub is honest: it defaults to claude on Self, the only fully-MCP-capable path today.
- [DIRECTION] [2026-05-22] Pure + synchronous v1. Reason: no I/O = trivially testable, no async deadlock risk in caller code. Async variant lands only when fleet-status probing is needed (v2+).
- [DIRECTION] [2026-05-22] `callerHints` always wins over heuristics. Reason: when Leo says "use codex for this", or when the voice-agent UI has a provider dropdown, the user's explicit pick must NEVER be overridden by router heuristics. Heuristics are advisory, not authoritative.
- [DIRECTION] [2026-05-22] Live in `moussey/lib/intent-router.ts` next to brain-dispatcher. Reason: same rationale as brain-dispatcher's home decision — moussey is the TypeScript host for all command-center infra. Promote to a separate package only when a non-moussey consumer needs it.
- [HARD-NEVER] No network calls in v1. The stub is pure data → data. v2 keyword heuristics also stay sync. Network probing waits for v2-plus.
- [HARD-NEVER] No persisting `RouterInput.prompt` in the router's own audit log. The brain dispatcher's audit log captures it; this library is purely a decision function.

## Claims board

| Task | Status | Owner | Blocking | Depends on | Updated |
|---|---|---|---|---|---|
| R1: v1 stub + types | [pending] | — | every downstream sub-project | brain-dispatcher B1 | 2026-05-22 |
| R2: Unit tests | [pending] | — | quality gate | R1 | 2026-05-22 |
| R3: README | [pending] | — | onboarding | R1 | 2026-05-22 |
| R4: v2 MCP detection heuristics | [pending] | — | non-claude brain MCP work | R1 | 2026-05-22 |
| R5: Mac picker heuristics | [pending] | — | cross-Mac dispatch routing | R1 | 2026-05-22 |
| R6: Cost-aware routing | [pending] | — | codex+local production use | R1, codex-with-MCP plan | 2026-05-22 |
| R7: Local LLM classifier | [pending] | — | (polish) | R4, R5 | 2026-05-22 |

## Two-agent coordination

Same atomic-claim protocol as parent. **Recommended first claim:**

- Either agent: **R1** is tiny (~30 lines of TypeScript including types). Whoever claims `brain-dispatcher B1` should claim `R1` in the same push since they share the `BrainProvider` type import.

R1 → R2 → R3 ships v1 end-to-end in one short session. R4-R7 are deferred until real cost/MCP data is available.

## Progress

- [2026-05-22] Plan created as Phase 0 keystone #2. Interface contract locked. v1 stub strategy committed (default-to-claude, caller-override-wins). Pairs naturally with brain-dispatcher B1 for a single-session ship.
