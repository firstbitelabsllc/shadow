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
- [Source: lkwan feedback] "We're not planning enough. We're coding while thinking." Vidux doctrine is the response.
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
- Reviewer preference (lkwan): Sports analogies (point guard, ref), not political ones (mayor)

## Decisions
- [2026-03-31] Decision: Vidux is a skill first, plugin packaging later. Rationale: Skills work NOW across all tools. Plugins are Claude-only. Can wrap in plugin manifest later.
- [2026-03-31] Decision: PLAN.md lives in the branch, not globally. Rationale: Travels with code, visible in PRs, any machine gets it on git fetch.
- [2026-03-31] Decision: Fan-out/fan-in for plan refinement, not 20 agents editing one file. Rationale: Research shows 17x error amplification. 4-agent groups with one synthesizer is the sweet spot.
- [2026-03-31] Decision: Two modes — Pilot for Mode A (small), Vidux for Mode B (quarter-long). Don't try to make one system do both.
- [2026-03-31] Decision: Channel Yegge (git-backed state, propulsion) and jlee (harness, dual five-whys) as advisor philosophies. Not literal framework adoption.
- [2026-04-06] Decision: Publish the portable Vidux core in its own public repo (`leojkwan/vidux`) instead of exposing the entire `ai` skills repo. Rationale: the core is reusable, while `ai/` carries personal and project-specific wiring.
- [2026-04-06] Decision: This repo is the canonical home for Vidux. The copy in `ai/skills/vidux/` is retired. All framework development happens here.

## Tasks

### Phase 1: Core Doctrine — COMPLETE
- [x] Write this PLAN.md (meta: Vidux plans itself)
- [x] Write DOCTRINE.md — standalone principles doc (the 60%) for quick reference
- [x] Set up hourly cron to iterate on these docs
- [x] Survey 26 open source skills/plugins for ingredients [Evidence: research agent]
- [x] Write LOOP.md — detailed loop mechanics (the 30%) with examples [Done: 2026-03-31]
- [x] Write INGREDIENTS.md — top 10 open source patterns to adopt with attribution [Done: 2026-03-31]

### Phase 2: Loop Implementation — COMPLETE
- [x] Write `vidux-loop.sh` — stateless cycle script (113 lines, JSON output, 7 edge cases) [Done: 2026-04-01]
- [x] Write `vidux-gather.sh` — fan-out research template generator [Done: 2026-04-01]
- [x] Write `vidux-checkpoint.sh` — structured checkpoint writer (81 lines, idempotent) [Done: 2026-04-01]
- [x] Test one full cycle: gather -> plan -> execute -> verify -> checkpoint [Depends: all above] [Done: 2026-04-01]

