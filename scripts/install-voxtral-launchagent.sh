#!/usr/bin/env bash
# Install or repair the local Voxtral MLX read-aloud LaunchAgent.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LABEL="${VIDUX_VOXTRAL_LABEL:-com.leokwan.vidux-voxtral-mlx}"
HOST="${VIDUX_VOXTRAL_HOST:-127.0.0.1}"
PORT="${VIDUX_VOXTRAL_PORT:-8765}"
UV_BIN="${VIDUX_UV_BIN:-${HOME}/.local/bin/uv}"
HF_HOME_DIR="${HF_HOME:-${HOME}/.cache/huggingface}"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
STDOUT_LOG="${HOME}/Library/Logs/vidux-voxtral-mlx.stdout.log"
STDERR_LOG="${HOME}/Library/Logs/vidux-voxtral-mlx.stderr.log"
BOOTSTRAP=1
CHECK=1
CHECK_EXPLICIT=0
PRINT_ONLY=0
LINT_ONLY=0

print_help() {
  cat <<EOF
install-voxtral-launchagent - install/repair Vidux local read-aloud TTS.

usage:
  scripts/install-voxtral-launchagent.sh [--no-bootstrap] [--no-check] [--check] [--print] [--lint]

env:
  VIDUX_VOXTRAL_LABEL   launchd label (default: ${LABEL})
  VIDUX_VOXTRAL_HOST    bind host (default: ${HOST})
  VIDUX_VOXTRAL_PORT    bind port (default: ${PORT})
  VIDUX_UV_BIN          uv executable (default: ${UV_BIN})
  HF_HOME               Hugging Face cache (default: ${HF_HOME_DIR})

examples:
  scripts/install-voxtral-launchagent.sh
  scripts/install-voxtral-launchagent.sh --lint
  scripts/install-voxtral-launchagent.sh --no-bootstrap --no-check
  launchctl print gui/\$(id -u)/${LABEL}
  curl http://${HOST}:${PORT}/health
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-bootstrap)
      BOOTSTRAP=0
      shift
      ;;
    --no-check)
      CHECK=0
      CHECK_EXPLICIT=1
      shift
      ;;
    --check)
      CHECK=1
      CHECK_EXPLICIT=1
      shift
      ;;
    --print)
      PRINT_ONLY=1
      shift
      ;;
    --lint)
      LINT_ONLY=1
      shift
      ;;
    --help|-h)
      print_help
      exit 0
      ;;
    *)
      echo "unknown flag: $1" >&2
      print_help >&2
      exit 2
      ;;
  esac
done

if [[ "${BOOTSTRAP}" == "0" && "${CHECK_EXPLICIT}" == "0" ]]; then
  CHECK=0
fi

xml_escape() {
  local value="$1"
  value="${value//&/&amp;}"
  value="${value//</&lt;}"
  value="${value//>/&gt;}"
  printf '%s' "${value}"
}

write_plist() {
  local dest="$1"
  local label repo_root uv_bin host port home_dir hf_home stdout_log stderr_log path_value
  label="$(xml_escape "${LABEL}")"
  repo_root="$(xml_escape "${REPO_ROOT}")"
  uv_bin="$(xml_escape "${UV_BIN}")"
  host="$(xml_escape "${HOST}")"
  port="$(xml_escape "${PORT}")"
  home_dir="$(xml_escape "${HOME}")"
  hf_home="$(xml_escape "${HF_HOME_DIR}")"
  stdout_log="$(xml_escape "${STDOUT_LOG}")"
  stderr_log="$(xml_escape "${STDERR_LOG}")"
  path_value="$(xml_escape "${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin")"
  cat >"${dest}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label}</string>
  <key>WorkingDirectory</key>
  <string>${repo_root}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${uv_bin}</string>
    <string>run</string>
    <string>--with</string>
    <string>git+https://github.com/redseaplume/Voxtral-4B-TTS-2603-MLX.git</string>
    <string>${repo_root}/browser/scripts/voxtral_mlx_server.py</string>
    <string>--host</string>
    <string>${host}</string>
    <string>--port</string>
    <string>${port}</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key>
    <string>${home_dir}</string>
    <key>HF_HOME</key>
    <string>${hf_home}</string>
    <key>LANG</key>
    <string>en_US.UTF-8</string>
    <key>LC_ALL</key>
    <string>en_US.UTF-8</string>
    <key>PATH</key>
    <string>${path_value}</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ProcessType</key>
  <string>Background</string>
  <key>StandardOutPath</key>
  <string>${stdout_log}</string>
  <key>StandardErrorPath</key>
  <string>${stderr_log}</string>
</dict>
</plist>
PLIST
}

if [[ "${PRINT_ONLY}" == "1" || "${LINT_ONLY}" == "1" ]]; then
  tmp="$(mktemp)"
  write_plist "${tmp}"
  if [[ "${PRINT_ONLY}" == "1" ]]; then
    cat "${tmp}"
  fi
  if [[ "${LINT_ONLY}" == "1" ]]; then
    plutil -lint "${tmp}"
  fi
  rm -f "${tmp}"
  exit 0
fi

if [[ ! -x "${UV_BIN}" ]]; then
  echo "[FAIL] uv executable not found or not executable: ${UV_BIN}" >&2
  exit 1
fi

mkdir -p "$(dirname "${PLIST}")" "$(dirname "${STDOUT_LOG}")" "${HF_HOME_DIR}"
write_plist "${PLIST}"
plutil -lint "${PLIST}"

if [[ "${BOOTSTRAP}" == "1" ]]; then
  user_id="$(id -u)"
  launchctl bootout "gui/${user_id}/${LABEL}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/${user_id}" "${PLIST}"
  launchctl kickstart -k "gui/${user_id}/${LABEL}"
  launchctl print "gui/${user_id}/${LABEL}" >/dev/null
fi

if [[ "${CHECK}" == "1" ]]; then
  deadline=$((SECONDS + 30))
  until curl -fsS --max-time 2 "http://${HOST}:${PORT}/health" >/dev/null; do
    if (( SECONDS >= deadline )); then
      echo "[FAIL] ${LABEL} did not answer http://${HOST}:${PORT}/health within 30s" >&2
      exit 1
    fi
    sleep 1
  done
fi

echo "[PASS] ${LABEL} installed at ${PLIST}"
echo "health=http://${HOST}:${PORT}/health"
