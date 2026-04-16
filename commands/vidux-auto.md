---
name: vidux-auto
description: "Automation companion for vidux. Session management, lane operations, delegation modes, fleet ops, PR lifecycle, observer pairs, and platform-specific mechanics for running vidux workers on a schedule."
---

# /vidux-auto

Automation companion for vidux. Covers session management, lane operations, delegation modes, fleet ops, PR lifecycle, and observer pairs. Platform-specific mechanics for running vidux workers on a schedule.

Vidux-auto is the HOW of automation. The core `/vidux` skill is the WHAT (discipline, principles, cycle). Use both together.

Replaces the former `/vidux-claude`, `/vidux-codex`, and `/vidux-fleet` companion skills.

---

## 1. The 24/7 Fleet Operating Model

The fleet runs indefinitely on one invariant: **lanes persist on disk, sessions cycle through them.**

```
Lanes (persistent, never disposed)   Sessions (disposable, GC'd)
──────────────────────────────────   ──────────────────────────
~/.claude-automations/                ~/.claude/projects/*/*.jsonl
├── <lane>/prompt.md                  - Session A: 12h → 50MB → cycle
├── <lane>/memory.md                  - Session B: fresh, picks up lanes
└── ...                               - Session C: ...
```

**In practice:**

1. **A lane = `prompt.md` + `memory.md` on disk.** These files are NEVER deleted while the assignment is active. When a session dies, the files stay. A new session re-schedules the cron pointing at the same files. The lane resumes from memory.md. Work is never lost to a session restart.
2. **A session = one Claude Code process + its JSONL.** Sessions are disposable. They die for many reasons: account rotation, laptop sleep, compaction pressure, manual restart. Their JSONLs accumulate on disk until GC'd.
3. **session-gc is the mandatory janitor.** Without it, the 24/7 model breaks. It runs hourly and deletes old session JSONLs (>3 days), subagent JSONLs (>1 day), and reports the current session's growth rate. See Section 2.
4. **Lane count stays low.** More than 6 lanes per session causes worktree contention and JSONL bloat.
5. **Cross-session handoff is implicit.** When a session dies at ~50 MB, the next session starts fresh, re-schedules crons, and each lane reads its own memory.md to resume. **No state lives in the session.** All durable state is on disk: PLAN.md, memory.md, `.agent-ledger/activity.jsonl`, evidence/. The session is a transient execution environment, not a database.

### Hot vs cold storage

| Layer | What lives here | Lifetime | GC |
|---|---|---|---|
| **Cold (durable)** | PLAN.md (queue + decision log), evidence/, investigations/, memory.md per lane, `.agent-ledger/activity.jsonl` | Until assignment done | Manual archive per vidux rules (completed tasks rotate to `evidence/` when PLAN.md > 200 lines) |
| **Hot (disposable)** | `~/.claude/projects/*/*.jsonl` (conversation log) | One session | Automatic via `session-prune.py --gc-old` hourly |

**Every cold-storage entry has a stable home and a reason to exist.** Every hot-storage byte is evictable once the session it belongs to is inactive. If you find yourself reading old JSONLs to recover state, the cold-storage contract is broken — fix the checkpoint discipline, don't revive the JSONL.

### Why not cloud scheduling?

Cloud-based scheduling primitives (Routines, remote triggers) are persistent and survive laptop sleep. **Rejected for local-first fleets** because:

- **Per-account binding.** Each routine is bound to one account. Multi-account rotation for quota management breaks routines.
- **Minimum cadence too long.** Some lanes need 20-30 min cycles (code-writing lanes with tight CI loops). Cloud primitives often enforce 1-hour minimums.
- **No local file access.** Cloud schedules cannot read local automation directories, git worktrees, simulators, or `.env.local`.
- **No memory.md cross-reads.** Cross-lane coordination via sibling memory files does not work from a cloud sandbox.

