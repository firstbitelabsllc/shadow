#!/usr/bin/env bash
# vidux-firstbite-verified-alive-runner.sh - review-only verified-alive heartbeat packet.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIDUX_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNNER_SCRIPT="$SCRIPT_DIR/vidux-firstbite-verified-alive-runner.sh"
VERIFY_SCRIPT="${VIDUX_VERIFIED_ALIVE_SCRIPT:-$SCRIPT_DIR/vidux-firstbite-verified-alive.py}"
GOAL_AUDIT_SCRIPT="${VIDUX_LOCAL_OPERATOR_GOAL_AUDIT_SCRIPT:-$SCRIPT_DIR/vidux-local-operator-goal-audit.py}"
LEDGER_DIR="${AGENT_LEDGER_DIR:-$HOME/.agent-ledger}"
RUN_ID="${VIDUX_VERIFIED_ALIVE_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
CADENCE_SECONDS="${VIDUX_VERIFIED_ALIVE_CADENCE_SECONDS:-1800}"
PRINT_JSON=0

usage() {
  cat <<'EOF'
Usage: vidux-firstbite-verified-alive-runner.sh [--json] [--run-id <id>]

Refreshes the FirstBite verified-alive rollup in review-only mode, then writes:
  ~/.agent-ledger/vidux-firstbite-verified-alive-runner/<run-id>/report.json
  ~/.agent-ledger/vidux-firstbite-verified-alive-runner/<run-id>/summary.md

It also writes a LaunchAgent plist template into the packet directory. It does
not install the LaunchAgent, execute local-CI lanes, delete files, write drift
records, dispatch workers, mutate repos, or restart services.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --json) PRINT_JSON=1; shift ;;
    --run-id) RUN_ID="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$RUN_ID" in
  ''|*[!A-Za-z0-9._-]*)
    echo "VIDUX_VERIFIED_ALIVE_RUN_ID/--run-id must use only letters, numbers, dot, underscore, or hyphen" >&2
    exit 2
    ;;
esac

case "$CADENCE_SECONDS" in
  ''|*[!0-9]*) echo "VIDUX_VERIFIED_ALIVE_CADENCE_SECONDS must be a positive integer" >&2; exit 2 ;;
  0) echo "VIDUX_VERIFIED_ALIVE_CADENCE_SECONDS must be positive" >&2; exit 2 ;;
esac

RUN_DIR="$LEDGER_DIR/vidux-firstbite-verified-alive-runner/$RUN_ID"
REPORT_JSON="$RUN_DIR/report.json"
SUMMARY_MD="$RUN_DIR/summary.md"
LAUNCHAGENT_TEMPLATE="$RUN_DIR/com.leokwan.vidux-firstbite-verified-alive.template.plist"

command -v jq >/dev/null 2>&1 || { echo "vidux-firstbite-verified-alive-runner.sh requires jq" >&2; exit 127; }
[[ -f "$VERIFY_SCRIPT" ]] || { echo "missing verified-alive script: $VERIFY_SCRIPT" >&2; exit 2; }
[[ -f "$GOAL_AUDIT_SCRIPT" ]] || { echo "missing local-operator goal audit script: $GOAL_AUDIT_SCRIPT" >&2; exit 2; }

mkdir -p "$RUN_DIR"

iso_now() {
  date -u +%Y-%m-%dT%H:%M:%SZ
}

write_launchagent_template() {
  cat > "$LAUNCHAGENT_TEMPLATE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.leokwan.vidux-firstbite-verified-alive</string>
  <key>ProgramArguments</key>
  <array>
    <string>$RUNNER_SCRIPT</string>
  </array>
  <key>StartInterval</key>
  <integer>$CADENCE_SECONDS</integer>
  <key>StandardOutPath</key>
  <string>$LEDGER_DIR/vidux-firstbite-verified-alive-runner/launchagent.out.log</string>
  <key>StandardErrorPath</key>
  <string>$LEDGER_DIR/vidux-firstbite-verified-alive-runner/launchagent.err.log</string>
</dict>
</plist>
EOF
}

write_launchagent_template

ROLLUP_JSON="$RUN_DIR/verified-alive.json"
ROLLUP_MD="$RUN_DIR/verified-alive.md"

(
  cd "$VIDUX_ROOT"
  python3 "$VERIFY_SCRIPT" \
    --refresh-dir "$RUN_DIR" \
    --prefix "$RUN_ID" \
    --write-json "$ROLLUP_JSON" \
    --write-markdown "$ROLLUP_MD"
) > "$RUN_DIR/verified-alive.stdout"

[[ -f "$ROLLUP_JSON" ]] || { echo "verified-alive JSON missing: $ROLLUP_JSON" >&2; exit 1; }
[[ -f "$ROLLUP_MD" ]] || { echo "verified-alive markdown missing: $ROLLUP_MD" >&2; exit 1; }

