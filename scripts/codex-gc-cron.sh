#!/usr/bin/env bash
# codex-gc-cron.sh — launchd-invoked wrapper around codex-gc.sh with
# timestamped logging to $HOME/.vidux/codex-gc.log. Bails silently when
# codex is running (via codex-gc.sh's own safety check).
#
# Usage: bash scripts/codex-gc-cron.sh [--dry-run]
set -uo pipefail

DRY=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY="--dry-run" ;;
    *) echo "unknown arg: $arg" >&2; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GC="$SCRIPT_DIR/codex-gc.sh"
LOG_DIR="$HOME/.vidux"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/codex-gc.log"

stamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

{
  echo "=== codex-gc $(stamp) ${DRY:+[DRY-RUN]} ==="
  bash "$GC" $DRY
  rc=$?
  echo "=== done $(stamp) rc=$rc ==="
  echo
} >> "$LOG" 2>&1
