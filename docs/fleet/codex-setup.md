# Codex Setup Guide

Step-by-step guide to creating a Codex automation on Mac. Covers the TOML + DB + app-restart sequence that every new lane must follow.

> **⚠️ The Codex CLI cannot run automations.**
> Recurring jobs require the **Codex Mac desktop app**. If you're on Linux, a remote server, or CI, this workflow will not run there. Use Claude Code `CronCreate` instead (see [claude-lifecycle.md](claude-lifecycle.md)).

## Prerequisites

- Codex Mac desktop app installed and signed in
- `~/.codex/config.toml` configured with `model`, `sandbox_mode`, and trusted project paths
- `sqlite3` CLI (preinstalled on macOS)
- this repo's `scripts/lib/codex-db.sh` helpers for safe DB writes and TOML verification

Verify your environment:

```bash
ls ~/.codex/sqlite/codex-dev.db         # runtime DB must exist
ls ~/.codex/automations/                # lane directory root
grep -E "^(model|sandbox_mode)" ~/.codex/config.toml
```

## The Five-Step Setup Flow

Every new automation follows this exact sequence. Skipping steps causes the bugs listed in [codex-lifecycle.md](codex-lifecycle.md#known-bugs).

```
1. Write `automation.toml`      → disk (UI visibility source)
2. Insert DB row                → sqlite (runtime source)
3. Write `prompt.md` + `memory.md` → disk (lane state)
4. Run `codex_verify_tomls`     → catches missing or malformed TOMLs
5. Full-quit + reopen the app   → clears Electron cache (Bug #14/#15)
```

## Step 1 — Write `automation.toml`

Pick a unique `id` (UUID or a slugified name) and create the lane directory:

```bash
LANE_ID="my-project-coordinator"   # or a UUID
mkdir -p "$HOME/.codex/automations/$LANE_ID"
LANE_DIR="$HOME/.vidux/lanes/$LANE_ID"
mkdir -p "$LANE_DIR"
```

The lane directory can live anywhere you choose. The important invariant from the current repo guides is that `prompt.md` and `memory.md` stay paired under one `<lane-dir>/<lane-id>/`.

Write `automation.toml`:

```toml
version = 1
id = "my-project-coordinator"
kind = "cron"
name = "my project coordinator"
prompt = "Read $HOME/.vidux/lanes/my-project-coordinator/prompt.md FIRST. Execute one vidux cycle: READ → ASSESS → ACT → VERIFY → CHECKPOINT.\nHonor all constraints in the prompt file.\nAppend one line to memory.md at the end."
status = "ACTIVE"
rrule = "FREQ=MINUTELY;INTERVAL=30"
model = "gpt-5.4"
reasoning_effort = "medium"
execution_environment = "sandbox"
cwds = ["/absolute/path/to/project"]
created_at = 1744761600000
updated_at = 1744761600000
```

**Field notes:**

- `id` — must match the directory name and the DB row `id`. All three must agree.
- `prompt` — **single-line only**. Escape newlines as `\n` (Bug #22 — raw newlines break TOML parsing).
- `rrule` — RFC 5545. Common patterns:
  - Every 30 min: `FREQ=MINUTELY;INTERVAL=30`
  - Hourly on the hour: `FREQ=HOURLY;INTERVAL=1;BYMINUTE=0`
  - Daily at 09:00: `FREQ=DAILY;BYHOUR=9;BYMINUTE=0`
- `cwds` — JSON-style array of absolute paths. Codex runs in the first path by default.
- `created_at` / `updated_at` — **required**. The repo helpers generate millisecond-epoch values for the live scheduler format.
- `execution_environment` — `"sandbox"` for most lanes; `"host"` for lanes that need full system access.

## Step 2 — Insert the DB row

The TOML is the UI source; the DB is the runtime. Both must exist.

```bash
source /path/to/vidux/scripts/lib/codex-db.sh
codex_db_stop_app
NOW_MS=$(codex_db_epoch_ms)
PROMPT_ESCAPED=$(grep '^prompt = ' "$HOME/.codex/automations/$LANE_ID/automation.toml" | sed 's/^prompt = "\(.*\)"$/\1/')

sqlite3 "$(codex_db_path)" <<EOF
INSERT INTO automations (
  id, name, prompt, status, rrule, cwds,
  model, reasoning_effort, created_at, updated_at
) VALUES (
  '$LANE_ID',
  'my project coordinator',
  '$PROMPT_ESCAPED',
  'ACTIVE',
  'FREQ=MINUTELY;INTERVAL=30',
  '["/absolute/path/to/project"]',
  'gpt-5.4',
  'medium',
  $NOW_MS,
  $NOW_MS
);
EOF
```

**Confirm the row landed:**

```bash
sqlite3 "$(codex_db_path)" \
  "SELECT id, name, status, rrule FROM automations WHERE id='$LANE_ID';"
```

If the row is missing, the automation won't fire. If the TOML is missing, the UI won't show it. **Both are required** (Bug #16).

## Step 3 — Write lane state files

The TOML holds the schedule. The lane's actual instructions and memory live in separate files that the prompt points at:

```bash
# prompt.md — 8-block structure (Mission / Skills / Read / Gate / Assess / Act / Authority / Checkpoint)
$EDITOR "$LANE_DIR/prompt.md"

# memory.md — seed with the lane's creation entry
cat > "$LANE_DIR/memory.md" <<EOF
# $LANE_ID — memory
- [$(date -u +%Y-%m-%dT%H:%M:%SZ) codex setup] Lane created. First fire scheduled per rrule.
EOF
```

See [prompt-template.md](../reference/prompt-template.md) for the 8-block structure.

## Step 4 — Verify

Run the verifier **before** reopening the app. It catches missing fields, raw newlines, and TOML-vs-DB drift:

```bash
source /path/to/vidux/scripts/lib/codex-db.sh
codex_verify_tomls
```

Expected output on success:

```
All active TOMLs verified — single-line prompts, files exist.
```

If it fails, fix the reported issue and re-run. **Do not reopen the app with broken TOMLs** — the desktop app may silently skip or crash on them.

## Step 5 — Full-quit and reopen the Codex app

This is the step most often skipped. A full quit clears the Electron frontend's in-memory automation cache.

```bash
osascript -e 'tell application "Codex" to quit'
sleep 3
open -a "Codex"
```

**Why a full quit matters:**

- `pkill -f codex-app-server` kills the backend but leaves the Electron frontend running. The UI keeps its cached automation list and your new lane stays invisible (Bug #15).
- `Cmd+Q` from the menu bar works too, but `osascript` is scriptable.
- `sleep 3` gives the app time to flush DB writes and release file locks.
- After reopen, check the Automations panel in the Codex UI — your new lane should appear with a countdown to the next fire.

## Verification Checklist

Before considering the lane "live," confirm all five:

- [ ] `ls ~/.codex/automations/$LANE_ID/automation.toml` — TOML file exists
- [ ] `sqlite3 "$(codex_db_path)" "SELECT id FROM automations WHERE id='$LANE_ID';"` — DB row exists
- [ ] `codex_verify_tomls` — exits 0
- [ ] Codex app shows the lane in the Automations UI
- [ ] After the first fire, `tail -1 $LANE_DIR/memory.md` shows a cycle checkpoint

If any check fails, re-read [codex-lifecycle.md § Known Bugs](codex-lifecycle.md#known-bugs).

## Updating an Existing Automation

To change the prompt, schedule, or model of a live lane:

```bash
source /path/to/vidux/scripts/lib/codex-db.sh

# 1. Edit the TOML
$EDITOR "$HOME/.codex/automations/$LANE_ID/automation.toml"

# 2. Update the DB row (both sources must match)
NOW_MS=$(codex_db_epoch_ms)
sqlite3 "$(codex_db_path)" \
  "UPDATE automations SET prompt='<new prompt>', updated_at=$NOW_MS WHERE id='$LANE_ID';"

# 3. Verify
codex_verify_tomls

# 4. Full-quit + reopen (the app caches the prompt at startup)
osascript -e 'tell application "Codex" to quit' && sleep 3 && open -a "Codex"
```

Editing the TOML without updating the DB (or vice versa) leaves the two sources out of sync — the UI shows one thing, the runtime fires another.

## Stopping / Deleting an Automation

**Pause (keep on disk):**

```bash
source /path/to/vidux/scripts/lib/codex-db.sh
sqlite3 "$(codex_db_path)" \
  "UPDATE automations SET status='PAUSED' WHERE id='$LANE_ID';"
osascript -e 'tell application "Codex" to quit' && sleep 3 && open -a "Codex"
```

**Full delete:**

```bash
source /path/to/vidux/scripts/lib/codex-db.sh
sqlite3 "$(codex_db_path)" \
  "DELETE FROM automations WHERE id='$LANE_ID';"
rm -rf "$HOME/.codex/automations/$LANE_ID"
# Lane state (prompt.md + memory.md) lives in $LANE_DIR — keep it as a record
# unless the lane is truly retired.
osascript -e 'tell application "Codex" to quit' && sleep 3 && open -a "Codex"
```

## See Also

- [Codex Lifecycle](codex-lifecycle.md) — what happens each fire
- [Platform Comparison](platforms.md) — when to pick Codex vs Claude Code
- [Prompt Template](../reference/prompt-template.md) — the 8-block prompt structure
- [Fleet Operations](/fleet/operations) — research and implementation dispatch plus worktree discipline
- [Recipe Catalog](/fleet/recipes) — reusable automation patterns layered on top
