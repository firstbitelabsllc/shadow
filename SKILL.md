---
name: vidux
description: "Plan-first discipline for AI agents. Write down what you're going to build before you build it. Plans live in markdown files in git. Any agent can pick up where the last one left off."
---

# Vidux

Vidux is a discipline for AI agents: write down what you're going to build before you build it. Plans live in markdown files in git. Agents read the plan, do one piece of work, update the plan, and checkpoint. Any agent can pick up where the last one left off because the plan file is the only state that matters.

---

## Five Principles

### 1. Plan first, code second

PLAN.md is the source of truth. Code is derived from it. To change code, update the plan first.

Every plan entry cites evidence -- a codebase grep, a PR comment, a design doc quote, a team chat message. A plan entry without evidence is a guess. Guesses cause rework.

### 2. Design for interruption

Every session ends. Context will be lost. Auth will expire. State lives in files, never in memory. Checkpoints are structured (not freeform summaries). Any agent can resume from the last checkpoint.

After any interruption, re-read PLAN.md and evidence/ from disk. Never trust summaries or memory for plan details.

### 3. Investigate before fixing

Bug tickets are not line items. Before coding, map root cause, related surfaces, and impact. A fix without investigation is a guess.

When 2+ tickets touch the same surface, bundle them into one investigation. The investigation produces a root cause analysis, an impact map, and a fix spec. If the fix spec is missing, the cycle is investigation only -- no code.

### 4. Self-extend with a brake

Agents add tasks they discover. When you fix a bug, log the related bugs you saw. When you add a feature, log the edge cases you spotted.

But a shipped surface that works is done -- stop polishing and move to the next gap. If overall mission has gaps elsewhere, polish on a done surface is procrastination. Only re-extend plans when investigation reveals new surfaces, not when you find one more thing to tweak on a surface you already finished.

### 5. Prove it mechanically

Never assert "it works." Run the build, run the tests, show the screenshot. Definition of done for UI work is a visual proof, never just "the build passes."

When an audit or grep produces a count or classification, **spot-check at least one entry from each category** before making decisions on it. A grep hit is not a fact -- it's a lead. A line matching "git push" might be a prohibition ("NEVER git push"), not an instruction. An automation classified as "push-capable" might operate on a non-git directory. Validate before you plan; plan before you code.

After a failure, produce two artifacts: a code fix (the immediate repair) and a process fix (a hook, a test, a constraint, a plan update). The process fix is the valuable output -- it makes the system smarter for next time.

---

## The Cycle

Every work session follows this loop:

```
READ       -> PLAN.md, INBOX.md, git log, git diff (uncommitted work?)
ASSESS     -> Resume [in_progress] first, else first eligible [pending].
             No evidence? Refine plan, no code. Empty plan? Research first.
ACT        -> Execute tasks until queue empty, blocker, or context budget
VERIFY     -> Build, test, gate
CHECKPOINT -> Commit as `vidux: [what you did]` + Progress entry.
             Reconcile planned vs actual; update plan if they diverge.
```

**Crash recovery:** If `git diff` shows uncommitted work from a dead session, commit it first: `vidux: recover uncommitted work from crashed session`.

**Stuck detection:** If the same task appears in 3+ Progress entries while still `[in_progress]`, it is stuck. Mark it `[blocked]` with a Decision Log entry. Only a human can unblock it.

**Push authorization:** Not all pushes carry the same risk. Agents should act on the safest tier without asking and escalate for riskier tiers:

1. **Draft PRs** — always safe. Push to a feature branch + `gh pr create --draft` without asking. The PR is the review gate; the push itself is low-risk because nothing reaches main without human merge.
2. **Direct-to-main** — explicit authorization required per lane or per session. A blanket "you can push" from the human covers this tier.
3. **Destructive** (force push, branch delete, `git reset --hard`) — per-action authorization. Never batch these under a blanket approval.

