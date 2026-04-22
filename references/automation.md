# Automation Reference (vidux)

Detailed automation doctrine for vidux — session management, lane operations, delegation modes, fleet ops, PR lifecycle, and platform-specific mechanics for running vidux workers on a schedule. Read this reference from `/vidux` when a task involves creating lanes, managing fleet state, or coordinating cross-session handoff.

This reference contains the full doctrine merged from the former `/vidux-claude`, `/vidux-codex`, and `/vidux-fleet` companion skills. The core `/vidux` skill (SKILL.md) contains a condensed automation overview; this reference contains the full details.

---

## 1. The 24/7 Fleet Operating Model

The fleet runs indefinitely on one invariant: **lanes persist on disk, sessions cycle through them.**

```
Lanes (persistent, never disposed)   Sessions (disposable, GC'd)
──────────────────────────────────   ──────────────────────────
<lane-dir>/                ~/.claude/projects/*/*.jsonl
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
| **Cold (durable)** | PLAN.md (queue + decision log), evidence/, investigations/, memory.md per lane, `.agent-ledger/activity.jsonl` | Until assignment done | Agent archives completed tasks when the plan feels heavy — no fixed threshold |
| **Hot (disposable)** | `~/.claude/projects/*/*.jsonl` (conversation log) | One session | Automatic via `session-prune.py --gc-old` hourly |

**Every cold-storage entry has a stable home and a reason to exist.** Every hot-storage byte is evictable once the session it belongs to is inactive. If you find yourself reading old JSONLs to recover state, the cold-storage contract is broken — fix the checkpoint discipline, don't revive the JSONL.

### Why not cloud scheduling?

Cloud-based scheduling primitives are persistent and survive laptop sleep. **Rejected for local-first fleets** because:

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

**Location:** `<lane-dir>/session-gc/prompt.md`
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

The vidux GC rule — archive completed tasks when the plan feels heavy (agent decides, no fixed threshold) — is the **coordinator's** job. Each coordinator reads its own PLAN.md at the top of every cycle and, if the plan is heavy, rolls completed tasks to `evidence/YYYY-MM-DD-completed-tasks-archive.md` before picking up new work. **One lane owns a repo's entire lifecycle: ship, fix, GC.**

---

## 3. Lane Management

**Rule: minimum lanes needed, max 6 per session.** Every lane must earn its keep.

### Decision tree

```
Is this a 24/7 ongoing fleet concern (long-running product shipping)?
├─ YES → 1 COORDINATOR per active repo
│        + 1 SESSION-GC for the whole session (MANDATORY for 24/7)
│        Total: 2–4 lanes for 1–3 active repos. Hard cap at 6 per session.
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
                  └─ NO  → 1 WRITER lane for the specific shipping task.
                           Total: 1 lane.
```

### The coordinator pattern (default for 24/7 work)

A **coordinator** is one lane that owns ALL concerns for one repo: ship code, fix CI, archive completed tasks in PLAN.md, watch INBOX.md, update Progress log. It is the opposite of the specialist model (separate shipper / product / creative-engine / a11y-sweep / seo-radar lanes for the same repo).

**Why one coordinator beats N specialists:**

- **No PLAN.md stampede.** Multiple writers touching the same PLAN.md cause merge races and Progress-log corruption. One coordinator per repo is a natural serialization.
- **End-to-end ownership.** The coordinator that shipped the code is the same one that fixes the test when it fails. No handoff bugs, no "that's not my lane" gaps.
- **Simpler mental model.** When something breaks, the operator opens ONE memory.md to diagnose, not 5.
- **JSONL savings.** 1 coordinator firing 3x/hour adds ~600KB/hour of JSONL. 5 specialists firing 3x/hour each add ~3MB/hour. Over 10 hours the difference is 24MB vs 6MB.
- **Works with multi-account rotation.** On account switch, the coordinator's state is on disk (memory.md). The new session picks up. Specialist sprawl multiplies this handoff risk.

### Observer lanes are deprecated (2026-04-17)

Observers were previously framed as the one exception to "fewer lanes" — read-only lanes that audit the writer each cycle. In practice they are an orchestration smell: extra memory.md files, cross-lane reads, and cycle offsets that rarely catch bugs the writer couldn't already see in its own logs. Drift belongs upstream. If a writer keeps getting stuck or producing wrong flags, fix the writer's prompt or the doctrine that's producing the drift. Do not pay for a second read-only lane to report it back to you. Need independent eyes? Run a one-shot audit by hand. Do not schedule it.

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

## 4. Delegation (Research + Implementation Dispatch)

Two delegation modes for distributing work between a **primary model** (metered, taste/review/commit) and a **secondary model** (unlimited or cheaper, grunt work). The primary directs; the secondary executes. The knob is whether the secondary produces a summary (research) or a diff (implementation).

### Research dispatch — secondary reads, compresses to summary

```
Primary: reads PLAN.md, picks next task
Primary: "This task needs 30 file reads. Hand it off."
Primary: writes a tight research prompt with the compression contract
   |
   v
Secondary (read-only sandbox, separate token account):
   grinds through files, reasons, compresses to 3 sections
   returns: Summary + Evidence + Recommendation
   |
   v
Primary: reads the ~300-token summary
Primary: applies taste — accept, reject, or re-prompt
Primary: ships the edit, updates plan, checkpoints
```

Use for: audits, investigations, cross-file grep synthesis, pattern hunting, evidence gathering.

### Implementation dispatch — secondary writes, primary reviews diff

```
Primary: reads PLAN.md, picks next task
Primary: "This is a 50-line fix with a clear spec. Hand it off."
Primary: writes a 5-block implementation prompt (see below)
   |
   v
Secondary (workspace-write sandbox, edits files in working tree):
   reads task files, writes code, saves edits
   |
   v
Primary: runs `git diff` in the working tree (~500 tokens)
Primary: applies taste — accept-and-commit, re-prompt, or `git checkout .` + redo
Primary: runs lint/test/build, commits, pushes (if authorized)
```

Use for: bug fixes, feature implementation, refactors, tests, docs — anywhere a tight spec produces 10-500 lines of code.

### Cost shift table

| Role | Primary (metered) | Secondary (unlimited/cheaper) |
|---|---|---|
| Read plans | Small reads only | Delegate if > 3 KB |
| Decide approach | Yes (taste) | Never |
| Write code | Only < 10 lines | All substantial code |
| Review diffs | Yes | Never |
| Build/test | Yes (local toolchain) | Can't (local env, simulators) |
| Commit/push | Yes | Never |

### When to delegate (decision tree)

```
Is the task substantial code writing (> 10 lines, clear spec)?
  YES -> implementation dispatch (workspace-write). Secondary edits files, primary reviews diff.

  NO -> Is the task reading code / grinding a hard problem / research?
    NO (pure planning, taste call, < 10 lines of obvious writing)
      -> Primary handles it directly. Don't delegate taste or trivial work.

    YES -> research dispatch (read-only). Secondary reads + compresses to 3-section summary.
    |-- Is the target an external library / package?
    |   |-- "Where should I look?" -> quick research tool (URL discovery, safe)
    |   |-- "Package source / exact types" -> package search tool (real source)
    |   |-- "Exact API / config syntax" -> secondary model (can do live web search)
    |   +-- NEVER deep research mode for implementation — hallucinates schemas
    |
    |-- Is the task reading the local codebase or plan files?
    |   |-- < 3 KB source (one small file)?
    |   |   -> Primary reads directly. Below break-even.
    |   |-- 3-50 KB source (plan + immediate evidence)?
    |   |   -> Delegate if re-read every cycle. 10-50x primary savings.
    |   |-- 50-200 KB source (plan + evidence + some logs)?
    |   |   -> ALWAYS delegate. 30-100x primary savings.
    |   +-- 200 KB+ source (full project directory)?
    |       -> Mandatory delegate. Direct read wastes ~100K primary tokens/cycle.
    |
    +-- Long analysis / computation?
        -> Delegate. Secondary holds the working set, primary gets the answer.
```

### Tier math (flat-fee delegation model, measured)

| Tier | Source size | Direct-read primary tokens | Delegated primary tokens | Savings ratio |
|---|---:|---:|---:|---:|
| TINY | 33 KB | 8,262 | 814 | **10.1x** |
| MEDIUM | 160 KB | 40,208 | 814 | **49.4x** |
| HEAVY | 357 KB | 89,339 | 814 | **109.7x** |

Delegation cost is ~constant at ~814 primary tokens (~314 compressed summary + ~500 orchestration) because the secondary's baseline cost is on a separate account. Savings grow linearly with source size.

### The compression contract (mandatory on every research dispatch prompt)

```
Output ONLY these sections, nothing else, no preamble, no code blocks, no closing:

1. Summary: 3 sentences MAX describing <the thing>.
2. Evidence: 3 file:line references MAX, one per line.
3. Recommendation: 1 sentence MAX on the next action.

Do not explain your reasoning. Do not echo the task. Do not write code.
If you find yourself writing more than those three sections, stop.
```

The contract is honored reliably across reasoning levels (medium/high/xhigh all return exactly 3 sections with <0.2% token variance).

### The implementation prompt shape (mandatory on every implementation dispatch prompt)

Every implementation dispatch prompt includes ALL FIVE blocks:

```
1. Task: one-sentence description of the change.
2. Files: exact paths the secondary may edit. NO other files.
3. Spec: what the code must do, in 3-10 bullets. Include error handling,
   edge cases, and test expectations when relevant.
4. Acceptance criteria: how the primary will judge the diff on review.
5. Out of scope: what the secondary must NOT change (prevents refactor creep).
```

The "Out of scope" block is load-bearing. Without it, the secondary will often refactor adjacent code it decides "looks wrong" — the primary's diff review then either accepts unasked-for scope (tech debt) or rejects the whole diff (wasted cycle).

### Diff-review checklist (primary's job after implementation dispatch returns)

Run `git diff` and verify in this order — stop at the first fail:

1. **Scope.** Does the diff touch only files listed in the prompt? If not -> `git checkout .` + re-prompt with stricter "Files" list.
2. **Spec fit.** Does each change map to a Spec bullet? Unexplained edits -> reject.
3. **Out-of-scope drift.** Renamed functions, import reordering, style-only tweaks, "cleanup" refactors -> reject unless explicitly asked.
4. **Obvious correctness.** Does the logic make sense? Spot-check against the Spec's edge cases.
5. **Taste.** Readable? Matches surrounding style? If not -> re-prompt, don't hand-fix (that burns the primary tokens you saved).
6. **Lint + test + build.** Run local toolchain. If red: small fix = primary fixes; structural = re-prompt secondary.
7. **Commit.** ONE commit per delegated task. Primary writes the message.

### Invocation mechanics

**Research dispatch (read-only):** Invoke secondary with read-only sandbox, a research prompt containing the compression contract, and stdin closed (to prevent input hang). Pipe stdout+stderr to a log file.

**Implementation dispatch (workspace-write):** Same pattern but with workspace-write sandbox. After the secondary returns, run `git diff` and apply the diff-review checklist above. Accept, reject (`git checkout .`), or partial-accept (`git add -p`).

**Prompts with backticks or shell metacharacters:** Write the prompt to a temp file and pass via stdin to avoid quoting issues in the shell.

### Execution rules

1. **One cycle per invocation.** Do not chain multiple delegated tasks.
2. **Compression contract is mandatory in research dispatch.** Implementation dispatch uses the 5-block spec shape instead.
3. **Primary keeps taste.** Never let the secondary make final architectural or design decisions.
4. **Verify before acting.** Research dispatch: discard off-topic summaries and re-prompt. Implementation dispatch: if `git diff` shows over-scope or spec mismatch, `git checkout .` and re-prompt.
5. **Log every delegation.** One line per call in PROGRESS.md: task id, mode (research/implementation), log filename, approximate secondary tokens, primary tokens consumed, exit code.
6. **Main-context budget.** If the cycle exceeds 20 tool calls before acting, stop and checkpoint.
7. **Sandbox matches mode.** Research dispatch -> read-only always. Implementation dispatch -> workspace-write. Never give workspace-write for research (enables edits you didn't ask for). Never give read-only for implementation (it'll just describe what it would do).
8. **Primary owns the commit boundary.** Even in implementation dispatch, the secondary never runs `git commit`, `git push`, or mutates `.git/`.
9. **No implementation dispatch for schema/migration/destructive work.** Database migrations, dependency bumps, CI config, auth flows stay in the primary's direct-write path.

---

## 5. Fleet Operations

Creating, managing, and auditing automation fleets at scale. Four operations: **discover** the current fleet, **prescribe** the right topology, **write** lean harnesses, and **audit** existing prompts against doctrine.

> Full recipe templates: `guides/recipes.md` (11 recipes). Fleet patterns and gate mechanics: `guides/fleet-ops.md`.

### 5.1 Discover + Slot Map

Before creating or modifying lanes, scan for existing automations:

1. **Scan** `<lane-dir>/*/{prompt.md,memory.md}` for active CronCreate lanes.
2. **Build the slot map.** Parse cadence fields, map each automation to its minute-of-hour slots.
3. **Find the lowest-density slot.** Pick a 5-minute slot (`:00`, `:05`, ... `:55`) with the fewest automations. Writers get priority for isolated slots (heavier). Radars can share.

```
Fleet: <project> (5 automations)
  :00  <project>-writer     (writer, every 30m)
  :05  <project>-ux-radar   (radar, every 30m)
  :10  <project>-flow-radar (radar, every 30m)
  :15  <project>-api-writer (writer, every 30m)
  :20  <project>-coordinator (coordinator, every 2h)

