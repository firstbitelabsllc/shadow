# vidux + pilot merge — [SUPERSEDED 2026-05-22]

> **STATUS: SUPERSEDED.** Direction reversed 2026-05-22. Leo's instruction was the opposite of this plan — keep `/pilot` as the mega orchestrator entry point, keep `/vidux` as the pure dev-execution mechanic called by `/pilot`, and create `/pilot-leo` (in ai-leo) as the personal overlay absorbing the former `/vidux-leo`. `/captain` continues to own skill OS work.
>
> **What actually shipped (2026-05-22):**
> - `/pilot-leo` created at `ai-leo/skills/pilot-leo/SKILL.md` (873 lines, absorbed all `/vidux-leo` content + new Section 0 PR macro-shape)
> - `/vidux-leo` → SUPERSEDED stub redirecting to `/pilot-leo`
> - `/pilot` shipped Specialist Fan-out Molecule + cross-tool hooks/skills/plugins section (ct-ai-skills commits `a03c9ea`, `f339e3a`, `5d7540b`)
> - `/captain` shipped Snap Mode section (ct-ai-skills commit `b2b8c7a`)
>
> **Why this plan didn't ship:** Tasks 2-6 below were never executed. The 2026-05-22 session that Leo drove went the other direction (consolidate at /pilot, not /vidux). This file kept for historical context only.
>
> **If you're picking up vidux/pilot work**, the canonical current state lives at:
> - `~/Snapchat/Dev/ct-ai-skills/skills/pilot/SKILL.md` (shared, Snap-internal)
> - `~/Snapchat/Dev/ai-leo/skills/pilot-leo/SKILL.md` (personal overlay)

---

## Original Purpose (historical)

Consolidate `/vidux` and `/pilot` into a single skill at `~/Development/ai/skills/vidux/SKILL.md`. Today `/pilot` is the universal router that detects stack/stage/scale, then delegates expedition-scale work into `/vidux`. Leo asked to merge them on 2026-05-13 — they overlap enough that two skills create friction.

Outcome: one entry point. `/vidux loop` and `/vidux nurse` replace `/pilot loop` and `/pilot nurse`. Pilot's `stacks/`, `stages/`, `orchestration/`, `patterns/`, `scripts/` subfiles remain on disk and are referenced by name from the merged SKILL.md.

## Evidence

- [Source: Leo voice, 2026-05-13] "combine /vidux /pilot"
- [Source: codebase grep] `~/Development/ai/skills/vidux/SKILL.md` is 657 lines; `~/Development/ai/skills/pilot/SKILL.md` is 505 lines.
- [Source: pilot SKILL.md L82-91] Pilot's own description: "Pilot is the universal entrypoint and router. Vidux is Pilot's plan-first expedition mode for long-running, doc-first, multi-session work."
- [Source: codebase grep] 10 sibling skills reference `/pilot` literally — `auto`, `ralph`, `creator`, `captain`, `ledger`, `clipdiff`, `amp`, `disk-clean`, `jam`, `vidux-leo`. Each needs a rewrite to `/vidux`.
- [Source: ct-ai-skills checkout] `~/.claude/skills/pilot/SKILL.md` is a real directory copy (not a symlink into ai repo), maintained in the `ct-ai-skills` repo. Captain audit flags drift between the two.
- [Source: pilot/scripts/, pilot/orchestration/, pilot/stages/, pilot/stacks/, pilot/patterns/] 13 subfiles contain real content that the merged SKILL.md cross-links to by name. Deleting the directory wholesale would force 1100+ inline lines.

## Constraints

