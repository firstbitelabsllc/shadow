#!/bin/bash
set -euo pipefail

LAB_HOST="Leos-MacBook-Pro-5.local"
EXPECTED_STUDIO="Leos-Mac-Studio-10442.local"
EXPECTED_LAB="Leos-MacBook-Pro-5.local"
EXPECTED_MODE="any"
SSH_PORT=22
VNC_PORT=5900
OUTPUT="-"

usage() {
  cat <<'USAGE'
usage: closed-lid-probe.sh [--host HOST] [--expected-studio HOST]
       [--expected-host HOST] [--expect any|open|closed]
       [--ssh-port PORT] [--vnc-port PORT] [--output PATH|-]
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) LAB_HOST=${2:?missing host}; shift 2 ;;
    --expected-studio) EXPECTED_STUDIO=${2:?missing expected Studio}; shift 2 ;;
    --expected-host) EXPECTED_LAB=${2:?missing expected lab}; shift 2 ;;
    --expect) EXPECTED_MODE=${2:?missing expected mode}; shift 2 ;;
    --ssh-port) SSH_PORT=${2:?missing SSH port}; shift 2 ;;
    --vnc-port) VNC_PORT=${2:?missing VNC port}; shift 2 ;;
    --output) OUTPUT=${2:?missing output}; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 64 ;;
  esac
done

case "$EXPECTED_MODE" in
  any|open|closed) ;;
  *) echo "--expect must be any, open, or closed" >&2; exit 64 ;;
esac
case "$SSH_PORT:$VNC_PORT" in
  *[!0-9:]*) echo "--ssh-port and --vnc-port must be numeric" >&2; exit 64 ;;
esac

PROBE_TMP=$(mktemp -d "${TMPDIR:-/tmp}/closed-lid-probe.XXXXXX")
trap 'rm -rf "$PROBE_TMP"' EXIT
REMOTE_TSV="$PROBE_TMP/remote.tsv"

OBSERVED_AT=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
STUDIO_HOST=$(hostname)
SSH_BATCH=false
SCREEN_TCP=false
STRICT_HOST_KEY_CHECKING=true

RESOLVED_ADDRESS=$(/usr/bin/python3 - "$LAB_HOST" <<'PY'
import socket
import sys

host = sys.argv[1]
rows = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
addresses = sorted({(row[0], row[4][0]) for row in rows}, key=lambda item: (item[0] != socket.AF_INET, item[1]))
if not addresses:
    raise SystemExit(1)
print(addresses[0][1])
PY
) || RESOLVED_ADDRESS=""

SCREEN_ADDRESS=${CLOSED_LID_PROBE_VNC_ENDPOINT_OVERRIDE:-$RESOLVED_ADDRESS}
ENDPOINT_DIGEST=""
SCREEN_ENDPOINT_DIGEST=""
ENDPOINT_BOUND=false
if [[ -n "$RESOLVED_ADDRESS" ]]; then
  ENDPOINT_DIGEST=$(printf '%s' "$RESOLVED_ADDRESS" | shasum -a 256 | awk '{print $1}')
fi
if [[ -n "$SCREEN_ADDRESS" ]]; then
  SCREEN_ENDPOINT_DIGEST=$(printf '%s' "$SCREEN_ADDRESS" | shasum -a 256 | awk '{print $1}')
fi
if [[ -n "$ENDPOINT_DIGEST" && "$ENDPOINT_DIGEST" == "$SCREEN_ENDPOINT_DIGEST" ]]; then
  ENDPOINT_BOUND=true
fi

KNOWN_HOST_FINGERPRINT_DIGEST=""
if /usr/bin/ssh-keygen -F "$LAB_HOST" >"$PROBE_TMP/known-hosts" 2>/dev/null; then
  KNOWN_HOST_FINGERPRINT_DIGEST=$(
    grep -v '^#' "$PROBE_TMP/known-hosts" \
      | /usr/bin/ssh-keygen -lf - 2>/dev/null \
      | shasum -a 256 \
      | awk '{print $1}'
  )
fi

if [[ -n "$SCREEN_ADDRESS" ]] && /usr/bin/nc -G 3 -z "$SCREEN_ADDRESS" "$VNC_PORT" >/dev/null 2>&1; then
  SCREEN_TCP=true
fi

if [[ -n "$RESOLVED_ADDRESS" ]] && /usr/bin/ssh \
  -o BatchMode=yes \
  -o ConnectTimeout=8 \
  -o StrictHostKeyChecking=yes \
  -o HostKeyAlias="$LAB_HOST" \
  -o HostName="$RESOLVED_ADDRESS" \
  -p "$SSH_PORT" \
  "$LAB_HOST" /bin/bash -s >"$REMOTE_TSV" 2>/dev/null <<'REMOTE'
