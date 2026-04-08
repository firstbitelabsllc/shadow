# Vidux — Build Plan

## Purpose
Create a net-new plan-first orchestration system that makes quarter-long iOS projects completable in a week via overnight cron loops. Vidux = Vibe + Redux. The plan is the store, code is the view.

## Evidence
- [Source: 9 research agents, 2026-03-31] SDD (Spec-Driven Development) is 2025-2026's defining practice. Plan-first improves success by ~33%.
- [Source: SlopCodeBench, arxiv 2603.24755] Agent code degradation is monotonic. Erosion in 80% of trajectories. "Coding while thinking" is empirically bad.
- [Source: OpenAI harness engineering] "The harness is the 80% factor." Swapping models = 10-15% change. Swapping harness = works or doesn't.
- [Source: Martin Fowler on SDD tools] "Agents frequently don't follow instructions." Enforcement gap is real.
- [Source: Gastown v0.13.0, 13.3K stars] Git-backed state + persistent agent identity + multi-tool support is production-proven at 20-30 agent scale.
- [Source: Jeffrey Lee-Chan /harness PR #265] Dual five-whys + three-strike gate + contract tests is a working plugin in production.
- [Source: swiftify-v4 session] Combine rework happened because plan didn't capture team conventions. 50/30/20 would have caught it.
- [Source: Factory.ai] Anchored iterative summarization (structured > freeform) scores 3.70 vs 3.44.
- [Source: Arize pattern] Planning-as-tool-calls with hard finish gate. Can't mark done with pending tasks.
- [Source: Multi-agent research] Coordination gains plateau at ~4 agents. 17x error amplification beyond that without hierarchy.
- [Source: Anthropic] "Agents plan by doing" for simple tasks. "Scale effort to complexity" for big ones. Both modes needed.
- [Source: user feedback] "We're not planning enough. We're coding while thinking." Vidux doctrine is the response.
- [Source: open source survey, 26 tools] Key ingredients: PAUL's Execute/Qualify/Unify loop (603 stars), tick-md's markdown-native coordination (18 stars but exact pattern match), spec-kit's three-doc chain (84K stars), GSD's stuck-loop detection (46K stars), opslane/verify's one-agent-per-AC model (100 stars), adversarial-spec's multi-LLM debate (517 stars).
- [Source: superpowers, 128K stars] Dominant skill framework. Chains: brainstorm -> plan -> execute -> verify. Subagent dispatch model. Already installed in our env.
- [Source: Chachamaru127/claude-code-harness, 383 stars] 5-verb workflow: Setup -> Plan -> Work -> Review -> Release. TypeScript guardrail engine. 4-perspective review (Security, Performance, Quality, A11y).

## Constraints
- ALWAYS: Work on Claude Code, Cursor, AND Codex (model/tool interop is #1 priority)
- ALWAYS: Simple to install and debug (one command bootstrap)
- ALWAYS: Keep existing skills untouched (Vidux is additive, not a rewrite)
- ALWAYS: Company-agnostic — no references to any employer's internal tools
- ASK FIRST: Before changing Captain's bootstrap or sync scripts
- NEVER: Typed YAML schemas (user feedback: natural language markdown only)
- NEVER: More than 4 coding agents in parallel (research: diminishing returns)
- Reviewer preference: Sports analogies (point guard, ref), not political ones (mayor)

## Decisions
- [2026-03-31] Decision: Vidux is a skill first, plugin packaging later. Rationale: Skills work NOW across all tools. Plugins are Claude-only. Can wrap in plugin manifest later.
- [2026-03-31] Decision: PLAN.md lives in the branch, not globally. Rationale: Travels with code, visible in PRs, any machine gets it on git fetch.
- [2026-03-31] Decision: Fan-out/fan-in for plan refinement, not 20 agents editing one file. Rationale: Research shows 17x error amplification. 4-agent groups with one synthesizer is the sweet spot.
- [2026-03-31] Decision: Two modes — Pilot for Mode A (small), Vidux for Mode B (quarter-long). Don't try to make one system do both.
- [2026-03-31] Decision: Channel Yegge (git-backed state, propulsion) and jlee (harness, dual five-whys) as advisor philosophies. Not literal framework adoption.
- [2026-04-06] Decision: Publish the portable Vidux core in its own public repo (`user/vidux`) instead of exposing the entire `ai` skills repo. Rationale: the core is reusable, while `ai/` carries personal and project-specific wiring.
- [2026-04-06] Decision: This repo is the canonical home for Vidux. The copy in `ai/skills/vidux/` is retired. All framework development happens here.

## Tasks

### Phase 1: Core Doctrine — COMPLETE

### Phase 2: Loop Implementation — COMPLETE

### Phase 3: Enforcement — COMPLETE

### Phase 4: Plugin Packaging — COMPLETE

### Phase 5: Integration

### Phase 6: V1 Finalization — Harness + Guides

### Phase 7: Open Source Publication — COMPLETE

### Phases 8-12 — ARCHIVED (see ARCHIVE.md)
<!-- 38 tasks archived to ARCHIVE.md on 2026-04-07, Cycle 38 -->

### Phase 13: Hardening & Coverage — COMPLETE

**Goal:** Fix security/correctness bugs found by self-audit, close test coverage gaps, and improve cross-platform portability. Evidence-driven: every task traces to audit findings.

[Evidence: `projects/vidux-self-investigation/evidence/2026-04-07-hardening-audit.md`, `projects/vidux-self-investigation/evidence/2026-04-07-coverage-gaps.md`]


### Phase 14: Fleet Restructuring — Cadence, REDUCE Gates, Dead Lane Cleanup

**Goal:** Fix the structural problems exposed by overnight fleet data: cadence-runtime mismatches, missing REDUCE gates, blocked lanes burning cycles, and ghost automations.

[Evidence: `projects/vidux-v230/evidence/2026-04-07-fleet-overnight-diagnosis.md`]


### Phase 15: Fleet Intelligence & Self-Healing — COMPLETE

**Goal:** Make vidux fleets self-healing based on real runtime data. Fix the 32% mid-zone problem, add circuit breakers, implement idle-churn detection, and template the radar pattern.

[Evidence: `projects/vidux-self-investigation/evidence/2026-04-07-fleet-loop-analysis.md`, `projects/vidux-self-investigation/evidence/2026-04-07-agentic-patterns-research.md`]

- [completed] **15.3 Radar template pattern** — Created guides/vidux/radar-template.md: {{placeholder}}-based harness template for read-only radars. Includes updated REDUCE gate (circuit_breaker check), sizing guidance (800-1200 chars target), examples table. Contract test added. [Done: 2026-04-07] [Evidence: fleet-loop-analysis.md#5, prompt analysis]
- [completed] **15.4 Mid-zone enforcement in harness prompts** — Added "Dispatch-side mid-zone kill" to DOCTRINE.md Principle 10 and best-practices.md REDUCE gate section. Rule: 3+ minutes with no file write in dispatch = checkpoint and exit. Cited fleet data (32% mid-zone, target <15%). 2 contract tests. [Done: 2026-04-07] [Evidence: fleet-loop-analysis.md#3]
- [completed] **15.5 Contract tests for circuit breaker** — 2 tests: circuit_breaker field exists and is open/closed, idle progress triggers open + blocks dispatch. Merged into 15.1 delivery. [Done: 2026-04-07] [Evidence: coverage-gaps pattern]

### Phase 16: Plan Hygiene & Archive — COMPLETE

**Goal:** The PLAN.md has grown to 200+ lines with 80+ completed tasks across 15 phases. Archive completed phases to keep the hot window lean (<30 tasks). Also prune stale evidence and project plans.

[Evidence: vidux-loop.sh context_warning=true, context_note="69 completed tasks"]

- [completed] **16.1 Archive phases 8-12 to ARCHIVE.md** — 38 completed tasks moved. PLAN.md dropped from 230 to ~130 lines. Phases 1-7 were already headers-only. Phases 13-15 kept as recent context. [Done: 2026-04-07] [Evidence: loop context_warning]
- [completed] **16.2 Prune stale project plans** — Scanned 9 project plans. Archived 2 (nextjs-cve-sweep 4/4, vidux-stress-test 6/6). 7 still active with pending tasks. vidux-v230 has 1 in_progress investigation (D3 backpressure). [Done: 2026-04-07] [Evidence: project scan]
- [completed] **16.3 Update README.md with Phase 13-15 features** — Added "Fleet Intelligence (v2.3+)" section: circuit breaker, idle-churn detection, REDUCE gate, mid-zone kill, radar template, cross-platform compat. Updated "What Ships Here" with scripts/lib/, tests/, radar template. [Done: 2026-04-07] [Evidence: self-extending plan, Doctrine 11]

### Phase 17: Fleet Awareness & Accessibility

**Goal:** Fix the systemic fleet failures found in the 11-automation audit: SIGPIPE crashes, empty queues, broken feedback loops, FP jargon accessibility, and the missing cross-lane awareness that lets automations duplicate work or ignore siblings.

[Evidence: `projects/vidux-self-investigation/evidence/2026-04-07-fleet-audit-11-automations.md`]

- [completed] **17.1 Fix SIGPIPE in vidux-loop.sh** — Wrapped 3 `grep|head` pipe patterns with `|| true` to prevent exit 141 under `set -euo pipefail`. Moved circuit breaker + auto_pause evaluation before early exits. Added `_FLEET_SUFFIX` to all 4 early-exit JSON paths for consistent schema. Fixed `self.ROOT` test bug and DOCTRINE.md `stateless` keyword. 30/30 loop tests pass. [Done: 2026-04-07] [Evidence: fleet-audit-11-automations.md#systemic-1]
- [completed] **17.2 Rename dispatch/reduce to plain English** — Replace FP jargon across all docs, scripts, commands, and tests. Proposal: "REDUCE gate" → "Quick Check", "DISPATCH" → "Deep Work" or "Execute". Cross-cutting change across 12+ files — needs dedicated pass. [Evidence: user feedback "this isn't functional programming"] [Depends: none] [P]
- [completed] **17.3 Add cross-lane awareness as Doctrine 13** — Every automation must read sibling lane state before acting. Not just ledger as add-on — baked into SKILL.md, DOCTRINE.md, harness template, and both REDUCE/SCAN gates. Includes: sibling memory scan, hot-files collision check, fleet-level duplicate detection. The orchestrator creating a localization lane without checking existing fleet is the failure case. [Done: 2026-04-07] [Evidence: user feedback "this is so important... all worklanes even cross project"]
- [completed] **17.4 Bake ledger into harness template** — Update `guides/vidux/radar-template.md` and `guides/vidux/best-practices.md` to make ledger reads mandatory in the READ step, not optional. Include sibling memory scan pattern. [Evidence: fleet-audit-11-automations.md#systemic-2]
- [completed] **17.5 Blocker dedup gate** — If last 3 memory notes report the same blocker keyword, vidux-loop.sh emits `blocker_dedup: true` and REDUCE gate auto-pauses. Prevents `acme-launch-loop` pattern (5× same ASC key blocker in 6 hours). [Evidence: fleet-audit-11-automations.md#systemic-3]
- [completed] **17.6 Queue starvation detection** — vidux-loop.sh detects "all tasks done but mission not complete" → emits `queue_starved: true` instead of generic `action: none`. Helps radars vs writers understand the real state. [Evidence: fleet-audit-11-automations.md#why-4]
- [completed] **17.7 Radar→writer inbox pattern** — Radars append findings to `INBOX.md` next to PLAN.md. Writers consume inbox entries and promote to `[pending]` tasks during READ step. Breaks the circular deadlock where radars observe but can't create work. [Evidence: fleet-audit-11-automations.md#systemic-2]
- [completed] **17.8 Sub-plan tree traversal** — Add `[spawns: investigations/foo.md]` tag support to vidux-loop.sh. Script traverses sub-plans when parent task is in_progress, reports aggregate status. [Evidence: user question "maybe we're not doing a good enough job with keeping the task queue or sub plan tree"]
- [completed] **17.9 Orchestrator fleet health mode** — Redesign orchestrator from "edit one prompt at a time" to "detect fleet-level patterns and take fleet-level action." When 6/11 automations REDUCE-exit, the orchestrator should notice and act, not wordsmith one radar prompt. [Evidence: fleet-audit-11-automations.md#why-5]

### Phase 18: Fleet Prompt Rewrite & Best Practices

**Goal:** All 6 active Codex automations were dead overnight (0/6 shipped code). Root causes: wrong gate files, scanner using writer gate, circuit breaker and auto_pause deadlocks. Rewrite every prompt using v2.4.0 patterns and document prompt authoring best practices.

[Evidence: `projects/vidux-self-investigation/evidence/2026-04-08-automation-prompt-rewrites.md`]

- [completed] **18.1 Remove personal project data from repo** — Untracked 5 files in projects/, deleted fleet-rebuild script, genericized 92 private project references to acme/beacon across 10 docs, removed hardcoded paths. [Done: 2026-04-08]
- [completed] **18.2 Diagnose all 6 active automations** — Audited prompts, ran vidux-loop.sh on each plan, read all memory files. Found: 4 wrong gate files, 1 scanner-as-writer, 2 safety deadlocks (CB + auto_pause). [Done: 2026-04-08] [Evidence: automation-prompt-rewrites.md]
- [completed] **18.3 Rewrite all automation prompts (v3)** — Final rewrite: all 5 active automations use "Quick check gate" (no more REDUCE naming). acme-asc now gates on fresh vidux plan with 9 real tasks. acme-localization-pro uses SCAN gate. All prompts handle find_work state. acme-currency paused (1 task, folded into plan task 7). [Done: 2026-04-08]
- [completed] **18.4 Write prompt authoring best practices** — Added Section 14 to best-practices.md: prompt structure, before/after example (real ASC failure), gate selection guide, 7 common mistakes, skill token format, size guidance. [Done: 2026-04-08]
- [completed] **18.5 Create fresh acme/PLAN.md** — Imported real work from 4 Cursor plans: 9 pending tasks across ASC bugs (6 new + 4 triaged + 56 verify + 5 blocked), release (TestFlight + screenshots), and ops (FX docs + migration + web parity). Created INBOX.md for scanner→writer pattern. [Done: 2026-04-08]
- [completed] **18.6 Handle find_work + rename REDUCE to Quick Check** — All 5 prompts now use "Quick check gate" naming. Exit condition simplified: only exit on action=complete AND type=done AND queue_starved=false. Everything else (dispatch, find_work, gather_evidence) proceeds. [Done: 2026-04-08]
- [pending] **18.7 Verify fleet recovery after Codex restart** — Check next cycle's memory notes. At least 3/5 should dispatch real work (acme-asc has 9 tasks, acme-web has 6, beacon has 6). [Depends: Codex restart]
- [completed] **18.8 Auto-archive in vidux-loop.sh** — vidux-loop.sh now auto-runs vidux-checkpoint.sh --archive when cold_tasks > archive_threshold. Tested on Beacon: 81 tasks archived, 1061→497 lines. Sliding window is now enforced automatically. [Done: 2026-04-08]

### Phase 19: Config-Authoritative Plan Resolution

**Goal:** Scripts and docs still assume `projects/` under repo root. `vidux.config.json` should be the single authority for where plans live. This is design debt, not break-glass — the live fleet works because prompts use absolute paths. Fix so multi-machine setups and new automations resolve plan locations from config at runtime.

[Evidence: Snap workstation feedback 2026-04-08 — `vidux-doctor.sh` line 40, `vidux-prune.sh` line 25, `commands/vidux.md` line 58, `test_vidux_contracts.py` line 1111 all hardcode `projects/` path assumptions]

- [pending] **19.1 Add `resolve_plan_store` helper in `scripts/lib/`** — Reads `vidux.config.json`, returns the absolute plan store path. Falls back to `$VIDUX_ROOT/projects` if no config exists. [Evidence: config already has `projects_path` field]
- [pending] **19.2 Wire `vidux-doctor.sh` and `vidux-prune.sh` to use `resolve_plan_store`** — Replace hardcoded `$VIDUX_ROOT/projects` references with config-resolved path. [Depends: 19.1]
- [pending] **19.3 Stop parsing `projects/<name>/PLAN.md` out of prompt text** — Give automations a project slug or explicit authority-store field, then resolve from config at runtime. [Depends: 19.1]
- [pending] **19.4 Update docs and tests** — Fix `commands/vidux.md` and `test_vidux_contracts.py` to match config-authoritative resolution. [Depends: 19.2, 19.3]

### Phase 10 Open Questions
- [x] Q6: Max plan nesting depth = 3, 4th allowed but flagged. Enforced by dashboard. [Decision Log entry exists.] [Done: 2026-04-07]
- [x] Q7: Dashboard refresh = on-demand. Config added in 10.2 (`dashboard.refresh_mode: "on-demand"`). [Done: 2026-04-07]
- [x] Q8: Ledger = vendored in scripts/lib/. Extract if community adopts. [Done: 2026-04-07]

## Open Questions
- [x] Q1: EARS for acceptance criteria only, not tasks/constraints/evidence. Add optional `[Done-When: EARS statement]` per task or phase-level acceptance criteria blocks. Current task format (checkbox + evidence + depends) is better for agent execution. Kiro validates: EARS for specs, free-form for tasks. [Done: 2026-04-01]
- [x] Q2: Plan readiness = 10-point checklist in LOOP.md. 5 required gates + 5 quality points. Score >= 7 to code, < 7 means refine the plan. [Done: 2026-04-01]
- [x] Q3: SKILL.md alone is sufficient for all 3 tools (agentskills.io open standard). Plugin manifests are for marketplace distribution only, not cross-tool compat. Captain symlinks handle discovery. [Done: 2026-04-01]
- [x] Q4: Agent subagents (not Teams) for fan-out. Teams persist across sessions (violates stateless doctrine), add coordination overhead, and risk orphaned state if cron dies. Subagents are fire-and-forget, perfect for embarrassingly parallel research. Teams reserved for future multi-turn critic debates. [Done: 2026-04-01]
- [x] Q5: Ship **templates**, not full harnesses. The public repo already has: `guides/vidux/radar-template.md` (Phase 15.3), `examples/fleet-reference/` (Phase 9), and the REDUCE gate block in `guides/vidux/best-practices.md`. Full harnesses are project-specific (Layer 2) and contain absolute paths, skill lists, and authority chains that don't generalize. Templates with `{{placeholders}}` are the right abstraction. [Done: 2026-04-07] [Evidence: Phase 15.3 radar template, Phase 9 fleet configs, fleet-loop-analysis.md prompt quality audit]

## Surprises
- [2026-03-31] obra/superpowers (128K stars) already installed in our env. Its brainstorm->plan->execute->verify chain is close to Vidux's gather->plan->execute->verify. Could be a companion rather than competitor.
- [2026-03-31] tick-md (18 stars) uses a single TICK.md file as Git-backed multi-agent task board — structurally identical to what Vidux PLAN.md does. Low stars but exact pattern match.
- [2026-03-31] PAUL (603 stars) has Execute/Qualify/Unify loop with escalation statuses (DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, BLOCKED). The UNIFY step (reconcile planned vs actual) is a gap in our design — should add.
- [2026-04-01] Previous session already landed pilot-ledger-emit.sh + project build recipe + env vars on main (commit 1c8c0f9). Merged into vidux branch. Phase 5 integration is partially done for free.
- [2026-04-01] All 5 swarm agents completed successfully in parallel. Phase 1 + Phase 2 + contract tests all done in one burst. 10/10 tests passing.
- [2026-04-06] The first scaffold pass accidentally mirrored internal root plan files. Impact: public repo would have leaked the wrong story.
- [2026-04-06] Self-investigation revealed: ~/.claude/skills/vidux was a stale DIRECTORY copy, not a symlink. Fixed. But 14 automation prompts hardcode `ai/skills/vidux/SKILL.md`, bypassing all symlinks. Every automation run loads stale vidux with Ralph, old paths, and "smallest slice" language.
- [2026-04-06] Prompt quality audit: beacon-release-train is 56 lines, 73% restated doctrine. acme-nurse is ~120 lines. Lean version is 13 lines with 100% project-specific signal density.
- [2026-04-06] Ralph skill was never deleted in Phase 8 — stale copies persisted at ~/.claude/skills/ralph/ and ~/.codex/skills/ralph/ (6157 bytes each, dated Mar 28). Also found acme-nurse codex automation (7816 bytes, ACTIVE, runs every 20min) still referencing RALPH.md.
- [2026-04-06] vidux-checkpoint.sh had no git repo guard — running on a plan outside a git repo produced raw git `fatal:` error (exit 128). Fixed with rev-parse check.
- [2026-04-06] Claude Code has 3 tiers of scheduling: /loop (ephemeral, 1min), Desktop Scheduled Tasks (persistent, local, 1min), Cloud Scheduled Tasks (Anthropic infra, 1hr). Desktop tasks are the Claude equivalent of Codex automations.
- [2026-04-07] Overnight fleet data reveals structural bimodal failure: acme-asc fires every 20min but takes 63min per run. 37 acme-android runs restated "still blocked" at 2-7min each. The REDUCE gate vidux designed (Phase 11) was never actually deployed to live automation prompts — the doctrine exists but the enforcement is missing.

## Decision Log
- [DIRECTION] [2026-04-06] Stage indicators use emoji prefixes (🔍📐⚡✅📌) not color-only. Reason: works in terminal, IDE, CI, and copy-paste. Do not switch to color-only.
- [DIRECTION] [2026-04-06] Max plan nesting depth = 3, with L4 allowed but flagged. Reason: research shows 17x error amplification beyond 4 agents; 3-deep keeps coordination manageable.
- [DIRECTION] [2026-04-06] Ledger is centralized at ~/.agent-ledger/ (not per-project). Reason: single source of truth for cross-tool, cross-worktree coordination. Dashboard reads one location.
- [DIRECTION] [2026-04-06] Dashboard index is machine-local (not git-backed). Reason: plans travel with code via git; dashboard aggregation is local concern. No pollution of repos.
- [DIRECTION] [2026-04-06] vidux-prune.sh has dry-run (--simulate) by default for destructive ops. Reason: pruning completed plans is irreversible without git history spelunking.
- [DIRECTION] [2026-04-06, corrected 2026-04-07] The DB-only fleet rebuild was a local experiment, not a durable default. On the current machine, the live control plane still runs from repo-backed `ai/automations` plus `~/.codex/sqlite/codex-dev.db` until a verified DB-only cutover actually exists. Evidence: `projects/context-ops/evidence/2026-04-07-public-vidux-control-plane-drift.md`. Do not describe DB-only storage as present-tense truth without a fresh fleet audit.
- [DIRECTION] [2026-04-07] Phase 12 addresses the merge-gate gap: automations must land work on the default branch, not just in worktrees. The old launch-loop role was correctly deleted (too complex) but its merge responsibility must be distributed into dispatch mode and each harness.
- [DELETION] [2026-04-06, corrected 2026-04-07] A temporary local pass removed `ai/automations/` and treated the orchestrator as retired, but that did not remain the canonical live state on this machine. Current fleet truth still includes repo-backed `ai/automations/` plus an active `codex-automation-orchestrator` row. Evidence: `projects/context-ops/evidence/2026-04-07-public-vidux-control-plane-drift.md`. Do not cite the temporary removal as current truth.
- [DIRECTION] [2026-04-06] Fleet rebuilt: 33 automations → 12 (4 acme, 6 beacon, 1 vidux-meta, 1 media-studio). All harnesses use burst-mode doctrine, 30-min cadences, and self-extending plans. Reason: old writer/radar split was for overnight cycles; new fleet organized by work stream. Evidence: `projects/context-ops/evidence/2026-04-06-fleet-rebuild-final.md`.
- [DIRECTION] [2026-04-06] All harnesses must include MODE: DISPATCH block. Structural bimodal enforcement — quick (<2min) or deep (drain queue), mid-zone (3-8min) is forbidden. Evidence: `projects/vidux-v230/evidence/2026-04-06-burst-vs-watch-mode-insight.md`.
- [DIRECTION] [2026-04-06] Automations self-extend plans. Every automation can add tasks to PLAN.md. No writer/reader distinction. Bounded by three-strike rule to prevent recursive overload.

## Progress
- [2026-04-08] Fleet watchdog (post-v2.5.1 peer review): 0/5 shipping, 3 idle-prefx, 1 blocked, 1 warm. Fixes verified by 6-agent swarm (7/7 peer review passed). CB minimum-entries fix committed. Scanner prompt execution permission removed. 33 stale "REDUCE gate" prose refs renamed across 5 docs. JSON schema gap fixed (exit_criteria in 2 paths). All 3 plans dispatch: acme=9 hot, beacon=6 hot, acme-web=2 hot. Next cycles should show [QC]/[SCAN] memory notes. Beacon blocked on T70 (Vercel domain). Beacon plan needs triage (35 abandoned in_progress, 296KB bloat). 8 ghost memory files from deleted automations on disk.
- [2026-04-08] Fleet watchdog (post-rebuild): 0/5 shipping, 5 reset — all awaiting Codex restart. Fleet rebuilt: fresh acme/PLAN.md with 9 real tasks, all prompts v3 with "Quick check gate" naming, INBOX.md created, acme-currency paused. Plans verified: acme dispatches (9 hot), acme-web dispatches (6 hot), beacon dispatches (6 hot). No issues found. Next: Codex restart triggers first real cycles.
- [2026-04-08] Fleet watchdog (post-v2.5.0): 0/6 shipping, 4 reset, 2 stale-exit. All 6 prompts rewritten, memories cleared, CB/auto_pause deadlocks fixed, Doctrine 14 + Working Philosophy shipped. New concern: `find_work` signal from vidux-loop.sh not handled by with-vidux gate prompts (falls through both exit and dispatch checks). Task 18.7 created. Next: Leo must restart Codex to pick up DB changes, then verify 18.5. [Evidence: fleet memory scan]
- [2026-04-08] Fleet watchdog: 1/7 shipping (14%), 5 idle, 1 mid-zone. Natural wind-down — acme-asc + launch-loop queues drained. Only acme-web still working (subtree extraction). acme-localization-pro still REDUCE-gated. beacon-release-train still shows exit 141 in memory (pre-fix). No code fix needed this cycle.
- [2026-04-07] Fleet watchdog (hourly): 2/7 shipping (29%), 4 idle, 1 mid-zone, 0 crashed. SIGPIPE fix confirmed — no exit 141 in active fleet. Found: acme-localization-pro still uses old REDUCE gate (created before scanner fix). Orchestrator mid-zone on dirty ai repo. Next: fix localization-pro toml to use SCAN gate.
- [2026-04-07] Cycle 40: 🔍→📐→⚡ FULL LOOP — Fleet audit of all 11 active Codex automations via 6-agent fan-out. Found: 2/11 shipping (18%), SIGPIPE exit 141 crashing 3+ automations, 5 Beacon automations on empty queue, broken radar→writer feedback loop, no cross-lane awareness. Fixed SIGPIPE (3 pipe patterns + consistent JSON schema). Planned Phase 17 (9 tasks). Paused 4 idle Beacon radars. Cross-lane awareness elevated to Doctrine 13 candidate. Evidence: `fleet-audit-11-automations.md`. Next: 17.2 (rename dispatch/reduce), 17.3 (Doctrine 13: cross-lane awareness).
- [2026-04-07] Cycle 39: ⚡→📌 CHECKPOINT — Phase 16 COMPLETE (3/3). Archived 2 project plans (nextjs-cve-sweep, vidux-stress-test). Updated README with Fleet Intelligence section (circuit breaker, idle-churn, REDUCE gate, mid-zone kill, radar template, compat). Phases 13-16 all shipped in one session. Queue empty — next cycle should REDUCE exit or plan Phase 17 from agentic research gaps.
- [2026-04-07] Cycle 38: 📐→⚡ PLAN+EXECUTE — Resolved Q5 (ship templates not full harnesses). Archived 38 tasks from phases 8-12 to ARCHIVE.md (230→~130 lines). Planned Phase 16 (3 tasks). Shipped 16.1 (archive). All open questions now answered. Next: 16.2 (prune stale projects), 16.3 (README update).
- [2026-04-07] Cycle 37: ⚡→📌 CHECKPOINT — Phase 15 COMPLETE (5/5). Shipped 15.4 (dispatch-side mid-zone kill in DOCTRINE.md + best-practices.md). Rule: 3+ min with no file write in dispatch = exit. Fleet data cited (32% mid-zone, target <15%). 2 contract tests. Phases 13-15 all complete. Next: research-driven Phase 16 or archive + plan pruning.
- [2026-04-07] Cycle 36: ⚡ EXECUTE — Shipped 15.3 (radar template at guides/vidux/radar-template.md). Extracted shared pattern from 3 Beacon radars (~80% identical). Template includes updated REDUCE gate with circuit_breaker, sizing guidance, examples. Contract test added. Phase 15: 4/5 done. Next: 15.4 (mid-zone enforcement).
- [2026-04-07] Cycle 35: ⚡ EXECUTE — Shipped 15.2 (idle-churn detection in witness.sh: per-automation idle_churn_pct + total_entries). Fixed compat.sh nounset guard. Verified: hourly-media-studio=100% churn, acme-android=66%, codex-orchestrator=33%. Next: 15.3 (radar template), 15.4 (mid-zone enforcement).
- [2026-04-07] Cycle 34: 🔍→📐→⚡ FULL LOOP — 3-agent fan-out (fleet memory analysis, ledger runtime patterns, prompt quality audit). Wrote comprehensive fleet loop analysis evidence. Planned Phase 15 (5 tasks). Shipped 15.1 (circuit breaker — scans Progress for shipping signals, blocks dispatch after 3 idle cycles) + 15.5 (2 contract tests). Evidence: `fleet-loop-analysis.md`. Key finding: 32% mid-zone rate, beacon-content 60% idle churn. Next: 15.2-15.4.
- [2026-04-07] Cycle 33: ⚡→📌 CHECKPOINT — Phase 13 COMPLETE (10/10 tasks). compat.sh portability layer confirmed done (hooks-created). All PLAN tasks synced to completed state. 159 tests, all scripts portable. Research evidence (MCO, OpenSpec, circuit breakers) committed. Next: Phase 14 (fleet restructuring) or Phase 15 (research-driven: circuit breaker, task DAG, lease ownership from agentic-patterns-research.md).
- [2026-04-07] Cycle 32: ⚡ EXECUTE — Phase 13 dispatch. Shipped 13.3 (checkpoint sed metachar fix — grep -nF by line number, _mark_task helper), 13.6-13.10 (10 new contract tests: witness JSON validity, compound task docs, doctrine content validation, empty-plan edge case, test-all self-test). 159 total tests. Next: 13.4 (portability layer).
- [2026-04-07] Cycle 31: 🔍→📐→⚡ FULL LOOP — 3-agent fan-out (agentic patterns, coverage audit, hardening audit). Synthesized into Phase 13 (10 tasks). Shipped 13.1 (json_escape +\r, learned python3 per-call too slow), 13.2 (config path injection — 15 instances/6 scripts), 13.5 (doctor 8→1 python3 calls). 149/149 tests pass. Evidence: `2026-04-07-hardening-audit.md`, `2026-04-07-coverage-gaps.md`. Next: 13.3-13.10.
- [2026-04-07] Cycle 30: 📐 PLAN — Fleet overnight diagnosis complete. Cadence-runtime mismatch is critical: 150+ runs across 4 acme lanes when 30-40 would ship the same work. Phase 14 added with 7 tasks. Evidence at `projects/vidux-v230/evidence/2026-04-07-fleet-overnight-diagnosis.md`. Next: fix cadences, add REDUCE gates, pause dead lanes.
- [2026-04-07] Cycle 29: 📐 PLAN — Public Vidux docs had drifted back to a stale DB-only retirement story even though the live machine still runs `26` repo-backed TOMLs plus `34` SQLite rows with an active orchestrator. Added `projects/context-ops/evidence/2026-04-07-public-vidux-control-plane-drift.md` and corrected the Decision Log so the 2026-04-06 DB-only cutover is treated as a historical experiment instead of current truth. Next: return to the `8` DB-only active rows for an explicit archive/promotion decision once a safe approval path exists.
- [2026-04-06] Cycle 28: ⚡ EXECUTE — Fleet rebuild complete. Deleted 22 old automations, created 11 new burst-mode harnesses (4 acme + 6 beacon + 1 vidux-meta). All 30-min cadence except vidux-meta (1hr). Prompts ~2.5-3K chars (down from 5-7K). Burst doctrine, self-extending plans, $picasso + product-taste focus baked into every harness. DB race with Codex app daemon discovered and fixed (close app before writes). Evidence: `projects/context-ops/evidence/2026-04-06-fleet-rebuild-final.md`. Next: verify automations run clean against live plans.
- [2026-04-06] Cycle 27: ⚡ EXECUTE — Retired repo-backed automation source control. Captured full fleet snapshot (13 active automations, topology, patterns, per-automation essence) into evidence. Deleted ai/automations/ from disk. Added gitignore entry. Decision Log entries recorded. Orchestrator role transferred to interactive Leo + Claude sessions. Next: clean up 11 paused DB rows, investigate endurance/v230 scheduler drift.
- [2026-04-06] Cycle 27: ⚡ EXECUTE → ✅ VERIFY — Ledger integration complete (Task 10.3). Built 3-file integration layer in scripts/lib/ (ledger-config.sh, ledger-emit.sh, ledger-query.sh). Wired into vidux-loop.sh (loop_start event, conflict check, ledger_available/ledger_conflicts in JSON output) and vidux-checkpoint.sh (checkpoint event after commit). Updated vidux-manager.md fleet-health and diagnose to use ledger queries. Validated against real production ledger: 3205 entries, 14 automations, bimodal scores computed (acme-ios: 70% critical). 83/83 tests pass. Next: automation recipes command, then testing.
- [2026-04-06] Cycle 26: ⚡ EXECUTE → ✅ VERIFY — Phase 8 retirement complete. Fixed 9 automation.toml files (old ai/skills/vidux path → canonical vidux repo). Removed dead ralph refs from orchestrator, dead vidux-amp from media-studio, converted acme-android relative paths to absolute. Symlink at ai/skills/vidux removed. Next: Phase 10 remaining tasks (10.2, 10.3, 10.7).
- [2026-04-06] Cycle 25: ⚡ EXECUTE → ✅ VERIFY — Phase 10 Tasks 10.1, 10.4, 10.5, 10.6 complete. Stage indicators embedded in /vidux command (6 stages + 3 meta + depth). "DIE" → "COMPLETE" across 9 files. Dashboard command (205 lines), manager command (312 lines), prune script (387 lines) all delivered by team agents. Ralph skill deleted from ~/.claude and ~/.codex. "nursing" → "maintenance" in SKILL.md. Checkpoint.sh git guard added. 83/83 tests pass. 11 agents fanned out total. Next: 10.2 config extensions, 10.3 ledger integration, 10.7 contract tests.
- [2026-04-06] Cycle 24: 📐 PLAN — Phase 10 designed via 5-agent fan-out. Stage indicators, dashboard, ledger integration, backpressure, vidux-manager all specified. 7 tasks, 3 open questions. Evidence synthesis written. 7 additional research agents launched (audit, platform comparison, radar-writer architecture, plan store protection).
- [2026-04-06] Cycle 23: Fleet quality inspector built (vidux-fleet-quality.sh). Scans 15 automations, classifies run durations, reports bimodal verdict. Phase 9 Tasks 1+2+3 done. Next: Phase 9 Task 4 (e2e test) — already validated via self-investigation.
- [2026-04-06] Cycle 22: Example fleet configs created (examples/fleet-reference/). 4 automations: writer + 2 radars + coordinator, staggered slots, lean prompts. Phase 9 Tasks 1+3 done. Next: quality inspector and e2e test.
- [2026-04-06] Cycle 21: Bimodal runtime enforcement added to vidux-doctor.sh (CHECK 11). Self-investigation 5/5 tasks COMPLETE. Phase 9 Task 1 done. 83/83 tests passing, 11/11 doctor checks. Next: Phase 9 remaining tasks (quality inspector, fleet configs, e2e test).
- [2026-04-06] Cycle 20: E2e results collected. NextJS 17/20, iOS 19/20. Both created compound task investigations. Plan quality validated across web and mobile. Self-investigation 4/5 tasks complete. Committing all Phase 8 work. Next: bimodal runtime simulation, then Phase 9.
- [2026-04-06] Cycle 19: Self-investigation launched. Fixed stale skill directory (was copy, now symlink). Discovered 14 automations hardcode old path. Prompt quality audit: most prompts 3-7x too long. E2e test agents swarming on NextJS and iOS — both creating compound task investigations (good). Next: collect e2e results, update investigation PLAN.md, fix automation paths.
- [2026-04-06] Cycle 18: Canonical unification — restored full build history, brought over vidux-development evidence, retired ai/skills/vidux copy. This repo is now the single source of truth.
- [2026-04-06] Cycle 17.5: Published open source repo (user/vidux). Added README, LICENSE, CONTRIBUTING, guides, .github templates. Rewired all paths to standalone.
- [2026-04-01] Cycle 17: Final session wrap. Hot/cold window in loop script. Archive mode in checkpoint. Tagline aligned. 4-agent audit fixed 12 mismatches. Backed up to user/ai (PR #1). 34/34 tests. V1 COMPLETE.
- [2026-04-01] Cycle 16: V1 finalization complete. Expanded harness (10 -> 34 tests, all passing). 3 guides written (quickstart 88 lines, architecture 181 lines, best practices 187 lines). All 4 scripts verified working. Symlinks verified across 3 tool mounts. Phase 6 complete. Next: cross-tool test (human-blocked). Blocker: none.
- [2026-04-01] Cycle 15: Test cycle: verified scripts work. Next: Add PreToolUse hook guidance: check if target file is in PLAN.md [Evidence: needed]. Blocker: none.
- [2026-03-31 20:15] Cycle 0: Initial SKILL.md + PLAN.md + DOCTRINE.md created. 9 research agents completed. Doctrine established. Cron set up.
- [2026-03-31 20:45] Cycle 1: Open source survey complete (26 tools). Top ingredients identified. Evidence + surprises added to plan. Next: LOOP.md.
- [2026-04-01 00:15] Cycle 2: Architecture refined (two data structures: doc tree + work queue). Company-agnostic layer separation added.
- [2026-04-01 00:30] Cycle 3: 5-agent swarm completed Phase 1 + Phase 2 + contract tests. INGREDIENTS.md, vidux-loop.sh, vidux-checkpoint.sh, vidux-gather.sh, test_vidux_contracts.py all landed. Merged main (pilot improvements). 10/10 tests pass. Next: Phase 3 enforcement + Phase 4 plugin packaging.
- [2026-04-01 01:00] Cycle 4: 3-agent swarm for Phase 3+4. Plugin packaging landed (manifest + 3 commands + hooks.json). ENFORCEMENT.md landed (389 lines, 4 hooks, three-strike gate, enforcement gradient). E2E tests 5/5 pass. Phase 1-4 COMPLETE. Next: Phase 5 integration (Captain install, cross-tool test).
- [2026-04-01 05:07] Cycle 5: Captain install wiring. Surprise: no Captain changes needed — auto-installs via existing symlinks. Added install-hooks.sh (optional enforcement). Next: cross-tool test. Blocker: none.
- [2026-04-01 06:07] Cycle 6: Answered Q2 — plan readiness checklist. Upgraded LOOP.md with 10-point scoring system (5 required + 5 quality). Threshold: 7/10 to code, below = refine plan. Next: Q3 (plugin format).
- [2026-04-01 07:07] Cycle 7: Answered Q3 — SKILL.md alone is the cross-tool format (agentskills.io standard). Plugin manifests NOT needed for interop. Surprise: Phase 4 was over-engineered. Next: Q4.
- [2026-04-01 08:07] Cycle 8: Answered Q4 — Agent subagents beat Teams for cron fan-out. Teams violate stateless doctrine. Next: Q1 (EARS notation).
- [2026-04-01 09:07] Cycle 9: Answered Q1 — EARS for acceptance criteria only (Done-When tags). All 4 open questions now answered. All 5 phases complete except 2 human-blocked tasks. Vidux 1.0 autonomous build is DONE. Remaining: Leo tests cross-tool and cross-machine manually.
<!-- 1 tasks archived to ARCHIVE.md -->
