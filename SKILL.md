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
READ       -> git fetch --prune (kill stale tracking refs first),
              PLAN.md, INBOX.md, git log, git diff (uncommitted work?),
              vidux-worktree-gc.py --base origin/main before new worktrees.
ASSESS     -> Resume [in_progress] first, else pick highest-impact unblocked task.
             No evidence? Gather it locally before coding. Empty plan? Research first.
ACT        -> Execute tasks until queue empty, blocker, or context budget.
             Empty queue? Scan INBOX, owned paths, git log, blocked tasks. Anything
             found becomes [pending] and runs this cycle. Nothing found? Checkpoint and exit.
VERIFY     -> Build, test, gate
CHECKPOINT -> Commit as `vidux: [what you did]` + Progress entry.
             Reconcile planned vs actual; update plan if they diverge.
COMPLETE   -> Close the local worktree lifecycle or record why it remains.
```

**Crash recovery:** If `git diff` shows uncommitted work from a dead session, commit it first: `vidux: recover uncommitted work from crashed session`.

**Stuck detection (adaptive):** If the same task appears in 3+ Progress entries while still `[in_progress]`, stop retrying. Force a surface switch — move to the next unblocked task and mark the stuck one `[blocked]` with a one-line Decision Log entry explaining what was tried. No human hand-off required; the next cycle either finds new evidence that unblocks it (via observed signal, new PR comment, or queue re-sort) or the task stays blocked until replaced. Polish is fractal — the brake is what prevents forever-loops, not a human approval gate.

**Push authorization:** Operational PRs are always safe to push without asking. Open them ready-for-review by default so configured review bots can run; use draft only for true WIP with a missing gate. Direct-to-main or destructive operations (force push, branch delete, `git reset --hard`) require explicit authorization. A lane prompt that says "NEVER push" without qualification still allows a normal PR push; parking on a local branch wastes cycles.

**Worktree lifecycle:** Before starting new lane work or leaving a branch behind, run `python3 ~/Development/vidux/scripts/vidux-worktree-gc.py --base origin/main <repo>`. `merged_clean` is the only automatic cleanup bucket. `open_pr` is durable handoff and must be nursed or recorded. `dirty`, `closed_unmerged`, and `unmerged_no_pr` are not cleanup; they require inspect/stash/commit/escalate, PR creation, absorption, or an explicit abandoned note. A task is not done while its work exists only as unrecorded local worktree state.

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
Ordered, with status tags and evidence citations. Completion (X/Y tasks done)
is the headline. `[ETA: Xh]` is optional — useful when tasks are similar-sized,
skip when they vary in difficulty.
- [pending] Task 1: description [Evidence: ...] [ETA: 0.5h]
- [in_progress] Task 2: description [Evidence: ...]
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

**`[ETA: Xh]` — optional AI-hour estimate.** Completion (X/Y tasks done) is
the headline; ETA is supplementary. Use it when tasks in a plan are
similar-sized and the sum gives a meaningful "AI-hours remaining" read; skip
it when tasks vary in difficulty and the sum becomes fiction. An AI-hour is
how much focused AI-agent work a task takes end-to-end, not wall-clock time.
Calibration when you do tag (still useful for the tasks that get one):
0.25h trivial / 0.5h simple fix / 1h small feature / 2h moderate / 4h e2e
bug / 8h+ multi-phase (promote to compound). ETAs are elastic — when scope
moves, log the revision in `## Decision Log` and update the tag.
`/vidux-status` sums whatever ETAs are present on pending + in_progress
tasks; the sum is informational, not a contract. Completed + blocked tasks
don't need an ETA (they're terminal for this calibration).

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

**Leo fleet primacy (2026-04-24).** Across Leo's repos (`strongyes-web`, `resplit-web`, `leojkwan`, plus local plan_store at `~/Development/vidux/projects/`), GitHub Projects is the **primary work-planning surface** — not PLAN.md alone. Leo drops new asks directly onto a GH Project card; agents sync cards back into PLAN.md via the `pull` half, then execute against PLAN.md. The GH Project board is the "front door" for non-code collaborators (Leo, Nicole) to feed work into the fleet without touching markdown.