Load: max 2 concurrent at :30
Gaps: :25, :35, :40, :45, :50, :55 — available
```

### 5.2 Prompt Templates (<=15 lines each)

Four role-specific templates. Each follows the 8-block structure (Section 10) compressed to <=15 lines.

| Role | Key directives | Gate type |
|---|---|---|
| **Writer** | "Keep working through the queue until a real boundary." UI proof gate. Bounded recursion. Self-extend. | Quick check |
| **Radar** | SCAN gate (exit if unchanged 3x). Evidence with screenshots/repro. Surface bundles (3 tickets = 1 investigation). | SCAN |
| **Coordinator** | Read sibling memory.md. Score bimodal. Flag handoff gaps. Adjust prompts, never code. Every 2h. | Quick check |
| **Specialist** | Single-repo writer. Cross-repo handoff via PLAN.md. Same keep-working + proof-gate directives. | Quick check |

> Full prompt templates with fill-in-the-blank fields: `guides/fleet-ops.md`.

### 5.3 Bimodal Quality Model

Good automations are bimodal:

- **Quick check (< 2 min):** Nothing actionable, checkpoint and exit. Healthy.
- **Deep run (15+ min):** Full e2e cycle — ideate, plan, code, test, QA, commit. Real work.
- **Stuck in the middle (3-8 min):** Started but did not finish. Fix: make tasks concrete with clear gates, prompt says "keep working through the queue."

The coordinator enforces bimodal quality by checking run durations and flagging stuck-in-middle patterns.

### 5.4 Validation Rubric (9 checks)

| # | Check | Pass criteria | Severity |
|---|---|---|---|
| 1 | Line count | <= 15 lines (hard) / <= 20 (critical) | high / blocker |
| 2 | Correct gate | Writers: Quick check. Radars: SCAN gate | high |
| 3 | "Keep working" | Writers contain "keep working" or "until a real boundary" | high |
| 4 | UI proof gate | Writers + UX radars mention screenshot/visual proof | medium |
| 5 | Self-extend | Mentions "add tasks" / "file related" / "extend the plan" | medium |
| 6 | Bounded recursion | Contains "good enough" / "stop polishing" / "next mission gap" | medium |
| 7 | No doctrine restating | Does NOT restate FSM, checkpoint protocol, loop mechanics | high |
| 8 | No "smallest slice" | Does NOT contain "smallest slice" / "land one task" | high |
| 9 | Bimodal health | Last 5 runs >= 80% in quick or deep buckets | medium |

**Scoring:** Each pass = +1, out of 9. Score <= 5 = needs rewrite. Score 0 on a high-severity check = critical.

### 5.5 Prescription (fleet topology selection)

Parse PLAN.md to extract surface signals, then match to a recipe:

| Project state | Recipe | Agents |
|---|---|---|
| 1 plan + 1 active surface | Solo Writer | 1 |
| 2-3 surfaces or recurring UX work | Writer + Radar | 2 |
| 4+ surfaces or handoff problems | Writer + 2 Radars + Coordinator | 4 |
| Multi-repo project | Multi-Repo Fleet | N writers + 1 coordinator |
| Quiet/maintenance | Maintenance Mode | 0 (manual only) |
| Active dev sprint, no cron | Deep Work Mode | 1 persistent |

Compare existing fleet to the prescription: match (no changes), over-provisioned (suggest removals), or under-provisioned (suggest additions).

> Full recipe details, prompt templates, and worked examples: `guides/recipes.md`.

### 5.6 Hard Rules

1. Generated prompts MUST be under 15 lines. The core `/vidux` skill handles the rest.
2. Never restate vidux doctrine, loop mechanics, or checkpoint protocol in generated prompts.
3. Never generate prompts that say "land the smallest verified slice" or "stop after one task."
4. Writer prompts MUST say "keep working through the queue until a real boundary."
5. Schedules MUST avoid thundering herd — max 3 automations per minute offset.
6. Every fleet with 3+ automations MUST have a coordinator.
7. Coordinator runs every 2 hours, not every 30 minutes.
8. Recipes are deterministic — no new recipes invented at runtime. New recipes ship via PR.
9. `prescribe` and `audit` are READ-ONLY. They never modify files.

---

## 6. PR Lifecycle

Mandatory PR triage at the start of every automation cycle. The PR Nurse pattern closes the feedback gap where review comments go unaddressed for cycles while the writer ships new code.

> Cross-reference: `guides/draft-pr-flow.md` for the 5-step draft-PR flow, branch naming, PR body template, and recovery via `gh pr list`. Recipe 9 (PR Nurse) in `guides/recipes.md` for the full prompt template.

### 6.1 Triage (every cycle start)

Before picking up new plan tasks, scan for open PRs that need attention:

```
gh pr list --state open --author @me --json number,title,reviewDecision,isDraft
```

Filter to automation-created PRs with unaddressed review comments. If any P1/P2 comments exist, the PR nurse pass takes priority over new work.

### 6.2 PR Nurse Responsibilities

The writer lane nurses its own PRs — this is NOT a separate lane. Each cycle:

1. **Scan:** `gh api repos/{owner}/{repo}/pulls/{N}/comments` for unresolved threads.
2. **Prioritize:** P1 (blocking) and P2 (significant) comments first. Skip P3 (style/nit).
3. **Fix one:** Address ONE P1/P2 per cycle. Push the fix to the PR branch. Reply to the comment thread with what changed.
4. **Verify:** CI green (remote check) or local build pass (for repos without remote CI — run build, lint, type-check and post results as PR comment).
5. **Signal:** When ALL comments resolved + CI green, post `READY_FOR_MERGE` comment. Human promotes.

### 6.3 Self-Review Before Push

Every writer prompt includes a pre-push checklist (baked into the Act block, not a separate lane):

- Diff matches exactly one plan task (no scope creep)
- No unrelated formatting / import reordering changes
- Tests pass locally
- PR body carries: lane id, plan task id, resume point

---

## 6.5 Model Capabilities and Effort Levels

### Effort levels

| Level | When to use | Token cost |
|---|---|---|
| `high` | Routine reads, idle scans, quick PR checks | Baseline |
| **`xhigh`** | **Default for most lanes** — code writing, plan assessment, PR nursing | 1.2-1.5x baseline |
| `max` | Genuinely hard reasoning — investigation root cause, architecture decisions, complex refactors | 2-3x baseline |

`xhigh` is the Claude Code default as of Opus 4.7. Use it for all code-writing and coordinator lanes. Reserve `max` for investigation-only cycles or tasks explicitly marked [HARD] in the plan.

### Tokenizer impact (Opus 4.7 vs 4.6)

Opus 4.7 uses a new tokenizer: **same text = 1.0-1.35x more tokens**. Practical impact:
- 1M context window = ~555k words (was ~750k on 4.6)
- Sessions hit compaction 20-30% sooner
- Each PLAN.md read costs more tokens
- Same-runtime subagent dispatch (Mode A / Mode B) conserves context more than before — the tokenizer upgrade widens the delegation payoff

Adjust session-gc thresholds if you see compaction thrashing after upgrading.

### `/ultrareview` — dedicated code review

New Claude Code command for deep code review. Use in the VERIFY step of the vidux cycle before marking a task `[completed]`. Especially valuable for:
- PR merge flow: run `/ultrareview` on the diff before squash-merge
- Investigation close-out: verify the fix matches the root cause analysis
- Cross-fleet handoff: review Codex-authored PRs before Claude merges them

### Vision (3x resolution)

Opus 4.7 accepts images up to 2,576px (~3.75 megapixels). Design lanes using Playwright screenshots for visual QA now get 3x the detail — font rendering, subtle spacing, and dark-mode edge cases are more visible.

### Literal instruction following

Opus 4.7 interprets prompts more literally than 4.6. This is a net positive for our structured 8-block lane prompts. Edge cases to watch:
- "2-3 sentences" will produce exactly 2-3 (not 4-5)
- "Exit 'peer active'" may be interpreted as a specific exit string
- Gate conditions with ambiguous language may trigger differently

If lanes behave unexpectedly after upgrading, check the prompt phrasing first.

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

## 8. Observer Pairs — DEPRECATED (2026-04-17)

Observer lanes are deprecated. They are an orchestration smell: read-only lanes that add memory.md files, cross-lane reads, and cycle offsets without catching bugs the writer couldn't already see. Drift belongs upstream — fix the writer's prompt or the doctrine that produces drift. If you need independent eyes, run a one-shot audit by hand, not a scheduled lane.

See Section 3 "Observer lanes are deprecated" for the full rationale. This section is kept only so historical references resolve.

---

## 8.5 Cross-Fleet Coordination (Claude + Codex on the same project)

When a project runs BOTH a Claude writer lane (in `<lane-dir>/`) and a Codex peer writer (in `<codex-lane-dir>/`) against the same PLAN.md, coordination stacks 4 mechanisms by authority:

### The stack

1. **PLAN.md state machine** (primary lock). Every writer atomically flips `[pending]` → `[in_progress] (<fleet>/<lane>)` before touching code. Loser on a race re-reads, sees `[in_progress]`, picks another task. Only the marking writer may mark `[completed]`.

2. **Cross-fleet memory tail** (peer-active hint). Each writer reads the peer fleet's `memory.md` last entry during GATE:
   - Codex reads `<lane-dir>/<claude-peer>/memory.md`
   - Claude reads `<codex-lane-dir>/<codex-peer>/memory.md` (optional, increasingly common)

   If peer entry <10 min old AND `[in_progress]` → exit "peer active". Hint, not lock.

3. **Agent ledger** (cross-session cross-fleet visibility). Both fleets write to `~/.agent-ledger/activity.jsonl` via Stop hooks. `ledger-inject.sh` pre-seeds the last 3 repo-scoped entries on SessionStart — fresh Claude sessions know what Codex did recently, and vice versa.


### Peer-drift: when a specialist gets replaced by a coordinator

Signal: specialist memory.md stale >24 hrs while coordinator has recent activity AND coordinator prompt says "Replaces prior specialist split".

Fix: hot-edit `<codex-lane-dir>/<lane>/prompt.md` to point at the coordinator. Takes effect on next cron fire, no Codex restart needed:

```
Peer Claude lane memory: <lane-dir>/<repo>-coordinator/memory.md
```

Worked example: a `<project>-shipper` specialist goes dormant for 24+ hrs while a `<project>-coordinator` lane ships new commits. Fix: edit the specialist's `prompt.md` to point at the coordinator's `memory.md`, or retire the specialist entirely if the coordinator now covers its scope.

### Symmetric rule: NEVER `--no-verify` across BOTH fleets

Pre-commit hooks (prettier, lint, typecheck, SwiftLint) are the review trail. If a hook fails: document the exact failure in memory.md, write `[BLOCKED-CI-HOOK]`, exit. A human fixes the hook, not the automation. Violates CLAUDE.md discipline on both fleets.

Both fleets carry this rule. Historical violations (one fleet bypassing `prettier --write` hook failures with `--no-verify` to ship faster) are rule breaches — diagnose the hook, never bypass it.

### When to add a Codex peer

Add when:
- Claude quota rotation drops cycles (Codex unlimited subscription = free continuity)
- PR queue backs up faster than one writer clears
- Project has ≥5 `[pending]` tasks in rotation

Skip when:
- <3 `[pending]` at any time (peers idle, clutter memory)
- Tasks need heavy human taste calls (Codex peers are spec-execution, not direction)
- Single Claude coordinator already clears the queue at its cadence

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
- Commit inside the worktree, push the branch, open a draft PR (draft PRs are always safe — no authorization needed). Direct-to-main or destructive operations require explicit authorization.

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
                    + optional delegation blocks (research read / implementation write)
7. Authority      — paths this lane owns vs. paths it must not touch
8. Checkpoint     — memory.md append format, reconcile plan vs. diff
```

