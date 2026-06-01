#!/usr/bin/env bash
# vidux-loop.sh — stateless cycle script
# Usage:  bash vidux-loop.sh <plan-path>              # READ + ASSESS -> JSON
#         bash vidux-loop.sh <plan-path> --checkpoint  # Mark current task done
#
# Supports both v1 checkbox format and v2 FSM states:
#   v1: - [ ] pending task    - [x] completed task
#   v2: - [pending], - [in_progress], - [completed], - [blocked]
# v2 takes priority in detection; v1 checkpoint output stays as - [x].
set -euo pipefail

PLAN="${1:-}"; MODE="${2:-read}"

# --- read config defaults (if vidux.config.json exists nearby) ------------ #
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG="$SCRIPT_DIR/../vidux.config.json"
ARCHIVE_THRESHOLD=30; CONTEXT_WARNING_LINES=200
if [ -f "$CONFIG" ]; then
  ARCHIVE_THRESHOLD=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('defaults',{}).get('archive_threshold',30))" "$CONFIG" 2>/dev/null) || true
  if [ -z "$ARCHIVE_THRESHOLD" ]; then echo "WARNING: Could not parse vidux.config.json. Using defaults." >&2; ARCHIVE_THRESHOLD=30; fi
  CONTEXT_WARNING_LINES=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('defaults',{}).get('context_warning_lines',200))" "$CONFIG" 2>/dev/null || echo 200)
fi

# --- ledger integration (optional) ----------------------------------------- #
_LEDGER_LIB="$SCRIPT_DIR/lib/ledger-emit.sh"
if [ -f "$_LEDGER_LIB" ]; then
  # shellcheck source=./scripts/lib/ledger-emit.sh disable=SC1091
  source "$_LEDGER_LIB" 2>/dev/null || true
fi

die()  { echo "{\"error\": \"$1\"}" >&2; exit 1; }
json() { printf '%s\n' "$1"; }
json_escape() {
  # Bash-native JSON escape — handles all common chars including backticks and $.
  # No subprocess spawn (python3 per-call adds ~80ms x N calls = seconds of overhead).
  local s="$1"
  s="${s//\\/\\\\}"    # backslash (must be first)
  s="${s//\"/\\\"}"    # double quote
  s="${s//$'\t'/\\t}"  # tab
  s="${s//$'\n'/\\n}"  # newline
  s="${s//$'\r'/\\r}"  # carriage return
  printf '%s' "$s"
}
# Platform-aware sed -i
sedi() { if [[ "$(uname)" == "Darwin" ]]; then sed -i '' "$@"; else sed -i "$@"; fi; }

# Contradiction detection: stop words (inline, no external file)
CD_STOP="the a an is are was were be been being have has had do does did
will would shall should may might can could must need to of in for on at
by with from as into through during before after above below between about
against this that these those it its they them their we our you your not
no nor and but or if then else when where which what who whom how all each
every both few more most other some such any only own same than too very
just because so task removed reason added chose over unless evidence changes
date limited per day action plan do"

# Extract significant keywords from a string: lowercase, dedup, skip stops
_cd_keywords() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -cs '[:alnum:]-' '\n' \
    | sort -u | while IFS= read -r w; do
      [ ${#w} -lt 3 ] && continue
      case " $CD_STOP " in *" $w "*) continue ;; esac
      printf '%s\n' "$w"
    done
}

# --- guards ---------------------------------------------------------------- #
[ -z "$PLAN" ] && die "usage: vidux-loop.sh <plan-path> [--checkpoint]"
if [ ! -f "$PLAN" ]; then
  json '{"mode":"reduce","error":"no plan found","action":"create_plan","next_action":"none"}'; exit 0
fi
PLAN_DIR="$(cd "$(dirname "$PLAN")" && pwd)"
PROJECT_NAME="$(basename "$PLAN_DIR")"

# --- emit loop start event ------------------------------------------------- #
if type vidux_emit_loop_start &>/dev/null; then
  vidux_emit_loop_start "$PROJECT_NAME" "$PLAN" "" 2>/dev/null || true
fi

# --- Exit Criteria parsing (early — needed by task-counting below) ---------- #
# Count unchecked `- [ ]` lines inside the ## Exit Criteria section.
# If the section exists, exit_criteria_met is true only when all are checked.
# Also compute the line range so task search can exclude exit criteria lines.
EXIT_CRITERIA_MET=true; EXIT_CRITERIA_PENDING=0
EC_LINE_START=0; EC_LINE_END=0
if grep -q '^## Exit Criteria' "$PLAN" 2>/dev/null; then
  EC_LINE_START="$(awk '/^## Exit Criteria/{print NR; exit}' "$PLAN")"
  # End = next ## heading after EC, or EOF+1
  EC_LINE_END="$(awk -v start="$EC_LINE_START" 'NR>start && /^## /{print NR; exit}' "$PLAN")"
  [ -z "$EC_LINE_END" ] && EC_LINE_END="$(( $(wc -l < "$PLAN" | tr -d ' ') + 1 ))"
  EC_BLOCK="$(awk '/^## Exit Criteria/{found=1; next} found && /^## /{found=0} found{print}' "$PLAN")"
  EXIT_CRITERIA_PENDING="$(printf '%s\n' "$EC_BLOCK" | grep -cE '^\- \[ \] ' || true)"
  if [ "$EXIT_CRITERIA_PENDING" -gt 0 ]; then
    EXIT_CRITERIA_MET=false
  fi
fi

# Helper: filter out Exit Criteria line range from grep -n output
_exclude_ec_lines() {
  if [ "$EC_LINE_START" -gt 0 ]; then
    while IFS= read -r line; do
      _ec_lnum="${line%%:*}"
      if [ "$_ec_lnum" -ge "$EC_LINE_START" ] && [ "$_ec_lnum" -lt "$EC_LINE_END" ]; then
        continue
      fi
      printf '%s\n' "$line"
    done
  else
    cat
  fi
}

