# Platform Comparison: Claude Code vs Codex

Vidux is the discipline. Claude Code and Codex are two runtimes that execute vidux cycles on a schedule. This page documents the concrete differences so you can pick the right platform for each lane.

## At a Glance

| Feature | Claude Code (`/vidux-claude`) | Codex (`/vidux-codex`) |
|---|---|---|
| **Models** | Claude Opus / Sonnet / Haiku | GPT-5.x (gpt-5.4 default) |
| **Scheduling** | `CronCreate` — in-session, 5-field cron | TOML + rrule — persistent, survives app restart |
| **Auto-expire** | 7 days (session-bound) | None (runs until stopped or app closed) |
| **CLI automations** | Yes | **No** — Mac desktop app only |
| **Config location** | In-session (no config file) | `~/.codex/config.toml` |
| **Lane state** | `~/.claude-automations/<name>/` | `~/.codex/automations/<id>/` |
| **Lane files** | `prompt.md` + `memory.md` | `automation.toml` + `memory.md` + DB row |
| **Restart flow** | Re-schedule `CronCreate` on new session | Full-quit app → reopen (`osascript` + `open -a`) |
| **Sandbox** | N/A (local execution, full access) | `read-only` / `workspace-write` / `danger-full-access` |
| **Multi-agent** | `Agent` tool (subagents in-session) | `max_depth` / `max_threads` in config.toml |
| **Session model** | Disposable sessions; lanes persist on disk | Desktop app process; automations in DB + TOML |
| **Session GC** | Required (`session-prune.py`, mandatory lane) | Not needed (app manages its own state) |
| **Max lanes** | 6 per session (worktree contention limit) | Limited by `max_threads` (default 6) |
| **Delegation** | N/A (Claude is the writer) | Mode A (research) / Mode B (implementation) |

## Scheduling

### Claude Code

Scheduling uses `CronCreate`, a deferred tool that must be fetched via `ToolSearch` before first use. Jobs are **session-scoped** — they die when the Claude Code process exits. Lanes survive across sessions because state lives on disk (`prompt.md` + `memory.md`), not in the cron.

```
CronCreate(cron: "8,38 * * * *", prompt: "Your cron prompt here...")
```

To restart a fleet after a session dies: re-schedule each `CronCreate` in the new session. Each lane reads its own `memory.md` and picks up where it left off.

**Hard limit:** 7-day auto-expire on all recurring jobs.

### Codex

Scheduling uses **TOML files + DB rows** read by the Mac desktop app. The Codex CLI (`codex` command) **cannot run automations** — it can only run `codex exec` for one-shot delegation. All recurring work requires the desktop app.

Each automation lives at `~/.codex/automations/<id>/automation.toml` with a corresponding row in `~/.codex/sqlite/codex-dev.db`. Both must exist: the DB is the runtime source, the TOML is the UI source (Bug #16).

To create or update an automation: write the TOML, insert/update the DB row, then **full-quit and reopen** the Codex app. `pkill app-server` alone is insufficient for new automations (Bug #15).

**No auto-expire.** Automations run until manually stopped or the app is closed.

## Persistence Model

Both platforms use the same persistence philosophy: **lanes persist on disk, sessions are disposable.**

### Claude Code

```
~/.claude-automations/
├── leojkwan-coordinator/
│   ├── prompt.md      ← source of truth (read every cycle)
│   └── memory.md      ← append-only checkpoint log
├── session-gc/
│   ├── prompt.md
│   └── memory.md
└── ...
```

Session JSONLs (`~/.claude/projects/*/*.jsonl`) are hot storage — disposable, GC'd by `session-prune.py`. Lane files are cold storage — durable, never auto-deleted.

### Codex

```
~/.codex/automations/
├── <uuid>/
│   ├── automation.toml  ← schedule + prompt + config
│   └── memory.md        ← append-only checkpoint log
└── ...

~/.codex/sqlite/codex-dev.db  ← runtime state (automations table)
```

The DB and TOML must stay in sync. DB-only inserts create runnable but UI-invisible automations. TOML-only files are visible but don't fire.

## When to Use Which

| Scenario | Platform | Why |
|---|---|---|
| 24/7 fleet across account rotation | Claude Code | Session cycling + memory.md handoff works across accounts |
| Sub-hour cadence (< 60 min) | Claude Code | CronCreate supports any cron expression |
| Persistent automation (weeks/months) | Codex | No 7-day auto-expire |
| Heavy code generation | Codex (Mode B) | Unlimited tokens for code writing |
| Research / file reading > 3 KB | Codex (Mode A) | Compressed summary saves Claude tokens |
| Local toolchain (Xcode, simulators) | Claude Code | Full local access; Codex sandbox restricts |
| Multi-account rotation | Claude Code | Codex is per-app-install |

## Known Bugs (Codex, as of Apr 2026)

| # | Bug | Impact |
|---|---|---|
| 14 | New automations invisible after DB insert | Must full-quit app, not just restart app-server |
| 15 | `pkill app-server` insufficient for new rows | Electron frontend caches automation list separately |
| 16 | TOML files required for UI visibility | DB-only inserts are runnable but invisible in UI |
| 18 | Missing `created_at` / `updated_at` | Automation fails silently |
| 22 | Raw newlines in prompt field | TOML parse failure; escape as `\n` |

Run `codex-toml-verify.sh` between writing TOMLs and reopening the app to catch these.

## See Also

- [Claude Code Lifecycle](claude-lifecycle.md) — full lifecycle of a Claude lane
- [Codex Lifecycle](codex-lifecycle.md) — full lifecycle of a Codex automation
- [Codex Setup Guide](codex-setup.md) — step-by-step Mac app setup