Fleet wiring:
- `leojkwan/projects/3` (**"vidux-ext"** / `PVT_kwHOAJyhO84BVg10`) — wired to `strongyes-web/vidux/*` via `strongyes-web/vidux.config.json` → `inbox_sources[0]`
- `leojkwan/projects/4` (**"resplit-web vidux backlog"** / `PVT_kwHOAJyhO84BVmKZ`) — wired to `resplit-web/vidux/*` via `resplit-web/vidux.config.json`

When agents pick up work in a fleet repo, they should:
1. Fetch the wired GH Project's `Dev` column via `gh project item-list` to see what's actively in-flight
2. Read PLAN.md for the source-of-truth status (the board is a read-mostly mirror; PLAN.md is canonical)
3. If the board has items the PLAN.md doesn't, run `python3 ~/Development/vidux/scripts/vidux-inbox-sync.py --direction=pull` to promote them to `INBOX.md`
4. Push newly-added PLAN.md tasks with `--direction=push` during checkpoint so Leo sees what shipped on the board too

**Always-on fleet sync cron** (`~/bin/vidux-fleet-sync`, LaunchAgent `com.leokwan.vidux-fleet-sync`, cadence :00 :15 :30 :45). Runs `--direction=both` against every repo in `FLEET_REPOS` (currently `strongyes-web`, `resplit-web`). Pure python, no Claude CLI, ~2s per fire. Per-run cost: 2 metadata loads + 2 `gh project item-list` calls (the adapter caches the board read for the instance's lifetime — critical since the sync iterates 40+ plan_dirs against the same adapter per run). State at `~/.agent-ledger/vidux-fleet-sync.{state,log}`. Inspect via `vidux-fleet-sync --status`. Uninstall via `--uninstall`.

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
- **AUTO-PROMOTE** — opt-in via `auto_promote_target` (relative or absolute path) on each `inbox_sources[]` entry. When set, novel cards skip INBOX and land directly in the named plan_dir's PLAN.md as `- [pending] BD-<seq>: <title> [Source: <adapter>:<id>]` tasks. `BD` = "board-dropped" (per-plan namespace, sequence minted from `_next_bd_seq`). Idempotency uses BOTH the state file mapping AND in-text `[Source:]` marker scan, so a state-file loss during git races (rebase + stash drop) cannot cause re-promotion. Missing targets fail closed; vidux refuses to fall back to INBOX because that would route work to the wrong lane and re-enable pushes for import-only sources.
- **PR sweep** — opt-in via `--include-prs`. Sweeps `gh pr list` open + recently-merged PRs from the repo containing the config and adds open PRs to the bound GH Project as items linked via `addProjectV2ItemById`. Status follows PR state: open-draft→Dev, open-ready→QA-Review, merged→Prod-Shipped. Already-tracked PRs reconcile status. Merged PRs that were never on the board are NOT backfilled (avoids flooding Backlog with shipped history).
- Flags: `--dry-run` skips writes; `--direction={push,pull,both}` gates the halves; `--include-prs` enables PR sweep; `--repo-dir` overrides repo for PR list source; `--json` emits machine-readable summary; exit codes `0/2/3` for success / config-error / adapter-error.

Per-plan sidecar `.external-state.json` stores the `task_id ↔ external_id` map per adapter. Lives inside the plan directory; gitignored. **Race-recovery rule:** if you `git stash push -u` (which captures the gitignored state file as untracked) and then `git stash drop` instead of `pop`, the state file is permanently lost and the next cron tick will see all already-tracked items as "novel." The in-text `[Source:]` marker safety net catches this for auto-promote, but PUSH still trusts the state file. Mitigation: always `git stash pop` (not drop) after a rebase that captured the sidecar.

**Blocked is orthogonal.** Status column represents pipeline state; the `Blocked` field is a separate flag. An item can be `[in_progress]` AND blocked simultaneously without losing pipeline position. Adapters MUST reject `push_status(BLOCKED)` — callers write `Blocked=Yes` via `push_fields({'_blocked': True})`.

**Writing a new adapter.** See `~/Development/vidux/adapters/README.md` for the 6-step authors guide + 5-step round-trip rubric (push seed, pull status change, custom-field round-trip, blocked orthogonality check, idempotency). Current fleet: `gh_projects` and `linear` are live; `asana` / `jira` / `trello` ship as stubs (`NotImplementedError`) with per-platform auth + API docstrings — subclass-ready when a real integration is needed.

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

Worktree GC is separate from plan GC. It classifies local git worktrees by branch/PR state before removing anything:

```bash
python3 ~/Development/vidux/scripts/vidux-worktree-gc.py --base origin/main [repo-dir]
```

Read-only is the default. `--apply --yes` removes only `merged_clean` worktrees: clean non-primary worktrees whose branch is already merged into the base or whose PR is merged. Dirty worktrees, open PRs, closed-unmerged PRs, and no-PR unmerged branches are reported but never removed automatically.

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

## Replaces /superpowers (folded 2026-04-26)

The Anthropic `superpowers` plugin used to provide 14 process-discipline subskills that auto-loaded on relevant triggers (brainstorming, TDD, debugging, code review, parallel agents, worktrees, etc.). All of those concepts are already covered by core vidux and its companion skills — having both was redundant ("if vidux is supposed to be my superpower"). The plugin is uninstalled. Use this routing table when you'd previously have reached for a `/superpowers:*` skill:

| `/superpowers:*` was for | Use this instead |
|---|---|
| `brainstorming` (before any creative work) | Vidux Principle 1: plan first. Brainstorm in main thread, then write the PLAN.md before code. Quick brainstorms can stay in chat — only formalize when the work spans 30+ minutes. |
| `writing-plans` | Vidux core — `## PLAN.md Template` section above |
| `executing-plans` | Vidux Cycle (READ → ASSESS → ACT → VERIFY → CHECKPOINT) |
| `subagent-driven-development` | `guides/automation.md` § subagent dispatch + `/auto` § auto-dispatch protocol |
| `dispatching-parallel-agents` | `guides/automation.md` § parallel agents (surface-disjoint precondition) + `/auto` § fan-out rule |
| `test-driven-development` | Vidux Principle 5: prove it mechanically. Write the assertion before the implementation when the surface needs regression protection (per `/auto` E-row "visual proof merge gate") |
| `systematic-debugging` | Vidux Principle 3: investigate before fixing. Use the `## Investigation Template` for any bug touching 2+ tickets or unclear root cause |
| `requesting-code-review` / `receiving-code-review` | `/vidux-leo` § review-bot ack discipline (Graphite / Greptile / Cursor / Seer yay-or-nay before merge) |
| `verification-before-completion` | Vidux Principle 5: prove it mechanically. UI work definition-of-done = visual proof per `/auto` E-row |
| `using-git-worktrees` | `/vidux-leo` § worktree isolation + `/bigapple` § per-lane DerivedData |
| `finishing-a-development-branch` | `/vidux-leo` § merge-timing rubric (ready-PR auto-merge once review-bots ack) |
| `writing-skills` | Use `/captain` — owns skill creation, registry, and symlink hygiene |
| `using-superpowers` (meta loader) | Removed — vidux loads when you say `/vidux` or describe expedition-scale work; `/auto` loads when you're tempted to ask Leo something operational |

**Rule of thumb:** if you'd reach for a `/superpowers:*` skill, you're already inside `/vidux`'s domain. Read the relevant principle / cycle step / guide instead of summoning a separate plugin.

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

---

## Browser

A localhost web UI for viewing every PLAN.md across the fleet at a glance. Read-only — the source of truth is still the markdown file in git.

```
vidux-browse              # start server, open http://127.0.0.1:7191
vidux-browse --no-open    # start server without opening
vidux-browse -f           # foreground (stream logs)
```

What it shows:
- Sidebar grouped by repo, with hot/stale/cold pills (≤7d / 7-30d / >30d by mtime)
- Selected plan rendered as markdown, with sibling tabs for `PROGRESS.md` / `INBOX.md` / `ASK-LEO.md` when present
- Filter box to search across repo / slug / purpose

Discovery globs (covers the three conventions in use across the fleet):

- `<repo>/ai/plans/<slug>/PLAN.md`
- `<repo>/vidux/<slug>/PLAN.md`
- `<repo>/projects/<slug>/PLAN.md`
- `<repo>/PLAN.md` (root-level)

Stack: Python stdlib `http.server` + plain HTML/CSS + vanilla JS + `marked.js` from CDN. Zero pip dependencies. Default bind is `127.0.0.1`; `VIDUX_BROWSER_HOST=0.0.0.0` enables trusted-LAN read access for Moussey-style home dashboards.

Code lives at `~/Development/vidux/browser/`. See `projects/vidux-browser/PLAN.md` for design decisions and the v1/Polish roadmap (sessions panel, ledger entries, memory viewer, launchd auto-start).

### Ad-hoc artifacts (anytime, anywhere in chat)

The browser has a second surface beyond plan-viewing: ad-hoc HTML artifacts that any agent can drop in from any session. They appear in a top-level "ARTIFACTS" section in the sidebar (above the repo-grouped plans), decoupled from any specific plan.

**Two ways to drop an artifact:**

```bash
# Option 1 — file write (works from any shell)
cat > ~/Development/vidux/browser/artifacts/<slug>.html

# Option 2 — POST endpoint (works from any session with HTTP, no shell needed)
curl -X POST http://127.0.0.1:7191/api/artifact \
  -H "Content-Type: application/json" \
  -d '{"slug":"<slug>","html":"<!DOCTYPE html>..."}'
```

**Slug rules** (POST-validated): `^[a-z0-9][a-z0-9-]{0,63}$`. Lowercase, dashes only, no slashes, no `..`. Same slug overwrites.

**Component CSS shim** — to inherit the paper-and-ink palette in your artifact, use these classes (defined in `static/style.css`):

- `.card-grid` — auto-fill grid container, 280px min column
- `.contact-card` — bordered card with padding; nests `<h3>`, `.meta`, `<a>`, `<p>`
- `.pill .pill-hot/.pill-stale/.pill-cold/.pill-artifact` — status dots
- `.lead-row` — single-row list item with name + tier
- `.person-chip` — pill-shaped inline tag
- `.label` — uppercase mono label (e.g., `<span class="label">hook</span>`)

Artifacts render via direct `innerHTML` into the same pane that renders markdown, so anything in your `<body>` works. Trust boundary: localhost + your own filesystem; no XSS surface.

**Use cases this enables:**
- Research summaries with vendor / lead / contact cards (vs flat markdown tables)
- Visual fleet dashboards (per-repo status grids)
- One-off briefings to share with yourself across sessions
- Plan-adjacent visualizations (timeline, network graph, decision tree) without bloating PLAN.md

For lanes consuming this surface: drop the artifact, log the URL to memory if you want to reference it later (`http://127.0.0.1:7191/` then click into the slug in the sidebar). The artifact survives across sessions; the slug is the stable handle.

### Local plan notes (loopback-only)

When an agent needs to leave a constrained note for the current Mac's vidux plan, use the local plan-note endpoint. It appends to that plan directory's `INBOX.md`; it does not edit `PLAN.md` directly.

```bash
curl -X POST http://127.0.0.1:7191/api/local-plan-note \
  -H "Content-Type: application/json" \
  -d '{"plan_path":"/Users/leokwan/Development/vidux/projects/moussey/PLAN.md","source":"codex/moussey","agent":"codex/moussey","note":"Short note for the next local agent."}'
```

This endpoint rejects non-loopback clients. Even when vidux-browse is bound to `0.0.0.0` for home-LAN reading, `POST /api/local-plan-note` must be called through `127.0.0.1` or `::1`; other Wi-Fi devices can read but cannot write plan notes.