_first_in_progress_task_line() {
  awk -v ec_start="$EC_LINE_START" -v ec_end="$EC_LINE_END" '
    ec_start > 0 && NR >= ec_start && NR < ec_end { next }
    /^- \[in_progress\] / { print NR ":" $0; exit }
  ' "$PLAN"
}

_first_pending_task_line() {
  awk -v ec_start="$EC_LINE_START" -v ec_end="$EC_LINE_END" '
    ec_start > 0 && NR >= ec_start && NR < ec_end { next }
    /^- (\[ \]|\[pending\]) / { print NR ":" $0; exit }
  ' "$PLAN"
}

_progress_entries_head() {
  local limit="${1:-3}"
  awk -v limit="$limit" '
    /^## Progress/ { found = 1; next }
    found && /^## / { exit }
    found && /^- \[/ {
      print
      count += 1
      if (count >= limit) { exit }
    }
  ' "$PLAN"
}

# --- hot/cold window (read-only context budget awareness) ----------------- #
# HOT = pending + in_progress (v1 and v2) — excludes Exit Criteria lines
HOT_TASKS="$(grep -nE '^\- (\[ \]|\[(pending|in_progress)\]) ' "$PLAN" | _exclude_ec_lines | grep -c '.' || true)"
# COLD = completed (v1 and v2) — excludes Exit Criteria lines
COLD_TASKS="$(grep -nE '^\- (\[x\]|\[completed\]) ' "$PLAN" | _exclude_ec_lines | grep -c '.' || true)"
TOTAL_LINES="$(wc -l < "$PLAN" | tr -d ' ')"
CONTEXT_WARNING=false; CONTEXT_NOTE=""
if [ "$TOTAL_LINES" -gt "$CONTEXT_WARNING_LINES" ] || [ "$COLD_TASKS" -gt "$ARCHIVE_THRESHOLD" ]; then
  CONTEXT_WARNING=true
  # Auto-archive: run checkpoint --archive if threshold exceeded
  _CHECKPOINT_SCRIPT="$SCRIPT_DIR/vidux-checkpoint.sh"
  if [ -x "$_CHECKPOINT_SCRIPT" ] && [ "$COLD_TASKS" -gt "$ARCHIVE_THRESHOLD" ]; then
    _ARCHIVE_OUT=$("$_CHECKPOINT_SCRIPT" "$PLAN" --archive 2>&1 || true)
    # Re-count after archive
    COLD_TASKS="$(grep -nE '^\- (\[x\]|\[completed\]) ' "$PLAN" | _exclude_ec_lines | grep -c '.' || true)"
    TOTAL_LINES="$(wc -l < "$PLAN" | tr -d ' ')"
    HOT_TASKS="$(grep -nE '^\- (\[ \]|\[(pending|in_progress)\]) ' "$PLAN" | _exclude_ec_lines | grep -c '.' || true)"
    CONTEXT_NOTE="Auto-archived completed tasks (was $COLD_TASKS). $_ARCHIVE_OUT"
  else
    CONTEXT_NOTE="PLAN.md has $COLD_TASKS completed tasks ($TOTAL_LINES lines). Consider archiving with vidux-checkpoint.sh --archive"
  fi
fi

# --- Decision Log awareness (READ step) ------------------------------------ #
# Parse ## Decision Log section. Cron agents MUST read entries before executing
# to avoid contradicting intentional deletions, rate limits, or directions.
# Contradiction detection requires LLM judgment — this surfaces the raw entries.
DL_COUNT=0; DL_ENTRIES=""; DL_WARNING=false
if grep -q '^## Decision Log' "$PLAN" 2>/dev/null; then
  DL_BLOCK="$(awk '/^## Decision Log/{found=1; next} found && /^## /{found=0} found{print}' "$PLAN")"
  DL_ENTRIES="$(printf '%s' "$DL_BLOCK" | grep -E '^\- \[(DELETION|RATE-LIMIT|DIRECTION|STUCK)\]' || true)"
  if [ -n "$DL_ENTRIES" ]; then
    DL_COUNT="$(printf '%s\n' "$DL_ENTRIES" | grep -c '.' || true)"
    DL_WARNING=true
  fi
fi

# Initialize contradiction detection fields (populated after task description is extracted)
CONTRADICTION_WARNING=false; CONTRADICTION_MATCHES=""; CONTRADICTS_TAG=""
PROCESS_FIX_DECLARED=""
DRIFT_SUGGESTIONS_JSON='{"schema_version":1,"source":"vidux-drift-log.py","suggestions":[]}'

# --- fleet health (early — needed by all exit paths) ---------------------- #
# Initialize fleet health fields so early-exit JSON always has consistent schema.
AUTO_PAUSE_RECOMMENDED=false; UNPRODUCTIVE_STREAK=0
BIMODAL_SCORE=-1; BIMODAL_GATE="pass"
CIRCUIT_BREAKER="closed"; CIRCUIT_BREAKER_STREAK=0
BLOCKER_DEDUP=false; QUEUE_STARVED=false

# Circuit breaker: if last N Progress entries show no shipping signals, block dispatch.
# Scoped to ## Progress section only — don't match task descriptions elsewhere.
CB_THRESHOLD=3
if [ -f "$CONFIG" ]; then
  CB_THRESHOLD=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('backpressure',{}).get('circuit_breaker_threshold',3))" "$CONFIG" 2>/dev/null || echo 3)
