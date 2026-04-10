#!/usr/bin/env bash
# vidux-fleet-rebuild.sh — Kill Codex processes, clean the automation DB, apply dispatch-mode fleet.
# Run manually: bash scripts/vidux-fleet-rebuild.sh
# Requires: sqlite3, pkill
set -euo pipefail

DB="$HOME/.codex/sqlite/codex-dev.db"
[[ ! -f "$DB" ]] && { echo "Error: Codex DB not found at $DB"; exit 1; }

echo "=== Vidux Fleet Rebuild ==="
echo ""

# --- Step 1: Kill Codex processes so they stop racing the DB ---
echo "Step 1: Stopping Codex processes..."
pkill -f "codex app-server" 2>/dev/null && echo "  Killed codex app-server(s)" || echo "  No codex app-server running"
pkill -f "Codex Helper" 2>/dev/null && echo "  Killed Codex Helper(s)" || echo "  No Codex Helper running"
sleep 2
echo ""

# --- Step 2: Show current state ---
echo "Step 2: Current fleet (BEFORE):"
sqlite3 "$DB" "SELECT id, status, length(prompt) as chars FROM automations ORDER BY status, id;"
echo ""

# --- Step 3: Delete old automations ---
echo "Step 3: Deleting old automations..."
OLD_IDS=(
  codex-automation-orchestrator
  dji-regrade-loop
  resplit-hourly-mayor
  resplit-ios-ux-lab
  resplit-launch-loop
  resplit-oversight
  resplit-super-team-hourly
  resplit-vidux
  strongyes-content
  strongyes-flow-radar
  strongyes-release-train
  strongyes-revenue-radar
  strongyes-ux-radar
  vidux-endurance
  vidux-v230-planner
)
for id in "${OLD_IDS[@]}"; do
  sqlite3 "$DB" "DELETE FROM automations WHERE id='$id';"
done
REMAINING=$(sqlite3 "$DB" "SELECT COUNT(*) FROM automations;")
echo "  Deleted ${#OLD_IDS[@]} old IDs. $REMAINING automations remain."
echo ""

# --- Step 4: Update cadences to 30-min spread ---
# The live scheduler stores epoch timestamps in milliseconds, not seconds.
echo "Step 4: Setting 30-min cadences..."
sqlite3 "$DB" <<'SQL'
UPDATE automations SET rrule='FREQ=HOURLY;INTERVAL=1;BYMINUTE=0,30',  updated_at=CAST(strftime('%s','now') AS INTEGER) * 1000 WHERE id='resplit-web';
UPDATE automations SET rrule='FREQ=HOURLY;INTERVAL=1;BYMINUTE=3,33',  updated_at=CAST(strftime('%s','now') AS INTEGER) * 1000 WHERE id='resplit-asc';
UPDATE automations SET rrule='FREQ=HOURLY;INTERVAL=1;BYMINUTE=6,36',  updated_at=CAST(strftime('%s','now') AS INTEGER) * 1000 WHERE id='resplit-currency';
UPDATE automations SET rrule='FREQ=HOURLY;INTERVAL=1;BYMINUTE=9,39',  updated_at=CAST(strftime('%s','now') AS INTEGER) * 1000 WHERE id='resplit-android';
UPDATE automations SET rrule='FREQ=HOURLY;INTERVAL=1;BYMINUTE=12,42', updated_at=CAST(strftime('%s','now') AS INTEGER) * 1000 WHERE id='strongyes-ux';
UPDATE automations SET rrule='FREQ=HOURLY;INTERVAL=1;BYMINUTE=15,45', updated_at=CAST(strftime('%s','now') AS INTEGER) * 1000 WHERE id='strongyes-product';
UPDATE automations SET rrule='FREQ=HOURLY;INTERVAL=1;BYMINUTE=18,48', updated_at=CAST(strftime('%s','now') AS INTEGER) * 1000 WHERE id='strongyes-backend';
UPDATE automations SET rrule='FREQ=HOURLY;INTERVAL=1;BYMINUTE=21,51', updated_at=CAST(strftime('%s','now') AS INTEGER) * 1000 WHERE id='strongyes-content-scraper';
UPDATE automations SET rrule='FREQ=HOURLY;INTERVAL=1;BYMINUTE=24,54', updated_at=CAST(strftime('%s','now') AS INTEGER) * 1000 WHERE id='strongyes-email';
UPDATE automations SET rrule='FREQ=HOURLY;INTERVAL=1;BYMINUTE=27,57', updated_at=CAST(strftime('%s','now') AS INTEGER) * 1000 WHERE id='strongyes-problem-builder';
UPDATE automations SET rrule='FREQ=HOURLY;INTERVAL=1;BYMINUTE=0',     updated_at=CAST(strftime('%s','now') AS INTEGER) * 1000 WHERE id='vidux-meta';
SQL
echo "  Done."
echo ""

# --- Step 5: Ensure all remaining are ACTIVE with xhigh reasoning ---
echo "Step 5: Activating all + xhigh reasoning..."
sqlite3 "$DB" "UPDATE automations SET status='ACTIVE', reasoning_effort='xhigh', model='gpt-5.4', updated_at=CAST(strftime('%s','now') AS INTEGER) * 1000 WHERE status != 'ACTIVE' OR reasoning_effort != 'xhigh';"
echo "  Done."
echo ""

# --- Step 6: Verify ---
echo "Step 6: Final fleet (AFTER):"
sqlite3 "$DB" "SELECT id, status, rrule, length(prompt) as chars FROM automations ORDER BY id;"
echo ""
FINAL=$(sqlite3 "$DB" "SELECT COUNT(*) FROM automations WHERE status='ACTIVE';")
echo "=== Fleet rebuild complete: $FINAL active automations ==="
echo ""
echo "IMPORTANT: Do NOT reopen Codex Desktop App until you've verified the fleet looks correct."
echo "The app may re-sync from cloud and revert these changes."
echo "If that happens, consider disabling cloud sync in Codex settings before running this again."
