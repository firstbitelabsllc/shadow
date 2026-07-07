---
name: vidux
description: "Plan-first project router for AI agents. Detects stack, stage, and scale, then executes directly or shifts into markdown plan work with proof and resume metadata."
---

# Vidux

> **Opt-in legacy/reference toolkit.** Vidux is no longer a default runtime or
> router for Leo's Claude/Codex/Cursor/Agents skill farm. Keep this repo for old
> plans, browser/artifact utilities, scripts, and explicit legacy/reference
> tasks. Default work should route through `/leo-flow`, repo skills, native host
> tools, PLAN.md/FLOW.md, `/hook`, and the ledger.

Vidux is a discipline for AI agents: write down what you build before you build it. Plans live in markdown files in git. Agents read the plan, do one piece of work, update the plan, and checkpoint. Any agent resumes where the last left off: the owning plan records queue, decisions, constraints, progress; matching ledger rows carry shipped-cycle proof.

**publish packet** = the publish ledger row that carries `{summary, task-id, plan-path, proof, handoff_status, files claimed, path-like claims, next-agent resume}`. Named once here; referenced by name below.

**2026-07-07 kernel-cut boundary:** Vidux is a thin planning and proof control
plane. The planner-executor bakeoff refuted the default handoff bet, so
Fable/Claude/GLM/Grok/Codex remain bounded workers, eval subjects, or
Flow-selected sidecars. Vidux keeps the durable surfaces that proved useful:
one canonical `PLAN.md`, explicit Decision Log, publish packet proof, resume
metadata, and the read-only browser cockpit.

## Rising Tide Doctrine (Leo 2026-06-22 — the stapled mantra for /vidux and /leo-flow)

**A rising tide lifts all boats.** Every cycle improves *everything it touches*, not just the immediate goal row. This is the standing operating philosophy across `/vidux` and `/leo-flow`.

1. **Drive-by improve everything.** While in a file/surface for the goal, leave it better than you found it: rewrite weak code, delete dead/bad tests and write real ones, reconsider major system design, tighten UI, add/improve unit tests, prune+update docs/READMEs, clean stale Storybook/UI artifacts. The DEFAULT is "improve it now," not "log it for later" — bounded only by the self-improvement brake (name the file + the generic rule + the verify command + the stop condition; never fossilize a one-repo incident into a shared skill; never let "improve" become forever-work).

2. **YOLO because everything reverts.** Any project Leo is working on can be YOLO'd — we can ALWAYS revert (a commit, a closed PR, `git revert`). So the default is *act*, not *ask*; ship the call and revert if wrong. A reverted call costs less than a no-op inbox.

3. **Rewrite human gates by default.** On hitting a human gate (`[ASK-LEO]` tag, approval pause, "Leo-gated" row, "wait for sign-off"), the DEFAULT is to **rewrite it to agent-owned and proceed** — *unless it truly must exist*. The only gates that truly must exist are the hard safety rails: destructive git (force-push to main, branch delete, `reset --hard`, `clean -fd`), real-money spend beyond an existing tier, credential/secret handling, sending messages to external services, irreversible public brand/hero-copy, and prod data loss. Everything else: rewrite the gate, act, stay ready to revert. **Do not lean on Leo as a human gate.**

4. **Never stop while there's a next cycle.** A dynamic-loop goal does not stop because one row landed — if a fresh PLAN sweep finds a next agent-reachable cycle, auto-start it immediately. Stop only when there is genuinely no next cycle (every row shipped-or-parked-at-a-named-hard-rail-gate). **Context-token budget is NEVER a stop condition** (see `/leo-flow` hard stops): the opencode goal-plugin auto-continues on idle and survives compaction, so on a `<budget_wrapup>`/"0s remaining" frame you END THE TURN to auto-continue into a fresh cycle — you never emit a "stopping because budget" message and never cite budget as a `[goal:blocked]` gate. Budget is a pacing hint, not a wall.

   **Reconciliation with the self-extend brake (Principle 4 below / `/leo-flow` P0 Bounded Autonomy).** "Never stop" is NOT a license for forever-work, and the brake is NOT a license to idle — they are one rule from two sides. The cap is on **inventing fake adjacent work** (re-auditing shipped rows, re-polishing a done surface, bookkeeping-only PRs, restating the same skill lesson), never on **continuous real improvement**. Every cycle still ships real artifact(s)/receipt(s) and closes with a precise state, and **every loop traverses the full priority order including planning compound items — it does NOT cap at one bounded move** (this is universal, not resplit-only; the one-bounded-move-per-cycle reflex is a slop mode). Default loop cadence is **~20 min**. Close states (`full_pass_driven` / `planned_compound` / `completed_move` / `blocked_with_resume` / `handoff_ready` / `scheduled_resume`) are used honestly; `scheduled_resume` only when no higher-importance reachable work or plan step remains this pass. With "drive-by improve everything" (rule 1) as the scope, a genuinely-empty queue is now rare. The terminal signal is unchanged: three consecutive cycles with no new code diff, merged/synced artifact, runtime receipt, narrowed blocker, or queue transition is churn — stop broadening and record the exact resume point. A no-op-with-receipt (a heartbeat that checked fresh state and found nothing agent-reachable) is a *healthy* close, not a failure.

Leo 2026-06-22 verbatim: *"any project i am working on can be yolo and reverted, we can ALWAYS revert … everything and anything driveby improve everything not just the immediate goal."*

---

## Goal Navigation Plans

A Vidux goal prompt is a navigation contract, not a frozen task list. It must
make the next runner faster at choosing the next best move after fresh disk
state is read; it must not pretend to know every future task before the work has
taught us what matters.

The durable chain is:

1. `/goal`, `/loop`, or chat launcher is only a compact pointer into Vidux.
2. The prompt file is also a pointer/control contract, not the goal; it carries
   standing navigation rules, skill bindings, and the mutation rule.
3. `PLAN.md` owns the actual goal: mission outcome, queue state, decisions,
   blockers, evidence, drift, real work rows, exit criteria, and the next action.
4. Matching publish ledger rows carry shipped-cycle proof, handoff status, files
   claimed, path-like claims, and next-agent resume.

Canonical Leo control-plane prompt:
`/Users/leokwan/Development/vidux/prompts/goal-navigation-control-plane.prompt.md`.
Use it when the mission is to improve the goal/prompt/plan primitives
themselves, especially before starting broad long-loop work.

Before long-loop work starts, the goal-navigation plan names:

- mission outcome and explicit non-goals;
- authority chain and first-read rule;
- how to rank work when state changes, not the exact future task list;
- hard-blocker move-on rule: park the blocked row with proof and resume, then
  select the next largest agent-reachable row unless the whole plan has no
  reachable work;
- primitive readiness and proof floors for research, review, visual proof,
  browser/simulator/deploy, vendor tooling, cross-machine access, and skill
  runtime health;
- worktree convergence rule: a worktree is nursed until merged, safely parked,
  or explicitly collapsed; branch/PR transport never replaces plan plus ledger
  recovery;
- prompt mutation rule: update the plan first, then mutate the prompt only when
  the standing instruction changes.
- completion rule: `/goal` and `/loop` keep appending and executing real work
  rows until the Vidux plan's exit criteria are satisfied, or every remaining
  row is parked at a named hard blocker with exact resume proof.

Ownership boundary for this contract:

- **Vidux core** owns the plan/prompt/ledger schema, loop close states, worktree
  lifecycle, proof packet shape, recovery semantics, and the N-agents-one-PLAN
  concurrency contract: leases/claims, disjoint file/path ownership, shared
  progress rows, proof foldback, append/park rules, and resume packets. Vidux
  core does not choose model-specific leader/follower hierarchies.
- **Leo Flow** owns Leo-private routing, skill ownership, the active no-wait
  decision layer formerly split through `/auto`, primitive registry bindings,
  leader/follower orchestration, Codex/Claude/GLM/Grok runner selection,
  headless Codex control, and blocker move-on routing. `/auto` is deleted;
  stale live pointers are repaired at their owning artifact instead of revived
  as a shim.
- **Amp** authors and refines goal-navigation prompts and pointer text; it cites
  Vidux and Flow instead of copying their whole rule banks.
---

## First-Time Setup

NEVER: create duplicate plans, execute local-CI lanes, install LaunchAgents, delete worktrees, or push/merge unless the owning plan AND user authorization make it explicit.

Prereqs: clone the owning repo plus this Vidux checkout, install the repo's declared toolchain, and read local `AGENTS.md`/`PLAN.md` before changing code. For Leo's fleet, use `/leo-flow` for lane/proof routing and live no-wait decisions, and `/ledger` for handoff proof when the active goal asks for them. Load downstream project skills after `/vidux` when the active goal asks; use `/captain` only for skill packaging or mount hygiene.

Verify: resolve the canonical plan path, inspect git state, and run the smallest repo-owned proof command before claiming progress. For local operator work, prefer read-only verified-alive/audit packets before executing lanes or installing LaunchAgents.

## Overlay contract

Vidux is the thin plan/proof control plane. A downstream project skill may route
org-specific requests on top; it does NOT replace the `PLAN.md` plus publish
packet recovery contract. Vidux owns the schema and lifecycle for plan state,
decision logs, proof packets, checkpoints, resume semantics, and browser
projection. Downstream skills own local policy and product-specific routing.
Leo Flow owns model/runner selection and leader/follower foldback. If local
policy contradicts core plan/proof/checkpoint semantics, fix the local policy.

