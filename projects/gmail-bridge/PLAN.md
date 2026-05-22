# Gmail Bridge — Email as Agent Input

> **Parent plan:** `~/Development/vidux/projects/agentic-command-center/PLAN.md` — this is **Phase 3 / sub-project #7**. Turns Gmail into an input modality for the brain dispatcher (read incoming → dispatch → drafts reply with context).

## Purpose

Leo (or anyone) forwards an email to a known address — or labels an incoming email with `@agent`. The bridge cron picks it up, reads the full thread context via the existing Gmail MCP, dispatches via the brain dispatcher (default: claude with full MCP), then writes the response back as a **Gmail draft** in the same thread. Leo reviews the draft in Gmail, edits if needed, sends manually.

**Killer use case:** Amazon shipping notification lands. Forward it to `agent@leokwan.com` (or apply a `@agent` label). 30 seconds later the original thread has a draft saying "Got it — tracked shipment #X, ETA Thursday, added to Snowcubes inventory tracker. Will follow up if delayed." Leo opens Gmail, sees the draft, hits send.

Hard rule: **NEVER send automatically.** Always leave as a draft for Leo to review and send manually. The agent does the heavy reading + drafting; Leo retains send authority.

## Architecture (LOCKED 2026-05-22)

```
┌──────────────────────────────────────────────────────────────────┐
│ Gmail (cloud)                                                     │
│                                                                    │
│   New email lands → gets `@agent` label OR is forwarded to       │
│   agent@leokwan.com (forwarder set up server-side via filter)    │
└──────────────────────────────────┬──────────────────────────────┘
                                   │ Gmail MCP poll
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ moussey :4321 — gmail-bridge cron (this project)                │
│                                                                  │
│   com.leokwan.moussey-gmail-bridge LaunchAgent (cron 5-min)     │
│      ├─ mcp__gmail__search_emails(label:"@agent")               │
│      ├─ for each unprocessed: read full thread                  │
│      ├─ route(intent) → claude (always, MCP coverage needed)    │
│      ├─ dispatch(req)  → AsyncIterable<BrainChunk>               │
│      ├─ collect response text                                   │
│      ├─ mcp__gmail__draft_email(threadId, body, replyTo)        │
│      └─ remove `@agent` label, add `@agent-drafted`             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                       Audit log: ~/.moussey/brain-events.jsonl
                       (modality: "gmail")
```

The bridge is a CRON, not a webhook. Gmail webhooks require Pub/Sub setup; polling at 5-min cadence is plenty for inbound that isn't latency-critical (the killer use case has minute-scale latency tolerance).

## Phases

### Phase 1 — Forward-to-agent flow (cheap to ship, contained scope)

- [pending] **GB1**: Pick the trigger surface. Two options to pick first:
  - (a) Gmail filter on `from:leo@...` AND `subject:@agent` → applies `@agent` label.
  - (b) Forward filter on `agent@leokwan.com` → applies label.
  - Pick (a) for v1 — simpler, no forwarding mechanics, Leo can label any thread from his iPhone via Gmail's label menu.
- [pending] **GB2**: moussey cron skeleton — `com.leokwan.moussey-gmail-bridge.plist` LaunchAgent firing `scripts/gmail-bridge-tick.ts` every 5 min via `StartInterval=300`. Script: connect to Gmail MCP, search for `label:@agent`, log how many threads match. No dispatch yet — just prove the read path.
- [pending] **GB3**: `lib/gmail-bridge.ts` reading the full thread for one labeled message. Concatenate subject + sender + body of last 5 messages into a context string. Returns `{threadId, replyTo, contextText}`.
- [pending] **GB4**: Wire dispatch — for each unprocessed thread, build a prompt: `"You are reading an email thread for Leo. Draft a reply. Be concise. The thread context follows:\n\n<contextText>"`. Call `dispatch({prompt, provider: "claude", metadata: {sourceModality: "gmail"}})`. Collect full text.
- [pending] **GB5**: Create draft via `mcp__gmail__draft_email`. Body = the collected text. ThreadId = original. To = original sender. Subject = `Re: <original>`. Remove `@agent` label; add `@agent-drafted`.
- [pending] **GB6**: Idempotency. Re-running the cron on the same labeled thread MUST NOT create duplicate drafts. Track processed threadIds in `~/.moussey/gmail-bridge-state.jsonl` keyed by thread id + last-message-id.
- **GATE 1**: Apply `@agent` label to a real thread in Gmail. Wait <6 min. Open the thread — see a draft from Leo with the agent response. Original label removed; `@agent-drafted` label applied.

### Phase 2 — Quality + safety (deferred)

- [pending] **GB7**: Sender allowlist. Only draft replies on threads where the most-recent message is FROM an address on `~/.moussey/gmail-bridge-allowlist.txt`. Reason: avoid drafting replies to spam or untrusted senders.
- [pending] **GB8**: Content allowlist. If the original thread contains keywords like "wire transfer", "password", "credit card", DO NOT draft a reply — instead create a draft saying "🚨 sensitive content detected, not auto-drafting." Conservative posture for v1.
- [pending] **GB9**: Cost ceiling. Track `costCents` per dispatch via the brain-audit; if a single thread exceeds 50 cents, abort with a "cost ceiling exceeded" draft. Reason: a thread with 50 messages could balloon token usage.

