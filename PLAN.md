# Vidux v3 — Simplification Revamp

## Purpose
Strip vidux down to its essence: plan first, code second. Remove Redux jargon, circuit breakers, auto-pause, and all fleet ops machinery that belongs in /codex. Rewrite all 12 Codex automations to use the simplified v3 gate pattern. Each automation retains its job — just with a cleaner, shorter prompt.

## Evidence
- [Source: staff review agents, 2026-04-09] 15 doctrines → 6. 1100 lines → 200. Redux analogy costs more than it teaches.
- [Source: plan clobber postmortem, 2026-04-09] Gate was too blunt (dirty=stop). Needs green/yellow/red triage.
- [Source: release-train parking, 2026-04-09] Automation saw file casing collision and said "hold" when it could have fixed it.
- [Source: overnight fleet data, 2026-04-08-09] vidux-loop.sh circuit breakers caused auto-pause on automations doing real branch-push work.

## Constraints
- ALWAYS: Contract tests (test_vidux_contracts.py) must pass before any SKILL.md or PLAN.md change ships
- ALWAYS: Every automation prompt must include TRUNK HEALTH gate (Doctrine 15)
- NEVER: Use re.sub or sed to patch TOML prompt fields — always regenerate from DB (Bug #22)
- NEVER: Accept --theirs or --ours blindly in merge conflicts — preserve both sides (Doctrine 16)

## Tasks

### Phase 1: SKILL.md v3 — core rewrite

- [completed] 1.1 Draft SKILL-v3.md (220 lines, 6 principles) [Done: 2026-04-09]
- [completed] 1.2 Extract fleet ops to guides/fleet-ops.md [Done: 2026-04-09]
- [completed] 1.3 Extract investigation template to guides/investigation.md [Done: 2026-04-09]
- [completed] 1.4 Extract harness authoring to guides/harness.md [Done: 2026-04-09]
- [completed] 1.5 Extract evidence format to guides/evidence-format.md [Done: 2026-04-09]
- [completed] 1.6 Replace SKILL.md with SKILL-v3.md — 1000→208 lines, 14 tests updated, 144/144 pass [Done: 2026-04-09]
- [completed] 1.7 Verified /claude skill has no v2 references (vidux-loop.sh, Redux jargon, etc.) — already clean [Done: 2026-04-09]

### Phase 2: Resplit automation revamp [spawns: investigations/resplit-revamp.md]

- [completed] 2.1 Rewrite 6 resplit prompts — drop vidux-loop.sh, use v3 gate [Done: 2026-04-09]
- [completed] 2.2 Apply prompts to Codex DB + restart [Done: 2026-04-09]
- [completed] 2.3 Verify: resplit-web-ux SHIPPED (CTA fix, 20min run). Others idle/reset. [Done: 2026-04-09]
- [completed] 2.4 GC stale worktrees + branches — 394 worktree dirs removed (33GB), 38 merged branches deleted. 130 resplit-ios branches with unmerged work left for trunk guardian. Disk: 2.8GB→147GB free. [Done: 2026-04-09]

### Phase 3: StrongYes automation revamp [spawns: investigations/strongyes-revamp.md]

- [completed] 3.1 Rewrite 4 strongyes prompts — drop vidux-loop.sh, use v3 gate [Done: 2026-04-09]
- [completed] 3.2 Apply prompts to Codex DB + restart [Done: 2026-04-09]
- [completed] 3.3 Verify: T92 shipped via Claude cron. Vercel build passes. [Done: 2026-04-09]
- [completed] 3.4 Revert hallucinated copy from remote trigger (5ef4498c). Added COPY SAFETY constraint. [Done: 2026-04-09]

### Phase 4: Fleet infrastructure

- [completed] 4.1 Rewrite codex-watch prompt (simplified fleet scan)
- [completed] 4.2 Rewrite strongyes-content-scanner prompt
- [completed] 4.3 Apply fleet prompts to DB + restart [Done: 2026-04-09]
- [completed] 4.4 Fleet scan: 1 shipping (resplit-web-ux), 1 watching (codex-watch), 12 idle. [Done: 2026-04-09]

### Phase 5: Draft-PR architecture [in_progress]

**Goal:** All automation pushes go through draft PRs, never direct-to-main. Draft PRs are the **durable source-of-truth for in-flight work** — if a local worktree dies, `gh pr list` is the recovery manifest. Each PR carries: automation id, plan task id, last pushed diff, and the resume point. Closes the Phase 2.4 loop (130 stranded resplit-ios branches with no PR metadata). Formalizes the 2026-04-09 remote-trigger direction. Eliminates the COPY SAFETY-class incident (5ef4498c) by forcing human review.

**Scope (Leo 2026-04-11):** This is a huge change up — every automation today works local-worktree → branch-push → merge-back-to-main. Phase 5 rolls out incrementally in waves.

**Side effects are agnostic (Leo 2026-04-11):** This plan covers ONLY the cloud-agnostic draft-PR mechanics. Paid-service integrations (Greptile review, Sentry context, Seer fixes, Nia indexing) live in `/vidux-codex` scope as composable skills bolted on after the core works. Core ships independently. Research: `investigations/paid-tooling-pr-integration.md`.

**Rollout (wave-based, reversible at every step):**
1. **Wave 0 — Plan + audit.** Lock the plan, audit current push behavior, Leo answers open Qs. No production changes.
2. **Wave 1 — Reference implementation.** Convert ONE low-stakes automation to draft-PR-first. Prove it works for one full production cycle. Document lessons in `guides/draft-pr-flow.md`.
3. **Wave 2 — Batch.** Apply the reference to 3-4 more lanes. Mix shipping + idle.
4. **Wave 3 — Full fleet.** All push-capable automations on draft-PR flow.
5. **Wave 4 — Lock the gate.** Branch protection rejects direct-main pushes from automation actors. Never before Wave 3 completes.

Every wave boundary is reversible. Leo gates each transition.

#### Wave 0 — Plan + audit [completed]
- [completed] 5.0.1 Wave-mapped plan with provisional Q answers and Core/Delegation split. [Done: 2026-04-11]
- [completed] 5.0.2 Audit current push behavior across fleet. Real count: **37 total (35 Claude lanes + 2 Codex observers), ~20 push-capable, 0 currently create PRs.** The "14 automations" from Phases 2-4 is outdated — the fleet migrated to Claude and expanded. Output: `investigations/draft-pr-flow.md`. [Done: 2026-04-11]
- [completed] 5.0.3 Leo confirmed all provisionals (Q2-Q7): lane-owned PRs, human-click promotion, never auto-merge, vidux fleet only, Leo's personal pushes unchanged, stranded branches left dead. [Done: 2026-04-11]
- [completed] 5.0.4 Wave 1 pilot: **`vidux-core-test`**. Reasoning: fleet-internal (no customer surface), observer already exists (`vidux-core-test-observer` in Codex DB), lowest blast radius, exercises the vidux repo where the draft-PR doctrine lives. [Done: 2026-04-11]

#### Wave 1 — Reference implementation: `vidux-core-test` [pending]
- [pending] 5.1.1 Modify `~/.claude/automations/vidux-core-test/prompt.md`: swap push step to `git push origin <branch>` then `gh pr create --draft --title "[vidux-core-test] <task>" --body "Automation: vidux-core-test\nPlan task: <id>\nLog: <snippet>\nResume: <point>"`. [Depends: 5.0.4 ✓]
- [pending] 5.1.2 Run one full production cycle. Observer-pair audit. Record friction. [Depends: 5.1.1]
- [pending] 5.1.3 Distill `guides/draft-pr-flow.md` — cloud-agnostic core doctrine. [Depends: 5.1.2]

#### Wave 2 — Batch rollout (3-4 lanes)
- [pending] 5.2.1 Pick 3-4 additional lanes (mix shipping + idle). [Depends: 5.1.3]
- [pending] 5.2.2 Apply `guides/draft-pr-flow.md` pattern. [Depends: 5.2.1]
- [pending] 5.2.3 Observer-pair audit. One cycle per lane. No regressions = exit. [Depends: 5.2.2]

#### Wave 3 — Full fleet
- [pending] 5.3.1 Remaining ~10 automations. [Depends: Wave 2 complete]
- [pending] 5.3.2 Validate `gh pr list` shows in-flight PR per active lane. [Depends: 5.3.1]

#### Wave 4 — Lock the gate
- [pending] 5.4.1 Branch protection: reject direct-main pushes from automation actors, preserve human pushes. [Depends: Wave 3 complete]
- [pending] 5.4.2 Smoke test both paths. [Depends: 5.4.1]

## Decisions
(Decision Log — intentional choices that future agents must not undo)
- [DIRECTION] [2026-04-09] vidux-loop.sh is NOT deleted — it still works and vidux-loop.sh stays as optional tooling. But automation prompts no longer require it. The gate is now inline in the prompt.
- [DIRECTION] [2026-04-09] 15 doctrines → 6 principles. The 9 removed are fleet ops (moved to guides/fleet-ops.md and /codex skill).
- [DIRECTION] [2026-04-09] No Redux jargon. No "store", "dispatch", "reduce", "unidirectional flow." Plain English only.
- [DIRECTION] [2026-04-09] COPY SAFETY: Automations must never invent marketing copy. Use only text patterns that exist in the codebase. Product is "StrongYes Pro" with "unlimited AI coaching." No sprints, no founder notes, no day-one plans. Evidence: remote trigger hallucinated copy in commit 5ef4498c.
- [DIRECTION] [2026-04-09] Remote triggers (claude.ai/code/scheduled) are dangerous — they push directly to main with zero review. Prefer Codex worktree model (pushes to branch first). Remote trigger for strongyes disabled.
- [DIRECTION] [2026-04-11] All automation pushes go through draft PRs — NEVER direct-to-main. Draft PRs are the durable, worktree-loss-proof manifest of in-flight work (recoverable via `gh pr list`). Phase 5 implements the cloud-agnostic core. Builds on the 2026-04-09 remote-trigger direction. Closes the Phase 2.4 loop (130 stranded resplit-ios branches with no PR metadata).
- [DIRECTION] [2026-04-11] vidux core is open-source and cloud-agnostic. Phase 5 contains ONLY draft-PR mechanics — no Greptile, no Sentry, no Nia, no Seer. Paid-service integrations live in `/vidux-codex` scope as composable skills, not in this plan. "Keep side effects like greptile and followups agnostic, that is more a /vidux-codex kinda thing." — Leo.

## Open Questions
- Q1: Should contract tests track guide files (guides/*.md) or only SKILL.md? -> Action: decide after v3 guides land
- Q2: Draft-PR ownership — lane-owned (`gh pr create --draft` per automation). **Confirmed 2026-04-11.**
- Q3: Draft → Ready promotion — always human click. **Confirmed 2026-04-11.**
- Q4: Auto-merge — NEVER from automation. **Confirmed 2026-04-11.**
- Q5: Scope — vidux fleet only; other repos adopt via their own plans. **Confirmed 2026-04-11.**
- Q6: Leo's personal pushes stay as-is (Phase 5 is automation-only). **Confirmed 2026-04-11.**
- Q7: 130 stranded resplit-ios branches left dead. **Confirmed 2026-04-11.**

## Surprises
- [2026-04-09] v3 rewrite removed 6 PLAN.md sections the contracts enforce. Contract tests caught it immediately.
- [2026-04-09] Remote Claude trigger hallucinated marketing copy ("14-day sprint", "founder notes", "First Bite Labs") while fixing T91/T92. The automation read the plan correctly but invented product concepts. Root cause: no copy safety constraint in prompt. Fix: added COPY SAFETY to writer prompts + reverted bad commit.
- [2026-04-09] Claude Desktop v1.1062.0 migrated from local-agent-mode-sessions/ to claude-code-sessions/. Local scheduled tasks JSON not carried over. Local task creation is UI-only — no programmatic API exists (anthropics/claude-code#41364).

## Progress
- [2026-04-09] Plan created. SKILL-v3.md drafted (220 lines). 4 guides extracted (810 lines). /claude skill created. Remote trigger created then disabled (pushed hallucinated copy to main).
- [2026-04-09] All 12 Codex automations on v3 prompts. 0 vidux-loop.sh refs. resplit-web-ux SHIPPED (CTA fix). codex-watch ran fleet scan. StrongYes T92 shipped (/prep 44→101 companies). Bad copy reverted + COPY SAFETY added. 4 repos synced (0/0).
- [2026-04-09] SKILL.md replaced with v3 (1000→208 lines). 14 contract tests updated. 394 worktree dirs GC'd (33GB freed, disk 2.8→147GB). 38 merged branches deleted. All 4 phases complete — v3 revamp shipped.
- [2026-04-11] Wave 0 tasks 5.0.1 (plan) and 5.0.2 (audit) completed. Audit discovered: 37 total lanes (35 Claude + 2 Codex observers), NOT the 14 stated in Phases 2-4. ~20 are push-capable, 0 create PRs today. Full audit at investigations/draft-pr-flow.md. Codex-to-Claude migration is effectively complete (only 2 Codex observers remain). CronCreate lane `vidux-draft-pr` created (every 15 min, session-only — CronCreate durable mode did not persist to disk). Claude automation prompt written at ~/.claude/automations/vidux-draft-pr/prompt.md. Wave 0 now blocked on: Leo Q2-Q7 answers (5.0.3) and pilot lane decision (5.0.4). Delegation Track + Track B (paid-service skills, sentry cleanup) moved out of this plan per Leo direction — lives in /vidux-codex scope. Good night cycle — cron takes over.
- [2026-04-11] Phase 5 restructured from 3-track (Core + Delegation + Track B) to clean core-only after Leo direction: "vidux is open source — keep side effects agnostic, paid tooling lives in /vidux-codex." Removed Delegation Track (5D.1-5D.5), Track B (5B.1-5B.2), and all Greptile/Sentry/Seer/Nia references from Phase 5 tasks, Decision Log, and Open Questions. Research results preserved at investigations/paid-tooling-pr-integration.md for /vidux-codex to consume. Key research findings: Nia has NO PR surface; Greptile supports drafts via triggerOnDrafts; Seer Code Review hard-skips drafts. Phase 5 now contains 15 tasks across 5 waves (Wave 0 plan+audit → Wave 1 pilot → Wave 2 batch → Wave 3 fleet → Wave 4 gate). 6 Open Questions with provisional answers (Q2-Q7) await Leo's confirm/overturn. Cron and team agents being set up to grind on Phase 5 continuously.
- [2026-04-11] Leak audit clean. Phase 5 opened as draft-PR flow with wave-based rollout strategy. Research dispatched to background Agent. Leo: "this is a huge change up since we've mainly done things local and merged back to main."
- [2026-04-10 04:58 EDT] Overnight quality cycle 1: Fleet scorecard 6 SHIPPING / 4 IDLE / 0 blocked / 0 crashed / 0 mid-zone. SHIPPING: resplit-bug-fixer (re-verifying AJBM/AI4/AJL5 family on build 1648), resplit-code-quality (UITestLaunchConfigurationTests + dead-code prune), resplit-currency (CLF/CNH/FOK/GGP/IMP/JEP/XDR catalog gap), resplit-ios-ux (ja/es-ES/fr-FR locale screenshots, 5 locales remaining), resplit-web-ux (claim tap-target + desktop grid + heading hierarchy), strongyes-ux-scanner (problems metadata fix). IDLE: resplit-launch-loop (1648 already uploaded + distributed), strongyes-backend, strongyes-blog-writer (pivoted to DSA landers, evidence file pending), strongyes-release-train. ASC tracker: 17 fixed / 79 verified / 3 blocked / 0 new — bug-fixer is *correctly* idle-scanning per nurse log; 3 blocked rows (ABv07GVF OCR polling singleton, AFw7znl8 address geocoding, AKigU4Rh OCR key-value extraction) are architecture/eng-design tasks needing human input, not auto-resolvable. Vidux: pushed `f84b53e fix: align gate test with worker-first model` to origin/main (was 1 ahead); uncommitted v3 cleanup (-1834 lines: SKILL-v3 drafts + guides/vidux/* legacy guides + DOCTRINE/SKILL/commands/vidux.md consolidation) left untouched as in-progress sibling work. Flagged: `test_checkpoint_accepts_untracked_matching_process_fix_artifact` is a pre-existing flake — hangs at 10s subprocess timeout under pytest's capture_output but completes in 1-2s under raw subprocess.run; not caused by v3 cleanup, exists at HEAD.
