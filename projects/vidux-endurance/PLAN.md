# Vidux Endurance Test — Multi-Domain Stress Validation

## Purpose
Validate Vidux v2.2.0 under sustained autonomous operation by running realistic fake projects through the full doctrine set. Each project exercises a different domain and different doctrine combinations. The output is a graded scorecard of what works, what breaks, and what's missing — not the fake projects themselves.

## Evidence
- [Source: stress-test results, 2026-04-04] v2.1.0 validated: nested planning, investigation routing, three-strike, Q-gating all passed. 3 friction points and 2 doctrine gaps logged.
- [Source: v2.2.0 release, 2026-04-04] New capabilities: worktree handoff protocol, stuck-loop mechanical enforcement, Doctrine 9 (subagent coordinator), Codex TOML agents.
- [Source: contract tests, 2026-04-06] 83/83 pass. 14/14 doctor checks passed on the 2026-04-04 baseline.
- [Source: `evidence/2026-04-04-fintech-dashboard-baseline.md`] Nia MCP is unavailable in this runtime, so Project 1 uses repo-local revenue/dashboard evidence as the documented fallback instead of claiming external Nia research.

## Constraints
- ALWAYS: Log a Surprise for any doctrine that felt wrong, slow, or confusing
- ALWAYS: Grade each completed project on all 9 doctrines (pass/friction/fail)
- ALWAYS: Run contract tests after each project completes
- NEVER: Write real application code outside /tmp
- NEVER: Push to origin without explicit human approval
- NEVER: Reuse a completed project — start fresh each time
- ASK FIRST: Before modifying any file outside projects/vidux-endurance/

## Decisions
- [2026-04-04] Decision: Each fake project is a self-contained batch of 3-5 tasks inside this PLAN.md, not separate project directories. Alternatives: separate dirs per fake project. Rationale: keeps evaluation in one file, easier to grade.

## Decision Log
- [DIRECTION] [2026-04-04] This tests Vidux itself. Fake project quality doesn't matter — doctrine exercise coverage does.
- [DIRECTION] [2026-04-04] When Nia MCP cannot initialize, use only repo-local evidence inside `projects/vidux-endurance/` and cited repo files. Do not claim Nia-backed findings unless the server actually responds.
- [DIRECTION] [2026-04-06] When a fake project maintains its own `PLAN.md` (for example `projects/resplit-android/PLAN.md`), that child plan is the boundary source for task state. Repair this parent queue from the child store before opening a new lane.

## Tasks

### Project 1: Fake Fintech Dashboard (exercises: Doctrines 1-4, 7, 9)
- [completed] Task 1.1: Research fintech dashboard patterns. Produce evidence snapshot with an explicit Nia fallback when the MCP server is unavailable. [Done: 2026-04-04] [Evidence: `evidence/2026-04-04-fintech-dashboard-baseline.md#findings`] [Depends: none]
- [completed] Task 1.2: Create compound task with investigation — "transaction history renders wrong totals" (3 related tickets). Exercise three-strike escalation + Impact Map. [Done: 2026-04-04] [Investigation: `investigations/transaction-history-wrong-totals.md`] [Evidence: Doctrine 7 requires investigation for 2+ tickets on same surface; `evidence/2026-04-04-fintech-dashboard-baseline.md#findings`] [Depends: 1.1]
- [completed] Task 1.3: Fan out 2 subagents (Doctrine 9) — one researches state management patterns, one researches API pagination. Synthesize into evidence. Grade: did fan-out save tokens vs inline? [Done: 2026-04-04] [Evidence: `evidence/2026-04-04-fintech-subagent-synthesis.md#findings`] [Depends: 1.1] [P]
- [completed] Task 1.4: Grade Project 1 on all 9 doctrines. Log score in Progress. [Done: 2026-04-04] [Evidence: `evidence/2026-04-04-project1-scorecard.md#findings`; `python3 -m unittest discover -s /Users/leokwan/Development/ai/skills/vidux/tests -p 'test_*.py' -q`, executed 2026-04-04] [Depends: 1.2, 1.3]

