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

When 2+ tickets touch the same surface, bundle them into one investigation. The investigation produces a root cause analysis, an impact map, and a fix spec. Investigation notes live locally in the working tree until the fix ships — they are not a separate deliverable. No investigation PR, no evidence PR, no plan-flip PR. The unit of progress is code change.

### 4. Self-extend with a brake

Agents add tasks they discover. When you fix a bug, log the related bugs you saw. When you add a feature, log the edge cases you spotted.

But a shipped surface that works is done -- stop polishing and move to the next gap. If overall mission has gaps elsewhere, polish on a done surface is procrastination. Only re-extend plans when investigation reveals new surfaces, not when you find one more thing to tweak on a surface you already finished.

**If evidence changes mid-cycle, the queue re-sorts.** Observed user behavior, a failing deploy, a new PR comment — any of these can reorder what's next. You don't need permission to reorder. Note the reorder in the next Progress entry so future agents see the why.

### 5. Prove it mechanically

Never assert "it works." Run the build, run the tests, show the screenshot. Definition of done for UI work is a visual proof, never just "the build passes."

When an audit or grep produces a count or classification, **spot-check at least one entry from each category** before making decisions on it. A grep hit is not a fact -- it's a lead. A line matching "git push" might be a prohibition ("NEVER git push"), not an instruction. An automation classified as "push-capable" might operate on a non-git directory. Validate before you plan; plan before you code.

After a failure, produce two artifacts: a code fix (the immediate repair) and a process fix (a hook, a test, a constraint, a plan update). The process fix is the valuable output -- it makes the system smarter for next time.

**Progress is code change.** A PR that only touches `PLAN.md`, `investigations/`, `evidence/`, or `INBOX.md` without a source-code change is not progress — it's bookkeeping. Bundle plan updates into the code PR that ships the fix, or keep the notes local until a fix is ready. Standalone "flip row to [completed]", "reconcile Phase N", "audit already-delivered", or "investigation closeout" PRs are prohibited. If a cycle produces no code, it produces no PR and no commit — the notes stay on disk for the next cycle to pick up.

---

## The Cycle

Every work session follows this loop:

```
READ       -> PLAN.md, INBOX.md, git log, git diff (uncommitted work?)
ASSESS     -> Resume [in_progress] first, else pick highest-impact unblocked task.
             No evidence? Gather it locally before coding. Empty plan? Research first.
ACT        -> Execute tasks until queue empty, blocker, or context budget.
             Empty queue? Scan INBOX, owned paths, git log, blocked tasks. Anything
             found becomes [pending] and runs this cycle. Nothing found? Checkpoint and exit.
VERIFY     -> Build, test, gate
CHECKPOINT -> Commit as `vidux: [what you did]` + Progress entry.
             Reconcile planned vs actual; update plan if they diverge.
```

**Crash recovery:** If `git diff` shows uncommitted work from a dead session, commit it first: `vidux: recover uncommitted work from crashed session`.

**Stuck detection (adaptive):** If the same task appears in 3+ Progress entries while still `[in_progress]`, stop retrying. Force a surface switch — move to the next unblocked task and mark the stuck one `[blocked]` with a one-line Decision Log entry explaining what was tried. No human hand-off required; the next cycle either finds new evidence that unblocks it (via observed signal, new PR comment, or queue re-sort) or the task stays blocked until replaced. Polish is fractal — the brake is what prevents forever-loops, not a human approval gate.

**Push authorization:** Draft PRs are always safe to push — push the branch and `gh pr create --draft` without asking. Direct-to-main or destructive operations (force push, branch delete, `git reset --hard`) require explicit authorization. A lane prompt that says "NEVER push" without qualification still allows draft PRs; parking on a safe draft-PR push wastes cycles.

### Queue order

Tasks are processed with these rules:

1. **[in_progress] always resumes first** -- a prior session died mid-task
2. **Dependencies resolve before dependents** -- `[Depends: Task N]` blocks until N is `[completed]`
3. **Pick the highest-impact unblocked task** -- strict FIFO is the default, but re-sort when new `[Source: observed]` evidence or a Decision Log entry changes priority. Note the reorder in the next Progress entry; you don't need permission to reorder.

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
- [Source: observed] "flicker on launch in TestFlight build 990" (user-observed behavior is first-class evidence)

