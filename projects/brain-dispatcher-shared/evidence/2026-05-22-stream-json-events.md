# Stream-JSON event capture — B2.0 reference

Captured 2026-05-22 via `claude -p --output-format stream-json --include-partial-messages --model haiku "say hi in exactly one word"` on M4 Pro (cmux-bundled `claude` binary at `/Applications/cmux.app/Contents/Resources/bin/claude`). Used to design the B2 → BrainChunk mapping in `lib/brain-dispatcher.ts`.

## Event types observed (in order)

| Stream-json event | Frequency | BrainChunk to yield |
|---|---|---|
| `{type:"system", subtype:"hook_started"}` | many (5+ session-start hooks) | **skip** — noise |
| `{type:"system", subtype:"hook_response"}` | matches hook_started count | **skip** — noise |
| `{type:"system", subtype:"init", model, apiKeySource, ...}` | 1 (at start) | `{type:"system_init", model, apiKeySource}` |
| `{type:"stream_event", event:{type:"content_block_delta", delta:{type:"thinking_delta", thinking}}}` | many | **skip** (thinking is internal — don't surface in voice/text UI) OR yield as a separate "thinking" chunk type (future enhancement) |
| `{type:"stream_event", event:{type:"content_block_delta", delta:{type:"text_delta", text}}}` | many | `{type:"text", text}` ← **THIS is the real streaming text** |
| `{type:"stream_event", event:{type:"content_block_start"}}` | per block | **skip** — block boundaries |
| `{type:"stream_event", event:{type:"content_block_stop"}}` | per block | **skip** |
| `{type:"assistant", message:{content:[...]}}` | 1+ (snapshots) | **skip** — duplicates the text_deltas |
| `{type:"stream_event", event:{type:"message_delta"}}` | 1 | **skip** — stop reason already implied by `result` |
| `{type:"stream_event", event:{type:"message_stop"}}` | 1 | **skip** |
| `{type:"rate_limit_event"}` | 1 | **skip** (or warn if `status != "allowed"`) |
| `{type:"result", duration_ms, total_cost_usd, result, is_error}` | 1 (final) | `{type:"complete", totalText: result, durationMs: duration_ms, costCents: round(total_cost_usd*100), exitCode: is_error ? 1 : 0}` |

## Tool-use events (not captured in this prompt but expected)

When claude invokes a tool (Bash, Read, mcp__gmail__*, etc.):

| Stream-json event | BrainChunk |
|---|---|
| `{type:"stream_event", event:{type:"content_block_delta", delta:{type:"input_json_delta", partial_json}}}` | accumulate into tool_use args |
| `{type:"stream_event", event:{type:"content_block_start", content_block:{type:"tool_use", name, id}}}` | `{type:"tool_use", name}` (input not yet complete here) |
| `{type:"user", message:{content:[{type:"tool_result", tool_use_id, content}]}}` | `{type:"tool_result", name, output: content}` |

## Implementation notes for B2.0

trigger-claude swap is small:

```diff
- const args: string[] = ["-p", "--model", model, "--output-format", "json"];
+ const args: string[] = [
+   "-p",
+   "--model", model,
+   "--output-format", "stream-json",
+   "--include-partial-messages",
+ ];
```

But the receiver-side cost extraction in `app/api/lan/trigger-claude/route.ts:206` parses the final JSON ARRAY from buffered stdout. With stream-json, lines arrive one-by-one and the receiver needs:

1. Buffer stdout line-by-line (split on `\n`)
2. Parse each line as JSON
3. On `type === "result"` event: extract `total_cost_usd`, `duration_ms`, `result`
4. The SSE `{chunk: text}` wire frames are pass-through (text is already line-delimited JSON, the consumer parses)

No SSE wire-format change needed — only the receiver-side cost extraction.

## What changes for current consumers

- **CLI sender** (`scripts/moussey-trigger-claude`) — no change. It just shows the streamed output.
- **GUI sender** (`/triggers` form) — no change for v1. Eventually upgrade to parse per-event (show "🛠 using <tool>") which is purely additive.
- **trigger-feed.ts** cost extraction — needs the per-line parser update (line 100-115).
- **brain-dispatcher B2** — consumes new line-delimited events directly, maps per table above.

## Open questions

- **`hook_started`/`hook_response` noise.** Each session-start emits 5+ hook events at the top. B2 should filter these out before yielding the first chunk. Alternative: `--no-include-hook-events` flag (worth trying).
- **`thinking_delta` chunks.** Claude emits internal reasoning as thinking_delta. For voice/text UI, these should be hidden by default. Future: a `verbosity: "thinking"` flag in `BrainRequest` could surface them.
- **`api_key_source`** field in the init event. The current code looks for `apiKeySource: "none"` — confirm this name in stream-json's init event (couldn't see it in this capture because filtered as noise).