### Phase 3 — Multi-account + iMessage-bridge parity (deferred)

- [pending] **GB10**: Run the bridge for `gmail-fbl` and `gmail-personal` accounts too (those MCPs already exist in `~/.claude/.config.json`). One bridge per account; per-account label conventions.
- [pending] **GB11**: Shared utilities with imessage-bridge — both modalities are "agent reads inbound, drafts reply for human-approval." Extract common scaffolding into `lib/inbound-bridge.ts` once both ship.

## Decision Log

- [DIRECTION] [2026-05-22] Polling cron, not Gmail webhook. Reason: webhooks need Google Cloud Pub/Sub setup + IAM + persistent endpoint that handles retries. 5-min poll is way simpler and matches Leo's latency expectation (minute-scale, not second-scale).
- [DIRECTION] [2026-05-22] Always-draft, never-send. Reason: outbound email is irreversible and has reputational/relationship blast radius. Leo retains send authority. This rule lifts from `/captain` "Executing actions with care."
- [DIRECTION] [2026-05-22] Label `@agent` (not forwarding to a magic address) is the v1 trigger. Reason: applying a label is a one-tap action from Gmail iOS — works on every device. Email forwarding requires setup + a separate inbox.
- [DIRECTION] [2026-05-22] Default brain = claude. Reason: needs full MCP toolkit to read the thread + check related context (other emails, calendar, etc.) before drafting. Codex/local can't do that today.
- [DIRECTION] [2026-05-22] Per-account label namespace: primary inbox uses `@agent`; `gmail-fbl` uses `@agent-fbl`; `gmail-personal` uses `@agent-personal`. Reason: keeps which-account-this-came-from explicit, prevents cross-pollination.
- [HARD-NEVER] Auto-send a draft. Always leave for human review.
- [HARD-NEVER] Process unlabeled emails. The `@agent` label is the only opt-in trigger.
- [HARD-NEVER] Bridge runs without a sender-allowlist once Phase 2 ships. v1 can run open during testing; v2 must gate.
- [HARD-NEVER] Forward labeled-as-private emails (e.g. `personal`) to the agent unless the user explicitly labels with `@agent` ON TOP of that.

## Claims board

| Task | Status | Owner | Blocking | Depends on | Updated |
|---|---|---|---|---|---|
| GB1: Pick trigger surface (label vs forward) | [completed] | claude | GB2 | nothing | 2026-05-22 (resolved in plan: label) |
| GB2: Cron skeleton LaunchAgent + read path | [pending] | — | GB3+ | Gmail MCP available | 2026-05-22 |
| GB3: Thread context reader | [pending] | — | GB4 | GB2 | 2026-05-22 |
| GB4: Wire dispatch | [pending] | — | GB5 | GB3, brain-dispatcher B2 | 2026-05-22 |
| GB5: Draft creator | [pending] | — | GATE 1 | GB4 | 2026-05-22 |
| GB6: Idempotency state | [pending] | — | GATE 1 | GB5 | 2026-05-22 |
| GB7: Sender allowlist | [pending] | — | (Phase 2) | GB5 | 2026-05-22 |
| GB8: Sensitive-content guard | [pending] | — | (Phase 2) | GB5 | 2026-05-22 |
| GB9: Cost ceiling | [pending] | — | (Phase 2) | GB5 | 2026-05-22 |
| GB10: Multi-account fan-out | [pending] | — | (Phase 3) | GB6 | 2026-05-22 |
| GB11: Shared `lib/inbound-bridge.ts` | [pending] | — | (Phase 3) | imessage-bridge | 2026-05-22 |

## Two-agent coordination

**Recommended first claim: Codex on GB2/GB3** — Python or TS subprocess-spawn work (Gmail MCP CLI invocation), straightforward. **Claude on GB5/GB6** — TS draft creation + idempotency state management.

GB4 needs brain-dispatcher B2 shipped first.

## Open questions for Leo

- **Account scope for v1**: just `gmail` (primary inbox) or all three (`gmail`, `gmail-fbl`, `gmail-personal`)? Default per plan: primary only, fan-out is Phase 3.
- **Draft from-address**: when the bridge drafts a reply on a thread where Leo was BCC'd, who is the draft "from"? Leo's primary account. (gmail draft API uses the authenticated identity.)
- **Allowlist seed**: when Phase 2 lands, who's the initial allowlist for sender filter? Probably Nicole + family + close work contacts. Configure in `~/.moussey/gmail-bridge-allowlist.txt`.

## Progress

- [2026-05-22] Plan created. Architecture locked: 5-min polling cron, label-triggered (`@agent`), always-draft-never-send. GB1 [completed] in plan: label trigger picked over forward-address for tap-from-Gmail-iOS ergonomics. Gates on brain-dispatcher B2.