## Activation & Triage

Vidux is the universal entrypoint. Drop into any repo. Read the room. Run the right lifecycle. At expedition scale, shift into plan-first multi-session work; at smaller scales, execute the stage playbook directly.

### Fast-exit triage (trivial requests stop here)

Before any detection, check if the request is trivially answerable inline. If ANY apply, respond with 2-3 options inline and STOP — do NOT invoke brainstorming, planning skills, or heavy routing:

- ≤50 words AND names copy/wording/naming work. Triggers: `tagline`, `hero`, `CTA`, `copy`, `wording`, `name`, `naming`, `rename`, `headline`, `subtitle`, `blurb`, `caption`, `alt text`, `commit message`, `title`.
- A single factual question ("what's the flag for X?", "where does Z live?").
- A quick refinement on prior output ("shorter", "different angle", "punchier").

Routing-layer enforcement: routing fires before repo-local "respond with 2-3 options" rules, so brainstorming chains do not spin up for one-line asks.

NOT for: expedition-scale work, multi-file changes, production-code edits, or anything framed "plan first" / "think through" / "design." Those bypass triage and load full vidux.

### When vidux activates

Full vidux loads when:

- User says `/vidux`, `vidux`, `plan first`, `quarter project`, `big project`, or describes multi-session work.
- An existing `PLAN.md` (inline or in the `vidux.config.json` plan store) already governs the work.
- User asks to create/manage a lane/automation/cron (load `guides/automation.md` alongside).
- Work touches 5+ files, needs phases, or is multi-session.

### When vidux does NOT activate

- Single-file changes with obvious cause.
- Anything under 30 minutes with a clear root cause.
- Trivial requests that passed fast-exit triage.

For requests in between (substantive but small), the stage playbook handles it directly without a PLAN.md — see `## Stack & Stage Routing` below.

---

## Five Principles

### 1. Plan first, code second

PLAN.md is the planning authority for queue, decisions, constraints, Progress/Drift record. Code derives from plan state: to change code, update the plan first. To claim a shipped cycle, pair the plan update with the publish packet.

Every plan entry cites evidence — a codebase grep, PR comment, design-doc quote, team chat. A plan entry without evidence is a guess; guesses cause rework.

### 2. Design for interruption

Every session ends; context is lost; auth expires. Durable recovery lives in repo files + append-only ledger rows, NEVER in chat memory. Checkpoints are structured plan/ledger packets, not freeform summaries.

After any interruption: re-read PLAN.md and evidence/ from disk, then check the ledger for the latest publish or handoff packet. NEVER trust summaries or memory for plan details.

### 3. Investigate before fixing

Bug tickets are not line items. Before coding, map root cause, related surfaces, impact. A fix without investigation is a guess.

When 2+ tickets touch the same surface, bundle them into one investigation producing a root-cause analysis, impact map, and fix spec. Investigation notes live locally in the working tree until the fix ships. No investigation PR, no evidence PR, no plan-flip PR. The unit of progress is code change.

### 4. Self-extend with a brake

Agents add tasks they discover: fixing a bug, log related bugs; adding a feature, log edge cases.

But a shipped surface that works is done — stop polishing, move to the next gap. Polish on a done surface while the mission has gaps elsewhere is procrastination. Re-extend plans only when investigation reveals new surfaces, not for one more tweak on a finished surface.

**Evidence changes mid-cycle → the queue re-sorts.** Observed user behavior, a failing deploy, a new PR comment can reorder what's next. Reorder without permission; note it in the next Progress entry so future agents see why. When implementation deviates from plan, run `vidux drift` (or `scripts/vidux-drift-log.py`) to record planned/actual/why/plan-update/prevention-hints/subplan-mirrors before continuing. Add a prevention hint when a drift has a preventable pattern so cache suggestions stop the same miss before code changes.

### 5. Prove it mechanically

Never assert "it works." Run the build, run the tests, show the screenshot. UI definition-of-done is a visual proof, never just "the build passes."

For Leo's FirstBite repos, GitHub Actions is not the runner for unit, UI, E2E,
or expensive regression proof. Use repo-owned local-ci lanes, Moussey-held
evidence, local simulator/browser/device runs, and result bundles. If a needed
local lane is missing, plan and ship the local-ci/Moussey improvement before
routing proof back through GitHub Actions.

When applying that policy, audit `.github/workflows` directly. Convert any
PR/push unit, UI, E2E, matrix, or expensive regression workflow to a
`workflow_dispatch` pointer that names the local-ci/Moussey proof route. Cheap
lint, mergeability, metadata, or security checks may remain only when they do
not run those suites or burn meaningful runner minutes.

If the change reaches a **deployed surface**, proof is hitting the LIVE surface — not the merge, upload, or ledger row. A merge is not a deploy; an upload is not a release. Verify the live route/worker/build serves the new code (`curl <route>/api/health` returns the merged SHA; a worker fetch returns the new version; a mobile build number reaches "ready to test"). Can't verify the live surface? Leave the row `[in_review]`, record `deploy unverified` with the exact check command — never mark it done.

When an audit or grep produces a count or classification, **spot-check at least one entry per category** before deciding on it. A grep hit is a lead, not a fact:
- A "git push" line may be a prohibition ("NEVER git push"), not an instruction.
- An automation classified "push-capable" may operate on a non-git directory.

Validate before you plan; plan before you code.

After a failure, produce two artifacts: a **code fix** (the immediate repair) and a **process fix** (a hook, test, constraint, or plan update). The process fix is the valuable output — it makes the system smarter next time.

A scaffold PR that leaves skipped tests for a "pending" served path: the follow-up PR wiring the path MUST activate those tests or delete the placeholder rows. No stale skips.

**Progress is code change.** A PR touching only `PLAN.md`, `investigations/`, `evidence/`, or `INBOX.md` with no source change is bookkeeping, not progress. Bundle plan updates into the code PR that ships the fix, or keep notes local until a fix is ready. Standalone "flip row to [completed]", "reconcile Phase N", "audit already-delivered", and "investigation closeout" PRs are prohibited. A cycle that produces no code produces no PR and no commit — notes stay on disk for the next cycle.

---

## Working Defaults

Tactical defaults from 30+ plan files across 5 repos. They apply everywhere, regardless of stack or stage.

### Flow with the water

- Read existing code before writing new code.
- Match the repo's patterns, naming, DI approach, test style. Discover architecture and extend it; don't impose. Factory DI → use Factory; manual injection → use that.
- For doc/PR/diagram tone drift, use repo-owned examples or style guides when they exist; do not invent a new voice from scratch.
- Skill/documentation expeditions: artifact changes are the product. Update PLAN, source ledger, examples, and owning skill hooks each pass.
- Do not mark a broad loop complete just because the first useful artifact exists. Close it only after floor requirements, verification, and stop condition are met.

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
- Before coding a similar task, apply any cache-backed drift prevention suggestion that matches the current task.

### Lean plan dirs

- A plan dir holds current state, decisions, and pointers — nothing regenerable. Never let a `venv/`, `node_modules/`, build output, or large binaries live inside a plan dir; gitignore them and don't create them there. (A regenerable virtualenv once accounted for ~98% of a plan dir's size — a one-line delete, zero knowledge lost.)
- `projects/*` (or the equivalent scratch tree) stays gitignored; only allowlisted, tracked artifacts are committed.
- Trimming a bloated plan is a first-class chore, not cleanup-when-it-hurts. A plan that has grown to thousands of lines of completed rows + drift logs should be rolled up to current truth; archive or delete the history rather than carrying it.

### Lean on the fact cache

- Durable facts belong in the local fact cache for recall, not in proliferating scratch docs. The plan references them; it does not re-state them.
- Scratch (drafts, reviews, receipts) is deletable once its conclusion is in the canonical doc + the fact cache. Capture the unique fact first (bookmark it), then delete the file — knowledge survives, footprint drops.

### Don't strand; remote is canonical

- A cycle that edited skills, docs, or durable artifacts ends committed-or-stashed — never silently uncommitted across sessions. Uncommitted work is invisible to the next session and the next machine.
- On multi-machine work, the remote is the source of truth. Push durable work the same cycle, or treat it as at-risk; a "pull weekend" reconcile is the symptom of work that was left local.

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

## Worktree Lifecycle Contract (WLC)

Every git worktree moves through four states and MUST transition out of the first three. Leaving one stuck is the exact bug that produced **34 orphaned worktrees + a 12-branch unmerged graveyard** across the Resplit fleet (see `resplit-ios/.cursor/plans/WORKTREE-RECOVERY-2026-06-14.md`: 81 worktrees enumerated across 4 repos, 12 held genuinely lost work, all force-recovered to `recover/*` branches but left UNMERGED). The lifecycle is the contract; the GC pipeline is its enforcement — doctrine without a reaper is exactly how the graveyard grew.