fi
if grep -q '^## Progress' "$PLAN" 2>/dev/null; then
  _recent_progress="$(_progress_entries_head "$CB_THRESHOLD")"
  _shipping_signals=0
  while IFS= read -r line; do
    if echo "$line" | grep -qiE 'shipped|commit|fixed|merged|created|built|added|wrote|pushed|branch:|origin/codex/|cherry-picked|worktree'; then
      _shipping_signals=$((_shipping_signals + 1))
    fi
  done <<< "$_recent_progress"
  # Count how many entries we actually have — don't judge with fewer than threshold
  _cb_entry_count=0
  [ -n "$_recent_progress" ] && _cb_entry_count=$(printf '%s\n' "$_recent_progress" | grep -c '.' || true)
  if [ "$_cb_entry_count" -ge "$CB_THRESHOLD" ] && [ "$_shipping_signals" -eq 0 ]; then
    CIRCUIT_BREAKER="open"
    CIRCUIT_BREAKER_STREAK=$CB_THRESHOLD
  fi
fi

# Auto-pause: if most recent 3 Progress entries are unproductive, recommend pausing.
# Uses head -3 (not tail -3) because Progress entries are newest-first.
if grep -q '^## Progress' "$PLAN" 2>/dev/null; then
  _AP_LAST_3="$(_progress_entries_head 3)"
  if [ -n "$_AP_LAST_3" ]; then
    _AP_UNPRODUCTIVE=0; _AP_TOTAL=0
    while IFS= read -r pline; do
      [ -z "$pline" ] && continue
      _AP_TOTAL=$((_AP_TOTAL + 1))
      # Branch pushes are real shipped work — override unproductive signals
      if printf '%s' "$pline" | grep -qiE 'branch:|pushed to origin|origin/codex/|cherry-picked|worktree.*(commit|merged)'; then
        continue
      fi
      if printf '%s' "$pline" | grep -qiE 'blocked|proof-refresh only|nothing to do|no pending|all blocked|checkpoint_only|escalate|no actionable'; then
        _AP_UNPRODUCTIVE=$((_AP_UNPRODUCTIVE + 1))
      fi
    done <<< "$_AP_LAST_3"
    UNPRODUCTIVE_STREAK=$_AP_UNPRODUCTIVE
    if [ "$_AP_UNPRODUCTIVE" -ge 3 ] && [ "$_AP_TOTAL" -ge 3 ]; then
      AUTO_PAUSE_RECOMMENDED=true
    fi
  fi
fi

# --- read: find first actionable task ------------------------------------- #
# Priority 1: resume an in_progress task (session may have died mid-task)
TASK_LINE="$(_first_in_progress_task_line)"
IS_RESUMING=false
if [ -n "$TASK_LINE" ]; then
  IS_RESUMING=true
fi

# Priority 2: first pending task (v2 FSM or v1 checkbox)
if [ -z "$TASK_LINE" ]; then
  TASK_LINE="$(_first_pending_task_line)"
fi

