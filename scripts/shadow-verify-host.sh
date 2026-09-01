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
# Cursor has no file-backed global directive, so its live tier is deliberately
# repository-scoped: pass --repo PATH only when PATH is a Git repository root
# with tracked AGENTS.md or CLAUDE.md. Without it, Cursor remains an explicit skip.
#
# usage: scripts/shadow-verify-host.sh --host claude-code|codex|cursor|grok|zai [--by SEAT] [--repo PATH] [--live] [--timeout-seconds N]
set -uo pipefail

ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST=""
LIVE=0
SEAT=""
REPO=""
LIVE_TIMEOUT=120
FAILURES=0

# Ambient Git redirection must not steer the repository probes below: GIT_DIR
# and friends override `git -C`. The variable list is derived from the same
# boundary the Python side enforces (scripts/shadow_git.py), so it cannot
# drift; the fallback covers a machine where the import fails.
GIT_INJECTION="$(python3 -c "
import sys
sys.path.insert(0, '${ROOT}/scripts')
import shadow_git
print(' '.join(sorted(shadow_git.GIT_INJECTION_VARS)))
" 2>/dev/null || echo 'GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_COMMON_DIR')"
for GIT_VAR in ${GIT_INJECTION}; do
  unset "${GIT_VAR}"
done
for GIT_VAR in $(env | sed -n 's/^\(GIT_CONFIG_KEY_[0-9][0-9]*\)=.*/\1/p; s/^\(GIT_CONFIG_VALUE_[0-9][0-9]*\)=.*/\1/p'); do
  unset "${GIT_VAR}"
done
export GIT_NO_REPLACE_OBJECTS=1 GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/usr/bin/false
unset GIT_INJECTION GIT_VAR

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      [[ $# -ge 2 ]] || { echo "verify-host: --host requires a value" >&2; exit 2; }
      HOST="$2"; shift 2 ;;
    --by)
      [[ $# -ge 2 ]] || { echo "verify-host: --by requires a value" >&2; exit 2; }
      SEAT="$2"; shift 2 ;;
    --repo)
      [[ $# -ge 2 ]] || { echo "verify-host: --repo requires a value" >&2; exit 2; }
      REPO="$2"; shift 2 ;;
    --live) LIVE=1; shift ;;
    --timeout-seconds)
      [[ $# -ge 2 ]] || { echo "verify-host: --timeout-seconds requires a value" >&2; exit 2; }
      LIVE_TIMEOUT="$2"; shift 2 ;;
    -h|--help) sed -n '2,26p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "verify-host: unknown argument: $1" >&2; exit 2 ;;
  esac
done

case "${HOST}" in
  claude-code) MOUNT="${HOME}/.claude/skills/shadow"; DIRECTIVE="${HOME}/.claude/CLAUDE.md"; BIN="claude" ;;
  codex)       MOUNT="${HOME}/.agents/skills/shadow"; DIRECTIVE="${HOME}/.codex/AGENTS.md"; BIN="codex" ;;
  cursor)      MOUNT="${HOME}/.cursor/skills/shadow"; DIRECTIVE=""; BIN="cursor-agent" ;;
  grok)        MOUNT="${HOME}/.grok/skills/shadow"; DIRECTIVE="${HOME}/.grok/AGENTS.md"; BIN="grok" ;;
  zai)         MOUNT=""; DIRECTIVE=""; BIN="opencode" ;;
  *) echo "verify-host: --host must be claude-code, codex, cursor, grok, or zai" >&2; exit 2 ;;
esac

if [[ -n "${REPO}" && "${HOST}" != "cursor" ]]; then
  echo "verify-host: --repo is only valid for --host cursor" >&2
  exit 2
fi

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