### Phase 3: Enforcement — COMPLETE
- [x] Add PreToolUse hook guidance + full ENFORCEMENT.md (389 lines, 4 hooks, three-strike gate) [Done: 2026-04-01]
- [x] Add /harness integration for failure protocol (three-strike gate in ENFORCEMENT.md) [Done: 2026-04-01] [Evidence: Jeffrey's PR #265]
- [x] Add contract tests (10 tests, all passing) [Done: 2026-04-01] [Evidence: Jeffrey's pattern]

### Phase 4: Plugin Packaging — COMPLETE
- [x] Create .claude-plugin/plugin.json manifest [Done: 2026-04-01]
- [x] Create /vidux command wrapper [Done: 2026-04-01]
- [x] Create /vidux-plan command (plan-only mode) [Done: 2026-04-01]
- [x] Create /vidux-status command (quick status check) [Done: 2026-04-01]

### Phase 5: Integration
- [x] Wire ledger lifecycle events (AGENT_LANE, mission_id) — DONE on main via pilot-ledger-emit.sh [Done: 2026-04-01]
- [x] Wire project-specific build recipe — DONE on main [Done: 2026-04-01]
- [x] Wire Captain install — no changes needed, auto-installs via symlinks. Added install-hooks.sh for optional enforcement. [Done: 2026-04-01]
- [x] [P2 — deferred] Cross-tool and cross-machine testing moved to future scope. Solo-computer, source-controlled is the v1 contract. [Done: 2026-04-01]

### Phase 6: V1 Finalization — Harness + Guides
- [x] Expand harness: contract tests for scripts (executable, valid JSON), commands (frontmatter), hooks (valid JSON), ENFORCEMENT.md (4 hooks), INGREDIENTS.md (10 items) [Evidence: Jeffrey's contract-test-as-harness pattern from PR #265] [Done: 2026-04-01]
- [x] Write quickstart guide: guides/vidux/quickstart.md — activation, installation, first /vidux run [Done: 2026-04-01]
- [x] Write architecture guide: guides/vidux/architecture.md — two data structures, unidirectional flow, Layer 1 vs Layer 2, Redux analogy [Done: 2026-04-01]
- [x] Write best practices guide: guides/vidux/best-practices.md — PLAN.md writing, overnight cron, fan-out, common mistakes, Vidux vs Pilot [Done: 2026-04-01]
- [x] End-to-end verification: run expanded harness, verify all scripts, verify symlinks, checkpoint [Depends: all Phase 6 above] [Done: 2026-04-01]

### Phase 7: Open Source Publication — COMPLETE
- [x] Export the portable Vidux core into its own public repo with docs, commands, scripts, hooks, and tests. [Done: 2026-04-06]
- [x] Add README, LICENSE, CONTRIBUTING, .github templates. [Done: 2026-04-06]
- [x] Rewire all paths from `skills/vidux/` to repo-root. [Done: 2026-04-06]

### Phase 8: Canonical Unification — IN PROGRESS
- [x] Restore full build history PLAN.md to public repo. [Done: 2026-04-06]
- [x] Bring over vidux-development project evidence (v230, endurance, stress-test). [Done: 2026-04-06]
- [x] Bring over ARCHIVE.md and SETUP_NEW_MACHINE.md. [Done: 2026-04-06]
- [x] Build /vidux-loop command — fleet creation, lean prompts, staggered schedules, coordinator pattern, bimodal quality enforcement. [Done: 2026-04-06]
- [x] Fix "smallest slice" language in /vidux command — agents keep working through queue until real boundary. [Done: 2026-04-06]
- [x] Absorb Ralph into vidux core — Ralph had no hooks, no commands, just a SKILL.md. Queue contract is PLAN.md task FSM. Removed all references. [Done: 2026-04-06]
- [completed] Integrate ledger into this repo — built thin integration layer (scripts/lib/ledger-config.sh, ledger-emit.sh, ledger-query.sh) that discovers ~/.agent-ledger/ and provides fleet analysis functions. Wired into vidux-loop.sh (loop_start, conflict check, ledger_available in JSON output) and vidux-checkpoint.sh (checkpoint events). Updated vidux-manager.md to use ledger-query.sh. 83/83 tests pass. [Done: 2026-04-06] [Evidence: real ledger data: 3205 entries, 14 automations, bimodal scores computed]
- [completed] Retire `ai/skills/vidux/` — all 9 automation.toml files updated to canonical path. Ralph + vidux-amp dead refs removed. ai/skills/vidux symlink removed. [Done: 2026-04-06] [Evidence: `projects/vidux-self-investigation/evidence/2026-04-06-stale-path-audit.md`]

### Phase 9: Automation Quality — COMPLETE
- [completed] Add bimodal runtime enforcement to vidux-doctor.sh — CHECK 11: flags projects where >30% of runs fall in 3-8 min dead zone. Uses git commit timestamps. [Done: 2026-04-06]
- [completed] Build automation quality inspector — vidux-fleet-quality.sh reads memory.md files, classifies runs (quick/deep/mid/normal), reports per-automation and fleet-wide bimodal quality. [Done: 2026-04-06]
- [completed] Create example fleet configs for a reference project (writer + 2 radars + coordinator, staggered schedule). [Done: 2026-04-06] [Evidence: examples/fleet-reference/]
- [completed] End-to-end test: ran /vidux from scratch on NextJS (17/20) and iOS (19/20). Both created compound task investigations. Plan quality validated. [Done: 2026-04-06] [Evidence: projects/vidux-self-investigation/evidence/2026-04-06-e2e-plan-quality.md]

### Phase 10: Visibility, Intelligence & Health — IN PROGRESS

**Goal:** Make vidux self-aware, visible, and self-healing. Clear stage indicators, cross-tool dashboard, ledger-powered coordination, backpressure, and a manager that can diagnose and test itself.

[Evidence: 5-agent fan-out research synthesis at `projects/vidux-self-investigation/evidence/2026-04-06-phase10-research-synthesis.md`]

- [completed] **10.1 Stage indicators** — 6 primary stages (🔍 GATHER, 📐 PLAN, ⚡ EXECUTE, ✅ VERIFY, 📌 CHECKPOINT, 🏁 COMPLETE) + 3 meta-stages + depth tracking [L1/L2/L3]. Embedded in /vidux command. "DIE" renamed to "COMPLETE" across 9 files. "Design for yield" renamed to "Design for completion." [Done: 2026-04-06]
- [ ] **10.2 vidux.config.json extensions** — Add `plan_storage_root`, `external_plan_roots[]`, `dashboard.*`, `ledger.*`, `pruning.*`, `backpressure.*` config sections. Foundation for all Phase 10 features.
- [completed] **10.3 Ledger integration** — Built 3-file integration layer: ledger-config.sh (discovery + fallback), ledger-emit.sh (vidux_loop_start/end, checkpoint, plan_modified, fleet_health events), ledger-query.sh (bimodal_distribution, automation_runs, handoff_gaps, fleet_health, conflict_check). Wired into vidux-loop.sh and vidux-checkpoint.sh. vidux-manager.md updated to use ledger queries. Validated against real production ledger (3205 entries, 14 automations). [Done: 2026-04-06]
- [completed] **10.4 /vidux-dashboard command** — 3-source plan discovery (local projects/, ~/.codex/automations/, ~/.claude/ + external roots). Tree view with status, health, last activity. JSON mode. 205 lines. [Done: 2026-04-06]
- [completed] **10.5 vidux-prune.sh** — Subcommands: plans, worktrees, ledger, all, pressure. Plan archival at threshold. Worktree lifecycle. Ledger compaction. Circuit breaker. Pressure scoring 0-10. Dry-run mode. 387 lines. [Done: 2026-04-06]
- [completed] **10.6 /vidux-manager command** — 4 modes: diagnose, test, investigate, fleet-health. Stage indicators integrated. Quality scoring against 17-19/20 baseline. 312 lines. [Done: 2026-04-06]
- [ ] **10.7 Contract tests** — Cover all new scripts (ledger-config.sh, vidux-prune.sh), commands (vidux-dashboard.md, vidux-manager.md), and config schema validation. [Depends: 10.1-10.6]

### Phase 10 Open Questions
- [ ] Q6: Max plan nesting depth — research says 3, stage indicators support 4. Decision: 3 enforced by dashboard, 4th level allowed but flagged as "consider splitting."
- [ ] Q7: Dashboard refresh — real-time (tail -f) vs polling (5s interval) vs on-demand only? Start with on-demand for simplicity, add watch mode later.
- [ ] Q8: Ledger as vendored dependency or external install? Start vendored (scripts/lib/), extract to separate package if community adopts.

## Open Questions
- [x] Q1: EARS for acceptance criteria only, not tasks/constraints/evidence. Add optional `[Done-When: EARS statement]` per task or phase-level acceptance criteria blocks. Current task format (checkbox + evidence + depends) is better for agent execution. Kiro validates: EARS for specs, free-form for tasks. [Done: 2026-04-01]
- [x] Q2: Plan readiness = 10-point checklist in LOOP.md. 5 required gates + 5 quality points. Score >= 7 to code, < 7 means refine the plan. [Done: 2026-04-01]
- [x] Q3: SKILL.md alone is sufficient for all 3 tools (agentskills.io open standard). Plugin manifests are for marketplace distribution only, not cross-tool compat. Captain symlinks handle discovery. [Done: 2026-04-01]
- [x] Q4: Agent subagents (not Teams) for fan-out. Teams persist across sessions (violates stateless doctrine), add coordination overhead, and risk orphaned state if cron dies. Subagents are fire-and-forget, perfect for embarrassingly parallel research. Teams reserved for future multi-turn critic debates. [Done: 2026-04-01]
- [ ] Q5: Should the public repo ship example automation harnesses, or stay focused on the skill and loop contract first? -> Action: gather feedback from Issues after first publish.

## Surprises
- [2026-03-31] obra/superpowers (128K stars) already installed in our env. Its brainstorm->plan->execute->verify chain is close to Vidux's gather->plan->execute->verify. Could be a companion rather than competitor.
- [2026-03-31] tick-md (18 stars) uses a single TICK.md file as Git-backed multi-agent task board — structurally identical to what Vidux PLAN.md does. Low stars but exact pattern match.
- [2026-03-31] PAUL (603 stars) has Execute/Qualify/Unify loop with escalation statuses (DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, BLOCKED). The UNIFY step (reconcile planned vs actual) is a gap in our design — should add.
- [2026-04-01] Previous session already landed pilot-ledger-emit.sh + project build recipe + env vars on main (commit 1c8c0f9). Merged into vidux branch. Phase 5 integration is partially done for free.
- [2026-04-01] All 5 swarm agents completed successfully in parallel. Phase 1 + Phase 2 + contract tests all done in one burst. 10/10 tests passing.
- [2026-04-06] The first scaffold pass accidentally mirrored internal root plan files. Impact: public repo would have leaked the wrong story.
- [2026-04-06] Self-investigation revealed: ~/.claude/skills/vidux was a stale DIRECTORY copy, not a symlink. Fixed. But 14 automation prompts hardcode `ai/skills/vidux/SKILL.md`, bypassing all symlinks. Every automation run loads stale vidux with Ralph, old paths, and "smallest slice" language.
- [2026-04-06] Prompt quality audit: strongyes-release-train is 56 lines, 73% restated doctrine. resplit-nurse is ~120 lines. Lean version is 13 lines with 100% project-specific signal density.
- [2026-04-06] Ralph skill was never deleted in Phase 8 — stale copies persisted at ~/.claude/skills/ralph/ and ~/.codex/skills/ralph/ (6157 bytes each, dated Mar 28). Also found resplit-nurse codex automation (7816 bytes, ACTIVE, runs every 20min) still referencing RALPH.md.
- [2026-04-06] vidux-checkpoint.sh had no git repo guard — running on a plan outside a git repo produced raw git `fatal:` error (exit 128). Fixed with rev-parse check.
- [2026-04-06] Claude Code has 3 tiers of scheduling: /loop (ephemeral, 1min), Desktop Scheduled Tasks (persistent, local, 1min), Cloud Scheduled Tasks (Anthropic infra, 1hr). Desktop tasks are the Claude equivalent of Codex automations.

## Decision Log
- [DIRECTION] [2026-04-06] Stage indicators use emoji prefixes (🔍📐⚡✅📌) not color-only. Reason: works in terminal, IDE, CI, and copy-paste. Do not switch to color-only.
- [DIRECTION] [2026-04-06] Max plan nesting depth = 3, with L4 allowed but flagged. Reason: research shows 17x error amplification beyond 4 agents; 3-deep keeps coordination manageable.
- [DIRECTION] [2026-04-06] Ledger is centralized at ~/.agent-ledger/ (not per-project). Reason: single source of truth for cross-tool, cross-worktree coordination. Dashboard reads one location.
- [DIRECTION] [2026-04-06] Dashboard index is machine-local (not git-backed). Reason: plans travel with code via git; dashboard aggregation is local concern. No pollution of repos.
- [DIRECTION] [2026-04-06] vidux-prune.sh has dry-run (--simulate) by default for destructive ops. Reason: pruning completed plans is irreversible without git history spelunking.
- [DIRECTION] [2026-04-06] Automations are DB-only. No repo-backed TOMLs. Reason: repo ↔ DB sync was the #1 time sink — constant drift, constant churn. SQLite is the live truth. Leo + Claude are the orchestrator now. Fleet snapshot preserved at `projects/context-ops/evidence/2026-04-06-fleet-snapshot-before-retirement.md`. Do not recreate repo-backed TOML source control.
- [DELETION] [2026-04-06] Removed ai/automations/ directory and codex-automation-orchestrator automation role. Reason: replaced by interactive Leo + Claude orchestration via /vidux. Do not re-add repo-backed automation files.
- [CORRECTION] [2026-04-06] Treat the DB-only retirement notes above as a premature branch-local experiment, not durable live truth. The live control plane on this machine still consists of `27` repo-backed `ai/automations` definitions plus SQLite, and the Codex orchestrator remains active until an explicit cutover is shipped and verified.

## Progress
- [2026-04-06] Cycle 27: ⚡ EXECUTE — Retired repo-backed automation source control. Captured full fleet snapshot (13 active automations, topology, patterns, per-automation essence) into evidence. Deleted ai/automations/ from disk. Added gitignore entry. Decision Log entries recorded. Orchestrator role transferred to interactive Leo + Claude sessions. Next: clean up 11 paused DB rows, investigate endurance/v230 scheduler drift.
- [2026-04-06] Cycle 28: Context Ops self-audit rechecked the live machine and found the DB-only retirement story was premature. Current state still has 27 repo-backed ai automation definitions, 33 SQLite rows, a 6-row DB-only StrongYes cluster, and zero drift across the 27 shared repo/DB rows. The real bug was stale authority copy, not a missing repo-backed fleet. Corrected the public story so future control-plane runs trust live filesystem + DB truth until a real cutover lands.
- [2026-04-06] Cycle 27: ⚡ EXECUTE → ✅ VERIFY — Ledger integration complete (Task 10.3). Built 3-file integration layer in scripts/lib/ (ledger-config.sh, ledger-emit.sh, ledger-query.sh). Wired into vidux-loop.sh (loop_start event, conflict check, ledger_available/ledger_conflicts in JSON output) and vidux-checkpoint.sh (checkpoint event after commit). Updated vidux-manager.md fleet-health and diagnose to use ledger queries. Validated against real production ledger: 3205 entries, 14 automations, bimodal scores computed (resplit-ios: 70% critical). 83/83 tests pass. Next: automation recipes command, then testing.
- [2026-04-06] Cycle 26: ⚡ EXECUTE → ✅ VERIFY — Phase 8 retirement complete. Fixed 9 automation.toml files (old ai/skills/vidux path → canonical /Users/leokwan/Development/vidux). Removed dead ralph refs from orchestrator, dead vidux-amp from media-studio, converted resplit-android relative paths to absolute. Symlink at ai/skills/vidux removed. Next: Phase 10 remaining tasks (10.2, 10.3, 10.7).
- [2026-04-06] Cycle 25: ⚡ EXECUTE → ✅ VERIFY — Phase 10 Tasks 10.1, 10.4, 10.5, 10.6 complete. Stage indicators embedded in /vidux command (6 stages + 3 meta + depth). "DIE" → "COMPLETE" across 9 files. Dashboard command (205 lines), manager command (312 lines), prune script (387 lines) all delivered by team agents. Ralph skill deleted from ~/.claude and ~/.codex. "nursing" → "maintenance" in SKILL.md. Checkpoint.sh git guard added. 83/83 tests pass. 11 agents fanned out total. Next: 10.2 config extensions, 10.3 ledger integration, 10.7 contract tests.
- [2026-04-06] Cycle 24: 📐 PLAN — Phase 10 designed via 5-agent fan-out. Stage indicators, dashboard, ledger integration, backpressure, vidux-manager all specified. 7 tasks, 3 open questions. Evidence synthesis written. 7 additional research agents launched (audit, platform comparison, radar-writer architecture, plan store protection).
- [2026-04-06] Cycle 23: Fleet quality inspector built (vidux-fleet-quality.sh). Scans 15 automations, classifies run durations, reports bimodal verdict. Phase 9 Tasks 1+2+3 done. Next: Phase 9 Task 4 (e2e test) — already validated via self-investigation.
- [2026-04-06] Cycle 22: Example fleet configs created (examples/fleet-reference/). 4 automations: writer + 2 radars + coordinator, staggered slots, lean prompts. Phase 9 Tasks 1+3 done. Next: quality inspector and e2e test.
- [2026-04-06] Cycle 21: Bimodal runtime enforcement added to vidux-doctor.sh (CHECK 11). Self-investigation 5/5 tasks COMPLETE. Phase 9 Task 1 done. 83/83 tests passing, 11/11 doctor checks. Next: Phase 9 remaining tasks (quality inspector, fleet configs, e2e test).
- [2026-04-06] Cycle 20: E2e results collected. NextJS 17/20, iOS 19/20. Both created compound task investigations. Plan quality validated across web and mobile. Self-investigation 4/5 tasks complete. Committing all Phase 8 work. Next: bimodal runtime simulation, then Phase 9.
- [2026-04-06] Cycle 19: Self-investigation launched. Fixed stale skill directory (was copy, now symlink). Discovered 14 automations hardcode old path. Prompt quality audit: most prompts 3-7x too long. E2e test agents swarming on NextJS and iOS — both creating compound task investigations (good). Next: collect e2e results, update investigation PLAN.md, fix automation paths.
- [2026-04-06] Cycle 18: Canonical unification — restored full build history, brought over vidux-development evidence, retired ai/skills/vidux copy. This repo is now the single source of truth.
- [2026-04-06] Cycle 17.5: Published open source repo (leojkwan/vidux). Added README, LICENSE, CONTRIBUTING, guides, .github templates. Rewired all paths to standalone.
- [2026-04-01] Cycle 17: Final session wrap. Hot/cold window in loop script. Archive mode in checkpoint. Tagline aligned. 4-agent audit fixed 12 mismatches. Backed up to lkwan/ai (PR #1). 34/34 tests. V1 COMPLETE.
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
