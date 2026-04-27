# Recipe: Vidux on Codex (Native Runtime)

How to run vidux natively on Codex Desktop, where Codex is the primary (and only) tool. Codex is no longer a delegation target — it's a standalone runtime option with its own scheduling and subagent primitives.

This recipe is the exception path. In normal vidux automation flow, Codex defaults to **Chat** execution. Use this document only when you explicitly want a Codex automation to run repo-bound in `Local` or `Worktree`.

---

## When to use

- You run Codex Desktop (or Cursor's Codex extension) as your primary tool
- You want vidux's cycle (READ → ASSESS → ACT → VERIFY → CHECKPOINT) to run natively on Codex
- You need Codex's unlimited compute budget for long-cycle or heavy-read work
- You are **NOT** trying to mix Claude + Codex in one fleet (that pattern is deprecated — see `guides/recipes/subagent-delegation.md`)

---

## Runtime parity

Vidux core doctrine is **tool-agnostic**. The five principles, the cycle, the PLAN.md template, and the investigation pattern all work identically on Codex as on Claude. A Codex-run vidux cycle reads PLAN.md, picks a task, ships code, runs the verification gate, and checkpoints to memory.md — exactly the same shape as a Claude-run cycle.

What differs between runtimes:

| Surface | Claude Code | Codex Desktop |
|---|---|---|
| Scheduling primitive | `CronCreate` (session-scoped tool call) | `automations` table in SQLite + rrule |
| Registration surface | Tool call only (no disk) | DB row + filesystem TOML (both required) |
| Hot-reload of prompt | Yes — cron is a thin wrapper pointing at `prompt.md` | Yes, with the Dynamic Prompt Shim pattern |
| Restart requirement | Never — new session re-schedules crons | Full app quit + reopen whenever TOML changes |
| Subagent dispatch | `Agent()` tool | Codex's equivalent subagent primitive |

Core doctrine stays the same. Only the Part 2 automation mechanics swap out.

---

## Scheduling — the two coupled stores

Codex Desktop uses **two sources of truth** for every automation, and both must agree:

```
1. SQLite DB  — ~/.codex/sqlite/codex-dev.db → `automations` table
               Runtime source: this is what the scheduler fires on.
               Scanned continuously.

2. Filesystem — ~/.codex/automations/<id>/automation.toml
               UI source: this is what the Automations panel displays.
               Scanned ONCE at app startup.
```

If the DB row is missing, the automation never fires (no matter how perfect the TOML). If the TOML is missing, the UI won't show it but the scheduler still runs it — invisible-but-live is worse than broken-and-visible. **Keep both in sync.**

### Prerequisites

```bash
ls ~/.codex/sqlite/codex-dev.db         # runtime DB must exist
ls ~/.codex/automations/                # lane directory root
grep -E "^(model|sandbox_mode)" ~/.codex/config.toml
```

The `~/.codex/automations/` directory must be a **real directory, not a symlink**. Codex's startup scan uses `isDirectory()` which filters out symlinks — automations stored behind a symlink never register.

---

## The Dynamic Prompt Shim pattern

Codex caches `automation.toml` at app startup. Editing the TOML normally requires a full-quit + reopen to take effect. The Dynamic Prompt Shim sidesteps this by making the TOML prompt **static** and pointing at an editable `prompt.md` on disk:

```
~/.codex/automations/<lane-id>/automation.toml  — static shim (changes never)
<lane-dir>/<lane-id>/prompt.md       — the real prompt (hot-editable)
<lane-dir>/<lane-id>/memory.md       — lane memory
```

Lane state (prompt.md + memory.md) lives under a shared `<lane-dir>/` — pick one convention per fleet (e.g. `~/.vidux/lanes/`, `~/.claude-automations/`, `~/.codex-automations/`, or a project-scoped directory) and reuse it across runtimes. Mixing conventions is fine; keeping prompt + memory paired inside the same `<lane-dir>/<lane-id>/` is what matters.

**The static shim prompt** (goes in `automation.toml`):

```
prompt = "Read <lane-dir>/<lane-id>/prompt.md FIRST. Execute one vidux cycle: READ → ASSESS → ACT → VERIFY → CHECKPOINT.\nHonor all constraints in the prompt file.\nAppend one line to memory.md at the end."
```

The shim points Codex at the real prompt on disk. Edits to `prompt.md` take effect on the **next fire** — no Codex restart needed. This is the primary win: you can iterate on lane behavior without restarting the app every time.

TOML constraint: `prompt` must be **single-line**. Escape newlines as `\n`. Raw newlines break TOML parsing (Bug #22).

---

## Registration recipe

Every new automation follows this exact 5-step sequence:

```
1. Write automation.toml       → disk (UI visibility source)
2. Insert DB row               → sqlite (runtime source)
3. Write prompt.md + memory.md → disk (lane state — hot-reload target)
4. Run codex_verify_tomls      → catches missing fields / TOML-DB drift
5. Full-quit + reopen the app  → clears Electron cache (Bug #14/#15)
```

### Batch INSERT (SQL)

```sql
INSERT INTO automations (
  id, name, prompt, status, rrule, cwds,
  model, reasoning_effort, created_at, updated_at
) VALUES (
  'my-coordinator',
  'my coordinator',
  'Read <lane-dir>/my-coordinator/prompt.md FIRST...\n...',
  'ACTIVE',
  'FREQ=MINUTELY;INTERVAL=30',
  '["/path/to/repo"]',
  'gpt-5.4',
  'medium',
  <unix-epoch-milliseconds>,
  <unix-epoch-milliseconds>
);
```

**Field notes (all required unless noted):**

- `id` — must match the TOML filename's parent dir AND the TOML's `id` field. All three must agree.
- `prompt` — single-line, newlines escaped as `\n`.
- `rrule` — RFC 5545. Common patterns: `FREQ=MINUTELY;INTERVAL=30`, `FREQ=HOURLY;INTERVAL=1;BYMINUTE=0`, `FREQ=DAILY;BYHOUR=9;BYMINUTE=0`.
- `cwds` — JSON-style array of absolute paths. Codex runs in the first path by default.
- `created_at` / `updated_at` — **both required.** Missing either causes silent failure (Bug #18). Use millisecond epoch integers (`python3 -c 'import time; print(int(time.time() * 1000))'`) or `codex_db_epoch_ms` from `scripts/lib/codex-db.sh`.

### Python batch registration

For registering multiple lanes at once, wrap the INSERT in Python:

```python
import sqlite3, time, os

db = os.path.expanduser("~/.codex/sqlite/codex-dev.db")
conn = sqlite3.connect(db)
now = int(time.time() * 1000)

for lane in lanes:  # lanes = list of dicts with id, name, rrule, cwds, ...
    conn.execute("""
        INSERT OR REPLACE INTO automations
            (id, name, prompt, status, rrule, cwds,
             model, reasoning_effort, created_at, updated_at)
        VALUES (?, ?, ?, 'ACTIVE', ?, ?, 'gpt-5.4', 'medium', ?, ?)
    """, (lane['id'], lane['name'], SHIM_PROMPT.format(id=lane['id']),
          lane['rrule'], lane['cwds'], now, now))

conn.commit()
conn.close()
```

After the INSERTs, **full-quit and reopen Codex** before the first fire.

Before the reopen, source `scripts/lib/codex-db.sh` and run `codex_verify_tomls` so broken prompt lines or missing TOMLs fail locally instead of on the next fire.

---

## Safety rules

1. **Never edit `automations` while Codex is running.** The app holds an in-memory cache; writes from `sqlite3` can race the cache and get overwritten. Stop the app first (`osascript -e 'tell application "Codex" to quit'`), write, then reopen.
2. **`~/.codex/automations/` must be a real directory, not a symlink.** Codex's startup scan filters symlinks via `isDirectory()`. If you need to share automation definitions across machines, symlink individual lane subfolders into a real parent — never symlink the parent itself.
3. **Never register without both stores.** DB row without TOML = invisible-but-live. TOML without DB row = visible-but-dead. Both must exist.
4. **Never bypass pre-commit hooks with `--no-verify`.** Pre-commit hooks (prettier, lint, typecheck, SwiftLint) are the review trail on Codex as on Claude. If a hook fails: document the failure in memory.md, write `[BLOCKED-CI-HOOK]`, exit. A human fixes the hook, not the automation.
5. **Full-quit on every schema change.** `pkill -f codex-app-server` leaves the Electron frontend alive with stale cache. Use `osascript -e 'tell application "Codex" to quit' && sleep 3 && open -a "Codex"`.

---

## Cycling Codex sessions

Claude Code has `/resume` for fresh sessions picking up lanes from disk. Codex's equivalent is a full-quit + reopen — the app restarts, re-reads the DB, and resumes scheduling. Lanes pick up from `memory.md` on the next fire.

Codex state GC is managed externally, not by Codex itself. Worktree cleanup for Codex-spawned worktrees is the operator's responsibility — Codex auto-delete is OFF, and a sensible retention policy for `~/Development/<repo>-worktrees/codex-*` is 3h minimum. Without external GC, worktrees accumulate at ~84/day at 10 GB under a heavy-cadence fleet.

There is no Codex equivalent of `session-prune.py --gc-old` — Codex's conversation logs live elsewhere (Electron's IndexedDB) and are not JSONL-shaped. If you notice Codex slowing down, the fix is a full app restart, not a log-pruning script.

---

## Cross-tool delegation IS deprecated

**Do not mix Claude and Codex in one fleet.** If you run Codex, run Codex-only: Codex lanes spawn Codex subagents via Codex's own `Agent()`-equivalent primitive. "Claude directs, Codex executes" was tried and retired in vidux 2.10.0 for context-loss and prompt-shim fragility (see `guides/recipes/subagent-delegation.md` § Deprecated patterns).

The shared `~/.agent-ledger/activity.jsonl` still works for cross-session cross-fleet visibility when both runtimes happen to touch the same repo — that's not delegation, it's just telemetry.

---

## See Also

- `guides/automation.md` — platform-agnostic automation doctrine
- `guides/recipes/subagent-delegation.md` — same-tool Mode A / Mode B dispatch
- `docs/fleet/codex-setup.md` — full step-by-step setup walkthrough with verification checklist
- `docs/fleet/codex-lifecycle.md` — what happens each fire, known bugs catalog
- `docs/fleet/platforms.md` — Claude Code vs Codex comparison table
