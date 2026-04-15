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
ASSESS     -> Does the next task have evidence? Yes = code. No = refine plan.
ACT        -> Execute tasks until queue empty, blocker, or context budget
VERIFY     -> Build, test, gate
CHECKPOINT -> Structured commit: what changed, what's next, blockers
```

**Crash recovery:** If `git diff` shows uncommitted work from a dead session, commit it first: `vidux: recover uncommitted work from crashed session`.

**Stuck detection:** If the same task appears in 3+ Progress entries while still `[in_progress]`, it is stuck. Mark it `[blocked]` with a Decision Log entry. Only a human can unblock it.

**Push authorization:** Not all pushes carry the same risk. Agents should act on the safest tier without asking and escalate for riskier tiers:

1. **Draft PRs** — always safe. Push to a feature branch + `gh pr create --draft` without asking. The PR is the review gate; the push itself is low-risk because nothing reaches main without human merge.
2. **Direct-to-main** — explicit authorization required per lane or per session. A blanket "you can push" from the human covers this tier.
3. **Destructive** (force push, branch delete, `git reset --hard`) — per-action authorization. Never batch these under a blanket approval.

If the lane prompt says "NEVER push" with no tier distinction, treat it as tier 2+3 blocked but tier 1 (draft PRs) still allowed. An agent that parks for 8 hours on a draft-PR push is wasting time on a safe operation.

### When to plan vs when to code

```
IF plan has [in_progress] task:
  -> Resume it (a prior session died mid-task)
  -> Verify, then set to [completed] or [blocked]

ELIF plan has [pending] tasks with evidence:
  -> Set first [pending] to [in_progress], execute, verify, checkpoint

ELIF plan has [pending] tasks without evidence:
  -> Gather evidence, update plan with citations, checkpoint (no code)

ELIF plan is empty or missing:
  -> Research, synthesize into initial PLAN.md, checkpoint (no code)

ELIF all tasks are [completed]:
  -> Verify final state. Mark mission complete.
```

### Queue order

Tasks are processed top-to-bottom with these rules:

1. **[in_progress] always resumes first** -- a prior session died mid-task
2. **Dependencies resolve before dependents** -- `[Depends: Task N]` blocks until N is `[completed]`
3. **[pending] tasks run top-to-bottom** -- the first eligible task wins
4. **[P] tasks may run in parallel** -- up to 4 concurrent agents, one point guard
5. **No reordering mid-cycle** -- to change priority, update the plan with a Decision Log entry

### Checkpoint format

Every cycle ends with a checkpoint commit and a Progress entry:

```
vidux: [what you did]
```

Progress entry: `- [DATE] What happened. Next: what's next. Blocker: if any.`

Reconcile planned vs actual: compare what the plan SAID with what the git diff SHOWS. If they diverge, update the plan and add a Surprise entry. The plan always reflects truth.

---

## PLAN.md Template

**Every project has exactly ONE PLAN.md.** Course corrections — even dramatic pivots — update the existing plan's Decision Log. They do NOT spawn a sibling plan store. If you catch yourself justifying a new plan with phrases like "clean slate," "emotional separation," or "this rewrite deserves its own home," stop: that's fabricated reasoning. The correct move is to open the existing PLAN.md, add a `[DIRECTION]` entry to the Decision Log, mark now-obsolete tasks `[blocked]` with a pointer to the new direction, and append the new direction as fresh `[pending]` tasks in the same queue. New plan stores are for new PROJECTS (different codebase, different product, different problem surface), not for new OPINIONS about how the same project should look. "Rewrite resplit-web from scratch" and "polish resplit-web" are the same project — one plan. "Build a new iOS app for Resplit 2.0" and "ship resplit-web" are different projects — different plans.

Planning itself can happen in Claude's main thread (planning is taste, not delegation — per `/vidux-codex`). What matters is WHERE the output lands: the existing PLAN.md for the project, always.

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

### The Decision Log prevents loops

Stateless agents have no memory of WHY a previous agent made a choice. Without a Decision Log, an agent that finds "missing" code will re-add it, undoing a deliberate deletion. The Decision Log is the lock file: agents read it before acting and never contradict an entry.

---

## Every agent is a worker

There is no scanner/writer split for the **writer role**. Every writer finds work AND does work. A writer that only observes and reports is a parked car with the engine running. (The Observer Pair pattern below is the one intentional exception: a separate read-only auditor paired WITH a writer — not a standalone observer running alone.)

When the queue is empty, agents don't exit -- they look for work:

1. Check INBOX.md for unprocessed findings
2. Scan the codebase for issues in their owned paths
3. Check git log for recent changes that may need follow-up
4. Recheck blocked tasks for resolved blockers

If any scan finds work: add it to the plan as a `[pending]` task, then execute it. If all scans come up clean: checkpoint and exit. An agent that exits without looking is not done -- it's lazy.

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

## Automation is platform-specific (see companion skills)

Vidux is a **discipline**, not an automation system. The cycle (READ → ASSESS → ACT → VERIFY → CHECKPOINT), the PLAN.md structure, the investigation template, the Decision Log, the five principles — all work whether the agent is a human, a one-shot AI session, or a cron-scheduled worker. Nothing in this skill prescribes a runtime.

The automation layer — how work actually fires on a schedule, how workers persist across restarts, how garbage collection handles session state, how observers audit writers, how heavy reads get delegated to a second model — is **platform-specific** and lives in the companion skills:

- **`/vidux-claude`** — Claude Code automation. `CronCreate` lanes, `~/.claude-automations/<name>/{prompt.md,memory.md}` convention, 24/7 fleet operating model (lanes persist on disk, sessions cycle), session GC via `session-prune.py`, the "how many lanes per assignment?" decision tree, and the 6-lane hard cap. This is the opinionated runtime for Leo's fleet.
- **`/vidux-codex`** — Codex automation. `codex exec` Mode A (research, compressed summary) and Mode B (implementation, diff review), Framing B cost math (Claude metered / Codex unlimited), observer lane setup (read-only Codex audits offset from the writer), and the delegation decision tree.

**Two patterns worth naming** even though their mechanics live in the platform skills:

1. **The observer pair.** Every long-running writer benefits from a read-only auditor that reads the writer's PLAN.md, Progress log, and memory fresh each cycle. The writer can't self-audit — it shares the worldview that produced the error. An independent reader catches wrong-flag invocations, non-chronological Progress entries, queue FSM violations (e.g., a task flipping to `[completed]` without passing through `[in_progress]`), and strategic drift after the queue closes. **Verdicts:** `SHIPPING | IDLE | WARNING | BLOCKED | CRASHED`. **How to create one:** platform-specific — see `/vidux-claude` or `/vidux-codex`.

2. **Delegation for heavy reads or code writes.** If a worker's READ step pulls more than ~3 KB of source each cycle, or if a task needs substantial code writing with a clear spec, hand the grunt work to a second model and consume only the summary or diff. The decider stays the primary model; the executor does the grinding. **Mechanics:** platform-specific — see `/vidux-codex` for the Mode A / Mode B contract.

Both patterns are **optional** for a vidux worker. A human following the five principles alone is doing vidux correctly. Adding observers and delegation is the production upgrade for long-running autonomous work — the platform skills tell you exactly how.

---

## Activation

Vidux activates when:
- User says `/vidux` or describes work spanning multiple sessions
- An existing PLAN.md governs the work
- Pilot routes into it after detecting expedition-scale work

Vidux does NOT activate for:
- Single-file changes with obvious cause
- Anything that takes less than 30 minutes with a clear root cause