if [ -z "$TASK_LINE" ]; then
  # Shared fleet health suffix for all early-exit JSON paths
  # Queue starvation: all tasks done, but plan has a Purpose section and no MISSION COMPLETE marker
  if grep -q '^## Purpose' "$PLAN" 2>/dev/null; then
    if ! grep -qi 'MISSION COMPLETE\|mission.complete' "$PLAN" 2>/dev/null; then
      QUEUE_STARVED=true
    fi
  fi
  _FLEET_SUFFIX="\"auto_pause_recommended\": $AUTO_PAUSE_RECOMMENDED, \"unproductive_streak\": $UNPRODUCTIVE_STREAK, \"bimodal_score\": $BIMODAL_SCORE, \"bimodal_gate\": \"$BIMODAL_GATE\", \"circuit_breaker\": \"$CIRCUIT_BREAKER\", \"circuit_breaker_streak\": $CIRCUIT_BREAKER_STREAK, \"blocker_dedup\": $BLOCKER_DEDUP, \"queue_starved\": $QUEUE_STARVED, \"sub_plan\": null"
  # Check if there are blocked tasks left (not "done" — escalate)
  BLOCKED_COUNT="$(grep -nE '^\- \[blocked\] ' "$PLAN" | _exclude_ec_lines | grep -c '.' || true)"
  if [ "$BLOCKED_COUNT" -gt 0 ]; then
    json "{\"mode\":\"reduce\", \"cycle\": 0, \"task\": \"none\", \"type\": \"all_blocked\", \"action\": \"escalate\", \"next_action\": \"none\", \"context\": \"$BLOCKED_COUNT task(s) blocked — escalate blockers to human\", \"hot_tasks\": $HOT_TASKS, \"cold_tasks\": $COLD_TASKS, \"context_warning\": $CONTEXT_WARNING, \"context_note\": \"$(json_escape "$CONTEXT_NOTE")\", \"decision_log_count\": $DL_COUNT, \"decision_log_warning\": $DL_WARNING, \"decision_log_entries\": \"$(json_escape "$DL_ENTRIES")\", \"contradiction_warning\": $CONTRADICTION_WARNING, \"contradiction_matches\": \"$(json_escape "$CONTRADICTION_MATCHES")\", \"contradicts_tag\": \"$(json_escape "$CONTRADICTS_TAG")\", \"process_fix_declared\": \"$(json_escape "$PROCESS_FIX_DECLARED")\", \"exit_criteria_met\": $EXIT_CRITERIA_MET, \"exit_criteria_pending\": $EXIT_CRITERIA_PENDING, $_FLEET_SUFFIX}"
    exit 0
  fi
  # Check if there are ANY tasks at all (any FSM state) — excludes Exit Criteria lines
  HAS_TASKS="$(grep -nE '^\- (\[.\]|\[(pending|in_progress|completed|blocked)\]) ' "$PLAN" | _exclude_ec_lines | grep -c '.' || true)"
  if [ "$HAS_TASKS" -gt 0 ]; then
    # Gate on exit criteria: if criteria exist and aren't all checked, keep working
    if [ "$EXIT_CRITERIA_MET" = false ]; then
      json "{\"mode\":\"reduce\", \"cycle\": 0, \"task\": \"none\", \"type\": \"exit_criteria_pending\", \"action\": \"execute\", \"next_action\": \"dispatch\", \"context\": \"All tasks done but $EXIT_CRITERIA_PENDING exit criteria unmet\", \"hot_tasks\": $HOT_TASKS, \"cold_tasks\": $COLD_TASKS, \"context_warning\": $CONTEXT_WARNING, \"context_note\": \"$(json_escape "$CONTEXT_NOTE")\", \"decision_log_count\": $DL_COUNT, \"decision_log_warning\": $DL_WARNING, \"decision_log_entries\": \"$(json_escape "$DL_ENTRIES")\", \"contradiction_warning\": $CONTRADICTION_WARNING, \"contradiction_matches\": \"$(json_escape "$CONTRADICTION_MATCHES")\", \"contradicts_tag\": \"$(json_escape "$CONTRADICTS_TAG")\", \"process_fix_declared\": \"$(json_escape "$PROCESS_FIX_DECLARED")\", \"exit_criteria_met\": $EXIT_CRITERIA_MET, \"exit_criteria_pending\": $EXIT_CRITERIA_PENDING, $_FLEET_SUFFIX}"
    else
      if [ "$QUEUE_STARVED" = true ]; then
        json "{\"mode\":\"reduce\", \"cycle\": 0, \"task\": \"none\", \"type\": \"done\", \"action\": \"scan_for_work\", \"next_action\": \"find_work\", \"context\": \"Queue empty — run five-point idle scan before exiting\", \"hot_tasks\": $HOT_TASKS, \"cold_tasks\": $COLD_TASKS, \"context_warning\": $CONTEXT_WARNING, \"context_note\": \"$(json_escape "$CONTEXT_NOTE")\", \"decision_log_count\": $DL_COUNT, \"decision_log_warning\": $DL_WARNING, \"decision_log_entries\": \"$(json_escape "$DL_ENTRIES")\", \"contradiction_warning\": $CONTRADICTION_WARNING, \"contradiction_matches\": \"$(json_escape "$CONTRADICTION_MATCHES")\", \"contradicts_tag\": \"$(json_escape "$CONTRADICTS_TAG")\", \"process_fix_declared\": \"$(json_escape "$PROCESS_FIX_DECLARED")\", \"exit_criteria_met\": $EXIT_CRITERIA_MET, \"exit_criteria_pending\": $EXIT_CRITERIA_PENDING, $_FLEET_SUFFIX}"
      else
        json "{\"mode\":\"reduce\", \"cycle\": 0, \"task\": \"none\", \"type\": \"done\", \"action\": \"complete\", \"next_action\": \"none\", \"context\": \"All tasks done\", \"hot_tasks\": $HOT_TASKS, \"cold_tasks\": $COLD_TASKS, \"context_warning\": $CONTEXT_WARNING, \"context_note\": \"$(json_escape "$CONTEXT_NOTE")\", \"decision_log_count\": $DL_COUNT, \"decision_log_warning\": $DL_WARNING, \"decision_log_entries\": \"$(json_escape "$DL_ENTRIES")\", \"contradiction_warning\": $CONTRADICTION_WARNING, \"contradiction_matches\": \"$(json_escape "$CONTRADICTION_MATCHES")\", \"contradicts_tag\": \"$(json_escape "$CONTRADICTS_TAG")\", \"process_fix_declared\": \"$(json_escape "$PROCESS_FIX_DECLARED")\", \"exit_criteria_met\": $EXIT_CRITERIA_MET, \"exit_criteria_pending\": $EXIT_CRITERIA_PENDING, $_FLEET_SUFFIX}"
      fi
    fi
  else
    json "{\"mode\":\"reduce\", \"cycle\": 0, \"task\": \"none\", \"type\": \"empty\", \"action\": \"create_tasks\", \"next_action\": \"none\", \"context\": \"Plan has no tasks\", \"hot_tasks\": $HOT_TASKS, \"cold_tasks\": $COLD_TASKS, \"context_warning\": $CONTEXT_WARNING, \"context_note\": \"$(json_escape "$CONTEXT_NOTE")\", \"decision_log_count\": $DL_COUNT, \"decision_log_warning\": $DL_WARNING, \"decision_log_entries\": \"$(json_escape "$DL_ENTRIES")\", \"contradiction_warning\": $CONTRADICTION_WARNING, \"contradiction_matches\": \"$(json_escape "$CONTRADICTION_MATCHES")\", \"contradicts_tag\": \"$(json_escape "$CONTRADICTS_TAG")\", \"process_fix_declared\": \"$(json_escape "$PROCESS_FIX_DECLARED")\", \"exit_criteria_met\": $EXIT_CRITERIA_MET, \"exit_criteria_pending\": $EXIT_CRITERIA_PENDING, $_FLEET_SUFFIX}"
  fi
  exit 0
fi

LINE_NUM="${TASK_LINE%%:*}"
TASK_REST="${TASK_LINE#*:}"
# Strip the FSM/checkbox prefix: - [ ] , - [pending] , - [in_progress] , etc.
TASK_DESC="$(echo "$TASK_REST" | sed -E 's/^- \[([^]]*)\] //')"
PROCESS_FIX_DECLARED="$({ echo "$TASK_DESC" | grep -oE '\[ProcessFix: ?[a-z_]+\]' || true; } | head -1 | sed -E 's/\[ProcessFix: ?([a-z_]+)\]/\1/' || true)"
DRIFT_SUGGESTIONS_JSON="$(python3 "$SCRIPT_DIR/vidux-drift-log.py" suggest "$PLAN" --task-text "$TASK_DESC" --limit 3 --json 2>/dev/null || printf '%s' "$DRIFT_SUGGESTIONS_JSON")"
[ -z "$DRIFT_SUGGESTIONS_JSON" ] && DRIFT_SUGGESTIONS_JSON='{"schema_version":1,"source":"vidux-drift-log.py","suggestions":[]}'

