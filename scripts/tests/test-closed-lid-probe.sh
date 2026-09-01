#!/bin/bash
set -euo pipefail

TEST_DIR=$(cd "$(dirname "$0")" && pwd)
PROBE="$TEST_DIR/../closed-lid-probe.sh"
EXPECTED_STUDIO="Leos-Mac-Studio-10442.local"
EXPECTED_LAB="Leos-MacBook-Pro-5.local"
TEST_TMP=$(mktemp -d "${TMPDIR:-/tmp}/closed-lid-probe-test.XXXXXX")
trap 'rm -rf "$TEST_TMP"' EXIT

fail() {
  echo "CLOSED_LID_PROBE_TEST_FAIL $*" >&2
  exit 1
}

assert_json() {
  local path=$1
  local expression=$2
  /usr/bin/python3 - "$path" "$expression" <<'PY'
import json
import sys

path, expression = sys.argv[1:]
with open(path, encoding="utf-8") as handle:
    payload = json.load(handle)
if not eval(expression, {"__builtins__": {}}, {"p": payload, "len": len}):
    raise SystemExit(f"assertion failed: {expression}; payload={payload!r}")
PY
}

[[ -x "$PROBE" ]] || fail "probe missing or not executable: $PROBE"

OPEN_JSON="$TEST_TMP/open.json"
"$PROBE" \
  --host "$EXPECTED_LAB" \
  --expected-studio "$EXPECTED_STUDIO" \
  --expected-host "$EXPECTED_LAB" \
  --expect open \
  --output "$OPEN_JSON"
assert_json "$OPEN_JSON" "p['schema'] == 'xcode-lab.closed-lid-probe.v1'"
assert_json "$OPEN_JSON" "p['studio']['hostname'] == '$EXPECTED_STUDIO'"
assert_json "$OPEN_JSON" "p['lab']['hostname'] == '$EXPECTED_LAB'"
assert_json "$OPEN_JSON" "p['transport']['ssh_batch'] is True and p['transport']['screen_sharing_tcp'] is True"
assert_json "$OPEN_JSON" "p['transport']['endpoint_bound'] is True and p['transport']['endpoint_digest'] == p['transport']['screen_endpoint_digest']"
assert_json "$OPEN_JSON" "p['transport']['strict_host_key_checking'] is True and len(p['transport']['known_host_fingerprint_digest']) == 64"
assert_json "$OPEN_JSON" "p['lab']['power_source'] == 'AC Power'"
assert_json "$OPEN_JSON" "p['lab']['lid'] == 'open'"
assert_json "$OPEN_JSON" "p['lab']['arch'] == 'arm64' and p['lab']['os_version'] and p['lab']['os_build']"
assert_json "$OPEN_JSON" "p['transport']['screen_sharing_service'] == 'running'"
assert_json "$OPEN_JSON" "p['lab']['filevault'] == 'off'"
assert_json "$OPEN_JSON" "p['lab']['prevent_system_sleep'] is not None and p['lab']['prevent_idle_sleep'] is not None"
assert_json "$OPEN_JSON" "p['verdict']['status'] == 'PASS' and p['verdict']['expected'] == 'open'"

CLOSED_JSON="$TEST_TMP/expected-closed.json"
set +e
"$PROBE" \
  --host "$EXPECTED_LAB" \
  --expected-studio "$EXPECTED_STUDIO" \
  --expected-host "$EXPECTED_LAB" \
  --expect closed \
  --output "$CLOSED_JSON"
CLOSED_EXIT=$?
set -e
[[ "$CLOSED_EXIT" -eq 24 ]] || fail "expected open-lid negative control exit 24, got $CLOSED_EXIT"
assert_json "$CLOSED_JSON" "p['lab']['lid'] == 'open' and p['verdict']['status'] == 'FAIL_MODE_MISMATCH'"

WRONG_STUDIO_JSON="$TEST_TMP/wrong-studio.json"
set +e
"$PROBE" \
  --host "$EXPECTED_LAB" \
  --expected-studio "not-the-studio.local" \
  --expected-host "$EXPECTED_LAB" \
  --expect any \
  --output "$WRONG_STUDIO_JSON"