If the lane prompt says "NEVER push" with no tier distinction, treat it as tier 2+3 blocked but tier 1 (draft PRs) still allowed. An agent that parks for 8 hours on a draft-PR push is wasting time on a safe operation.

### Queue order

Tasks are processed top-to-bottom with these rules:

1. **[in_progress] always resumes first** -- a prior session died mid-task
2. **Dependencies resolve before dependents** -- `[Depends: Task N]` blocks until N is `[completed]`
3. **[pending] tasks run top-to-bottom** -- the first eligible task wins
4. **[P] tasks may run in parallel** -- up to 4 concurrent agents, one point guard
5. **No reordering mid-cycle** -- to change priority, update the plan with a Decision Log entry

---

## PLAN.md Template

**Every project has exactly ONE PLAN.md.** Course corrections — even dramatic pivots — update the existing plan's Decision Log. They do NOT spawn a sibling plan store. If you catch yourself justifying a new plan with phrases like "clean slate," "emotional separation," or "this rewrite deserves its own home," stop: that's fabricated reasoning. The correct move is to open the existing PLAN.md, add a `[DIRECTION]` entry to the Decision Log, mark now-obsolete tasks `[blocked]` with a pointer to the new direction, and append the new direction as fresh `[pending]` tasks in the same queue. New plan stores are for new PROJECTS (different codebase, different product, different problem surface), not for new OPINIONS about how the same project should look. "Rewrite resplit-web from scratch" and "polish resplit-web" are the same project — one plan. "Build a new iOS app for Resplit 2.0" and "ship resplit-web" are different projects — different plans.

Planning itself can happen in the agent's main thread. What matters is WHERE the output lands: the existing PLAN.md for the project, always.

Required sections:

```markdown
# [Project Name]

## Purpose
Why this exists. One paragraph. User-visible goal.

## Evidence
What we know, cited with sources.
- [Source: codebase grep] file:line pattern
- [Source: GitHub PR #1234] "feedback or constraint"
- [Source: design doc] "architectural decision"

## Constraints
- ALWAYS: [things that must be true]
- NEVER: [things that are forbidden]

## Tasks
Ordered, with status tags and evidence citations.
- [pending] Task 1: description [Evidence: ...]
- [in_progress] Task 2: description [Evidence: ...]
- [completed] Task 3: description [Evidence: ...]
- [blocked] Task 4: description [Blocker: ...]

Inside ## Tasks, every line starting with `- ` MUST be a task with a
status tag. Use numbered lists (1. 2. 3.) or headers for non-task
content like rollout strategies or phase preambles.

Status FSM: pending -> in_progress -> completed
                 \-> blocked -> pending

## Decision Log
Intentional choices that future agents must not undo.
- [DELETION] [date] Removed X. Reason: Y. Do not re-add.
- [DIRECTION] [date] Chose X over Y. Reason: Z.

## Open Questions
- Q1: [question] -> Action: [what to research]

## Surprises
Unexpected findings during execution. Timestamped.
- [Date] Found: X. Impact: Y. Plan update: Z.

## Progress
Living log updated each cycle.
- [Date] What happened. Next: what's next. Blocker: if any.
```

---

## Quarter-Sized Projects

Vidux is designed for projects that span days to months. A quarter project has:

- **A top-level PLAN.md** with the mission, phases, and current tasks
- **Sub-plans in `investigations/`** for complex surfaces that need root cause analysis before code
- **Evidence snapshots in `evidence/`** that back plan decisions (named `YYYY-MM-DD-<slug>.md`)
- **An `INBOX.md`** where humans or external tools deposit findings for agents to act on
- **A Progress log** that any agent can read to understand where things stand

The plan LIVES -- it gets updated every cycle, not written once and followed blindly.

### Compound tasks and sub-plans

Not every task is atomic. Some need investigation before code. A compound task links to an investigation file:

```markdown
- [pending] Task 3: Fix payment flow [Investigation: investigations/payment-flow.md]
```

