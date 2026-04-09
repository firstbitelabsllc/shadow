# Automation Prompt Authoring

Reference for writing cron automation prompts (harnesses). Loaded by `/codex` and `/claude` when creating or updating automation prompts.

---

## Core Rule (Doctrine 8)

A cron prompt is a **stateless harness** -- it encodes the end goal and project-specific instructions the agent cannot infer. It never contains current state.

**The harness is the PROCESS. PLAN.md is the STATE. Never mix them.**

**IN the harness:** end goal, authority store path, role boundary, design DNA, guardrails, skills to invoke.

**NEVER in the harness:** task numbers, cycle counts, progress summaries, branch names, file lists, implementation tasks, current blockers, or any snapshot of state.

One loop per project/mission. If a loop exists, refine it -- do not create a sibling.

---

## 8-Block Prompt Structure

Every harness follows these eight blocks, in this order. Rearranging or omitting blocks produces known failure modes.

```
1. MISSION        -- One line. User-visible goal. No implementation details.
2. SKILLS         -- Load skills: $vidux, $pilot, $picasso, etc.
3. GATE           -- Quick check or SCAN. Runs FIRST. Decides work/exit in <60 sec.
4. AUTHORITY      -- Read order for plan files. Primary state file is #1.
5. CROSS-LANE     -- Read sibling memory + hot-files. Dedup, yield, skip.
6. ROLE BOUNDARY  -- What this lane owns. What belongs to siblings.
7. EXECUTION      -- How to do the work. Mid-zone kill. Queue drain. Worktree merge-back.
8. CHECKPOINT     -- Memory format. Lead line. What to leave explicit. Worktree state.
```

**Why this order:** Gate runs before authority reads. An agent that reads 6 files before discovering it has nothing to do wastes 90 seconds. Cross-lane comes after authority but before execution so the agent never starts work without knowing fleet state.

---

## Writer vs Scanner Detection

The gate type must match the automation type. A scanner on a quick check gate is permanently dead -- it checks plan state, finds nothing, and exits every cycle.

| Signal in request | Type | Gate |
|---|---|---|
| scan, watch, monitor, audit, check quality, find issues, radar, lint, detect, sweep, inspect | **Scanner** | SCAN gate (file changes + last scan results) |
| build, ship, release, deploy, execute tasks, pop queue, run plan, train | **Writer** | Quick check gate (vidux-loop.sh + plan state) |
| Ambiguous | Ask: "scanner (inspects for issues) or writer (executes plan tasks)?" | |

**Quick check gate** -- for writers. Checks plan state via `vidux-loop.sh` or memory + primary state file. Exits when all tasks are done/blocked.

**SCAN gate** -- for scanners. Checks reality via `git log --since` on watched paths + last scan results. Exits when no codebase changes and 3 consecutive clean scans.

Both gates must complete in under 60 seconds. See `guides/vidux/best-practices.md` Section 12 for full gate templates.

---

## Size Guidance

**Target: 2000-3000 characters.**

| Range | Signal |
|---|---|
| < 1500 chars | Missing a block. Check: gate? cross-lane? role boundary? |
| 1500-3000 chars | Healthy. Each block is present and concise. |
| 3000-4000 chars | Audit for doctrine restatement or verbose gate logic. |
| 4000+ chars | Almost certainly restating things skill files already provide. |

**Where bloat hides:** doctrine restatement (the agent loads it via `$vidux`), verbose execution philosophy, authority listing files already loaded via skill tokens, inline explanations of why gate steps matter.

**The test:** Can you delete a sentence without changing the agent's behavior? If yes, delete it.

---

## Common Mistakes

1. **Gating on the wrong file.** Three of six automations gated on a meta-plan marked "done." The agent saw "complete" and exited before loading a single skill.
2. **Scanner with a writer gate.** Checks plan state, finds no tasks, exits. Never scans.
3. **Restating doctrine.** 500-1000 chars of "plan is the store" prose the agent already knows from `$vidux`. Delete it.
4. **Vague authority.** "Read the bug tracker" forces a search. Give absolute paths.
5. **Missing mid-zone kill.** Without "if 3+ min pass with no file write, exit," agents drift into plan-reading loops.
6. **Missing role boundary.** Agent drifts into sibling work, creates merge conflicts.
7. **Missing cross-lane.** Agent duplicates work a sibling just shipped.
8. **Empty queue = exit.** Wrong. Doctrine 14 requires a five-point idle scan before any "nothing to do" exit. Cite what was scanned.

---

## Prompt Amplification (Amp Flow)

When `/vidux` is invoked interactively, amplify the request before executing.

```
RAW INPUT -> GATHER -> AMPLIFY -> PRESENT -> [STEER...] -> FIRE -> EXECUTE
```

**GATHER** (10 sec max): git status/log, glob/grep keywords, check existing plans/automations, active tasks, recent evidence.

**AMPLIFY** -- detect mode from input:

| Signal | Mode |
|---|---|
| cron, automation, schedule, loop, recurring | **HARNESS** -- produce evergreen cron prompt per Doctrine 8 (then detect writer vs scanner) |
| plan, project, investigate, research | **PLAN** -- produce mission description, no code |
| Everything else | **EXECUTE** -- produce specific, evidence-cited, actionable prompt |

**PRESENT**: Show amplified prompt in a box. End with "steer me or say fire."

**STEER**: "fire"/"go" = proceed. "closer" = minor tweak. "no" = major redirect. "add/drop X" = scope change. Max 5 rounds.

**FIRE**: Strip scaffolding, execute the amplified prompt as the task spec.

**Rules:** Real context only. Never hallucinate sources. If GATHER finds 3+ unrelated candidates, disambiguate. For HARNESS mode, never include task numbers, cycle counts, or progress -- state lives in PLAN.md.

**Skip amplification when:** cron automation running, `[in_progress]` task exists, user says "fire"/"go"/"continue".
