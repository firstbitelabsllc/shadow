# Archived Tasks

Tasks completed and archived from PLAN.md to keep context lean.

## Archived 2026-04-01
- [x] Write SKILL.md with doctrine, loop mechanics, PLAN.md structure, failure protocol

## Archived 2026-04-07
- [x] Write this PLAN.md (meta: Vidux plans itself)
- [x] Write DOCTRINE.md — standalone principles doc (the 60%) for quick reference
- [x] Set up hourly cron to iterate on these docs
- [x] Survey 26 open source skills/plugins for ingredients [Evidence: research agent]
- [x] Write LOOP.md — detailed loop mechanics (the 30%) with examples [Done: 2026-03-31]
- [x] Write INGREDIENTS.md — top 10 open source patterns to adopt with attribution [Done: 2026-03-31]
- [x] Write `vidux-loop.sh` — stateless cycle script (113 lines, JSON output, 7 edge cases) [Done: 2026-04-01]
- [x] Write `vidux-gather.sh` — fan-out research template generator [Done: 2026-04-01]
- [x] Write `vidux-checkpoint.sh` — structured checkpoint writer (81 lines, idempotent) [Done: 2026-04-01]
- [x] Test one full cycle: gather -> plan -> execute -> verify -> checkpoint [Depends: all above] [Done: 2026-04-01]
- [x] Add PreToolUse hook guidance + full ENFORCEMENT.md (389 lines, 4 hooks, three-strike gate) [Done: 2026-04-01]
- [x] Add /harness integration for failure protocol (three-strike gate in ENFORCEMENT.md) [Done: 2026-04-01] [Evidence: Jeffrey's PR #265]
- [x] Add contract tests (10 tests, all passing) [Done: 2026-04-01] [Evidence: Jeffrey's pattern]
- [x] Create .claude-plugin/plugin.json manifest [Done: 2026-04-01]
- [x] Create /vidux command wrapper [Done: 2026-04-01]
- [x] Create /vidux-plan command (plan-only mode) [Done: 2026-04-01]
- [x] Create /vidux-status command (quick status check) [Done: 2026-04-01]
- [x] Wire ledger lifecycle events (AGENT_LANE, mission_id) — DONE on main via pilot-ledger-emit.sh [Done: 2026-04-01]
- [x] Wire project-specific build recipe — DONE on main [Done: 2026-04-01]
- [x] Wire Captain install — no changes needed, auto-installs via symlinks. Added install-hooks.sh for optional enforcement. [Done: 2026-04-01]
- [x] [P2 — deferred] Cross-tool and cross-machine testing moved to future scope. Solo-computer, source-controlled is the v1 contract. [Done: 2026-04-01]
- [x] Expand harness: contract tests for scripts (executable, valid JSON), commands (frontmatter), hooks (valid JSON), ENFORCEMENT.md (4 hooks), INGREDIENTS.md (10 items) [Evidence: Jeffrey's contract-test-as-harness pattern from PR #265] [Done: 2026-04-01]
- [x] Write quickstart guide: guides/vidux/quickstart.md — activation, installation, first /vidux run [Done: 2026-04-01]
- [x] Write architecture guide: guides/vidux/architecture.md — two data structures, unidirectional flow, Layer 1 vs Layer 2, Redux analogy [Done: 2026-04-01]
- [x] Write best practices guide: guides/vidux/best-practices.md — PLAN.md writing, overnight cron, fan-out, common mistakes, Vidux vs Pilot [Done: 2026-04-01]
- [x] End-to-end verification: run expanded harness, verify all scripts, verify symlinks, checkpoint [Depends: all Phase 6 above] [Done: 2026-04-01]
- [x] Export the portable Vidux core into its own public repo with docs, commands, scripts, hooks, and tests. [Done: 2026-04-06]
- [x] Add README, LICENSE, CONTRIBUTING, .github templates. [Done: 2026-04-06]
- [x] Rewire all paths from `skills/vidux/` to repo-root. [Done: 2026-04-06]
- [x] Restore full build history PLAN.md to public repo. [Done: 2026-04-06]
- [x] Bring over vidux-development project evidence (v230, endurance, stress-test). [Done: 2026-04-06]
- [x] Bring over ARCHIVE.md and SETUP_NEW_MACHINE.md. [Done: 2026-04-06]
- [x] Build /vidux-loop command — fleet creation, lean prompts, staggered schedules, coordinator pattern, bimodal quality enforcement. [Done: 2026-04-06]
- [x] Fix "smallest slice" language in /vidux command — agents keep working through queue until real boundary. [Done: 2026-04-06]
- [x] Absorb Ralph into vidux core — Ralph had no hooks, no commands, just a SKILL.md. Queue contract is PLAN.md task FSM. Removed all references. [Done: 2026-04-06]
- [completed] Integrate ledger into this repo — built thin integration layer (scripts/lib/ledger-config.sh, ledger-emit.sh, ledger-query.sh) that discovers ~/.agent-ledger/ and provides fleet analysis functions. Wired into vidux-loop.sh (loop_start, conflict check, ledger_available in JSON output) and vidux-checkpoint.sh (checkpoint events). Updated vidux-manager.md to use ledger-query.sh. 83/83 tests pass. [Done: 2026-04-06] [Evidence: real ledger data: 3205 entries, 14 automations, bimodal scores computed]
- [completed] Retire `ai/skills/vidux/` — all 9 automation.toml files updated to canonical path. Ralph + vidux-amp dead refs removed. ai/skills/vidux symlink removed. [Done: 2026-04-06] [Evidence: `projects/vidux-self-investigation/evidence/2026-04-06-stale-path-audit.md`]
- [completed] Add bimodal runtime enforcement to vidux-doctor.sh — CHECK 11: flags projects where >30% of runs fall in 3-8 min dead zone. Uses git commit timestamps. [Done: 2026-04-06]
- [completed] Build automation quality inspector — vidux-fleet-quality.sh reads memory.md files, classifies runs (quick/deep/mid/normal), reports per-automation and fleet-wide bimodal quality. [Done: 2026-04-06]

## Archived 2026-04-07 (Cycle 38) — Phases 8-12

### Phase 8: Canonical Unification
### Phase 9: Automation Quality — fleet configs, e2e tests (NextJS 17/20, iOS 19/20)
### Phase 10: Visibility, Intelligence & Health — 7 tasks (10.1-10.7): stage indicators, config extensions, ledger integration, dashboard, prune, manager, 30 contract tests
### Phase 11: Dispatch/Reduce + Fleet Hardening — 9 tasks (11.1-11.9): doctrine bake, dispatch.sh, reduce mode, exit-criteria, Codex DB resilience, stale ref prune, queue-jsonl, lifecycle hooks. 11.5 blocked (Vercel MCP).
### Phase 12: Continuous Feedback Loop — 6 tasks (12.1-12.6): merge-gate, auto-pause, bimodal enforcement, witness.sh, self-extension metric, 11 contract tests (149 total)

## Archived 2026-04-08
- [completed] **13.1 Harden json_escape** — Added `\r` escape handling across 5 scripts. Attempted python3 delegation but reverted due to ~80ms/call overhead causing 4 test timeouts. Process fix: never spawn subprocesses in hot-path JSON helpers. [Done: 2026-04-07] [Evidence: hardening-audit.md#2]
- [completed] **13.2 Fix config path injection** — All 15 `python3 -c "...open('$CONFIG')..."` calls across 6 scripts now pass path via sys.argv[1]. vidux-doctor.sh batched 8 calls into 1. [Done: 2026-04-07] [Evidence: hardening-audit.md#5]
- [completed] **13.3 Fix checkpoint sed metacharacter handling** — Used grep -Fn line addressing instead of sed regex. No regex in the task text path. [Done: 2026-04-07] [Evidence: commit f30b05a]
- [completed] **13.4 Add portability layer for stat/date** — scripts/lib/compat.sh created (60 lines): file_mtime_epoch, dir_newest_mtime, parse_date_epoch, parse_iso_epoch. OS detection once at source-time. vidux-prune.sh and vidux-witness.sh both source it, no raw stat -f/date -j calls remain. [Done: 2026-04-07] [Evidence: hardening-audit.md#4]
- [completed] **13.5 Batch config reads into single python3 call** — Merged into 13.2: vidux-doctor.sh now reads all 8 config values in one python3 call. [Done: 2026-04-07] [Evidence: hardening-audit.md#9]
- [completed] **13.6 Contract tests: witness.sh functional tests** — 2 tests: JSON validity + fleet_grade is A-F letter. [Done: 2026-04-07] [Evidence: coverage-gaps.md#1]
- [completed] **13.7 Contract tests: test-all.sh self-test** — 1 test: --json produces valid JSON with overall and sections array. [Done: 2026-04-07] [Evidence: coverage-gaps.md#3]
- [completed] **13.8 Contract tests: compound task / investigation docs** — 2 tests: SKILL.md Compound Tasks section + investigation template required sections. [Done: 2026-04-07] [Evidence: coverage-gaps.md#5]
- [completed] **13.9 Contract tests: doctrine content contracts** — 4 tests: Principle 5 (compaction in SKILL.md), 7 (investigation/nested), 8 (harness/stateless), 9 (coordinator/subagent). [Done: 2026-04-07] [Evidence: coverage-gaps.md#7,12]
- [completed] **13.10 Contract tests: edge cases** — 1 test: empty Tasks → valid JSON with hot_tasks=0. [Done: 2026-04-07] [Evidence: coverage-gaps.md#9]
- [completed] **14.1 Fix cadence-runtime mismatches** — All active automations moved to 1x/hr with staggered BYMINUTE values. Fleet: 46 runs/hr → 12 runs/hr. [Done: 2026-04-07]
- [completed] **14.2 Design and ship REDUCE gate prompt block** — Both variants (with-vidux + standalone) designed and shipped to DOCTRINE.md, best-practices.md, and all 12 active automation TOMLs. [Done: 2026-04-07]
- [completed] **14.3 PAUSE blocked lanes** — acme-android PAUSED (Play Store blocked), 14 total automations paused then cleaned. Beacon radars later unpaused after domain fix. [Done: 2026-04-07]
- [completed] **14.4 Kill ghost fleet rows** — 22 paused/ghost rows deleted from Codex DB. Dashboard clean: 12 active, 0 paused. [Done: 2026-04-07]
- [completed] **14.5 Clean stale worktrees and browser processes** — 229 worktrees pruned (11GB), 750 browser processes killed (20GB RAM). [Done: 2026-04-07]
- [completed] **14.6 Add cadence-runtime health check to vidux-doctor.sh** — CHECK 12 added. Reads rrule BYMINUTE count + memory file runtimes. Doctor now has 14 checks. [Done: 2026-04-07]
- [completed] **14.7 Fleet restructuring contract tests** — 8 new tests (168 total): cadence-runtime check existence, 14+ doctor checks, REDUCE gate in DOCTRINE.md + best-practices.md, compat.sh functions, prune/witness use compat not raw stat/date. [Done: 2026-04-07]
- [completed] **15.1 Add circuit breaker to vidux-loop.sh** — Scans last N Progress entries for shipping signals (shipped/commit/fixed/merged/etc). If none found, sets `circuit_breaker: open` and blocks dispatch. Configurable via `backpressure.circuit_breaker_threshold` (default 3). 2 contract tests added. [Done: 2026-04-07] [Evidence: agentic-patterns-research.md#5, fleet-loop-analysis.md#4]


## Archived 2026-04-08
## Archived 2026-04-08
- [completed] **15.2 Add idle-churn detection to vidux-witness.sh** — Per-automation `idle_churn_pct` and `total_entries` in JSON output. Counts memory.md entries with/without shipping signals (shipped/commit/fixed/etc). Also fixed compat.sh nounset guard. [Done: 2026-04-07] [Evidence: fleet-loop-analysis.md#4]
- [completed] **15.2 Add idle-churn detection to vidux-witness.sh** — Per-automation `idle_churn_pct` and `total_entries` in JSON output. Counts memory.md entries with/without shipping signals (shipped/commit/fixed/etc). Also fixed compat.sh nounset guard. [Done: 2026-04-07] [Evidence: fleet-loop-analysis.md#4]

## Archived 2026-04-08
- [completed] **15.3 Radar template pattern** — Created guides/vidux/radar-template.md: {{placeholder}}-based harness template for read-only radars. Includes updated REDUCE gate (circuit_breaker check), sizing guidance (800-1200 chars target), examples table. Contract test added. [Done: 2026-04-07] [Evidence: fleet-loop-analysis.md#5, prompt analysis]
- [completed] **15.4 Mid-zone enforcement in harness prompts** — Added "Dispatch-side mid-zone kill" to DOCTRINE.md Principle 10 and best-practices.md REDUCE gate section. Rule: 3+ minutes with no file write in dispatch = checkpoint and exit. Cited fleet data (32% mid-zone, target <15%). 2 contract tests. [Done: 2026-04-07] [Evidence: fleet-loop-analysis.md#3]
- [completed] **15.5 Contract tests for circuit breaker** — 2 tests: circuit_breaker field exists and is open/closed, idle progress triggers open + blocks dispatch. Merged into 15.1 delivery. [Done: 2026-04-07] [Evidence: coverage-gaps pattern]
- [completed] **16.1 Archive phases 8-12 to ARCHIVE.md** — 38 completed tasks moved. PLAN.md dropped from 230 to ~130 lines. Phases 1-7 were already headers-only. Phases 13-15 kept as recent context. [Done: 2026-04-07] [Evidence: loop context_warning]
- [completed] **16.2 Prune stale project plans** — Scanned 9 project plans. Archived 2 (nextjs-cve-sweep 4/4, vidux-stress-test 6/6). 7 still active with pending tasks. vidux-v230 has 1 in_progress investigation (D3 backpressure). [Done: 2026-04-07] [Evidence: project scan]
- [completed] **16.3 Update README.md with Phase 13-15 features** — Added "Fleet Intelligence (v2.3+)" section: circuit breaker, idle-churn detection, REDUCE gate, mid-zone kill, radar template, cross-platform compat. Updated "What Ships Here" with scripts/lib/, tests/, radar template. [Done: 2026-04-07] [Evidence: self-extending plan, Doctrine 11]

## Archived 2026-04-08
- [completed] **15.3 Radar template pattern** — Created guides/vidux/radar-template.md: {{placeholder}}-based harness template for read-only radars. Includes updated REDUCE gate (circuit_breaker check), sizing guidance (800-1200 chars target), examples table. Contract test added. [Done: 2026-04-07] [Evidence: fleet-loop-analysis.md#5, prompt analysis]
- [completed] **15.4 Mid-zone enforcement in harness prompts** — Added "Dispatch-side mid-zone kill" to DOCTRINE.md Principle 10 and best-practices.md REDUCE gate section. Rule: 3+ minutes with no file write in dispatch = checkpoint and exit. Cited fleet data (32% mid-zone, target <15%). 2 contract tests. [Done: 2026-04-07] [Evidence: fleet-loop-analysis.md#3]
- [completed] **15.5 Contract tests for circuit breaker** — 2 tests: circuit_breaker field exists and is open/closed, idle progress triggers open + blocks dispatch. Merged into 15.1 delivery. [Done: 2026-04-07] [Evidence: coverage-gaps pattern]
- [completed] **16.1 Archive phases 8-12 to ARCHIVE.md** — 38 completed tasks moved. PLAN.md dropped from 230 to ~130 lines. Phases 1-7 were already headers-only. Phases 13-15 kept as recent context. [Done: 2026-04-07] [Evidence: loop context_warning]
- [completed] **16.2 Prune stale project plans** — Scanned 9 project plans. Archived 2 (nextjs-cve-sweep 4/4, vidux-stress-test 6/6). 7 still active with pending tasks. vidux-v230 has 1 in_progress investigation (D3 backpressure). [Done: 2026-04-07] [Evidence: project scan]
- [completed] **16.3 Update README.md with Phase 13-15 features** — Added "Fleet Intelligence (v2.3+)" section: circuit breaker, idle-churn detection, REDUCE gate, mid-zone kill, radar template, cross-platform compat. Updated "What Ships Here" with scripts/lib/, tests/, radar template. [Done: 2026-04-07] [Evidence: self-extending plan, Doctrine 11]

## Archived 2026-04-08
- [completed] **17.1 Fix SIGPIPE in vidux-loop.sh** — Wrapped 3 `grep|head` pipe patterns with `|| true` to prevent exit 141 under `set -euo pipefail`. Moved circuit breaker + auto_pause evaluation before early exits. Added `_FLEET_SUFFIX` to all 4 early-exit JSON paths for consistent schema. Fixed `self.ROOT` test bug and DOCTRINE.md `stateless` keyword. 30/30 loop tests pass. [Done: 2026-04-07] [Evidence: fleet-audit-11-automations.md#systemic-1]

## Archived 2026-04-08
- [completed] **17.1 Fix SIGPIPE in vidux-loop.sh** — Wrapped 3 `grep|head` pipe patterns with `|| true` to prevent exit 141 under `set -euo pipefail`. Moved circuit breaker + auto_pause evaluation before early exits. Added `_FLEET_SUFFIX` to all 4 early-exit JSON paths for consistent schema. Fixed `self.ROOT` test bug and DOCTRINE.md `stateless` keyword. 30/30 loop tests pass. [Done: 2026-04-07] [Evidence: fleet-audit-11-automations.md#systemic-1]

## Archived 2026-04-08
- [completed] **17.1 Fix SIGPIPE in vidux-loop.sh** — Wrapped 3 `grep|head` pipe patterns with `|| true` to prevent exit 141 under `set -euo pipefail`. Moved circuit breaker + auto_pause evaluation before early exits. Added `_FLEET_SUFFIX` to all 4 early-exit JSON paths for consistent schema. Fixed `self.ROOT` test bug and DOCTRINE.md `stateless` keyword. 30/30 loop tests pass. [Done: 2026-04-07] [Evidence: fleet-audit-11-automations.md#systemic-1]


## Archived 2026-04-08
## Archived 2026-04-08
- [completed] **17.4 Bake ledger into harness template** — Update `guides/vidux/radar-template.md` and `guides/vidux/best-practices.md` to make ledger reads mandatory in the READ step, not optional. Include sibling memory scan pattern. [Evidence: fleet-audit-11-automations.md#systemic-2]
- [completed] **17.4 Bake ledger into harness template** — Update `guides/vidux/radar-template.md` and `guides/vidux/best-practices.md` to make ledger reads mandatory in the READ step, not optional. Include sibling memory scan pattern. [Evidence: fleet-audit-11-automations.md#systemic-2]
- [completed] **17.5 Blocker dedup gate** — If last 3 memory notes report the same blocker keyword, vidux-loop.sh emits `blocker_dedup: true` and REDUCE gate auto-pauses. Prevents `acme-launch-loop` pattern (5× same ASC key blocker in 6 hours). [Evidence: fleet-audit-11-automations.md#systemic-3]
- [completed] **17.5 Blocker dedup gate** — If last 3 memory notes report the same blocker keyword, vidux-loop.sh emits `blocker_dedup: true` and REDUCE gate auto-pauses. Prevents `acme-launch-loop` pattern (5× same ASC key blocker in 6 hours). [Evidence: fleet-audit-11-automations.md#systemic-3]

## Archived 2026-04-08
- [completed] **17.7 Radar→writer inbox pattern** — Radars append findings to `INBOX.md` next to PLAN.md. Writers consume inbox entries and promote to `[pending]` tasks during READ step. Breaks the circular deadlock where radars observe but can't create work. [Evidence: fleet-audit-11-automations.md#systemic-2]