Every lane prompt ends with a **STRATEGIC DIRECTION** block that captures *why* the lane exists and what biases the agent should lean into (e.g., "hardening > new features," "research only, never delete").

### The <=15 line harness rule

The cron wrapper (the text passed to `CronCreate`) should be <=15 lines. It says "read prompt.md, execute one cycle." All real instructions live in `prompt.md` on disk, not in the cron payload. Never restate core vidux principles in prompts — reference the skill instead.

> Cross-reference: `guides/fleet-ops.md` for lean prompt templates per fleet role (writer, radar, coordinator, specialist).

---

## 11. Composition Recipes

Six composition patterns for combining delegation with fleet operations.

### Recipe 1: vidux -> delegated secondary

Standard delegation from a directing agent to an executing agent within a vidux cycle.

```
Primary: [reads PLAN.md, picks task]
Primary: "Next task needs 30 file reads — delegating"
Primary: [writes tight prompt, invokes secondary, consumes summary]
Primary: [back in vidux cycle, ships the edit]
```

Use when the plan is standard vidux but a single task exceeds the delegation threshold (Section 4).

### Recipe 2: delegation + prompt amplifier

```
Primary: [reads PLAN.md, task is "audit auth middleware for leaks"]
Primary: prompt is vague — invokes prompt amplifier to tighten it
Primary: [amplifier returns focused spec: "grep for req.session, trace handlers..."]
Primary: [sends amplified prompt to secondary]
```

