# Vidux v2.3.0 — Mega Plan

## Purpose
Fix what broke in the v2.2.0 endurance test. Two independent machines ran 10+ Vidux plans overnight and converged on the same failures: the dependency matcher is broken, process fixes decay into prose, contradiction detection is LLM-only, and control-plane hygiene is not self-healing. This plan synthesizes both machines' findings into one actionable improvement backlog for Vidux v2.3.0.

## Evidence
- [Source: this-computer endurance scorecard, 2026-04-05] `skills/vidux/projects/vidux-endurance/evidence/2026-04-05-final-endurance-scorecard.md` — 8/9 doctrines pass, D3 sole friction, dependency matcher triple-bug P0.
- [Source: other-computer batch 1 scorecard, 2026-04-05] `/Users/leokwan/Desktop/vidux-endurance/evidence/2026-04-05-batch-1-scorecard-and-vnext.md` — D1-D4 stable, D6 weakest, control-plane hygiene dragging D5/D8/D9.
- [Source: this-computer contradiction test, 2026-04-05] `skills/vidux/projects/vidux-endurance/evidence/2026-04-05-decision-log-contradiction-test.md` — script surfaces Decision Log entries, LLM judges contradictions, `[Depends: none]` false-positive bug.
- [Source: other-computer decision log drill, 2026-04-05] `/Users/leokwan/Desktop/vidux-endurance/evidence/2026-04-05-decision-log-and-q-gating-drill.md` — agent respected Decision Log, but loop provides warning-only support.
- [Source: this-computer stuck-loop test, 2026-04-05] `skills/vidux/projects/vidux-endurance/evidence/2026-04-05-stuck-loop-mechanical-test.md` — auto_blocked fires correctly, 4 verification checks green.
- [Source: other-computer stuck-loop precheck, 2026-04-05] `/Users/leokwan/Desktop/vidux-endurance/evidence/2026-04-05-live-radar-and-stuck-loop-precheck.md` — enforcement is text-fragile, first-40-char match, paraphrased Progress lines miss.
- [Source: this-computer dependency matcher analysis, 2026-04-05] `vidux-loop.sh` line 124: `grep -qi "$DEP_TARGET"` against full task text causes 3 failure modes.
- [Source: other-computer control-plane radar, 2026-04-05] `/Users/leokwan/Desktop/vidux-endurance/evidence/2026-04-05-live-radar-regression-trend.md` — 9+ stale worktrees, two active automations on one authority plan, orphan automation dirs, stale sibling plans.
- [Source: contract tests, 2026-04-05] 63/63 pass on both machines. ResourceWarning on line 983 in both runs.
- [Source: fresh Phase 3 refresh + doctor repo fix, 2026-04-06] `evidence/2026-04-06-phase3-refresh-and-doctor-repo-fix.md` — new `vidux-doctor.sh --repo` scoping bug found, fixed, and re-verified with fresh `/tmp` + live-plan runs.
- [Source: refreshed final scorecard, 2026-04-06] `evidence/2026-04-06-v231-final-scorecard.md` — v2.3.1 beats the 2026-04-05 baseline on contract depth and control-plane enforcement; D3 still friction.

## Constraints
- ALWAYS: Read both machines' endurance evidence before modifying vidux-loop.sh
- ALWAYS: Run contract tests (63/63 must still pass) after each code change
- ALWAYS: Cite evidence for every design decision — this is Vidux improving Vidux
- NEVER: Break backward compatibility with existing PLAN.md formats
- NEVER: Skip the planning phase — minimum 5 planning iterations before code
- NEVER: Push to origin without explicit human approval
- ASK FIRST: Before modifying SKILL.md doctrine language
- ASK FIRST: Before changing the automation TOML structure

