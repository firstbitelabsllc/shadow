#!/usr/bin/env bash
# Prove a host's wiring works — not that its files exist.
#
# `shadow doctor` answers "is it installed": the mount resolves, the command on
# PATH belongs to this checkout, the standing goal is current. Every one of
# those is an existence check, and the failure this milestone cares about slips
# past all of them: a host that has the files and still opens cold, without the
# skill, asking which project to attach to.
#
# Two tiers, because the honest answer is that only one of them is free:
#
#   offline (default)  Everything checkable without a model. Mount resolution,
#                      shadowing by a higher-priority source, parseable skill
#                      frontmatter, the directive present and current, `shadow`
#                      on PATH being THIS checkout, and the board reachable
#                      from an unrelated directory through that same command.
#
#   --live             One real non-interactive host invocation. This is the
#                      only thing that proves a SESSION resolves the skill, and
#                      it costs the owner's quota, so it never runs by default.
#
# usage: scripts/shadow-verify-host.sh --host claude-code|codex|cursor|grok [--by SEAT] [--live] [--timeout-seconds N]
set -uo pipefail

ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST=""
LIVE=0
SEAT=""
LIVE_TIMEOUT=120
FAILURES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      [[ $# -ge 2 ]] || { echo "verify-host: --host requires a value" >&2; exit 2; }
      HOST="$2"; shift 2 ;;
    --by)
      [[ $# -ge 2 ]] || { echo "verify-host: --by requires a value" >&2; exit 2; }
      SEAT="$2"; shift 2 ;;
    --live) LIVE=1; shift ;;
    --timeout-seconds)
      [[ $# -ge 2 ]] || { echo "verify-host: --timeout-seconds requires a value" >&2; exit 2; }
      LIVE_TIMEOUT="$2"; shift 2 ;;
    -h|--help) sed -n '2,22p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "verify-host: unknown argument: $1" >&2; exit 2 ;;
  esac
done

case "${HOST}" in
  claude-code) MOUNT="${HOME}/.claude/skills/shadow"; DIRECTIVE="${HOME}/.claude/CLAUDE.md"; BIN="claude" ;;
  codex)       MOUNT="${HOME}/.agents/skills/shadow"; DIRECTIVE="${HOME}/.codex/AGENTS.md"; BIN="codex" ;;
  cursor)      MOUNT="${HOME}/.cursor/skills/shadow"; DIRECTIVE=""; BIN="cursor-agent" ;;
  grok)        MOUNT="${HOME}/.grok/skills/shadow"; DIRECTIVE="${HOME}/.grok/AGENTS.md"; BIN="grok" ;;
  *) echo "verify-host: --host must be claude-code, codex, cursor, or grok" >&2; exit 2 ;;
esac

