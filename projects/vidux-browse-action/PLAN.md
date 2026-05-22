# vidux-browse Action — Comments as Agent Triggers

> **Parent plan:** `~/Development/vidux/projects/agentic-command-center/PLAN.md` — this is **Phase 3 / sub-project #5**. Turns vidux-browse's existing anchored-comment surface into an input modality for the brain dispatcher.

## Purpose

vidux-browse already lets a viewer anchor a comment to a specific DOM element on a plan or artifact. Today those comments are read-only annotations: a human writes them, another human reads them later.

This project upgrades the loop: when a comment is tagged with a known trigger prefix (`@agent` or `@claude` or `@codex`), the matching local agent picks it up, dispatches via the brain dispatcher with the comment + anchor context, and writes the response back as a child comment thread on the same anchor.

**Killer use case:** Leo reads a draft Snowcubes brand brief in vidux-browse, anchors a comment on a paragraph saying `@agent rewrite this for tone — punchier`, walks the dog. By the time he's back, a child comment thread shows the agent's rewrite anchored to the same paragraph, ready to apply.

## Architecture (LOCKED 2026-05-22)

```
┌────────────────────────────────────────────────────────────────────┐
│ vidux-browse :7191 (Python http.server)                             │
│                                                                      │
│   POST /api/comments  appends to ~/.vidux-browser/comments.jsonl    │
│                                                                      │
│   New POST hook: if comment.body starts with `@agent` / `@claude` / │
│   `@codex`, also POST to moussey :4321/api/voice/dispatch-comment    │
└────────────────────────────────────────────────────────────────────┘
                                  │ HTTP loopback
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│ moussey :4321 — comment-action orchestrator (this project)          │
│                                                                      │
│   POST /api/vidux-browse-action/dispatch                            │
│      ├─ parse comment.body for trigger prefix → provider hint       │
│      ├─ route(intent) → {provider, targetMac, reason}                │
│      ├─ dispatch(req) → AsyncIterable<BrainChunk>                    │
│      ├─ collect full response text                                  │
│      └─ POST back to vidux-browse :7191/api/comments as a child     │
│         comment thread (parentId = original.id, body = response)    │
│                                                                      │
└────────────────────────────────────────────────────────────────────┘
                                  │ HTTP loopback
                                  ▼
              ~/.vidux-browser/comments.jsonl (child thread appended)
```

The receiver (moussey) handles the heavy lifting. vidux-browse stays a thin static-file server with one tiny hook to forward triggering comments.

## Trigger prefixes

| Prefix | Action |
|---|---|
| `@agent <prompt>` | Dispatch via `intent-router` default (claude with full MCP) |
| `@claude <prompt>` | Force `provider: "claude"` |
| `@codex <prompt>` | Force `provider: "codex"` (cost-sensitive heavy reads) |
| `@local <prompt>` | Force `provider: "local"` (offline / private) |

A comment that doesn't start with any of these prefixes is a regular human-only annotation. No agent invocation.

## Anchor context as part of the prompt

When dispatching, the prompt to the brain includes both:

1. The comment body (with prefix stripped).
2. The anchored target's surrounding text — captured from `target.elementText` field that vidux-browse already records in the comment record.

System hint added by the dispatcher: `You are responding to a comment anchored to a plan/artifact. The original anchored text follows. Write your response so it can be applied as a child comment thread on the same anchor.`

## Phases

### Phase 1 — Read-side hook (cheap to ship, immediately useful)

- [pending] **VA1**: vidux-browse `POST /api/comments` route gets a tail-hook: after appending to JSONL, if body matches `^@(agent|claude|codex|local)\s+`, fire-and-forget POST to `http://localhost:4321/api/vidux-browse-action/dispatch` with the new comment record. No retry needed — if moussey is down, the comment is still recorded, just doesn't trigger.
- [pending] **VA2**: moussey `POST /api/vidux-browse-action/dispatch` route. Validates source = loopback (no LAN reach). Parses prefix → provider hint. Calls `route()` + `dispatch()`. Collects streamed text. POSTs response back to vidux-browse as a child comment (`parentId = req.body.id`). Audit log entry via `appendBrainEvent({modality: "vidux-browse"})`.
- [pending] **VA3**: vidux-browse client (the existing `app.js`) renders child comment threads under the parent comment when the parent has a `@trigger` prefix. Optional: small "🤖" icon next to the parent body so humans see at a glance which comments are agent-triggered.
- **GATE 1**: Anchor a comment with `@agent what does this paragraph mean?` → walk away 60 seconds → return to the same plan → see a child comment with the agent's response anchored to the same paragraph.