**CronCreate + session-gc is the opinionated 24/7 primitive**: local-first, multi-account-compatible, sub-hour cadence, and (with session-gc running) JSONL growth is bounded to ~30-50 MB per active session.

If your constraints differ (single account, no local tooling, hourly cadence is fine), cloud scheduling may work. This skill covers only the local-first path.

---

## 2. Session Management

Without GC, `~/.claude/projects/` grows 5-10 MB/hour with an active fleet, hits 1 GB in days, and makes `/resume` unusable. **session-gc is mandatory for 24/7 operation.**

### What grows (per 24h with a 5-lane fleet)

| Entry type | Share | Prunable? | Notes |
|---|---|---|---|
| `hook_success` + `async_hook_response` | ~32% | YES — noise | Hook ack metadata |
| `assistant` + `user` messages | ~49% | NO | Real conversation — needed by `/resume` |
| `queue-operation` | ~3% | YES — noise | Enqueue/dequeue tracking |
| `task_reminder` | ~1% | YES — noise | Unused-tool nags |
| `file-history-snapshot` | ~2% | YES — noise | File state snapshots |
| `skill_listing`, `invoked_skills`, `deferred_tools_delta`, `mcp_instructions_delta` | ~5% | Keep-last-N | Keep recent 1-3, prune older |
| `subagent JSONLs` | -- | YES — delete entirely | Session forks spawned by `Agent()`. Results already in parent. Throwaway after 1h. |

### The three GC levels (all in `scripts/session-prune.py`)

**Level 1 — Per-session noise pruning (`--prune <file>`).**
Strips noise categories from a JSONL file. Repairs the `parentUuid` chain so `/resume` still works. Creates a `.bak` backup first. Applied to INACTIVE sessions only — never the live one.

**Level 2 — Old-session GC (`--gc-old [days]`).**
DELETES main session JSONLs older than N days across all projects. These sessions will never be `/resume`d — their durable state has already moved to PLAN.md, ledger, and memory.md by design. Default: 3 days.

**Level 3 — Subagent GC.**
Same `--gc-old` invocation also deletes ALL subagent JSONL files older than 1 day. Standalone variant: `--gc-subagents [hours]`.

```bash
# Commands (run manually or via the session-gc lane)
python3 scripts/session-prune.py --dry-run     <file>     # read-only analysis
python3 scripts/session-prune.py --prune       <file>     # strip noise + repair chain + backup
python3 scripts/session-prune.py --gc-old-dry  3          # preview what would be deleted
python3 scripts/session-prune.py --gc-old      3          # DELETE main >3d + subagents >1d
python3 scripts/session-prune.py --gc-subagents 1         # DELETE subagents >1 hour
```

**Measured results:** A typical GC pass reclaims 30-50% of disk. Per-session noise pruning saves ~30% on fleet-heavy sessions.

### The current session is NEVER pruned while live

The session-gc lane is a subagent inside the parent session. Modifying the parent's JSONL while the parent is live is risky — Claude Code may be mid-read during compaction or `/resume`. **Treat the parent's JSONL as immutable while the parent is running.**

Instead, session-gc **measures the current session's growth rate** and emits a cycle-time signal when the JSONL crosses a threshold:

```
- [CYCLE SIGNAL] Current session at 42MB, growing ~5MB/hr. Recommend /resume to a
  fresh session. Lanes will pick up from disk automatically; no work lost.
```

The human reads the signal and decides when to restart. On restart:
1. New session starts (fresh JSONL)
2. New session re-schedules the crons (CronCreate calls)
3. Each lane's next fire reads its own `memory.md` and picks up where it left off
4. The old session's JSONL becomes eligible for `--gc-old` on the next cycle

### The session-gc lane (mandatory for 24/7)

**Location:** `~/.claude-automations/session-gc/prompt.md`
**Cadence:** hourly (offset from the :00/:30 pileup)
**Authority:** `~/.claude/projects/` only. MUST NOT touch memory.md, PLAN.md, ledger, or any git repo.

Each fire does EXACTLY this, in order:

1. `python3 scripts/session-prune.py --gc-old 3` — delete stale sessions + subagents
2. Measure current session size and growth since last cycle
3. If current session > 40-80 MB (tunable threshold) → emit `[CYCLE SIGNAL]` in `memory.md`
4. Append checkpoint:
   ```
   - [YYYY-MM-DDTHH:MM:SSZ] Freed <X>MB (<N> files). Current: <M>MB (+<D>MB/hr). <SIGNAL or OK>.
   ```

That is the entire session-gc lane. Under 50 lines of prompt. One script, one cadence, one checkpoint format. Do not extend it — GC is GC, not a coordinator.

### Plan-GC is NOT a separate lane

The vidux GC rule — archive completed tasks when PLAN.md exceeds 200 lines — is the **coordinator's** job. Each coordinator reads its own PLAN.md at the top of every cycle and, if the threshold is hit, rolls completed tasks to `evidence/YYYY-MM-DD-completed-tasks-archive.md` before picking up new work. **One lane owns a repo's entire lifecycle: ship, fix, GC.**

---

## 3. Lane Management

**Rule: minimum lanes needed, max 6 per session.** Every lane must earn its keep.

### Decision tree

```
Is this a 24/7 ongoing fleet concern (long-running product shipping)?
├─ YES → 1 COORDINATOR per active repo
│        + 1 OBSERVER per coordinator (optional — add when drift is measured)
│        + 1 SESSION-GC for the whole session (MANDATORY for 24/7)
│        Total: 3–7 lanes for 1–3 active repos. Hard cap at 6 per session.
│
└─ NO  → Is this a burst fix (< 1 day, specific stuck PR / failing CI)?
         ├─ YES → 1 BURST lane with auto-expire (see `qa-iterator` pattern)
         │        + session-gc if not already running
         │        Total: 1–2 lanes.
         │
         └─ NO  → Is this research only (audit, evidence gathering, no code)?
                  ├─ YES → 1 RADAR lane (read-only, no worktree)
                  │        Total: 1 lane.
                  │
                  └─ NO  → 1 WRITER lane for the specific shipping task
                           + optionally 1 observer if drift is expected
                           Total: 1–2 lanes.
```

### The coordinator pattern (default for 24/7 work)

A **coordinator** is one lane that owns ALL concerns for one repo: ship code, fix CI, archive completed tasks in PLAN.md, watch INBOX.md, update Progress log. It is the opposite of the specialist model (separate shipper / product / creative-engine / a11y-sweep / seo-radar lanes for the same repo).

**Why one coordinator beats N specialists:**

- **No PLAN.md stampede.** Multiple writers touching the same PLAN.md cause merge races and Progress-log corruption. One coordinator per repo is a natural serialization.
- **End-to-end ownership.** The coordinator that shipped the code is the same one that fixes the test when it fails. No handoff bugs, no "that's not my lane" gaps.
- **Simpler mental model.** When something breaks, the operator opens ONE memory.md to diagnose, not 5.
- **JSONL savings.** 1 coordinator firing 3x/hour adds ~600KB/hour of JSONL. 5 specialists firing 3x/hour each add ~3MB/hour. Over 10 hours the difference is 24MB vs 6MB.
- **Works with multi-account rotation.** On account switch, the coordinator's state is on disk (memory.md). The new session picks up. Specialist sprawl multiplies this handoff risk.

### The observer (the one exception to "fewer lanes")

Observers are the only kind of lane to add preemptively. They are read-only lanes that audit the writer's work each cycle. Full setup details in Section 8 (Observer Pairs).

**Why observers are cheap:** read-only (zero write contention), catches drift the writer cannot self-audit (wrong flags, FSM violations, retroactive edits, stale cross-references).

**When to add one:** after running a writer for a full day, read its memory.md. If there is drift (3+ cycles stuck on the same task, non-chronological entries, "completed" without an "in_progress" predecessor, stale authority refs), add an observer. If not, skip. 1 observer per writer max — never stack.