# --- sub-plan traversal ([spawns:] tag) ----------------------------------- #
# If the current task links to a sub-plan via [spawns: path], count its tasks.
# Single-level only — does not recurse into nested spawns.
SUB_PLAN_JSON="null"
SPAWNS_PATH="$(echo "$TASK_DESC" | grep -oE '\[spawns: [^]]+\]' | sed -E 's/\[spawns: (.+)\]/\1/' || true)"
if [ -n "$SPAWNS_PATH" ]; then
  # Resolve relative to PLAN_DIR
  SUB_PLAN_FILE="$PLAN_DIR/$SPAWNS_PATH"
  if [ -f "$SUB_PLAN_FILE" ]; then
    _SP_PENDING="$(grep -cE '^\- (\[ \]|\[pending\]) ' "$SUB_PLAN_FILE" 2>/dev/null || true)"
    _SP_IN_PROGRESS="$(grep -cE '^\- \[in_progress\] ' "$SUB_PLAN_FILE" 2>/dev/null || true)"
    _SP_COMPLETED="$(grep -cE '^\- (\[x\]|\[completed\]) ' "$SUB_PLAN_FILE" 2>/dev/null || true)"
    _SP_BLOCKED="$(grep -cE '^\- \[blocked\] ' "$SUB_PLAN_FILE" 2>/dev/null || true)"
    SUB_PLAN_JSON="{\"path\": \"$(json_escape "$SPAWNS_PATH")\", \"pending\": $_SP_PENDING, \"in_progress\": $_SP_IN_PROGRESS, \"completed\": $_SP_COMPLETED, \"blocked\": $_SP_BLOCKED}"
  fi
fi

# --- contradiction detection (keyword overlap + explicit tag) -------------- #
# Check for explicit [Contradicts: ...] tag first
CONTRADICTS_TAG="$(echo "$TASK_DESC" | grep -oE '\[Contradicts: [^]]+\]' || true)"
if [ -n "$CONTRADICTS_TAG" ]; then
  CONTRADICTION_WARNING=true
  CONTRADICTION_MATCHES="explicit: $CONTRADICTS_TAG"
fi

# Keyword overlap check against DELETION and DIRECTION entries
if [ "$DL_WARNING" = true ] && [ -n "$TASK_DESC" ]; then
  TASK_KW="$(_cd_keywords "$TASK_DESC")"
  if [ -n "$TASK_KW" ]; then
    while IFS= read -r DL_LINE; do
      [ -z "$DL_LINE" ] && continue
      # Only check DELETION and DIRECTION entries (RATE-LIMIT is quantity-based, not subject-based)
      DL_TAG="$(printf '%s' "$DL_LINE" | grep -oE '\[(DELETION|DIRECTION)\]' || true)"
      [ -z "$DL_TAG" ] && continue

      DL_KW="$(_cd_keywords "$DL_LINE")"
      [ -z "$DL_KW" ] && continue

      # Intersection via comm on sorted lists
      OVERLAP="$(comm -12 <(printf '%s\n' "$TASK_KW" | sort) <(printf '%s\n' "$DL_KW" | sort) 2>/dev/null || true)"
      OVERLAP_COUNT=0
      [ -n "$OVERLAP" ] && OVERLAP_COUNT="$(printf '%s\n' "$OVERLAP" | grep -c '.' || true)"

      if [ "$OVERLAP_COUNT" -ge 2 ]; then
        CONTRADICTION_WARNING=true
        OVERLAP_CSV="$(printf '%s\n' "$OVERLAP" | tr '\n' ',' | sed 's/,$//')"
        MATCH_NOTE="$DL_TAG overlap(${OVERLAP_COUNT}): ${OVERLAP_CSV}"
        CONTRADICTION_MATCHES="${CONTRADICTION_MATCHES:+$CONTRADICTION_MATCHES; }$MATCH_NOTE"
      fi
    done <<< "$DL_ENTRIES"
  fi
fi

# --- assess ---------------------------------------------------------------- #
CYCLE_COUNT="$(grep -c 'Cycle [0-9]' "$PLAN" 2>/dev/null || true)"
NEXT_CYCLE=$((CYCLE_COUNT + 1))

# Task type
TYPE="code"
case "$TASK_DESC" in
  *Write*\.md*|*PLAN*|*DOCTRINE*|*LOOP*|*INGREDIENTS*|*README*|*doc*|*spec*) TYPE="doc" ;;
  *[Gg]ather*|*[Rr]esearch*|*[Ss]urvey*) TYPE="research" ;;
esac

# Evidence check
HAS_EVIDENCE=false
echo "$TASK_DESC" | grep -qi '\[Evidence\|evidence:\|Source:' && HAS_EVIDENCE=true

# Long-horizon handoff contract.
# The prompt template teaches these rules in prose; reduce mode exposes them
# mechanically so schedulers and dashboards can gate handoffs without guessing.
LONG_HORIZON_TASK=false
HANDOFF_REQUIRED=false
METER_CHECKPOINT_REQUIRED=false
STALE_PROOF_GATE=false
STALE_PROOF_DATES_JSON="[]"
if printf '%s' "$TASK_DESC" | grep -qiE 'long-horizon|multi-agent|week-long|weeklong|handoff|resume|stale-proof|meter checkpoint|cron|launchagent|claims bus|worktree|fleet'; then
  LONG_HORIZON_TASK=true
fi
if [ "$IS_RESUMING" = true ] || [ "$LONG_HORIZON_TASK" = true ] || [ "$SUB_PLAN_JSON" != "null" ]; then
  HANDOFF_REQUIRED=true
  METER_CHECKPOINT_REQUIRED=true
fi
_STALE_PROOF_JSON="$(TASK_DESC="$TASK_DESC" python3 - <<'PY' 2>/dev/null || printf '[]'
import json
import os
import re
from datetime import datetime, timezone