- ALWAYS: keep `~/Development/ai/skills/pilot/` directory present so sibling files (stacks/*, stages/*, orchestration/*, patterns/*, scripts/*) stay reachable.
- ALWAYS: ship in 3 commits — references first, content merge second, pilot stub third. Stage gate after each.
- ALWAYS: search active crons / Routines / launchd plists for literal `/pilot` invocations BEFORE pilot SKILL.md is stubbed. Replace those prompts in commit 1.
- NEVER: symlink `/pilot` → `/vidux` (frontmatter collision; captain audit breaks).
- NEVER: delete `/pilot` SKILL.md without leaving a redirect stub. Mid-session muscle memory must hit a "load /vidux" message, not a 404.

## Tasks

Ordered, with status tags and evidence citations.

- [completed] Task 1: Audit live cron prompts for literal `/pilot` invocations. Check `CronList` output, `~/Library/LaunchAgents/*.plist`, and `~/.codex/automations/`. Report findings. [Evidence: cron-audit agent 2026-05-13 — ZERO automation risk, all clean] [ETA: 0.5h]
- [pending] Task 2 [Depends: Task 1]: Rewrite `/pilot` → `/vidux` in 10 sibling skill SKILL.md files (auto, ralph, creator, captain, ledger, clipdiff, amp, disk-clean, jam, vidux-leo). Also update `vidux/guides/fleet-ops.md` L423 and `vidux/guides/harness.md` L27 to drop `$pilot` from SKILLS-load examples. Single commit titled `skills: prepare for /vidux merge — rewrite /pilot references`. [Evidence: cross-skill grep, 23 total references] [ETA: 1.5h]
- [pending] Task 3 [Depends: Task 2]: Merge pilot SKILL.md content into vidux SKILL.md per the 22-section outline below. Target ~720 lines (vidux today 657 + 70 net new from pilot after dedup). Single commit titled `vidux: absorb /pilot routing + loop + nurse + orchestration content`. [Evidence: merge plan §2 outline below] [ETA: 3h]
- [pending] Task 4 [Depends: Task 3]: Wait 24h after Task 3 ships. Verify no `[in_progress]` lanes cite `/pilot`. Verify no cron has fired against unrewritten prompt. [Evidence: stage-gate per Decision Log] [ETA: 24h elapsed]
- [pending] Task 5 [Depends: Task 4]: Replace `~/Development/ai/skills/pilot/SKILL.md` with 5-line redirect stub. Commit to both ai repo AND `ct-ai-skills` repo (the `~/.claude/skills/pilot/SKILL.md` real-directory copy). [Evidence: captain two-machine sync rule] [ETA: 0.5h]
- [pending] Task 6 [Depends: Task 5]: Verify fleet: spin `/pilot` in a fresh Claude Code session, confirm stub redirects to `/vidux`. Spin `/vidux loop` in a real repo, confirm it picks up the queue. Update Leo's CLAUDE.md if needed (currently no `/pilot` literal mention, just `/vidux-leo`). [Evidence: smoke test before declaring done] [ETA: 0.5h]

## Decision Log

- [DIRECTION] [2026-05-13] Merge into `/vidux` (not the other way). Vidux is the deeper plan-first concept; pilot was always a router into vidux. Pilot's name becomes a redirect stub.
- [DELETION] [2026-05-13] Pilot's restatement of "plan first" principle (L6-18) — duplicates Vidux Principle 1.
- [DELETION] [2026-05-13] Pilot's "Relationship To Vidux" section (L82-91) — becomes self-referential after merge.
- [DIRECTION] [2026-05-13] Keep `pilot/stacks/`, `pilot/stages/`, `pilot/orchestration/`, `pilot/patterns/`, `pilot/scripts/` subfiles in place. Don't migrate to `vidux/`. Cross-link by relative path from merged SKILL.md. Defer the directory-rename migration — second cliff with no immediate user benefit.
- [DIRECTION] [2026-05-13] Stage as 3 commits with 24h gate between commit 3 (content merge) and commit 4 (pilot stub). Anti-cliff discipline: if a cron fires `/pilot loop` literally and we stub before catching the prompt, the cron breaks. The gate catches it.
- [DIRECTION] [2026-05-13] Redirect strategy = stub (option b). Not delete (subfiles still referenced). Not symlink (frontmatter collision + captain audit).

## Merged SKILL.md outline (22 sections)

For reference during Task 3. Target line count in parens.

1. Frontmatter (5)
2. Intro paragraph (8) — vidux verbatim
3. Activation & Triage (40) — NEW; merges pilot Step 0 + vidux Activation
4. Five Principles (60) — vidux verbatim
5. Working Defaults (25) — NEW from pilot: flow-with-water, testability, close-the-loop, smallest-slice, DELETE-before-MODIFY, No-Re-Ask
6. The Cycle (80) — vidux verbatim + absorbs pilot Step 4 "Read the Room" as READ checklist; adds Trunk-First Rule
7. PLAN.md Template (50) — vidux verbatim
8. Quarter-Sized Projects (180) — vidux verbatim: investigations, nesting modes, vidux.config.json, adapter contract, Linear extension, INBOX, GC
9. Course Correction (15) — vidux verbatim
10. Investigation Template (18) — vidux verbatim
11. Persistent Loop Mode (50) — NEW; absorbs pilot /pilot loop + Anti-Loop Discipline (3-strike, diminishing returns, same-command ban, all-blocked, compaction survival, cron+interactive interleave)
12. Nursing Mode (30) — NEW; absorbs pilot /pilot nurse
13. Orchestration Mode (50) — NEW; compressed from pilot orchestration: SOLO vs ORCHESTRATED, Default Discipline Swarm, Release Swarm (10-role table), heat scan, multi-prototype fan-out, cross-links to orchestration/*
14. Stack & Stage Routing (25) — NEW; compressed from pilot Steps 1-2, with cross-links to stacks/* and stages/*
15. Skill Composition (25) — NEW; pilot Step 5 universal-skills list + 8 Routines recipes table + Routines/CronCreate/loop heuristic
16. Checkpoint Breadcrumbs (10) — NEW; pilot's commit+push+ledger+plan rule
17. Replaces /superpowers (35) — vidux verbatim
18. Output Formats — One-shot HTML decision briefs (10) — vidux verbatim
19. Browser (90) — vidux verbatim: vidux-browse, artifacts, annotations, local plan notes, Voxtral
20. Voice & Tone (15) — NEW from pilot
21. Reference Files (10) — NEW from pilot; table of pilot/orchestration/*, pilot/patterns/*, pilot/stacks/*, pilot/stages/*
22. Beyond Core — Automation and Recipes (10) — vidux verbatim

Estimated total: ~720 lines (current vidux 657 + 70 net pilot content after deletes).

## Pilot stub content (for Task 5)

```
---
name: pilot
description: "Merged into /vidux on 2026-05-13. Load /vidux instead."
---

# Pilot — merged into /vidux

This skill consolidated into `/vidux` on 2026-05-13. All routing, /loop, /nurse, stack
detection, orchestration molecules, and lane discipline now live in `/vidux`.

Subfiles (orchestration/*, patterns/*, stacks/*, stages/*, scripts/*) remain in this
directory and are referenced by name from `/vidux` SKILL.md.

Use `/vidux` for all entry points. `/vidux loop` and `/vidux nurse` replace `/pilot loop`
and `/pilot nurse`.
```

## Migration risk register

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Cron prompt literally invokes `/pilot loop`, breaks after stub | Medium | Task 1 audits all crons; Task 2 rewrites prompts BEFORE Task 5 stubs the skill |
| In-flight `[in_progress]` lane mid-cycle cites /pilot | Low | Ship Task 5 on a Friday EOD; verify no in_progress lanes mention /pilot |
| ct-ai-skills `~/.claude/skills/pilot` drifts from ai repo | Medium | Task 5 commits to BOTH repos in same change |
| Long-running agent session muscle memory still calls /pilot | Low | Stub's first line says "MERGED INTO /vidux" — partial reads still catch redirect |
| /auto "Resplit default bundle" row still loads /pilot | High | Task 2 rewrites /auto in same commit as other sibling skills |
| /vidux-leo overlay references "core /vidux § ...section..." that doesn't exist post-merge | Low | Preserve existing vidux section names in merged file; only NEW sections get new names |

## Progress

- [2026-05-13] Plan opened. Pre-merge audit complete: 4 stale plans archived, 1 worktree GC'd, 5 doc fixes (statusline.sh, install-hooks.sh, Linear config fields, config field schema, SECURITY.md audit date), .gitleaksignore added. Next: Task 1 (cron audit) before any reference rewrites.
