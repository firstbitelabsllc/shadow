# Codex Setup Guide

Step-by-step guide to creating a native Codex automation on Mac. Covers the TOML + DB + app-restart sequence for repo-bound `Local` or `Worktree` lanes.

The automation guide treats `Chat` as the default for Codex-created automations. Use this setup flow only when the lane truly needs native project-folder execution.

> **⚠️ The Codex CLI cannot run automations.**
> The `codex` CLI can run one-shot tasks, but recurring jobs require the **Codex Mac desktop app**. If you're on Linux, a remote server, or CI — this workflow will not work. Use Claude Code `CronCreate` instead (see [claude-lifecycle.md](claude-lifecycle.md)).

## Prerequisites

- Codex Mac desktop app installed and signed in
- `~/.codex/config.toml` configured with `model`, `sandbox_mode`, and trusted project paths
- `sqlite3` CLI (preinstalled on macOS)
- Local vidux checkout so you can `source scripts/lib/codex-db.sh` and use the shipped helpers (`codex_verify_tomls`, `codex_sync_tomls`, `codex_safe_restart`)

Verify your environment:

```bash
ls ~/.codex/sqlite/codex-dev.db         # runtime DB must exist
ls ~/.codex/automations/                # lane directory root
grep -E "^(model|sandbox_mode)" ~/.codex/config.toml
```

## The Five-Step Setup Flow