## Decisions
- [2026-04-05] Decision: Synthesize both machines' findings into one plan instead of separate tracks. Alternatives: machine-specific fix branches. Rationale: findings converge — maintaining two tracks doubles overhead for the same bugs.
- [2026-04-05] Decision: Spend 5+ planning iterations before any code changes. Alternatives: fix P0 bugs immediately. Rationale: user explicitly requested deep planning first; the bugs are well-characterized but the fix designs need evidence-backed validation.
- [2026-04-05] Decision: Fix dependency matcher by extracting task IDs into a separate matching step, not by patching the grep. Alternatives: add special-case escaping. Rationale: both machines independently identified the grep-against-full-text pattern as the root cause, not any single keyword.

## Decision Log
- [DIRECTION] [2026-04-05] This plan improves Vidux itself. Every change must cite endurance evidence. Do not invent features not supported by the two-machine convergence data.
- [DIRECTION] [2026-04-05] Phase 0 (planning) must complete 5+ iterations before Phase 1 (implementation) begins. Each iteration refines the plan using fresh evidence reads, not stale context.
- [DIRECTION] [2026-04-05] Control-plane hygiene checks are implementation work, not just documentation. They should be runnable shell commands or script additions, not prose checklists.

## Tasks

### Phase 0: Evidence Synthesis & Design (5+ planning iterations, no code)