[[ -z "${SEAT}" ]] && SEAT="${HOST/claude-code/claude}"
if [[ ! "${SEAT}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "verify-host: --by must be one stable public seat name" >&2
  exit 2
fi
if [[ ! "${LIVE_TIMEOUT}" =~ ^[1-9][0-9]*$ ]]; then
  echo "verify-host: --timeout-seconds must be a positive integer" >&2
  exit 2
fi

ok()   { printf '  [PASS] %s\n' "$1"; }
bad()  { printf '  [FAIL] %s\n' "$1"; FAILURES=$((FAILURES + 1)); }
warn() { printf '  [WARN] %s\n' "$1"; }
skip() { printf '  [SKIP] %s\n' "$1"; }

board_facts() {
  python3 -c '
import json, sys

try:
    data = json.load(sys.stdin)
    seat = sys.argv[1]
    plans = data.get("v4_plans", [])
    current = None
    selected = None
    for plan in plans:
        claim = next(
            (item for item in plan.get("live_claims", []) if item.get("owner") == seat),
            None,
        )
        if claim:
            current = plan
            selected = claim
            break
    if current is None:
        current = next((plan for plan in plans if plan.get("next_unclaimed")), None)
        if current is not None:
            row_id = current["next_unclaimed"]
            selected = next(
                checkpoint
                for milestone in current.get("milestones", [])
                for checkpoint in milestone.get("checkpoints", [])
                if checkpoint.get("id") == row_id
            )
    if current is None or selected is None:
        raise ValueError
    revision = data["root_board"]["revision"]
    project = current["project"]
    resume = selected.get("row") or selected.get("id")
    work = selected.get("text")
    if not isinstance(revision, int) or not project or not resume or not work:
        raise ValueError
except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError):
    sys.exit(1)

print(revision)
print(project)
print(resume)
print(work)
' "${1}"
}

run_bounded() {
  local stdout_path="$1" stderr_path="$2"
  shift 2
  python3 - "${LIVE_TIMEOUT}" "${stdout_path}" "${stderr_path}" "$@" <<'PY'
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

timeout = int(sys.argv[1])
stdout_path = Path(sys.argv[2])
stderr_path = Path(sys.argv[3])
command = sys.argv[4:]

def stop_process_group(process: subprocess.Popen[bytes]) -> None:
    # A host may return after leaving tools or helpers in the background. The
    # verifier owns the whole fresh process group on every exit path, not only
    # on timeout, so no successful proof can leak work into the next run.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    # A loaded release train can delay a cooperative child's TERM trap beyond
    # a fixed 200 ms sleep. Poll the process group for a bounded grace period:
    # ordinary hosts return immediately once drained, while a stuck descendant
    # still receives an unconditional KILL after one second.
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        try:
            os.killpg(process.pid, 0)
        except (ProcessLookupError, PermissionError):
            return
        time.sleep(0.02)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass

with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
    process = subprocess.Popen(
        command,
        stdout=stdout,
        stderr=stderr,
        start_new_session=True,
    )
    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        stop_process_group(process)
        process.wait()
        raise SystemExit(124)
    stop_process_group(process)
    raise SystemExit(returncode)
PY
}

# Resolve a command to the real file it ends at, so a symlinked `shadow` on
# PATH can be compared against this checkout's own binary.
resolve_cmd() {
  local p="$1" t
  while [[ -L "${p}" ]]; do
    t="$(readlink "${p}")"
    [[ "${t}" != /* ]] && t="$(dirname "${p}")/${t}"
    p="${t}"
  done
  printf '%s/%s\n' "$(cd -P "$(dirname "${p}")" 2>/dev/null && pwd)" "$(basename "${p}")"
}

echo "verify-host: ${HOST}"

# 1. The mount resolves to THIS checkout. A mount pointing at another clone
#    means the session reads one version's law while `shadow` runs another's.
if [[ ! -e "${MOUNT}" ]]; then
  bad "no skill mount at \$HOME/${MOUNT#"${HOME}/"} — run: bash install.sh"
elif [[ "$(cd -P "${MOUNT}" 2>/dev/null && pwd)" != "${ROOT}" ]]; then
  bad "skill mount resolves elsewhere — another checkout is serving this host"
else
  ok "skill mount resolves to this checkout"
fi

# 2. Nothing shadows it. Host loaders take the first match, so a directory of
#    the same name in a higher-priority source wins silently and forever.
SHADOWED=0
for other in "${HOME}/.claude/skills" "${HOME}/.agents/skills" "${HOME}/.cursor/skills" "${HOME}/.grok/skills"; do
  candidate="${other}/shadow"
  [[ "${candidate}" == "${MOUNT}" ]] && continue
  if [[ -e "${candidate}" && "$(cd -P "${candidate}" 2>/dev/null && pwd)" != "${ROOT}" ]]; then
    bad "a different 'shadow' skill is mounted in ${other#"${HOME}/"} — one of them is stale"
    SHADOWED=1
  fi
done
[[ "${SHADOWED}" -eq 0 ]] && ok "no competing 'shadow' skill in any host root"

# 3. The skill is loadable, not merely present. A loader that cannot parse the
#    frontmatter drops the skill without saying so, so parse the block the way
#    a host does: a terminated YAML mapping carrying name and description.
SKILL="${MOUNT}/SKILL.md"
if [[ ! -f "${SKILL}" ]]; then
  bad "no SKILL.md behind the mount"
elif ! REASON="$(python3 - "${SKILL}" <<'PY'
import re, sys

lines = open(sys.argv[1], encoding="utf-8").read().splitlines()
if not lines or lines[0].strip() != "---":
    print("does not open with a --- fence"); sys.exit(1)
end = next((i for i, l in enumerate(lines[1:], 1) if l.strip() in ("---", "...")), None)
if end is None:
    print("is never closed"); sys.exit(1)

body = lines[1:end]
try:
    import yaml
    data = yaml.safe_load("\n".join(body))
except ImportError:
    data = {}
    for raw in body:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", raw)
        if not m:
            data = None; break
        value = m.group(2).strip()
        if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        data[m.group(1)] = value
except Exception:
    print("is not valid YAML"); sys.exit(1)

if not isinstance(data, dict):
    print("is not a key/value mapping"); sys.exit(1)
missing = [k for k in ("name", "description") if not str(data.get(k) or "").strip()]
if missing:
    print("is missing " + " and ".join(missing)); sys.exit(1)
PY
)"; then
  bad "SKILL.md frontmatter ${REASON} — a loader would drop the skill"
else
  ok "SKILL.md frontmatter parses, with name and description"
fi

# 4. The standing goal is present and current. `shadow doctor` owns the
#    authoritative comparison; this reports the same fact per host.
if [[ -z "${DIRECTIVE}" ]]; then
  # Cursor user rules live in application settings, not a file. Asserting a
  # path here would invent a convention and then report success for wiring
  # that does nothing.
  skip "cold directive activation is unsupported for this host; host-run and skill mount remain verifiable"
elif [[ ! -f "${DIRECTIVE}" ]]; then
  bad "no instruction file — run: shadow goal --install"
elif ! "${ROOT}/bin/shadow" goal | head -1 | grep -qF "$(head -1 <("${ROOT}/bin/shadow" goal))" 2>/dev/null; then
  bad "could not read the standing goal from this checkout"
else
  anchor="$("${ROOT}/bin/shadow" goal | head -1)"
  copies="$(grep -cF "${anchor}" "${DIRECTIVE}" || true)"
  if [[ "${copies}" -eq 0 ]]; then
    bad "the standing goal is not in this host's instruction file — run: shadow goal --install"
  elif [[ "${copies}" -gt 1 ]]; then
    bad "${copies} copies of the standing goal — the host reads the first one"
  elif "${ROOT}/bin/shadow" goal | grep -qF "$(sed -n '1p' <("${ROOT}/bin/shadow" goal))" && \
       python3 - "${DIRECTIVE}" "${ROOT}" <<'PY'
import subprocess, sys
directive, root = sys.argv[1], sys.argv[2]
block = subprocess.run([f"{root}/bin/shadow", "goal"], capture_output=True, text=True).stdout.strip()
sys.exit(0 if block and block in open(directive, encoding="utf-8").read() else 1)
PY
  then
    ok "the standing goal is present and current"
  else
    bad "the standing goal is stale — run: shadow goal --install"
  fi
fi

# 5. The command a cold session actually reaches. A session types `shadow`, so
#    PATH identity is part of the wiring: an installer that linked into a
#    directory the host never sees, or another checkout earlier on PATH, both
#    leave every file in place and still break the first move. Everything below
#    runs whatever PATH resolves, because that is what a session runs.
ON_PATH="$(command -v shadow 2>/dev/null || true)"
if [[ -z "${ON_PATH}" ]]; then
  SHADOW_CMD="${ROOT}/bin/shadow"
  bad "no 'shadow' on PATH — a cold session's first command is not found"
elif [[ "$(resolve_cmd "${ON_PATH}")" != "$(resolve_cmd "${ROOT}/bin/shadow")" ]]; then
  SHADOW_CMD="${ON_PATH}"
  bad "'shadow' on PATH is ${ON_PATH} — a session would run another checkout"
else
  SHADOW_CMD="${ON_PATH}"
  ok "'shadow' on PATH is this checkout"
fi

# 6. THE POINT. A session's first move is `shadow status` from wherever it
#    opened. If that returns nothing, the host asks "which project?" — the one
#    question this whole milestone exists to make unnecessary.
SCRATCH="$(mktemp -d)"
trap 'rm -rf -- "${SCRATCH}"' EXIT
BOARD_STATUS=0
BOARD_ERROR="${SCRATCH}/board-status.err"
BOARD="$(cd "${SCRATCH}" && "${SHADOW_CMD}" status --json --by "${SEAT}" 2>"${BOARD_ERROR}")" || BOARD_STATUS=$?
BOARD_FACTS="$(printf '%s' "${BOARD}" | board_facts "${SEAT}" 2>/dev/null || true)"
BOARD_REVISION="$(sed -n '1p' <<<"${BOARD_FACTS}")"
BOARD_PROJECT="$(sed -n '2p' <<<"${BOARD_FACTS}")"
BOARD_RESUME="$(sed -n '3p' <<<"${BOARD_FACTS}")"
BOARD_WORK="$(sed -n '4p' <<<"${BOARD_FACTS}")"
if grep -q "portfolio refresh failed" "${BOARD_ERROR}" || { [[ "${BOARD_STATUS}" -ne 0 ]] && [[ -z "${BOARD}" ]]; }; then
  bad "the board refresh fails from an unrelated directory — a cold session would start from stale authority"
elif [[ -z "${BOARD}" ]]; then
  bad "the board is empty from an unrelated directory — a cold session has nothing to open"
elif [[ -z "${BOARD_REVISION}" || -z "${BOARD_PROJECT}" || -z "${BOARD_RESUME}" || -z "${BOARD_WORK}" ]]; then
  bad "the board names no reachable resume checkpoint — a session would have nothing to take"
else
  ok "the board is reachable from an unrelated directory, with a reachable resume checkpoint"
  if [[ "${BOARD_STATUS}" -ne 0 ]]; then
    warn "status also reports unrelated plan health; the selected checkpoint remains current"
  fi
fi

# 7. The live tier. Only this proves a SESSION loads the skill; everything
#    above proves the pieces are in place for it to.
if [[ "${LIVE}" -eq 0 ]]; then
  skip "session check (costs model quota) — re-run with --live to prove a cold session resolves the skill"
elif [[ "${HOST}" == "cursor" ]]; then
  skip "live session check is unsupported for this host because it has no cold directive activation surface"
elif ! command -v "${BIN}" >/dev/null 2>&1; then
  bad "${BIN} is not installed, so the session check cannot run"
elif [[ -z "${BOARD_REVISION}" || -z "${BOARD_PROJECT}" || -z "${BOARD_RESUME}" || -z "${BOARD_WORK}" ]]; then
  bad "the live session has no current board evidence to verify"
else
  # The prompt names no command on purpose. Spelling out `shadow status` would
  # let any generic session pass by following instructions; asking only what
  # the work is means the answer can arrive one way — the skill and standing
  # goal loaded, and the session went to the board on its own. It names neither
  # the command, the evidence fields, nor any value the verifier will accept.
  PROMPT="As seat ${SEAT}, what am I working on right now?"
  LIVE_OUT="${SCRATCH}/host-final.txt"
  LIVE_LOG="${SCRATCH}/host-diagnostics.txt"
  BOARD_TEXT_FILE="${SCRATCH}/board.txt"
  BOARD_JSON_FILE="${SCRATCH}/board.json"
  READ_ONLY_BIN="${SCRATCH}/read-only-bin"
  LIVE_STATUS=0
  BOARD_TEXT_STATUS=0
  (cd "${SCRATCH}" && "${SHADOW_CMD}" status --by "${SEAT}" >"${BOARD_TEXT_FILE}" 2>/dev/null) || BOARD_TEXT_STATUS=$?
  printf '%s' "${BOARD}" >"${BOARD_JSON_FILE}"
  mkdir "${READ_ONLY_BIN}"
  cat >"${READ_ONLY_BIN}/shadow" <<'SH'
#!/bin/sh
root=$(CDPATH= cd "$(dirname "$0")/.." && pwd)
if [ "${1:-}" != "status" ]; then
  echo "shadow verifier: only read-only status is available in this session" >&2
  exit 2
fi
shift
for arg in "$@"; do
  if [ "$arg" = "--json" ]; then
    exec cat "$root/board.json"
  fi
done
exec cat "$root/board.txt"
SH
  chmod 700 "${READ_ONLY_BIN}/shadow"
  if [[ "${BOARD_TEXT_STATUS}" -ne 0 ]]; then
    bad "the human board view could not be frozen for the live session"
  else
    case "${HOST}" in
      claude-code)
        (cd "${SCRATCH}" && PATH="${READ_ONLY_BIN}:${PATH}" \
          run_bounded "${LIVE_OUT}" "${LIVE_LOG}" \
          "${BIN}" --no-session-persistence --permission-mode plan \
          -p "${PROMPT}") || LIVE_STATUS=$?
        ;;
      grok)
        (cd "${SCRATCH}" && PATH="${READ_ONLY_BIN}:${PATH}" \
          run_bounded "${LIVE_OUT}" "${LIVE_LOG}" \
          "${BIN}" --permission-mode plan -p "${PROMPT}") || LIVE_STATUS=$?
        ;;
      codex)
        (cd "${SCRATCH}" && PATH="${READ_ONLY_BIN}:${PATH}" \
          run_bounded "${LIVE_LOG}" "${LIVE_LOG}.stderr" \
          "${BIN}" exec --ephemeral --skip-git-repo-check --sandbox read-only \
          --output-last-message "${LIVE_OUT}" "${PROMPT}") || LIVE_STATUS=$?
        ;;
    esac
  fi
  AFTER_STATUS=0
  AFTER_BOARD="$(cd "${SCRATCH}" && "${SHADOW_CMD}" status --json --by "${SEAT}" 2>/dev/null)" || AFTER_STATUS=$?
  AFTER_FACTS="$(printf '%s' "${AFTER_BOARD}" | board_facts "${SEAT}" 2>/dev/null || true)"
  if [[ "${BOARD_TEXT_STATUS}" -ne 0 ]]; then
    : # The specific failure was already reported without spending host quota.
  elif [[ "${LIVE_STATUS}" -eq 124 ]]; then
    [[ "${LIVE_TIMEOUT}" -eq 1 ]] && TIME_UNIT="second" || TIME_UNIT="seconds"
    bad "the cold ${HOST} session timed out after ${LIVE_TIMEOUT} ${TIME_UNIT} — the result is inconclusive; re-run"
  elif [[ "${LIVE_STATUS}" -ne 0 ]]; then
    bad "the cold ${HOST} session invocation failed"
  elif [[ "${AFTER_STATUS}" -ne 0 || -z "${AFTER_FACTS}" ]]; then
    bad "the board could not be re-observed after the live session"
  elif [[ "${AFTER_FACTS}" != "${BOARD_FACTS}" ]]; then
    bad "the root board changed during the live session — the result is inconclusive; re-run"
  elif python3 - "${LIVE_OUT}" "${BOARD_PROJECT}" "${BOARD_WORK}" <<'PY'
import re
from pathlib import Path
import sys

path, project, work = sys.argv[1:]
try:
    answer = Path(path).read_text(encoding="utf-8")
except (OSError, UnicodeError):
    raise SystemExit(1)

stop = {
    "after", "also", "and", "are", "before", "being", "blocked", "completed",
    "current", "from", "have", "into", "only", "pending", "that", "the", "their",
    "this", "through", "what", "when", "where", "which", "with", "without", "working",
}

def stems(value: str) -> set[str]:
    result = set()
    for token in re.findall(r"[a-z0-9]+", value.lower()):
        if len(token) < 4 or token in stop:
            continue
        for suffix in ("ations", "ation", "ating", "ated", "ates", "ate", "ing", "ed", "es", "s"):
            if token.endswith(suffix) and len(token) > len(suffix) + 3:
                token = token[:-len(suffix)]
                break
        result.add(token)
    return result

project_pattern = r"[-_ ]+".join(re.escape(part) for part in project.split("-"))
project_seen = re.search(
    rf"(?<![A-Za-z0-9_-]){project_pattern}(?![A-Za-z0-9_-])",
    answer,
    re.IGNORECASE,
)
expected = stems(work)
overlap = expected.intersection(stems(answer))
needed = min(3, len(expected))
raise SystemExit(0 if project_seen and needed and len(overlap) >= needed else 1)
PY
  then
    ok "a cold ${HOST} session found the board unprompted and described its current work"
  else
    bad "a cold ${HOST} session did not identify the current project and work unprompted"
  fi
fi

if [[ "${FAILURES}" -gt 0 ]]; then
  echo "verify-host: ${HOST} — ${FAILURES} failure(s)"
  exit 1
fi
echo "verify-host: ${HOST} — wiring verified"