today = datetime.now(timezone.utc).date()
stale = []
for raw in sorted(set(re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", os.environ.get("TASK_DESC", "")))):
    try:
        observed = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        continue
    age_days = (today - observed).days
    if age_days > 1:
        stale.append({"date": raw, "age_days": age_days})
print(json.dumps(stale, separators=(",", ":")))
PY
)"
[ -n "$_STALE_PROOF_JSON" ] && STALE_PROOF_DATES_JSON="$_STALE_PROOF_JSON"
if [ "$STALE_PROOF_DATES_JSON" != "[]" ]; then
  STALE_PROOF_GATE=true
  HANDOFF_REQUIRED=true
  METER_CHECKPOINT_REQUIRED=true
fi

# Blocker check: [Depends: X] where X still has incomplete tasks
# Note: tasks with [blocked] FSM state are filtered out of TASK_LINE selection entirely,
# so they never reach here. This check handles [Depends:] annotations on pending/in_progress tasks.
# Fix (v2.3.0): matches against task identifiers only, not full task text.
# Handles [Depends: none], multi-dep lists, and numeric ID partial-match safety.
BLOCKED=false; BLOCKER_NOTE=""
DEP="$(echo "$TASK_DESC" | grep -o '\[Depends: [^]]*\]' || true)"
if [ -n "$DEP" ]; then
  DEP_TARGET="${DEP#\[Depends: }"; DEP_TARGET="${DEP_TARGET%\]}"
  # Short-circuit: "none" is a sentinel, not a dependency (fixes [Depends: none] false-positive)
  if ! echo "$DEP_TARGET" | grep -qi '^none$'; then
    # Extract task identifiers from all non-completed task lines (exclude current task line)
    # Each identifier is "Task N" or "Task N.N" from the start of the task description
    PENDING_IDS="$(grep -nE '^\- (\[ \]|\[(pending|in_progress)\]) ' "$PLAN" \
      | grep -v "^${LINE_NUM}:" \
      | sed -E 's/^[0-9]+:- \[([^]]*)\] //' \
      | grep -oE '^Task [0-9]+(\.[0-9]+)?' || true)"
    # Split DEP_TARGET on comma for multi-dep support (e.g., [Depends: 0.3, 0.4, 0.5])
    IFS=',' read -ra DEP_PARTS <<< "$DEP_TARGET"
    for DEP_PART in "${DEP_PARTS[@]}"; do
      DEP_PART="$(echo "$DEP_PART" | xargs)"  # trim whitespace
      [ -z "$DEP_PART" ] && continue
      # Match against each pending task identifier
      while IFS= read -r TASK_ID; do
        [ -z "$TASK_ID" ] && continue
        # Full form: "Task 0.3" matches identifier "Task 0.3"
        if [[ "$TASK_ID" == "$DEP_PART" ]]; then
          BLOCKED=true; BLOCKER_NOTE="Waiting on: $DEP_PART"; break 2
        fi
        # Short form: "0.3" matches the numeric part of "Task 0.3"
        TASK_NUM="${TASK_ID#Task }"
        if [[ "$TASK_NUM" == "$DEP_PART" ]]; then
          BLOCKED=true; BLOCKER_NOTE="Waiting on: $DEP_PART"; break 2
        fi
      done <<< "$PENDING_IDS"
    done
  fi
fi

# --- blocker dedup detection ------------------------------------------------ #
# If this task is blocked (dep-gated or FSM [blocked]), check whether the same
# blocker keyword appears in the last 3 Progress entries. If the same blocker
# has been reported 3 times already, the loop is wasting cycles. Set
# blocker_dedup=true so the quick check gate can recommend auto-pause.
if grep -q '^## Progress' "$PLAN" 2>/dev/null; then
  _BD_IS_BLOCKED=false
  echo "$TASK_REST" | grep -qE '^\- \[blocked\] ' && _BD_IS_BLOCKED=true
  [ "$BLOCKED" = true ] && _BD_IS_BLOCKED=true

  if [ "$_BD_IS_BLOCKED" = true ]; then
    _BD_KEY="${BLOCKER_NOTE:-$TASK_DESC}"
      _BD_KEY="$(printf '%s' "$_BD_KEY" | cut -c1-40)"
    if [ -n "$_BD_KEY" ]; then
      _BD_LAST_3="$(_progress_entries_head 3)"
      _BD_HITS=0
      while IFS= read -r _bd_line; do
        [ -z "$_bd_line" ] && continue
        if printf '%s' "$_bd_line" | grep -qF "$_BD_KEY"; then
          _BD_HITS=$((_BD_HITS + 1))
        fi
      done <<< "$_BD_LAST_3"
      if [ "$_BD_HITS" -ge 3 ]; then
        BLOCKER_DEDUP=true
        AUTO_PAUSE_RECOMMENDED=true
      fi
    fi
  fi
fi

# Open questions — per-task-specific: only gate on Qn refs mentioned in THIS task's description
# LOOP.md:39 doctrine: "no items blocking the NEXT task specifically"
TASK_OPEN_QS=0; TASK_OPEN_REFS=""
Q_REFS_IN_TASK="$(echo "$TASK_DESC" | grep -oE 'Q[0-9]+' | sort -u || true)"
if [ -n "$Q_REFS_IN_TASK" ]; then
  while IFS= read -r QREF; do
    [ -z "$QREF" ] && continue
    # Question is open if it appears as "- [ ] Qn:" in the plan
    if grep -qE "^\- \[ \] ${QREF}[: ]" "$PLAN" 2>/dev/null; then
      TASK_OPEN_QS=$((TASK_OPEN_QS + 1))
      TASK_OPEN_REFS="${TASK_OPEN_REFS:+$TASK_OPEN_REFS, }$QREF"
    fi
  done <<< "$Q_REFS_IN_TASK"
fi

# Decide action
ACTION="execute"; CONTEXT="Ready to execute"
if [ "$IS_RESUMING" = true ]; then
  ACTION="execute"; CONTEXT="Resuming in_progress task"
elif [ "$BLOCKED" = true ]; then
  ACTION="blocked"; CONTEXT="$(json_escape "$BLOCKER_NOTE")"
elif [ "$TASK_OPEN_QS" -gt 0 ] && [ "$TYPE" = "code" ]; then
  ACTION="refine"; CONTEXT="$TASK_OPEN_QS task-linked open question(s) (${TASK_OPEN_REFS}); resolve before executing"
elif [ "$HAS_EVIDENCE" = false ] && [ "$TYPE" = "code" ]; then
  ACTION="gather_evidence"; CONTEXT="Task lacks evidence; gather before executing"
fi
if [ "$STALE_PROOF_GATE" = true ] && [ "$ACTION" = "execute" ]; then
  ACTION="refresh_proof"; CONTEXT="Stale dated proof detected; refresh proof before dispatch/publish"
fi

# --- stuck-loop detection -------------------------------------------------- #
# Uses Progress section (not git log) — survives commit message wording changes
# and LLM compaction. A task appearing in 3+ Progress entries without [completed] = stuck.
STUCK=false; STUCK_HITS=0; AUTO_BLOCKED=false
TASK_SHORT="$(echo "$TASK_DESC" | cut -c1-40)"
if grep -q '^## Progress' "$PLAN" 2>/dev/null; then
  PROG_BLOCK="$(awk '/^## Progress/{found=1; next} found && /^## /{found=0} found{print}' "$PLAN")"
  STUCK_HITS="$(printf '%s\n' "$PROG_BLOCK" | grep -cF "$TASK_SHORT" 2>/dev/null || true)"
  if [ "$STUCK_HITS" -ge 3 ]; then
    STUCK=true; ACTION="stuck"
    CONTEXT="Task in $STUCK_HITS Progress entries without completing; possible stuck loop"

    # --- mechanical enforcement: auto-block after 3+ cycles on same task --- #
    # Only act on [in_progress] tasks (pending tasks haven't been started yet)
    if [ "$IS_RESUMING" = true ] && [ -n "$LINE_NUM" ]; then
      TODAY="$(date +%Y-%m-%d)"
      # Grab the last progress entry mentioning this task for the reason
      LAST_PROG="$(printf '%s\n' "$PROG_BLOCK" | grep -F "$TASK_SHORT" | tail -1 || true)"
      LAST_PROG_ESCAPED="$(json_escape "${LAST_PROG:-no progress entry found}")"

      # Flip [in_progress] -> [blocked] on the task line
      if sedi -E "${LINE_NUM}s/^- \[in_progress\] /- [blocked] /" "$PLAN" 2>/dev/null; then AUTO_BLOCKED=true; fi

      if [ "$AUTO_BLOCKED" = true ]; then
        # Append to Decision Log (create section if missing)
        DL_ENTRY="- [STUCK] [$TODAY] Task stuck for ${STUCK_HITS}+ cycles. Auto-blocked. Reason: ${LAST_PROG_ESCAPED}"
        if grep -q '^## Decision Log' "$PLAN" 2>/dev/null; then
          sedi "/^## Decision Log/a\\
$DL_ENTRY" "$PLAN"
        else
          # Insert Decision Log section before ## Tasks (or append to end)
          if grep -q '^## Tasks' "$PLAN" 2>/dev/null; then
            sedi "/^## Tasks/i\\
## Decision Log\\
$DL_ENTRY\\
" "$PLAN"
          else
            printf '\n## Decision Log\n%s\n' "$DL_ENTRY" >> "$PLAN"
          fi
        fi
        ACTION="auto_blocked"
        CONTEXT="Task stuck for ${STUCK_HITS}+ cycles. Auto-blocked in PLAN.md. Human must unblock."
      fi
    fi
  fi
fi

# --- recompute hot_tasks after mutations (stuck-loop may have auto-blocked) - #
HOT_TASKS="$(grep -nE '^\- (\[ \]|\[(pending|in_progress)\]) ' "$PLAN" | _exclude_ec_lines | grep -c '.' || true)"

# --- checkpoint mode ------------------------------------------------------- #
if [ "$MODE" = "--checkpoint" ]; then
  TODAY="$(date +%Y-%m-%d)"
  # v1 checkbox → [x]
  sedi "${LINE_NUM}s/^- \[ \] /- [x] /" "$PLAN"
  # v2 FSM → [completed]
  sedi -E "${LINE_NUM}s/^- \[(pending|in_progress)\] /- [completed] /" "$PLAN"
  PROGRESS="- [$TODAY] Cycle $NEXT_CYCLE: Done: $(json_escape "$TASK_DESC"). Next: check plan."
  if grep -q '^## Progress' "$PLAN"; then
    sedi "/^## Progress/a\\
$PROGRESS" "$PLAN"
  fi
  # Emit checkpoint event
  if type vidux_emit_checkpoint &>/dev/null; then
    local_commit=$(git -C "$PLAN_DIR" rev-parse HEAD 2>/dev/null || echo "")
    vidux_emit_checkpoint "$PROJECT_NAME" "$PLAN" "$local_commit" "done" 2>/dev/null || true
  fi
  json "{\"checkpoint\": true, \"cycle\": $NEXT_CYCLE, \"task\": \"$(json_escape "$TASK_DESC")\", \"status\": \"done\"}"
  exit 0
fi

# --- ledger conflict check ------------------------------------------------- #
LEDGER_CONFLICT_COUNT=0
if type ledger_conflict_check &>/dev/null 2>&1; then
  # Source query lib (emit already sourced config)
  _QUERY_LIB="$SCRIPT_DIR/lib/ledger-query.sh"
  # shellcheck source=./scripts/lib/ledger-query.sh disable=SC1090,SC1091
  if [ -f "$_QUERY_LIB" ]; then source "$_QUERY_LIB" 2>/dev/null || true; fi
  if type ledger_conflict_check &>/dev/null 2>&1; then
    _REPO_NAME="$(basename "$(git -C "$PLAN_DIR" rev-parse --show-toplevel 2>/dev/null || echo "$PLAN_DIR")")"
    _CONFLICT_JSON=$(ledger_conflict_check "$_REPO_NAME" "[\"$PLAN\"]" 2 2>/dev/null || echo '[]')
    LEDGER_CONFLICT_COUNT=$(printf '%s' "$_CONFLICT_JSON" | jq 'length' 2>/dev/null || echo 0)
  fi
fi

# --- bimodal enforcement --------------------------------------------------- #
BIMODAL_CRITICAL=70
if [ -f "$CONFIG" ]; then
  BIMODAL_CRITICAL=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('backpressure',{}).get('bimodal_critical_threshold',70))" "$CONFIG" 2>/dev/null || echo 70)