### Why the hard cap at 6

Measured, not theoretical:

- **Git worktree contention.** With 7+ concurrent lanes on the same repo, `lint-staged` stash collisions and branch-switch data loss become common (verified in overnight ops).
- **JSONL growth.** Each fire adds ~200KB. 6 lanes x 3 fires x 200KB x 8 hours = 29MB. 15 lanes at the same rate = 72MB. Same session length, **60% less bloat.**
- **Mental model.** When something goes sideways, the operator needs to scan N memory.md files. 6 files is tractable. 15 is not.
- **Account rotation.** On account switch, every running cron dies. 6 lanes = 6 crons to re-schedule. Fewer lanes = faster session rotation.

If your assignment needs more than 6 lanes, the assignment is too big for one session. Split across accounts or across time — do not stack.

### Anti-patterns (never do these)

- **Specialist splitting.** Do not create separate `<project>-shipper`, `<project>-product`, `<project>-creative-engine`, `<project>-a11y-sweep`, `<project>-seo-radar` lanes for the same repo. Collapse into one coordinator.
- **Lane-per-PR.** Do not spawn a lane for each in-flight PR. The coordinator picks the next PR to work on.
- **"Helper" lanes.** A `fleet-coordinator` that only watches other lanes is a parked car. Collapse its responsibilities into the lanes themselves.
- **Preemptive observers.** Do not create observers "just in case." Measure drift, then add one.
- **Resurrection lanes.** Do not create a lane to restart another lane. Sessions cycle; lanes resume from disk. The restart is implicit.

### Ghost lane detection

If a lane checkpoints "nothing to do" 3 times in a row, kill it or collapse it into a coordinator.

### Polish-brake trigger (Principle 4 in practice)

**If your last 3 checkpoint entries all shipped fixes from the same surface pattern** (e.g. 3 review-comment triage fixes in a row, 3 lint polish commits in a row, 3 docstring touchups), **pause polish and force a surface switch.** One of:

1. Promote the oldest actionable `INBOX.md` finding to a `[pending]` plan task, then execute it.
2. Advance the first unblocked `[pending]` task in PLAN.md that is NOT on the same surface.
3. If neither exists, checkpoint "queue clean, surface N exhausted" and exit — do not invent work.

**Why:** polish is fractal — every green PR has another P3 comment, every tightened test has one more edge case. Without the brake, a lane will iterate forever on the same surface while the rest of the mission rots.

**Measurement:** each checkpoint entry should name the surface (repo, PR number, test file, plan task). The rule fires when `grep -c <surface>` on the last 3 entries returns 3.

---

## 4. Delegation (Mode A + Mode B)

Two delegation modes for distributing work across agents with different cost/capability profiles.

- **Mode A (Research):** Read-only sandbox, 3-section compressed summary, large token savings.
- **Mode B (Implementation):** Workspace-write sandbox, delegated agent writes code, directing agent reviews diff and ships.

Includes: decision tree (when to delegate), tier math table, invocation flags, temp-file workaround for backticks, the compression contract (Mode A), the 5-block implementation prompt shape (Mode B), and the diff-review checklist.

<!-- SOURCE: vidux-codex L39-97 (Mode A/B diagrams, cost shift table), L136-186 (decision tree, T15 tier math), L207-341 (invocation flags, compression contract, implementation prompt, diff-review checklist) -->

---

## 5. Fleet Operations

Creating, managing, and auditing automation fleets at scale.

- **Slot map:** Visual schedule of all active lanes with cadence and stagger offsets.
- **Prompt templates:** Writer, radar, coordinator, specialist (<=15 lines each).
- **Bimodal quality model:** Quick/deep/stuck-in-middle classification.
- **Validation rubric:** 9 checks (schedule collisions, prompt bloat, doctrine restating, stale automations, bimodal quality, orphan radars, missing coordinator, etc.).
- **Audit scoring:** 9-check rubric, scoring math, report format.
- **Recipe selection heuristics:** Quick-reference table pointing to `guides/recipes.md` for full templates.