Use when the research question is vague enough that the secondary might wander.

### Recipe 3: delegation + research agent

```
Primary: [task needs external library API signature]
Primary: "External library — use research agent, not secondary"
Primary: [research agent returns actual package source in ~2K tokens]
Primary: [applies to the edit, secondary is NEVER called]
```

Research agents beat secondary models ~16x for package source lookups. This is already the documented decision tree in Section 4.

### Recipe 4: Agent parallelism

```
Primary: [task is a broad codebase survey]
Primary: option A — secondary with compression contract
Primary: option B — subagent in primary's context (faster feedback, still isolated)
Primary: choose based on budget pressure:
         budget tight -> secondary (offloads to separate account)
         budget ok    -> subagent (faster, but costs primary tokens)
```

### Recipe 5: Agent wrapper for long autonomous crons

```
Parent cron: [4+ hour autonomous lane running many cycles]
  spawns subagent(prompt="run ONE delegation cycle against PLAN.md")
    |
  Subagent: separate subthread, own context
    reads skill, runs secondary delegation (free tokens)
    returns 5-line summary to parent
    |
  Parent: sees ONLY the 5-line summary (~500 tokens)
    checkpoints, waits for next cron fire
```

**Use for autonomous lanes running 4+ hours.** The skill-only pattern accumulates parent context ~2-5K per cycle; over 12+ hours, the parent hits context limits. The wrapper keeps parent context at ~10K indefinitely.