fi
if type ledger_bimodal_distribution &>/dev/null 2>&1; then
  _REPO_NAME="${_REPO_NAME:-$(basename "$(git -C "$PLAN_DIR" rev-parse --show-toplevel 2>/dev/null || echo "$PLAN_DIR")")}"
  _BIMODAL_JSON=$(ledger_bimodal_distribution "$_REPO_NAME" 24 2>/dev/null || echo '{}')
  BIMODAL_SCORE=$(printf '%s' "$_BIMODAL_JSON" | jq '.bimodal_score // -1' 2>/dev/null || echo -1)
  if [ "$BIMODAL_SCORE" != "-1" ] && [ "$BIMODAL_SCORE" -lt "$BIMODAL_CRITICAL" ] 2>/dev/null; then
    BIMODAL_GATE="blocked"
  fi
fi

# --- output ---------------------------------------------------------------- #
# Field semantics: blocked vs auto_blocked
#   blocked     = dependency-gated: task's [Depends: X] references an unresolved task
#   auto_blocked = stuck-loop enforcement: task was in_progress for 3+ cycles, script
#                  flipped it to [blocked] in PLAN.md. Human must unblock.
#   Both are booleans. A task can be auto_blocked=true with blocked=false (stuck, not dep-gated).
NEXT_ACTION="none"
case "$ACTION" in
  execute|gather_evidence|refine)
    if [ "$BIMODAL_GATE" = "blocked" ] || [ "$CIRCUIT_BREAKER" = "open" ]; then
      NEXT_ACTION="none"
    else
      NEXT_ACTION="dispatch"
    fi
    ;;
  refresh_proof)
    NEXT_ACTION="refresh_proof"
    ;;