### Project 2: Fake Health Tracker iOS App (exercises: Doctrines 5, 6, 8, worktree handoff)
- [completed] Task 2.1: Create project plan with simulated "session death" — checkpoint mid-task, then resume as if the context was lost. Does Doctrine 5 (design for death) work? [Done: 2026-04-04] [Evidence: `evidence/2026-04-04-health-tracker-session-death-drill.md#findings`; `evidence/2026-04-04-health-tracker-resume-proof.md#findings`] [Depends: 1.4]
- [completed] Task 2.2: Simulate a build failure. Produce both code fix and process fix (Doctrine 6). Log whether the process fix would actually prevent recurrence. [Done: 2026-04-04] [Evidence: `evidence/2026-04-04-health-tracker-build-failure-drill.md#findings`] [Depends: 2.1]
- [completed] Task 2.3: Write a cron harness prompt for this fake project. Self-evaluate against Doctrine 8 — does it contain any state snapshots? Any task numbers? [Done: 2026-04-04] [Evidence: `evidence/2026-04-04-health-tracker-harness-review.md#findings`] [Depends: 2.1]
- [completed] Task 2.4: Grade Project 2 on all 9 doctrines. [Done: 2026-04-04] [Evidence: `evidence/2026-04-04-project2-scorecard.md#findings`; `python3 -m unittest discover -s /Users/leokwan/Development/ai/skills/vidux/tests -p 'test_*.py' -q`, executed 2026-04-04] [Depends: 2.2, 2.3]

### Project 3: Fake CLI DevTool (exercises: stuck-loop, Decision Log, Q-gating)
- [completed] Task 3.1: Create a task that will deliberately trigger stuck-loop detection — mark it [in_progress] and add 3 Progress entries without completion. Verify auto_blocked fires in vidux-loop.sh output. [Done: 2026-04-05] [Evidence: `evidence/2026-04-05-stuck-loop-mechanical-test.md#findings`; all 4 verification checks green] [Depends: 2.4]
- [completed] Task 3.2: Add a Decision Log entry, then attempt an action that contradicts it. Log whether the LLM respected or ignored the entry. [Done: 2026-04-05] [Evidence: `evidence/2026-04-05-decision-log-contradiction-test.md#findings`; script surfaces entries, LLM judges contradictions (by design)] [Depends: 3.1]
- [completed] Task 3.3: Create a task with Q-refs that gate it, and another without. Verify only the Q-gated task blocks. [Done: 2026-04-05] [Evidence: `evidence/2026-04-05-q-gating-mechanical-test.md#findings`; both scenarios pass. New bug: [Depends: none] self-match] [Depends: 3.1] [P]
- [completed] Task 3.4: Grade Project 3 on all 9 doctrines. [Done: 2026-04-05] [Evidence: `evidence/2026-04-05-project3-scorecard.md#findings`; 5 pass, 4 minimal exercise; contract tests 63/63] [Depends: 3.2, 3.3]

### Aggregate Baseline (Projects 1-3)
- [completed] Task 4: Produce baseline evidence snapshot: aggregate scorecard across the first 3 projects, all 9 doctrines. Identify top 3 friction points and top 3 strengths. Recommend v2.3.0 priorities. [Done: 2026-04-05] [Evidence: `evidence/2026-04-05-final-endurance-scorecard.md#findings`; 8/9 doctrines pass aggregate, D3 sole friction. P0 fix: dependency matcher triple-bug]

### Project 4: Resplit Android (exercises: real development under Vidux)
- [completed] Task 4.1: Scaffold Android project, build, install on emulator. [Done: 2026-04-05] [Evidence: `projects/resplit-android/PLAN.md`; BUILD SUCCESSFUL, APK running on Pixel_3a_API_34]
- [completed] Task 4.2: Verify UI tests for core flows and reconcile the parent endurance queue against the child Android store. [Done: 2026-04-06] [Evidence: `projects/resplit-android/PLAN.md`; `/tmp/resplit-android/app/src/androidTest/java/com/resplit/android/ResplitUiTest.kt`; `/tmp/resplit-android/app/build/outputs/androidTest-results/connected/debug/TEST-Pixel_3a_API_34_extension_level_7_arm64-v8a(AVD) - 14-_app-.xml`; `evidence/2026-04-06-project4-scorecard.md#sources`]
- [completed] Task 4.3: Grade Project 4 on all 9 doctrines. [Done: 2026-04-06] [Evidence: `evidence/2026-04-06-project4-scorecard.md#findings`; `python3 -m unittest discover -s /Users/leokwan/Development/vidux/tests -p 'test_*.py' -q`, executed 2026-04-06, 83/83 passing] [Depends: 4.2]

### Project 5: Fake Community Event Ops Console (exercises: D3, D5 explicit worktree handoff, D8 harness purity, D9 coordinator fan-out)
- [completed] Task 5.1: Write a stateless harness prompt plus explicit worktree handoff checklist for a fake community event ops console. Verify the harness contains no task numbers, progress snapshots, branch names, or worktree-local state. [Done: 2026-04-06] [Evidence: `evidence/2026-04-06-project5-harness-handoff.md#findings`] [Depends: 4.3]
- [pending] Task 5.2: Fan out 3 subagents for domain evidence slices (volunteer scheduling, vendor payout reconciliation, rain-plan logistics) and synthesize overlap/friction into one evidence snapshot. [Depends: 5.1] [P]
- [pending] Task 5.3: Run a two-hop handoff drill across fresh worktrees: first cycle plans + checkpoints, second cycle resumes from disk only and records whether the 50/30/20 split stays balanced. [Depends: 5.1, 5.2]
- [pending] Task 5.4: Grade Project 5 on all 9 doctrines and rerun the Vidux contract suite. [Depends: 5.3]

