#!/usr/bin/env bash
# vidux-fleet-quality.sh — automation fleet quality inspector
# Usage:  bash vidux-fleet-quality.sh [--json] [--dir PATH]
#
# Reads automation memory.md files and classifies run quality:
#   quick  = <2 min (healthy — nothing to do)
#   deep   = >15 min (healthy — real work)
#   mid    = 3-8 min (dead zone — rubbing sticks)
#   normal = 2-3 or 8-15 min (acceptable)
#
# Reports per-automation and fleet-wide bimodal quality scores.
set -euo pipefail

JSON_MODE=false
AUTOMATIONS_DIR=""

# --- parse args ------------------------------------------------------------- #
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json) JSON_MODE=true; shift ;;
    --dir)  AUTOMATIONS_DIR="$2"; shift 2 ;;
    *)      echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

# Auto-discover automations directory
if [[ -z "$AUTOMATIONS_DIR" ]]; then
  # Try common locations
  for candidate in \
    "$HOME/.codex/automations" \
    "$(cd "$(dirname "$0")/.." && pwd)/automations" \
    "./automations"; do
    if [[ -d "$candidate" ]]; then
      AUTOMATIONS_DIR="$candidate"
      break
    fi
  done
fi

if [[ -z "$AUTOMATIONS_DIR" ]] || [[ ! -d "$AUTOMATIONS_DIR" ]]; then
  if [[ "$JSON_MODE" = true ]]; then
    echo '{"error": "no automations directory found", "automations": []}'
  else
    echo "No automations directory found. Use --dir PATH to specify."
  fi
  exit 0
fi

# --- classify a run duration ------------------------------------------------ #
classify_minutes() {
  local m="$1"
  if [[ "$m" -lt 2 ]]; then echo "quick"
  elif [[ "$m" -ge 2 ]] && [[ "$m" -lt 3 ]]; then echo "normal"
  elif [[ "$m" -ge 3 ]] && [[ "$m" -le 8 ]]; then echo "mid"
  elif [[ "$m" -gt 8 ]] && [[ "$m" -lt 15 ]]; then echo "normal"
  else echo "deep"
  fi
}

# --- extract run durations from memory.md ----------------------------------- #
# Memory files typically contain timestamps from agent runs.
# We parse git log on the memory file for accurate cycle timing.
extract_durations() {
  local mem_file="$1"
  local repo_dir
  repo_dir="$(cd "$(dirname "$mem_file")" && git rev-parse --show-toplevel 2>/dev/null || echo "")"

  if [[ -n "$repo_dir" ]]; then
    # Use git log timestamps for accuracy
    git -C "$repo_dir" log --format='%at' -- "$mem_file" 2>/dev/null | sort -n | awk '
      NR > 1 {
        delta = $1 - prev
        if (delta > 30 && delta < 7200) print int(delta / 60)
      }
      { prev = $1 }
    '
  else
    # Fallback: parse ISO timestamps from memory content and compute deltas in minutes
    grep -oE '20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}' "$mem_file" 2>/dev/null | sort | uniq | while read -r ts; do
      # Convert ISO timestamp to epoch seconds (macOS date -j)
      epoch=$(date -j -f "%Y-%m-%dT%H:%M" "$ts" "+%s" 2>/dev/null || echo "")
      [[ -n "$epoch" ]] && echo "$epoch"
    done | awk '
      NR > 1 {
        delta = $1 - prev
        if (delta > 30 && delta < 7200) print int(delta / 60)
      }
      { prev = $1 }
    '
  fi
}

# --- main scan -------------------------------------------------------------- #
FLEET_QUICK=0; FLEET_DEEP=0; FLEET_MID=0; FLEET_NORMAL=0; FLEET_TOTAL=0
AUTOMATIONS_JSON="["
FIRST=true

if [[ "$JSON_MODE" = false ]]; then
  echo ""
  echo "  Fleet Quality Inspector"
  echo "  Scanning: $AUTOMATIONS_DIR"
  echo ""
fi