jq -n \
  --slurpfile rollup "$ROLLUP_JSON" \
  --arg run_id "$RUN_ID" \
  --arg created_at "$(iso_now)" \
  --arg report_path "$REPORT_JSON" \
  --arg summary_path "$SUMMARY_MD" \
  --arg rollup_json "$ROLLUP_JSON" \
  --arg rollup_markdown "$ROLLUP_MD" \
  --arg launchagent_template "$LAUNCHAGENT_TEMPLATE" \
  --argjson cadence_seconds "$CADENCE_SECONDS" \
  '{
    run_id:$run_id,
    created_at:$created_at,
    report_path:$report_path,
    summary_path:$summary_path,
    readonly:true,
    local_ci_lanes_executed:false,
    install_performed:false,
    deletion_performed:false,
    drift_records_written:false,
    workers_dispatched:false,
    cadence_seconds:$cadence_seconds,
    launchagent:{
      label:"com.leokwan.vidux-firstbite-verified-alive",
      template_path:$launchagent_template,
      installed:false,
      install_rule:"Template only. Do not install or bootstrap without an explicit operator decision."
    },
    rollup:{
      json_path:$rollup_json,
      markdown_path:$rollup_markdown,
      status:$rollup[0].status,
      summary:$rollup[0].summary,
      inputs:$rollup[0].inputs,
      checks:$rollup[0].checks
    },
    rule:"Review-only verified-alive heartbeat packet. Install nothing and execute no lanes unless Leo explicitly approves the exact LaunchAgent or local-CI operation."
  }' > "$REPORT_JSON"

GOAL_AUDIT_JSON="$RUN_DIR/goal-audit.json"
GOAL_AUDIT_MD="$RUN_DIR/goal-audit.md"

(
  cd "$VIDUX_ROOT"
  python3 "$GOAL_AUDIT_SCRIPT" \
    --repo-root "$VIDUX_ROOT" \
    --verified-alive-report "$REPORT_JSON" \
    --write-json "$GOAL_AUDIT_JSON" \
    --write-markdown "$GOAL_AUDIT_MD"
) > "$RUN_DIR/goal-audit.stdout"

[[ -f "$GOAL_AUDIT_JSON" ]] || { echo "goal audit JSON missing: $GOAL_AUDIT_JSON" >&2; exit 1; }
[[ -f "$GOAL_AUDIT_MD" ]] || { echo "goal audit markdown missing: $GOAL_AUDIT_MD" >&2; exit 1; }

tmp_report="$RUN_DIR/report.with-goal-audit.json"
jq \
  --arg goal_audit_json "$GOAL_AUDIT_JSON" \
  --arg goal_audit_markdown "$GOAL_AUDIT_MD" \
  --slurpfile goal "$GOAL_AUDIT_JSON" \
  '.goal_audit = {
    json_path: $goal_audit_json,
    markdown_path: $goal_audit_markdown,
    status: $goal[0].status,
    summary: $goal[0].summary,
    status_counts: $goal[0].status_counts,
    recommended_next_goal: $goal[0].recommended_next_goal,
    next_resume_order: $goal[0].next_resume_order,
    local_ci_launch_trust: $goal[0].local_ci_launch_trust,
    criteria: $goal[0].criteria,
    non_claims: $goal[0].non_claims
  }' "$REPORT_JSON" > "$tmp_report"
mv "$tmp_report" "$REPORT_JSON"