1. **CREATE → register.** Create ONLY off `origin/<trunk>`, **into a CONTAINED path — `<repo>-worktrees/<name>/` (preferred, already GC-classified), `<repo>/.claude/worktrees/`, or `/tmp/wt-*`. NEVER directly under a scan root like `~/Development/`.** A worktree at `~/Development/<name>` has a `.git` *file* that the ledger discover scan mis-reads as a repo root, re-enumerating the parent's whole worktree set N× and polluting repo discovery (an ad-hoc campaign's 17 `~/Development/sy-*` strongyes checkouts caused a ~17× rescan + a 53s→8s GC slowdown, 2026-06-20). Always pass an explicit contained absolute path to `git worktree add` — never a bare short slug. Log the creation to the ledger (`~/.agent-ledger/activity.jsonl`) with repo + branch + purpose. Pre-flight budget: if a repo already carries more than ~12 reapable orphan worktrees, run the GC sweep BEFORE adding another — don't grow the graveyard.
2. **WORK → disposable scratch.** The worktree is a short-lived integration helper, never the source of truth (Trunk-First Rule).
3. **LAND → same cycle, no open-ended deferral.** The branch is EITHER merged to trunk OR pushed to origin WITH an open draft PR. "Pushed but no PR" (`unmerged_no_pr`) is a BANNED terminal state. A `recover/*` branch is a 72-hour ticket — open a PR, cherry-pick onto current trunk, or log an explicit `ABANDONED: <reason>`; it is never a permanent parking lot.
4. **TEARDOWN → reclaim.** Once landed, `git worktree remove` + delete the local branch + `git worktree prune`. A plan row / lane / task is NOT done while its work exists only as local worktree state.

**Enforcement:** the `ledger` skill's `worktree_gc.sh` pipeline is the SINGLE cross-repo reaper of record, run by the `com.ai.worktree-gc` LaunchAgent every ~20 min — that cron IS the enforcement (a fast cached SessionStart warning hook exists but is an optional manual opt-in, not auto-wired). GC auto-removes ONLY provably-safe trees (clean / merged / on-origin); trees with unpushed commits, a detached HEAD not merged to base, uncommitted changes, or an unknown source are LISTED for the owner, never auto-deleted. `vidux-worktree-gc.py` is the planning/classifier layer that feeds this reaper — see the Worktree GC mechanics below.

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
             Then CLASSIFY the task: atomic (one PR, nameable diff) -> code it.
             Compound (3+ files / unclear root cause / multi-step) -> spawn a
             sub-plan FIRST (see "The decomposition gate" below). No inline sprawl.
ACT        -> Execute tasks until queue empty, blocker, or context budget.
             Empty queue? Scan INBOX, owned paths, git log, blocked tasks. Anything
             found becomes [pending] and runs this cycle. Nothing found? Checkpoint and exit.
VERIFY     -> Build, test, gate. If the repo declares CANON terms (e.g. a
             vidux.config.json `canon_terms` / CANON.md, or approved entity
             names), grep the diff + touched plan rows for retired aliases
             before CHECKPOINT — a hit blocks completion. Citation-only canon
             ("use the right names") is insufficient; a stale agent drifts, an
             executable grep gate does not.
CHECKPOINT -> Update the plan/queue note, emit the publish packet, then
             commit/push only after those breadcrumbs exist. Reconcile planned
             vs actual; use `vidux drift` if they diverge.
COMPLETE   -> Close the local worktree lifecycle or record why it remains.
```

### Read the Room (READ-phase checklist)

Before touching code, check these eight surfaces in order:

1. **`AGENTS.md` / `CLAUDE.md` / repo instructions** — these override everything.
2. **`ai/skills/hooks/`** — repo-specific build/test/lint commands.
3. **`.cursor/plans/`** — existing plans for this feature or related work.
4. **`RALPH.md`** — repo-owned queue contract for recurring loops and nurse passes.
5. **The ledger** (`~/.agent-ledger/activity.jsonl`) — recent entries from other agents, active lanes, waiting handoffs. Repo-local `.agent-ledger/` is optional companion state only when documented.
6. **Memory files** — ownership boundaries, lane assignments.
7. **Neighboring files** — match existing patterns; don't impose new ones.
8. **`vidux.config.json`** — resolve the authority `PLAN.md` before anything else.

Ad hoc scratch files (e.g. `<repo>-loop-state.md`) are optional helpers; they do not override the repo's queue, ledger, or checkpoint files unless the repo says they are canonical. NEVER read another repo's queue files, nurse logs, or ledger when selecting work for the current repo.

**Crash recovery:** If `git diff` shows uncommitted work from a dead session, preserve it first: identify the touched files, classify whether the work belongs to the current plan row, record the recovery path in the owning plan + a ledger handoff before any commit/push/cleanup. NEVER commit, overwrite, or discard unknown WIP just to clean the tree.

**Stuck detection (adaptive):** If the same task appears in 3+ Progress entries while still `[in_progress]`, stop retrying. Switch surface — move to the next unblocked task, mark the stuck one `[blocked]` with a one-line Decision Log entry of what was tried. No human hand-off; the next cycle finds new evidence (observed signal, new PR comment, queue re-sort) or the task stays blocked until replaced. The brake prevents forever-loops; it is not a human approval gate.

**Push authorization:** Operational PR-branch pushes are safe without asking only after the owning PLAN.md row/Progress/Drift Log is updated AND `ledger-emit.sh --event publish` records the publish packet. Open PRs ready-for-review by default so review bots run; use draft only for true WIP with a missing gate. Draft PRs are publish actions too. Direct-to-main requires explicit authorization + the same publish propagation before push/merge. Destructive operations (force push, branch delete, `git reset --hard`) require explicit per-action authorization. A lane prompt saying "NEVER push" without qualification still allows a normal publish-propagated PR-branch push; parking on a local branch wastes cycles.

### Trunk-First Rule

Vidux defaults to trunk-first:

- Start from the current trunk branch in the canonical checkout. Prefer `main`; if a repo hasn't renamed its trunk, detect and use the actual one — don't force a broken assumption.
- Create short-lived branches/worktrees from the trunk head only when isolation helps. **When 2+ agents may touch the same repo, an isolated worktree off `origin/<trunk>` is MANDATORY — never edit, commit, rebase, or reset the shared trunk checkout a sibling may hold.** A fresh worktree has no `node_modules`/`vendor` — run the repo's install (`npm ci` / `bundle install`) BEFORE the first commit, or husky/lint-staged hooks revert the work; never `--no-verify` to dodge that.
- Treat lane branches/worktrees as disposable integration helpers, not the source of truth.
- Before a job is done, every intended change MUST be merged or cherry-picked back into trunk in the canonical tree, with publish propagation recorded in the owning plan row + publish packet.
- Run the final proof, release gates, and ship/deploy commands from that merged trunk state. If they publish externally, record the plan + ledger propagation before claiming done.
- Do not end a job with required work stranded in a side branch/worktree unless a real external blocker prevents merge-back; if so, the carve-out MUST produce a tracked 72-hour ticket — an open PR against the unresolved question OR an explicit `ABANDONED: <reason>` note in the owning plan + ledger. Silent indefinite deferral on a local branch is banned (it is the `unmerged_no_pr` state the WLC forbids); record the exact blocker and unmerged branch either way.

**Worktree lifecycle:** This is the operational form of the **Worktree Lifecycle Contract (WLC)** above — see it for the four states and the BANNED terminal states. The `ledger` skill's `worktree_gc.sh` pipeline (`com.ai.worktree-gc` LaunchAgent, 20-min sweeps) is the SINGLE cross-repo reaper of record. `python3 <vidux-dir>/scripts/vidux-worktree-gc.py --base origin/main <repo>` is the per-repo planning/classifier layer that feeds (or defers to) that reaper — run it before starting new lane work or leaving a branch behind to classify the tree. `merged_clean` is the only guarded cleanup bucket; the top-level `cleanup_decision` says whether guarded removal is available, owner approval is required before apply, or owner review is still required. `--owner-review-markdown` produces a handoff packet for non-removable rows with per-row `review_command` commands, last-activity evidence, and the exact `merged_clean` rows in guarded cleanup. `cleanup_decision`/`safe_cleanup_items` carry `cleanup_approval_status=required_before_apply` — read-only evidence until the owner approves the concrete paths. `open_pr` is durable handoff (nurse or record); it can come from a local branch name or a detached checkout whose `HEAD` matches the PR head SHA. `dirty`, `closed_unmerged`, `unmerged_no_pr` are not cleanup — they require inspect/stash/commit/escalate, PR creation, absorption, or an explicit abandoned note. A task is not done while its work exists only as unrecorded local worktree state.

**Build/test ownership in multi-agent repos:**

- Do not burn GitHub Actions minutes for unit/UI/E2E proof in Leo's FirstBite
  repos. Local-ci and Moussey are the proof authority unless the active plan
  names a narrow exception.
- Treat build/test execution as a serial lane unless the repo documents a safe parallel workflow.
- When the ledger shows active parallel lanes, nominate one build owner before verification churn.
- If multiple isolated proofs are unavoidable, give each lane its own `-derivedDataPath`; avoid shared package/bootstrap churn.
- If `.mise.toml`, `.tool-versions`, installed CLIs, and skill docs disagree, resolve version authority before trusting command examples.

**Plan discovery before plan creation:** Before opening a new PLAN.md (or heavy research that would produce one) for any lane, `grep -ri <topic-keyword>` across your configured plan stores — `plan_store` path from `vidux.config.json`, any `external_plan_roots`, repo-inline `PLAN.md`, and the conventions (`<repo>/ai/plans/<slug>/`, `<repo>/.cursor/plans/`, `<repo>/projects/<slug>/`) — plus memory entries referencing existing plans for that surface. `vidux-browse` sidebar filter box covers the same ground from the UI. If a same-surface plan exists, append; never create a sibling. Evidence: a cold second session skips the check, rebuilds weeks of receipts, and ships duplicate placeholder PRs that must then be reconciled and closed.

**Cross-session collision detection:** When multiple Claude/Codex sessions may run concurrently against the same repo, check `~/.agent-ledger/activity.jsonl` for recent entries (last ~72h) keyed on the same lane keyword before heavy research. A cold second session is the highest-risk path to a duplicate plan; a 30-second ledger grep is cheaper than re-discovering the prior session's receipts.

### Queue order

Tasks are processed with these rules:

1. **[in_progress] always resumes first** -- a prior session died mid-task
2. **Dependencies resolve before dependents** -- `[Depends: Task N]` blocks until N is `[completed]`
3. **Pick the highest-impact unblocked task** -- strict FIFO is the default, but re-sort when new `[Source: observed]` evidence or a Decision Log entry changes priority. Note the reorder in the next Progress entry; you don't need permission to reorder.

---

## Harness Contract

Every recurring or long-running entrypoint (cron, /loop, /goal, heartbeat, fleet lane) MUST satisfy this contract. Amp mints entrypoints; this section owns the invariants those entrypoints cite.

1. **No state in the prompt.** The prompt holds only durable instruction — NEVER task numbers, branch names, blockers, or cycle snapshots. Cron agents are stateless; a "T3 is next" prompt is stale by the next fire (Principle 2).

2. **One Authority Store.** Exactly one absolute PLAN.md path; the runner rehydrates from it fresh each cycle and records all state changes there. Two sources of truth diverge silently.

3. **Cycle skeleton: Orient → Choose → Execute → Handoff.** Read store + repo state; pick ONE bounded unblocked row; do the work with verification; write progress/decisions back; exit clean. Plural scope makes agents cherry-pick easy work.

4. **Stop condition + cycle cap — mandatory.** Name what "done / park the lane" looks like AND a max-cycle (or token) cap with stuck detection (same row touched N consecutive fires → halt and flag). When every remaining row is gated outside the lane's write scope, parking with a Closeout is the SUCCESS state — never grind against a gate to satisfy a meter. Loops without stop conditions end only when a human notices ("overbaking").

5. **Disjoint write scopes for concurrent lanes.** Every lane declares the paths/fields it may write; two lanes NEVER share a write scope or a live feature branch. Check `git status -sb` before writing to any repo a sibling may hold. Isolation is what makes parallel lanes safe.

6. **Smoke check at cycle start.** Before choosing work, verify the lane's ground truth holds (auth alive, branch state expected, store readable), including re-checking recorded gates — they clear without notice. Degrade to an explicit blocker note; never silent-skip. A cleared gate left unchecked strands unblockable work.

7. **Closeout per cycle:** decision, risk, blocker, next action — written to the Authority Store. Proof receipts live in the store, not the prompt; the human-facing line helps the reader decide (Closeout Gate stays in /amp). A reader continuing the lane needs decision/risk/blocker, not self-attestation.

8. **CONVERGENCE & FINDABILITY — done means merged + findable, nothing less.**
   This is the done-state contract. It is the canon amp / leo-flow / ralph cite;
   they point here, they do not redefine it.

   - **The status ladder is a strict ladder, not a synonym set:**
     `branch_pushed < pr_open < merged < findable`. You may only claim the rung
     you can prove. **"done" / "complete" is NOT a status** — it is deleted from
     the vocabulary. A row stamped `merged` requires a merge SHA reachable from
     trunk; a row stamped `findable` requires a build/URL locator on top of that.
   - **Findability gate.** A task is `[completed]` ONLY with BOTH (a) a merge SHA
     reachable from `origin/<trunk>` AND (b) a typed `[Findable: …]` field naming
     exactly where Leo opens it:
     `- [completed] <task> [Findable: merged <sha> -> TestFlight build N | prod URL | preview URL | "in main"]`
     A green draft PR is `pr_open`, never `[completed]`. A `[completed]` row whose
     change is not in trunk is a contradiction — reject it.
     *Findability is ONE typed field a tired human will actually fill, not a form.*
   - **Honest-status rule.** The words **shipped / done / live / complete /
     landed** are RESERVED for changes MERGED to trunk. For unmerged work the only
     legal status words are **drafted / in review / stranded / pending merge**.
     Say "draft PR #N, unmerged" — never "shipped" — until a merge SHA exists.
   - **Convergence-pass trap (anti-fragmentation brake).** When **> 3** branches
     in a repo are stranded (pushed but unmerged) for the lane, the next
     READ/orient phase MUST run a convergence pass — DRIVE the mergeable ones to
     trunk — BEFORE fanning out any new feature work. This is symmetric to the
     Anti-Loop 3-strike brake: that one stops over-polishing, this one stops
     over-spawning. Threshold default is **3** (conservative on purpose — never
     tighten it to 1 and put the lane offline).
   - **Stacking discipline.** If you branch off an UNMERGED base, you OWN driving
     that base to merge OR integrating both into one branch before handoff. Track
     merge order (`merge #889 then #891`). A feature stranded behind another
     unmerged draft is born `[blocked: base #N unmerged]` and is never
     `[completed]`. Never strand a feature behind an unmerged base on handoff.

   *Why block 8 exists: the system optimizes fan-OUT and had no fan-IN. Every
   literal gate could be satisfied by a green draft PR + a `COMPLETE` claim, so
   "built but never merged" features stranded where Leo couldn't find them. The
   ladder + findability field + convergence trap make convergence structural,
   not narrative. See `## Trunk-First Rule` (every change merged before done) and
   Principle 5 (prove the LIVE surface).*