Every new automation follows this exact sequence. Skipping steps causes the bugs listed in [codex-lifecycle.md](codex-lifecycle.md#known-bugs).

```
1. Write automation.toml      → disk (UI visibility source)
2. Insert DB row              → sqlite (runtime source)
3. Write prompt.md + memory.md → disk (shared lane state)
4. Run codex_verify_tomls     → lightweight preflight before reopen
5. Full-quit + reopen the app → clears Electron cache (Bug #14/#15)
```

## Step 1 — Write `automation.toml`

Pick a unique `id` (UUID or a slugified name) and create the lane directory:

```bash
LANE_ID="project-coordinator"   # or a UUID
mkdir -p "$HOME/.codex/automations/$LANE_ID"
```

Write `automation.toml`:

```toml
version = 1
id = "project-coordinator"
kind = "cron"
name = "project coordinator"
prompt = "Read {lane-dir}/project-coordinator/prompt.md FIRST. Execute one vidux cycle: READ → ASSESS → ACT → VERIFY → CHECKPOINT.\nHonor all constraints in the prompt file.\nAppend one line to memory.md at the end."
status = "ACTIVE"
rrule = "FREQ=MINUTELY;INTERVAL=30"
model = "gpt-5.4"
reasoning_effort = "medium"
execution_environment = "worktree"
cwds = ["/path/to/repo"]
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
- `created_at` / `updated_at` — **required**. Missing either causes silent failure (Bug #18). Use a **millisecond** unix epoch integer. If you have already sourced `scripts/lib/codex-db.sh`, `codex_db_epoch_ms` prints the right format.
- `execution_environment` — `"worktree"` for recurring vidux lanes. Sandbox access still comes from `sandbox_mode` in `~/.codex/config.toml`.

## Step 2 — Insert the DB row

The TOML is the UI source; the DB is the runtime. Both must exist.

```bash
NOW=$(python3 -c 'import time; print(int(time.time() * 1000))')
PROMPT_ESCAPED=$(grep '^prompt = ' "$HOME/.codex/automations/$LANE_ID/automation.toml" | sed 's/^prompt = "\(.*\)"$/\1/')

sqlite3 "$HOME/.codex/sqlite/codex-dev.db" <<EOF
INSERT INTO automations (
  id, name, prompt, status, rrule, cwds,
  model, reasoning_effort, created_at, updated_at
) VALUES (
  '$LANE_ID',
  'project coordinator',
  '$PROMPT_ESCAPED',
  'ACTIVE',
  'FREQ=MINUTELY;INTERVAL=30',
  '["/path/to/repo"]',
  'gpt-5.4',
  'medium',
  $NOW,
  $NOW
);
EOF
```

**Confirm the row landed:**

```bash
sqlite3 "$HOME/.codex/sqlite/codex-dev.db" \
  "SELECT id, name, status, rrule FROM automations WHERE id='$LANE_ID';"
```

If the row is missing, the automation won't fire. If the TOML is missing, the UI won't show it. **Both are required** (Bug #16).

## Step 3 — Write lane state files

The TOML holds the schedule. The lane's actual instructions and memory live in separate files that the prompt points at:

```bash
# Pick one shared lane-state root for your fleet and keep prompt + memory
# together there. This example uses ~/.vidux/lanes/, but ~/.claude-automations/,
# ~/.codex-automations/, or a project-scoped directory also work.
LANE_DIR="$HOME/.vidux/lanes/$LANE_ID"
mkdir -p "$LANE_DIR"

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

Run the verifier **before** reopening the app. It is the repo's lightweight preflight: it confirms that active DB rows have TOML files with prompt lines before reopen.

```bash
source scripts/lib/codex-db.sh
codex_verify_tomls
```

Expected output on success:

```
All 1/1 TOMLs verified — single-line prompts, files exist.
```

If it fails, fix the reported issue and re-run. **Do not reopen the app with broken TOMLs** — the desktop app may silently skip or crash on them.

If you want the repo's full safe path instead of the manual Step 5 flow, run `codex_safe_restart` after sourcing `scripts/lib/codex-db.sh`. That helper quits the app, regenerates TOMLs from DB rows via `codex_sync_tomls`, and reopens Codex.

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
- [ ] `sqlite3 ~/.codex/sqlite/codex-dev.db "SELECT id FROM automations WHERE id='$LANE_ID';"` — DB row exists
- [ ] `source scripts/lib/codex-db.sh && codex_verify_tomls` — exits 0
- [ ] Codex app shows the lane in the Automations UI
- [ ] After the first fire, `tail -1 $LANE_DIR/memory.md` shows a cycle checkpoint

If any check fails, re-read [codex-lifecycle.md § Known Bugs](codex-lifecycle.md#known-bugs).

## Updating an Existing Automation

To change the prompt, schedule, or model of a live lane:

```bash
# 1. Edit the TOML
$EDITOR "$HOME/.codex/automations/$LANE_ID/automation.toml"

# 2. Update the DB row (both sources must match)
NOW=$(python3 -c 'import time; print(int(time.time() * 1000))')
sqlite3 "$HOME/.codex/sqlite/codex-dev.db" \
  "UPDATE automations SET prompt='{new prompt}', updated_at=$NOW WHERE id='$LANE_ID';"

# 3. Verify
source scripts/lib/codex-db.sh
codex_verify_tomls

# 4. Full-quit + reopen (the app caches the prompt at startup)
osascript -e 'tell application "Codex" to quit' && sleep 3 && open -a "Codex"
```

Editing the TOML without updating the DB (or vice versa) leaves the two sources out of sync — the UI shows one thing, the runtime fires another.

## Stopping / Deleting an Automation

**Pause (keep on disk):**

```bash
sqlite3 "$HOME/.codex/sqlite/codex-dev.db" \
  "UPDATE automations SET status='PAUSED' WHERE id='$LANE_ID';"
osascript -e 'tell application "Codex" to quit' && sleep 3 && open -a "Codex"
```

**Full delete:**

```bash
sqlite3 "$HOME/.codex/sqlite/codex-dev.db" \
  "DELETE FROM automations WHERE id='$LANE_ID';"
rm -rf "$HOME/.codex/automations/$LANE_ID"
# Lane state (prompt.md + memory.md) lives in the shared lane directory — keep
# it as a record unless the lane is truly retired.
osascript -e 'tell application "Codex" to quit' && sleep 3 && open -a "Codex"
```

## See Also

- [Codex Lifecycle](codex-lifecycle.md) — what happens each fire
- [Platform Comparison](platforms.md) — when to pick Codex vs Claude Code
- [Prompt Template](../reference/prompt-template.md) — the 8-block prompt structure
- [Fleet Operations](/fleet/operations) — research and implementation dispatch plus worktree discipline
- [Recipe Catalog](/fleet/recipes) — reusable automation patterns layered on top
