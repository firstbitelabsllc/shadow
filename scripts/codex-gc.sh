#!/usr/bin/env bash
# codex-gc.sh — Garbage-collect Codex caches (logs, sessions, archived rollouts, stale threads).
# Usage: bash scripts/codex-gc.sh [--dry-run] [--json]
set -euo pipefail

DRY=false; JSON=false
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=true ;;
    --json)    JSON=true ;;
    *)         echo "Usage: codex-gc.sh [--dry-run] [--json]"; exit 1 ;;
  esac
done

# Safety: bail if Codex is running
pgrep -f "codex" > /dev/null && echo "Codex running, skipping" && exit 0

CODEX="$HOME/.codex"
TOTAL=0

bytes_of() { stat -f%z "$1" 2>/dev/null || echo 0; }
human() { numfmt --to=iec --suffix=B "$1" 2>/dev/null || awk "BEGIN{printf \"%.1f MB\", $1/1048576}"; }

emit() { # target rows_or_files bytes
  TOTAL=$((TOTAL + $3))
  if $JSON; then
    printf '{"target":"%s","deleted":%d,"bytes_recovered":%d}\n' "$1" "$2" "$3"
  else
    printf 'codex-gc: %s — deleted %d %s, recovered %s\n' \
      "$1" "$2" "$([ "$1" = "sessions" ] && echo dirs || echo rows/files)" "$(human "$3")"
  fi
}

# --- 1. logs_2.sqlite ---
LOG_DB="$CODEX/logs_2.sqlite"
if [[ -f "$LOG_DB" ]]; then
  before=$(bytes_of "$LOG_DB")
  if $DRY; then
    info=$(sqlite3 "$LOG_DB" "SELECT count(*), coalesce(sum(length(message)),0) FROM logs WHERE ts < strftime('%s','now','-7 days');")
    cnt=${info%%|*}; sz=${info##*|}
    emit "logs_2.sqlite" "$cnt" "$sz"
  else
    cnt=$(sqlite3 "$LOG_DB" "SELECT count(*) FROM logs WHERE ts < strftime('%s','now','-7 days');")
    sqlite3 "$LOG_DB" "DELETE FROM logs WHERE ts < strftime('%s','now','-7 days');"
    sqlite3 "$LOG_DB" "VACUUM;"
    after=$(bytes_of "$LOG_DB")
    emit "logs_2.sqlite" "$cnt" $((before - after))
  fi
fi

# --- 2. archived_sessions (JSONL > 14 days, keep newest 50) ---
ARCH="$CODEX/archived_sessions"
if [[ -d "$ARCH" ]]; then
  # Build list of files older than 14 days, excluding the 50 most recent
  keep50=$(ls -1t "$ARCH"/*.jsonl 2>/dev/null | head -n 50 | sort)
  old_files=$(find "$ARCH" -name '*.jsonl' -mtime +14 -type f 2>/dev/null | sort)
  # Subtract keep50 from old_files
  targets=$(comm -23 <(echo "$old_files") <(echo "$keep50") 2>/dev/null || true)
  fcnt=0; fbytes=0
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    fbytes=$((fbytes + $(bytes_of "$f")))
    fcnt=$((fcnt + 1))
    $DRY || rm -f "$f"
  done <<< "$targets"
  emit "archived_sessions" "$fcnt" "$fbytes"
fi

# --- 3. sessions (dirs > 30 days, never current month) ---
SESS="$CODEX/sessions"
if [[ -d "$SESS" ]]; then
  cur_month=$(date +%Y-%m)
  dcnt=0; dbytes=0
  while IFS= read -r d; do
    [[ -z "$d" ]] && continue
    [[ "$(basename "$d")" == *"$cur_month"* ]] && continue
    sz=$(du -sk "$d" 2>/dev/null | awk '{print $1 * 1024}')
    dbytes=$((dbytes + sz)); dcnt=$((dcnt + 1))
    $DRY || rm -rf "$d"
  done < <(find "$SESS" -mindepth 1 -maxdepth 1 -type d -mtime +30 2>/dev/null)
  emit "sessions" "$dcnt" "$dbytes"
fi

# --- 4. state_5.sqlite ---
STATE_DB="$CODEX/state_5.sqlite"
if [[ -f "$STATE_DB" ]]; then
  before=$(bytes_of "$STATE_DB")
  if $DRY; then
    cnt=$(sqlite3 "$STATE_DB" "SELECT count(*) FROM threads WHERE archived = 1 AND updated_at < datetime('now','-30 days');")
    emit "state_5.sqlite" "$cnt" 0
  else
    cnt=$(sqlite3 "$STATE_DB" "SELECT count(*) FROM threads WHERE archived = 1 AND updated_at < datetime('now','-30 days');")
    sqlite3 "$STATE_DB" "DELETE FROM threads WHERE archived = 1 AND updated_at < datetime('now','-30 days');"
    sqlite3 "$STATE_DB" "VACUUM;"
    after=$(bytes_of "$STATE_DB")
    emit "state_5.sqlite" "$cnt" $((before - after))
  fi
fi

# --- Summary ---
if $JSON; then
  printf '{"target":"total","bytes_recovered":%d}\n' "$TOTAL"
else
  printf 'codex-gc: total recovered — %s\n' "$(human "$TOTAL")"
fi