Rule of thumb:
- Interactive session, < 2 hours -> skill-only (cheaper)
- Autonomous cron, 4+ hours -> agent wrapper (parent context stays bounded)
- Autonomous cron, 24+ hours -> agent wrapper is mandatory

### Recipe 6: Review-feedback triage (qa-iterator)

A burst lane that fires every ~17 min, scans open PRs for reviewer P1/P2 comments, and lands minimal fixes. Measured: 4 review-comment PRs shipped in 5 cycles, all green CI, each fix under 20 LOC.

**Why this earns a lane:** PR reviewers (bots + humans) drop P1/P2 comments faster than coordinators address them. A 17-min cadence matches the bot re-review window.

**Setup:**

```
<lane-dir>/qa-iterator/prompt.md   # 8-block lane prompt
<lane-dir>/qa-iterator/memory.md   # append-only checkpoint log
CronCreate rrule: FREQ=MINUTELY;INTERVAL=17;COUNT=11  # ~3 hours, 11 fires max
```

**Hard rules:**
- SKIP any comment that requires a design decision the human would want to make.
- SKIP merges — reviewer approval is a human gate, not a bot gate.
- After COUNT expires (~3 hours), the cron auto-expires. Don't re-schedule without re-checking whether the fleet still has review debt.
- If the PR diff is > 3 KB, delegate reading to the secondary model (research dispatch) to keep the primary's context budget for judgment.

