# Claude Code Lane Lifecycle

A Claude Code lane is a recurring vidux cycle scheduled via `CronCreate` inside a live Claude Code session. This page documents the full lifecycle from creation to session death and recovery.

## Prerequisites

- Claude Code CLI or desktop app running
- `CronCreate` tool available (fetch via `ToolSearch("select:CronCreate")` — it's a deferred tool)

## Lane Files

Every lane has two files on disk:

```
{lane-dir}/{lane-name}/
├── prompt.md      ← source of truth (read every cycle)
└── memory.md      ← append-only checkpoint log
```

The **prompt** is the full instruction set — mission, read list, gate rules, assess priority, act steps, authority boundaries, checkpoint format. It follows the [8-block structure](../reference/prompt-template.md).

The **memory** is the lane's durable state. One line per cycle. Any new session reads this to pick up where the last one left off.

## Creation

```
CronCreate(
  cron: "8,38 * * * *",   // fires at :08 and :38 past each hour
  prompt: "**Claude cron: {name} (every 30 min)**\n\nYour instructions live at {lane-dir}/{name}/prompt.md. Read that file FIRST..."
)
```

The cron prompt is a **thin wrapper** — it tells the agent where to find the real instructions and lists critical constraints that must be honored even if `prompt.md` is missing. The heavy logic lives on disk.

**Returned:** a job ID (e.g., `ee960240`) for `CronDelete`.

## Cycle Execution

Each cron fire injects the prompt into the live session. The agent then executes one vidux cycle:

```
1. READ     prompt.md → memory.md (last 3 entries) → git fetch + status → PLAN.md → INBOX.md
2. GATE     Dirty tree not mine? → [QC] exit. 3x stuck? → [blocked]. Main CI red? → fix.
3. ASSESS   Priority: CI red → PR fix → PR merge → resume in_progress → next pending → filler audit
4. ACT      Worktree per code change. Lint + build before commit. Verify branch after commit.
5. VERIFY   Build passes. Tests pass. Visual check for UI.
6. CHECKPOINT  Append one line to memory.md. Update PLAN.md status. Commit if code changed.
```

### Post-push defer

After pushing a PR, the lane MUST NOT attempt merge in the same cycle. This gives CI and review automation time to run. Merge eligibility: CI green + ≥1h since last fix-push + no unresolved required findings.

## Session Cycling

Sessions are disposable. They die for many reasons:

- Multi-account rotation when a fleet spreads load across sessions
- Laptop sleep / lid close
- Compaction pressure (JSONL too large)
- Manual `/resume`
- Process crash

**When a session dies, the cron dies with it.** But the lane files (`prompt.md` + `memory.md`) survive on disk. When a new session starts:

1. Re-schedule `CronCreate` with the same prompt pointing to the same `prompt.md`
2. The first cycle reads `memory.md` and picks up exactly where the last session left off
3. No state is lost — the lane resumes from disk

This is the core invariant: **lanes persist, sessions cycle.**

## Session GC

Without garbage collection, session JSONLs grow unbounded and `/resume` becomes slow. A mandatory `session-gc` lane runs hourly (or every 30 min) to:

1. Delete main session JSONLs older than 3 days
2. Delete subagent JSONLs older than 1 day
3. Measure the current session's size and growth rate
4. Emit a `[CYCLE SIGNAL]` when the session exceeds 40 MB

The GC lane uses an operator-provided JSONL cleanup helper and NEVER touches lane files, ledger, or git repos. This repo documents the lane pattern, but it does not ship the pruning script itself.

### CYCLE SIGNAL

When a session crosses 40 MB, the GC lane emits a signal in its memory. This is a recommendation to `/resume` to a fresh session — not an automatic action. The operator decides when to cycle.

**Growth patterns (measured):**
- Checkpoint-only cycle: ~0-1 MB
- Filler audit cycle: ~1-2 MB
- Ship cycle (worktree + build + PR): ~16 MB

## Lane Count

Hard cap: **6 lanes per session.** More than 6 causes worktree contention and JSONL bloat. Measured, not theoretical.

The default fleet for one repo is:

| Lane | Role | Cadence |
|---|---|---|
| `<repo>-coordinator` | Ship + fix CI + merge PRs + archive PLAN.md | ~30 min |
| `session-gc` | Delete old JSONLs, measure growth | 30-60 min |

Add burst lanes only when drift is measured. See [platforms.md](platforms.md) for the full decision tree.

## Auto-Expire

All `CronCreate` jobs auto-expire after **7 days**. This bounds session lifetime. If the fleet needs to run longer, the operator re-schedules the crons in a new session.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Cron not firing | Session died or auto-expired | Re-schedule `CronCreate` |
| Lane stuck on same task | 3x stuck rule not triggered | Check memory.md for 3+ consecutive same-task entries |
| Dirty tree blocking ops | Another session's uncommitted work | `[QC] concurrent-cycle` exit; wait for other session |
| JSONL growing fast | Ship cycles or ScheduleWakeup bloat | Prefer `CronCreate` over `ScheduleWakeup` for 10+ fires |
| Branch hijack after commit | `lint-staged` stash interference | Always verify `git branch --show-current` after commit |

## See Also

- [Platform Comparison](platforms.md) — Claude Code vs Codex overview
- [Codex Lifecycle](codex-lifecycle.md) — the Codex equivalent of this page
- [Prompt Template](../reference/prompt-template.md) — the 8-block prompt structure