{
  echo "# Vidux FirstBite Verified-Alive Runner"
  echo
  jq -r '"- run_id: \(.run_id)\n- created_at: \(.created_at)\n- readonly: \(.readonly)\n- local_ci_lanes_executed: \(.local_ci_lanes_executed)\n- install_performed: \(.install_performed)\n- deletion_performed: \(.deletion_performed)\n- drift_records_written: \(.drift_records_written)\n- workers_dispatched: \(.workers_dispatched)\n- cadence_seconds: \(.cadence_seconds)\n- rollup_status: \(.rollup.status)\n- rollup_summary: \(.rollup.summary)\n- rollup_json: `\(.rollup.json_path)`\n- rollup_markdown: `\(.rollup.markdown_path)`\n- goal_audit_status: \(.goal_audit.status)\n- goal_audit_summary: \(.goal_audit.summary)\n- goal_audit_json: `\(.goal_audit.json_path)`\n- goal_audit_markdown: `\(.goal_audit.markdown_path)`\n- launchagent_template: `\(.launchagent.template_path)`"' "$REPORT_JSON"
  echo
  echo "## Rollup Checks"
  echo
  jq -r '.rollup.checks[] | "- `\(.id)`: `\(.status)` - \(.summary // "no summary")"' "$REPORT_JSON"
  echo
  echo "## Goal Audit Criteria"
  echo
  jq -r '.goal_audit.criteria[] | "- `\(.id)`: `\(.status)` - \(.summary // "no summary")"' "$REPORT_JSON"
  echo
  echo "## Goal Audit Resume Order"
  echo
  jq -r '.goal_audit.next_resume_order[]? | "- \(.rank). `\(.criterion_id)`: `\(.resume_class)` / `\(.status)` - \(.why_next // "no reason")"' "$REPORT_JSON"
  echo
  echo "## Local CI Launch Trust"
  echo
  jq -r '
    .goal_audit.local_ci_launch_trust
    | "- status: `\(.status)`\n- summary: \(.summary)\n- gates: ready=`\(.ready_gate_count)` blocked=`\(.blocked_gate_count)` warning=`\(.warning_gate_count)` total=`\(.total_gate_count)`\n- failing_lanes: `\(.failing_lanes | length)`\n- manifest_blocking_repos: `\(.manifest_blocking_repos | length)`\n- stale_mcp_processes_effective: `\(.loaded_mcp_client.effective_stale_process_count // .loaded_mcp_client.stale_process_count)` / `\(.loaded_mcp_client.process_count)`\n- stale_mcp_processes_historical_refresh: `\(.loaded_mcp_client.historical_stale_process_count // .loaded_mcp_client.stale_process_count)` / `\(.loaded_mcp_client.process_count)`"
  ' "$REPORT_JSON"
  echo
  echo "### Blocked Gates"
  echo
  jq -r '.goal_audit.local_ci_launch_trust.blocked_gates[]? | "- `\(.id)`: \(.summary // "no summary")"' "$REPORT_JSON"
  echo
  echo "### Non-Pass Lanes"
  echo
  jq -r '.goal_audit.local_ci_launch_trust.failing_lanes[]? | "- `\(.lane)`: `\(.status)` rc=`\(.rc)` - \(.reason // "no reason")"' "$REPORT_JSON"
  echo
  echo "### Current Source Notes"
  echo
  jq -r '
    .goal_audit.local_ci_launch_trust.current_source_notes
    | "- status: `\(.status)`\n- summary: \(.summary)\n- worktree_execute_would_include_current_source: `\(.worktree_execute_would_include_current_source)`\n- clean_snowcubes_package_candidate: `\(.clean_snowcubes_package_candidate)`\n- package_json_delta: `\(.package_json_delta.status)` - \(.package_json_delta.summary)\n- safe_next_action: \(.safe_next_action)"
  ' "$REPORT_JSON"
  jq -r '
    (.goal_audit.local_ci_launch_trust.current_source_notes.approval_packet // {})
    | "- approval_packet: status=`\(.status)` path=`\(.path)` readonly=`\(.readonly)` tracker_files_copied=`\(.tracker_files_copied)` local_ci_lanes_executed=`\(.local_ci_lanes_executed)` approval_gate=`\(.approval_gate_status)`"
  ' "$REPORT_JSON"
  jq -r '
    .goal_audit.local_ci_launch_trust.current_source_notes.files[]?
    | "- `\(.path)`: tracked=`\(.tracked)` exists=`\(.exists)` status=`\(.status)`"
  ' "$REPORT_JSON"
  jq -r '
    .goal_audit.local_ci_launch_trust.current_source_notes.adjacent_files[]?
    | "- adjacent `\(.path)`: tracked=`\(.tracked)` exists=`\(.exists)` status=`\(.status)`"
  ' "$REPORT_JSON"
  jq -r '
    .goal_audit.local_ci_launch_trust.current_source_notes.package_json_delta
    | "- unrelated package drift: scripts=`\((.unrelated_script_changes // []) | join(","))` deps=`\((.unrelated_dependency_changes // []) | join(","))`"
  ' "$REPORT_JSON"
  echo
  echo "No LaunchAgent was installed. No local-CI lanes were executed."
  echo "No files were deleted. No drift records were written. No workers were dispatched."
  echo "The LaunchAgent plist is a template for review only."
} > "$SUMMARY_MD"

if [[ "$PRINT_JSON" -eq 1 ]]; then
  cat "$REPORT_JSON"
else
  jq -r '"report_path=\(.report_path)\nsummary_path=\(.summary_path)\nrollup_status=\(.rollup.status)\nrollup_summary=\(.rollup.summary)\ngoal_audit_status=\(.goal_audit.status)\ngoal_audit_summary=\(.goal_audit.summary)\nlaunchagent_template=\(.launchagent.template_path)\ninstall_performed=\(.install_performed)\nlocal_ci_lanes_executed=\(.local_ci_lanes_executed)"' "$REPORT_JSON"
fi