Completion claims are governed by the Evaluator Gate (see PLAN.md template:
`Accept:` criteria + `[verify]` status flow) — a generator never flips its own
row to done — AND by block 8 above: the evaluator may flip to `[completed]` only
when a merge SHA and a `[Findable: …]` locator both exist.

---

## PLAN.md Template

**Every project has exactly ONE PLAN.md.** Course corrections — even pivots — update the existing plan's Decision Log; they do NOT spawn a sibling plan store. A new plan justified by "clean slate," "emotional separation," or "this rewrite deserves its own home" is fabricated reasoning. Instead:

1. Open the existing PLAN.md.
2. Add a `[DIRECTION]` entry to the Decision Log.
3. Mark now-obsolete tasks `[blocked]` with a pointer to the new direction.
4. Append the new direction as fresh `[pending]` tasks in the same queue.

New plan stores are for new PROJECTS (different codebase/product/problem surface), not new OPINIONS about the same project. "Rewrite project-X from scratch" and "polish project-X" are one project, one plan. "Build a new iOS app" and "ship the web app" are different projects, different plans.

Planning can happen in the agent's main thread. What matters is WHERE the output lands: the existing PLAN.md, always.

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
  Accept: testable criteria written at PLAN time (commands + expected outcomes — "works" is not a criterion)
- [in_progress] Task 2: description [Evidence: ...]
- [verify] Task 3: generator finished; awaiting evaluator verdict
- [completed] Task 4: description [Evidence: ...]
- [blocked] Task 5: description [Blocker: ...]

**Evaluator Gate:** every task row carries `Accept:` criteria written at plan
time. Status flows `[pending] → [in_progress] → [verify] → [completed]`. The
generator's authority over status ENDS at `[verify]` — only an independent
evaluator verdict (the `evaluator` agent: read+execute tools, re-runs the
Accept commands itself, never reads generator prose) flips `[verify] →
[completed]`. A FAIL loops the row back to `[in_progress]` with the judge's
reasons appended as the next work item. Test-weakening (skipped tests, loosened
assertions) is an automatic FAIL regardless of pass counts.

Inside ## Tasks, every line starting with `- ` MUST be a task with a
status tag. Use numbered lists (1. 2. 3.) or headers for non-task
content like rollout strategies or phase preambles.

Status FSM: pending -> in_progress -> [in_review] -> [merged] -> completed
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

`[merged]` is the convergence rung between `[in_review]` and `[completed]`
(Harness Contract block 8). A feature-class row may reach `[completed]` ONLY
once its change is merged to trunk (a merge SHA reachable from `origin/<trunk>`)
AND it carries a typed `[Findable: …]` locator. A green draft PR is `pr_open`,
not `[completed]`; an `[in_review]` row with an open/draft PR has NOT converged.
Non-feature rows (docs/config/refactors that never produce a user-openable
artifact) skip `[merged]`/`[Findable]` and use the existing gates.

**`[ETA: Xh]` — optional AI-hour estimate.** Completion (X/Y tasks done) is the headline; ETA is supplementary. Use it when tasks are similar-sized and the sum gives a meaningful "AI-hours remaining" read; skip it when tasks vary and the sum becomes fiction. An AI-hour is focused AI-agent work end-to-end, not wall-clock. Calibration: 0.25h trivial / 0.5h simple fix / 1h small feature / 2h moderate / 4h e2e bug / 8h+ multi-phase (promote to compound). ETAs are elastic — log scope moves in `## Decision Log` and update the tag. `/vidux-status` sums ETAs on pending + in_progress tasks; the sum is informational, not a contract. Completed + blocked tasks need no ETA (terminal for this calibration).

