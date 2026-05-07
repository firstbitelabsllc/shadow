#!/usr/bin/env bash
# acquire-cycle-lock.sh — single-instance lock guard for launchd cron wrappers.
#
# Two parallel cron cycles racing on the same shared state (PLAN.md mutations,
# `.external-state.json` sidecars, Linear MCP intake) silently produce
# duplicate work and clobber each other. This helper provides an atomic claim
# step that any wrapper can call before invoking Claude or any mutator.
#
# The lock format is `PID|ISO|EPOCH\n`. A lock is treated as "fresh" while
# the recorded PID is alive AND its age is below `--max-age-seconds`
# (default 1500 = 25 min, longer than the longest healthy linear-health-watch
# cycle observed). Stale locks (dead PID OR age >= max) are swept.
#
# Usage:
#   acquire-cycle-lock.sh --acquire --lock-file <path> [--max-age-seconds N]
#       exit 0 → lock claimed, wrapper owns it
#       exit 1 → another fresh process holds it (LOCKED token on stderr)
#       exit 2 → bad arguments / IO error
#
#   acquire-cycle-lock.sh --release --lock-file <path>
#       exit 0 → released (or absent — release is idempotent)
#
# Caller pattern:
#   LOCK_FILE="$AUTOMATION_DIR/locks/cycle.lock"
#   if ! acquire-cycle-lock.sh --acquire --lock-file "$LOCK_FILE"; then
#     log "[LOCKED] another cycle in flight; exiting"
#     exit 0
#   fi
#   trap 'acquire-cycle-lock.sh --release --lock-file "$LOCK_FILE" || true' EXIT

set -euo pipefail

MODE=""
LOCK_FILE=""
MAX_AGE_SECONDS=1500

while [[ $# -gt 0 ]]; do
  case "$1" in
    --acquire) MODE=acquire; shift ;;
    --release) MODE=release; shift ;;
    --lock-file) LOCK_FILE="${2:-}"; shift 2 ;;
    --max-age-seconds) MAX_AGE_SECONDS="${2:-1500}"; shift 2 ;;
    -h|--help)
      sed -n '2,/^set -euo/p' "$0" | sed -e '$d' -e 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "ERR: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$MODE" ]]; then
  echo "ERR: must pass --acquire or --release" >&2
  exit 2
fi

if [[ -z "$LOCK_FILE" ]]; then
  echo "ERR: --lock-file is required" >&2
  exit 2
fi

case "$MAX_AGE_SECONDS" in
  ''|*[!0-9]*)
    echo "ERR: --max-age-seconds must be a positive integer" >&2
    exit 2
    ;;
esac

LOCK_DIR=$(dirname "$LOCK_FILE")
mkdir -p "$LOCK_DIR" || { echo "ERR: cannot mkdir $LOCK_DIR" >&2; exit 2; }

now_epoch() { date +%s; }
iso_now()   { date -u +%FT%TZ; }

pid_alive() {
  local pid="${1:-}"
  [[ -n "$pid" && "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

case "$MODE" in
  acquire)
    if [[ -e "$LOCK_FILE" ]]; then
      held_line=$(head -n 1 "$LOCK_FILE" 2>/dev/null || true)
      held_pid=""
      held_iso=""
      held_epoch=""
      if [[ -n "$held_line" ]]; then
        IFS='|' read -r held_pid held_iso held_epoch <<<"$held_line" || true
      fi

      now=$(now_epoch)
      age=0
      if [[ "$held_epoch" =~ ^[0-9]+$ ]]; then
        age=$(( now - held_epoch ))
      else
        age=$MAX_AGE_SECONDS
      fi

      if pid_alive "$held_pid" && (( age < MAX_AGE_SECONDS )); then
        echo "LOCKED pid=$held_pid iso=${held_iso:-?} age=${age}s file=$LOCK_FILE" >&2
        exit 1
      fi

      echo "STALE-SWEEP held_pid=${held_pid:-?} age=${age}s file=$LOCK_FILE" >&2
      rm -f "$LOCK_FILE"
    fi

    tmp=$(mktemp "${LOCK_FILE}.tmp.XXXXXX") || { echo "ERR: mktemp failed" >&2; exit 2; }
    printf '%s|%s|%s\n' "$$" "$(iso_now)" "$(now_epoch)" >"$tmp"

    # `mv -n` is non-clobbering: a second concurrent acquirer that won the
    # race after our stale-sweep would have written the lock first, and our
    # mv would be a no-op. Detect that by re-reading the lock owner.
    mv "$tmp" "$LOCK_FILE" 2>/dev/null || { rm -f "$tmp"; }
    if [[ ! -e "$LOCK_FILE" ]]; then
      echo "ERR: lock file vanished after claim" >&2
      exit 2
    fi
    owner_pid=$(head -n 1 "$LOCK_FILE" 2>/dev/null | awk -F'|' '{print $1}')
    if [[ "$owner_pid" != "$$" ]]; then
      echo "RACE-LOST owner_pid=$owner_pid self=$$ file=$LOCK_FILE" >&2
      exit 1
    fi
    echo "ACQUIRED pid=$$ file=$LOCK_FILE" >&2
    exit 0
    ;;

  release)
    if [[ ! -e "$LOCK_FILE" ]]; then
      echo "RELEASE-NOOP file=$LOCK_FILE" >&2
      exit 0
    fi
    rm -f "$LOCK_FILE"
    echo "RELEASED file=$LOCK_FILE" >&2
    exit 0
    ;;
esac
