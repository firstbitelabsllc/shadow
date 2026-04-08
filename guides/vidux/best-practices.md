# Vidux Best Practices

Lessons from 28+ cycles where Vidux built itself, managed a 10-automation fleet across Acme and Beacon, and ran overnight cron loops unsupervised. This is not theory. Everything here was learned the hard way.

---

## 1. Writing a Good PLAN.md

The plan is the single most important artifact. Not the code. The plan. If the plan is wrong, everything downstream is wrong.

**Purpose:** One paragraph, user-visible goal only. No implementation details. The Vidux build plan says: "Create a net-new plan-first orchestration system that makes quarter-long iOS projects completable in a week via overnight cron loops." No mention of hooks, scripts, or files. Just the outcome.

**Evidence** is the backbone. Every bullet cites a source with `[Source: ...]`. No source means it is a guess. Remove it or go find evidence.

Good evidence entry:
```
- [Source: SlopCodeBench, arxiv 2603.24755] Agent code degradation is monotonic.
  Erosion in 80% of trajectories. "Coding while thinking" is empirically bad.
```

Bad evidence entry:
```
- Agents probably drift from the plan over time. We should add checks.
```
No source. "Probably" means guessing. Does not belong in the plan.

**Constraints** use the ALWAYS / ASK FIRST / NEVER format:
- ALWAYS: invariants. "ALWAYS work across Claude Code, Cursor, and Codex."
- ASK FIRST: human-gated. "ASK FIRST before changing installer or bootstrap behavior."
- NEVER: hard prohibitions. "NEVER run more than 4 coding agents in parallel."

Include reviewer preferences grounded in real PR comments.

**The 10-point readiness checklist.** Score 7+ to code:

Required (all must be true or score is 0):
1. Purpose section filled
2. Evidence has 3+ cited sources with `[Source:]` markers
3. Constraints has at least one ALWAYS and one NEVER
4. At least one task with evidence cited
5. No open questions blocking the next task

Quality (each adds 1):
6. Evidence includes an external source (not just codebase greps)
7. Constraints include a stakeholder preference
8. Tasks have `[Depends:]` markers where applicable
9. Decisions section has an entry with alternatives and rationale
10. No vague task descriptions

**What happens when you skip this:** swiftify-v4 coded without capturing team conventions. Result: a Combine implementation reworked because the team preferred async/await. A 30-minute evidence pass through PR reviews would have caught it. The plan scored maybe 4/10.

---

## 2. The 50/30/20 Rule

50% refining the plan. 30% writing code. 20% last mile (build errors, CI, reviewer feedback, merges).

```
|  50% PLAN REFINEMENT     |  30% CODE     |  20% LM  |
|  gather, synthesize,     |  one task     |  build,  |
|  prune, update PLAN.md   |  per cycle    |  CI,     |
|                          |  derived      |  review  |
   <-- front-load thinking --> <mechanical> <- tail ->
```

If you are coding more than planning, stop. The Vidux build: of 16 early cycles, 9 were plan refinement, 4 code execution, 3 last mile. Roughly 56/25/19. It shipped clean. swiftify-v4 inverted this. Heavy coding, light planning. Multiple reworks.

---

## 3. The Closure Bias Defense

