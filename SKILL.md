---
name: vidux
description: "Plan-first discipline and universal project router for AI agents. Detects stack, stage, and scale, then either executes directly or shifts into plan-first multi-session work. Write down what you're going to build before you build it. Plans live in markdown files in git. Any agent can pick up where the last one left off."
---

# Vidux

Vidux is a discipline for AI agents: write down what you're going to build before you build it. Plans live in markdown files in git. Agents read the plan, do one piece of work, update the plan, and checkpoint. Any agent can pick up where the last one left off because the plan file is the only state that matters.

---

## Activation & Triage

Vidux is the universal entrypoint. Drop into any repo. Read the room. Run the right lifecycle. At expedition scale, shift into plan-first multi-session work; at smaller scales, execute the stage playbook directly.

### Fast-exit triage (trivial requests stop here)

Before any detection, check if the request is trivially answerable inline. If ANY of these apply, respond with 2-3 options directly in conversation and STOP — do NOT invoke brainstorming, TaskCreate, planning skills, or heavy routing:

- Request is ≤50 words AND names copy/wording/naming work. Keyword triggers: `tagline`, `hero`, `CTA`, `copy`, `wording`, `name`, `naming`, `rename`, `headline`, `subtitle`, `blurb`, `caption`, `alt text`, `commit message`, `title`.
- Request is a single factual question ("what's the flag for X?", "how does Y work?", "where does Z live?").
- Request is a quick refinement on prior output ("make that shorter", "try a different angle", "punchier").

**Why this exists:** routing layers fire before CLAUDE.md "respond directly with 2-3 options" rules. This is the routing-layer enforcement so brainstorming/TaskCreate chains do not spin up for hero-copy or one-line wording asks.

**Who this is NOT for:** expedition-scale work, multi-file changes, anything that would edit production code, or anything framed as "plan first" / "think through" / "design." Those bypass triage and load full vidux.

### When vidux activates

Full vidux loads when:

- User says `/vidux`, `vidux`, `plan first`, `quarter project`, `big project`, or describes work spanning multiple sessions.
- An existing `PLAN.md` (inline, in `vidux.config.json` plan store, or via an enabled adapter) already governs the work.
- User asks to create or manage a lane / automation / cron (load `guides/automation.md` alongside).
- Work touches 5+ files, needs phases, or is multi-session.

### When vidux does NOT activate

- Single-file changes with obvious cause.
- Anything that takes less than 30 minutes with a clear root cause.
- Trivial requests that passed fast-exit triage above.

For requests in between (substantive but small), the stage playbook handles it directly without spinning up a PLAN.md — see `## Stack & Stage Routing` below.

If an automation is being created from Codex, default it to Chat execution unless the user explicitly asks for Worktree or Local.

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

## Working Defaults

Tactical defaults extracted from 30+ plan files across 5 repos. They apply everywhere, regardless of stack or stage.

### Flow with the water

- Read existing code before writing new code.
- Match the repo's patterns, naming, DI approach, test style.
- Don't impose architecture — discover it and extend it.
- If the repo uses Factory DI, use Factory. If it uses manual injection, use that.

### Testability from the start

- Design for test seams before writing implementation.
- Protocol-backed dependencies so mocks are trivial.
- State machines as enums — compiler-enforced, exhaustively testable.
- In-memory containers / mock APIs for isolation.
- Name tests before writing them (TDD slice ordering).

### Close the feedback loop

- Every change must be verifiable by a command you can run.
- Track test counts across sessions (did coverage go up or down?).
- Plans are living documents — update in-place with `[DONE]`, `[NEW]`, dates.
- If a gate is blocked, log: exact command, blocker point, what passed, what's pending.

### Smallest vertical slice

- Model → Service → View → Test, wired end-to-end.
- Ship one slice before starting the next.
- Each slice must compile and pass tests independently.

### DELETE before MODIFY

- When refactoring, remove the old thing first.
- Grep dead-code gates confirm removed symbols are gone.
- Superseded plans get a banner, not silent deletion.
- Deprecated skills redirect to canonical, not deleted.

### No re-ask

- When the user says "do it," execute the full connected scope.
- A11y IDs, tests, docs, lifecycle checks are one deliverable.
- Don't ask permission for obvious follow-through tasks.
- Ship code + tests + verification together.

---

## The Cycle

Every work session follows this loop:

