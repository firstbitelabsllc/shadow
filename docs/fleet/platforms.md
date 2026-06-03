# Platform Comparison: Claude Code vs Codex

Vidux is the discipline. Claude Code and Codex are two runtimes that execute vidux cycles on a schedule. Cursor can run the same discipline interactively or as an editor-bound worker when the surrounding toolchain supports it. This page documents the concrete differences so you can pick the right platform for each lane without changing the proof model.

For Codex, this page describes the native automation path that registers a repo-bound lane with the desktop app. The automation guide treats `Chat` as the default for Codex-created automations; `Local` and `Worktree` are explicit opt-ins when the lane truly needs direct project-folder execution.

## At a Glance

| Feature | Claude Code | Codex |
|---|---|---|
| **Models** | Claude Opus / Sonnet / Haiku | GPT-5.x (gpt-5.4 default) |
| **Scheduling** | `CronCreate` — in-session, 5-field cron | TOML + rrule — persistent, survives app restart |
| **Auto-expire** | 7 days (session-bound) | None (runs until stopped or app closed) |
| **CLI automations** | Yes | **No** — Mac desktop app only |
| **Config location** | In-session (no config file) | `~/.codex/config.toml` |
| **Lane files** | Shared `{lane-dir}/{lane-id}/` for `prompt.md` instructions + `memory.md` lane-local log | Shared `{lane-dir}/{lane-id}/` for `prompt.md` instructions + `memory.md` lane-local log |
| **Automation registration** | Session-scoped `CronCreate` job | `automation.toml` + DB row |
| **Restart flow** | Re-schedule `CronCreate` on new session | Full-quit app → reopen (`osascript` + `open -a`) |
| **Sandbox** | N/A (local execution, full access) | `read-only` / `workspace-write` / `danger-full-access` |
| **Multi-agent** | Native subagents in-session | Native subagents in-session |
| **Session model** | Disposable sessions; lanes persist on disk | Desktop app process; automations in DB + TOML |
| **Session GC** | Required (`session-gc` lane + operator-provided JSONL cleanup helper) | Not needed (app manages its own state) |
| **Max lanes** | 6 per session (worktree contention limit) | No separate repo-defined Codex cap |
| **Delegation** | Mode A / Mode B via native subagents | Mode A / Mode B via native subagents |

For Codex, the table above applies to native scheduled automations. A Chat-mode Codex automation skips the TOML + DB registration path and only needs the shared lane files and prompt discipline.

## Shared lifecycle contract

Scheduling and sandboxing differ, but the runtime proof packet should look the same:

- Config readiness: run `vidux config check --json` before trusting plan-store or adapter paths. Use `vidux config show --json` when a redacted human summary is needed.
- Pre-task hook: run `scripts/vidux-doctor.sh --json` for runtime health. Reserve `vidux doctor` for terminal install/readiness checks because it may run `npm test`.
- Signpost run id: set one `VIDUX_SIGNPOST_RUN_ID` for the parent cycle and reuse it for pre-task, subagent, verification, and after-task events.
- Call-stack signposts: emit `hook.beforeTask`, `subagent.spawn`, `task.verify`, and `hook.afterTask`, then inspect them with `vidux signpost trace --run-id <id>`.
- Runtime attribution: set `VIDUX_RUNTIME=claude`, `VIDUX_RUNTIME=codex`, or `VIDUX_RUNTIME=cursor` for spawned workers when inherited environment variables would otherwise misattribute the event.
- Durable handoff: update the owning `PLAN.md` and emit the matching publish ledger row with task id, proof, handoff status, files claimed, path-like claims, and next-agent resume before any branch/PR/release publish.

Use `vidux signpost lifecycle-smoke --json` as the disposable cross-runtime trace-shape smoke. Use `vidux signpost spawned-subagent-smoke --json` for the disposable inherited-env attribution smoke. Both are intentionally local: they verify expected Codex/Claude/Cursor call-stack labels and env attribution, not that those external tools actually ran.