CURSOR_REPO=""
CURSOR_REPO_REASON=""
CURSOR_INSTRUCTION=""
if [[ "${HOST}" == "cursor" && -n "${REPO}" ]]; then
  if [[ ! -d "${REPO}" ]]; then
    CURSOR_REPO_REASON="the path does not exist or is not a directory"
  elif ! CURSOR_REPO="$(cd -P "${REPO}" 2>/dev/null && pwd)"; then
    CURSOR_REPO_REASON="the path cannot be resolved"
  else
    GIT_TOP="$(git -C "${CURSOR_REPO}" rev-parse --show-toplevel 2>/dev/null || true)"
    if [[ -z "${GIT_TOP}" ]]; then
      CURSOR_REPO_REASON="the path is not a Git repository"
    elif [[ "$(cd -P "${GIT_TOP}" 2>/dev/null && pwd)" != "${CURSOR_REPO}" ]]; then
      CURSOR_REPO_REASON="the path is not the Git repository root"
    else
      for candidate in AGENTS.md CLAUDE.md; do
        if [[ -f "${CURSOR_REPO}/${candidate}" ]] && \
           git -C "${CURSOR_REPO}" ls-files --error-unmatch -- "${candidate}" >/dev/null 2>&1; then
          CURSOR_INSTRUCTION="${candidate}"
          break
        fi
      done
      if [[ -z "${CURSOR_INSTRUCTION}" ]]; then
        CURSOR_REPO_REASON="the repository root has no source-controlled AGENTS.md or CLAUDE.md"
      fi
    fi
  fi
fi

board_facts() {
  python3 -c '
import json, sys

try:
    data = json.load(sys.stdin)
    seat = sys.argv[1]
    plans = data.get("v4_plans", [])
    targets = []
    for plan in plans:
        targets.extend(
            (plan, item)
            for item in plan.get("live_claims", [])
            if item.get("owner") == seat
        )
    if not targets:
        current = next((plan for plan in plans if plan.get("next_unclaimed")), None)
        if current is not None:
            row_id = current["next_unclaimed"]
            selected = next(
                checkpoint
                for milestone in current.get("milestones", [])
                for checkpoint in milestone.get("checkpoints", [])
                if checkpoint.get("id") == row_id
            )
            targets.append((current, selected))
    if not targets:
        raise ValueError
    revision = data["root_board"]["revision"]
    if not isinstance(revision, int):
        raise ValueError
    facts = []
    for current, selected in targets:
        project = current["project"]
        resume = selected.get("row") or selected.get("id")
        work = selected.get("text")
        if not project or not resume or not work:
            raise ValueError
        facts.append((project, resume, work))
except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError):
    sys.exit(1)

print(revision)
for project, resume, work in facts:
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

# 1. The mount resolves to the product source explicitly elected by Skillbox,
#    or to this checkout on a standalone direct install. The command checkout
#    and the clean skill-runtime clone may be separate, but an undeclared clone
#    is still a split-brain failure.
EXPECTED_SKILL_DIR=""
if ! EXPECTED_SKILL_DIR="$(python3 - "${ROOT}" <<'PY' 2>&1
import importlib.util
from pathlib import Path
import sys

root = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location(
    "shadow_doctor_expected_skill",
    root / "scripts" / "shadow-doctor.py",
)
if spec is None or spec.loader is None:
    raise SystemExit("doctor module is unavailable")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
expected, error = module.expected_skill_file()
if error or expected is None:
    raise SystemExit(error or "Shadow skill source election is unavailable")
print(expected.parent)
PY
)"; then
  bad "skill source election is unreadable: ${EXPECTED_SKILL_DIR}"
  EXPECTED_SKILL_DIR="${ROOT}"
fi

if [[ -z "${MOUNT}" ]]; then
  skip "no file-backed skill mount for this host; sealed host-run remains verifiable"
elif [[ ! -e "${MOUNT}" ]]; then
  bad "no skill mount at \$HOME/${MOUNT#"${HOME}/"} — run: bash install.sh"
elif [[ "$(cd -P "${MOUNT}" 2>/dev/null && pwd)" != "${EXPECTED_SKILL_DIR}" ]]; then
  bad "skill mount resolves elsewhere — another checkout is serving this host without the explicit election"
else
  ok "skill mount resolves to the elected product source"
fi