The `[Investigation: ...]` marker tells the agent: read the sub-plan before coding. If the investigation has no fix spec yet, the cycle is investigation only. Sub-plans follow the same structure (evidence, root cause, fix spec, tests).

**Nesting depth:** Max two levels (L1 plan, L2 investigation). L3 is allowed only when an investigation reveals a nested bug that itself needs investigation -- this is rare. If you need L3, the surface is probably too complex and should be broken into separate L1 plans.

**Status propagation:** When an L2 investigation's Fix Spec is coded, tested, and gated, the parent task in L1 PLAN.md moves to `[completed]`. An L2 with no Fix Spec yet means the parent stays `[in_progress]` -- the investigation IS the work.

#### Worked example: L1 compound task + L2 investigation lifecycle

Parent task in L1 `PLAN.md`:

```
- [in_progress] Task 3: Fix payment flow [Investigation: investigations/payment-flow.md]
  [Evidence: Sentry def-123, 47 occurrences; grep "checkout" → 4 hits across 3 files]
```

**Stage 1 — investigation stub, no Fix Spec yet.**

`investigations/payment-flow.md`:

```
## Reporter Says
"Checkout double-charges on fast retry." — Sentry def-123, PR #4567 comment.

## Evidence
- src/checkout/submit.ts:42 — no idempotency key
- src/checkout/retry.ts:18 — no in-flight guard
- Sentry def-123 — 47 occurrences / 7 days

## Root Cause    (pending)
## Impact Map    (pending)
## Fix Spec      (pending)
## Tests         (pending)
## Gate          (pending)
```

L1 Task 3 STAYS `[in_progress]`. This cycle is investigation-only — no code. The agent's job is to push one `(pending)` section forward (Root Cause → Impact Map → Fix Spec → Tests → Gate) and checkpoint. Any cycle that tries to ship code while Fix Spec is still `(pending)` is a mechanism violation — catch it at VERIFY.

**Stage 2 — Fix Spec + Tests + Gate land. Code ships. L1 flips.**

Once the Gate section confirms build + tests + visual pass, the parent task in L1 flips:

```
- [completed] Task 3: Fix payment flow [Investigation: investigations/payment-flow.md]
  [Fix: src/checkout/submit.ts:42, src/checkout/retry.ts:18] [Shipped: <commit sha>]
```

The investigation file is NOT deleted on completion. It stays as the historical record of *why* the fix looks the way it does. Future agents who touch the same surface read it before acting.

**Four rules this example illustrates:**

1. **No Fix Spec = no code.** The investigation IS the work until the Fix Spec section is filled. Cycles that find `(pending)` in Fix Spec may only push sections forward, not ship code.
2. **Status flows UP.** L1 completion is driven by L2 state — never mark L1 `[completed]` while L2 has any `(pending)` section.
3. **Sub-plans are durable.** Keep `investigations/<slug>.md` after the parent task completes. Archive it via the GC rules (older than 180 days, not "task done"), not immediately.
4. **Decision Log stays in L1.** L2 has Root Cause + Impact Map, but directional choices ("we chose idempotency over a distributed lock") belong in the parent PLAN.md Decision Log so they survive even after the investigation file is archived. L2 is the *why this bug happened*; L1 Decision Log is *why we fixed it this way*.

### Inbox

`INBOX.md` is where humans or external tools drop findings for agents to act on:

- Agents check INBOX.md during READ, before looking at tasks
- Promote actionable findings to `[pending]` tasks in PLAN.md
- Annotate non-actionable ones with `[SKIP: reason]`
- Max 20 entries. If full, oldest are archived to `evidence/`.

### Garbage collection

- **Archive** completed tasks when PLAN.md exceeds 200 lines or 30+ completed tasks
- **Prune** worktrees older than 24h with no unmerged commits
- **Rotate** Decision Log entries older than 180 days to `evidence/`
- **Clean** INBOX.md entries promoted or skipped

