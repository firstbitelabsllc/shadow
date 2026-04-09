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
- [pending] 1.6 Replace SKILL.md with SKILL-v3.md (after testing automations with new prompts)
- [pending] 1.7 Update /claude skill to reference v3 patterns

### Phase 2: Resplit automation revamp [spawns: investigations/resplit-revamp.md]

- [completed] 2.1 Rewrite 6 resplit prompts — drop vidux-loop.sh, use v3 gate [Done: 2026-04-09]
- [completed] 2.2 Apply prompts to Codex DB + restart [Done: 2026-04-09]
- [completed] 2.3 Verify: resplit-web-ux SHIPPED (CTA fix, 20min run). Others idle/reset. [Done: 2026-04-09]
- [pending] 2.4 Clean up stale resplit worktrees (351) and branches (71)

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

## Decisions
(Decision Log — intentional choices that future agents must not undo)
- [DIRECTION] [2026-04-09] vidux-loop.sh is NOT deleted — it still works and vidux-loop.sh stays as optional tooling. But automation prompts no longer require it. The gate is now inline in the prompt.
- [DIRECTION] [2026-04-09] 15 doctrines → 6 principles. The 9 removed are fleet ops (moved to guides/fleet-ops.md and /codex skill).
- [DIRECTION] [2026-04-09] No Redux jargon. No "store", "dispatch", "reduce", "unidirectional flow." Plain English only.
- [DIRECTION] [2026-04-09] COPY SAFETY: Automations must never invent marketing copy. Use only text patterns that exist in the codebase. Product is "StrongYes Pro" with "unlimited AI coaching." No sprints, no founder notes, no day-one plans. Evidence: remote trigger hallucinated copy in commit 5ef4498c.
- [DIRECTION] [2026-04-09] Remote triggers (claude.ai/code/scheduled) are dangerous — they push directly to main with zero review. Prefer Codex worktree model (pushes to branch first). Remote trigger for strongyes disabled.

## Open Questions
- Q1: Should contract tests track guide files (guides/*.md) or only SKILL.md? -> Action: decide after v3 guides land

## Surprises
- [2026-04-09] v3 rewrite removed 6 PLAN.md sections the contracts enforce. Contract tests caught it immediately.
- [2026-04-09] Remote Claude trigger hallucinated marketing copy ("14-day sprint", "founder notes", "First Bite Labs") while fixing T91/T92. The automation read the plan correctly but invented product concepts. Root cause: no copy safety constraint in prompt. Fix: added COPY SAFETY to writer prompts + reverted bad commit.
- [2026-04-09] Claude Desktop v1.1062.0 migrated from local-agent-mode-sessions/ to claude-code-sessions/. Local scheduled tasks JSON not carried over. Local task creation is UI-only — no programmatic API exists (anthropics/claude-code#41364).

## Progress
- [2026-04-09] Plan created. SKILL-v3.md drafted (220 lines). 4 guides extracted (810 lines). /claude skill created. Remote trigger created then disabled (pushed hallucinated copy to main).
- [2026-04-09] All 12 Codex automations on v3 prompts. 0 vidux-loop.sh refs. resplit-web-ux SHIPPED (CTA fix). codex-watch ran fleet scan. StrongYes T92 shipped (/prep 44→101 companies). Bad copy reverted + COPY SAFETY added. 4 repos synced (0/0). Remaining: replace SKILL.md with v3, GC 351 resplit worktrees + 71 branches.
