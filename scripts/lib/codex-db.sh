#!/usr/bin/env bash
# codex-db.sh — Safe Codex DB write helpers
#
# The Codex desktop app caches automation state in memory and overwrites
# SQLite on restart/sync. Direct DB writes WILL be reverted unless the
# app is stopped first. This lib provides the kill→write→verify pattern.
#
# Usage:
#   source scripts/lib/codex-db.sh
#   codex_db_path          # prints path to codex-dev.db
#   codex_db_stop_app      # kills Codex processes (required before writes)
#   codex_db_query "SQL"   # runs read-only query
#   codex_db_write "SQL"   # runs write query (asserts app is stopped)
#   codex_db_is_app_running  # returns 0 if running, 1 if stopped
#
# Evidence: fleet rebuild sessions — 3 failed DB writes before discovering
# the race condition. Codex app-server PIDs cache state in memory.

[[ -n "${_VIDUX_CODEX_DB_LOADED:-}" ]] && return 0
_VIDUX_CODEX_DB_LOADED=1

CODEX_DB="${CODEX_DB:-$HOME/.codex/sqlite/codex-dev.db}"

codex_db_path() {
  echo "$CODEX_DB"
}

codex_db_is_app_running() {
  pgrep -f "codex app-server" >/dev/null 2>&1 || pgrep -f "Codex Helper" >/dev/null 2>&1
}

codex_db_stop_app() {
  pkill -f "codex app-server" 2>/dev/null || true
  pkill -f "Codex Helper" 2>/dev/null || true
  sleep 1
  # Verify stopped
  if codex_db_is_app_running; then
    echo "WARNING: Codex processes still running after kill attempt" >&2
    return 1
  fi
  return 0
}

codex_db_query() {
  local sql="$1"
  [[ ! -f "$CODEX_DB" ]] && { echo "Error: Codex DB not found at $CODEX_DB" >&2; return 1; }
  sqlite3 "$CODEX_DB" "$sql"
}

codex_db_write() {
  local sql="$1"
  [[ ! -f "$CODEX_DB" ]] && { echo "Error: Codex DB not found at $CODEX_DB" >&2; return 1; }
  # Safety: refuse to write if app is running
  if codex_db_is_app_running; then
    echo "ERROR: Codex app is running. DB writes will be reverted." >&2
    echo "Run codex_db_stop_app first, or use vidux-fleet-rebuild.sh." >&2
    return 1
  fi
  # Use millisecond epoch for updated_at (Codex scheduler format)
  sqlite3 "$CODEX_DB" "$sql"
}

# Convenience: current epoch in milliseconds (Codex timestamp format)
codex_db_epoch_ms() {
  python3 -c "import time; print(int(time.time() * 1000))" 2>/dev/null || \
    echo "$(date +%s)000"
}
