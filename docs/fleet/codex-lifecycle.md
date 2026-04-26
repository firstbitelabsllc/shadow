# Codex Automation Lifecycle

A Codex lane is a recurring vidux cycle scheduled via a **TOML file + DB row** read by the Codex Mac desktop app. This page documents the full lifecycle from creation to troubleshooting, including the app-restart discipline that is unique to Codex.

## Prerequisites

- Codex Mac desktop app installed (CLI `codex` alone **cannot run automations** — recurring work lives in the desktop app)
- `~/.codex/config.toml` with `sandbox_mode` + `model` set
- `sqlite3` CLI for DB operations
- Local vidux checkout so you can `source scripts/lib/codex-db.sh` and use the shipped helpers (`codex_verify_tomls`, `codex_sync_tomls`, `codex_safe_restart`)

## Lane Files

Every Codex lane has four pieces that must stay in sync:

```
~/.codex/automations/{id}/automation.toml  ← schedule + static shim prompt (UI source)
~/.codex/sqlite/codex-dev.db               ← runtime source (one row per lane)
{lane-dir}/{lane-id}/prompt.md             ← real instructions, hot-editable
{lane-dir}/{lane-id}/memory.md             ← append-only checkpoint log
```

**The TOML and DB row register the automation.** `prompt.md` and `memory.md` hold the actual lane state. DB-only inserts are runnable but invisible in the UI (Bug #16). TOML-only files are visible but never fire. The shared lane directory is what makes the next fire pick up prompt edits and checkpoint history without rewriting the registration.

## Creation

### 1. Write the TOML

```toml
version = 1
id = "project-coordinator"
kind = "cron"
name = "project coordinator"
prompt = "Read {lane-dir}/project-coordinator/prompt.md FIRST...\nThen execute one vidux cycle."
status = "ACTIVE"
rrule = "FREQ=MINUTELY;INTERVAL=30"
model = "gpt-5.4"
reasoning_effort = "medium"
execution_environment = "worktree"
cwds = ["/path/to/repo"]
created_at = 1744761600
updated_at = 1744761600
```

**Required fields** in the public examples and the helper-generated TOMLs (`codex_sync_tomls`) are: `version`, `id`, `kind`, `name`, `prompt`, `status`, `rrule`, `model`, `reasoning_effort`, `execution_environment`, `cwds`, `created_at`, `updated_at`. Missing `created_at` / `updated_at` causes silent failure (Bug #18).

`execution_environment = "worktree"` is the current registration shape written by the shipped Codex helpers. Sandbox access still comes from `sandbox_mode` in `~/.codex/config.toml`.

**Prompt field is single-line.** Escape newlines as `\n` — raw newlines in the TOML break parsing (Bug #22).

### 2. Insert the DB row

```sql
INSERT INTO automations (id, name, prompt, status, rrule, cwds, model, reasoning_effort, created_at, updated_at)
VALUES ('project-coordinator', 'project coordinator', '{prompt}', 'ACTIVE',
        'FREQ=MINUTELY;INTERVAL=30', '["/path/to/repo"]',
        'gpt-5.4', 'medium', 1744761600, 1744761600);
```

### 3. Verify

```bash
source scripts/lib/codex-db.sh
codex_verify_tomls
```

Exit 0 = safe to reopen. Exit 1 = fix errors before reopening.

This is the repo's lightweight preflight: it confirms that active DB rows have TOML files with prompt lines before reopen. For the full shipped quit → sync → reopen path, use `codex_safe_restart`.

### 4. Full-quit and reopen the Codex app

```bash
osascript -e 'tell application "Codex" to quit'
sleep 3
open -a "Codex"
```

**`pkill app-server` is insufficient** for new automations (Bug #15). The Electron frontend caches the automation list separately from the server process — only a full quit clears it.

## Cycle Execution

Each rrule fire launches a fresh Codex agent in the configured `cwds`. The agent executes one vidux cycle:

```
1. READ     prompt.md → memory.md (last 3 entries) → PLAN.md → INBOX.md
2. GATE     Dirty tree not mine? → [QC] exit. 3x stuck? → [blocked]. Main CI red? → fix.
3. ASSESS   Priority: CI red → PR fix → PR merge → resume in_progress → next pending → filler audit
4. ACT      Worktree per code change. Research dispatch (read-only) / implementation dispatch (workspace-write) per task.
5. VERIFY   Build passes. Tests pass. Visual check for UI.
6. CHECKPOINT  Append one line to memory.md. Update PLAN.md status. Commit if code changed.
```

### Sandbox modes

Codex agents run inside one of three sandboxes, set per-task or per-session in `config.toml`:

| Mode | Reads | Writes | Use |
|---|---|---|---|
| `read-only` | Yes | No | Research dispatch — compressed summaries |
| `workspace-write` | Yes | Working tree only | Implementation dispatch — code edits |
| `danger-full-access` | Yes | Anywhere | Trusted automations only |

Research dispatch keeps the parent context small; implementation dispatch hands a bounded write task to a secondary Codex agent. See [Fleet Operations](/fleet/operations) for the docs-site summary of that delegation and coordination model.

### Post-push defer

Same as Claude lanes: after pushing a PR, the lane MUST NOT attempt merge in the same cycle. CI and review automation need time to run. Merge eligibility: CI green + ≥1h since last fix-push + no unresolved required findings.

## Persistence Model

Codex lanes persist differently from Claude lanes:

- **TOML + DB row** live on disk; they survive app quit, reboot, and account-level changes
- **`prompt.md` + `memory.md`** live in the shared lane directory and are the durable lane state
- **Agent sessions** live inside the desktop app process; they die when the app quits
- **No session GC needed** — the Codex app manages its own memory internally (no growing JSONL files to prune)

When the Mac app reopens after a quit, it reads the DB, resumes all `ACTIVE` automations, and fires them per their rrule. Each fire reads the shared `prompt.md` and `memory.md` to pick up where the lane left off.

**No auto-expire.** Codex automations run until manually stopped (`status = 'PAUSED'` or DB delete) or the app is closed permanently.

## Known Bugs

| # | Symptom | Fix |
|---|---|---|
| 14 | New automation invisible after DB insert | Full-quit app (`osascript 'quit'`), not just restart app-server |
| 15 | `pkill app-server` doesn't pick up new rows | Electron frontend caches automation list separately — full quit required |
| 16 | TOML files required for UI visibility | DB-only inserts are runnable but hidden — always write both |
| 18 | Automation fails silently | Missing `created_at` / `updated_at` — both must be set to unix epoch |
| 22 | TOML parse failure on multi-line prompts | Raw newlines break parsing — escape as `\n` |

Use `codex_verify_tomls` as the lightweight local preflight, or `codex_safe_restart` for the full shipped quit → sync → reopen path.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Automation not firing | App quit or rrule typo | Reopen app; check `rrule` syntax (RFC 5545) |
| Automation invisible in UI | TOML missing or DB-only | Write both TOML + DB row, full-quit + reopen |
| Silent failure on fire | Missing `created_at` / `updated_at` | Fill both; run verify script |
| Prompt truncated | Raw newline in TOML | Replace `\n` with `\\n` escape; re-verify |
| Lane can't write files | Sandbox = `read-only` | Switch to `workspace-write` for implementation dispatch tasks |
| Can't run from CLI | Expected — CLI doesn't support automations | Use Mac desktop app |

## See Also

- [Platform Comparison](platforms.md) — Claude Code vs Codex overview
- [Claude Code Lifecycle](claude-lifecycle.md) — the Claude equivalent of this page
- [Codex Setup Guide](codex-setup.md) — step-by-step Mac app setup (Task 5)
- [Fleet Operations](/fleet/operations) — research and implementation dispatch plus worktree discipline
- [Recipe Catalog](/fleet/recipes) — reusable automation patterns layered on top