## Open Questions
- [ ] Q1: Can vidux-loop.sh stuck detection work in a simulated context (no actual cron cycles)? → Action: Test by manually calling the script with a PLAN.md that has 3+ Progress entries for the same task.

## Surprises
- [2026-04-04] Nia MCP failed during initialize (`connection closed: initialize response`) for both resource and template probes. Impact: Project 1 could not use live Nia research in this runtime. Plan update: added repo-local evidence fallback and prohibited uncited external claims.
- [2026-04-04] Doctrine 9 fan-out returned overlapping StrongYes citations across both explorer lanes. Impact: parallelism still saved coordinator context, but less than expected because the repo's strongest state-management and pagination analogues live in the same small source set. Plan update: grade this as a pass with overlap friction, not a clean win.
- [2026-04-04] Vidux contract tests passed but emitted a `ResourceWarning` from `skills/vidux/tests/test_vidux_contracts.py:983` for an unclosed `PLAN.md` file handle. Impact: verification is green with noise. Plan update: treat as future test-hygiene debt, not a blocker for endurance scoring.
- [2026-04-04] `vidux-loop.sh` falsely blocked Task 2.1 on completed dependency `1.4` during post-Project-1 readback. Impact: current dependency matching appears to self-match against the active task line when the task text contains `[Depends: 1.4]`. Plan update: record the bug, and use `in_progress` task state as the resume key for the Project 2 death drill.
- [2026-04-04] `vidux-loop.sh` returned `blocked=true` and `action="execute"` simultaneously when Task 2.1 resumed from `in_progress`. Impact: the loop still advances, but machine consumers cannot trust blocker metadata without also checking `action`. Plan update: track this as a separate reporting bug from the original dependency self-match.
- [2026-04-04] `swiftc` defaulted its module cache under `~/.cache/clang/ModuleCache`, which is not writable in this Codex sandbox. Impact: the first Project 2 compile attempt failed for environment reasons before the intended source error surfaced. Plan update: pin fake iOS compile drills to a `/tmp` module cache and treat permission failures as setup noise, not doctrine findings.
- [2026-04-04] Project 2 resumed cleanly from `PLAN.md` plus evidence without any `## Active Worktrees` entry. Impact: Doctrine 5 survives on FSM state plus Progress alone, but the dedicated worktree handoff protocol is not mechanically surfaced yet. Plan update: count worktree handoff as partial coverage until a later slice proves the explicit handoff path.
- [2026-04-04] After Project 2 completed, `vidux-loop.sh` still blocked Task 3.1 on completed dependency `2.4` (`action: "blocked"`, `context: "Waiting on: 2.4"`). Impact: the dependency matcher bug now stalls the next pending lane outright, not just resumed tasks. Plan update: stop at the Project 2 verification boundary and carry this forward as the explicit blocker before Project 3 begins.
- [2026-04-06] Project 4's parent endurance queue still showed `Task 4.2` as active even though the child store at `projects/resplit-android/PLAN.md` had already crossed to an owner-blocked Play submission boundary after the repo split recovery. Impact: a parent plan can drift behind a child fake-project store and send the next run back into solved work. Plan update: treat the child `PLAN.md` as the boundary source whenever a fake project owns its own store, then repair the parent queue before opening a new lane.

