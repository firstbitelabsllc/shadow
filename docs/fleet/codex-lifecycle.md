# Codex Automation Lifecycle

A Codex lane is a recurring vidux cycle scheduled via a **TOML shim + DB row** read by the Codex Mac desktop app. This page documents the lifecycle the current repo actually supports: static `automation.toml`, shared lane files on disk, DB verification helpers, and full-app restart when the schedule changes.

## Prerequisites

- Codex Mac desktop app installed (CLI `codex` alone **cannot run automations**)
- `~/.codex/config.toml` with `sandbox_mode` + `model` set
- `sqlite3` CLI for DB operations
- this repo's `scripts/lib/codex-db.sh` helpers for DB reads/writes and TOML verification

## Lane Files

Every Codex lane has four pieces that must stay in sync:

```
~/.codex/automations/<id>/
└── automation.toml   ← schedule shim + prompt pointer (UI source)

<lane-dir>/<lane-id>/
├── prompt.md         ← editable lane instructions
└── memory.md         ← append-only checkpoint log

~/.codex/sqlite/codex-dev.db
└── automations table ← runtime source (one row per lane)
```

**Both the TOML and the DB row must exist.** DB-only inserts are runnable but invisible in the UI (Bug #16). TOML-only files are visible but never fire. The DB is what the runtime reads; the TOML is what the UI renders. The repo's current guidance keeps the real prompt and memory outside the TOML so lane instructions stay hot-editable.

## Creation

### 1. Write the TOML

```toml
version = 1
id = "my-project-coordinator"
kind = "cron"
name = "my project coordinator"
prompt = "Read <lane-dir>/my-project-coordinator/prompt.md FIRST. Execute one vidux cycle: READ → ASSESS → ACT → VERIFY → CHECKPOINT.\nHonor all constraints in the prompt file.\nAppend one line to memory.md at the end."
status = "ACTIVE"
rrule = "FREQ=MINUTELY;INTERVAL=30"
model = "gpt-5.4"
reasoning_effort = "medium"
execution_environment = "sandbox"
cwds = ["/absolute/path/to/project"]
created_at = 1744761600000
updated_at = 1744761600000
```

**Required fields** (verified by the repo helpers): `version`, `id`, `kind`, `name`, `prompt`, `status`, `rrule`, `model`, `reasoning_effort`, `execution_environment`, `cwds`, `created_at`, `updated_at`. Missing or malformed timestamps cause silent failure (Bug #18).

**Prompt field is single-line.** Escape newlines as `\n` — raw newlines in the TOML break parsing (Bug #22).

### 2. Insert the DB row

```sql
INSERT INTO automations (id, name, prompt, status, rrule, cwds, model, reasoning_effort, created_at, updated_at)
VALUES ('my-project-coordinator', 'my project coordinator', '<prompt>', 'ACTIVE',
        'FREQ=MINUTELY;INTERVAL=30', '["/absolute/path/to/project"]',
        'gpt-5.4', 'medium', 1744761600000, 1744761600000);
```

### 3. Verify

```bash
source /path/to/vidux/scripts/lib/codex-db.sh
codex_verify_tomls
```

Exit 0 = safe to reopen. Exit 1 = fix errors before reopening.

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
4. ACT      Worktree per code change. Same-runtime delegation when the task is clear and bounded.
5. VERIFY   Build passes. Tests pass. Visual check for UI.
6. CHECKPOINT  Append one line to memory.md. Update PLAN.md status. Commit if code changed.
```

### Sandbox modes

Codex agents run inside one of three sandboxes, set per-task or per-session in `config.toml`:

| Mode | Reads | Writes | Use |
|---|---|---|---|
| `read-only` | Yes | No | Investigation or read-heavy work |
| `workspace-write` | Yes | Working tree only | Code edits inside the project workspace |
| `danger-full-access` | Yes | Anywhere | Trusted automations only |

See [Fleet Operations](/fleet/operations) and [Platform Comparison](/fleet/platforms) for the coordination and delegation model layered on top.

### Post-push defer

Same as Claude lanes: after pushing a PR, the lane MUST NOT attempt merge in the same cycle. CI bots and code review tools (Greptile, Seer, Vercel Agent) need time to run. Merge eligibility: CI green + ≥1h since last fix-push + no unresolved P0/P1 reviews.

## Persistence Model

Codex lanes persist differently from Claude lanes:

- **TOML + DB row** live on disk; they survive app quit, reboot, and account-level changes
- **`prompt.md` + `memory.md`** live in the shared lane directory and remain editable without changing the TOML path
- **Agent sessions** live inside the desktop app process; they die when the app quits
- **No session GC needed** — the Codex app manages its own memory internally (no growing JSONL files to prune)

When the Mac app reopens after a quit, it reads the DB, resumes all `ACTIVE` automations, and fires them per their rrule. Each lane reads its own `memory.md` to pick up where it left off.

**No auto-expire.** Codex automations run until manually stopped (`status = 'PAUSED'` or DB delete) or the app is closed permanently.

## Known Bugs

| # | Symptom | Fix |
|---|---|---|
| 14 | New automation invisible after DB insert | Full-quit app (`osascript 'quit'`), not just restart app-server |
| 15 | `pkill app-server` doesn't pick up new rows | Electron frontend caches automation list separately — full quit required |
| 16 | TOML files required for UI visibility | DB-only inserts are runnable but hidden — always write both |
| 18 | Automation fails silently | Missing or malformed timestamp fields — use the repo helpers when possible |
| 22 | TOML parse failure on multi-line prompts | Raw newlines break parsing — escape as `\n` |

Run `codex_verify_tomls` between writing TOMLs and reopening the app to catch all five before they bite.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Automation not firing | App quit or rrule typo | Reopen app; check `rrule` syntax (RFC 5545) |
| Automation invisible in UI | TOML missing or DB-only | Write both TOML + DB row, full-quit + reopen |
| Silent failure on fire | Missing or malformed timestamp fields | Fill both using the repo helper pattern; run verify script |
| Prompt truncated | Raw newline in TOML | Replace `\n` with `\\n` escape; re-verify |
| Lane can't write files | Sandbox = `read-only` | Switch to `workspace-write` for implementation dispatch tasks |
| Can't run from CLI | Expected — CLI doesn't support automations | Use Mac desktop app |

## See Also

- [Platform Comparison](platforms.md) — Claude Code vs Codex overview
- [Claude Code Lifecycle](claude-lifecycle.md) — the Claude equivalent of this page
- [Codex Setup Guide](codex-setup.md) — step-by-step Mac app setup
- [Fleet Operations](/fleet/operations) — research and implementation dispatch plus worktree discipline
- [Recipe Catalog](/fleet/recipes) — reusable automation patterns layered on top