esac
cat <<ENDJSON
{
  "mode": "reduce",
  "cycle": $NEXT_CYCLE,
  "task": "$(json_escape "$TASK_DESC")",
  "type": "$TYPE",
  "has_evidence": $HAS_EVIDENCE,
  "blocked": $BLOCKED,
  "stuck": $STUCK,
  "auto_blocked": $AUTO_BLOCKED,
  "is_resuming": $IS_RESUMING,
  "task_open_questions": $TASK_OPEN_QS,
  "action": "$ACTION",
  "next_action": "$NEXT_ACTION",
  "context": "$(json_escape "$CONTEXT")",
  "hot_tasks": $HOT_TASKS,
  "cold_tasks": $COLD_TASKS,
  "context_warning": $CONTEXT_WARNING,
  "context_note": "$(json_escape "$CONTEXT_NOTE")",
  "decision_log_count": $DL_COUNT,
  "decision_log_warning": $DL_WARNING,
  "decision_log_entries": "$(json_escape "$DL_ENTRIES")",
  "contradiction_warning": $CONTRADICTION_WARNING,
  "contradiction_matches": "$(json_escape "$CONTRADICTION_MATCHES")",
  "contradicts_tag": "$(json_escape "$CONTRADICTS_TAG")",
  "process_fix_declared": "$(json_escape "$PROCESS_FIX_DECLARED")",
  "drift_suggestions": $DRIFT_SUGGESTIONS_JSON,
  "exit_criteria_met": $EXIT_CRITERIA_MET,
  "exit_criteria_pending": $EXIT_CRITERIA_PENDING,
  "ledger_available": $([ "${LEDGER_AVAILABLE:-false}" = "true" ] && echo true || echo false),
  "ledger_conflicts": ${LEDGER_CONFLICT_COUNT:-0},
  "auto_pause_recommended": $AUTO_PAUSE_RECOMMENDED,
  "unproductive_streak": $UNPRODUCTIVE_STREAK,
  "bimodal_score": $BIMODAL_SCORE,
  "bimodal_gate": "$BIMODAL_GATE",
  "circuit_breaker": "$CIRCUIT_BREAKER",
  "circuit_breaker_streak": $CIRCUIT_BREAKER_STREAK,
  "blocker_dedup": $BLOCKER_DEDUP,
  "queue_starved": $QUEUE_STARVED,
  "sub_plan": $SUB_PLAN_JSON,
  "handoff_contract": {
    "long_horizon": $LONG_HORIZON_TASK,
    "handoff_required": $HANDOFF_REQUIRED,
    "stale_proof_gate": $STALE_PROOF_GATE,
    "stale_proof_dates": $STALE_PROOF_DATES_JSON,
    "meter_checkpoint_required": $METER_CHECKPOINT_REQUIRED,
    "required_fields": ["plan_row_moved", "ledger", "proof", "files_claimed", "handoff_status", "next_agent_resume"]
  },
  "reduce_contract": {
    "read_only": true,
    "max_budget_seconds": 120,
    "forbidden": ["code_changes", "plan_execution", "file_writes"],
    "allowed": ["read_plan", "read_evidence", "assess_state", "fire_dispatch", "route_refresh_proof"]
  }
}
ENDJSON