# 2. Nothing shadows it. Host loaders take the first match, so a directory of
#    the same name in a higher-priority source wins silently and forever.
SHADOWED=0
for other in "${HOME}/.claude/skills" "${HOME}/.agents/skills" "${HOME}/.cursor/skills" "${HOME}/.grok/skills"; do
  candidate="${other}/shadow"
  [[ "${candidate}" == "${MOUNT}" ]] && continue
  if [[ -e "${candidate}" && "$(cd -P "${candidate}" 2>/dev/null && pwd)" != "${EXPECTED_SKILL_DIR}" ]]; then
    bad "a different 'shadow' skill is mounted in ${other#"${HOME}/"} — one of them is stale"
    SHADOWED=1
  fi
done
[[ "${SHADOWED}" -eq 0 ]] && ok "no competing 'shadow' skill in any host root"

# Skills directories are not the whole loader graph. Claude and Codex also
# give installed plugins precedence, so a cached marketplace copy can
# win while every mount above resolves perfectly. Reuse doctor's one parser;
# two independent config readers would eventually disagree again.
if [[ "${HOST}" == "claude-code" || "${HOST}" == "codex" ]]; then
  if ! PRECEDENCE_REASON="$(python3 - "${ROOT}" "${HOST}" <<'PY'
import importlib.util
from pathlib import Path
import sys

root = Path(sys.argv[1])
host = sys.argv[2]
spec = importlib.util.spec_from_file_location(
    "shadow_doctor_precedence", root / "scripts" / "shadow-doctor.py"
)
if spec is None or spec.loader is None:
    print("could not load Shadow's skill-precedence check")
    raise SystemExit(1)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
check = next(
    item
    for item in module.skill_precedence_checks()
    if item["name"] == f"skill precedence: {host}"
)
print(check["detail"])
raise SystemExit(0 if check["state"] == "pass" else 1)
PY
)"; then
    [[ -n "${PRECEDENCE_REASON}" ]] || PRECEDENCE_REASON="could not evaluate installed Shadow plugin precedence"
    bad "${PRECEDENCE_REASON}"
  else
    ok "${PRECEDENCE_REASON}"
  fi
fi

# 3. The skill is loadable, not merely present. A loader that cannot parse the
#    frontmatter drops the skill without saying so, so parse the block the way
#    a host does: a terminated YAML mapping carrying name and description.
SKILL="${MOUNT}/SKILL.md"
if [[ -z "${MOUNT}" ]]; then
  skip "SKILL.md mount check is unsupported for this host"
elif [[ ! -f "${SKILL}" ]]; then
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
if [[ "${HOST}" == "zai" ]]; then
  skip "cold directive activation is unsupported for this host; sealed host-run remains verifiable"
elif [[ "${HOST}" == "cursor" && -z "${REPO}" ]]; then
  # Cursor user rules live in application settings, not a file. Asserting a
  # path here would invent a convention and then report success for wiring
  # that does nothing.
  skip "cold directive activation is unsupported for this host; host-run and skill mount remain verifiable"
elif [[ "${HOST}" == "cursor" && -n "${CURSOR_REPO_REASON}" ]]; then
  bad "Cursor --repo must name a repository root with source-controlled root AGENTS.md or CLAUDE.md — ${CURSOR_REPO_REASON}"
elif [[ "${HOST}" == "cursor" ]]; then
  ok "the Cursor repository root exposes source-controlled ${CURSOR_INSTRUCTION}"
elif [[ ! -f "${DIRECTIVE}" ]]; then
  bad "no instruction file — run: shadow goal --install"
else
  # `shadow doctor` owns the authoritative comparison; verify reports the
  # same fact per host through the same importlib door steps 1-2 use, so the
  # two can never rule opposite ways on one file again.
  GOAL_VERDICT="$(python3 - "${HOST}" "${ROOT}" <<'PY' 2>&1
import importlib.util
import json
from pathlib import Path
import sys