## Scheduling

### Claude Code

Scheduling uses `CronCreate`, a deferred tool that must be fetched via `ToolSearch` before first use. Jobs are **session-scoped** — they die when the Claude Code process exits. Lanes survive across sessions because instructions and local cycle notes live under the shared lane directory, while shipped-work proof lives in the owning plan plus publish ledger rows.

```
CronCreate(cron: "8,38 * * * *", prompt: "Your cron prompt here...")
```

To restart a fleet after a session dies: re-schedule each `CronCreate` in the new session. Each lane reads its own `memory.md` for local cycle orientation, then resumes from the owning plan plus publish ledger proof.

**Hard limit:** 7-day auto-expire on all recurring jobs.

### Codex

Scheduling uses **TOML files + DB rows** read by the Mac desktop app. The Codex CLI (`codex` command) **cannot run automations** — it can only run one-shot commands. All recurring work requires the desktop app.

This is the opt-in native path. If a Codex automation can stay in Chat mode, prefer that simpler default and only use the native registration flow when the lane needs direct `Local` or `Worktree` execution.

Each automation lives at `~/.codex/automations/{id}/automation.toml` with a corresponding row in `~/.codex/sqlite/codex-dev.db`. The actual lane instructions and local cycle notes live under a shared `{lane-dir}/{lane-id}/`. All four pieces matter: the DB is the runtime source, the TOML is the UI source, and the owning plan plus publish ledger rows carry shipped-work proof.

To create or update an automation: write the TOML, insert/update the DB row, then **full-quit and reopen** the Codex app. `pkill app-server` alone is insufficient for new automations (Bug #15).

**No auto-expire.** Automations run until manually stopped or the app is closed.

## Persistence Model

Both platforms use the same persistence philosophy: **lanes persist on disk, sessions are disposable.**

### Claude Code

```
{lane-dir}/
├── project-coordinator/
│   ├── prompt.md      ← lane instructions (read every cycle)
│   └── memory.md      ← lane-local cycle log
├── session-gc/
│   ├── prompt.md
│   └── memory.md
└── ...
```

Session JSONLs (`~/.claude/projects/*/*.jsonl`) are hot storage — disposable, typically pruned by the session-gc lane's chosen cleanup helper. Lane files are cold storage — durable, never auto-deleted.

### Codex

```
~/.codex/automations/{id}/automation.toml  ← schedule + static shim prompt
~/.codex/sqlite/codex-dev.db               ← runtime state (automations table)
{lane-dir}/{lane-id}/prompt.md             ← real instructions
{lane-dir}/{lane-id}/memory.md             ← lane-local cycle log
```

The DB and TOML must stay in sync. DB-only inserts create runnable but UI-invisible automations. TOML-only files are visible but do not fire. The shared lane directory keeps prompt edits and lane-local cycle history durable across restarts; the owning plan plus publish ledger keeps shipped-work proof durable.

## When to Use Which

| Scenario | Platform | Why |
|---|---|---|
| 24/7 fleet across account rotation | Claude Code | Session cycling + lane-local memory notes plus plan/ledger handoff works across accounts |
| Sub-hour cadence (< 60 min) | Claude Code | CronCreate supports any cron expression |
| Persistent automation (weeks/months) | Codex | No 7-day auto-expire |
| Heavy code generation | Codex | Long-lived desktop automation + native worktree editing |
| Research / file reading > 3 KB | Codex | Mode A summaries keep the parent context small in a native Codex lane |
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

Run `codex_verify_tomls` (from `scripts/lib/codex-db.sh`) as the lightweight local preflight before reopen, or use `codex_safe_restart` for the full shipped quit → sync → reopen path.

## See Also

- [Claude Code Lifecycle](claude-lifecycle.md) — full lifecycle of a Claude lane
- [Codex Lifecycle](codex-lifecycle.md) — full lifecycle of a Codex automation
- [Codex Setup Guide](codex-setup.md) — step-by-step Mac app setup