```
READ       -> git fetch --prune (kill stale tracking refs first),
              PLAN.md, INBOX.md, git log, git diff (uncommitted work?),
              vidux-worktree-gc.py --base origin/main before new worktrees.
              Then read the room (checklist below).
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

### Read the Room (READ-phase checklist)

Before touching code, always check these eight surfaces in order:

1. **`AGENTS.md`, `CLAUDE.md`, or equivalent repo instructions** — repo-level instructions override everything.
2. **`ai/skills/hooks/`** — repo-specific build/test/lint commands.
3. **`.cursor/plans/`** — existing plans for this feature or related work.
4. **`RALPH.md`** — repo-owned queue contract for recurring loops and nurse passes.
5. **The ledger** (`.agent-ledger/activity.jsonl`) — recent entries from other agents, active lanes, handoffs waiting.
6. **Memory files** — ownership boundaries, lane assignments.
7. **Neighboring files** — match existing patterns, don't impose new ones.
8. **`vidux.config.json`** — resolve the authority `PLAN.md` and any enabled adapters before anything else.

Ad hoc scratch files (e.g. `<repo>-loop-state.md`) are optional helpers only. They do not override the repo's queue, ledger, or checkpoint files unless the repo explicitly says they are canonical. Never read another repo's queue files, nurse logs, or ledger when selecting work for the current repo.

**Crash recovery:** If `git diff` shows uncommitted work from a dead session, commit it first: `vidux: recover uncommitted work from crashed session`.

**Stuck detection (adaptive):** If the same task appears in 3+ Progress entries while still `[in_progress]`, stop retrying. Force a surface switch — move to the next unblocked task and mark the stuck one `[blocked]` with a one-line Decision Log entry explaining what was tried. No human hand-off required; the next cycle either finds new evidence that unblocks it (via observed signal, new PR comment, or queue re-sort) or the task stays blocked until replaced. Polish is fractal — the brake is what prevents forever-loops, not a human approval gate.

**Push authorization:** Operational PRs are always safe to push without asking. Open them ready-for-review by default so configured review bots can run; use draft only for true WIP with a missing gate. Direct-to-main or destructive operations (force push, branch delete, `git reset --hard`) require explicit authorization. A lane prompt that says "NEVER push" without qualification still allows a normal PR push; parking on a local branch wastes cycles.

### Trunk-First Rule

Vidux defaults to trunk-first:

- Start from the current trunk branch in the canonical repo checkout. Prefer `main`.
- If a repo has not renamed its trunk, detect and use the actual trunk branch instead of forcing a broken assumption.
- Create short-lived branches or worktrees from the current trunk head only when isolation is useful.
- Treat lane branches/worktrees as disposable integration helpers, not as the source of truth.
- Before a job is done, every intended change must be merged or cherry-picked back into trunk in the canonical tree.
- Run the final proof, release gates, and any ship/deploy command from that merged trunk state.
- Do not end a job with required work stranded in a side branch or worktree unless a real external blocker prevents merge-back; if so, record the exact blocker and the exact unmerged branch.

**Worktree lifecycle:** Before starting new lane work or leaving a branch behind, run `python3 ~/Development/vidux/scripts/vidux-worktree-gc.py --base origin/main <repo>`. `merged_clean` is the only automatic cleanup bucket. `open_pr` is durable handoff and must be nursed or recorded. `dirty`, `closed_unmerged`, and `unmerged_no_pr` are not cleanup; they require inspect/stash/commit/escalate, PR creation, absorption, or an explicit abandoned note. A task is not done while its work exists only as unrecorded local worktree state.

**Build/test ownership in multi-agent repos:**

- Treat real build/test execution as a serial lane unless the repo explicitly documents a safe parallel workflow.
- When the ledger shows active parallel lanes, nominate one build owner before starting verification churn.
- If multiple isolated proofs are unavoidable, give each lane its own `-derivedDataPath` and avoid shared package/bootstrap churn.
- If `.mise.toml`, `.tool-versions`, installed CLIs, and skill docs disagree, resolve version authority before trusting command examples.

**Plan discovery before plan creation:** Before opening a new PLAN.md (or kicking off heavy research that would produce one) for any cross-repo lane, `grep -ri <topic-keyword>` across the known plan stores: `~/Development/vidux/projects/`, `~/REDACTED-EMPLOYER-PATH/Dev/<repo>/ai/plans/`, `~/REDACTED-EMPLOYER-PATH/Dev/<repo>/.cursor/plans/`, plus any memory entries referencing existing plans for that surface. Glob hits in `vidux-browse` (sidebar filter box) cover the same ground from the UI. If a same-surface plan exists, append to it; never create a sibling. The 2026-05-22 GetCTRecommendations duplication (a second session rebuilt 5 weeks of receipts and shipped two duplicate placeholder PRs because it skipped this check) is the canonical failure this rule prevents.

**Cross-session collision detection:** When multiple Claude / Codex sessions could be running concurrently against the same repo, check `~/.agent-ledger/activity.jsonl` for recent entries (last ~72h) keyed on the same lane keyword before kicking off heavy research. A second session walking in cold is the highest-risk path to a duplicate plan; a 30-second ledger grep is cheaper than re-discovering the prior session's receipts.

### Queue order

Tasks are processed with these rules:

1. **[in_progress] always resumes first** -- a prior session died mid-task
2. **Dependencies resolve before dependents** -- `[Depends: Task N]` blocks until N is `[completed]`
3. **Pick the highest-impact unblocked task** -- strict FIFO is the default, but re-sort when new `[Source: observed]` evidence or a Decision Log entry changes priority. Note the reorder in the next Progress entry; you don't need permission to reorder.

---

## PLAN.md Template

**Every project has exactly ONE PLAN.md.** Course corrections — even dramatic pivots — update the existing plan's Decision Log. They do NOT spawn a sibling plan store. If you catch yourself justifying a new plan with phrases like "clean slate," "emotional separation," or "this rewrite deserves its own home," stop: that's fabricated reasoning. The correct move is to open the existing PLAN.md, add a `[DIRECTION]` entry to the Decision Log, mark now-obsolete tasks `[blocked]` with a pointer to the new direction, and append the new direction as fresh `[pending]` tasks in the same queue. New plan stores are for new PROJECTS (different codebase, different product, different problem surface), not for new OPINIONS about how the same project should look. "Rewrite project-X from scratch" and "polish project-X" are the same project — one plan. "Build a new iOS app" and "ship the web app" are different projects — different plans.

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

### Two nesting modes

Vidux supports two distinct nesting shapes — pick the one that fits the work:

**1. Investigation (1-level, for compound tasks needing root-cause work)**

Some tasks are atomic — one PR, clear diff. Others are messy: unclear root cause, 3+ files in play, you need to think before you touch code. For those, the parent plan task delegates its deep work to a child investigation file:

```markdown
- [in_progress] Task 3: Fix payment flow [Investigation: investigations/payment-flow.md]
```

One parent plan, one child investigation per compound task. The investigation file lives next to the parent plan and is consumed when the parent task ships.

**2. Sub-plan rollup (N-level, for multi-phase missions with parallel sub-streams)**

For larger missions where multiple sub-streams ship in parallel — each with their own task list — use child PLAN.md files with a Parent backlink at the top:

```markdown
> Parent: vidux/projects/big-mission/PLAN.md
```

or

```markdown
**Parent:** vidux/projects/big-mission/PLAN.md
```

`vidux-browse` parses these backlinks, builds a parent → children tree, and computes recursive aggregate stats so the parent shows BOTH its own progress bar AND a rolled-up bar across every descendant. Sidebar indents children under their parent; cycle-safe via visited-set.

Use this when you have 5+ child plans that meaningfully ship independently (e.g., `T1-*/PLAN.md` through `T9-*/PLAN.md`). Don't use it for trivial nesting where an investigation file would do.

**Choosing between the two:** investigation = "I need to think before I code, for one task." Sub-plan rollup = "this mission has many sub-streams that ship independently and I want a consolidated dashboard." If you're not sure, default to investigation — it's the lower-overhead shape.

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

Other top-level fields (see `vidux.config.example.json` for the canonical schema):

- `version` — config schema version. `"1.0"` is current. Reserved for future schema migrations.
- `external_plan_roots` — optional list of additional absolute paths to scan for `PLAN.md` files. Default `[]`. Useful when plans live in sibling repos outside `plan_store.path`.
- `inbox_sources` — array of adapter configs (see "External boards" below).

Per-adapter optional fields:

- `auto_promote_target` — relative or absolute plan_dir path. Novel external cards land directly there instead of `INBOX.md` (see "External boards").
- `auto_promote_max_new` — cap on novel cards promoted per sync run. Default `25`. Prevents a misconfigured query from flooding a plan with hundreds of issues in one cycle.
- `push_only_for_plans` — optional list of plan_dir paths that opt INTO PUSH for brand-new external issues even when `auto_promote_target` is set. Default empty (all plans suppressed).

Agents read `vidux.config.json` at session start and resolve the authority PLAN.md from the config before anything else.

### External boards (adapter plugins)

vidux supports external kanban boards (GitHub Projects, Linear, Asana, Jira, Trello) as first-class inbox sources via a plugin adapter architecture. PLAN.md stays the source of truth; the external board is a view + input surface that round-trips through `scripts/vidux-inbox-sync.py`.

The checked-in example config (`vidux.config.example.json`) demonstrates a single `gh_projects` inbox source. The live repo config (`vidux.config.json`) enables both `gh_projects` and `linear`, each with its own token file and optional `auto_promote_target`.

When a repo opts into external boards, agents should:
1. Read `PLAN.md` first — it stays canonical even when a board is enabled.
2. Use `python3 scripts/vidux-inbox-sync.py --direction=pull` to promote new external items into `INBOX.md` or the adapter's `auto_promote_target`.
3. Use `python3 scripts/vidux-inbox-sync.py --direction=push` to mirror newly added local tasks back to the external board when the adapter is configured for that direction.
4. Use `--only-adapter <name>` when you want a run scoped to one configured adapter instead of all enabled sources.

The repo does not ship scheduler wrappers for these sync passes; operators decide whether to run one combined `--direction=both` invocation or separate scheduled invocations per adapter.

Keep organization-specific policy out of core. If a team needs concrete board
ids, repo/project maps, review-tool gates, or fleet cadences, put those in a
separate overlay skill or runbook that loads after `/vidux`. Core owns the
adapter contract; overlays own local taste and bindings.

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
- **AUTO-PROMOTE** — opt-in via `auto_promote_target` (relative or absolute path) on each `inbox_sources[]` entry. When set, novel cards skip INBOX and land directly in the named plan_dir's PLAN.md as `- [pending] BD-<seq>: <title> [Source: <adapter>:<id>]` tasks. `BD` = "board-dropped" (per-plan namespace, sequence minted from `_next_bd_seq`). Idempotency uses BOTH the state file mapping AND in-text `[Source:]` marker scan, so a state-file loss during git races (rebase + stash drop) cannot cause re-promotion. Missing targets fail closed; vidux refuses to fall back to INBOX because that would route work to the wrong lane. Auto-promote suppresses creation of brand-new external issues from local-only plan rows, but still pushes status for tasks already linked by `[Source:]`. Linear title-only cards are the exception: they land as `[blocked]` with a blocker asking for description, evidence/source, acceptance or repro, and estimate before any agent can claim them.
  - **Per-plan PUSH opt-in via `push_only_for_plans`** — optional list of plan-dir paths (relative to the config file's parent dir, or absolute) that opt INTO PUSH for brand-new external issues even when `auto_promote_target` is set. Listed plan_dirs get `create_missing_external_tasks=True`; every other plan stays suppressed by the global auto-promote. Canonical use case: specific lane plans opt into PUSH so their tasks become external issues, while the rest of the fleet stays in PULL-only mode and doesn't flood the external board. Default unset = empty list = unchanged behavior (every plan still suppressed by auto-promote).
- **PR sweep** — opt-in via `--include-prs`. Sweeps `gh pr list` open + recently-merged PRs from the repo containing the config and adds open PRs to the bound GH Project as items linked via `addProjectV2ItemById`. Status follows PR state: open-draft→Dev, open-ready→QA-Review, merged→Prod-Shipped. Already-tracked PRs reconcile status. Merged PRs that were never on the board are NOT backfilled (avoids flooding Backlog with shipped history).
- Flags: `--dry-run` skips writes; `--direction={push,pull,both}` gates the halves; `--include-prs` enables PR sweep; `--repo-dir` overrides repo for PR list source; `--json` emits machine-readable summary; exit codes `0/2/3` for success / config-error / adapter-error.

Per-plan sidecar `.external-state.json` stores the `task_id ↔ external_id` map per adapter. Lives inside the plan directory; gitignored. **Race-recovery rule:** if you `git stash push -u` (which captures the gitignored state file as untracked) and then `git stash drop` instead of `pop`, the state file is permanently lost and the next cron tick will see all already-tracked items as "novel." The in-text `[Source:]` marker safety net catches this for auto-promote, but PUSH still trusts the state file. Mitigation: always `git stash pop` (not drop) after a rebase that captured the sidecar.

**Blocked is orthogonal.** Status column represents pipeline state; the `Blocked` field is a separate flag. An item can be `[in_progress]` AND blocked simultaneously without losing pipeline position. Adapters MUST reject `push_status(BLOCKED)` — callers write `Blocked=Yes` via `push_fields({'_blocked': True})`.

**Writing a new adapter.** See `~/Development/vidux/adapters/README.md` for the 6-step authors guide + 5-step round-trip rubric (push seed, pull status change, custom-field round-trip, blocked orthogonality check, idempotency). Current fleet: `gh_projects` and `linear` are live full-round-trip PM adapters; `apple_asc` is live READ-only (parses ASC-style YAML tracker files — see below); `asana` / `jira` / `trello` ship as stubs (`NotImplementedError`) with per-platform auth + API docstrings — subclass-ready when a real integration is needed.

**Apple ASC adapter (read-only feedback-tracker shape).** Apple does not publish a public API for marking TestFlight / ASC beta feedback handled, so the `apple_asc` adapter parses a repo-local tracker file (typically `<repo>/.cursor/plans/app-store-feedback.plan.md`, maintained by `ruby scripts/asc_beta_feedback.rb sync-plan`) and returns each `## Open` row as an `ExternalItem` with `external_id = "asc:<id>"`. The standard `vidux-inbox-sync.py` PULL leg then auto-promotes those items to PLAN.md; pairing with `linear`'s `push_only_for_plans` mechanism gets the same row into a Linear EVE issue end-to-end. `push_task` / `push_status` / `push_fields` raise `NotImplementedError` ("Apple ASC has no public API for marking TestFlight / beta feedback handled; the tracker file is one-way READ-only."). Config schema: `tracker_file` (required path) + `status_filter` (optional list, defaults to `["new", "triaged", "claimed"]`; terminal states `fixed` / `verified` / `archived` are always dropped). See `~/Development/vidux/adapters/README.md` for the full tracker file format + parser tolerances (multi-line continuations, git-conflict markers, missing-file fail-safe).