After completing any task, agents have a learned impulse to checkpoint and exit. "Context is getting tight." "This is a good stopping point." This is closure bias (Claude Code #34238). It is the single most common failure mode in unattended cron loops.

**The rule: after completing any task, scan the queue before checkpointing.**

```
Task completed, build passes
     |
     v
DO NOT CHECKPOINT YET
     |
     v
Open PLAN.md, scan for unchecked tasks
     |
     +--> More tasks pending? --> execute the next one
     |
     +--> Queue empty? --> NOW checkpoint
     |
     +--> Hard blocker? --> checkpoint with blocker noted
```

The "I am done" feeling is unreliable. The queue is truth.

**Real failure:** An Acme automation completed a payment flow fix, checkpointed, and exited at 4.7 minutes. Six more tasks were pending. The next cron fire spent 2 minutes bootstrapping context just to pick up where the last one could have continued. Multiply this by every run in a 10-automation fleet running overnight and the waste is substantial.

**How the quick check / deep work model fixes this structurally:** Quick check exits in under 2 minutes (nothing to do). Deep work has no exit until queue drain or hard blocker. There is no middle ground. The agent never decides "should I keep going?" because the mode already decided. See the architecture guide, Section 2.

---

## 4. Self-Extending Plans

Automations add tasks to PLAN.md themselves. Do not wait for the human to enumerate work.

When you fix a bug, log the related bugs you saw on the same surface. When you add a feature, log the polish and edge-cases you spotted. When you fix /pricing, check /plans too -- the same bug class often lives on adjacent pages. Think N steps ahead.

**The brake: three-strike rule.** If a surface already has 3+ queued polish tasks, ship the most impactful one and move on. Self-extension without a brake becomes recursive optimization forever. A good automation knows when a surface is honestly good and stops adding work to its own queue.

**Real failure:** An Acme automation discovered 14 polish tasks on a single view controller. Without the three-strike brake it would still be polishing. With the brake it shipped the top 3 and moved to the next gap in the mission.

**Mission honesty rule:** Separate "current slice status" from "release boundary" from "overall mission completion." If the overall mission has gaps elsewhere, polish on a done surface is procrastination. Only re-extend plans when investigation reveals new surfaces, not when you find one more pixel to align on a surface you already touched.

---

## 5. Product Taste Over Functional Correctness

Functional code is table stakes. The build passes, the tests are green -- that is the floor, not the ceiling. What separates a good automation from a great one is taste: anticipating the next ask, catching visual issues before the human sees them, and knowing when "works correctly" is not the same as "works well."

**Visual proof, not just green builds.** For any UI work, definition of done is a simulator screenshot or before/after comparison, not "the build passes." Load `$picasso` (or equivalent) for visual evaluation. A payment form that compiles but has 4px misaligned labels is not done.

**Anticipate the next ask.** When you fix /pricing, also check /plans -- same bug class, adjacent page. When you add a new API endpoint, check that the error states render correctly, not just the happy path. The automation that does this saves the human a round-trip of "now fix the other one."

**Before/after screenshots as proof.** When a UI task is complete, capture before and after. This is not documentation -- it is evidence that the change is an improvement. An agent that says "I fixed the layout" without visual proof is asking the human to trust. An agent that shows the screenshots is showing.

**Real example from Acme:** An automation fixed the currency conversion display -- build passed, tests green. But the formatted amount was clipped by the container on small screens. A `$picasso` visual check caught it in the same cycle. Without taste-level checking, it would have shipped broken to 320px devices and required a second cycle to diagnose and fix.

**Real example from Beacon:** An automation built the interview prep timer. Functionally correct -- it counted down, it beeped. But the font was 12px on a component that needed to be glanceable from arm's length. Product taste means catching this in the same cycle, not three cycles later when the human notices.

---

## 6. Fan-Out Research Pattern

Never have 20 agents write one file. 17x error amplification beyond 4 parallel agents without hierarchy.

```
          +----------+  +----------+  +----------+  +----------+
TIER 1    | Agent A  |  | Agent B  |  | Agent C  |  | Agent D  |
(parallel)| team chat|  | codebase |  | rules    |  | issues   |
          +----+-----+  +----+-----+  +----+-----+  +----+-----+
               |              |              |              |
               v              v              v              v
          evidence/      arch/        constraints/   tasks/
               |              |              |              |
               +---------+---+--------------+--------------+
                         |
                         v
                   +-----------+
TIER 2 (serial)    | Synthesizer|  reads all 4, writes one PLAN.md
                   +-----------+
                         |
                         v
                   +-----------+
TIER 3 (serial)    |   Critic   |  challenges assumptions
                   +-----------+
```

**Tier 1** -- 4 research agents, all parallel. Each writes to its own file.

**Tier 2** -- One synthesizer reads all four, writes unified PLAN.md.

**Tier 3** -- One critic challenges assumptions, checks for contradictions and scope creep.

Cap coding agents at 4 with a point guard plus workers model. Research agents can go wider because they are read-only. The Vidux build ran 9 research agents in Cycle 0 successfully.

Why subagents, not Teams? Teams persist across sessions (violates stateless doctrine), add coordination overhead, and risk orphaned state if the cron dies. Subagents are fire-and-forget.

---

## 7. Running Overnight Cron Loops

Each cycle is stateless: quick check reads the store, optionally fires deep work, checkpoint, exit. The next cycle is a fresh agent that knows nothing except what is in the files.

**30-minute cadence for fleet automations.** The Acme/Beacon fleet uses 30-minute cron intervals. Quick check fires every 30 min. If work is pending, deep work runs until the queue is drained. If nothing is pending, quick check exits in under 2 minutes.

**Expect auth expiry.** Tokens expire, MCP servers disconnect. A crashed session loses at most one cycle. The next cycle commits recovered work first.

**Commit is the checkpoint, not push.** Solo computer workflow. Commit after every cycle. Push when ready. Commit message: `vidux: [what you did]` with structured body (Plan, Evidence, Next, Blocker).

**Environment variables for ledger:** `AGENT_LANE` (work track) and `AGENT_SKILLS` (loaded skills).

---

## 8. Common Mistakes

**Coding without a plan entry.** Number one mistake. Every code change traces to a PLAN.md task. The PreToolUse hook reminds you, but it is a safety net, not a substitute. During the Vidux build, agents kept making "quick cleanups" to unplanned files. Each cleanup was small. The cumulative drift was not.

**Checkpointing after one task when more are pending.** Number two mistake. This is closure bias in action. Scan the queue. If there is more work, keep going. Deep work mode exists to enforce this structurally.

**Carrying context between sessions.** The next agent remembers nothing. Write it to PLAN.md or it does not exist.

**Too many parallel coding agents.** Four is the cap. Research agents can go wider (read-only).

**Forgetting to checkpoint.** No commit means the next session starts blind. Even plan-only refinement gets a commit.

**Plan without evidence.** An uncited entry is a guess. The readiness checklist requires 3+ cited sources to start coding.

**Self-extending without the brake.** Adding polish tasks is good. Adding 14 polish tasks to one surface while the mission has gaps elsewhere is procrastination. Three-strike rule: 3+ queued tasks on one surface means ship the best and move on.

**Functional correctness without taste.** Build passes, tests green, but the UI is broken on small screens. Load visual evaluation tools for UI work. Before/after screenshots are not optional.

---

## 9. When to Use Vidux vs Pilot

```
How big is the work?
     |
     +--> Under 2 hours, single file --> Pilot (Mode A)
     |
     +--> PR nursing, CI fix --> Pilot + Sloth
     |
     +--> Multi-session, 8+ files --> Vidux (Mode B)
     |
     +--> "We need to plan this" --> Vidux
     |
     +--> "Just do it" --> Pilot
```

**Rule of thumb:** "Will a second agent need to pick this up later?" If yes, Vidux. The plan makes handoff possible.

---

## 10. Debugging a Stuck Plan

```
Task stuck 3+ cycles
     |
     v
Check readiness score
     |
     +--> Below 7? --> Stop coding, refine the plan
     |
     +--> 7+? --> Task too large?
                    |
                    +--> Yes --> Break into sub-tasks
                    |
                    +--> No --> Evidence missing?
                                 |
                                 +--> Yes --> Gather evidence
                                 |
                                 +--> No --> External blocker?
                                              |
                                              +--> Yes --> Mark BLOCKED, move on
                                              |
                                              +--> No --> Run dual five-whys
```

**Most common cause:** Plan was not ready and agents are flailing. Check readiness score first.

**Stuck-loop detection:** same task in 3+ consecutive cycles means task is too large (break it), evidence is missing (gather it), or it is externally blocked (mark BLOCKED).

**Dual five-whys:** Two chains on every failure. Why did the error happen (technical)? Why did the agent make that mistake (process)? The process chain is more valuable -- it produces process fixes.

**Three-strike gate:** 3+ fixes on the same surface without resolution means the problem is in the design, not the code. Stop patching. Move up one abstraction layer.

---

## 11. The Failure Protocol

```
Build/test fails
     |
     v
Retry once (read error, form hypothesis, apply targeted fix)
     |
     +--> Pass? --> Continue, log surprise
     |
     +--> Fail? --> Dual five-whys
                     |
                     +--> Error chain (what broke technically)
                     +--> Behavior chain (why did the agent do that)
                     |
                     v
                3+ fixes on same surface?
                     |
                     +--> Yes --> Move up one abstraction layer
                     +--> No --> Produce two artifacts:
                                   1. Code fix (immediate repair)
                                   2. Process fix (constraint/hook/test)
                     |
                     v
                Update PLAN.md surprises
```

The code fix is table stakes. The process fix is the valuable output. Over the Vidux build, the drift detection hook, checkpoint enforcement, and three-strike gate itself all came from failures that were analyzed, not just patched.

---

## 12. Entry Gates: Quick Check and SCAN

Every automation harness prompt starts with a gate -- a copy-paste block that forces the agent to evaluate whether there is actionable work *before* loading skills, reading authority files, or doing any other work. The gate structurally eliminates mid-zone exits by making the "nothing to do" path fast and cheap.

There are two gate patterns. Which one you use depends on the automation's job:

- **Quick check gate** -- for writer automations that execute plan tasks. Checks *plan state* via `vidux-loop.sh` or the primary state file.
- **SCAN gate** -- for scanner/radar automations that inspect the codebase or live product. Checks *reality* via git history, file state, and its own memory.

**When to use which:** If the automation's job is to **find** issues (radars, scanners, linters, audit bots), use the SCAN gate. If its job is to **fix** known issues (writers, builders, release trains), use the quick check gate.

**Expected impact:** Gate exits drop from ~2 minutes to under 30 seconds. Agents that have nothing to do never load skills or read the authority chain. Over a 10-automation fleet running 30-minute cron intervals, this saves hundreds of wasted agent-minutes per day.

### 12a. Quick Check Gate Pattern

### With-Vidux variant (~850 chars)

Use this when the automation loads `$vidux` and has access to `vidux-loop.sh`. This is the standard variant for all Acme and Beacon automations.

```
REDUCE gate (run FIRST, before any other work):
1. Run: bash scripts/vidux-loop.sh <plan-path>
2. Read the JSON output. If ANY of these are true, checkpoint and exit immediately:
   - action is "blocked" or "auto_blocked" or "stuck" or "all_blocked"
   - action is "complete" or type is "done" or "empty" (BUT if queue_starved is true, proceed to five-point idle scan instead of exiting)
   - auto_pause_recommended is true
   - blocker_dedup is true (same blocker reported 3+ times -- stop wasting cycles)
   - bimodal_gate is "blocked"
   - next_action is "none"
   Write a 1-line memory note: "[REDUCE] <date> <reason>. No deep work."
   Do NOT read authority files, load skills, or do any other work. Exit now.
3. Read the last 3 memory notes. If the top note is a [REDUCE] exit with the
   same reason as this run's JSON, exit with: "[REDUCE] <date> unchanged. No deep work."
4. If next_action is "dispatch": proceed to full execution below.
Budget: steps 1-3 must complete in under 60 seconds. If you are still in the quick check
after 60 seconds, you are in the mid-zone. Checkpoint what you know and exit.
```

### Standalone variant (~800 chars)

Use this when the automation does not have `vidux-loop.sh` or operates outside the vidux plan-store model. The agent reads its own memory and primary state file directly.

```
REDUCE gate (run FIRST, before any other work):
1. Read the last 3 notes from this automation's memory file.
2. If the most recent note says any of: "blocked", "nothing to do", "unchanged",
   "no pending", "waiting on human", "same blocker" -- and it was written less
   than 2 hours ago -- exit immediately with a 1-line note:
   "[REDUCE] <date> Same state as last run (<quote reason>). No deep work."
   Do NOT read authority files, load skills, or gather evidence. Exit now.
3. Read the single primary state file (plan, queue, or tracker). Count actionable
   items. If zero actionable items and no new items since the last note, exit with:
   "[REDUCE] <date> No new work. No deep work."
3.5. If zero items in the primary file, run the five-point idle scan (Doctrine 14):
   INBOX.md → sibling memory → git log on owned paths → blocked task recheck → codebase TODO/FIXME scan.
   If any scan finds work: add to plan, proceed to execution.
   If all scans clean: exit with "[REDUCE] <date> Five-point scan clean. No deep work."
4. If actionable work exists: proceed to full execution below.
Budget: steps 1-3 must complete in under 60 seconds.
```

### 12b. SCAN Gate Pattern

Use this for scanner and radar automations -- agents whose job is to observe, detect, and report, not to execute plan tasks. The SCAN gate checks reality (git history, file state, live surfaces) instead of plan state. A localization radar checks for hardcoded strings in the codebase; a UX radar checks rendered surfaces. Neither consults PLAN.md to decide whether to run.

```
SCAN gate (run FIRST, before any other work):
1. Read last 3 memory notes from this automation's memory file.
   If the same "no issues found" verdict appears 3 consecutive times with no
   codebase changes between them, exit with:
   "[SCAN] <date> unchanged, no new issues. No deep work."
   Do NOT read authority files, load skills, or do any other work. Exit now.
2. Check for changes: git log --since="<timestamp of last scan>" -- <watched_paths>
3. If no changes since last scan AND last scan found no issues → exit with:
   "[SCAN] <date> no changes to <watched_paths> since last scan. No deep work."
4. Otherwise → proceed to full scan below.
Budget: steps 1-3 must complete in under 60 seconds.
```

**Key differences from quick check:**
- No `vidux-loop.sh` call. Scanners do not read plan state.
- The staleness check is git-based (`git log --since`), not plan-based (`next_action`).
- The "3 consecutive identical verdicts" rule prevents a radar from endlessly re-scanning unchanged code.
- `<watched_paths>` scopes the change detection to the paths the radar actually cares about (e.g., `src/` for a code scanner, `assets/locales/` for a localization radar).

**When the SCAN gate exits:** The radar found nothing new to report, and the codebase has not changed in the paths it watches. This is the correct "nothing to do" signal for an observer.

**When the SCAN gate proceeds:** Either the codebase changed since the last scan (new commits in watched paths) or the last scan found issues that need re-verification. The radar does a full scan and writes its findings.

### Deep-work mid-zone kill

The quick check gate prevents mid-zone on the way *in*. This rule prevents it during deep work:

> **If 3+ minutes pass in deep work mode with no file write and no active research query,
> checkpoint what you have and exit.**

Do not re-read the plan, re-assess state, or "think about what to do next" -- that is
quick check work happening inside a deep run. Either write a file or exit. The circuit
breaker in `vidux-loop.sh` enforces this from the outside (blocks deep work after N idle
cycles), but the agent should self-enforce from the inside too.

Fleet data (2026-04-07): 32% of Codex sessions land in the 3-8 min mid-zone. Target: <15%.

### Cross-lane READ step

After the gate passes and before execution begins, every automation MUST read sibling state. This is Doctrine 13 -- cross-lane awareness is not optional. Three mandatory checks:

1. **Sibling memory scan** -- Read the last note from every sibling automation's memory file (`~/.codex/automations/*/memory.md`). Know what shipped in the last hour and what surfaces are claimed. An automation that skips this will duplicate work or collide with an active lane.

2. **Hot-files check** -- Read `.agent-ledger/hot-files.md` in the target repo. If another lane is actively touching files you are about to touch, yield or coordinate. Two lanes editing the same file in the same cycle produces merge conflicts that waste the next cycle to resolve.

3. **Fleet duplicate detection** -- If your planned work overlaps with what a sibling just shipped, skip it. Do not fix what is already fixed. Do not scan what was just scanned. The dedup check is a single pass over sibling memory notes -- it costs seconds and saves entire cycles.

**Where this goes in the harness prompt:** Immediately after the Authority/read-order block and before the Execution block. The agent reads the gate, then reads authority, then reads siblings, then acts. This ordering ensures the agent never starts work without knowing the fleet state.

**Real failure:** Five Beacon radars polled the same empty queue without knowing each other existed. `acme-web` did not know `acme-backend` just fixed the same surface. Both shipped competing branches. The merge cost more than the original fix.

### Insertion point guidance

Both gate blocks go **inside** the prompt string, immediately after the mission and skill-loading lines, and **before** the authority chain or read order. The agent must hit the gate before it starts reading authority files. The gate text is literal -- copy it verbatim, replacing only `<plan-path>` (quick check) or `<watched_paths>` (SCAN) with the automation's actual values.

### When to use which gate

| Automation type | Gate |
|-----------------|------|
| Writer that loads `$vidux`, has a PLAN.md | Quick check (With-Vidux) |
| Writer without vidux, has its own queue/tracker | Quick check (Standalone) |
| Scanner/radar that inspects codebase or product | SCAN |
| Radar that feeds findings to a writer via PLAN.md | SCAN (radar scans, writer acts) |

---

### 12c. Radar->Writer Inbox Pattern

Radars observe. Writers execute. The inbox connects them. When a scanner finds an actionable issue, it appends a timestamped entry to `INBOX.md` (which lives next to the project's `PLAN.md`). Writers check the inbox during their READ step, before looking at the task queue.

**When to use:** Any fleet where scanners and writers operate on the same project. Without the inbox, radar findings go to memory notes that writers never read. The feedback loop is broken.

**Entry format:**
```
- [YYYY-MM-DD] [scanner-id] Finding: <description> [Evidence: <file:line or proof path>]
```

**Promotion flow:** If actionable, the writer creates a `[pending]` task in PLAN.md and deletes the inbox entry. If not actionable, the writer annotates it with `[SKIP: reason]` and leaves it. Scanners are append-only -- they never edit or delete inbox entries.

**20-entry cap:** If INBOX.md reaches 20 entries, oldest non-skipped entries are archived to `evidence/` before new ones are appended. A full inbox means the writer is not keeping up. That is a fleet health signal, not a formatting problem.

---

## 13. Fleet Health Orchestrator

When running 5+ automations on the same project, a coordinator automation should manage fleet health instead of letting each automation fend for itself.

**When to use a coordinator:** Any fleet with 5+ automations, or any fleet where 3+ automations share the same plan or target repo. Below that threshold, individual gate logic (quick check/SCAN) is sufficient.

**The 5-step fleet scan:**

1. Read all automation memories in one pass (not one at a time)
2. Classify each: SHIPPING, IDLE, BLOCKED, CRASHED, MID-ZONE
3. Detect patterns: queue starvation (N idle on same plan), shared blockers (escalate, don't retry), file collisions (coordinate or yield), gate mismatches (scanner on quick check = wrong gate)
4. Act at fleet level: pause idle clusters, escalate repeated blockers, fix gate types, redistribute imbalanced queues
5. Report scorecard: N shipping / N idle / N blocked / N crashed / N mid-zone

**Anti-patterns:**

- Editing individual prompts while the fleet is dead (mid-zone work at orchestrator level)
- Retrying the same blocker across 3+ cycles without escalating
- Spinning up new automations without checking what the existing fleet is doing (Doctrine 13)
- Treating all idle automations identically — idle-because-queue-empty is different from idle-because-gate-misconfigured

See SKILL.md "Fleet health orchestrator pattern" for the full specification.

---

## 14. Quick Reference

**Before coding:** Readiness score 7+? If not, refine the plan.

**Before editing a file:** Covered by a PLAN.md task? If not, update plan first.

**After completing a task:** Scan the queue. More work pending? Keep going. Do not checkpoint yet.

**Before checkpoint:** Progress section updated? Tasks checked off? Committed?

**Before stopping:** Can a stranger pick up from the files alone?

**On failure:** Retry once. Dual five-whys. Three-strike check. Always produce a process fix alongside the code fix.

**On stuck plan:** Readiness score. Break large tasks. Gather missing evidence. Mark blockers. Escalate with five-whys.

**On UI work:** Visual proof required. Before/after screenshots. Load $picasso or equivalent.

**Commit is the checkpoint.** Not push. Every cycle. Always.

---

## 14. Writing Automation Prompts

A harness prompt is not prose. It is a machine-readable contract between the cron scheduler and the agent. Every prompt follows the same eight-block structure, in order. Rearranging blocks or omitting one produces the failure modes documented in Phase 18.

### 14a. Prompt Structure

```
1. MISSION        — One line. User-visible goal. No implementation details.
2. SKILLS         — Load skills: $vidux, $pilot, $picasso, etc.
3. GATE           — REDUCE or SCAN. Runs FIRST. Decides work/exit in <60 sec.
4. AUTHORITY      — Read order for plan files. Primary state file is #1.
5. CROSS-LANE     — Read sibling memory notes + hot-files. Dedup, yield, skip.
6. ROLE BOUNDARY  — What this lane owns. What belongs to siblings.
7. EXECUTION      — How to do the work. Mid-zone kill rule. Queue drain rule.
8. CHECKPOINT     — Memory format. Lead line. What to leave explicit.
```

**Why this order matters:** The gate must run before authority reads. An agent that reads 6 authority files before discovering it has nothing to do just wasted 90 seconds. Cross-lane must come after authority but before execution, so the agent never starts work without knowing fleet state.

### 14b. Before/After Example

This is based on a real fleet failure. The automation was dead overnight — 0 runs shipped code.

**BAD prompt (~4800 chars, gated on wrong file):**

```
You are a helpful assistant that fixes App Store Connect bugs.

Use $vidux and $pilot for ASC bug fixes in the Acme iOS repo.

Remember to always follow the plan-first methodology. The plan is the
store, code is the view. Always gather evidence before coding. Use the
50/30/20 split. Never code without a plan entry.

REDUCE gate:
1. Run: bash scripts/vidux-loop.sh projects/acme/PLAN.md
2. If action is "complete" or "done", exit.
3. Otherwise proceed.

Read these files:
- DOCTRINE.md
- SKILL.md
- projects/acme/PLAN.md
- The ASC bug tracker in the repo

When fixing bugs, investigate the root cause first. Use dual five-whys.
Apply the three-strike rule. Check readiness score. Remember the closure
bias defense. Ship with taste, not just functional correctness.

Commit with: vidux: [what you did]
```

**What is wrong:**

| Problem | Why it kills the automation |
|---------|---------------------------|
| Gates on `projects/acme/PLAN.md` (meta-plan, status: "done") | Gate always exits. Agent never reaches deep work. |
| Restates doctrine ("plan is the store", "50/30/20", "closure bias") | 800+ chars of noise the agent already knows from $vidux |
| No cross-lane awareness | Agent does not know if a sibling just fixed the same surface |
| No role boundary | Agent might try to do release work that belongs to launch-loop |
| "Read these files" lists DOCTRINE.md | Agent spends 60 sec reading files it loaded via $vidux |
| No mid-zone kill rule | Agent can sit in 3-8 min limbo reading plans without writing |
| Vague authority ("The ASC bug tracker in the repo") | Agent must search for the file instead of being told the path |

**GOOD prompt (~2400 chars, gates on actual bug tracker):**

```
Use [$vidux](/path/to/vidux/SKILL.md) and [$pilot](/path/to/pilot/SKILL.md)
for ASC bug fixes.

Mission: Fix App Store Connect feedback and bugs in /path/to/acme-ios.
Every bug fix leaves the UI better than the reporter expected.

Load skills: $vidux, $pilot, $picasso, $bigapple, $xcodebuild

REDUCE gate (run FIRST, before any other work):
1. Read the last 3 notes from this automation's memory file.
2. If the most recent note says any of: "blocked", "nothing to do",
   "unchanged", "no pending", "waiting on human", "same blocker"
   -- and it was written less than 2 hours ago -- exit immediately:
   "[REDUCE] <date> Same state as last run (<quote reason>). No deep work."
   Do NOT read authority files, load skills, or gather evidence. Exit now.
3. Read /path/to/acme-ios/plans/app-store-feedback.plan.md.
   Count open/pending bug items. If zero, exit with:
   "[REDUCE] <date> No pending ASC bugs. No deep work."
4. If actionable bugs exist: proceed to full execution below.
Budget: steps 1-3 must complete in under 60 seconds.

Authority:
1. /path/to/acme-ios/plans/app-store-feedback.plan.md (PRIMARY)
2. /path/to/acme-ios/.agent-ledger/hot-files.md

Cross-lane awareness (MANDATORY before execution):
- Read last note from siblings: acme-web, acme-currency, acme-launch-loop
- Read .agent-ledger/hot-files.md. If another lane owns files, yield.
- If a sibling just shipped a fix on the same surface, skip it.

Role boundary:
- This lane owns ASC feedback: investigation, reproduction, fix, proof.
- Release/upload belongs to acme-launch-loop. Hand off, do not own.

Execution:
- Pick the top pending ASC bug. Investigate root cause (Doctrine 7).
  Fix it. Screenshot proof via $xcodebuild + $picasso.
- Reading and triaging is NOT a valid stop. Fix at least one bug per run.
- If 2+ bugs hit the same surface, bundle into one investigation.
- Every failure produces a process fix alongside the code fix (Doctrine 6).
- If 3+ minutes pass with no file write, checkpoint and exit.
- Keep working until the queue is empty or a hard blocker stops you.

Checkpoint:
- Lead with ASC: hot or ASC: cold.
- Update memory (last 3 notes). Leave bug IDs, proof, blocker, next bug.
```

**What changed:** Gate targets the actual bug tracker (not the "done" meta-plan). Doctrine is loaded via `$vidux`, not restated. Cross-lane and role boundary are explicit. Mid-zone kill is present. Size dropped from ~4800 to ~2400 chars.

### 14c. Gate Selection Guide

```
What does the automation DO?
     |
     +--> Executes plan tasks, has vidux-loop.sh --> REDUCE (With-Vidux)
     |         e.g., acme-web, beacon-release-train
     |
     +--> Executes tasks, no vidux-loop.sh      --> REDUCE (Standalone)
     |         e.g., acme-asc (reads repo plan), acme-launch-loop (reads git state)
     |
     +--> Inspects codebase or product           --> SCAN
     |         e.g., acme-localization-pro, ux-radar, security-scanner
     |
     +--> Not sure                               --> Default to REDUCE (Standalone)
              Writer that finds nothing just exits. Scanner on REDUCE is permanently dead.
```

**The critical asymmetry:** A writer on the wrong plan file exits cleanly (no work found). A scanner on a quick check gate is permanently dead — it checks plan state instead of codebase state, finds "nothing to do," and exits every cycle forever. This is why the default is writer, not scanner. A miscategorized writer wastes one cycle. A miscategorized scanner never runs.

### 14d. Common Mistakes

**1. Gating on the wrong plan file.** The number one prompt authorship error. Three of six automations gated on a meta-plan that was already marked "done." The agent hit the gate, saw "complete," and exited before loading a single skill. The fix: the gate reads the file where actionable work items actually live.

**2. Scanner using a quick check gate.** A localization radar was given a writer gate. Writers check "is there work in my queue?" Scanners check "has the codebase changed?" The radar checked the plan, found no tasks assigned to it, and exited. It never scanned a single file. Fix: SCAN gate with `git log --since` on watched paths.

**3. Circuit breaker and auto_pause deadlocks.** Safety mechanisms can become traps. Circuit breaker opens after N idle cycles and blocks dispatch. But if dispatch is blocked, the automation stays idle, so CB stays open. Same loop with auto_pause. Fix: ensure the Progress section has shipping signal keywords when work is actually shipped (shipped, commit, fixed, merged, created, built, added, wrote, pushed). If the plan's Progress section has stale entries, the safety mechanisms fire on ghosts.

**4. Restating doctrine in the prompt.** The agent loads doctrine via `$vidux`. Restating "plan is the store," "50/30/20 split," or "closure bias defense" in the prompt adds 500-1000 chars of noise that the agent already internalized from the skill file. This pushes the prompt past 4000 chars and crowds out the actually-unique instructions (gate, authority, role boundary).

**5. Vague authority references.** "Read the bug tracker" forces the agent to search. "Read `/path/to/app-store-feedback.plan.md`" does not. Every authority file gets an absolute path and a role label (PRIMARY, collision avoidance, etc.).

**6. Missing mid-zone kill.** Without the explicit rule ("if 3+ minutes pass with no file write, checkpoint and exit"), agents drift into plan-reading loops during deep work. The kill rule is one line. Omitting it costs entire cycles.

**7. Missing role boundary.** Without an explicit "this lane owns X, sibling owns Y," a writer automation will drift into adjacent work and create merge conflicts with sibling lanes.

**8. Exiting on empty queue without scanning.** The queue being empty does not mean there is no work. The ASC bug tracker had 71 open items while the automation exited "nothing to do" for 24 hours. Doctrine 14 requires a five-point idle scan before any "nothing to do" exit. Every clean exit must cite what was scanned.

### 14e. Skill Token Format

Skill tokens use the `$name` convention. They are shorthand for "load this skill file."

```
$vidux      — Plan-first orchestration (SKILL.md)
$pilot      — Stack-aware routing and small tasks
$picasso    — Visual evaluation and screenshot proof
$bigapple   — iOS/Apple platform conventions
$xcodebuild — Xcode build, test, simulator, screenshot
$ledger     — Cross-agent activity ledger
$hooks      — PreToolUse/PostToolUse hooks
$brand-*    — Brand-specific design tokens (e.g., $brand-acme)
$*-engineering — Project-specific engineering conventions
```

The first line of the prompt declares skill dependencies with markdown links:

```
Use [$vidux](/path/to/SKILL.md) and [$pilot](/path/to/pilot/SKILL.md) for <work>.
```

This gives the agent both the token name and the file path. The `Load skills:` line later lists all tokens the agent should activate. Only list skills the automation actually uses — loading unused skills wastes context budget.

### 14f. Size Guidance

**Target: 2000-3000 characters.** The six rewritten fleet prompts range from 1800 to 2600 chars. The original broken prompts were 3500-5200 chars.

| Range | Signal |
|-------|--------|
| < 1500 chars | Missing a block. Check: gate? cross-lane? role boundary? |
| 1500-3000 chars | Healthy. Each block is present and concise. |
| 3000-4000 chars | Audit for doctrine restatement or verbose gate logic. |
| 4000+ chars | Almost certainly restating things the skill files already provide. |

**Where the bloat hides:**
- Doctrine restatement (500-1000 chars of "plan is the store" prose)
- Multiple paragraphs of execution philosophy instead of bullet rules
- Authority chain that lists DOCTRINE.md, SKILL.md, and other files the agent loads via skill tokens
- Inline explanations of why each gate step matters (the agent does not need justification, just rules)

**The test:** Can you delete a sentence without changing the agent's behavior? If yes, delete it.