> Cross-reference: `guides/recipes.md` for the 11 opinionated automation recipes. `guides/fleet-ops.md` for fleet patterns and gate mechanics.

<!-- SOURCE: vidux-fleet L22-247 (create/fleet/validate, slot map, prompt templates, bimodal quality, hard rules), L392-740 (prescribe/write/audit, recipe selection heuristics, scoring rubric) -->

---

## 6. PR Lifecycle

Mandatory PR triage at the start of every automation cycle. The PR Nurse pattern closes the feedback gap where review comments go unaddressed.

- **Triage:** `gh pr list --state open --author @me` to find automation-created PRs with unaddressed review comments.
- **Nurse responsibilities:** Scan, fix one P1/P2 per cycle, push to PR branch, reply to comment thread, verify CI (remote or local checks for repos without CI), signal READY_FOR_MERGE when all comments resolved.
- **Self-review before push:** Checklist baked into the writer prompt template.

> Cross-reference: `guides/draft-pr-flow.md` for the 5-step draft-PR flow, branch naming, PR body template, and recovery via `gh pr list`.

<!-- SOURCE: vidux-claude L444-448 (mandatory PR triage), NEW (PR Nurse pattern — closes PR #338 gap) -->

---

## 7. Concurrent-Cycle Hazards

When multiple lanes share a repo and fire on overlapping schedules, these failure modes are real (all verified in production):

### 1. lint-staged stash collision
`lint-staged` runs `git stash` internally to isolate staged changes. If another lane fires during this stash window, the stash pop on return will conflict. **Result: reverted files, merge conflicts, data loss.**

**Rule: NEVER use `git stash` + branch switch in the same cycle.** If the working tree is dirty when a cycle starts, log `[QC] concurrent-cycle detected, deferring` and exit immediately.

### 2. Branch-switch data loss
Lane A commits on `branch-a`, switches back to `main`. Lane B fires, reads main, starts editing. Lane A's merge into main has not happened yet. Lane B's `git checkout main` wipes Lane A's uncommitted writes.

**Rule: Always `git status` before any branch operation.** If you see uncommitted changes you did not create, STOP and exit.

### 3. CI review bot window
After pushing a draft PR, review bots take 2-5 min to post. If the next cycle fires before reviews arrive, it cannot merge (CI review gate). The lane wastes a full cycle re-checking.

**Rule: After pushing a PR, the same lane should NOT attempt merge until the NEXT cycle.** One cycle = push + wait. Next cycle = check reviews + merge if green.

### Prevention checklist (include in every cron wrapper prompt)
1. `git status` before any branch operation
2. If dirty tree not from this lane → `[QC] concurrent-cycle` → exit
3. No `git stash` + branch switch combo
4. After PR push, defer merge to next cycle

---

## 8. Observer Pairs

Observers are read-only lanes that watch a project for regressions, drift, or missed signals that the primary writer lane is too focused to catch.

- What observers catch (evidence from delegation studies).
- Setup recipe: cadence offset from writer, authority discipline, verdict format.
- When to add one (heuristic): add when a project has >1 active PR or ships >3x/week.

<!-- SOURCE: vidux-codex L396-430 (primary: T8b/T14 evidence, setup recipe, authority), vidux-claude L158-167 (when-to-add heuristic) -->

---

## 9. Worktree Discipline

Every code-writing lane uses git worktrees for isolation:

```
~/Development/<project>/                              <- main working copy
~/Development/<project>-worktrees/<lane>-<ts>/        <- per-cycle worktree
```

**Rules:**
- Fresh worktree per cycle for code changes
- Symlink `node_modules`, `.env.local`, `.env.test` from main into the worktree (CRITICAL — without this, test commands fail on env-var checks and look like code regressions)
- Commit inside the worktree, fast-forward merge into main, delete worktree
- Never push without explicit human authorization (cron cycles commit locally, human pushes)

**Investigation-only cycles** (plan updates, evidence files, no code changes) MAY skip the worktree and commit directly in main — worktree discipline isolates code changes that could break builds, not doc updates.

### lint-staged branch-hijack gotcha (verified)

Husky + lint-staged use `git stash` during pre-commit. On some setups, the stash pop occasionally checks out a different stashed branch, silently hijacking HEAD. Your commit lands on the wrong branch. **After EVERY commit:** run `git branch --show-current` to verify. If hijacked: capture SHA, checkout intended branch, cherry-pick.

---

## 10. Prompt File Structure

### Why prompt file on disk (not inline in the cron)

- **Disk-persisted authority.** Crashes, restarts, and Mac sleeps do NOT wipe `prompt.md`. Session-only cron state does. If the cron dies and gets re-scheduled, the new cron can be a thin wrapper pointing at the same on-disk prompt — zero rework.
- **Diffable lane evolution.** Edits land, the next cycle picks them up, and memory.md captures the before/after behavior.
- **Cross-lane coordination.** Lanes read each other's `memory.md` to avoid racing. A lane reads a sibling lane's memory before touching a shared file, because the sibling may have an `[in_progress]` task there.

### The 8-block structure

```
1. Mission        — one paragraph, end goal, why this lane exists
2. Skills         — skill tokens relevant to this lane (/vidux, etc.)
3. Read           — files to read every cycle IN ORDER (PLAN.md, cross-lane, memory)
4. Gate           — trunk divergence, stuck detection, resume rules
5. Assess         — unified queue rule (in_progress -> resume, else first eligible pending)
6. Act            — worktree discipline, verification commands, merge rules
                    + optional delegation blocks (Mode A read / Mode B write)
7. Authority      — paths this lane owns vs. paths it must not touch
8. Checkpoint     — memory.md append format, reconcile plan vs. diff
```

Every lane prompt ends with a **STRATEGIC DIRECTION** block that captures *why* the lane exists and what biases the agent should lean into (e.g., "hardening > new features," "research only, never delete").

### The <=15 line harness rule

The cron wrapper (the text passed to `CronCreate`) should be <=15 lines. It says "read prompt.md, execute one cycle." All real instructions live in `prompt.md` on disk, not in the cron payload. Never restate core vidux principles in prompts — reference the skill instead.

> Cross-reference: `guides/fleet-ops.md` for lean prompt templates per fleet role (writer, radar, coordinator, specialist).

---

## 11. Composition Recipes

Six composition patterns for combining delegation with other tools:

1. **vidux->delegated-agent:** Standard delegation from directing agent to executing agent.
2. **delegated-agent + prompt amplifier:** Amplify vague tasks before delegation.
3. **delegated-agent + research agent:** Package source lookup before implementation.
4. **Agent parallelism:** Fan-out independent subtasks to parallel agents.
5. **Agent wrapper for long crons:** Wrap session-scoped crons in an Agent call for crash recovery.
6. **Review-feedback triage (qa-iterator):** Automated PR review comment triage and fix loop.

<!-- SOURCE: vidux-codex L476-598 (Recipes 1-6, Agent wrapper pattern, qa-iterator) -->

---

## 12. Creating / Updating / Deleting Lanes

### Creating a lane

1. **Pick the plan.** Every lane exists to drive one PLAN.md. If there is no plan, write one first (use `/vidux`) before creating the lane.

2. **Draft the prompt file** at `~/.claude-automations/<lane-name>/prompt.md` using the 8-block structure (Section 10). Cite the PLAN.md path and list the files the agent must read every cycle.

3. **Seed the memory file** at `~/.claude-automations/<lane-name>/memory.md`:
   ```
   - [YYYY-MM-DDTHH:MM:SSZ] [RESET] Lane created. First cycle will read prompt.md
     and execute initial vidux pass against <plan path>.
   ```

4. **Schedule the cron** via `CronCreate` (see Section 15 for deferred tool loading). The prompt argument is the thin wrapper: "Read prompt.md first, then execute one vidux cycle." Set cadence per the table below.

5. **First fire.** Watch the first cycle — it should produce either a code commit, an evidence file, or an idle-scan memory note. If it does nothing, the prompt is wrong.

### Cadence table

| Lane type | Active cadence | Overnight cadence | Reason |
|---|---|---|---|
| Code-writing (fix/build/ship) | 20-30 min | 30-45 min | CI takes 3-5 min; 15 min causes concurrent-fire hazards |
| Research-only (audit/evidence) | 30 min | 60 min | Each cycle produces a deliverable |
| Idle-scan/watchdog | 30-60 min | 60 min | Paranoia is cheap, noise is expensive |
| Cross-fleet orchestrator | 60 min | 60 min | Reads everyone else's memory, does not need to be fast |

**15-min cadence is RETIRED for code-writing lanes** (verified in overnight ops). A PR needs: commit + push + CI (3-5 min) + review bot (2-5 min) + merge. 15-min fires mean the next cycle lands before the current PR is green, causing duplicate work or branch-switch data loss.

**Stagger fires >=8 min apart** when multiple lanes share the same repo. Example: `:03/:33`, `:12/:42`, `:21/:51` — no two fires within 8 min of each other.

### Updating a lane

1. Edit `~/.claude-automations/<lane-name>/prompt.md`. The next cron fire reads the edit, so the change is live within the cron cadence.
2. If you change the cadence, use `CronCreate` to replace the schedule.
3. If you change strategic direction mid-cycle, add a banner at the top of `memory.md`:
   ```
   > **LANE PRIORITY RESET YYYY-MM-DD:** <what changed>. See prompt.md for full guidance.
   ```

### Deleting a lane

1. Remove the cron via `CronDelete`.
2. Archive `~/.claude-automations/<lane-name>/` to `~/.claude-automations/_archive/<lane-name>-YYYY-MM-DD/`. Do NOT hard-delete — the memory.md is load-bearing history.
3. If the plan is complete, update PLAN.md Progress with a "lane closed" entry.

---

## 13. Memory Files

**Location:** `~/.claude-automations/<lane-name>/memory.md`

Agents have no built-in cross-session memory. The lane's memory.md IS the memory — every cycle reads the last 3 entries before acting, and appends a new entry after checkpointing.

### Entry format

```
- [YYYY-MM-DDTHH:MM:SSZ] <task>: <shipped or status>. Tests: pass/fail. Runtime: Xm.

  Optional sub-lines with:
  - Specific numbers (error counts, response times, LOC counts)
  - What was NOT done and why
  - Cross-lane notes
  - Next-cycle action items
```

### Delegation checkpoint format (dual-token accounting)

When a cycle delegates work to another agent, log both token pools:

```
[YYYY-MM-DD HH:MM] <cycle-id> T<n>: <what happened>. Delegated: <calls>/<approx-delegated-tokens>.
Directing agent budget impact: <approx-directing-tokens>. Next: <next task>. Blocker: <if any>.
```

### Reset markers

```
- [YYYY-MM-DDTHH:MM:SSZ] [RESET] <reason>. <what got reset>.
- [YYYY-MM-DDTHH:MM:SSZ] [QC] 3x same, no movement. Human needed.
- [YYYY-MM-DDTHH:MM:SSZ] [QC] prompt missing, human needed to rehydrate.
```

### Visibility rule

**Keep last ~10 entries visible.** Older entries are still valuable as history but the gate logic only looks at the last 3 for stuck detection.

---

## 14. Lean Fleet Dispatch Rules

Rules in priority order:

0. **Hard cap: 6 lanes per session.** More than 6 causes worktree contention, JSONL bloat, PLAN.md stampede, and session-restart friction.
1. **Max 3-4 parallel agents per wave.** More than 4 simultaneous agents on the same repo causes git worktree contention and branch-switch collisions.
2. **Fire-and-forget.** Dispatch background agents and move on. Do not block the parent waiting for results.
3. **Trust memory.md.** Do not inject stale briefing state into the agent prompt — the agent reads `prompt.md` and `memory.md` itself for live state.
4. **Don't bloat parent context.** Agent results are stored as attachments in the parent JSONL. Many agents with large output adds up fast. Keep agent prompts tight (<500 bytes) and let each agent read its own context from disk.
5. **Absorb duplicate fires.** If a cron fires while the previous cycle's agent is still running, skip it.
6. **Batch cron waves.** When multiple crons fire at the same minute, dispatch them in a single multi-tool-call message, not sequentially.
7. **Prefer coordinator over specialist.** When tempted to add a specialist lane for a concern on an already-covered repo, add the concern to the coordinator's prompt instead. The specialist will fight the coordinator on PLAN.md; the coordinator grows instead.

---

## 15. Deferred Tool Loading

The cron-management tools (`CronCreate`, `CronDelete`, `CronList`) are **deferred tools** in Claude Code — they are NOT loaded by default. Before invoking them, fetch their schemas:

```
ToolSearch(query: "select:CronCreate,CronDelete,CronList", max_results: 3)
```

This returns the JSONSchema definitions inline and makes the tools callable. A call to `CronCreate` without first running `ToolSearch` will fail with `InputValidationError`. Same pattern applies to `TaskCreate`, `WebFetch`, and any `mcp__*` tools not surfaced at session start.

Always call `ToolSearch` with `select:<tool_name>` before invoking deferred tools.

---

## 16. External Tool Pairing

When to pair delegation with external research or amplification tools.

- **Research agent pairing:** Package source lookup is significantly cheaper than inline research (measured: 16.5x token savings). Warning: deep research mode causes context overflow on delegation cycles — use quick mode only.
- **Prompt amplifier pairing:** Expand vague tasks into focused specifications before delegating. Most useful when the directing agent receives a one-liner task.

<!-- SOURCE: vidux-codex L343-374 (research pairing, deep-mode warning T14, amplifier pairing) -->

---

## 17. Recommended Agent Config Rules

Three battle-tested rules for agent configuration files (CLAUDE.md, .cursorrules, AGENTS.md, etc.), plus the T1-T4 change classification framework that protects core discipline from churn.

> Cross-reference: `guides/agent-config-rules.md` for the full guide — 3 rules (re-read before edit, re-read after fail, proportional response) + T1-T4 framework (Prompt -> Agent Config -> Companion -> Core).

<!-- SOURCE: guides/agent-config-rules.md (cross-reference, not inlined) -->

---

## 18. Insights Triage Process

After every 10 sessions, review friction findings and classify each as T1-T4. Apply T1 (prompt) and T2 (agent config) immediately. Plan T3 (companion recipe) in PLAN.md. Escalate T4 (core discipline) with a Decision Log entry.

This is a manual process. Build automation only when manual triage proves painful (>15 findings per review).

<!-- SOURCE: Phase 9.4 insights triage process (manual-first) -->

---

## 19. Activation

Activate `/vidux-auto` alongside `/vidux` when:

- Setting up or modifying automation lanes (CronCreate, scheduled agents).
- Diagnosing fleet health, session bloat, or lane contention.
- Delegating work between agents (Mode A/B).
- Running fleet scans, audits, or prescriptions.
- Creating or reviewing draft PRs from automation.
- Pairing a writer lane with an observer.

Do NOT activate for core plan-first work (use `/vidux` alone) or for one-off tasks that don't involve automation infrastructure.

---

## 20. Related Skills

| Skill | Role |
|---|---|
| `/vidux` | Core discipline — principles, cycle, planning |
| `/captain` | Skill registry management |
| `/pilot` | Universal project lead and router |
| `/amp` | Prompt amplifier for vague tasks |
| `/nia` | Research agent for package/doc lookup |
| `/ledger` | Agent activity log for cross-agent coordination |