## Decision Log
Intentional choices that future agents must not undo.
- [DELETION] [date] Removed X. Reason: Y. Do not re-add.
- [DIRECTION] [date] Chose X over Y. Reason: Z.

## Drift Log
Optional. `vidux drift` records planned/actual/why/plan update/next/subplans
and optional Prevention hints. Cache suggestions are derived from local drift
history, not chat memory.

## Progress
Living log updated each cycle. Unexpected findings, concerns noted during
execution, and reorder notes all live here — no separate Surprises or Open
Questions section. If a finding needs a task, promote it to a task.
- [Date] What happened. Next: what's next. Blocker: if any.
```

---

## Quarter-Sized Projects

Vidux is designed for projects spanning days to months. A quarter project has:

- **A top-level PLAN.md** with mission, phases, current tasks.
- **Sub-plans in `investigations/`** for complex surfaces needing root-cause analysis before code.
- **Evidence snapshots in `evidence/`** backing plan decisions (`YYYY-MM-DD-<slug>.md`).
- **An `INBOX.md`** where humans or external tools deposit findings.
- **A Progress log** any agent can read to understand where things stand.

The plan LIVES — updated every cycle, not written once and followed blindly.

### The decomposition gate

**Before you touch code, classify the task. Compound work spawns a sub-plan first; atomic work ships direct.** This keeps a vidux project resumable — a compound task done in your head leaves no artifact for the next agent (or the next you, after a context reset).

The test is one sentence: **can you name the exact diff before you start?**

| Signal | Classification | Do this |
|---|---|---|
| One PR. You can name the file(s) and change in a sentence. No open root-cause question. | **Atomic** | **Code it directly.** Do NOT spawn a sub-plan. Most tasks are atomic. |
| Any one of: 3+ files in play • unclear root cause • an ordered multi-step sequence with step dependencies • a sub-stream that ships on its own • "I need to think before I touch code." | **Compound** | **Spawn a sub-plan FIRST** (an `investigations/<slug>.md` or a child `PLAN.md` — see two modes below). Parent task stays `[in_progress]` and cites it (`[Investigation: …]`). No inline sprawl, no chat-only step list. The thinking lands in the sub-plan; code ships *with* it. |

**The sub-plan is a CHILD, never a SIBLING.** This keeps the gate compatible with "every project has exactly ONE PLAN.md":

- New work on a surface → **append a task** to the existing parent PLAN.md.
- A compound task within it → **nest a child** (investigation file beside the parent, or child PLAN.md with a `> Parent:` backlink).
- A second same-surface plan with no parent link is the forbidden sibling — in BOTH directions. Everything hangs off the one parent: appended as a task, or nested as a child. Nothing floats beside it.

**Why the gate, not "nest everything":** mandatory nesting buries the queue in bookkeeping and violates Principle 5 (no plan-only PRs). Atomic ships fast; compound gets the artifact it needs. Unsure? Can't name the diff → it's compound.

**Scope of the gate — two distinctions:**

- **Gate ≠ activation.** The gate structures a task you've already committed to *inside* a vidux project. Whether a standalone request needs a PLAN.md is the separate "Activation & Triage" question (multi-session / 5+ files / explicit plan-first). A 3-4 file change *under an existing plan* is compound → sub-plan; the same change as a one-off with an obvious cause may not pull in vidux at all.
- **Decomposition is for unfinished work.** If the surface already ships and works, the Principle 4 brake fires first — stop polishing, move to the next gap. "Think before I code" nests genuine unfinished work; it is not a license to re-open a done surface as an investigation.

### Two nesting modes

Two nesting shapes — pick the one that fits:

**1. Investigation (1-level, for one compound task needing root-cause work)**

The parent plan task delegates its deep work to a child investigation file:

```markdown
- [in_progress] Task 3: Fix payment flow [Investigation: investigations/payment-flow.md]
```

One parent plan, one child investigation per compound task. The investigation file lives next to the parent plan and is consumed when the parent task ships.

**2. Sub-plan rollup (N-level, for multi-phase missions with parallel sub-streams)**

Multiple sub-streams shipping in parallel — each with its own task list — use child PLAN.md files with a Parent backlink at the top (either form):

```markdown
> Parent: vidux/projects/big-mission/PLAN.md
**Parent:** vidux/projects/big-mission/PLAN.md
```

`vidux-browse` parses these backlinks into a parent → children tree with recursive aggregate stats: the parent shows BOTH its own progress bar AND a rolled-up bar across every descendant. Sidebar indents children; cycle-safe via visited-set.

Use this for 5+ child plans that ship independently (e.g. `T1-*/PLAN.md` through `T9-*/PLAN.md`), not for trivial nesting where an investigation file would do.

**Choosing** (once the gate says "compound"): investigation = "think before I code, one task." Sub-plan rollup = "many sub-streams ship independently, want a consolidated dashboard." Default to the investigation file; promote to a child PLAN.md only at 5+ independent sub-streams.

**How it works:**

1. **You write the investigation file first.** `investigations/payment-flow.md` has the seven sections of the `## Investigation Template` (below), filled bottom-up: Reporter Says and Evidence first, then Root Cause / Impact Map / Fix Spec / Tests / Gate each `(pending)`.

2. **The parent task stays `[in_progress]`** while the investigation is active. Each cycle fills one `(pending)` section. No PR opens during investigation — the sections live on disk.

3. **The fix ships with the investigation, as one commit.** When Fix Spec + Tests + Gate are all done, the code lands and the parent task flips `[completed]`:

   ```
   - [completed] Task 3: Fix payment flow [Investigation: investigations/payment-flow.md]
     [Fix: src/checkout/submit.ts:42, src/checkout/retry.ts:18] [Shipped: <commit sha>]
   ```

4. **The investigation file stays forever.** It records *why* the fix looks the way it does. Future agents touching the same surface read it before acting. Archived by age (180+ days), never by "task done."

**Four rules the example illustrates:**

1. **No Fix Spec = no PR** (steps 1-3 above).
2. **Parent status follows child status** — parent can't flip `[completed]` while any `(pending)` section remains.
3. **Decision Log stays in the parent PLAN.md.** Investigation captures *why this bug happened*; parent Decision Log captures *why we fixed it this way*.
4. **Atomic ships direct; compound nests** (the gate table). One-sentence-diff test is the tie-breaker; reserve nesting for 3+ files / unclear root cause / multi-step / independent sub-stream.

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

- `mode: "inline"` — plans live in the current repo as `PLAN.md`. Default when no config present.
- `mode: "local"` — plans live at the configured `path` (one subdir per project). For plans tracked in a separate git repo synced across machines.
- `mode: "external"` — same as local but path may point outside `~/Development`.

Other top-level fields (see `vidux.config.example.json`):

- `version` — config schema version. `"1.0"` is current.
- `external_plan_roots` — optional additional absolute paths to scan for `PLAN.md`. Default `[]`. For plans in sibling repos outside `plan_store.path`.

Agents read `vidux.config.json` at session start and resolve the authority PLAN.md before anything else.

### No external boards

vidux is markdown-plan-first: a `PLAN.md` in git is the only queue authority. There is **no** external-board sync — no third-party board integrations, no adapter-backed inboxes. Plans are read, updated, checkpointed as files. Want a board view? Mirror it by hand; vidux will not round-trip to one.

### Inbox

`INBOX.md` is where humans or external tools drop findings for agents:

- Agents check INBOX.md during READ, before tasks.
- Promote actionable findings to `[pending]` tasks in PLAN.md.
- Annotate non-actionable ones with `[SKIP: reason]`.
- Max 20 entries; if full, oldest archived to `evidence/`.

### Garbage collection

Plan GC is **mechanical, not vibes-based**: thresholds fire, "feels heavy" does not. Run from the plan dir (or pass it as an arg):

```bash
python3 <vidux-dir>/scripts/vidux-plan-gc.py [--dry-run] [--json] [plan-dir]
```

Three operations, one script:

| Target | Rule | Where archived |
|---|---|---|
| `[completed]` tasks in `## Tasks` | Soft cap 30 → archive oldest to 20. Hard cap 50 → archive + exit 2 (coordinator gate). | `ARCHIVE.md` (append-only, timestamped). |
| `investigations/*.md` | mtime ≥ 180 days | `investigations/archive/` (moved, not deleted). |
| `INBOX.md` | Soft cap 20 → drop oldest | `evidence/YYYY-MM-DD-inbox-archive.md`. |