for auto_dir in "$AUTOMATIONS_DIR"/*/; do
  [[ -d "$auto_dir" ]] || continue
  name="$(basename "$auto_dir")"
  mem_file="$auto_dir/memory.md"
  toml_file="$auto_dir/automation.toml"

  # Extract role from toml if available
  role="unknown"
  status="unknown"
  if [[ -f "$toml_file" ]]; then
    role="$(grep -m1 -o 'role = "[^"]*"' "$toml_file" 2>/dev/null | head -1 | grep -o '"[^"]*"' | tr -d '"' || echo "unknown")"
    status="$(grep -m1 -o 'status = "[^"]*"' "$toml_file" 2>/dev/null | head -1 | grep -o '"[^"]*"' | tr -d '"' || echo "unknown")"
  fi

  if [[ ! -f "$mem_file" ]]; then
    if [[ "$JSON_MODE" = false ]]; then
      echo "  $name ($role) — no memory.md"
    fi
    [[ "$FIRST" = true ]] && FIRST=false || AUTOMATIONS_JSON="$AUTOMATIONS_JSON,"
    AUTOMATIONS_JSON="$AUTOMATIONS_JSON{\"name\":\"$name\",\"role\":\"$role\",\"status\":\"$status\",\"has_memory\":false,\"runs\":0}"
    continue
  fi

  # Get durations
  durations="$(extract_durations "$mem_file" || true)"
  if [[ -z "$durations" ]]; then
    if [[ "$JSON_MODE" = false ]]; then
      echo "  $name ($role) — no measurable runs"
    fi
    [[ "$FIRST" = true ]] && FIRST=false || AUTOMATIONS_JSON="$AUTOMATIONS_JSON,"
    AUTOMATIONS_JSON="$AUTOMATIONS_JSON{\"name\":\"$name\",\"role\":\"$role\",\"status\":\"$status\",\"has_memory\":true,\"runs\":0}"
    continue
  fi

  # Classify each run
  quick=0; deep=0; mid=0; normal=0; total=0
  while IFS= read -r m; do
    [[ -z "$m" ]] && continue
    total=$((total + 1))
    FLEET_TOTAL=$((FLEET_TOTAL + 1))
    case "$(classify_minutes "$m")" in
      quick)  quick=$((quick + 1)); FLEET_QUICK=$((FLEET_QUICK + 1)) ;;
      deep)   deep=$((deep + 1)); FLEET_DEEP=$((FLEET_DEEP + 1)) ;;
      mid)    mid=$((mid + 1)); FLEET_MID=$((FLEET_MID + 1)) ;;
      normal) normal=$((normal + 1)); FLEET_NORMAL=$((FLEET_NORMAL + 1)) ;;
    esac
  done <<< "$durations"

  # Quality verdict
  verdict="ok"
  mid_pct=0
  [[ "$total" -gt 0 ]] && mid_pct=$((mid * 100 / total))
  if [[ "$mid_pct" -gt 30 ]]; then
    verdict="stuck-in-middle"
  elif [[ "$mid_pct" -gt 0 ]]; then
    verdict="mostly-bimodal"
  else
    verdict="bimodal"
  fi

  if [[ "$JSON_MODE" = false ]]; then
    printf "  %-30s %s  runs: %d quick, %d deep, %d mid, %d normal → %s\n" \
      "$name ($role)" "$status" "$quick" "$deep" "$mid" "$normal" "$verdict"
  fi

  [[ "$FIRST" = true ]] && FIRST=false || AUTOMATIONS_JSON="$AUTOMATIONS_JSON,"
  AUTOMATIONS_JSON="$AUTOMATIONS_JSON{\"name\":\"$name\",\"role\":\"$role\",\"status\":\"$status\",\"has_memory\":true,\"runs\":$total,\"quick\":$quick,\"deep\":$deep,\"mid\":$mid,\"normal\":$normal,\"mid_pct\":$mid_pct,\"verdict\":\"$verdict\"}"
done

AUTOMATIONS_JSON="$AUTOMATIONS_JSON]"

# --- fleet summary ---------------------------------------------------------- #
FLEET_MID_PCT=0
[[ "$FLEET_TOTAL" -gt 0 ]] && FLEET_MID_PCT=$((FLEET_MID * 100 / FLEET_TOTAL))
FLEET_VERDICT="ok"
if [[ "$FLEET_MID_PCT" -gt 30 ]]; then
  FLEET_VERDICT="stuck-in-middle"
elif [[ "$FLEET_MID_PCT" -gt 0 ]]; then
  FLEET_VERDICT="mostly-bimodal"
else
  FLEET_VERDICT="bimodal"
fi

if [[ "$JSON_MODE" = true ]]; then
  cat <<ENDJSON
{
  "dir": "$AUTOMATIONS_DIR",
  "total_runs": $FLEET_TOTAL,
  "quick": $FLEET_QUICK,
  "deep": $FLEET_DEEP,
  "mid": $FLEET_MID,
  "normal": $FLEET_NORMAL,
  "mid_pct": $FLEET_MID_PCT,
  "verdict": "$FLEET_VERDICT",
  "automations": $AUTOMATIONS_JSON
}
ENDJSON
else
  echo ""
  echo "  Fleet: $FLEET_TOTAL runs total"
  echo "    Quick (<2m):  $FLEET_QUICK"
  echo "    Deep (>15m):  $FLEET_DEEP"
  echo "    Mid (3-8m):   $FLEET_MID ($FLEET_MID_PCT%)"
  echo "    Normal:       $FLEET_NORMAL"
  echo "    Verdict:      $FLEET_VERDICT"
  echo ""
fi
