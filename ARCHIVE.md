# Archived Tasks

Tasks completed and archived from PLAN.md to keep context lean. History only — task + outcome. Verbose test-count/`docs:build`/`git diff --check` receipts trimmed.

## Archived 2026-04-01 — Bootstrap (Phases 1-7)
- SKILL.md, PLAN.md (meta: Vidux plans itself), DOCTRINE.md, LOOP.md, INGREDIENTS.md (10 OSS patterns), quickstart/architecture/best-practices guides.
- Core scripts: vidux-loop.sh (stateless cycle, JSON, 7 edge cases), vidux-gather.sh, vidux-checkpoint.sh.
- ENFORCEMENT.md (4 PreToolUse hooks, three-strike gate) + /harness integration; contract tests (Jeffrey's PR #265 pattern).
- Plugin manifest, /vidux + /vidux-plan + /vidux-status commands; ledger lifecycle + project build recipe wired; Captain auto-install via symlinks.
- Cross-tool/cross-machine testing deferred (P2): v1 contract is solo-computer, source-controlled.

## Archived 2026-04-06 — Public export
- Exported portable Vidux core to its own public repo (README, LICENSE, CONTRIBUTING, .github templates); rewired paths `skills/vidux/` → repo-root; restored full build-history PLAN.md; brought over evidence, ARCHIVE.md, SETUP_NEW_MACHINE.md.
- /vidux-loop command (fleet creation, lean prompts, staggered schedules, coordinator pattern, bimodal enforcement).
- Absorbed Ralph into vidux core (Ralph had no hooks/commands; queue contract = PLAN.md task FSM). Removed all Ralph refs.
- Ledger integration layer (ledger-config/emit/query.sh) discovers ~/.agent-ledger/, wired into loop + checkpoint. 83/83 tests.
- Retired `ai/skills/vidux/` — 9 automation.toml files repointed to canonical path.
- vidux-doctor.sh CHECK 11 (bimodal runtime: flags >30% of runs in 3-8min dead zone, uses git commit timestamps); vidux-fleet-quality.sh (per-automation + fleet-wide bimodal classification).

## Archived 2026-04-07 — Phases 8-15
- **Phase 8 Canonical Unification; Phase 9 Automation Quality** — fleet configs, e2e tests (NextJS 17/20, iOS 19/20).
- **Phase 10 Visibility/Intelligence/Health** (10.1-10.7): stage indicators, config extensions, ledger integration, dashboard, prune, manager, 30 contract tests.
- **Phase 11 Dispatch/Reduce + Fleet Hardening** (11.1-11.9): doctrine bake, dispatch.sh, reduce mode, exit-criteria, Codex DB resilience, stale-ref prune, queue-jsonl, lifecycle hooks. 11.5 blocked (Vercel MCP).
- **Phase 12 Continuous Feedback Loop** (12.1-12.6): merge-gate, auto-pause, bimodal enforcement, witness.sh, self-extension metric, 11 contract tests (149 total).
- **13.1 Harden json_escape** — added `\r` escape across 5 scripts. Reverted python3 delegation (~80ms/call → 4 test timeouts). Lesson: never spawn subprocesses in hot-path JSON helpers.
- **13.2 Fix config path injection** — 15 `python3 -c open('$CONFIG')` calls across 6 scripts now pass path via sys.argv[1]; doctor batched 8 calls into 1.
- **13.3 Fix checkpoint sed metacharacter handling** — grep -Fn line addressing instead of sed regex.
- **13.4 Portability layer for stat/date** — scripts/lib/compat.sh (file_mtime_epoch, dir_newest_mtime, parse_date_epoch, parse_iso_epoch); OS detection once at source-time; prune + witness source it, no raw stat -f/date -j remain.
- **13.6-13.10 Contract tests** — witness.sh functional, test-all.sh self-test, compound-task/investigation docs, doctrine content contracts (Principles 5/7/8/9), empty-Tasks edge case.
- **14.1 Fix cadence-runtime mismatch** — all active automations → 1x/hr staggered BYMINUTE; fleet 46→12 runs/hr.
- **14.2 REDUCE gate prompt block** — both variants (with-vidux + standalone) shipped to DOCTRINE.md, best-practices.md, 12 automation TOMLs.
- **14.3-14.5 Fleet cleanup** — acme-android PAUSED (Play Store blocked), 22 ghost rows deleted (dashboard: 12 active/0 paused), 229 worktrees pruned (11GB), 750 browser processes killed (20GB RAM).
- **14.6 vidux-doctor.sh CHECK 12** — cadence-runtime health (rrule BYMINUTE count + memory runtimes); doctor now 14 checks.
- **15.1 Circuit breaker in vidux-loop.sh** — scans last N Progress entries for shipping signals; none → `circuit_breaker: open` blocks dispatch. Configurable `backpressure.circuit_breaker_threshold` (default 3).
- **15.2 Idle-churn detection in vidux-witness.sh** — per-automation `idle_churn_pct` + `total_entries`; counts memory entries with/without shipping signals. Fixed compat.sh nounset guard.
- **15.3 Radar template** — guides/vidux/radar-template.md: {{placeholder}} harness for read-only radars, REDUCE gate w/ circuit_breaker check, 800-1200 char target.
- **15.4 Mid-zone enforcement** — "Dispatch-side mid-zone kill" in DOCTRINE.md Principle 10 + best-practices.md: 3+ min no-file-write in dispatch = checkpoint and exit (fleet data: 32% mid-zone, target <15%).
- **15.5 Circuit-breaker contract tests** — field exists + is open/closed; idle progress triggers open + blocks dispatch.
- **16.1 Archive phases 8-12** — 38 tasks moved; PLAN.md 230→~130 lines.
- **16.2 Prune stale project plans** — 2 archived (nextjs-cve-sweep, vidux-stress-test); 7 still active.
- **16.3 README Phase 13-15 features** — "Fleet Intelligence (v2.3+)" section.
- **17.1 Fix SIGPIPE in vidux-loop.sh** — wrapped 3 `grep|head` with `|| true` (exit 141 under `set -euo pipefail`); moved CB + auto_pause eval before early exits; added `_FLEET_SUFFIX` to all 4 early-exit JSON paths. 30/30 loop tests.
- **17.4 Bake ledger into harness template** — radar-template.md + best-practices.md make ledger reads mandatory in READ step + sibling memory scan.
- **17.5 Blocker dedup gate** — last 3 memory notes same blocker keyword → loop emits `blocker_dedup: true`, REDUCE auto-pauses (prevents acme-launch-loop 5× same-blocker pattern).
- **17.7 Radar→writer inbox** — radars append to INBOX.md; writers promote to `[pending]` during READ. Breaks observe-but-can't-create deadlock.
- **17.8 Sub-plan tree traversal** — `[spawns: investigations/foo.md]` tag support; loop traverses sub-plans when parent in_progress, reports aggregate.
- **17.9 Orchestrator fleet-health mode** — detect fleet-level patterns and act (e.g. 6/11 REDUCE-exit) instead of wordsmithing one radar prompt.

## Archived 2026-04-08 — Phases 18-20
- **18.1 Remove personal data** — untracked 5 files, deleted fleet-rebuild script, genericized 92 private refs → acme/beacon across 10 docs, removed hardcoded paths.
- **18.2 Diagnose 6 active automations** — found 4 wrong gate files, 1 scanner-as-writer, 2 safety deadlocks (CB + auto_pause).
- **18.3 Rewrite all automation prompts (v3)** — all 5 use "Quick check gate" (no REDUCE naming); handle find_work state; acme-currency paused/folded.
- **18.4 Prompt authoring best practices** — best-practices.md §14: structure, before/after (real ASC failure), gate selection, 7 mistakes, skill token format, sizing.
- **18.5 Fresh acme/PLAN.md** — 9 pending tasks from 4 Cursor plans (ASC bugs, release, ops); INBOX.md for scanner→writer.
- **18.6 find_work + rename REDUCE→Quick Check** — exit only on action=complete AND type=done AND queue_starved=false; else proceed.
- **18.7 Verify fleet recovery after Codex restart** — Bugs #14-17: DB-only writes overwritten by Electron cache (full-quit required); TOML files are runtime prompt source (not DB); new rows need TOMLs for UI visibility. 10 automations synced DB+TOML.
- **18.8 Auto-archive in vidux-loop.sh** — auto-runs checkpoint --archive when cold_tasks > archive_threshold (Beacon: 81 archived, 1061→497 lines).
- **19.1 resolve_plan_store helper** — scripts/lib/resolve-plan-store.sh: reads config plan_store.path, expands ~, falls back to $VIDUX_ROOT/projects. No jq.
- **19.3 Stop parsing PLAN.md path from prompt text** — addressed in 20.7 (absolute ~/.vidux/projects/ paths); runtime slug resolution deferred.
- **19.4 Docs/tests** — vidux.md references config-resolved plan_store.path; test_plan_store_resolvable replaces test_projects_directory_exists.
- **20.1 Restructure /codex skill** — generic core (DB, memory, Simple/SCAN Gate, fleet ops, `/codex watch`, 13 known bugs) + optional Vidux Integration section.
- **20.2 Generic gate tiers** — Simple (generic) → SCAN (scanners) → Quick Check (vidux writers).
- **20.3 Rename vidux-watchdog → codex-watch** — renamed in sqlite, moved memory dir.

## Archived 2026-04-12 — SKILL v3 split + lane migration
- **1.1-1.7 SKILL slim** — SKILL-v3.md (208 lines, 6 principles); extracted fleet-ops/investigation/harness/evidence-format guides; SKILL.md 1000→208 lines, 144/144 tests; /claude verified v2-clean.
- **2.1-2.4 Resplit** — 6 prompts dropped vidux-loop.sh → v3 gate; resplit-web-ux SHIPPED (CTA fix); 394 worktrees removed (33GB), 38 merged branches deleted; disk 2.8GB→147GB free.
- **3.1-3.4 StrongYes** — 4 prompts → v3 gate; T92 shipped; reverted hallucinated copy (5ef4498c) + added COPY SAFETY constraint.
- **4.1-4.2 Fleet prompts** — codex-watch + strongyes-content-scanner rewritten.

## Archived 2026-04-15 — Draft-PR groundwork
- **4.3-4.4** — fleet prompts applied; scan: 1 shipping, 1 watching, 12 idle.
- **5.0.1-5.0.3** — wave-mapped plan; real fleet count **37 (35 Claude + 2 Codex), ~20 push-capable, 0 create PRs** ("14 automations" was outdated). Leo confirmed: lane-owned PRs, human-click promotion, never auto-merge, vidux fleet only, Leo's personal pushes unchanged, stranded branches left dead.

## Archived 2026-04-17/26 — Draft-PR pilot
- **5.0.4 Wave 1 pilot = strongyes-coach-p0** — original pick vidux-core-test invalid (non-git, "NEVER git push").
- **5.1.1-5.1.3** — coach-p0 prompt: merge-to-main → push branch + draft PR (5-step flow); draft-PR mechanics validated e2e on vidux repo (leojkwan/vidux#4, `gh` clean); guides/draft-pr-flow.md (cloud-agnostic core doctrine). Surprise: coach-p0 plan closed → can't be production pilot.

## Archived 2026-05-31 — Wave 2 + ready-PR doctrine
- **5.2.1-5.2.3** — 3 active-plan lanes picked; draft-PR pattern applied. strongyes PASS; resplit-ios BLOCKED: `gh pr create` fails "shared commit overlaps with existing PR" when new branches share ancestry.
- **5.2.4 Doctrine correction** — ready-PR-first supersedes draft-first for operational PRs (review automation skips/delays drafts); preserved guides/draft-pr-flow.md path for link stability.

## Archived 2026-06-01 — Worktree finalizer + publish-invariant sweep (5.3.x)
- **5.3.0 Worktree lifecycle finalizer** — scripts/vidux-worktree-gc.py classifies worktrees by PR/merge/dirty state; safe explicit cleanup so PR-first lanes don't recreate the 130+ stranded-worktree failure (157 found 4/26).
- **5.3.0a Worktree GC CI + sidecar hygiene** — wired test_worktree_gc.py into CI; `.external-state.json` sidecars actually gitignored even inside tracked project exceptions.
- **5.3.0b Linear codebase guardrail** — adapters/linear.py requires `project_name` for guarded `project_id`, validates Linear project/team before fetch/create/update, fails closed on mismatch (prevents ingesting product buckets like "UX Overhaul").

Publish-invariant sweep — each closed a surface that could teach a plan-silent publish; all now require: update owning PLAN.md, emit publish ledger row (carry `$LEDGER_EID`), proof, handoff_status, files_claimed, next-agent resume — before push/PR/hook-enable.
- **5.3.0c PR body propagation** — scripts/vidux-pr-body.py requires plan/proof/handoff/ledger/files.
- **5.3.0d Week-long prompt contract** — docs/reference/prompt-template.md: one canonical PLAN.md, L2 sub-plans for investigations only, check claims bus, record files_claimed, refresh stale proof, checkpoint handoff at meter points, invariant/regression/adversarial passes before publish.
- **5.3.0e Branch-push publish recipe** — ready-PR flow updates plan + emits publish ledger row before `git push`; eid carried into PR body + fallback handoff. D-20260531-01 recorded earlier rejected push attempts as non-proof.
- **5.3.0f Hook-install recipe** — hook install/wiring updates target plan + emits publish ledger before copying/enabling.
- **5.3.0g Secondary recipes** — fleet-ops + lane-prompt-patterns carry the same update-plan/emit-ledger/push/PR sequence; incomplete work → handoff_status in_progress|needs_review.
- **5.3.0h Top-level recipes invariant** — guides/recipes.md (skill-refiner + self-improvement) can't teach push/PR/direct-main without plan update + publish ledger. (D-20260601-02)
- **5.3.0i Placeholder draft PR invariant** — placeholder draft PRs are publish actions: require plan update, publish ledger, handoff_status=needs_review, files claimed, proof, resume point before `gh pr create --draft`. (D-20260601-03)
- **5.3.0j CLAUDE.md rules invariant** — copied agent rules can't teach direct-to-main/trunk-merge/done-language without plan update, publish ledger, proof, handoff, files claimed, resume. (D-20260601-04)