---

## Course Correction

The plan is a living document. When evidence changes, the plan changes. When the plan changes, the work changes.

When something breaks or changes:

1. **Update the plan FIRST** -- what changed, why, what's the new direction
2. **Then update the code** -- derived from the new plan state
3. **Every failure produces a process fix** -- not just a code fix

---

## Every agent is a worker

Every writer finds work AND does work. When the queue is empty, agents look for work — check INBOX.md, scan owned paths, check git log, recheck blocked tasks. If any scan finds work: add it as `[pending]`, then execute. If all clean: checkpoint and exit.

---

## Investigation Template

For complex bugs or surfaces with 2+ tickets, create `investigations/<slug>.md`:

```markdown
# Investigation: [surface name]

## Reporter Says        — exact quote from feedback
## Evidence             — files, related tickets, recent commits, repro steps
## Root Cause           — the specific code path, not symptoms
## Impact Map           — other UI paths, other tickets, state flow
## Fix Spec             — file:line changes with evidence for why
## Tests                — assertions covering this ticket and related tickets
## Gate                 — build passes, tests pass, visual check (for UI)
```

If the Fix Spec is missing, the cycle is investigation only -- no code.

---

## Part 1 → Part 2 transition

Everything above is **Part 1: Discipline** — the five principles, the cycle, the PLAN.md template, investigations, course correction. It works for humans, one-shot AI sessions, and cron-scheduled workers alike. A human following Part 1 alone is doing vidux correctly.

**Part 2: Automation** (below) covers the *how* when vidux work runs on a schedule — sessions cycling, lanes persisting, delegation, session-gc, observer pairs. If your task is a one-off plan, stop reading here.

---

# Part 2: Automation

Automation is optional. It's how you run vidux workers on a schedule so work progresses even when you're not at the keyboard. Everything in Part 2 is additive — it never overrides Part 1.

## When to automate (and when not to)

