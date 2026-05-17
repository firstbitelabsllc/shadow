# TeamAgentCoordination — fleet coordination & shared protocols

## Purpose

Improve coordination between the team agents (`/resplit-watch`, `/resplit-2-0-loop`, `/linear-health-watch`, `/vidux`, `/auto`, `/nia`) so they operate as a fleet rather than as siloed crons. Eliminate the systemic failure modes that caused 34+ consecutive false-positive defers (sibling-cron live-steering collision), 11+ IDLE cycles (scope-cage starvation), and 13+ vidux projects with `[pending]` tasks no cron can reach. Outcome: a single shared cron-registry mechanism via the agent-ledger `automation_name` field, phase-shifted LaunchAgent schedules, a scope cascade so empty-tier crons fall through to broader queues, a claims bus, and mandatory `/auto` + `/nia` preflights on cron-dispatched lanes.

## Evidence

- [Source: last-session diagnosis 2026-05-07] Live-steering filter at `resplit-watch/scripts/run-once.sh:272` (jq fallback) and `resplit-2-0-loop/scripts/run-once.sh:200` use `startswith("claude-code")` only — cannot distinguish sibling-cron writes from Leo's interactive sessions.
- [Source: ai commit `8c92cff`] fix(resplit-watch): tuple-repeat filter unblocks 41-cycle defer streak — Python path added with (agent_id, summary_prefix) tuple-repeat dedup at lines 242-268. Partial fix; still trips on sibling-cron's first entry of a new tuple.
- [Source: ai commit `6a64bf4`] fix(resplit-watch): wrapper-bug-(a) — filter live-steering gate by files>0
- [Source: ai commit `a2ecabe`] skills: merge /pilot into /vidux (pilot deprecated 2026-05-13)
- [Source: ai commit `4a6b850`] captain: new skill — linear-health-watch (30-min Linear hygiene + vidux core feedback cron)
- [Source: ai commits `b29bff8`, `128e403`] Linear awareness gate in amp Harness Mode
- [Source: ai commit `c1dcdb6`] amp+vidux-leo: Goal Mode — mint CC /goal boilerplate bound to vidux PLAN.md
- [Source: ledger sample 2026-05-14T04:24-04:49Z] 10/10 ledger entries from recent cron firings have empty `automation_name` and `automation_id` fields despite the schema supporting them (ledger-append.sh:594-595, 808-810). The crons never set them.
- [Source: launchctl PlistBuddy 2026-05-14] `com.leokwan.resplit-watch` `StartInterval=900`, `com.leokwan.resplit-2-0-loop` `StartInterval=1800`, `com.leokwan.linear-health-watch` `StartInterval=1800` — all three on raw `StartInterval`, sibling cron fires collide on `:00/:30` boundaries.
- [Source: `~/.agent-ledger/cron-registry.txt` ls] file does not exist (verified 2026-05-14).
- [Source: `~/.agent-ledger/claims.jsonl` ls] file does not exist (verified 2026-05-14).
- [Source: ledger-append.sh:594-595] Schema supports `automation_name` / `automation_id` — fallback path needed to populate from env vars.
- [Source: resplit-watch/prompts/harness.md:7, 168, 187] `/auto` Hard NEVER references already present in resplit-watch harness; need to verify + extend to 2.0-loop and linear-health-watch.

## Constraints