set -u
host=$(hostname)
os_version=$(sw_vers -productVersion)
os_build=$(sw_vers -buildVersion)
arch=$(uname -m)
filevault_raw=$(fdesetup status 2>/dev/null || true)
case "$filevault_raw" in
  *"FileVault is On"*) filevault=on ;;
  *"FileVault is Off"*) filevault=off ;;
  *) filevault=unknown ;;
esac
clamshell_raw=$(ioreg -r -k AppleClamshellState -d 4 | awk -F' = ' '/AppleClamshellState/{print $2; exit}')
case "$clamshell_raw" in
  Yes) lid=closed ;;
  No) lid=open ;;
  *) lid=unknown ;;
esac
power_source=$(pmset -g batt | sed -n "s/^Now drawing from '\(.*\)'$/\1/p")
screen_state=$(launchctl print system/com.apple.screensharing 2>/dev/null | awk '/^[[:space:]]*state = /{print $3; exit}')
screen_active=$(launchctl print system/com.apple.screensharing 2>/dev/null | awk '/^[[:space:]]*active count = /{print $4; exit}')
prevent_system_sleep=$(pmset -g assertions | awk '/^[[:space:]]*PreventSystemSleep[[:space:]]/{print $2; exit}')
prevent_idle_sleep=$(pmset -g assertions | awk '/^[[:space:]]*PreventUserIdleSystemSleep[[:space:]]/{print $2; exit}')
printf 'hostname\t%s\n' "$host"
printf 'os_version\t%s\n' "$os_version"
printf 'os_build\t%s\n' "$os_build"
printf 'arch\t%s\n' "$arch"
printf 'filevault\t%s\n' "$filevault"
printf 'lid\t%s\n' "$lid"
printf 'power_source\t%s\n' "$power_source"
printf 'screen_state\t%s\n' "${screen_state:-unknown}"
printf 'screen_active_count\t%s\n' "${screen_active:-0}"
printf 'prevent_system_sleep\t%s\n' "${prevent_system_sleep:-unknown}"
printf 'prevent_idle_sleep\t%s\n' "${prevent_idle_sleep:-unknown}"
REMOTE
then
  SSH_BATCH=true
fi

LAB_HOSTNAME=""
LAB_OS_VERSION=""
LAB_OS_BUILD=""
LAB_ARCH=""
FILEVAULT="unknown"
LID="unknown"
POWER_SOURCE="unknown"
SCREEN_STATE="unknown"
SCREEN_ACTIVE_COUNT="0"
PREVENT_SYSTEM_SLEEP="unknown"
PREVENT_IDLE_SLEEP="unknown"

if [[ "$SSH_BATCH" == true ]]; then
  while IFS=$'\t' read -r key value; do
    case "$key" in
      hostname) LAB_HOSTNAME=$value ;;
      os_version) LAB_OS_VERSION=$value ;;
      os_build) LAB_OS_BUILD=$value ;;
      arch) LAB_ARCH=$value ;;
      filevault) FILEVAULT=$value ;;
      lid) LID=$value ;;
      power_source) POWER_SOURCE=$value ;;
      screen_state) SCREEN_STATE=$value ;;
      screen_active_count) SCREEN_ACTIVE_COUNT=$value ;;
      prevent_system_sleep) PREVENT_SYSTEM_SLEEP=$value ;;
      prevent_idle_sleep) PREVENT_IDLE_SLEEP=$value ;;
    esac
  done <"$REMOTE_TSV"
fi

VERDICT="PASS"
DETAIL="all requested infrastructure predicates passed"
EXIT_CODE=0
if [[ "$STUDIO_HOST" != "$EXPECTED_STUDIO" ]]; then
  VERDICT="FAIL_STUDIO_IDENTITY"; DETAIL="observed Studio hostname does not match expected identity"; EXIT_CODE=26
elif [[ "$ENDPOINT_BOUND" != true ]]; then
  VERDICT="FAIL_ENDPOINT_DIVERGENCE"; DETAIL="SSH and Screen Sharing are not bound to one resolved endpoint"; EXIT_CODE=28
elif [[ "$SSH_BATCH" != true ]]; then
  VERDICT="FAIL_SSH_BATCH"; DETAIL="BatchMode SSH did not reach the lab"; EXIT_CODE=20
elif [[ "$SCREEN_TCP" != true ]]; then
  VERDICT="FAIL_SCREEN_SHARING_TCP"; DETAIL="Screen Sharing TCP endpoint was unreachable"; EXIT_CODE=21
elif [[ "$LAB_HOSTNAME" != "$EXPECTED_LAB" ]]; then
  VERDICT="FAIL_HOST_IDENTITY"; DETAIL="remote hostname does not match expected lab identity"; EXIT_CODE=22