WRONG_STUDIO_EXIT=$?
set -e
[[ "$WRONG_STUDIO_EXIT" -eq 26 ]] || fail "expected wrong-studio exit 26, got $WRONG_STUDIO_EXIT"
assert_json "$WRONG_STUDIO_JSON" "p['verdict']['status'] == 'FAIL_STUDIO_IDENTITY'"

WRONG_HOST_JSON="$TEST_TMP/wrong-host.json"
set +e
"$PROBE" \
  --host "$EXPECTED_LAB" \
  --expected-studio "$EXPECTED_STUDIO" \
  --expected-host "not-the-m1.local" \
  --expect any \
  --output "$WRONG_HOST_JSON"
WRONG_HOST_EXIT=$?
set -e
[[ "$WRONG_HOST_EXIT" -eq 22 ]] || fail "expected wrong-host exit 22, got $WRONG_HOST_EXIT"
assert_json "$WRONG_HOST_JSON" "p['verdict']['status'] == 'FAIL_HOST_IDENTITY'"

VNC_JSON="$TEST_TMP/vnc-unreachable.json"
set +e
"$PROBE" \
  --host "$EXPECTED_LAB" \
  --expected-studio "$EXPECTED_STUDIO" \
  --expected-host "$EXPECTED_LAB" \
  --vnc-port 1 \
  --expect any \
  --output "$VNC_JSON"
VNC_EXIT=$?
set -e
[[ "$VNC_EXIT" -eq 21 ]] || fail "expected unreachable Screen Sharing exit 21, got $VNC_EXIT"
assert_json "$VNC_JSON" "p['transport']['ssh_batch'] is True and p['transport']['screen_sharing_tcp'] is False and p['verdict']['status'] == 'FAIL_SCREEN_SHARING_TCP'"

SSH_JSON="$TEST_TMP/ssh-unreachable.json"
set +e
"$PROBE" \
  --host "$EXPECTED_LAB" \
  --expected-studio "$EXPECTED_STUDIO" \
  --expected-host "$EXPECTED_LAB" \
  --ssh-port 1 \
  --expect any \
  --output "$SSH_JSON"
SSH_EXIT=$?
set -e
[[ "$SSH_EXIT" -eq 20 ]] || fail "expected unreachable SSH exit 20, got $SSH_EXIT"
assert_json "$SSH_JSON" "p['transport']['ssh_batch'] is False and p['transport']['screen_sharing_tcp'] is True and p['verdict']['status'] == 'FAIL_SSH_BATCH'"

DIVERGENT_JSON="$TEST_TMP/divergent-endpoint.json"
set +e
CLOSED_LID_PROBE_VNC_ENDPOINT_OVERRIDE=127.0.0.1 "$PROBE" \
  --host "$EXPECTED_LAB" \
  --expected-studio "$EXPECTED_STUDIO" \
  --expected-host "$EXPECTED_LAB" \
  --expect any \
  --output "$DIVERGENT_JSON"
DIVERGENT_EXIT=$?
set -e
[[ "$DIVERGENT_EXIT" -eq 28 ]] || fail "expected divergent-endpoint exit 28, got $DIVERGENT_EXIT"
assert_json "$DIVERGENT_JSON" "p['transport']['endpoint_bound'] is False and p['transport']['endpoint_digest'] != p['transport']['screen_endpoint_digest'] and p['verdict']['status'] == 'FAIL_ENDPOINT_DIVERGENCE'"

/usr/bin/python3 - "$OPEN_JSON" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
serialized_keys = " ".join(
    str(key)
    for item in [payload, *payload.values()]
    if isinstance(item, dict)
    for key in item
)
if re.search(r"password|credential|token|recovery.?key|username", serialized_keys, re.I):
    raise SystemExit(f"secret-shaped JSON key detected: {serialized_keys}")
PY

echo "CLOSED_LID_PROBE_TEST_PASS real_open=PASS expected_closed=RED wrong_studio=RED wrong_host=RED vnc_unreachable=RED ssh_unreachable=RED divergent_endpoint=RED strict_known_host=PASS remote_identity=PASS screen_service=PASS filevault=off sleep_assertions=NON_NULL secret_keys=ABSENT"
echo "GROUNDTRUTH_COMPLETE: real-host integration | real-dep: yes | gap: native Screen Sharing authentication, pixel input, physical lid-close, sleep/wake, IDE visual proof, and restart remain gated @ $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