---

## 12. Creating / Updating / Deleting Lanes

### Creating a lane

1. **Pick the plan.** Every lane exists to drive one PLAN.md. If there is no plan, write one first (use `/vidux`) before creating the lane.

2. **Draft the prompt file** at `<lane-dir>/<lane-name>/prompt.md` using the 8-block structure (Section 10). Cite the PLAN.md path and list the files the agent must read every cycle.

3. **Seed the memory file** at `<lane-dir>/<lane-name>/memory.md`:
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

1. Edit `<lane-dir>/<lane-name>/prompt.md`. The next cron fire reads the edit, so the change is live within the cron cadence.
2. If you change the cadence, use `CronCreate` to replace the schedule.
3. If you change strategic direction mid-cycle, add a banner at the top of `memory.md`:
   ```
   > **LANE PRIORITY RESET YYYY-MM-DD:** <what changed>. See prompt.md for full guidance.
   ```

### Deleting a lane

1. Remove the cron via `CronDelete`.
2. Archive `<lane-dir>/<lane-name>/` to `<lane-dir>/_archive/<lane-name>-YYYY-MM-DD/`. Do NOT hard-delete — the memory.md is load-bearing history.
3. If the plan is complete, update PLAN.md Progress with a "lane closed" entry.

---

## 13. Memory Files

