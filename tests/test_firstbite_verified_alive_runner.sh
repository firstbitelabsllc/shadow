#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER="$ROOT/scripts/vidux-firstbite-verified-alive-runner.sh"

TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/vidux-firstbite-verified-alive-runner-test.XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT

LEDGER_ROOT="$TMP_ROOT/ledger"
FAKE_VERIFY="$TMP_ROOT/fake-verified-alive.py"
FAKE_GOAL_AUDIT="$TMP_ROOT/fake-goal-audit.py"
RUN_ID="verified-alive-review"

cat > "$FAKE_VERIFY" <<'PY'
#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--refresh-dir", required=True)
parser.add_argument("--prefix", required=True)
parser.add_argument("--write-json", required=True)
parser.add_argument("--write-markdown", required=True)
args = parser.parse_args()

refresh_dir = Path(args.refresh_dir)
refresh_dir.mkdir(parents=True, exist_ok=True)
inputs = {}
for name in [
    "firstbite-status",
    "observe-policy",
    "moussey-health",
    "chat-providers",
    "moussey-local-ci",
]:
    path = refresh_dir / f"{args.prefix}-{name}.json"
    path.write_text(json.dumps({"ok": True, "name": name}), encoding="utf-8")
    inputs[name] = str(path)

payload = {
    "status": "warning",
    "summary": "warning: 3 ready, 5 warning, 0 blocked",
    "inputs": inputs,
    "checks": [
        {"id": "firstbite_catalog", "status": "ready", "summary": "repo-backed catalog is ready"},
        {"id": "chat_front_door", "status": "warning", "summary": "local chat works but escalation is gated"},
    ],
    "non_claims": [
        "This rollup did not execute local-CI lanes.",
        "This rollup did not install or bootstrap a LaunchAgent.",
    ],
}
Path(args.write_json).write_text(json.dumps(payload), encoding="utf-8")
Path(args.write_markdown).write_text("# fake verified alive\n", encoding="utf-8")
print(json.dumps(payload))
PY
chmod +x "$FAKE_VERIFY"

cat > "$FAKE_GOAL_AUDIT" <<'PY'
#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--repo-root", required=True)
parser.add_argument("--verified-alive-report", required=True)
parser.add_argument("--write-json", required=True)
parser.add_argument("--write-markdown", required=True)
args = parser.parse_args()

Path(args.verified_alive_report).read_text(encoding="utf-8")
payload = {
    "status": "incomplete",
    "summary": "incomplete: fake goal audit",
    "status_counts": {"partial": 1, "documented_non_blocking": 1},
    "recommended_next_goal": {
        "objective": "close the next partial criterion",
        "first_resume_criterion": "local_ci_current_machine",
        "first_resume_class": "agent_doable",
        "guardrails": ["stay read-only"],
    },
    "next_resume_order": [
        {
            "rank": 1,
            "criterion_id": "local_ci_current_machine",
            "status": "partial",
            "resume_class": "agent_doable",
            "why_next": "local-CI still warning",
            "next_resume": ["open latest summary"],
        }
    ],
    "local_ci_launch_trust": {
        "status": "blocked",
        "summary": "4/12 launch trust gate(s) ready; 3 blocked; 5 warning/unknown.",
        "ready_gate_count": 4,
        "blocked_gate_count": 3,
        "warning_gate_count": 5,
        "total_gate_count": 12,
        "blocked_gates": [
            {"id": "declared-lanes", "summary": "40/43 declared pass; 3 non-pass"}
        ],
        "warning_gates": [],
        "failing_lanes": [
            {
                "lane": "moussey_snowcubes_readiness",
                "status": "fail",
                "rc": 1,
                "reason": "command exited with code 1",
            }
        ],
        "current_source_notes": {
            "repo": "moussey",
            "repo_path": "/tmp/moussey",
            "status": "source_state_warning",
            "summary": "structured blocker proof is dirty/untracked",
            "worktree_execute_would_include_current_source": False,
            "clean_snowcubes_package_candidate": False,
            "reason": "current structured blocker proof is dirty/untracked",
            "safe_next_action": "Split the Snowcubes local-CI source package away from unrelated package drift, then rerun moussey_snowcubes_readiness from that source.",
            "files": [
                {
                    "path": ".firstbite/local-ci.json",
                    "tracked": True,
                    "exists": True,
                    "status": "M",
                },
                {
                    "path": "scripts/snowcubes-invoice-e2e-bundle.ts",
                    "tracked": False,
                    "exists": True,
                    "status": "??",
                },
            ],
            "adjacent_files": [
                {
                    "path": "package-lock.json",
                    "tracked": True,
                    "exists": True,
                    "status": "M",
                }
            ],
            "package_json_delta": {
                "status": "mixed_or_missing",
                "summary": "package.json mixes Snowcubes local-CI drift with unrelated or missing package changes; split before packaging source.",
                "required_script_present": True,
                "clean_snowcubes_package_candidate": False,
                "unrelated_script_changes": ["test:slack"],
                "unrelated_dependency_changes": ["@slack/bolt"],
            },
        },
        "manifest_blocking_repos": [{"repo": "Moussey"}],
        "loaded_mcp_client": {
            "stale_process_count": 5,
            "historical_stale_process_count": 5,
            "effective_stale_process_count": 0,
            "process_count": 5
        },
    },
    "criteria": [
        {
            "id": "local_ci_current_machine",
            "status": "partial",
            "summary": "local-CI still warning",
        },
        {
            "id": "captain_setup_health",
            "status": "documented_non_blocking",
            "summary": "Captain warnings are non-blocking",
        },
    ],
    "non_claims": [
        "This audit did not mark the active goal complete.",
    ],
}
Path(args.write_json).write_text(json.dumps(payload), encoding="utf-8")
Path(args.write_markdown).write_text("# fake goal audit\n", encoding="utf-8")
print(json.dumps(payload))
PY
chmod +x "$FAKE_GOAL_AUDIT"