Automate when **all** of these are true:
- Work spans multiple sessions and would lose context across handoff
- The cycle is repeatable (each fire does the same kind of work on whatever's pending)
- State can live on disk (PLAN.md, memory.md, ledger) between fires
- You accept losing conversation scrollback in exchange for 24/7 progress

Do NOT automate when:
- The work needs live human judgment every step
- The cycle can't be described in a self-contained prompt
- The state would have to live in session memory
- It's a one-off fix — just do it directly

## The 24/7 Fleet Operating Model (summary)

One invariant: **lanes persist on disk, sessions cycle through them.**

```
Lanes (persistent)                    Sessions (disposable)
~/.claude-automations/<lane>/         ~/.claude/projects/*/*.jsonl
├── prompt.md   (mission)             - cycle when bloated
└── memory.md   (durable state)       - state never lives here
```

A lane = `prompt.md` + `memory.md` on disk. These files persist regardless of what session fires them. When a session dies, the files stay; the next session re-schedules the cron and the lane resumes from memory.md tail.

**Hot vs cold storage:**

| Layer | Lives here | GC |
|---|---|---|
| **Cold** (durable) | PLAN.md, evidence/, investigations/, memory.md per lane, `.agent-ledger/activity.jsonl` | Manual archive when PLAN.md > 200 lines |
| **Hot** (disposable) | `~/.claude/projects/*/*.jsonl` | Automatic via `session-prune.py --gc-old` hourly |

**session-gc is mandatory for 24/7.** A lane at `~/.claude-automations/session-gc/prompt.md` fires hourly, runs `python3 scripts/session-prune.py --gc-old 3`, and emits `[CYCLE SIGNAL]` over 40 MB so you know when to `/resume`. Without it, JSONLs grow unbounded and `/resume` stops working.

**Session bloat controls:**
- Cycle session at 40 MB (fresh session starts under 1 MB)
- `"skillListingBudgetFraction": 0.005` in settings.json (halves skill-listing payload)
- Disable unused plugins (Vercel plugin on a non-Vercel project = ~30% of JSONL)
- `CronCreate` over `ScheduleWakeup` for ≥10 fires (CronCreate = fresh session per fire)

## Lane management — minimum needed, max 6 per session

Every lane must earn its keep. More than 6 lanes per session causes worktree contention and JSONL bloat (measured).

**Coordinator pattern (default for 24/7):** ONE coordinator lane per active repo that owns ALL concerns (ship code, fix CI, archive PLAN.md, watch INBOX). Beats the specialist model (separate shipper/product/a11y/seo lanes) for these reasons:
- No PLAN.md stampede (one writer per plan)
- End-to-end ownership (same lane that shipped fixes the test)
- 60% less JSONL growth (1 coordinator × 3 fires vs 5 specialists × 3 fires)
- Simpler mental model when something breaks

**Observer (one exception to "fewer lanes"):** A read-only lane that audits the coordinator each cycle. Catches drift the coordinator can't self-audit. Add one per repo if drift is measured — skip if not. Never preemptive.

**Polish-brake:** If your last 3 checkpoints all ship from the same surface, force a surface switch. Polish is fractal — every green PR has another P3 comment. The brake prevents infinite iteration on a done surface.

## Delegation (the primary context cutter)

Two modes distribute work between a **primary model** (metered, decides/reviews) and a **secondary model** (unlimited/cheaper, grunt work).

**Mode A: Research.** Primary writes a prompt, secondary reads 30–150 KB, returns a 3-section summary (~300 tokens). Primary reads only the summary. Measured: **10–110x token savings** vs direct reads.

```
Primary: "30 files, needs auditing. Hand it off."
Secondary: reads, reasons, compresses to Summary + Evidence + Recommendation.
Primary: reads ~300 tokens, applies taste, ships.
```

**Mode B: Implementation.** Primary writes a 5-block spec, secondary edits files in the working tree. Primary reviews `git diff` (~500 tokens) instead of writing 50 lines itself. Measured: **~5x further savings** on code-writing cycles.

```
Primary: "50-line fix. Here's Task + Files + Spec + Acceptance + Out-of-scope."
Secondary: writes code.
Primary: git diff → accept | re-prompt | git checkout . + retry.
```

**Decision tree:**
- Substantial code writing (>10 lines, clear spec) → Mode B
- Reading code, grinding a hard problem, research → Mode A
- Pure planning, taste call, <10 lines of obvious writing → primary does it directly

**The Mode A compression contract** (paste verbatim in every Mode A prompt):
```
Output ONLY these sections, nothing else:
1. Summary: 3 sentences MAX.
2. Evidence: 3 file:line references MAX, one per line.
3. Recommendation: 1 sentence MAX.
Do not explain. Do not echo the task. Do not write code.
```

**The Mode B prompt shape** (five blocks, all mandatory):
```
1. Task: one-sentence description.
2. Files: exact paths the secondary may edit.
3. Spec: what the code must do, 3–10 bullets.
4. Acceptance criteria: how the primary will judge the diff.
5. Out of scope: what the secondary must NOT change.
```

The "Out of scope" block is load-bearing. Without it, the secondary refactors adjacent code it decides "looks wrong" and the primary either accepts scope creep or rejects the whole diff.

## Lane Bootstrap Recipe

When the user asks to create an automation ("I want a lane that…", "automate this", "run this every hour"), follow this recipe.

### 1. Decide the runtime

| Signal | Choose |
|---|---|
| Tight cycle (15–30 min), fast feedback, reads memory.md | **Claude-local** (CronCreate) |
| Weekly / long-cycle, heavy reads, big compute budget | **Codex-local** (automations table + shim) |
| Unsure / first lane | **Claude-local** — simpler to debug |

Default: Claude-local unless the cycle needs Codex's unlimited compute budget.

### 2. Pick the role

- **Coordinator** — owns a whole repo (ship + fix + GC). 1 per active repo. Max 1.
- **Observer** — read-only auditor for a coordinator. Add only when drift is measured.
- **Burst** — single short-lived task with auto-expire. Delete when done.
- **Radar** — read-only scan, no writes, no worktree. For research-only missions.

### 3. Create the files

For **Claude-local** lanes:

```
~/.claude-automations/<lane-id>/
├── prompt.md        # Mission, authority, role, hard rules, checkpoint format
└── memory.md        # Empty on creation; lane appends 2-3 sentences per cycle
```

For **Codex-local** lanes (the Dynamic Prompt Shim pattern):

```
~/.codex-automations/<lane-id>/
├── prompt.md        # Real mission (editable — hot reload on next fire)
└── memory.md        # Same shape as Claude side
~/Development/ai/automations/<lane-id>/
└── automation.toml  # Canonical TOML (synced across machines)
~/.codex/automations/<lane-id>/     # Real dir (NOT symlink)
└── automation.toml  # Symlink to the canonical TOML above
```

The `automation.toml` contains a **static shim prompt** that routes Codex to the real `prompt.md`. Codex registers the shim in its SQLite DB at startup. Edits to the dynamic `prompt.md` take effect on the next fire — no restart needed.

### 4. Write the prompt

Every prompt.md has these sections (in order):

```
MISSION      — 1 paragraph. What this lane does, for which repo/project.
SKILLS       — "Load: /vidux, <lane-specific-skills>"
GATE         — Under-45s check at fire start. When to exit early vs proceed.
AUTHORITY    — Which files/systems this lane may touch. Paths explicit.
ROLE         — Writer | Observer | Radar | Burst. Sets tier permissions.
HARD RULES   — Never use --no-verify. Never force push. Never edit legal code.
              Never touch files outside AUTHORITY.
CHECKPOINT   — Format for the memory.md entry on exit.
```

The MISSION section matters most: it's what differentiates this lane from all others. Be specific about the *output* (a merged PR, a checkpointed decision, an appended evidence line) not just the *input* (check this, scan that).

### 5. Register + schedule

**Claude-local:**
```
CronCreate({
  name: "<lane-id>",
  cron: "0 */1 * * *",    # hourly, or your cadence
  prompt: "Read ~/.claude-automations/<lane-id>/prompt.md and execute the cycle it describes."
})
```
Test-fire once. If the first-fire output looks right, leave it.

**Codex-local:**
Use the SQLite INSERT recipe — see `references/automation.md` → "Creating Codex Desktop Automations". Needs a Codex restart once after first install; subsequent prompt.md edits hot-reload.

### 6. Verify + checkpoint

- Confirm the lane's `memory.md` gets its first entry on the next fire
- Confirm the `[CYCLE] ...` log format matches the CHECKPOINT spec in prompt.md
- Add the lane to INBOX or coordinator memo so future sessions know it exists

### When in doubt

Read `references/automation.md` for the full doctrine — session-gc internals, observer setup, PR lifecycle nursing, cross-fleet coordination, and Codex shim gotchas.

---

## When to use Part 2

Part 2 applies when any of these are true:
- Creating, managing, or auditing a lane
- Debugging fleet behavior (a lane isn't firing, checkpoints look wrong)
- Designing cross-fleet coordination (Claude + Codex on the same PLAN.md)
- Setting up session-gc or observer lanes

For everything else — planning, investigating, shipping a one-off fix — Part 1 alone is the full tool. Don't let automation mechanics leak into ordinary plan work.

---

## Activation

Vidux activates when:
- User says `/vidux` or describes work spanning multiple sessions
- An existing PLAN.md governs the work
- Pilot routes into it after detecting expedition-scale work
- User asks to create or manage a lane/automation/cron (Part 2 foregrounded)

Vidux does NOT activate for:
- Single-file changes with obvious cause
- Anything that takes less than 30 minutes with a clear root cause