**Location:** `<lane-dir>/<lane-name>/memory.md`

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

### Research agent pairing

For external libraries, packages, or public documentation, a dedicated research tool beats the secondary model ~16.5x on token cost for package source lookups. Decision tree:

- **Package source / exact types** -> use a package search tool (reads real source)
- **"Where should I look?" / discovery** -> use quick research mode (citation lists, URL discovery)
- **Exact API / config syntax** -> use the secondary model (can do live web searches during reasoning)

### Deep research mode warning

**NEVER use deep research mode for implementation-critical questions.** Deep mode hallucinates config schemas and API signatures. It returns plausible-looking JSON with keys that don't exist in the real API. Citations are real URLs, but synthesized example code is pattern-matched from generic blog articles — not copied from cited docs. Classic RAG hallucination: retrieve correctly, synthesize incorrectly.

**Safe use of research tools:**
- Package search tools -> accurate, reads real package source
- Quick research mode -> good for citation lists and discovery
- Deep research mode -> DISCOVERY ONLY, do NOT paste its synthesized examples into code

### Prompt amplifier pairing

Before delegating a vague task, run it through a prompt amplifier to tighten the spec. A well-amplified prompt produces better compression AND lower secondary reasoning cost. Use when:

- The initial research question is vague ("how does auth work here?")
- The expected output format needs explicit structure
- The task has hidden constraints to surface before delegating

Don't amplify a tight, concrete prompt — the overhead isn't worth it.

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

Read this reference (loaded on demand from within a `/vidux` session) when:

- Setting up or modifying automation lanes (CronCreate, scheduled agents).
- Diagnosing fleet health, session bloat, or lane contention.
- Delegating work between agents (research / implementation dispatch).
- Running fleet scans, audits, or prescriptions.
- Creating or reviewing draft PRs from automation.

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