AGENT_LEDGER_DIR="$LEDGER_ROOT" \
VIDUX_VERIFIED_ALIVE_SCRIPT="$FAKE_VERIFY" \
VIDUX_LOCAL_OPERATOR_GOAL_AUDIT_SCRIPT="$FAKE_GOAL_AUDIT" \
VIDUX_VERIFIED_ALIVE_RUN_ID="$RUN_ID" \
VIDUX_VERIFIED_ALIVE_CADENCE_SECONDS=1800 \
  bash "$RUNNER" > "$TMP_ROOT/stdout.txt"

REPORT="$LEDGER_ROOT/vidux-firstbite-verified-alive-runner/$RUN_ID/report.json"
SUMMARY="$LEDGER_ROOT/vidux-firstbite-verified-alive-runner/$RUN_ID/summary.md"
PLIST="$LEDGER_ROOT/vidux-firstbite-verified-alive-runner/$RUN_ID/com.leokwan.vidux-firstbite-verified-alive.template.plist"
GOAL_AUDIT_JSON="$LEDGER_ROOT/vidux-firstbite-verified-alive-runner/$RUN_ID/goal-audit.json"
GOAL_AUDIT_MD="$LEDGER_ROOT/vidux-firstbite-verified-alive-runner/$RUN_ID/goal-audit.md"

jq -e '
  .readonly == true
  and .local_ci_lanes_executed == false
  and .install_performed == false
  and .deletion_performed == false
  and .drift_records_written == false
  and .workers_dispatched == false
  and .cadence_seconds == 1800
  and .launchagent.installed == false
  and (.launchagent.template_path | endswith("com.leokwan.vidux-firstbite-verified-alive.template.plist"))
  and .rollup.status == "warning"
  and .rollup.summary == "warning: 3 ready, 5 warning, 0 blocked"
  and .goal_audit.status == "incomplete"
  and .goal_audit.summary == "incomplete: fake goal audit"
  and .goal_audit.status_counts.partial == 1
  and .goal_audit.recommended_next_goal.first_resume_criterion == "local_ci_current_machine"
  and .goal_audit.next_resume_order[0].resume_class == "agent_doable"
  and .goal_audit.local_ci_launch_trust.status == "blocked"
  and .goal_audit.local_ci_launch_trust.blocked_gates[0].id == "declared-lanes"
  and .goal_audit.local_ci_launch_trust.current_source_notes.status == "source_state_warning"
  and .goal_audit.local_ci_launch_trust.current_source_notes.worktree_execute_would_include_current_source == false
  and .goal_audit.local_ci_launch_trust.current_source_notes.clean_snowcubes_package_candidate == false
  and .goal_audit.local_ci_launch_trust.current_source_notes.package_json_delta.status == "mixed_or_missing"
  and (.goal_audit.json_path | endswith("goal-audit.json"))
  and (.goal_audit.markdown_path | endswith("goal-audit.md"))
