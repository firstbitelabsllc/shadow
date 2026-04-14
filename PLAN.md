# Vidux v3 — Simplification Revamp

## Purpose
Strip vidux down to its essence: plan first, code second. Remove Redux jargon, circuit breakers, auto-pause, and all fleet ops machinery that belongs in /codex. Rewrite all 12 Codex automations to use the simplified v3 gate pattern. Each automation retains its job — just with a cleaner, shorter prompt.

## Evidence
- [Source: staff review agents, 2026-04-09] 15 doctrines → 6. 1100 lines → 200. Redux analogy costs more than it teaches.
- [Source: plan clobber postmortem, 2026-04-09] Gate was too blunt (dirty=stop). Needs green/yellow/red triage.
- [Source: release-train parking, 2026-04-09] Automation saw file casing collision and said "hold" when it could have fixed it.
- [Source: overnight fleet data, 2026-04-08-09] vidux-loop.sh circuit breakers caused auto-pause on automations doing real branch-push work.
- [Source: nia_research, 2026-04-12] Anthropic Claude Code best practices: "Start minimal, add skills after 2 weeks of production use proves the need." OpenAI Codex best practices: "Test skills with evals to find overlap."
- [Source: ai/skills/ inventory, 2026-04-12] 54 skills, 12,830 total lines. 8 skills are bulk-import cruft with zero project references. 5 skill pairs overlap.
- [Source: design skill audit, 2026-04-12] Naming convention shipped: brand-* (identity), craft-* (platform), figma-* (workflow). 4 renames + 1 new (brand-leojkwan). All cross-refs updated (11 lane prompts, 4 skill files). Zero stale references.