### Linear extension — full round-trip (PULL + PUSH + CLOSEOUT)

The `linear` adapter (`~/Development/vidux/adapters/linear.py`) supports a complete project-management round-trip: external Linear cards become PLAN.md tasks via PULL; new local tasks become Linear issues via PUSH; status changes flow both directions; agents close issues from PLAN status flips. This is the canonical worked example for the broader adapter contract — Asana / Jira / Trello adapters should follow the same shape.

**PULL** — Linear → PLAN.md:

- New Linear issues in the configured project become `[pending] BD-<seq>: <title> [Source: linear:<issue-id>]` rows in INBOX.md (or auto-promoted to a target plan via `auto_promote_target` in `vidux.config.json`). If the Linear issue has no description, auto-promote writes `[blocked]` instead of `[pending]` and adds a blocker requiring real intake details before claim.
- Status changes on tracked issues flow back: a Linear issue moved to "Done" auto-flips its mapped PLAN.md row to `[completed]`.
- Idempotency: per-plan `.external-state.json` sidecar maps `task_id ↔ linear_issue_id`. The in-text `[Source:]` marker is the safety net if the sidecar is lost (see `### External boards` race-recovery rule).

**PUSH** — PLAN.md → Linear:

- Unmapped `[pending]` / `[in_progress]` PLAN tasks create Linear issues via `mcp__plugin_linear_linear__create_issue` (or the adapter's REST equivalent).
- Linear descriptions must not be title-only. The adapter renders Details, Evidence, non-core tags (`Sub-plan`, `Depends`, `Blocker`, etc.), plan location, ETA, and explicit Intake Gaps. If a PLAN row has no prose beyond the title, no `[Evidence:]`, or no `[ETA:]`, the Linear card says so instead of pretending the issue is specified. Existing mapped issues get the same treatment through `sync_task_metadata()`; the next sync updates stale titles/descriptions instead of only fixing future cards.
- Status flips on PLAN rows push to Linear via `update_issue` mutation:
  - `[pending]` → Backlog
  - `[in_progress]` → In Progress
  - `[in_review]` → In Review (if configured) or "Ready for QA"
  - `[completed]` → Done
- The `_blocked` flag pushes via `push_fields({'_blocked': True})` and sets the Blocked field separately (does NOT change pipeline status — Blocked is orthogonal per the adapter contract).

**CLOSEOUT** — when a fix PR merges:

- The agent that shipped the fix flips the PLAN row to `[completed]`. The next inbox-sync cycle pushes that to Linear automatically.
- For real-time closeout (don't wait for the next cron tick), call directly:

```bash
# Find the issue's stateId for the project's "Done" state via:
mcp__plugin_linear_linear__get_workflow_states project="<project-name>"
# Then update:
mcp__plugin_linear_linear__update_issue id=<issue-id> stateId=<done-state-uuid>
# Add the fix-commit SHA as context:
mcp__plugin_linear_linear__create_comment issueId=<issue-id> body="Fixed in <commit-sha> (PR #<N>)."
```

**Configuration** — each user / org configures their own Linear binding in `vidux.config.json`:

```json
{
  "inbox_sources": [{
    "adapter": "linear",
    "enabled": true,
    "config": {
      "token_file": "~/.config/vidux/linear.token",
      "team_id": "<your-linear-team-uuid>",
      "project_id": "<your-linear-project-uuid>",
      "project_name": "<project-display-name>",
      "state_mapping": {
        "pending": "<backlog-state-uuid>",
        "in_progress": "<in-progress-state-uuid>",
        "in_review": "<review-state-uuid>",
        "completed": "<done-state-uuid>"
      },
      "blocked_label": "blocked",
      "managed_labels": {
        "repo": "repo:<repo-name>",
        "source": "source:vidux"
      },
      "auto_promote_target": "<plan-dir>",
      "auto_promote_max_new": 25
    }
  }]
}
```

Workspace-specific bindings (project UUIDs, state UUIDs, token paths) are LOCAL to each user's `vidux.config.json` — core vidux ships only the adapter contract.

**Why this lives in CORE (not in a per-user overlay).** Linear is one of the supported PM tools alongside `gh_projects`, `asana`, `jira`, `trello`. The closeout pattern (fix PR → status flip → external system update) is the SAME shape for all of them. Documenting it in core lets other vidux users adopt Linear (or any adapter) without re-inventing the round-trip.

**Cross-workspace caveat.** A Linear adapter token (`token_file:` in the adapter config) is scoped to ONE Linear workspace. PUSH, PULL, and CLOSEOUT all run against THAT workspace's API only. If a different system — Jam.dev's Linear bridge, a separately-installed GitHub Linear sync, manual hand-create from a teammate — routes Linear issues into a DIFFERENT workspace, the configured adapter cannot see them: PULL never surfaces them as INBOX or auto-promote candidates, and PUSH never duplicates (those issues already exist somewhere, just not in the watched workspace).

When triaging a finding that mentions a Linear identifier (e.g. `EVE-317`), do not assume the prefix maps to the workspace your adapter token watches. Verify the workspace component of the Linear URL (`linear.app/<workspace-slug>/issue/<id>`) before deciding whether the cron should have caught it. Misreading the workspace as "ours" leads to wasted retries and false-negative reports about adapter health.

Two mitigations when work routes across workspaces:

1. **Consolidate sources** so every issue-creating system writes into the configured workspace.
2. **Configure multiple `inbox_sources` entries** with the `linear` adapter, each pointing at a different `token_file:` for a different workspace. Each entry maintains its own per-plan `.external-state.json` map; idempotency is per-adapter-instance, not per-adapter-class.

When Linear is unreachable for any reason — wrong workspace, expired OAuth, MCP disconnected, token rotated — the originating system's metadata is still authoritative. Jam recordings keep their console / network / repro detail; GitHub PR comments keep their thread; Sentry events keep their stack. Don't gate a fix lane on Linear being queryable; treat the originating system as the source of truth and let Linear catch up via CLOSEOUT or the next sync cycle.

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

### Placeholder draft PRs over blocked exits

When a multi-step plan stalls on external unblocks (DM responses, design decisions, sibling-PR merges, latency baselines, AB approvals), the cycle should **not** exit "drained" while there is agent-doable surface. Ship realistic placeholder draft PRs against the unresolved questions with assumptions baked in and documented in the PR body, so the conversation moves forward on concrete artifacts instead of speculative chat. Defaults: every flag default-off / zero, isolated worktree off `origin/master`, `gh pr create --draft`, no assigned reviewers, no `@`-mentions in the body. Per-organization-overlay placeholder discipline (review-bot acks, fleet wiring, person-specific routing) lives in `/vidux-leo § Placeholder draft PRs over blocking` (codified 2026-05-21); core vidux owns the principle, overlays own the local taste.

### Plan archival pattern (parallel-session reconciliation)

When two plans for the same surface are discovered post-hoc (the discovery rule above failed and a duplicate exists), fold the smaller / newer / less-receipt-dense one INTO the canonical older one. Append an H2 section to the canonical plan titled `## YYYY-MM-DD — Parallel-Session Reconciliation` that lists what the other plan covered, which receipts merged in, and which tasks transferred. Then move the duplicate plan directory into `_archived/<plan-slug>/` next to the canonical, and prepend a SUPERSEDED banner to its top-level file pointing at the canonical PLAN.md. Don't delete; archival preserves the receipts and the conversation trail for future agents. Close any duplicate placeholder PRs the second session opened with a comment linking the canonical plan. The 2026-05-22 GetCTRecommendations reconciliation at `~/Development/vidux/projects/semantic-music-understanding/PLAN.md` is the worked example.

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

## Persistent Loop Mode

If the user says `/vidux loop`, `loop`, `don't stop until done`, `keep going`, `finish the queue`, or `finish the spec`, enter a persistent outer loop instead of stopping after one normal slice.

Loop body:

1. Read the queue source (`RALPH.md`, active plans, or inline spec).
2. Pick the next highest-leverage unblocked step inside the currently owned lane.
3. Execute it directly or delegate it.
4. Run targeted gates for the touched area.
5. Run the first viable UI/E2E/manual smoke path for the touched surface.
6. Absorb obvious same-slice follow-on fixes uncovered by that smoke.
7. Mark the item done in the queue source.
8. Update the active plan.
9. Checkpoint with commit + push.
10. Write breadcrumb context (ledger + plan/queue note).
11. Repeat until the queue/spec is actually done.

Persistent loop mode is **lane-persistent, not checkbox-persistent**: once vidux owns a feature, surface, or queue lane, keep driving connected follow-on work there until it reaches a verified boundary or a real blocker. Do not bounce to a second mission just because one checkbox landed if the same surface still has obvious connected work.

**Queue-source rule:** `RALPH.md` and `ralph.config.json` are repo-level queue contracts. Execute that contract directly in `/vidux loop` and `/vidux nurse`. Do not replace a repo's queue contract with an ad hoc shared-state file unless the repo explicitly documents that file as canonical.

**Blocking rule:** user-visible work is not done when unit tests or build gates pass. It is only done after the first viable UI/E2E/manual smoke path passes, or a real blocker is recorded with the exact attempted command/flow. If a screenshot, simulator, browser, preview, or your own eyes reveal visible breakage, interrupt the loop and act on that defect before continuing status/proof narration. Green identifier tests do not override clipped controls, overlap, illegible text, or off-brand/product-fiction UI.

Persistent loop mode only stops for: an external blocker or missing credential; a real product decision that changes implementation; conflicting repo state that would sweep another agent's work; an explicit user redirect. It does NOT stop just because one item landed, one test suite passed, a queue checkbox flipped, a connected regression remains, or only unit/build gates passed without UI/E2E smoke proof.

### Anti-Loop Discipline

These rules apply to `/vidux loop`, `/vidux nurse`, and any ORCHESTRATED tracking cycle. They are part of the core loop contract, not optional overlays.

1. **3-strike escalation.** Before picking the next slice, check whether the same blocker, failing command, or surface appeared in the last 3 checkpoints (ledger entries, plan logs, or memory). If it did: do NOT retry it. Write a one-paragraph escalation into the repo plan or nurse log (what is stuck, what was tried, what the human needs to do). Move to the next-highest-value unblocked lane.

2. **Diminishing-returns circuit breaker.** If the last 3 loop iterations produced zero shipped code (only coordination, proof attempts, or status updates), say so explicitly and either identify the structural reason and escalate, or pick a genuinely different surface. Do not pad a stuck run with busywork.

3. **Same-command ban.** Never re-execute the exact same command that failed in the previous iteration unless the environment visibly changed (disk freed, process cleared, credential restored). "Visibly changed" means a concrete observable difference, not hope.

4. **All-blocked early exit.** If every lane is blocked by the same root cause, say so in one sentence and stop. A blocked run that admits it in 30 seconds is better than one that burns 15 minutes restating the blockage from 10 angles.

5. **Compaction survival.** Auto-compact fires at ~50% context usage (configured via `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50`). Compaction is lossy — granular conversation details are replaced with summaries. Therefore:
   - **Before each checkpoint:** write iteration state to repo files (PLAN.md progress, RALPH.md queue, `.agent-ledger/`). The filesystem survives compaction; conversation memory does not.
   - **After compaction fires:** rehydrate from repo files. Read PLAN.md, RALPH.md, CLAUDE.md, and the last ledger entry. Do not trust pre-compaction conversation details.
   - **Put durable loop instructions in CLAUDE.md**, not in the loop prompt. CLAUDE.md is re-read from disk after every compaction. Loop prompts are summarized away.
   - **Use subagents for heavy work inside loops.** Each subagent gets a fresh context window. The parent loop stays light and survives more iterations before compaction.
   - **Run `/context` periodically** to check remaining capacity. If below 30% after compaction, the session is overloaded — consider starting fresh.
   - **PreCompact and PostCompact hooks** are installed globally. PreCompact reminds you to checkpoint; PostCompact reminds you to rehydrate.

### Cron + interactive interleave

When an autonomous cron lane is firing on a project AND the user interactively redirects mid-cycle ("revamp X next", "kill that pattern", "switch to Y"), UPDATE the cron prompt in-place rather than waiting for prior tasks to drain. The pattern is small and fast — ~2 seconds for a `CronDelete` + `CronCreate` rewrite vs a full cron-interval drain (15-20 min) that would otherwise flush the redirect.

Two re-arm shapes:

- **Soft re-arm** (layered scope) — when the redirect EXTENDS the current cron's scope. Edit the existing prompt's priority order; preserve in-flight task list. The next tick picks up the new priority without wasting current tasks.
- **Hard re-arm** (replaced scope) — when the redirect REPLACES the current cron's scope. `CronDelete` + `CronCreate` with a fresh prompt. The prior cron's working notes stay in PLAN.md as decision trail.

Cost asymmetry: 2-second re-arm vs 15-min full drain. Generalizes to any cron + interactive overlap (release babysitters, watcher loops, autonomous polish loops).

---

## Nursing Mode

If the user asks you to nurse, watch, or keep an eye on active work — `/vidux nurse`, "keep an eye on it", "watch the hot lanes" — switch into a **supervisory cadence** instead of a normal execute-once loop.

Nursing means:

- Read the ledger on a cadence.
- Read the active plan/queue on the same cadence.
- Keep track of hot lanes, owners, blockers, and fresh completions.
- Intervene only when a lane drifts, blocks, conflicts, or unlocks the next queued slice.
- Drive queue items directly when the next slice is unblocked and unowned.

Vidux owns the full nursing loop: supervision, coordination, queue advancement, build-owner discipline, and plan updates. Ralph remains the repo-level queue contract (`RALPH.md` / `ralph.config.json`); vidux reads that contract, picks the next item, executes or delegates it, marks completion, and checks the ledger before deciding what's next.

**Repo-level state rule:** nursing state must live in repo-local artifacts, not an ad hoc global handoff file. Preferred sources: `RALPH.md`, repo plan docs, repo nurse logs, and `.agent-ledger/activity.jsonl`. Do not invent or depend on a one-off `<repo>-loop-state.md` file unless the repo already committed it as a canonical contract. If an automation needs durable handled-state for external signals (for example App Store feedback IDs), keep that state in a repo plan/tracker file next to the rest of the queue. Never read another repo's queue files, nurse logs, or ledger when selecting work for the current repo.

Read `pilot/orchestration/nursing.md` when the user asks for any timed or repeated supervision.

**Cadence selection:**

- **Claude Routines** (cloud-native, always-on) are the production path for recurring nursing — they survive laptop close and support scheduled + GitHub event + API triggers.
- **CronCreate** or Claude Code `/loop` are suitable for session-scoped or experimental nursing.
- If the user wants **every 5 minutes** or other sub-hourly cadence, use an external scheduler (`launchd`, `cron`, `systemd`) to invoke a narrow nurse task.
- Do not fake timed nursing by spinning a blind idle loop in chat.
- Use `pilot/orchestration/nursing.md` and `pilot/scripts/nurse_pulse.sh` as the default concrete nurse mechanism.

---

## Orchestration Mode

After detecting stack and stage, determine scale:

| Scale | Signals | Mode |
|-------|---------|------|
| **SOLO** | Quick hit, kickoff, or mid-flight. < 8 files, single concern, serial by nature. | Execute directly — vidux is the worker. Follow the stage playbook. |
| **ORCHESTRATED** | Expedition-scale. 8+ files, multiple independent concerns, multi-session, cross-tool. | Vidux orchestrates — decompose, delegate, track. |

**ORCHESTRATED triggers** (any two = orchestrate):

- Multiple file sets with zero overlap.
- Work naturally splits into independent API + UI + test concerns.
- User mentions multiple agents, Routines, Cursor, or parallel work.
- Existing ledger entries show active lanes from other agents.
- PLAN.md has a lane table or multi-phase dependency graph.
- **Multi-prototype gallery / variant fan-out** — PLAN.md has ≥3 prototypes/variants AND user issues a surface-wide directive ("revamp all", "polish every", "team agents split up", "audit each one"). Pre-route to multi-agent fan-out: spawn one Plan agent per prototype/variant, each reads its own surface, returns task list with `file:line` citations, parent integrates into the single PLAN.md. Wall-clock 3-5x savings vs serial. Surface-disjoint precondition holds because each prototype is its own file and no agent edits another's file.

### Default Discipline Swarm

For product/UI work that spans multiple concerns, default to a discipline swarm even in an unfamiliar repo:

- UX / surface behavior
- copy / localization
- persistence / data correctness
- Dev App or preview/manual QA
- automation / E2E

This is project-agnostic — the decomposition pattern, not a specific repo's structure.

### Release Swarm (10 roles)

When the user asks for release readiness, a nurse loop, or a last-mile ship push across multiple surfaces, default to a 10-role release swarm:

1. Localization + Copy Sentinel
2. App Store Connect Feedback Triage
3. Sentry + Seer Error Hunter
4. UX Feedback Triage Lead
5. Code Review + Clipdiff Auditor
6. UX Uniformity + Canonical Surface Mayor
7. Dead Code + Drift Analyzer
8. Architecture + Test Discipline Guardian
9. Screenshot + Snapshot + UI Test Sheriff
10. App Store SEO + Metadata God

### Heat scan before spawn

Before spawning agents, spend 60 seconds on a heat scan: which roles have open items in the queue/plan/ledger? Which had activity in the last 2 runs? Which are blocked by known persistent blockers?

- **Hot** (2-4 roles): open items, recent activity, unblocked. Full inspection and dedicated agent lanes.
- **Warm** (2-3 roles): no open items but could have drifted. 30-second scan with a one-line verdict.
- **Cold** (remaining roles): confirmed stable in last 2 runs. Single line: "Role N: cold since [date], skipping."

Spawn agents for hot roles only. Do not spawn 6 agents when 2 lanes are hot and 4 would idle. Minimum spawn 1 (single deep lane while coordinator coordinates). Maximum 4-6 for genuinely parallel independent work. A cold role becomes warm when a new queue item touches its surface, a user mentions it, or 5+ runs pass since last inspection. Preserve the 10-role checklist for completeness; cold roles get one line in memory, not a full inspection pass.

### Orchestration loop

When ORCHESTRATED, follow this loop (see `pilot/orchestration/mayor.md` for the long form):

1. Select molecule from `pilot/orchestration/molecules.md` (Feature, Cleanup, Migration, Research, or composed).
2. Decompose into lanes per `pilot/orchestration/lanes.md`.
3. Write PLAN.md with lane table and dependency graph.
4. Spawn agents for independent lanes (Agent tool, background, worktrees).
5. Track via the ledger and completion notifications.
6. Intervene on blockers, drift, or discoveries.
7. Integrate when lanes complete — merge, cross-test, full gates.
8. Handoff per `pilot/orchestration/handoff.md` if work continues.

### First-class end-to-end proof

For any user-visible change, treat end-to-end proof as a blocking gate, not a polish task. Preferred order: (1) existing UI/E2E automation for the touched surface; (2) add or tighten focused UI/E2E coverage if the gap is small and the path is stable; (3) manual smoke path when no automation exists yet. Do not declare "done" on build + unit coverage alone. Record the exact smoke command or manual path you ran. If smoke reveals more bugs, reopen the queue and continue the loop.

---

## Stack & Stage Routing

Run `pilot/scripts/detect_stack.sh` or check signal files manually:

| Signal | Stack ID | Routing |
|--------|----------|---------|
| `Project.swift` or `*.xcodeproj` | `ios-tuist` | See `pilot/stacks/ios-tuist.md` |
| `next.config.*` | `nextjs-vercel` | See `pilot/stacks/nextjs-vercel.md` |
| `vite.config.*` (no next.config) | `vite-react` | See `pilot/stacks/vite-react.md` |
| `shopify/` or `*.liquid` | `shopify` | See `pilot/stacks/shopify.md` |
| `Cargo.toml` | `rust` | Inline (no skill yet) |
| `package.json` only | `node-generic` | playwright if e2e exists |

After stack, detect stage from repo state:

| Stage | Signals | Playbook |
|-------|---------|----------|
| **KICKOFF** | No plan file for this feature, user says "build X" / "add X" | `pilot/stages/kickoff.md` |
| **MID-FLIGHT** | Existing plan with pending items, branch with changes | `pilot/stages/mid-flight.md` |
| **LAST MILE** | Most plan items done, user says "ship" / "finish" / "polish" | `pilot/stages/last-mile.md` |
| **QUICK HIT** | Single-screen change, one-sentence description, < 3 files | `pilot/stages/quick-hit.md` |
| **EXPEDITION** | Touches 5+ files, needs phases, multi-session | `pilot/stages/expedition.md` (integrates orchestration for ORCHESTRATED scale) |

Every stage ends with verification gates from `pilot/patterns/gate-checklist.md`. Universal engineering patterns (DI, state machines, in-memory test seams, lifecycle gates) live in `pilot/patterns/leos-patterns.md`.

For Figma-driven work, prefer repo-local MCP rules over global defaults and preserve them in the repo's `ai/skills/` folder when they are durable project knowledge.

---

## Skill Composition

Vidux delegates. It never duplicates. See `pilot/stacks/*.md` for per-stack routing tables.

Universal skills available in any stack:

- `clipdiff` — PR-ready diffs.
- `captain` — meta/skill maintenance (skill audit, symlink discipline). If older prompts say `skill-manager`, route to `captain`.
- `maily` — email cross-referencing.
- `ledger` — cross-tool coordination (critical for ORCHESTRATED mode).
- `nia` — external doc / package source lookup (check before WebFetch).
- `amp` — prompt amplification for vague tasks (GATHER → steer → fire).

Local skills do not usually need a manual "on" switch if the `~/.claude/skills` or repo-local skills symlink is correct. MCP-backed tools are separate from skills and may still need app-side install/auth.

When a repo already has one active feature-reset plan and multiple agents are working in parallel: reuse the existing plan instead of creating a competing plan doc; add a claim line before editing canonical sections or cross-cutting files; append discoveries to the shared coordination log before rewriting product-contract text; treat chat guidance as non-canonical until it is written back into the active plan.

### Claude Routines vs CronCreate vs `/loop`

Codex fleet is deprecated — use **Claude Routines** (cloud-native, always-on, survives laptop close, configured at [claude.ai/code/routines](https://claude.ai/code/routines)) for production recurring automation. CronCreate is for session-scoped experiments. `/loop` is for in-session iteration.

| Trigger type | Fires when | Create via |
|---|---|---|
| **Scheduled** | Cron expression (min 1h, presets: hourly/daily/weekdays/weekly) | CLI (`/schedule`) or web |
| **GitHub event** | PR, push, issues, workflow runs, releases, etc. | Web UI only |
| **API** | `POST /fire` with bearer token + optional payload | Web UI only |

**Heuristic:**

- **Routines** — anything that must survive laptop close, GitHub event triggers, fleet watchers, lifecycle managers (always-on).
- **CronCreate** — session-scoped experiments, rapid recipe iteration, local-only resources (Xcode, simulators).
- A single routine can combine multiple triggers (e.g., nightly schedule + PR webhook).

When wiring fleet work, reference the 8 automation recipes from `guides/recipes.md`:

| # | Recipe | Role | Trigger |
|---|--------|------|---------|
| 1 | **Fleet Watcher** | Coordinator (read-only) | Scheduled 2h |
| 2 | **PR Reviewer** | Reviewer (read-only) | GitHub event (PR) |
| 3 | **Draft-PR Lifecycle** | Tracker (read-only) | Scheduled 1h |
| 4 | **Observer Pair** | Observer (read-only) | Scheduled 2h offset |
| 5 | **Deploy Watcher** | Verifier (time-bounded) | GitHub event (push) |
| 6 | **Trunk Health** | Infra monitor (read-only) | Scheduled 4h |
| 7 | **Skill Refiner** | Quality auditor | Scheduled 6h |
| 8 | **Self-Improvement** | Meta-writer | Scheduled 24h |

Start with Fleet Watcher + PR Reviewer (highest ROI), add more as daily budget supports them. A typical fleet combines 3-5 recipes.

---

## Checkpoint Breadcrumbs

After every meaningful completed slice, leave all three breadcrumbs:

1. **Git** — commit and push the owned slice.
2. **Ledger** — summarize what shipped, what remains, and the current branch/SHA.
3. **Plan / queue** — mark progress in the active plan, `RALPH.md`, or queue source.

Checkpoint at these moments: after a meaningful slice completes; before handoff; before changing lanes or worktrees; after an integration fix that creates a new stable base for other agents.

Commit everything the active agent owns, but do NOT sweep unrelated dirty files from other agents by default.

---

## Replaces /superpowers (folded 2026-04-26)

The Anthropic `superpowers` plugin used to provide 14 process-discipline subskills that auto-loaded on relevant triggers (brainstorming, TDD, debugging, code review, parallel agents, worktrees, etc.). All of those concepts are already covered by core vidux and its companion skills — having both was redundant ("if vidux is supposed to be my superpower"). The plugin is uninstalled. Use this routing table when you'd previously have reached for a `/superpowers:*` skill:

| `/superpowers:*` was for | Use this instead |
|---|---|
| `brainstorming` (before any creative work) | Vidux Principle 1: plan first. Brainstorm in main thread, then write the PLAN.md before code. Quick brainstorms can stay in chat — only formalize when the work spans 30+ minutes. |
| `writing-plans` | Vidux core — `## PLAN.md Template` section above |
| `executing-plans` | Vidux Cycle (READ → ASSESS → ACT → VERIFY → CHECKPOINT) |
| `subagent-driven-development` | `guides/automation.md` § subagent dispatch + your overlay skill's auto-dispatch protocol |
| `dispatching-parallel-agents` | `guides/automation.md` § parallel agents (surface-disjoint precondition) + your overlay skill's fan-out rule |
| `test-driven-development` | Vidux Principle 5: prove it mechanically. Write the assertion before the implementation when the surface needs regression protection (visual-proof merge gate) |
| `systematic-debugging` | Vidux Principle 3: investigate before fixing. Use the `## Investigation Template` for any bug touching 2+ tickets or unclear root cause |
| `requesting-code-review` / `receiving-code-review` | Your overlay skill's review-bot ack discipline (Graphite / Greptile / Cursor / Seer yay-or-nay before merge) |
| `verification-before-completion` | Vidux Principle 5: prove it mechanically. UI work definition-of-done = visual proof |
| `using-git-worktrees` | Your overlay skill's worktree isolation + per-lane DerivedData guidance |
| `finishing-a-development-branch` | Your overlay skill's merge-timing rubric (ready-PR auto-merge once review-bots ack) |
| `writing-skills` | Use `captain` — owns skill creation, registry, and symlink hygiene |
| `using-superpowers` (meta loader) | Removed — vidux loads when you say `/vidux` or describe expedition-scale work |

**Rule of thumb:** if you'd reach for a `/superpowers:*` skill, you're already inside `/vidux`'s domain. Read the relevant principle / cycle step / guide instead of summoning a separate plugin.

---

## Output formats — one-shot HTML decision briefs

For one-shot HTML decision briefs (not ongoing PLAN.md / repo work), use `/editorial-brief` — it ships a single-file editorial-magazine HTML artifact to vidux-browse on a trusted-LAN host, and follows /vidux plan-first discipline for the research/write phases but lands as a self-contained HTML file instead of a tracked-in-repo .md plan.

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
- Selected plan rendered as markdown, with sibling tabs for any sibling `.md` files in the same plan directory when present (common conventions include `PROGRESS.md` and `INBOX.md`; per-owner conventions like `ASK-<OWNER>.md` are also supported)
- Named comments attached to the selected plan tab or artifact, stored separately from source files
- Anchored annotations: click the top-bar `Annotate` control or press `Cmd/Ctrl+Shift+C`, then click the exact rendered element the comment is about
- Filter box to search across repo / slug / purpose

Discovery globs (covers the three conventions in use across the fleet):

- `<repo>/ai/plans/<slug>/PLAN.md`
- `<repo>/vidux/<slug>/PLAN.md`
- `<repo>/projects/<slug>/PLAN.md`
- `<repo>/PLAN.md` (root-level)

Stack: Python stdlib `http.server` + plain HTML/CSS + vanilla JS + `marked.js` from CDN. Zero pip dependencies. Default bind is `127.0.0.1`; `VIDUX_BROWSER_HOST=0.0.0.0` enables trusted-LAN read access for operator-owned dashboards.

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

#### Symlinks vs hard links in `artifacts/`

When you want an artifact file to share content with a canonical source elsewhere (e.g., the `.html` lives next to a `.md` source in some other repo and you want a single inode), use a **hard link, not a symlink**. The browser server enforces this mechanically; symlinks pointing outside `ARTIFACTS_DIR` fail closed.

**Why.** `browser/server.py`'s `safe_resolve_any()` validates request paths with `Path.resolve()`, which follows symlinks. If an artifact file is a symlink whose target resolves OUTSIDE `ARTIFACTS_DIR` (e.g., to a canonical source in another repo), the subsequent `Path.relative_to(ARTIFACTS_DIR.resolve())` raises `ValueError` — the server returns **403 forbidden** on `/api/file` and `/api/comments`.

**Symptom.** Artifact metadata shows in the sidebar (vidux-browse globs the dir for index purposes and that's directory iteration, not path resolution), but the body never loads. Browser console shows `failed to load comments: forbidden` plus a 403 on the file request. The H1 from the index may render but everything below is empty.

**Fix — hard link, no `-s`:**

```bash
rm ~/Development/vidux/browser/artifacts/<slug>.html
ln <canonical-path>.html ~/Development/vidux/browser/artifacts/<slug>.html   # no -s
```

**Constraints + verification:**
- Same filesystem only. Any path under the user's home volume is fine (`~/Development/...`, `~/REDACTED-EMPLOYER-PATH/Dev/...`, `~/.claude/...` all share one volume on a stock macOS install). Cross-volume hard links fail at `ln` time.
- `Path.resolve()` does NOT cross hard links — the artifact path stays inside `ARTIFACTS_DIR`, security check passes.
- Updates to the canonical file reflect instantly at the artifact path; it's one inode with two names.
- Verify with `stat -f '%i' <canonical> <artifact-path>` — matching inodes prove they share data.

**Real-world incident (2026-05-12).** `music-semantic-backend-mvp.html` was dropped into `artifacts/` as a symlink to its canonical source in another repo. vidux-browse sidebar showed it; clicking it rendered only the H1 plus `403: forbidden` in the body. Replacing the symlink with a hard link fixed it the same minute. Memory: `reference_vidux_artifacts_hardlink_rule.md`.

### Named comments / annotations

vidux-browse comments are lightweight annotations on the current view. They can target either an allowed markdown file (`PLAN.md`, `INBOX.md`, `investigations/*.md`, `evidence/*.md`, etc.) or an HTML artifact.

Key contract:
- Comments are append-only app data in `${VIDUX_BROWSER_COMMENTS_FILE:-~/.vidux-browser/comments.jsonl}`.
- Comments never mutate `PLAN.md`, `INBOX.md`, repo files, task claims, or artifact HTML.
- Cross-machine LAN viewers may comment through the vidux-browse UI, but POSTs must be JSON and same-origin (`Origin` or `Referer` must match the browser host).
- Use comments for human feedback, review notes, “worth knowing” annotations, and LAN collaboration. Use `INBOX.md` only when a local agent intentionally needs the note inside vidux state.
- For precise comments, use the top-bar `Annotate` control or `Cmd/Ctrl+Shift+C`; the next clicked rendered markdown/artifact element becomes a sanitized anchor with selector, label, excerpt, tag, and index metadata. The `Target` pill scrolls back to that element. Anchors are best-effort UI pointers, not plan authority. Annotation/filter shortcuts are ignored while typing in inputs, textareas, selects, or contenteditable fields.

### Local plan notes (loopback-only)

When an agent needs to leave a constrained note for the current Mac's vidux plan, use the local plan-note endpoint. It appends to that plan directory's `INBOX.md`; it does not edit `PLAN.md` directly.

```bash
curl -X POST http://127.0.0.1:7191/api/local-plan-note \
  -H "Content-Type: application/json" \
  -d '{"plan_path":"~/Development/project/PLAN.md","source":"codex/local","agent":"codex/local","note":"Short note for the next local agent."}'
```

This endpoint rejects non-loopback clients. Even when vidux-browse is bound to `0.0.0.0` for home-LAN reading, `POST /api/local-plan-note` must be called through `127.0.0.1` or `::1`; other Wi-Fi devices can read but cannot write plan notes.

### Read-aloud add-on (Voxtral 4B-TTS via mlx-audio, optional)

vidux-browse can ship a 🔊 "Read aloud" button that reads the active artifact / `PLAN.md` aloud via **Mistral Voxtral 4B-TTS running locally on Apple Silicon through `mlx-audio.server`**. vidux-browse is a thin HTTP client; the model and GPU state live in a dedicated Python process the operator manages as a LaunchAgent.

**Status:** opt-in add-on. Default vidux-browse builds include the client JS but it gracefully shows `🔊 Server offline — start mlx-audio LaunchAgent` until the operator installs the server side.

**Topology**

```
vidux-browse (127.0.0.1:7191)            mlx-audio.server (127.0.0.1:8000)
  static/readaloud.js (HTTP client)  ──▶  POST /v1/audio/speech
                                          loads weights lazily, returns WAV
                                          launchd: com.<user>.mlx-audio
```

**Stack:**

- **Model:** `mlx-community/Voxtral-4B-TTS-2603-mlx-bf16` (Mistral Voxtral 4B TTS, mlx-community bf16 conversion). 9 languages, 20 voice presets, native `ref_audio` voice cloning. RTF ~0.8× on M4 Pro after warm-up; peak ~9.3 GB RAM during synthesis.
- **Server:** `mlx_audio.server` from [Blaizzy/mlx-audio](https://github.com/Blaizzy/mlx-audio) (MIT). Exposes the OpenAI-compatible `/v1/audio/speech` endpoint over uvicorn/FastAPI.
- **Client:** plain `fetch` from `browser/static/readaloud.js`. No build step. Sentence-level chunking client-side; per-chunk highlight migrates as audio plays.
- **Hardware:** Apple Silicon (verified M4 Pro). 16 GB Macs likely OK with caveats; 8 GB Macs not recommended (peak 9.3 GB).
- **Browser fallback:** `browser/static/readaloud-kokoro.js` ships alongside as the offline / Apache-2.0 alternative (Kokoro 82M via WebGPU). Operators on machines without mlx-audio swap the `<script src>` in `index.html`.

**License — IMPORTANT:** Voxtral weights are **CC-BY-NC-4.0** (non-commercial). Personal vidux use is fine. Commercial properties MUST NOT call this endpoint with Voxtral — substitute Apple Premium voices via Web Speech API, or the Apache-2.0 Kokoro fallback.

**CORS:** mlx-audio.server's `--allowed-origins` allowlist must include both `http://localhost:7191` and `http://127.0.0.1:7191` for vidux-browse to call it from the browser. Loopback-only by default; LAN reading from another device requires adding that device's origin.

**Install:** see your machine-management skill's "Voxtral Reader add-on" section. The full install command, plist install, and `launchctl bootstrap` step live there because they're per-Mac.

**Reference plan + architecture:**

- `~/Development/vidux/projects/voxtral-reader-addon/PLAN.md` — task breakdown M1-M10 + Decision Log + Two-Agent Coordination protocol.
- `~/Development/vidux/projects/voxtral-reader-addon/evidence/2026-05-01-architecture.md` — port + endpoint + CORS + LaunchAgent decisions, with the canonical `uv tool install` command including the seven `--with` extras mlx-audio's PyPI metadata is missing.
- `~/Development/vidux/scripts/launchd/com.<user>.mlx-audio.plist` — the in-repo source-of-truth plist for cross-Mac install.

---

## Voice & Tone

Output should sound like a sharp teammate briefing the user, not a CI pipeline writing a report.

- **Lead with what matters.** What shipped, what is blocked, what you need from the user. Not role labels, not file lists, not generic summaries.
- **One warm paragraph beats a 10-row table.** Save structured role breakdowns for ledger entries and memory files. The human-facing output should read like a message from someone who cares about the project.
- **Name things by product meaning.** "Built and uploaded build 622 to TestFlight" beats "iOS Release Lane: shipped." "Screenshots stuck on CoreSimulator" beats "Screenshot + Snapshot + UI Test Sheriff: blocked."
- **Be honest about nothing happening.** If a run produced no shipped code, say that in one sentence. Do not inflate coordination work into apparent progress.
- **Blockers are requests, not complaints.** "The FX pipeline needs a fresh credential — can you rotate it?" beats "FX Lane: blocked (credential expired)."
- **Ledger, plans, and memory can stay structured** — those are for machines and future agents. The final message to the human is for a human.

Default to: terse, concrete, evidence-cited; one decision per paragraph; named files+lines for citations; no hedging language; no marketing tone.

---

## Reference Files

The `pilot/` subfiles remain on disk and are referenced by name from this SKILL.md. They contain the long-form detail for routing, orchestration, patterns, and stage playbooks.

| File | What It Contains |
|------|-----------------|
| **Orchestration** | |
| `pilot/orchestration/mayor.md` | Orchestration loop: decompose → plan → spawn → track → intervene → integrate → handoff |
| `pilot/orchestration/nursing.md` | Supervisory cadence for hot lanes, timed ledger polling, and queue driving |
| `pilot/orchestration/lanes.md` | Lane anatomy, rules, decomposition patterns, conflict resolution |
| `pilot/orchestration/handoff.md` | Handoff protocol: ledger entries, 5-suggestion pattern, receiving handoffs |
| `pilot/orchestration/molecules.md` | Composable workflow templates: Feature, Cleanup, Migration, Research, Integration |
| **Patterns** | |
| `pilot/patterns/leos-patterns.md` | 20+ universal engineering patterns with examples |
| `pilot/patterns/plan-template.md` | Skeleton plan: locked decisions, TDD slices, gates, kill list |
| `pilot/patterns/gate-checklist.md` | Per-stack verification commands |
| **Stage Playbooks** | |
| `pilot/stages/kickoff.md` | New feature playbook |
| `pilot/stages/mid-flight.md` | Resume/continue playbook |
| `pilot/stages/last-mile.md` | Polish/ship playbook |
| `pilot/stages/quick-hit.md` | Small feature playbook |
| `pilot/stages/expedition.md` | Multi-phase playbook (integrates orchestration for ORCHESTRATED scale) |
| **Stack Routing** | |
| `pilot/stacks/ios-tuist.md` | iOS skill routing |
| `pilot/stacks/nextjs-vercel.md` | Next.js skill routing |
| `pilot/stacks/shopify.md` | Shopify skill routing |
| `pilot/stacks/vite-react.md` | Vite/React skill routing |

---

## Beyond Core — Automation and Recipes

Everything above is **core vidux** — the five principles, the cycle, the PLAN.md template, investigations, course correction, routing, orchestration. It works for humans, one-shot AI sessions, and cron-scheduled workers alike. A human following core alone is doing vidux correctly.

If your work needs more, two companion surfaces carry the rest:

- **[`guides/automation.md`](guides/automation.md)** — the 24/7 fleet operating model, session-gc, lane management, subagent delegation, lane bootstrap. Load this when you run lanes on a schedule.
- **[`guides/recipes/`](guides/recipes/)** — opt-in tactics and patterns. CLAUDE.md rules, lane prompt templates, subagent dispatch, evidence discipline, proactive work surfacing, visual-proof requirements, and more. Load a specific recipe on demand.

**Codex automation default:** when creating a new automation from Codex, assume `Run in: Chat`. Do not default to `Worktree` or `Local` unless the user explicitly asks for repo-bound execution or the task cannot be done from chat.

Neither surface overrides core vidux. Core is opinionated machinery; automation and recipes are opt-in layers.