- **ALWAYS** — every change to a skill in `~/Development/ai/skills/` is committed + pushed via `cd ~/Development/ai && git add -A && git commit && git push` per Leo §Skill File Discipline.
- **ALWAYS** — backwards-compatible filter changes: if a cron does NOT set `CLAUDE_AUTOMATION_NAME`, the live-steering filter falls back to current `startswith("claude-code")` behavior (no regression for un-migrated crons).
- **ALWAYS** — verify before shipping: synthetic ledger entries with/without `automation_name` MUST round-trip through the jq filter and produce the expected exclude/include result.
- **NEVER** — change cadence as part of this work — Leo just tuned 1200s ↔ 600s; treat current intervals as authoritative (this work only changes the LaunchAgent **phase**, not the interval).
- **NEVER** — break the existing tuple-repeat filter that fixed the 41-cycle defer streak (ai commit `8c92cff`); the new automation_name exclusion is ADDITIVE on top of tuple-repeat.
- **NEVER** — bookkeeping-only PRs (resplit-ios CLAUDE.md MT-1); every ship in this PLAN flips a `[pending]` row AND ships code.
- **NEVER** — new repos (Leo's standing rule until September 2026).

## Tasks

- [completed] TC1: Merge /pilot into /vidux (pilot deprecated; /vidux is now universal router). [Evidence: ai commit a2ecabe] [Shipped: 2026-05-13]
- [completed] TC2: Linear awareness gate in amp Harness Mode — every cron-bound harness prompt MUST cite Linear UUID + fetch live issues + state closeout pattern + fallback recipe. [Evidence: ai commits b29bff8, 128e403]
- [completed] TC3: /linear-health-watch as vidux-Linear feedback cron (30-min launchd, runs reconcile + inbox-sync dry-runs across fleet, files vidux-core improvement PRs). [Evidence: ai commit 4a6b850]
- [completed] TC4: Tuple-repeat filter + files>0 gate on resplit-watch live-steering — partial fix for false-positive defers; (agent_id, summary[:80]) tuple-repeat 3+ in last 100 = loop-reporter, excluded. [Evidence: ai commits 8c92cff, 6a64bf4]
- [completed] TC5: Codify Goal Mode in amp — mint CC /goal boilerplate bound to vidux PLAN.md, <4000 char rendered output, fire-once + watch-the-meter pattern. [Evidence: ai commit c1dcdb6]
- [in_progress] T1: **Cron-registry via `CLAUDE_AUTOMATION_NAME` env var** — teach `ledger-append.sh` to fall back to `$CLAUDE_AUTOMATION_NAME` / `$CLAUDE_AUTOMATION_ID` env vars when input JSON lacks them; add `CLAUDE_AUTOMATION_NAME=<cron-name>` to each cron's Claude invocation; tighten live-steering filters to exclude entries where `automation_name != ""`. Documents the convention in `~/.agent-ledger/cron-registry.md`. [ETA: 1h] [claimed_by: claude-code interactive 2026-05-14, goal=team-agent-coordination cycle 1]
- [pending] T2: **Phase-shift LaunchAgents** off colliding `:NN` boundaries. Convert `StartInterval`-only plists for resplit-watch (900s), resplit-2-0-loop (1800s), linear-health-watch (1800s) to `StartCalendarInterval` arrays so sibling fires don't land on identical minute boundaries. resplit-watch fires :07/:22/:37/:52, 2.0-loop fires :03/:33, linear-health-watch fires :15/:45. [ETA: 1h]
- [pending] T3: **Drop WEEKEND_PUSH scope cage** in `resplit-2-0-loop/scripts/run-once.sh:18`. Replace with Tier-1=WEEKEND_PUSH → Tier-2=all-vidux-projects-with-[pending] → Tier-3=ASC investigations fall-through in the shell-side digest builder. Re-anchor the cap-meta-work rule in `prompts/iteration.md` to measure "same-shape" across whatever scope the cycle is operating on. [ETA: 2h]
- [pending] T4: **Claims bus protocol** — `~/.agent-ledger/claims.jsonl` append-on-claim + append-on-release. Update resplit-watch + 2.0-loop + linear-health-watch to read claims.jsonl before claiming a row (skip if claimed within 2h). [ETA: 3h]
- [pending] T5: **`/auto` Hard NEVER mandatory pre-action gate** in cron-dispatched lanes. Add explicit `/auto check <intended-action>` step to dispatch templates in resplit-watch + 2.0-loop + linear-health-watch + strongyes-watch + autobot-resplit-web. Audit /auto SKILL.md for the canonical Hard NEVER list. [ETA: 2h]
- [pending] T6: **`/nia` preflight in fix-lane dispatch templates** — when a cron dispatches a fix lane for a Sentry issue or ASC bug, prompt opens with `/nia search "<error fingerprint>"` before any code action. [ETA: 1h]

## Decision Log

- 2026-05-07 — Last-session diagnosis identified the four converging failure modes: sibling-cron filter false-positive, scope cage, phase-lock collision, no shared coordination layer.
- 2026-05-13 — `/pilot` merged into `/vidux` (ai commit a2ecabe). Five other coordination primitives partially landed: Linear awareness gate, /linear-health-watch cron, tuple-repeat filter, Goal Mode in amp.
- 2026-05-14 cycle-1-start — Disk verification confirmed 5/11 items already shipped (TC1-TC5) and 6/11 still pending (T1-T6). T1 design pivot: `automation_name` field-based registry (cleaner than registering session IDs which are per-fire — agent_id rotates on every cron fire).

## Progress

- [2026-05-14] Plan opened. Cycle 1 begins T1 (cron-registry via CLAUDE_AUTOMATION_NAME env var). Total pending=6, in_progress=1, completed=5. ETA-remaining ≈ 10h.