host, root = sys.argv[1], Path(sys.argv[2])
spec = importlib.util.spec_from_file_location(
    "shadow_doctor_verify_goal",
    root / "scripts" / "shadow-doctor.py",
)
if spec is None or spec.loader is None:
    raise SystemExit("doctor module is unavailable")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
for item in module.host_goal_checks():
    if item["name"] == f"standing goal: {host}":
        print(json.dumps({"state": item["state"], "detail": item["detail"]}))
        break
else:
    print(json.dumps({"state": "fail", "detail": f"doctor does not cover host {host}"}))
PY
)"
  goal_state="$(printf '%s' "${GOAL_VERDICT}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["state"])')"
  goal_detail="$(printf '%s' "${GOAL_VERDICT}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["detail"])')"
  case "${goal_state}" in
    pass) ok "${goal_detail}" ;;
    warn) warn "${goal_detail}" ;;
    *) bad "${goal_detail}" ;;
  esac
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
elif [[ "${HOST}" == "zai" ]]; then
  skip "live session check is unsupported for this host because it has no cold directive activation surface"
elif [[ "${HOST}" == "cursor" && -z "${REPO}" ]]; then
  skip "live session check is unsupported for this host because it has no cold directive activation surface"
elif [[ "${HOST}" == "cursor" && -n "${CURSOR_REPO_REASON}" ]]; then
  skip "live session check was not run because the Cursor repository root is invalid"
elif ! command -v "${BIN}" >/dev/null 2>&1; then
  bad "${BIN} is not installed, so the session check cannot run"
elif [[ -z "${BOARD_REVISION}" || -z "${BOARD_PROJECT}" || -z "${BOARD_RESUME}" || -z "${BOARD_WORK}" ]]; then
  bad "the live session has no current board evidence to verify"
else
  # The prompt names no command on purpose. Spelling out `shadow status` would
  # let any generic session pass by following instructions; asking only what
  # the work is means the answer can arrive one way — the skill and standing
  # goal loaded, and the session went to the board on its own. It names neither
  # the command or any value the verifier will accept. It asks for project and
  # work because those are the ordinary human answer this probe actually
  # scores; leaving either implicit made a correct model answer fail by chance.
  PROMPT="As seat ${SEAT}, which project or projects am I working on, and what is the current work? Give one concise answer from the first current scoped status you find, then stop; this read-only activation probe does not need deeper inspection or a routine footer."
  LIVE_OUT="${SCRATCH}/host-final.txt"
  LIVE_LOG="${SCRATCH}/host-diagnostics.txt"
  BOARD_TEXT_FILE="${SCRATCH}/board.txt"
  BOARD_TEXT_ERROR="${SCRATCH}/board-text-status.err"
  BOARD_IN_FLIGHT_FILE="${SCRATCH}/in-flight.json"
  BOARD_IN_FLIGHT_ERROR="${SCRATCH}/in-flight-status.err"
  READ_ONLY_BIN="${SCRATCH}/read-only-bin"
  LIVE_STATUS=0
  BOARD_TEXT_STATUS=0
  BOARD_TEXT_FAILED=0
  (cd "${SCRATCH}" && "${SHADOW_CMD}" status --by "${SEAT}" >"${BOARD_TEXT_FILE}" 2>"${BOARD_TEXT_ERROR}") || BOARD_TEXT_STATUS=$?
  (cd "${SCRATCH}" && "${SHADOW_CMD}" status --in-flight --json >"${BOARD_IN_FLIGHT_FILE}" 2>"${BOARD_IN_FLIGHT_ERROR}") || true
  mkdir "${READ_ONLY_BIN}"
  cat >"${READ_ONLY_BIN}/shadow" <<'SH'
#!/bin/sh
root=$(CDPATH= cd "$(dirname "$0")/.." && pwd)
if [ "${1:-}" != "status" ]; then
  echo "shadow verifier: only read-only status is available in this session" >&2
  exit 2
fi
shift
json=0
in_flight=0
for arg in "$@"; do
  [ "$arg" = "--json" ] && json=1
  [ "$arg" = "--in-flight" ] && in_flight=1