### Phase 2 — Loop-back actions (deferred)

- [pending] **VA4**: `@agent edit: rewrite this paragraph` triggers PROPOSE mode — the agent writes a proposed replacement text into the child comment WITHOUT applying it. Leo eyeballs, then clicks "Apply" in vidux-browse to actually mutate the source file. (Apply happens via the existing local-`/vidux` discipline — the comment-action layer never directly edits a file.)
- [pending] **VA5**: `@agent run: ./scripts/foo.sh` triggers EXEC mode — runs a sanctioned script via `child_process.spawn` in moussey, dumps stdout/stderr into the child comment. Allowlist of scripts in `~/.moussey/comment-action-allowlist.txt` — strict prefix match. No allowlist entry → no exec, just a "not permitted" reply comment.

### Phase 3 — Polish (deferred)

- [pending] **VA6**: Thread continuity. Replying to a child agent comment with another `@agent <followup>` carries the whole thread as context to the next dispatch (last 3 turns).
- [pending] **VA7**: Multi-modal anchors. If the anchored element is an `<img>`, pass the image to claude via the vision MCP. If it's a `<code>`, format it as a fenced block in the prompt.

## Decision Log

- [DIRECTION] [2026-05-22] Loopback only between vidux-browse + moussey. Reason: both are per-Mac LaunchAgents, no cross-Mac dispatch path needed for v1. Cross-Mac happens INSIDE the brain dispatch when the chosen provider is claude+peer.
- [DIRECTION] [2026-05-22] Trigger prefixes are explicit (`@agent` etc.) — NEVER infer agent intent from a regular comment. Reason: vidux-browse comments are also human-only review feedback (per /moussey "Vidux-Browse Comments" boundary). Auto-firing on every comment would surprise reviewers and burn budget.
- [DIRECTION] [2026-05-22] Replies come back AS COMMENTS, not as PLAN.md edits. Reason: keeps the vidux-browse boundary (comments are app data, never mutate source). PLAN.md/artifact edits still go through the normal `/vidux` discipline on the Mac that owns the repo.
- [DIRECTION] [2026-05-22] Fire-and-forget POST from vidux-browse → moussey. No retry. Reason: vidux-browse must NEVER block on the agent dispatch — comments must save instantly even if moussey is offline. The dispatch is best-effort enrichment.
- [HARD-NEVER] Auto-fire on every comment without `@trigger` prefix. Human-only comments must stay human-only.
- [HARD-NEVER] Apply changes directly to PLAN.md / artifact files from this layer. Always propose-then-human-apply.
- [HARD-NEVER] LAN-exposed `/api/vidux-browse-action/dispatch`. Loopback only — `X-Real-IP` or peer header rejection on receive.

## Claims board

| Task | Status | Owner | Blocking | Depends on | Updated |
|---|---|---|---|---|---|
| VA1: vidux-browse comment hook | [pending] | — | VA2 receives | nothing | 2026-05-22 |
| VA2: moussey dispatch route | [pending] | — | GATE 1 | brain-dispatcher B2, intent-router R1 [completed] | 2026-05-22 |
| VA3: child-comment rendering | [pending] | — | GATE 1 polish | VA1 | 2026-05-22 |
| VA4: PROPOSE-mode for edits | [pending] | — | (Phase 2) | VA2 | 2026-05-22 |
| VA5: EXEC-mode for sanctioned scripts | [pending] | — | (Phase 2) | VA2 | 2026-05-22 |
| VA6: Thread continuity | [pending] | — | (Phase 3) | VA2, VA3 | 2026-05-22 |
| VA7: Multi-modal anchors | [pending] | — | (Phase 3) | VA2 | 2026-05-22 |

## Two-agent coordination

Same atomic-claim protocol as parent. **Recommended first claims:**

- **Codex**: VA1 (vidux-browse Python hook — modifies `browser/server.py`'s comment POST handler, adds fire-and-forget HTTP). Python work, matches Codex strengths.
- **Claude**: VA3 (child-comment rendering — JS in `browser/static/app.js`, augments the existing comment renderer with thread nesting + 🤖 icon). JS/UI work.
- VA2 needs brain-dispatcher B2 (claude provider) shipped first.

## Progress

- [2026-05-22] Plan created. Architecture locked: loopback hook from vidux-browse `:7191/api/comments` → moussey `:4321/api/vidux-browse-action/dispatch` → brain dispatcher → child comment thread back to vidux-browse. Trigger prefixes `@agent/@claude/@codex/@local`. PROPOSE-only for v1; never directly mutates source files.
