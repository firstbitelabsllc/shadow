#!/usr/bin/env bash
# vidux-plan-gc-cron.sh — Sweep every PLAN.md-bearing directory under the known
# vidux roots and run mechanical plan GC on each.
#
# Intended for scheduled execution (launchd / cron). Idempotent: no-ops when
# every plan is under its soft caps. Logs to $HOME/.vidux/gc.log (rotated by
# append, trimmed externally).
#
# Usage: bash scripts/vidux-plan-gc-cron.sh [--dry-run]
#   --dry-run  forward to vidux-plan-gc.py; nothing is archived
set -uo pipefail

DRY=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY="--dry-run" ;;
    *) echo "unknown arg: $arg" >&2; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GC="$SCRIPT_DIR/vidux-plan-gc.py"
LOG_DIR="$HOME/.vidux"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/gc.log"

stamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

# Roots to scan. Both Mac layouts supported: ~/Development/* (personal Mac)
# and ~/REDACTED-EMPLOYER-PATH/Dev/* (Snap work machine). Non-existent roots skip silently.
ROOTS=(
  "$HOME/Development/vidux"
  "$HOME/REDACTED-EMPLOYER-PATH/Dev/vidux"
  "$HOME/Development/ai/vidux"
  "$HOME/REDACTED-EMPLOYER-PATH/Dev/ai/vidux"
)

hard_cap_any=0
swept=0
skipped_roots=0
SEEN_FILE="$(mktemp -t vidux-plan-gc-seen.XXXXXX)"
trap 'rm -f "$SEEN_FILE"' EXIT

{
  echo "=== vidux-plan-gc sweep $(stamp) ${DRY:+[DRY-RUN]} ==="
  for root in "${ROOTS[@]}"; do
    if [ ! -d "$root" ]; then
      skipped_roots=$((skipped_roots + 1))
      continue
    fi
    while IFS= read -r planmd; do
      plan_dir="$(cd "$(dirname "$planmd")" && pwd -P)"
      if grep -qxF "$plan_dir" "$SEEN_FILE" 2>/dev/null; then
        continue
      fi
      printf '%s\n' "$plan_dir" >> "$SEEN_FILE"
      echo "--- $plan_dir ---"
      if python3 "$GC" $DRY "$plan_dir" 2>&1; then
        :
      else
        rc=$?
        if [ "$rc" = "2" ]; then
          hard_cap_any=1
          echo "  [!!] hard-cap exit from vidux-plan-gc.py (rc=2) — plan needs attention"
        else
          echo "  [err] vidux-plan-gc.py rc=$rc"
        fi
      fi
      swept=$((swept + 1))
    done < <(find "$root" -name PLAN.md \
             -not -path '*/.git/*' \
             -not -path '*/archive/*' \
             -not -path '*/node_modules/*' \
             -not -path '*/.venv/*' \
             2>/dev/null)
  done
  echo "=== done $(stamp) swept=$swept roots_missing=$skipped_roots hard_cap_any=$hard_cap_any ==="
  echo
} >> "$LOG" 2>&1

exit $hard_cap_any
