# Recipe: Lane Prompt Patterns

> The 8-block structure plus common patterns for writing automation lane prompts (`prompt.md` files that drive cron lanes).

## When to use

- Creating a new automation lane (writer, radar, or coordinator)
- Auditing an existing `prompt.md` that's drifting, stalling, or duplicating work
- Migrating a legacy prompt to the current repo-owned authority model

## The 8-block structure

Every lane prompt has these eight blocks, in this order. Rearranging or omitting blocks produces known failure modes.

```
1. Mission      — why this lane exists; retirement condition. One paragraph.
2. Skills       — public, mission-relevant guidance to load.
3. Read         — explicit file-read order every cycle.
4. Gate         — pre-flight checks that can abort the cycle cheaply.
5. Assess       — priority rule for picking the ONE thing to do this cycle.
6. Act          — how to do the work (worktree, verify, commit, merge).
7. Authority    — paths owned vs paths forbidden (+ push tier).
8. Checkpoint   — proof, remaining risk, and one resume action.
```

Full reference: `docs/reference/prompt-template.md`. Keep the prompt as short as
possible while preserving all eight blocks.

## Block-by-block guide

### 1. Mission
One paragraph. Present-tense and concrete. Name the PLAN.md the lane drives. **Name the retirement condition.** A lane without an exit is a zombie.

> Ship and maintain example.com. Every cycle moves PLAN.md forward, fixes CI, merges eligible PRs, or rotates a filler audit. Retires when Phase 9 launch ships.

### 2. Skills
Name only public guidance that the lane actually needs. Do not embed private
skill catalogs, operator aliases, provider settings, or account details.

### 3. Read
Use repository-relative authority paths and commands that work from the named
working directory. End with a bounded ownership check.

> 1. `PLAN.md`
> 3. `git fetch && git status --short && git log --oneline -10`
> 4. `gh pr list --json number,title,mergeable,statusCheckRollup`
> 5. active claims for the paths this lane may edit

### 4. Gate
Binary pre-flight aborts. Trigger → exit cheaply with `[QC] <reason>`. Don't "maybe work around it." Keep the list short; too many gates and cycles never fire.

Typical gates: dirty tree not mine → `[QC] concurrent-cycle`; same task `[in_progress]` 3+ cycles → set `[blocked]` + exit; main CI red → fix-first mode; post-push defer (see below).

### 5. Assess
One deterministic priority order. Resume the active row; otherwise take the
highest unblocked row. Complete one bounded row, checkpoint, and exit.

> Priority: CI red > failing PR fix > eligible PR merge > resume `[in_progress]` > first `[pending]` with evidence > promote INBOX > rotate filler audit > `[IDLE]`.

### 6. Act
Worktree discipline + verification commands + commit/push/merge procedure. Every command literal — don't paraphrase.

Mandatory: isolate each code change; name the repository's lint, test, and build
checks; never use broad staging; and require direct visual proof for UI changes.
Before handoff, update the owning `PLAN.md` with the revision, checks run,
remaining risk, and one resume action. Provider receipts and private runtime
records are not public proof.

### 7. Authority
Explicit owned paths + explicit forbidden paths with reasons. The authority block is the lane's immune system. **Mandatory push-tier line** for any code-writing lane.

> Owns: `app/**`, `next.config.ts`, `vidux/PLAN.md`, `vidux/INBOX.md`.
> Never: `content/posts/**/*.mdx` body (the user's historical prose), `.env*`, other lanes' `memory.md`.
> Push tier: operational PRs only; open ready-for-review by default with the canonical vidux PR body. No direct-to-main, no destructive ops.

### 8. Checkpoint
Update the owning `PLAN.md` with result, named proof, uncertainty, and one
cold-resume next move. A host-local note or ledger projection is optional and
never outranks the plan.

> `- [YYYY-MM-DDThh:mm:ssZ] [SHIP] <what>. <next-cycle hint>.`
> Tags: `SHIP` / `MERGED` / `FIX` / `PROMOTE` / `DEFER` / `IDLE` / `QC` / `AUDIT-N` / `MILESTONE`.
> No "everything fine" entries.

## Common patterns

**Post-push defer.** The cycle that pushes a PR must NOT also merge it. Gate: "if last cycle pushed, this cycle may only review CI — no merge until 1h since last fix-push AND all checks green." Prevents auto-merging a failing build.

**QC exit.** Cheap exits for concurrent-cycle, stuck tasks, red CI. Always tagged `[QC] <reason>`. A `[QC]` exit is not a failure — it's the correct move when preconditions aren't met.

**Optional host note.** A coding host may keep a short local activity note, but
the repository plan and linked proof are the durable handoff.

**Worktree-per-change.** Every code edit happens in a fresh worktree from `origin/main`. Never edit on the main worktree. Merge back to trunk before closing the task.

**Branch verification after commit.** After `git commit`, always run `git branch --show-current` and confirm it matches the intended branch. Prevents committing to `main` by accident when a worktree is misconfigured.

**Polish-brake.** If the last 3 checkpoints ship from the same surface, force-rotate to another surface next cycle. Polish is fractal; every green PR has another P3 comment.

## Anti-patterns

- **Hard-coded transient state.** A prompt that says "fix the auth flow" will stop making sense once auth is fixed. Put task-level specifics in PLAN.md; the prompt stays evergreen.
- **Queue draining.** Completing several rows in one run blurs proof and resume
  state. Do one bounded row, checkpoint, and exit.
- **No retirement condition.** Lane runs forever, ships polish PRs no one reads. Every mission names an exit ("retires when Phase 9 launches" / "retires after the backfill completes").
- **Skipping the Authority block.** The lane drifts into sibling work or edits
  user-owned prose. Authority is load-bearing.
- **Provider-specific runtime receipts.** Account, session, usage, cost, or
  private log data does not belong in a public lane prompt.
- **Doctrine restatement.** Do not repeat plan-first prose when a reference is
  enough. Delete sentences that do not change behavior.
- **Gating on the wrong file.** If Block 4 checks a meta-plan marked "done," the agent exits before loading any skill. Gate on actual work state (dirty tree, CI status, queue depth).

## See Also

- `guides/automation.md` — where to plug a prompt.md in a lane (Lane Bootstrap Recipe)
- `docs/reference/prompt-template.md` — canonical 8-block reference with full examples
- `guides/fleet-ops.md` — multi-lane operations, radar vs writer vs coordinator
- `guides/recipes/subagent-delegation.md` — same-tool Mode A / Mode B delegation
- `guides/recipes/codex-runtime.md` — Codex-native lane setup