elif [[ "$LAB_ARCH" != "arm64" || -z "$LAB_OS_VERSION" || -z "$LAB_OS_BUILD" ]]; then
  VERDICT="FAIL_REMOTE_IDENTITY"; DETAIL="remote architecture or OS identity is incomplete"; EXIT_CODE=27
elif [[ "$POWER_SOURCE" != "AC Power" ]]; then
  VERDICT="FAIL_POWER_SOURCE"; DETAIL="lab is not drawing from AC power"; EXIT_CODE=23
elif [[ "$SCREEN_STATE" != "running" ]]; then
  VERDICT="FAIL_SCREEN_SHARING_SERVICE"; DETAIL="remote Screen Sharing service is not running"; EXIT_CODE=25
elif [[ "$EXPECTED_MODE" != "any" && "$LID" != "$EXPECTED_MODE" ]]; then
  VERDICT="FAIL_MODE_MISMATCH"; DETAIL="observed lid mode does not match expected mode"; EXIT_CODE=24
fi

JSON_OUT="$PROBE_TMP/probe.json"
/usr/bin/python3 - \
  "$OBSERVED_AT" "$STUDIO_HOST" "$EXPECTED_STUDIO" \
  "$LAB_HOST" "$LAB_HOSTNAME" "$EXPECTED_LAB" "$LAB_OS_VERSION" "$LAB_OS_BUILD" "$LAB_ARCH" \
  "$SSH_BATCH" "$SSH_PORT" "$SCREEN_TCP" "$VNC_PORT" "$SCREEN_STATE" "$SCREEN_ACTIVE_COUNT" \
  "$STRICT_HOST_KEY_CHECKING" "$ENDPOINT_DIGEST" "$SCREEN_ENDPOINT_DIGEST" "$ENDPOINT_BOUND" "$KNOWN_HOST_FINGERPRINT_DIGEST" \
  "$POWER_SOURCE" "$LID" "$FILEVAULT" "$PREVENT_SYSTEM_SLEEP" "$PREVENT_IDLE_SLEEP" \
  "$EXPECTED_MODE" "$VERDICT" "$DETAIL" >"$JSON_OUT" <<'PY'
import json
import sys

(
    observed_at,
    studio_host,
    expected_studio,
    lab_target,
    lab_hostname,
    expected_lab,
    os_version,
    os_build,
    arch,
    ssh_batch,
    ssh_port,
    screen_tcp,
    vnc_port,
    screen_state,
    screen_active_count,
    strict_host_key_checking,
    endpoint_digest,
    screen_endpoint_digest,
    endpoint_bound,
    known_host_fingerprint_digest,
    power_source,
    lid,
    filevault,
    prevent_system_sleep,
    prevent_idle_sleep,
    expected_mode,
    verdict,
    detail,
) = sys.argv[1:]

def truth(value: str) -> bool:
    return value == "true"

def integer(value: str):
    try:
        return int(value)
    except ValueError:
        return None

payload = {
    "schema": "xcode-lab.closed-lid-probe.v1",
    "observed_at": observed_at,
    "studio": {
        "hostname": studio_host,
        "expected_hostname": expected_studio,
    },
    "lab": {
        "target": lab_target,
        "hostname": lab_hostname or None,
        "expected_hostname": expected_lab,
        "os_version": os_version or None,
        "os_build": os_build or None,
        "arch": arch or None,
        "power_source": power_source,
        "lid": lid,
        "filevault": filevault,
        "prevent_system_sleep": integer(prevent_system_sleep),
        "prevent_idle_sleep": integer(prevent_idle_sleep),
    },
    "transport": {
        "ssh_batch": truth(ssh_batch),
        "ssh_port": integer(ssh_port),
        "strict_host_key_checking": truth(strict_host_key_checking),
        "known_host_fingerprint_digest": known_host_fingerprint_digest or None,
        "screen_sharing_tcp": truth(screen_tcp),
        "screen_sharing_port": integer(vnc_port),
        "screen_sharing_service": screen_state,
        "screen_sharing_active_count": integer(screen_active_count),
        "endpoint_digest": endpoint_digest or None,
        "screen_endpoint_digest": screen_endpoint_digest or None,
        "endpoint_bound": truth(endpoint_bound),
    },
    "verdict": {
        "expected": expected_mode,
        "status": verdict,
        "detail": detail,
        "pixel_control_proven": False,
    },
}
json.dump(payload, sys.stdout, indent=2, sort_keys=True)
sys.stdout.write("\n")
PY

if [[ "$OUTPUT" == "-" ]]; then
  cat "$JSON_OUT"
else
  mkdir -p "$(dirname "$OUTPUT")"
  cp "$JSON_OUT" "$OUTPUT"
fi

exit "$EXIT_CODE"