- [completed] Task 0.1: Read and cross-reference both machines' endurance scorecards. Produce a unified convergence table with: finding, this-computer evidence, other-computer evidence, convergence strength (strong/partial/divergent). [Done: 2026-04-05] [Evidence: `evidence/2026-04-05-two-machine-convergence.md#findings`] [Depends: none]
- [completed] Task 0.2: Read vidux-loop.sh lines 115-180 in detail. [Done: 2026-04-05] [Evidence: `evidence/2026-04-05-vidux-loop-annotated-analysis.md#findings`] Map every code path that touches dependency matching, stuck-loop detection, Q-gating, and Decision Log parsing. Produce an annotated line-by-line analysis with bug locations and fix candidates. [Evidence: vidux-loop.sh source] [Depends: 0.1]
- [completed] Task 0.3: Design the dependency matcher fix. [Done: 2026-04-05] [Evidence: `evidence/2026-04-05-dependency-matcher-fix-design.md#findings`] Must handle: (a) `[Depends: none]` short-circuit, (b) match against task identifiers only (not full task text), (c) handle numeric task IDs like "1.4" without partial matching "1.4" inside "Task 14". Write the fix spec as a diff against vidux-loop.sh:124. [Evidence: both machines' dependency bug analysis] [Depends: 0.2]
- [completed] Task 0.4: Design mechanical contradiction detection for the Decision Log. [Done: 2026-04-05] [Evidence: `evidence/2026-04-05-contradiction-detection-design.md#findings`] Evaluate three approaches: (a) keyword overlap between `[DELETION]` entries and pending task descriptions, (b) semantic similarity scoring (too heavy for bash?), (c) explicit `[Contradicts: DL-N]` tags in tasks. Pick the approach that works in bash and cite why. [Evidence: both machines' contradiction test evidence] [Depends: 0.2]
- [completed] Task 0.5: Design control-plane hygiene checks. [Done: 2026-04-05] [Evidence: `evidence/2026-04-05-control-plane-hygiene-design.md#findings`] Should detect: (a) multiple active automations on one authority plan, (b) missing `## Active Worktrees` sections, (c) stale `[in_progress]` tasks older than N cycles, (d) orphan automation directories (memory.md without automation.toml), (e) detached same-HEAD worktrees. Decide: new script or additions to vidux-loop.sh? [Evidence: other-computer control-plane radar] [Depends: 0.1]
- [completed] Task 0.6: Design D6 enforcement pattern. [Done: 2026-04-05] [Evidence: `evidence/2026-04-05-d6-enforcement-design.md#findings`] How do we mechanically verify that a process fix is "enforceable" vs "prose-only"? Evaluate: (a) require `[ProcessFix: test|hook|linter|script]` tag on tasks, (b) scan for new test/hook/script files in the fix commit, (c) manual annotation only. [Evidence: other-computer D6 analysis, batch scorecard] [Depends: 0.1]
- [completed] Task 0.7: Review all Phase 0 designs. [Done: 2026-04-05] [Evidence: `evidence/2026-04-05-phase0-design-review.md#findings`] Cross-check for conflicts, missing edge cases, and backward compatibility. Produce a "ready for code" verdict with any remaining open questions. [Depends: 0.3, 0.4, 0.5, 0.6]

### Phase 1: Implementation (P0 fixes)

- [completed] Task 1.1: Fix the dependency matcher triple-bug on vidux-loop.sh line 124. Apply the design from Task 0.3. [Done: 2026-04-05] [Evidence: Task 0.3 fix spec, `evidence/2026-04-05-dependency-matcher-fix-design.md`] [Depends: 0.7]
- [completed] Task 1.2: Fix the ResourceWarning on test_vidux_contracts.py line 983. Replace `open(plan).read()` with a context manager. [Done: 2026-04-05] [Evidence: both machines' contract test output] [Depends: 0.7]
- [completed] Task 1.3: Run contract tests. All 63 must pass. ResourceWarning must be gone. [Done: 2026-04-05] [Evidence: 63/63 pass, 0 ResourceWarning] [Depends: 1.1, 1.2]

### Phase 2: Implementation (P1 fixes)

- [completed] Task 2.1: Implement mechanical contradiction detection per Task 0.4 design. [Done: 2026-04-05] [Evidence: Task 0.4 design, `evidence/2026-04-05-contradiction-detection-design.md`] [Depends: 1.3]
- [completed] Task 2.2: Align `hot_tasks` count with post-mutation state. Move computation to after stuck-loop enforcement. [Done: 2026-04-05] [Evidence: this-computer endurance scorecard, hot_tasks finding] [Depends: 1.3]
- [completed] Task 2.3: Unify or document `blocked` vs `auto_blocked` fields. Chose: documentation in vidux-loop.sh (comment block before output section). [Done: 2026-04-05] [Evidence: this-computer endurance scorecard, blocked field finding] [Depends: 1.3]
- [completed] Task 2.4: Implement control-plane hygiene checks per Task 0.5 design. Created vidux-doctor.sh (7 checks, human+JSON output, --fix mode). [Done: 2026-04-05] [Evidence: Task 0.5 design, `evidence/2026-04-05-control-plane-hygiene-design.md`] [Depends: 1.3]
- [completed] Task 2.5: Run contract tests + regression drill against all known failure modes from both endurance tests. [Done: 2026-04-05] [Evidence: 63/63 pass, vidux-doctor.sh 6/7 pass (1 stale project: amp)] [Depends: 2.1, 2.2, 2.3, 2.4]

### Phase 3: New Tests & Verification

- [completed] Task 3.1: Write new contract tests covering every fixed bug — dependency matcher edge cases (`[Depends: none]`, numeric ID partial match, self-match), contradiction detection, stuck-loop with paraphrased Progress text. These are NEW tests, not reruns of the existing 63. [Done: 2026-04-05] [Evidence: 83/83 pass (63 original + 20 new)] [Depends: 2.5]
### QA: Stress Test Projects (fake plans in /tmp)
- [completed] Task 3.2a: Create fake project 1 in /tmp — dependency matcher torture test. Plan with: [Depends: none] tasks, numeric ID partial matches (1.4 vs 14), self-referencing deps, multi-dep comma lists, v1 checkbox format, unstructured tasks. Run vidux-loop.sh against each task permutation. Log pass/fail in evidence/. [Done: 2026-04-06] [Evidence: `evidence/2026-04-06-phase3-refresh-and-doctor-repo-fix.md`] [Depends: 3.1]
- [completed] Task 3.2b: Create fake project 2 in /tmp — contradiction detection torture test. Plan with: [DELETION] + task re-adding deleted feature, [DIRECTION] + task contradicting direction, [RATE-LIMIT] entries (should NOT trigger), explicit [Contradicts: DL-N] tags, no Decision Log (should produce all-false). Run vidux-loop.sh, assert contradiction_warning values. Log in evidence/. [Done: 2026-04-06] [Evidence: `evidence/2026-04-06-phase3-refresh-and-doctor-repo-fix.md`] [Depends: 3.1] [P]
- [completed] Task 3.2c: Create fake project 3 in /tmp — stuck-loop + auto-block torture test. Plan with: [in_progress] task that has 3+ Progress entries mentioning it. Run vidux-loop.sh, verify auto_blocked=true, verify [STUCK] entry appears in Decision Log, verify DL parser reads it back on second run. [Done: 2026-04-06] [Evidence: `evidence/2026-04-06-phase3-refresh-and-doctor-repo-fix.md`] [Depends: 3.1] [P]
- [completed] Task 3.2d: Create fake project 4 in /tmp — mixed format stress. Plan with: v1 checkboxes + v2 FSM states in same file, missing ## Progress section, missing ## Decision Log, empty tasks section, huge plan (100+ lines). Verify vidux-loop.sh handles all gracefully without crash. [Done: 2026-04-06] [Evidence: `evidence/2026-04-06-phase3-refresh-and-doctor-repo-fix.md`] [Depends: 3.1] [P]

### QA: vidux-doctor.sh Validation
- [completed] Task 3.2e: Run vidux-doctor.sh on this machine. Verify all 7 checks produce correct results. Run with --json and validate schema. Run with --fix on a temp repo with planted zombie worktrees and orphan dirs. [Done: 2026-04-06] [Evidence: `evidence/2026-04-06-phase3-refresh-and-doctor-repo-fix.md`] [Depends: 3.1]
- [completed] Task 3.2f: Create a temp plan with merge conflict markers (<<<<<<< / ======= / >>>>>>>). Run vidux-doctor.sh. Verify exit code 1 (BLOCK) and plan_merge_conflicts check fires. [Done: 2026-04-06] [Evidence: `evidence/2026-04-06-phase3-refresh-and-doctor-repo-fix.md`] [Depends: 3.1] [P]

### QA: Prompt Amplification (v2.3.1)
- [completed] Task 3.2g: Verify the amp section was correctly added to SKILL.md. Read the Prompt Amplification section, confirm it has GATHER/AMPLIFY/PRESENT/STEER/FIRE flow, confirm skip-amplification rules (cron, in_progress, "fire"/"go"). [Done: 2026-04-06] [Evidence: `evidence/2026-04-06-phase3-refresh-and-doctor-repo-fix.md`] [Depends: 3.1]

### QA: Live Plan Execution
- [completed] Task 3.3: Run vidux-loop.sh against the REAL vidux-v230/PLAN.md. Verify it correctly identifies the next pending task, respects all completed deps, and produces valid JSON with all new fields (contradiction_warning, contradiction_matches, contradicts_tag). [Done: 2026-04-06] [Evidence: `evidence/2026-04-06-phase3-refresh-and-doctor-repo-fix.md`] [Depends: 3.2a]
- [completed] Task 3.3b: Run vidux-loop.sh against the REAL resplit-android/PLAN.md. Verify it handles the cron-updated plan correctly (the cron has been modifying it). [Done: 2026-04-06] [Evidence: `evidence/2026-04-06-phase3-refresh-and-doctor-repo-fix.md`] [Depends: 3.2a] [P]
- [blocked] Task 3.3c: Run vidux-loop.sh against the REAL perf-investigation/PLAN.md. Verify the new plan format works. [Blocked: 2026-04-06] [Evidence: `evidence/2026-04-06-phase3-refresh-and-doctor-repo-fix.md`] Path no longer exists under `projects/`; needs replacement live plan or archival decision. [Depends: 3.2a] [P]

### QA: Contract Test Full Suite
- [completed] Task 3.4a: Run full 83-test contract suite one more time. All must pass. Zero warnings. [Done: 2026-04-06] [Evidence: `evidence/2026-04-06-phase3-refresh-and-doctor-repo-fix.md` — 84/84 pass, 0 warnings] [Depends: 3.2a, 3.2b, 3.2c, 3.2d]

### QA: Cleanup + Hygiene
- [pending] Task 3.4b: Audit all 5 PAUSED resplit-nurse automations (resplit-super-nurse-hourly, resplit-launch-loop, resplit-vidux, resplit-oversight, resplit-hourly-mayor). Check memory.md for useful history. If nothing worth keeping, flag for deletion. [Evidence: all 5 are PAUSED, reference deprecated resplit-nurse concept] [Depends: none] [P]
- [completed] Task 3.4c: Review the vidux-amp SKILL.md redirect. Confirm it correctly points to vidux SKILL.md. Confirm the legacy description in the skill list updated. [Done: 2026-04-06] [Evidence: `evidence/2026-04-06-phase3-refresh-and-doctor-repo-fix.md`] [Depends: 3.2g]

### QA: SKILL.md Doctrine Review
- [completed] Task 3.5a: Read SKILL.md Anti-loop section. Verify it still says "Contradiction detection is LLM judgment" — this should be updated to reflect the new mechanical keyword overlap detection added in v2.3.0. [Done: 2026-04-06] [Evidence: `evidence/2026-04-06-phase3-refresh-and-doctor-repo-fix.md`] [Depends: 3.4a]
- [completed] Task 3.5b: Read SKILL.md stuck-loop section. Verify it documents auto_blocked field and [STUCK] Decision Log entries. Update if missing. [Done: 2026-04-06] [Evidence: `evidence/2026-04-06-phase3-refresh-and-doctor-repo-fix.md`] [Depends: 3.4a]
- [completed] Task 3.5c: Read SKILL.md Companion Skills table. Add vidux-doctor.sh as a companion tool. [Done: 2026-04-06] [Evidence: `evidence/2026-04-06-phase3-refresh-and-doctor-repo-fix.md`] [Depends: 3.4a]

### Final Scorecard
- [completed] Task 3.6: Final scorecard — before/after comparison across all 9 doctrines. Run vidux-loop.sh against 5+ plans (v230, resplit-android, perf-investigation, 2+ fake /tmp plans). Grade each doctrine. The question: is v2.3.1 measurably better than v2.2.0? Write to evidence/2026-04-05-v231-final-scorecard.md. [Done: 2026-04-06] [Evidence: `evidence/2026-04-06-v231-final-scorecard.md`] Used v230, resplit-android, context-ops, and fresh `/tmp` plans because `perf-investigation/PLAN.md` no longer exists. [Depends: 3.4a, 3.5a, 3.5b, 3.5c]

## Open Questions
- [x] Q1: Should control-plane hygiene checks be a separate script (`vidux-doctor.sh`) or integrated into `vidux-loop.sh`? -> ANSWERED: New `vidux-doctor.sh`. Loop script is single-plan/stateless; hygiene checks are cross-plan/cross-repo. Different concern. Evidence: `evidence/2026-04-05-control-plane-hygiene-design.md`.
- [x] Q2: Is bash sufficient for keyword-overlap contradiction detection, or does this need a Python helper? -> ANSWERED: Bash is sufficient. `comm`/`sort`/`tr`/`case` handle keyword intersection in milliseconds. Semantic similarity is out of scope for v2.3.0. Evidence: `evidence/2026-04-05-contradiction-detection-design.md`.
- [x] Q3: What's the right threshold for "stale `[in_progress]`"? -> ANSWERED: 3 calendar days since last Progress entry. Cross-plan checks can't observe cycle counts, only dates. Evidence: `evidence/2026-04-05-control-plane-hygiene-design.md`.

## Surprises
- [2026-04-05] New bug found by loop-analyzer: DL-STUCK-TAG-BLIND — the Decision Log parser (line 59) only matches `[DELETION]`, `[RATE-LIMIT]`, `[DIRECTION]` but not `[STUCK]` entries that the script itself writes at line 181. The script has a blind spot to its own mutations. Impact: stuck-loop entries are invisible to subsequent Decision Log awareness. Plan update: add `[STUCK]` to the parser regex in the dependency matcher fix.
- [2026-04-06] New bug found by fresh QA: DOCTOR-REPO-SCOPE-BLIND — `vidux-doctor.sh --repo <path>` only re-scoped worktree/automation checks while project-plan checks still scanned the script checkout. Impact: temp-repo merge conflict drills could false-pass. Fix: derive `VIDUX_ROOT`, `PROJECTS_DIR`, `AUTOMATIONS_DIR`, and `CONFIG` from the resolved `REPO`, then add a contract test for `--repo`.

## Progress
- [2026-04-05] Cycle 0: Mega plan created. Synthesized findings from two independent machines running 10+ Vidux plans overnight. 17 tasks across 4 phases. Phase 0 has 7 planning tasks that must complete 5+ iterations before code. Next: Task 0.1 (evidence cross-reference).
- [2026-04-05] Cycle 1: Task 0.1 completed. Two-machine convergence analysis produced: 6 STRONG convergences (D1-D4 stable, dependency matcher bug, Decision Log warning-only, ResourceWarning, contract suite 63/63, evidence discipline), 2 key divergences (D3 scoring, D6 bar height). Adopted other machine's higher D6 bar. Fanned out 3 parallel agents for Tasks 0.2, 0.5, 0.6. Next: collect subagent results, then Tasks 0.3, 0.4.
- [2026-04-05] Cycle 2: Phase 0 COMPLETE (7/7 tasks). All designs reviewed, no conflicts, all backward-compatible, Bash 3.2 safe. All 3 open questions answered. Verdict: READY FOR CODE. Next: Task 1.1 (dependency matcher + DL-STUCK fix).
- [2026-04-05] Cycle 3: Phase 1 COMPLETE (3/3 tasks). Applied DL-STUCK-TAG-BLIND fix (line 59: added |STUCK to regex). Applied DEP-MATCHER-TRIPLE fix (lines 116-127: identifier-only matching, none sentinel, multi-dep, self-match exclusion). Fixed ResourceWarning (context manager). 63/63 contract tests pass, 0 warnings. Next: Phase 2 Task 2.1 (contradiction detection).
- [2026-04-05] Cycle 4: Phase 2 COMPLETE (5/5 tasks). Contradiction detection: _cd_keywords() helper + keyword overlap (threshold=2) + explicit [Contradicts:] tags, 3 new JSON fields. hot_tasks recomputed post-mutation. blocked/auto_blocked documented. vidux-doctor.sh: 7 runtime health checks (worktrees, automations, plans), human+JSON output, --fix mode, 6/7 pass on live state. vidux.config.json updated. 63/63 contract tests pass. Next: Phase 3 (new tests + verification).
- [2026-04-05] Cycle 5: Task 3.1 COMPLETE. 20 new contract tests written: 9 dep-matcher (none sentinel, self-match, numeric partial, dotted ID, multi-dep, unstructured, v1 compat), 1 DL-STUCK-TAG-BLIND, 7 contradiction detection (fields present, keyword overlap fires/no-fire, explicit tag, rate-limit skip, no DL, direction overlap), 3 vidux-doctor.sh (exists, valid JSON, required fields). 83/83 pass. Next: Tasks 3.2-3.5 (fake projects, SKILL.md, final scorecard).
- [2026-04-06] Cycle 6: Refreshed Phase 3 on fresh `/tmp` fixtures instead of reusing yesterday's grades. Found DOCTOR-REPO-SCOPE-BLIND during temp-repo merge-conflict validation, fixed `vidux-doctor.sh --repo` scoping, and added a new contract. Fresh results: 84/84 contract tests pass, `/tmp` refresh bundle 8/8 pass, extra contradiction + mixed-format bundle 8/8 pass, live plans v230/resplit-android/context-ops all return valid JSON. `perf-investigation/PLAN.md` is gone, so Task 3.3c is blocked pending replacement live plan or archival decision. Next: Task 3.4b (audit the 5 paused resplit-nurse automations) or explicitly retire that lane.