## Progress
- [2026-04-04] Cycle 0: Plan created. 13 tasks across 3 fake projects + 1 final evaluation. Next: Task 1.1 (Nia research for fintech dashboard).
- [2026-04-04] Cycle 1: Task 1.1 completed via repo-local fallback after Nia MCP initialize failed. Added an evidence snapshot grounded in StrongYes operator-surface and money-UI conventions. Next: Task 1.2 (compound investigation for wrong transaction totals).
- [2026-04-04] Cycle 2: Task 1.2 completed. The fake transaction-history surface now has a real investigation file with three linked tickets, one shared root cause, a full Impact Map, and a selector-driven Fix Spec. Next: Task 1.3 (Doctrine 9 subagent fan-out).
- [2026-04-04] Cycle 3: Task 1.3 completed. Two explorers ran in parallel, converged on a shared-selector and idempotent-pagination answer, and the coordinator only consumed synthesized citations. outcome=useful blocker_age=0 retry=0 evidence=+1 proof=+2agent-lanes control_plane=n/a. Next: Task 1.4. Blocker: none.
- [2026-04-04] Cycle 4: Project 1 graded. Scorecard = D1 pass, D2 pass, D3 friction, D4 pass, D5 friction, D6 friction, D7 pass, D8 friction, D9 pass; contract suite returned 63/63 passing. outcome=useful blocker_age=0 retry=0 evidence=+1 proof=+63tests control_plane=n/a. Next: Task 2.1 (design-for-death health-tracker simulation). Blocker: none.
- [2026-04-04] Cycle 5: Task 2.1 started intentionally as a resumable mid-task checkpoint. Wrote the health-tracker session-death drill to disk, confirmed that `vidux-loop.sh` currently false-blocks completed numeric dependencies, and left the lane `in_progress` so the next run can resume from files only. outcome=useful blocker_age=0 retry=0 evidence=+1 proof=+1checkpoint control_plane=n/a. Next: Resume Task 2.1 from `PLAN.md` + `evidence/2026-04-04-health-tracker-session-death-drill.md` only. Blocker: none.
- [2026-04-04] Cycle 6: Project 2 completed. Resumed Task 2.1 from disk-only state, confirmed the `vidux-loop.sh` dependency self-match bug (`blocked: true` plus `action: "execute"`), ran a real `/tmp` Swift compile/fix/re-verify drill for Doctrine 6, wrote an evergreen Project 2 harness prompt, and re-ran the Vidux contract suite (63/63 passing, same `ResourceWarning`). Scorecard = D1 pass, D2 pass, D3 friction, D4 pass, D5 pass, D6 pass, D7 friction, D8 pass, D9 friction. outcome=useful blocker_age=1 retry=0 evidence=+4 proof=+1resume,+1compile-fail,+1compile-pass,+63tests control_plane=n/a. Next: Task 3.1 once dependency matching is fixed or intentionally overridden. Blocker: `vidux-loop.sh` falsely reports completed dependency `2.4` as still live.
- [2026-04-05] Cycle 7: Project 3 completed + graded. Fanned out 3 parallel agents for stuck-loop (3.1), Decision Log (3.2), and Q-gating (3.3) mechanical tests. All passed. Found new bug: `[Depends: none]` self-matches (third variant of dependency matcher bug). Final aggregate scorecard: 8/9 doctrines pass, D3 sole friction. P0 v2.3.0 priority: fix dependency matcher triple-bug. outcome=useful blocker_age=0 retry=0 evidence=+3 proof=+3mechanical-tests,+63contract-tests.
- [2026-04-05] Cycle 8: Project 4 (Resplit Android) launched. Built a real Android app exercising Vidux under actual development. 10/14 tasks completed in one burst: scaffolded Compose+Room project, wrote 6 entities + 5 DAOs + 2 use cases + 8 unit tests + 11 UI screens. BUILD SUCCESSFUL, unit tests pass, APK running on Pixel_3a_API_34 emulator. outcome=useful blocker_age=0 retry=1(HorizontalDivider) evidence=+plan,+code,+screenshot. Next: UI tests (Task 12), then Project 4 grading.
- [2026-04-06] Cycle 9: Project 4 closed at a real owner-blocked boundary by trusting `projects/resplit-android/PLAN.md` over the stale parent queue. Fresh proof: `ResplitUiTest` and companion instrumentation artifacts still show 8/8 connected tests passing at `2026-04-06T18:44:50`, the serial Android gate returned `BUILD SUCCESSFUL in 8s`, and the Vidux contract suite returned 83/83 passing. Scorecard = D1 pass, D2 pass, D3 friction, D4 pass, D5 pass, D6 pass, D7 minimal exercise, D8 minimal exercise, D9 minimal exercise. outcome=useful blocker_age=0 retry=0 evidence=+1 proof=+8android-tests,+1serial-gate,+83contract-tests control_plane=n/a. Next: Task 5.1 (stateless harness + worktree handoff for the Fake Community Event Ops Console). Blocker: none.
- [2026-04-06] Cycle 10: Task 5.1 completed. Project 5 now has an evergreen harness prompt and a concrete register-read-remove-stale worktree checklist captured in `evidence/2026-04-06-project5-harness-handoff.md`. Doctrine 8 review is clean: no task numbers, progress snapshots, branch names, or worktree-local state leaked into the harness. outcome=useful blocker_age=0 retry=0 evidence=+1 proof=+1harness,+1handoff-checklist control_plane=n/a. Next: Task 5.2 (three-lane domain evidence fan-out). Blocker: none.