**What stays forever:** `[pending]`, `[in_progress]`, `[blocked]` tasks; the Decision Log; the Progress log (up to the lane's own discretion). Archived investigations remain on disk; the archive subdir is the record.

**When to run:** coordinator lanes include `vidux-plan-gc.py` in their READ step each cycle. `--dry-run` + `--json` gives a pre-check; the live run is idempotent (no-op under caps).

**Exit 2** (hard cap exceeded) is the gate signal: coordinators hold ACT and note the bloat in the next checkpoint — the plan needs attention beyond archival (too many completed tasks not split into phases, or Phase rollover overdue).

Worktree GC is separate from plan GC. **There is one reaper of record, not two:** the `ledger` skill's `worktree_gc.sh` pipeline (`com.ai.worktree-gc` LaunchAgent, ~20-min sweeps) is the SINGLE cross-repo actor that actually removes trees. `vidux-worktree-gc.py` is NOT a competing reaper — it is the per-repo planning/classifier layer that classifies local git worktrees by branch/PR state and feeds (or defers to) the ledger reaper. It never owns the cross-repo sweep:

```bash
python3 <vidux-dir>/scripts/vidux-worktree-gc.py --base origin/main [repo-dir]
```

Read-only by default; see **Worktree Lifecycle Contract (WLC)** and **Worktree lifecycle** (under Trunk-First Rule) for the bucket semantics and `--owner-review-markdown` packet. JSON top-level: `cleanup_decision.{guarded_removal_available, owner_approval_required_before_apply, cleanup_approval_status}` and `safe_cleanup_items` (removable rows, `cleanup_approval_required=true`, `cleanup_approval_status=required_before_apply` — read-only until owner approval). After approval, `--apply --yes` removes only `merged_clean` worktrees (clean non-primary, branch merged into base or PR merged) — provably-safe trees only. Dirty / open-PR / closed-unmerged / no-PR-unmerged are reported but never auto-removed by either layer.

---

## Course Correction

The plan is a living document: evidence changes → plan changes → work changes. When something breaks or changes:

1. **Update the plan FIRST** — what changed, why, new direction.
2. **Then update the code** — derived from the new plan state.
3. **Every failure produces a process fix**, not just a code fix.

### Placeholder draft PRs over blocked exits

When a multi-step plan stalls on external unblocks (DM responses, design decisions, sibling-PR merges, latency baselines, AB approvals), the cycle does **not** exit "drained" while agent-doable surface remains. Ship realistic placeholder draft PRs against the unresolved questions with assumptions baked in + documented in the PR body, so the conversation moves on concrete artifacts, not speculative chat.

A placeholder draft PR is still a publish action. Emit the publish packet with `handoff_status=needs_review` (`ledger-emit.sh --event publish` with non-empty `--summary`/`--task-id`/`--plan-path`/`--proof`/`--handoff-status needs_review`/`--resume`/`--file`/`--claim`), record the blocked question + assumptions in the owning PLAN.md Progress/Tasks or Drift Log, then carry that ledger eid into the PR body before `gh pr create --draft`. Defaults: every flag default-off/zero, isolated worktree off `origin/master`, no reviewers, no `@`-mentions. Core owns the publish/proof principle; downstream repos own reviewer taste and merge policy.

### Plan archival pattern (parallel-session reconciliation)

Recovery path when the discovery rule was skipped and a duplicate slipped through. Fold the smaller/newer/less-receipt-dense plan INTO the canonical older one:

1. Append an H2 `## YYYY-MM-DD — Parallel-Session Reconciliation` to the canonical plan listing what the other plan covered, which receipts merged in, which tasks transferred.
2. Move the duplicate plan dir into `_archived/<plan-slug>/` next to the canonical; prepend a SUPERSEDED banner pointing at the canonical PLAN.md. Don't delete — archival preserves receipts and the conversation trail.
3. Close any duplicate placeholder PRs the second session opened with a comment linking the canonical plan.

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

If the user says `/vidux loop`, `loop`, `don't stop until done`, `keep going`, `finish the queue`, or `finish the spec`, enter a persistent outer loop instead of stopping after one slice.

Loop body:

Priority-order full drive, not one-bounded:

1. Disk-first full re-read of queue/PLAN sources + ledger + git/deploy status + receipts.
2. P0 inference by importance (blast radius of largest reachable broken workflow, compounds eligible for planning).
3. Execute or plan (vidux sub-plan for compound) the current highest-importance unblocked item(s) in strict order.
4. Proof, land, drive-by, ladder advance.
5. Repeat inside pass: pick next-highest until no more unblocked priority-reachable work or hard gate.
6. Checkpoint: update the owning plan/queue note, emit the publish packet with proof, handoff status, files claimed, path-like claims, and next-agent resume, then commit + push the owned branch/PR path only after those breadcrumbs exist.
7. Record exact state (full_pass_driven / planned_compound / ...). Do not default-scheduled_resume when planning or higher work is viable.
8. Repeat until the queue/spec is done or every remaining row is parked at a named hard blocker with exact resume proof.

Persistent loop mode is **lane-persistent, not checkbox-persistent**: once vidux owns a feature, surface, or queue lane, keep driving connected follow-on work there until a verified boundary or real blocker. Do not bounce to a second mission because one checkbox landed while the same surface has obvious connected work.

**Queue-source rule:** `RALPH.md`/`ralph.config.json` are repo-level queue contracts. Execute that contract directly in `/vidux loop` and `/vidux nurse`. Do not replace it with an ad hoc shared-state file unless the repo documents that file as canonical.

**Blocking rule:** user-visible work is not done when unit/build gates pass — only after the first viable UI/E2E/manual smoke path passes, or a real blocker is recorded with the exact attempted command/flow. If a screenshot, simulator, browser, preview, or your own eyes reveal visible breakage, interrupt the loop and fix it before continuing status/proof narration. Green identifier tests do not override clipped controls, overlap, illegible text, or off-brand/product-fiction UI.

Stops only for: an external blocker or missing credential; a real product decision that changes implementation; conflicting repo state that would sweep another agent's work; an explicit user redirect. It does NOT stop because one item landed, a test suite passed, a checkbox flipped, a connected regression remains, or only unit/build gates passed without UI/E2E smoke proof.

### Anti-Loop Discipline

These rules apply to `/vidux loop`, `/vidux nurse`, and any coordinated tracking cycle. They are core loop contract, not optional overlays.

1. **3-strike escalation.** Before the next slice, check whether the same blocker, failing command, or surface appeared in the last 3 checkpoints (ledger, plan logs, memory). If so: do NOT retry. Write a one-paragraph escalation into the repo plan or nurse log (what's stuck, what was tried, what the human needs to do); move to the next-highest-value unblocked lane.

2. **Diminishing-returns circuit breaker.** If the last 3 loop iterations produced zero shipped code (only coordination, proof attempts, status updates), say so and either identify the structural reason and escalate, or pick a different surface. Do not pad a stuck run with busywork.

3. **Same-command ban.** Never re-execute the exact command that failed last iteration unless the environment visibly changed (disk freed, process cleared, credential restored) — a concrete observable difference, not hope.

4. **All-blocked early exit.** If every lane is blocked by the same root cause, say so in one sentence and stop. Admitting it in 30 seconds beats restating the blockage from 10 angles.

5. **Compaction survival.** Long sessions can compact or lose chat context. Conversation details become summaries. Therefore:
   - **Before each checkpoint:** write iteration state to durable files + ledger rows: update the owning PLAN.md/Progress or RALPH.md queue, emit the publish packet when work shipped, use repo-local `.agent-ledger/` only for configured companion state. Repo files + append-only ledger rows survive compaction; conversation memory does not.
   - **After compaction fires:** rehydrate from durable files + ledger rows. Read the owning PLAN.md/RALPH.md/repo instructions and the latest matching ledger entry. Do not trust pre-compaction conversation details.
   - **Put durable loop instructions in repo files**, not only in the loop prompt. Repo files are re-read from disk; loop prompts are easy to summarize away.
   - **Use subagents for heavy work inside loops** only when the surfaces are disjoint and the environment has enough headroom. Under pressure, do heavy work inline-sequentially instead of fanning out — degrade, never hard-fail.

### Cron + interactive interleave

When a cron lane is firing AND the user interactively redirects mid-cycle ("revamp X next", "switch to Y"), UPDATE the cron prompt in-place rather than waiting for prior tasks to drain. Two re-arm shapes:

- **Soft re-arm** (redirect EXTENDS scope) — edit the existing prompt's priority order; preserve in-flight task list. The next tick picks up the new priority.
- **Hard re-arm** (redirect REPLACES scope) — `CronDelete` + `CronCreate` with a fresh prompt. Prior cron's working notes stay in PLAN.md as decision trail.

Evidence: ~2s re-arm vs 15-20min full cron-interval drain. Generalizes to any cron + interactive overlap (release babysitters, watcher loops, polish loops).

---

## Nursing Mode

If the user asks you to nurse, watch, or keep an eye on active work — `/vidux nurse`, "keep an eye on it", "watch the hot lanes" — switch into a **supervisory cadence**, not a normal execute-once loop. Nursing means:

- Read the ledger and the active plan/queue on a cadence.
- Track hot lanes, owners, blockers, fresh completions.
- Intervene only when a lane drifts, blocks, conflicts, or unlocks the next queued slice.
- Drive queue items directly when the next slice is unblocked and unowned.

Vidux owns nursing state discipline: supervision reads, queue advancement
records, proof expectations, and plan updates. Ralph remains the repo-level
queue contract (`RALPH.md`/`ralph.config.json`); vidux reads it, selects the
next unowned item, records execution/delegation decisions, checks the ledger,
and writes the weakest truthful state back before deciding what's next. Runner
selection and model-worker foldback stay with Flow or the repo's own runner.

**Repo-level state rule:** nursing state MUST live in repo-local artifacts, not an ad hoc global handoff file. Preferred sources: `RALPH.md`, repo plan docs, repo nurse logs, the centralized `~/.agent-ledger/activity.jsonl` stream, repo-local `.agent-ledger/` only when documented. Per the Read-the-Room scratch-file rule: don't depend on a one-off `<repo>-loop-state.md` unless the repo committed it as canonical, and never read another repo's state when selecting work. Durable handled-state for external signals (e.g. App Store feedback IDs) goes in a repo plan/tracker file next to the queue.

For any timed or repeated supervision, use a concrete repo-owned runner and record its authority PLAN.md, cadence, proof command, and stop condition.

**Cadence selection:**

- Use the repo's declared automation surface for recurring nursing. Vidux core supplies the loop contract; the scheduler can be a local cron/systemd/launchd job, a hosted routine, or a manual session.
- In-session loops suit experimental nursing and short-lived follow-through.
- For **every 5 minutes** or other sub-hourly cadence, use an external scheduler (`launchd`, `cron`, `systemd`) to invoke a narrow nurse task.
- Do not fake timed nursing by spinning a blind idle loop in chat.

---

## Coordination Mode

After detecting stack and stage, determine scale:

| Scale | Signals | Mode |
|-------|---------|------|
| **SOLO** | Quick hit/kickoff/mid-flight. <8 files, single concern, serial by nature. | Execute directly — vidux is the worker. Follow the stage playbook. |
| **COORDINATED** | Expedition-scale. 8+ files, multiple independent concerns, multi-session, cross-tool. | Vidux coordinates state; host tools or Flow dispatch workers. |

**COORDINATED triggers** (any two = coordinate):

- Multiple file sets with zero overlap.
- Work splits into independent API + UI + test concerns.
- User mentions multiple agents, Routines, Cursor, or parallel work.
- Ledger entries show active lanes from other agents.
- PLAN.md has a lane table or multi-phase dependency graph.
- Surface-wide prototype or variant work where each variant lives in its own file.

When coordinated, keep the loop small:

1. Refresh or write the single owning `PLAN.md` with independent lanes, write scopes, proof gates, and resume metadata.
2. Delegate only surface-disjoint work through the current host tool or Flow. Vidux does not choose model tiers or leader/follower bindings.
3. Integrate returned diffs, proof, blockers, and weakest truthful claims back into the one plan.
4. Run cross-surface verification before claiming the parent task.
5. Checkpoint plan plus publish packet if work continues.

### First-class end-to-end proof

For any user-visible change, end-to-end proof is a blocking gate, not a polish task. Preferred order: (1) existing UI/E2E automation for the touched surface; (2) add/tighten focused UI/E2E coverage if the gap is small and the path is stable; (3) manual smoke path when no automation exists. Never declare "done" on build + unit coverage alone. Record the exact smoke command/path run. If smoke reveals more bugs, reopen the queue and continue.

---

## Stack & Stage Routing

Check signal files manually or use the repo's own detector script when one exists:

| Signal | Stack ID | Routing |
|--------|----------|---------|
| `Project.swift` or `*.xcodeproj` | `ios` | Use repo iOS build/test instructions |
| `next.config.*` | `nextjs` | Use repo web build/test/deploy instructions |
| `vite.config.*` (no next.config) | `vite-react` | Use repo web build/test instructions |
| `shopify/` or `*.liquid` | `shopify` | Use repo Shopify/theme instructions |
| `Cargo.toml` | `rust` | Inline (no skill yet) |
| `package.json` only | `node-generic` | playwright if e2e exists |

After stack, detect stage from repo state:

| Stage | Signals | Playbook |
|-------|---------|----------|
| **KICKOFF** | No plan file for this feature, user says "build X" / "add X" | Gather evidence, draft plan, then ship the first vertical slice |
| **MID-FLIGHT** | Existing plan with pending items, branch with changes | Resume `[in_progress]`, reconcile diff, then continue |
| **LAST MILE** | Most plan items done, user says "ship" / "finish" / "polish" | Verify, close blockers, prepare handoff/release |
| **QUICK HIT** | Single-screen change, one-sentence description, < 3 files | Execute directly with focused proof |
| **EXPEDITION** | Touches 5+ files, needs phases, multi-session | Use the full plan-first loop |

Every stage ends with repo-declared verification gates. When no gate exists, define the smallest honest build/test/manual-smoke proof in the PLAN before executing.

For Figma-driven work, prefer repo-local MCP rules over global defaults; preserve them in the repo's `ai/skills/` folder when they are durable project knowledge.

---

## Skill Composition

Vidux delegates; it never duplicates. Universal companion skills may be available in the host environment:

- `clipdiff` — PR-ready diffs.
- `captain` — meta/skill maintenance (audit, symlink discipline). Older `skill-manager` prompts route here.
- `maily` — email cross-referencing.
- `ledger` — cross-tool coordination (critical for coordinated mode).
- `nia` — external doc/package source lookup (check before WebFetch).
- `amp` — prompt amplification for vague tasks (GATHER → steer → fire).

Local skills need no manual "on" switch if the `~/.claude/skills` or repo-local symlink is correct. MCP-backed tools are separate from skills and may still need app-side install/auth.

When a repo has one active feature-reset plan and multiple agents work in parallel:
- Reuse the existing plan; never create a competing plan doc.
- Add a claim line before editing canonical sections or cross-cutting files.
- Append discoveries to the shared coordination log before rewriting product-contract text.
- Treat chat guidance as non-canonical until written back into the active plan.

### Automation Entrypoints

Vidux core is scheduler-agnostic. Use the host environment's approved mechanism for recurring work: local cron/systemd/launchd, hosted scheduled jobs, CI events, manual loops, or another repo-owned runner. The invariant is the same everywhere: each run rehydrates from the authority PLAN.md, does one bounded slice, writes proof back, and exits cleanly.

When wiring recurring work, reference the automation recipes from `guides/recipes/`:

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

Start with the smallest recipe that proves value. Add more only when the PLAN.md and ledger show durable demand.

---

## Checkpoint Breadcrumbs

After every meaningful completed slice, leave all three breadcrumbs:

1. **Plan / queue** — mark progress in the active plan, `RALPH.md`, or queue source, carrying the publish packet fields.
2. **Ledger** — emit `ledger-emit.sh --event publish` (the publish packet); keep the eid with the branch/PR handoff.
3. **Git** — commit and push only the owned slice after the plan + ledger breadcrumbs exist.

Checkpoint at: a meaningful slice completing; before handoff; before changing lanes or worktrees; after an integration fix that creates a new stable base for other agents.

Commit everything the active agent owns, but do NOT sweep unrelated dirty files from other agents by default.

---

## Replaces /superpowers (folded 2026-04-26)

The Anthropic `superpowers` plugin provided 14 process-discipline subskills (brainstorming, TDD, debugging, code review, parallel agents, worktrees, etc.). Core vidux + companion skills already cover those concepts; the plugin is uninstalled. Use this routing table when you'd previously have reached for a `/superpowers:*` skill:

| `/superpowers:*` was for | Use this instead |
|---|---|
| `brainstorming` | Principle 1: plan first. Brainstorm in main thread, then write the PLAN.md before code. Quick brainstorms stay in chat; formalize only when work spans 30+ min. |
| `writing-plans` | `## PLAN.md Template` above |
| `executing-plans` | The Cycle (READ → ASSESS → ACT → VERIFY → CHECKPOINT) |
| `subagent-driven-development` | `guides/automation.md` § subagent dispatch |
| `dispatching-parallel-agents` | `guides/automation.md` § parallel agents (surface-disjoint precondition) |
| `test-driven-development` | Principle 5: write the assertion before implementation when the surface needs regression protection |
| `systematic-debugging` | Principle 3: investigate before fixing. Use `## Investigation Template` for any bug touching 2+ tickets or unclear root cause |
| `requesting-code-review` / `receiving-code-review` | Repo-specific review discipline before merge |
| `verification-before-completion` | Principle 5: prove it mechanically. UI definition-of-done = visual proof |
| `using-git-worktrees` | Worktree lifecycle section above plus repo-specific isolation guidance |
| `finishing-a-development-branch` | Repo-specific merge and release policy |
| `writing-skills` | Use `captain` — owns skill creation, registry, symlink hygiene |
| `using-superpowers` (meta loader) | Removed — vidux loads on `/vidux` or expedition-scale work |

**Rule of thumb:** reaching for a `/superpowers:*` skill means you're already inside `/vidux`'s domain. Read the relevant principle/cycle-step/guide instead of summoning a separate plugin.

---

## Output formats — one-shot HTML decision briefs

For one-shot HTML decision briefs (not ongoing PLAN.md/repo work), use `/editorial-brief` — ships a single-file editorial-magazine HTML artifact to vidux-browse on a trusted-LAN host. Follows /vidux plan-first discipline for research/write, but lands as a self-contained HTML file, not a tracked-in-repo .md plan.

---

## Browser

A localhost web UI for viewing every PLAN.md across the fleet at a glance. Read-only — markdown plan files in git remain the queue/planning authority; the publish packet remains the shipped-cycle proof.

```
vidux-browse              # start server, open http://127.0.0.1:7191
vidux-browse --no-open    # start server without opening
vidux-browse -f           # foreground (stream logs)
```

What it shows:
- Sidebar grouped by repo, with hot/stale/cold pills (≤7d / 7-30d / >30d by mtime).
- Selected plan rendered as markdown, with sibling tabs for sibling `.md` files in the plan dir (e.g. `PROGRESS.md`, `INBOX.md`; per-owner `ASK-<OWNER>.md` supported).
- Named comments on the selected plan tab or artifact, stored separately from source files.
- Anchored annotations: top-bar `Annotate` control or `Cmd/Ctrl+Shift+C`, then click the exact rendered element.
- Filter box across repo / slug / purpose.

Discovery globs: `<repo>/ai/plans/<slug>/PLAN.md`, `<repo>/vidux/<slug>/PLAN.md`, `<repo>/projects/<slug>/PLAN.md`, `<repo>/PLAN.md`.

Stack: Python stdlib `http.server` + plain HTML/CSS + vanilla JS + `marked.js` (CDN). Zero pip deps. Default bind `127.0.0.1`; `VIDUX_BROWSER_HOST=0.0.0.0` enables trusted-LAN read access. Code lives in `<vidux-dir>/browser/`; design decisions and browser roadmap live in the relevant repo plan.

### Ad-hoc artifacts (anytime, anywhere in chat)

A second surface beyond plan-viewing: ad-hoc HTML artifacts any agent drops in from any session. They appear in a top-level "ARTIFACTS" sidebar section (above the repo-grouped plans), decoupled from any plan.

**Two ways to drop an artifact:**

```bash
# Option 1 — file write (any shell)
cat > <vidux-dir>/browser/artifacts/<slug>.html

# Option 2 — POST endpoint (any session with HTTP, no shell)
curl -X POST http://127.0.0.1:7191/api/artifact \
  -H "Content-Type: application/json" \
  -d '{"slug":"<slug>","html":"<!DOCTYPE html>..."}'
```

**Slug rules** (POST-validated): `^[a-z0-9][a-z0-9-]{0,63}$`. Lowercase, dashes only, no slashes/`..`. Same slug overwrites.

**Component CSS shim** — inherit the paper-and-ink palette via these classes (in `static/style.css`):

- `.card-grid` — auto-fill grid container, 280px min column
- `.contact-card` — bordered card with padding; nests `<h3>`, `.meta`, `<a>`, `<p>`
- `.pill .pill-hot/.pill-stale/.pill-cold/.pill-artifact` — status dots
- `.lead-row` — single-row list item with name + tier
- `.person-chip` — pill-shaped inline tag
- `.label` — uppercase mono label (e.g., `<span class="label">hook</span>`)

Artifacts render via direct `innerHTML` into the markdown pane, so anything in your `<body>` works. Trust boundary: localhost + your own filesystem; no XSS surface.

Use cases: research summaries with vendor/lead/contact cards; visual fleet dashboards; cross-session briefings; plan-adjacent visualizations (timeline, network graph, decision tree) without bloating PLAN.md. Drop the artifact, log the URL (`http://127.0.0.1:7191/` → click the slug) if you want to reference it later. Survives across sessions; the slug is the stable handle.

#### Symlinks vs hard links in `artifacts/`

To share content between an artifact and a canonical source elsewhere (single inode), use a **hard link, not a symlink**. The server fails closed on symlinks resolving outside `ARTIFACTS_DIR`: `browser/server.py` `safe_resolve_any()` uses `Path.resolve()` (follows symlinks); an outside target makes `Path.relative_to(ARTIFACTS_DIR.resolve())` raise `ValueError` → **403 forbidden** on `/api/file` and `/api/comments`. Symptom: sidebar shows the artifact but the body never loads; console shows `failed to load comments: forbidden` + a 403.

**Fix — hard link, no `-s`:**

```bash
rm <vidux-dir>/browser/artifacts/<slug>.html
ln <canonical-path>.html <vidux-dir>/browser/artifacts/<slug>.html   # no -s
```

Constraints: same filesystem only (the home volume shares one volume on stock macOS; cross-volume `ln` fails). `Path.resolve()` does NOT cross hard links so the check passes; canonical-file updates reflect instantly. Verify: `stat -f '%i' <canonical> <artifact-path>` — matching inodes prove shared data. Evidence (2026-05-12): a symlinked `artifacts/music-semantic-backend-mvp.html` rendered only H1 + `403`; hard link fixed it. Memory: `reference_vidux_artifacts_hardlink_rule.md`.

### Named comments / annotations

vidux-browse comments are lightweight annotations on the current view, targeting an allowed markdown file (`PLAN.md`, `INBOX.md`, `investigations/*.md`, `evidence/*.md`, etc.) or an HTML artifact.

Key contract:
- Append-only app data in `${VIDUX_BROWSER_COMMENTS_FILE:-~/.vidux-browser/comments.jsonl}`.
- Comments NEVER mutate `PLAN.md`, `INBOX.md`, repo files, task claims, or artifact HTML.
- Cross-machine LAN viewers may comment via the UI, but POSTs must be JSON + same-origin (`Origin`/`Referer` must match the browser host).
- Use comments for human feedback, review notes, annotations, LAN collaboration; use `INBOX.md` only when a local agent needs the note inside vidux state.
- For precise comments: `Annotate` control or `Cmd/Ctrl+Shift+C`, then click the rendered element → a sanitized anchor (selector, label, excerpt, tag, index). The `Target` pill scrolls back. Anchors are best-effort UI pointers, not plan authority. Annotation/filter shortcuts are ignored while typing in inputs, textareas, selects, contenteditable.

### Local plan notes (loopback-only)

To leave a constrained note for the current Mac's vidux plan, use the local plan-note endpoint. It appends to that plan dir's `INBOX.md`; it does NOT edit `PLAN.md` directly.

```bash
curl -X POST http://127.0.0.1:7191/api/local-plan-note \
  -H "Content-Type: application/json" \
  -d '{"plan_path":"~/Development/project/PLAN.md","source":"codex/local","agent":"codex/local","note":"Short note for the next local agent."}'
```

Rejects non-loopback clients: even when bound to `0.0.0.0` for home-LAN reading, `POST /api/local-plan-note` must come through `127.0.0.1`/`::1`. Other Wi-Fi devices can read but cannot write plan notes.

### Optional local audio add-ons

The browser footer has an optional read-aloud player + an optional local-transcription path for voice notes. Both rely on a local Apple-Silicon MLX speech backend that is **out of core scope** — install/wire it from your own overlay or runbook. Core vidux ships the browser client only.

## Voice & Tone

Output should sound like a sharp teammate briefing the user, not a CI pipeline writing a report.

- **Lead with what matters.** What shipped, what's blocked, what you need from the user. Not role labels, file lists, or generic summaries.
- **One warm paragraph beats a 10-row table.** Save structured role breakdowns for ledger entries and memory files.
- **Name things by product meaning.** "Built and uploaded build 622 to TestFlight" beats "iOS Release Lane: shipped."
- **Be honest about nothing happening.** No shipped code → say so in one sentence. Don't inflate coordination into progress.
- **Blockers are requests, not complaints.** "The FX pipeline needs a fresh credential — can you rotate it?" beats "FX Lane: blocked (credential expired)."
- **Ledger, plans, and memory can stay structured** — those are for machines and future agents. The final message to the human is for a human.

Default: terse, concrete, evidence-cited; one decision per paragraph; named files+lines for citations; no hedging; no marketing tone.

---

## Reference Files

Core Vidux references are shipped as docs and guides in this repo:

- **[`README.md`](README.md)** — public overview, quick start, CLI/browser install.
- **[`guides/automation.md`](guides/automation.md)** — recurring lane and automation doctrine.
- **[`guides/recipes/`](guides/recipes/)** — opt-in tactics and lane prompt patterns.
- **[`docs/reference/`](docs/reference/)** — CLI, config, hooks, scripts, browser, and PLAN field references.
- **[`examples/`](examples/)** — worked plan-first examples.

---

## Beyond Core — Automation and Recipes

Everything above is **core vidux** — five principles, cycle, PLAN.md template, investigations, course correction, and routing boundaries. It works for humans, one-shot AI sessions, and scheduled workers alike. Two companion surfaces carry the rest (neither overrides core; both are opt-in layers):

- **[`guides/automation.md`](guides/automation.md)** — 24/7 fleet operating model, session-gc, lane management, subagent delegation, lane bootstrap. Load when running lanes on a schedule.
- **[`guides/recipes/`](guides/recipes/)** — opt-in tactics: CLAUDE.md rules, lane prompt templates, subagent dispatch, evidence discipline, proactive work surfacing, visual-proof requirements. Load a specific recipe on demand.
- **[`guides/figma-net-new-project.md`](guides/figma-net-new-project.md)** — Figma MCP onboarding for new vidux projects: install, OAuth, verify, kickoff, lane-selection for design→code vs code→design vs library-build. Load when a vidux project gets its first visual surface.

**Automation default:** prefer the least privileged execution surface that can do the job. Do not default to repo-bound execution unless the user explicitly asks for it or the task cannot be done from a read-only/chat-style context.