## Constraints
- ALWAYS: Contract tests (test_vidux_contracts.py) must pass before any SKILL.md or PLAN.md change ships
- ALWAYS: Every automation prompt must include TRUNK HEALTH gate (Doctrine 15)
- NEVER: Use re.sub or sed to patch TOML prompt fields — always regenerate from DB (Bug #22)
- NEVER: Accept --theirs or --ours blindly in merge conflicts — preserve both sides (Doctrine 16)

## Tasks

### Phase 1: SKILL.md v3 — core rewrite


### Phase 2: Resplit automation revamp [spawns: investigations/resplit-revamp.md]


### Phase 3: StrongYes automation revamp [spawns: investigations/strongyes-revamp.md]


### Phase 4: Fleet infrastructure

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
- [completed] 5.0.4 Wave 1 pilot: **`strongyes-coach-p0`**. Original pick `vidux-core-test` is invalid — it operates on a non-git experiment dir with explicit "NEVER git push" in its Authority block. Corrected to `strongyes-coach-p0`: currently pushes directly to origin/main (the exact behavior to replace), StrongYes is smaller than Resplit (lower blast radius), lane is P0-active so it exercises real production cycles. [Corrected: 2026-04-11, see Surprise]

#### Wave 1 — Reference implementation [completed]
- [completed] 5.1.1 Modified `~/.claude/automations/strongyes-coach-p0/prompt.md`: ACT section changed from "merge to main" to "push branch + draft PR". PUSH POLICY replaced: 5-step flow (push branch → `gh pr create --draft` → never direct-to-main → sync main each cycle → fallback on `gh` failure). PR body template carries lane id, plan task, resume point. [Done: 2026-04-11]
- [completed] 5.1.2 Draft-PR mechanics validated end-to-end on vidux repo (leojkwan/vidux#4). Branch push → `gh pr create --draft` → `gh pr list` (visible, isDraft: true) → close + cleanup. coach-p0 plan was CLOSED (no work to ship), so tested directly instead. Friction: zero — `gh` CLI worked cleanly. Surprise: coach-p0 can't be the production pilot (plan closed); need a lane with active work for Wave 2. [Done: 2026-04-12]
- [completed] 5.1.3 Wrote `guides/draft-pr-flow.md` — cloud-agnostic core doctrine: the 5-step flow, branch naming convention, PR body template, recovery via `gh pr list`, fallback on `gh` failure, adoption snippet for lane prompts. [Done: 2026-04-12]

#### Wave 2 — Batch rollout (3 lanes) [completed]
- [completed] 5.2.1 Picked 3 lanes with active plans: `strongyes-backend-trust` (26p+25ip, high-vol), `strongyes-blog-pipeline` (8p, content), `resplit-revamp-executor` (12p+1ip, iOS shipping). [Done: 2026-04-12]
- [completed] 5.2.2 Applied draft-PR pattern from `guides/draft-pr-flow.md` to all 3 lane prompts: ACT sections updated (no merge to main, push branch + draft PR), PUSH POLICY replaced with 5-step flow, fallback on `gh` failure. [Done: 2026-04-12]
- [completed] 5.2.3 Observer-pair audit. strongyes lanes PASS (PR #283 open DRAFT, 10+ merged today by Leo). resplit-ios BLOCKED: `gh pr create` fails 4x with "shared commit overlaps with an existing PR" — lanes are following the draft-PR prompt but `gh` rejects when new branches share ancestry with old branches/PRs. [Done: 2026-04-14]

#### Wave 3 — Full fleet
- [pending] 5.3.1 Remaining ~10 automations. [Depends: Wave 2 complete ✓ — but resplit `gh pr create` overlap issue must be solved first for resplit lanes]
- [pending] 5.3.2 Validate `gh pr list` shows in-flight PR per active lane. [Depends: 5.3.1]

#### Wave 4 — Lock the gate
- [pending] 5.4.1 Branch protection: reject direct-main pushes from automation actors, preserve human pushes. [Depends: Wave 3 complete]
- [pending] 5.4.2 Smoke test both paths. [Depends: 5.4.1]

### Phase 6: Skill consolidation — 54 → ~42 skills [in_progress]

**Goal:** Cut dead weight and merge overlapping skills. 54 skills is bloat — vendor research (Anthropic + OpenAI) says: "earn your complexity" and "eval-driven pruning." Description quality drives activation (20%→90% with optimized descriptions per Anthropic testing). Every unused skill is noise in the routing table.

**Approach:** Three tiers. Tier 1 (delete) and Tier 2 (merge) are safe — evidence is clear. Tier 3 needs Leo's call.

#### Tier 1 — DELETE dead weight (8 skills, ~1,294 lines)

Bulk-import cruft from Codex skill installer. Zero project references in any lane prompt or PLAN.md.

- [completed] 6.1.1 Delete `hooks` — done 2026-04-12
- [completed] 6.1.2 Delete `jed` — done 2026-04-12
- [completed] 6.1.3 Delete `atlas` — done 2026-04-12
- [completed] 6.1.4 Delete `greenapple` — done 2026-04-12
- [completed] 6.1.5 Delete `judge0` — done 2026-04-12
- [completed] 6.1.6 Delete `doc` — done 2026-04-12
- [completed] 6.1.7 Delete `jupyter-notebook` — done 2026-04-12
- [completed] 6.1.8 Delete `spreadsheet` — done 2026-04-12

#### Tier 2 — MERGE overlapping skills (5 merges, net -5 skills)

- [completed] 6.2.1 Merge `ahrefs-seo` into `seo` — done 2026-04-12 (3 lane prompt refs updated)
- [completed] 6.2.2 Fold `figma` into `figma-implement` — done 2026-04-12 (MCP rules + references merged)
- [completed] 6.2.3 Merge `vidux-loop` + `vidux-recipes` → `vidux-fleet` — done 2026-04-12 (symlinks swapped)
- [completed] 6.2.4 Fold `vidux-version` + `vidux-status` — removed as standalone commands, done 2026-04-12
- [completed] 6.2.5 Delete `splitter` — done 2026-04-12 (Leo: "can be deleted")

#### Tier 3 — EVALUATE with Leo (needs human judgment)

- [completed] 6.3.1 `codex` (455 lines) — Deleted. Codex fleet deprecated, vidux is the super champ now. [Done: 2026-04-12]
- [completed] 6.3.2 `multithready` (198 lines) — Deleted. Worktree isolation absorbed by bigapple. [Done: 2026-04-12]
- [completed] 6.3.3 Fold `resplit-engineering` into `bigapple` — done 2026-04-12 (9 lane prompt refs updated). Leo confirmed.
- [completed] 6.3.4 `imagegen` — KEEP. Leo: "yes i think i do"
- [completed] 6.3.5 `maily` — KEEP. Leo: "yes i use maily"
- [completed] 6.3.6 Merge `media-studio` + `fcp` → `media` — done 2026-04-12 (2 lane prompt refs updated). Leo confirmed.

## Decisions
(Decision Log — intentional choices that future agents must not undo)
- [DIRECTION] [2026-04-09] vidux-loop.sh is NOT deleted — it still works and vidux-loop.sh stays as optional tooling. But automation prompts no longer require it. The gate is now inline in the prompt.
- [DIRECTION] [2026-04-09] 15 doctrines → 6 principles. The 9 removed are fleet ops (moved to guides/fleet-ops.md and /codex skill).
- [DIRECTION] [2026-04-09] No Redux jargon. No "store", "dispatch", "reduce", "unidirectional flow." Plain English only.
- [DIRECTION] [2026-04-09] COPY SAFETY: Automations must never invent marketing copy. Use only text patterns that exist in the codebase. Product is "StrongYes Pro" with "unlimited AI coaching." No sprints, no founder notes, no day-one plans. Evidence: remote trigger hallucinated copy in commit 5ef4498c.
- [DIRECTION] [2026-04-09] Remote triggers (claude.ai/code/scheduled) are dangerous — they push directly to main with zero review. Prefer Codex worktree model (pushes to branch first). Remote trigger for strongyes disabled.
- [DIRECTION] [2026-04-11] All automation pushes go through draft PRs — NEVER direct-to-main. Draft PRs are the durable, worktree-loss-proof manifest of in-flight work (recoverable via `gh pr list`). Phase 5 implements the cloud-agnostic core. Builds on the 2026-04-09 remote-trigger direction. Closes the Phase 2.4 loop (130 stranded resplit-ios branches with no PR metadata).
- [DIRECTION] [2026-04-11] vidux core is open-source and cloud-agnostic. Phase 5 contains ONLY draft-PR mechanics — no Greptile, no Sentry, no Nia, no Seer. Paid-service integrations live in `/vidux-codex` scope as composable skills, not in this plan. "Keep side effects like greptile and followups agnostic, that is more a /vidux-codex kinda thing." — Leo.
- [DIRECTION] [2026-04-12] Design skill naming convention: `brand-*` (identity), `craft-*` (platform patterns), `figma-*` (workflow). Renames: strongyes-design→brand-strongyes, picasso→craft-ios, preview-svg-design→craft-svg, figma-implement-design→figma-implement. New: brand-leojkwan. Do not revert these names.
- [DIRECTION] [2026-04-12] Skill consolidation: 54→~42 skills. Vendor research (Anthropic + OpenAI) confirms: "earn your complexity," "eval-driven pruning." Unused skills are noise in the routing table. Tier 1 deletes bulk-import cruft; Tier 2 merges overlapping pairs; Tier 3 needs Leo's call. vidux-skill-refiner cron (20 min) handles ongoing quality.

## Open Questions
- Q1: Should contract tests track guide files (guides/*.md) or only SKILL.md? -> Action: decide after v3 guides land
- Q2: Draft-PR ownership — lane-owned (`gh pr create --draft` per automation). **Confirmed 2026-04-11.**
- Q3: Draft → Ready promotion — always human click. **Confirmed 2026-04-11.**
- Q4: Auto-merge — NEVER from automation. **Confirmed 2026-04-11.**
- Q5: Scope — vidux fleet only; other repos adopt via their own plans. **Confirmed 2026-04-11.**
- Q6: Leo's personal pushes stay as-is (Phase 5 is automation-only). **Confirmed 2026-04-11.**
- Q7: 130 stranded resplit-ios branches left dead. **Confirmed 2026-04-11.**

## Surprises
- [2026-04-11] `vidux-core-test` cannot be the Wave 1 pilot — it operates on a non-git experiment directory (`~/Development/vidux-core-test/`) with explicit "NEVER do: `git push` anywhere" in its Authority block. The audit falsely classified it as "push-capable" because the prohibition text matched the grep pattern. Corrected pilot to `strongyes-coach-p0` which pushes directly to origin/main (the exact behavior to replace).
- [2026-04-14] resplit-ios `gh pr create` fails with "shared commit overlaps with an existing PR" — lanes follow the draft-PR prompt (they TRY to create PRs) but `gh` rejects when new branches share commit ancestry with old branches. The 130 stranded branches (Q7: "left dead") may be contributing. Impact: resplit Wave 3 blocked until this is resolved. strongyes unaffected.
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
- [2026-04-12] Phase 6 opened: skill consolidation 54→42. Design skill renames shipped (4 renames, 1 new brand-leojkwan, 15 cross-refs updated, 0 stale). Nia research confirms vendor guidance: Anthropic says "start minimal, earn complexity," OpenAI says "eval-driven pruning." Tier 1 (8 deletes: hooks, jed, atlas, greenapple, judge0, doc, jupyter-notebook, spreadsheet — all bulk-import cruft with zero lane references). Tier 2 (5 merges: seo+ahrefs-seo, figma+figma-implement, vidux-loop+vidux-recipes, vidux-version+vidux-status→vidux, splitter→pilot). Tier 3 (6 evaluate: codex, multithready, resplit-engineering, imagegen, maily, media-studio+fcp — need Leo). vidux-skill-refiner cron live (20 min, session-only). Next: Leo approves Tier 1+2 cuts, then execute.
- [2026-04-10 04:58 EDT] Overnight quality cycle 1: Fleet scorecard 6 SHIPPING / 4 IDLE / 0 blocked / 0 crashed / 0 mid-zone. SHIPPING: resplit-bug-fixer (re-verifying AJBM/AI4/AJL5 family on build 1648), resplit-code-quality (UITestLaunchConfigurationTests + dead-code prune), resplit-currency (CLF/CNH/FOK/GGP/IMP/JEP/XDR catalog gap), resplit-ios-ux (ja/es-ES/fr-FR locale screenshots, 5 locales remaining), resplit-web-ux (claim tap-target + desktop grid + heading hierarchy), strongyes-ux-scanner (problems metadata fix). IDLE: resplit-launch-loop (1648 already uploaded + distributed), strongyes-backend, strongyes-blog-writer (pivoted to DSA landers, evidence file pending), strongyes-release-train. ASC tracker: 17 fixed / 79 verified / 3 blocked / 0 new — bug-fixer is *correctly* idle-scanning per nurse log; 3 blocked rows (ABv07GVF OCR polling singleton, AFw7znl8 address geocoding, AKigU4Rh OCR key-value extraction) are architecture/eng-design tasks needing human input, not auto-resolvable. Vidux: pushed `f84b53e fix: align gate test with worker-first model` to origin/main (was 1 ahead); uncommitted v3 cleanup (-1834 lines: SKILL-v3 drafts + guides/vidux/* legacy guides + DOCTRINE/SKILL/commands/vidux.md consolidation) left untouched as in-progress sibling work. Flagged: `test_checkpoint_accepts_untracked_matching_process_fix_artifact` is a pre-existing flake — hangs at 10s subprocess timeout under pytest's capture_output but completes in 1-2s under raw subprocess.run; not caused by v3 cleanup, exists at HEAD.
- [2026-04-14] Self-improvement cron complete (10 items, 4 cycles, commits 01cb9c2→206b6cd): README Mode B diagram, fleet pattern refresh, comparison table fix, Lessons from Production section, claudux alignment, mermaid render fix. Cron cancelled after 2 IDLE checkpoints. Wave 2 observer audit (5.2.3): strongyes PASS (draft PRs working, Leo promoting), resplit-ios BLOCKED (gh pr create shared-commit overlap). Next: investigate resplit gh overlap issue before Wave 3.
<!-- 17 tasks archived to ARCHIVE.md -->
