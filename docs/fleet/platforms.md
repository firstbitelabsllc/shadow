# Platform Comparison: Claude Code vs Codex

Vidux is the discipline. Claude Code and Codex are two runtimes that execute vidux cycles on a schedule. This page documents the concrete differences so you can pick the right platform for each lane.

## At a Glance

| Feature | Claude Code | Codex |
|---|---|---|
| **Models** | Claude Opus / Sonnet / Haiku | GPT-5.x (gpt-5.4 default) |
| **Scheduling** | `CronCreate` — in-session, 5-field cron | TOML + rrule — persistent, survives app restart |
| **Auto-expire** | 7 days (session-bound) | None (runs until stopped or app closed) |
| **CLI automations** | Yes | **No** — Mac desktop app only |
| **Config location** | In-session (no config file) | `~/.codex/config.toml` |
| **Lane state** | Shared `<lane-dir>/<lane-id>/prompt.md` + `memory.md` | Shared `<lane-dir>/<lane-id>/prompt.md` + `memory.md`, plus `~/.codex/automations/<id>/automation.toml` |
| **Restart flow** | Re-schedule `CronCreate` on new session | Full-quit app → reopen (`osascript` + `open -a`) |
| **Sandbox** | N/A (local execution, full access) | `read-only` / `workspace-write` / `danger-full-access` |
| **Multi-agent** | `Agent()` subagents in-session | Codex's own same-runtime subagent primitive |
| **Session model** | Disposable sessions; lanes persist on disk | Desktop app process; automations in DB + TOML |
| **Session GC** | Required (`session-prune.py`, mandatory lane) | Not needed (app manages its own state) |
| **Max lanes** | 6 per session (worktree contention limit) | Limited by `max_threads` (default 6) |
| **Delegation** | Same-tool delegation when useful | Same-tool delegation when useful |

## Scheduling

### Claude Code

Scheduling uses `CronCreate`, a deferred tool that must be fetched before first use. Jobs are **session-scoped** — they die when the Claude Code process exits. Lanes survive across sessions because state lives on disk (`prompt.md` + `memory.md`), not in the cron.

```
CronCreate(cron: "8,38 * * * *", prompt: "Your cron prompt here...")
```

To restart a fleet after a session dies: re-schedule each `CronCreate` in the new session. Each lane reads its own `memory.md` and picks up where it left off.

**Hard limit:** 7-day auto-expire on all recurring jobs.

### Codex

Scheduling uses **TOML files + DB rows** read by the Mac desktop app. The Codex CLI (`codex` command) **cannot run automations**. All recurring work requires the desktop app.

Each automation lives at `~/.codex/automations/<id>/automation.toml` with a corresponding row in `~/.codex/sqlite/codex-dev.db`. In the current repo guidance, that TOML is a static shim which points at the real lane prompt on disk under a shared `<lane-dir>/<lane-id>/prompt.md`.

To create or update an automation: write the TOML, insert/update the DB row, verify with the repo helpers in `scripts/lib/codex-db.sh`, then **full-quit and reopen** the Codex app. `pkill app-server` alone is insufficient for new automations (Bug #15).

**No auto-expire.** Automations run until manually stopped or the app is closed.

## Persistence Model

Both platforms use the same persistence philosophy: **lanes persist on disk, sessions are disposable.**

### Claude Code

```
<lane-dir>/
├── <lane-id>/
│   ├── prompt.md      ← source of truth (read every cycle)
│   └── memory.md      ← append-only checkpoint log
└── ...
```

Session JSONLs (`~/.claude/projects/*/*.jsonl`) are hot storage — disposable, GC'd by `session-prune.py`. Lane files are cold storage — durable, never auto-deleted.

### Codex

```
~/.codex/automations/
├── <uuid>/
│   └── automation.toml  ← schedule shim + prompt pointer
└── ...

<lane-dir>/
└── <lane-id>/
    ├── prompt.md        ← editable lane prompt
    └── memory.md        ← append-only checkpoint log

~/.codex/sqlite/codex-dev.db  ← runtime state (automations table)
```

The DB and TOML must stay in sync. DB-only inserts create runnable but UI-invisible automations. TOML-only files are visible but do not fire.

## When to Use Which

| Scenario | Platform | Why |
|---|---|---|
| 24/7 fleet across account rotation | Claude Code | Session cycling + memory.md handoff works across accounts |
| Sub-hour cadence (< 60 min) | Claude Code | CronCreate supports any cron expression |
| Persistent automation (weeks/months) | Codex | No 7-day auto-expire |
| Durable Mac app automation | Codex | No auto-expire; recurrence lives in the app |
| Same-runtime subagent delegation | Either | Both runtimes support a same-tool delegation model now |
| Local toolchain (Xcode, simulators) | Claude Code | Full local access; Codex sandbox restricts |
| Multi-account rotation | Claude Code | Codex is per-app-install |

## Known Bugs (Codex, as of Apr 2026)

| # | Bug | Impact |
|---|---|---|
| 14 | New automations invisible after DB insert | Must full-quit app, not just restart app-server |
| 15 | `pkill app-server` insufficient for new rows | Electron frontend caches automation list separately |
| 16 | TOML files required for UI visibility | DB-only inserts are runnable but invisible in UI |
| 18 | Missing or wrong timestamp fields | Automation fails silently; use the repo helpers when possible |
| 22 | Raw newlines in prompt field | TOML parse failure; escape as `\n` |

Use `source scripts/lib/codex-db.sh && codex_verify_tomls` between writing TOMLs and reopening the app to catch these.

## See Also

- [Claude Code Lifecycle](claude-lifecycle.md) — full lifecycle of a Claude lane
- [Codex Lifecycle](codex-lifecycle.md) — full lifecycle of a Codex automation
- [Codex Setup Guide](codex-setup.md) — step-by-step Mac app setup
