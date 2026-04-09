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

- [in_progress] 2.1 Rewrite 6 resplit prompts — drop vidux-loop.sh, use v3 gate
- [pending] 2.2 Apply prompts to Codex DB + restart
- [pending] 2.3 Verify each fires and dispatches (check memories after 1 cycle)
- [pending] 2.4 Clean up stale resplit worktrees and branches

### Phase 3: StrongYes automation revamp [spawns: investigations/strongyes-revamp.md]

- [in_progress] 3.1 Rewrite 4 strongyes prompts — drop vidux-loop.sh, use v3 gate
- [pending] 3.2 Apply prompts to Codex DB + restart
- [pending] 3.3 Verify each fires and dispatches
- [pending] 3.4 Verify Vercel build passes (casing fix landed)

### Phase 4: Fleet infrastructure

- [completed] 4.1 Rewrite codex-watch prompt (simplified fleet scan)
- [completed] 4.2 Rewrite strongyes-content-scanner prompt
- [pending] 4.3 Apply fleet prompts to DB + restart
- [pending] 4.4 Run /codex fleet to verify scorecard

## Decisions
(Decision Log — intentional choices that future agents must not undo)
- [DIRECTION] [2026-04-09] vidux-loop.sh is NOT deleted — it still works and vidux-loop.sh stays as optional tooling. But automation prompts no longer require it. The gate is now inline in the prompt.
- [DIRECTION] [2026-04-09] 15 doctrines → 6 principles. The 9 removed are fleet ops (moved to guides/fleet-ops.md and /codex skill).
- [DIRECTION] [2026-04-09] No Redux jargon. No "store", "dispatch", "reduce", "unidirectional flow." Plain English only.

## Open Questions
- Q1: Should contract tests track guide files (guides/*.md) or only SKILL.md? -> Action: decide after v3 guides land

## Surprises
- [2026-04-09] v3 rewrite removed 6 PLAN.md sections the contracts enforce. Contract tests caught it immediately.

## Progress
- [2026-04-09] Plan created. SKILL-v3.md drafted (220 lines). 4 guides extracted. 8/12 prompt rewrites in progress (3 agents). /claude skill created. Remote trigger created then disabled (user wants local/Codex only).