## Constraints
- ALWAYS: [things that must be true]
- NEVER: [things that are forbidden]

## Tasks
Ordered, with status tags, evidence citations, and — for pending + in_progress — a mandatory `[ETA: Xh]` tag.
- [pending] Task 1: description [Evidence: ...] [ETA: 0.5h]
- [in_progress] Task 2: description [Evidence: ...] [ETA: 2h]
- [completed] Task 3: description [Evidence: ...]
- [blocked] Task 4: description [Blocker: ...]

Inside ## Tasks, every line starting with `- ` MUST be a task with a
status tag. Use numbered lists (1. 2. 3.) or headers for non-task
content like rollout strategies or phase preambles.

Status FSM: pending -> in_progress -> [in_review] -> completed
                              │                │
                              └───> blocked <───┘  (orthogonal tag on any active
                                                    state — an item can be
                                                    [in_progress] + blocked
                                                    simultaneously; set via a
                                                    separate Blocked field /
                                                    label, not by column move)

`in_review` is optional — use it when a task has a PR awaiting merge + CI +
review-bot acks. Skip it for docs, config, or plan-only work that never goes
through review. Existing 4-state plans (pending / in_progress / completed /
blocked) remain valid; agents may adopt in_review per-task.

**`[ETA: Xh]` — mandatory AI-hour estimate on pending + in_progress tasks.**
An AI-hour is how much focused AI-agent work a task takes end-to-end, not
wall-clock time. Calibration: 0.25h trivial / 0.5h simple fix / 1h small
feature / 2h moderate / 4h e2e bug / 8h+ multi-phase (promote to compound).
ETAs are elastic — when scope moves, log the revision in `## Decision Log`
and update the tag. `/vidux-status` sums pending + in_progress ETAs to show
remaining AI-hours per plan. Completed + blocked tasks don't need an ETA
(they're terminal for this calibration). Adding a new `[pending]` task
without `[ETA: Xh]` is a plan defect — fill it in before checkpoint.

## Decision Log
Intentional choices that future agents must not undo.
- [DELETION] [date] Removed X. Reason: Y. Do not re-add.
- [DIRECTION] [date] Chose X over Y. Reason: Z.

## Progress
Living log updated each cycle. Unexpected findings, concerns noted during
execution, and reorder notes all live here — no separate Surprises or Open
Questions section. If a finding needs a task, promote it to a task.
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

### When a task needs an investigation (the only nesting vidux allows)

Some tasks are atomic — one PR, clear diff. Others are messy: unclear root cause, 3+ files in play, you need to think before you touch code. For those, the parent plan task delegates its deep work to a child investigation file:

```markdown
- [in_progress] Task 3: Fix payment flow [Investigation: investigations/payment-flow.md]
```

That's the entire nesting model. One parent plan, one child investigation per compound task. No deeper nesting. If you need a third level, split into two separate parent plans instead.

**How it works:**

1. **You write the investigation file first.** `investigations/payment-flow.md` has seven sections, filled bottom-up:

   ```
   ## Reporter Says    — exact quote from feedback
   ## Evidence         — files, related tickets, repro steps
   ## Root Cause       (pending)
   ## Impact Map       (pending)
   ## Fix Spec         (pending)
   ## Tests            (pending)
   ## Gate             (pending)
   ```

2. **The parent task stays `[in_progress]`** while the investigation is active. Each cycle fills one `(pending)` section. No PR opens during investigation — the sections live on disk.

3. **The fix ships with the investigation, as one commit.** When Fix Spec + Tests + Gate are all done, the code lands and the parent task flips `[completed]`:

   ```
   - [completed] Task 3: Fix payment flow [Investigation: investigations/payment-flow.md]
     [Fix: src/checkout/submit.ts:42, src/checkout/retry.ts:18] [Shipped: <commit sha>]
   ```

4. **The investigation file stays forever.** It's the historical record of *why* the fix looks the way it does. Future agents who touch the same surface read it before acting. Archived by age (180+ days), never by "task done."

**Four rules the example illustrates:**

1. **No Fix Spec = no PR.** Investigation file lives on disk until the Fix Spec is filled AND the code ships.
2. **Parent status follows child status.** Parent task can't flip `[completed]` while the investigation has any `(pending)` section.
3. **Decision Log stays in the parent PLAN.md.** The investigation captures *why this bug happened*; the parent Decision Log captures *why we fixed it this way*.
4. **When in doubt, don't nest.** A plain task with clear evidence doesn't need an investigation. Reserve nesting for surfaces that genuinely have a root-cause question.

### vidux.config.json (where plans live)

One optional config file at the repo root controls plan discovery:

```json
{
  "plan_store": {
    "mode": "local",
    "path": "~/Development/vidux/projects"
  }
}
```

- `mode: "inline"` — plans live in the current repo as `PLAN.md`. Default when no config is present.
- `mode: "local"` — plans live at the configured `path` (one subdir per project). Useful when you want plans tracked in a separate git repo synced across machines.
- `mode: "external"` — same as local but path may point outside `~/Development`.

Agents read `vidux.config.json` at session start and resolve the authority PLAN.md from the config before anything else.

### External boards (adapter plugins)

vidux supports external kanban boards (GitHub Projects, Linear, Asana, Jira, Trello) as first-class inbox sources via a plugin adapter architecture. PLAN.md stays the source of truth; the external board is a view + input surface that round-trips through `scripts/vidux-inbox-sync.py`.

Opt-in. Empty `inbox_sources: []` (the default) keeps vanilla vidux unchanged. Populate the array to enable one or more adapters:

```json
{
  "plan_store": { "mode": "local", "path": "~/Development/vidux/projects" },
  "inbox_sources": [
    {
      "adapter": "gh_projects",
      "enabled": true,
      "config": {
        "owner": "<you>",
        "project_number": 3,
        "token_file": "~/.config/vidux/gh-project.token",
        "status_field_name": "Status",
        "column_mapping": { "pending": "Backlog", "in_progress": "Dev", "in_review": "QA/Testing/Review", "completed": "Prod/Shipped" },
        "blocked_field_name": "Blocked",
        "blocked_linked_label_fallback": "blocked",
        "field_mapping": {
          "Evidence":      { "project_field": "Evidence",      "type": "TEXT"   },
          "Investigation": { "project_field": "Investigation", "type": "TEXT"   },
          "ETA":           { "project_field": "ETA",           "type": "NUMBER" },
          "Source":        { "project_field": "Source",        "type": "TEXT"   }
        }
      }
    }
  ]
}
```

See `vidux.config.example.json` at the repo root for a live block you can copy.

**Adapter contract.** Each adapter subclasses `AdapterBase` at `~/Development/vidux/adapters/base.py` and implements six methods: `fetch_inbox` (external items → `list[ExternalItem]`), `push_task` (`PlanTask` → opaque `external_id`), `pull_status` / `push_status` (column ↔ vidux FSM), `pull_fields` / `push_fields` (custom fields like Evidence / ETA / Source). Adapters self-register via the `@register` decorator at import time; `get_adapter(name)` resolves the class.

**Sync script.** `scripts/vidux-inbox-sync.py` walks every PLAN.md under `plan_store.path`, diffs tasks against each enabled adapter's external state, and:

- **PULL** — novel external items append to `INBOX.md` as `- [live-feedback] <title> [Source: <adapter>:<id>]` entries (idempotent — marker-based dedupe). External items whose status lands in `completed` auto-flip the corresponding PLAN.md task to `[completed]`.
- **PUSH** — unmapped `[pending]` / `[in_progress]` tasks create via `push_task`; mapped tasks receive `push_status` (column move) + `push_fields({'_blocked': ...})` for the orthogonal blocked flag.
- Flags: `--dry-run` skips writes; `--direction={push,pull,both}` gates the halves; `--json` emits a machine-readable summary; exit codes `0/2/3` for success / config-error / adapter-error.

Per-plan sidecar `.external-state.json` stores the `task_id ↔ external_id` map per adapter. Lives inside the plan directory; gitignore the plan tree to keep it private.

**Blocked is orthogonal.** Status column represents pipeline state; the `Blocked` field is a separate flag. An item can be `[in_progress]` AND blocked simultaneously without losing pipeline position. Adapters MUST reject `push_status(BLOCKED)` — callers write `Blocked=Yes` via `push_fields({'_blocked': True})`.

**Writing a new adapter.** See `~/Development/vidux/adapters/README.md` for the 6-step authors guide + 5-step round-trip rubric (push seed, pull status change, custom-field round-trip, blocked orthogonality check, idempotency). Current fleet: `gh_projects` live; `linear` / `asana` / `jira` / `trello` shipped as stubs (`NotImplementedError`) with per-platform auth + API docstrings — subclass-ready when a real integration is needed.

### Inbox

`INBOX.md` is where humans or external tools drop findings for agents to act on:

- Agents check INBOX.md during READ, before looking at tasks
- Promote actionable findings to `[pending]` tasks in PLAN.md
- Annotate non-actionable ones with `[SKIP: reason]`
- Max 20 entries. If full, oldest are archived to `evidence/`.

### Garbage collection

Plan GC is **mechanical, not vibes-based**. "Feels heavy" doesn't fire; thresholds do. Run from the plan dir (or pass it as an arg):

```bash
python3 ~/Development/vidux/scripts/vidux-plan-gc.py [--dry-run] [--json] [plan-dir]
```

Three operations, one script:

| Target | Rule | Where archived |
|---|---|---|
| `[completed]` tasks in `## Tasks` | Soft cap 30 → archive oldest to 20. Hard cap 50 → archive + exit 2 (coordinator gate). | `ARCHIVE.md` (append-only, timestamped). |
| `investigations/*.md` | mtime ≥ 180 days | `investigations/archive/` (moved, not deleted). |
| `INBOX.md` | Soft cap 20 → drop oldest | `evidence/YYYY-MM-DD-inbox-archive.md`. |

**What stays forever:** `[pending]`, `[in_progress]`, `[blocked]` tasks; the Decision Log; the Progress log (up to the lane's own discretion). Archived investigations remain on disk; the archive subdir is the record.

**When to run:** coordinator lanes include `vidux-plan-gc.py` in their READ step each cycle. `--dry-run` + `--json` gives a pre-check; the live run is idempotent (no-op under caps).

**Exit 2** (hard cap exceeded) is the gate signal: coordinators should hold ACT and loudly note the bloat in the next checkpoint — the plan structurally needs attention beyond archival (too many tasks completed without being split into phases, or Phase rollover is overdue).

---

## Course Correction

The plan is a living document. When evidence changes, the plan changes. When the plan changes, the work changes.

When something breaks or changes:

1. **Update the plan FIRST** -- what changed, why, what's the new direction
2. **Then update the code** -- derived from the new plan state
3. **Every failure produces a process fix** -- not just a code fix

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

If the Fix Spec is missing, notes stay local. The investigation ships with the fix, not ahead of it.

---

## Beyond Core — Automation and Recipes

Everything above is **core vidux** — the five principles, the cycle, the PLAN.md template, investigations, course correction. It works for humans, one-shot AI sessions, and cron-scheduled workers alike. A human following core alone is doing vidux correctly.

If your work needs more, two companion surfaces carry the rest:

- **[`guides/automation.md`](guides/automation.md)** — the 24/7 fleet operating model, session-gc, lane management, subagent delegation, lane bootstrap. Load this when you run lanes on a schedule.
- **[`guides/recipes/`](guides/recipes/)** — opt-in tactics and patterns. CLAUDE.md rules, lane prompt templates, subagent dispatch, evidence discipline, proactive work surfacing, visual-proof requirements, and more. Load a specific recipe on demand.

**Codex automation default:** when creating a new automation from Codex, assume `Run in: Chat`. Do not default to `Worktree` or `Local` unless the user explicitly asks for repo-bound execution or the task cannot be done from chat.

Neither surface overrides core vidux. Core is opinionated machinery; automation and recipes are opt-in layers.

---

## Activation

Vidux activates when:
- User says `/vidux` or describes work spanning multiple sessions
- An existing PLAN.md governs the work
- Pilot routes into it after detecting expedition-scale work
- User asks to create or manage a lane/automation/cron (load `guides/automation.md` alongside)

If the automation is being created from Codex, default it to Chat execution unless the user explicitly asks for Worktree or Local.

Vidux does NOT activate for:
- Single-file changes with obvious cause
- Anything that takes less than 30 minutes with a clear root cause