' "$REPORT" >/dev/null || {
  jq '{readonly, local_ci_lanes_executed, install_performed, deletion_performed, drift_records_written, workers_dispatched, cadence_seconds, launchagent, rollup, goal_audit}' "$REPORT" >&2
  exit 1
}

[[ -f "$GOAL_AUDIT_JSON" ]]
[[ -f "$GOAL_AUDIT_MD" ]]
grep -q 'No LaunchAgent was installed. No local-CI lanes were executed.' "$SUMMARY"
grep -q '## Rollup Checks' "$SUMMARY"
grep -q '`firstbite_catalog`: `ready` - repo-backed catalog is ready' "$SUMMARY"
grep -q '`chat_front_door`: `warning` - local chat works but escalation is gated' "$SUMMARY"
grep -q 'goal_audit_status: incomplete' "$SUMMARY"
grep -q '## Goal Audit Criteria' "$SUMMARY"
grep -q '`local_ci_current_machine`: `partial` - local-CI still warning' "$SUMMARY"
grep -q '`captain_setup_health`: `documented_non_blocking` - Captain warnings are non-blocking' "$SUMMARY"
grep -q '## Goal Audit Resume Order' "$SUMMARY"
grep -q '1. `local_ci_current_machine`: `agent_doable` / `partial` - local-CI still warning' "$SUMMARY"
grep -q '## Local CI Launch Trust' "$SUMMARY"
grep -q 'failing_lanes: `1`' "$SUMMARY"
grep -q '`declared-lanes`: 40/43 declared pass; 3 non-pass' "$SUMMARY"
grep -q '`moussey_snowcubes_readiness`: `fail` rc=`1` - command exited with code 1' "$SUMMARY"
grep -q '### Current Source Notes' "$SUMMARY"
grep -q 'worktree_execute_would_include_current_source: `false`' "$SUMMARY"
grep -q 'clean_snowcubes_package_candidate: `false`' "$SUMMARY"
grep -q 'package_json_delta: `mixed_or_missing`' "$SUMMARY"
grep -q '`scripts/snowcubes-invoice-e2e-bundle.ts`: tracked=`false` exists=`true` status=`??`' "$SUMMARY"
grep -q 'adjacent `package-lock.json`: tracked=`true` exists=`true` status=`M`' "$SUMMARY"
grep -q 'unrelated package drift: scripts=`test:slack` deps=`@slack/bolt`' "$SUMMARY"
grep -q '<key>StartInterval</key>' "$PLIST"
grep -q '<integer>1800</integer>' "$PLIST"
grep -q 'goal_audit_status=incomplete' "$TMP_ROOT/stdout.txt"
grep -q 'install_performed=false' "$TMP_ROOT/stdout.txt"
grep -q 'local_ci_lanes_executed=false' "$TMP_ROOT/stdout.txt"

CLI_RUN_ID="verified-alive-cli"
AGENT_LEDGER_DIR="$LEDGER_ROOT" \
VIDUX_VERIFIED_ALIVE_SCRIPT="$FAKE_VERIFY" \
VIDUX_LOCAL_OPERATOR_GOAL_AUDIT_SCRIPT="$FAKE_GOAL_AUDIT" \
VIDUX_VERIFIED_ALIVE_CADENCE_SECONDS=1800 \
  bash "$RUNNER" --run-id "$CLI_RUN_ID" --json > "$TMP_ROOT/stdout-cli.json"

CLI_REPORT="$LEDGER_ROOT/vidux-firstbite-verified-alive-runner/$CLI_RUN_ID/report.json"
jq -e --arg run_id "$CLI_RUN_ID" --arg report "$CLI_REPORT" '
  .run_id == $run_id
  and .report_path == $report
  and (.rollup.json_path | contains($run_id))
  and .goal_audit.status == "incomplete"
  and .goal_audit.recommended_next_goal.first_resume_criterion == "local_ci_current_machine"
  and .goal_audit.local_ci_launch_trust.status == "blocked"
  and .goal_audit.local_ci_launch_trust.current_source_notes.status == "source_state_warning"
  and .goal_audit.local_ci_launch_trust.current_source_notes.package_json_delta.status == "mixed_or_missing"
  and (.goal_audit.json_path | contains($run_id))
  and (.launchagent.template_path | contains($run_id))
' "$TMP_ROOT/stdout-cli.json" >/dev/null || {
  jq '{run_id, report_path, rollup_json:.rollup.json_path, goal_audit, launchagent_template:.launchagent.template_path}' "$TMP_ROOT/stdout-cli.json" >&2
  exit 1
}