done
if [ "$json" -eq 1 ]; then
  if [ "$in_flight" -eq 1 ] && [ -s "$root/in-flight.json" ]; then
    exec cat "$root/in-flight.json"
  fi
  echo "shadow verifier: full portfolio JSON is unavailable in a cold session; use shadow status --by SEAT" >&2
  exit 2
fi
exec cat "$root/board.txt"
SH
  chmod 700 "${READ_ONLY_BIN}/shadow"
  if grep -q "portfolio refresh failed" "${BOARD_TEXT_ERROR}" || { [[ "${BOARD_TEXT_STATUS}" -ne 0 ]] && [[ ! -s "${BOARD_TEXT_FILE}" ]]; }; then
    BOARD_TEXT_FAILED=1
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
      cursor)
        (cd "${SCRATCH}" && PATH="${READ_ONLY_BIN}:${PATH}" \
          run_bounded "${LIVE_OUT}" "${LIVE_LOG}" \
          "${BIN}" --print --mode ask --workspace "${CURSOR_REPO}" \
          "${PROMPT}") || LIVE_STATUS=$?
        ;;
    esac
  fi
  AFTER_STATUS=0
  AFTER_REFRESH_FAILED=0
  AFTER_ERROR="${SCRATCH}/after-board-status.err"
  AFTER_BOARD="$(cd "${SCRATCH}" && "${SHADOW_CMD}" status --json --by "${SEAT}" 2>"${AFTER_ERROR}")" || AFTER_STATUS=$?
  AFTER_FACTS="$(printf '%s' "${AFTER_BOARD}" | board_facts "${SEAT}" 2>/dev/null || true)"
  if grep -q "portfolio refresh failed" "${AFTER_ERROR}" || { [[ "${AFTER_STATUS}" -ne 0 ]] && [[ -z "${AFTER_BOARD}" ]]; }; then
    AFTER_REFRESH_FAILED=1
  fi
  if [[ "${BOARD_TEXT_FAILED}" -ne 0 ]]; then
    : # The specific failure was already reported without spending host quota.
  elif [[ "${LIVE_STATUS}" -eq 124 ]]; then
    [[ "${LIVE_TIMEOUT}" -eq 1 ]] && TIME_UNIT="second" || TIME_UNIT="seconds"
    bad "the cold ${HOST} session timed out after ${LIVE_TIMEOUT} ${TIME_UNIT} — the result is inconclusive; re-run"
  elif [[ "${LIVE_STATUS}" -ne 0 ]]; then
    bad "the cold ${HOST} session invocation failed"
  elif [[ "${AFTER_REFRESH_FAILED}" -ne 0 || -z "${AFTER_FACTS}" ]]; then
    bad "the board could not be re-observed after the live session"
  elif [[ "${AFTER_FACTS}" != "${BOARD_FACTS}" ]]; then
    bad "the root board changed during the live session — the result is inconclusive; re-run"
  elif python3 - "${LIVE_OUT}" "${BOARD_FACTS}" <<'PY'
import re
from pathlib import Path
import sys

path, facts = sys.argv[1:]
try:
    answer = Path(path).read_text(encoding="utf-8")
except (OSError, UnicodeError):
    raise SystemExit(1)

lines = facts.splitlines()
if len(lines) < 4 or (len(lines) - 1) % 3:
    raise SystemExit(1)
targets = [tuple(lines[index:index + 3]) for index in range(1, len(lines), 3)]

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

def matches(target: tuple[str, str, str]) -> bool:
    project, _resume, work = target
    project_pattern = r"[-_ ]+".join(re.escape(part) for part in project.split("-"))
    project_seen = re.search(
        rf"(?<![A-Za-z0-9_-]){project_pattern}(?![A-Za-z0-9_-])",
        answer,
        re.IGNORECASE,
    )
    expected = stems(work)
    overlap = expected.intersection(stems(answer))
    needed = min(3, len(expected))
    return bool(project_seen and needed and len(overlap) >= needed)

raise SystemExit(0 if any(matches(target) for target in targets) else 1)
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
