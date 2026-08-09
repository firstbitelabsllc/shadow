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
#                      shadowing by a higher-priority source, loadable skill
#                      frontmatter, the directive present and current, and the
#                      board actually reachable from an unrelated directory.
#
#   --live             One real non-interactive host invocation. This is the
#                      only thing that proves a SESSION resolves the skill, and
#                      it costs the owner's quota, so it never runs by default.
#
# usage: scripts/shadow-verify-host.sh --host claude-code|codex|cursor [--live]
set -uo pipefail

ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST=""
LIVE=0
FAILURES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="${2:-}"; shift 2 ;;
    --live) LIVE=1; shift ;;
    -h|--help) sed -n '2,22p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "verify-host: unknown argument: $1" >&2; exit 2 ;;
  esac
done

case "${HOST}" in
  claude-code) MOUNT="${HOME}/.claude/skills/shadow"; DIRECTIVE="${HOME}/.claude/CLAUDE.md"; BIN="claude" ;;
  codex)       MOUNT="${HOME}/.agents/skills/shadow"; DIRECTIVE="${HOME}/.codex/AGENTS.md"; BIN="codex" ;;
  cursor)      MOUNT="${HOME}/.cursor/skills/shadow"; DIRECTIVE=""; BIN="cursor-agent" ;;
  *) echo "verify-host: --host must be claude-code, codex, or cursor" >&2; exit 2 ;;
esac

ok()   { printf '  [PASS] %s\n' "$1"; }
bad()  { printf '  [FAIL] %s\n' "$1"; FAILURES=$((FAILURES + 1)); }
skip() { printf '  [SKIP] %s\n' "$1"; }

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
for other in "${HOME}/.claude/skills" "${HOME}/.agents/skills" "${HOME}/.cursor/skills"; do
  candidate="${other}/shadow"
  [[ "${candidate}" == "${MOUNT}" ]] && continue
  if [[ -e "${candidate}" && "$(cd -P "${candidate}" 2>/dev/null && pwd)" != "${ROOT}" ]]; then
    bad "a different 'shadow' skill is mounted in ${other#"${HOME}/"} — one of them is stale"
    SHADOWED=1
  fi
done
[[ "${SHADOWED}" -eq 0 ]] && ok "no competing 'shadow' skill in any host root"

# 3. The skill is loadable, not merely present. A loader that cannot parse the
#    frontmatter drops the skill without saying so.
SKILL="${MOUNT}/SKILL.md"
if [[ ! -f "${SKILL}" ]]; then
  bad "no SKILL.md behind the mount"
elif ! head -1 "${SKILL}" | grep -q '^---$' && ! head -1 "${SKILL}" | grep -q '^# '; then
  bad "SKILL.md opens with neither frontmatter nor a heading — a loader may skip it"
else
  ok "SKILL.md is loadable"
fi

# 4. The standing goal is present and current. `shadow doctor` owns the
#    authoritative comparison; this reports the same fact per host.
if [[ -z "${DIRECTIVE}" ]]; then
  # Cursor user rules live in application settings, not a file. Asserting a
  # path here would invent a convention and then report success for wiring
  # that does nothing.
  skip "no file-backed directive for this host — verify its user rules by hand"
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

# 5. THE POINT. A session's first move is `shadow status` from wherever it
#    opened. If that returns nothing, the host asks "which project?" — the one
#    question this whole milestone exists to make unnecessary.
SCRATCH="$(mktemp -d)"
BOARD="$(cd "${SCRATCH}" && "${ROOT}/bin/shadow" status 2>/dev/null)"
rmdir "${SCRATCH}" 2>/dev/null || true
if [[ -z "${BOARD}" ]]; then
  bad "the board is empty from an unrelated directory — a cold session has nothing to open"
elif ! grep -q 'Resume:' <<<"${BOARD}"; then
  bad "the board names no resume row — a session would have nothing to take"
else
  ok "the board is reachable from an unrelated directory, with a resume row"
fi

# 6. The live tier. Only this proves a SESSION loads the skill; everything
#    above proves the pieces are in place for it to.
if [[ "${LIVE}" -eq 0 ]]; then
  skip "session check (costs model quota) — re-run with --live to prove a cold session resolves the skill"
elif ! command -v "${BIN}" >/dev/null 2>&1; then
  bad "${BIN} is not installed, so the session check cannot run"
else
  # The expected row comes from ${ROOT}/bin/shadow, so the session has to run
  # that same checkout. Bare `shadow` is the realistic command and stays the
  # prompt when PATH already resolves here; when it resolves to another clone,
  # asking for `shadow` would compare two different boards, so name the path.
  resolve_cmd() {
    local p="$1" t
    while [[ -L "${p}" ]]; do
      t="$(readlink "${p}")"
      [[ "${t}" != /* ]] && t="$(dirname "${p}")/${t}"
      p="${t}"
    done
    printf '%s/%s\n' "$(cd -P "$(dirname "${p}")" && pwd)" "$(basename "${p}")"
  }
  ON_PATH="$(command -v shadow 2>/dev/null || true)"
  if [[ -n "${ON_PATH}" ]] && [[ "$(resolve_cmd "${ON_PATH}")" == "$(resolve_cmd "${ROOT}/bin/shadow")" ]]; then
    STATUS_CMD='shadow status'
  else
    STATUS_CMD="${ROOT}/bin/shadow status"
    skip "\`shadow\` on PATH is not this checkout — the session check names the full path instead"
  fi
  PROMPT="Run the shell command \`${STATUS_CMD}\` and reply with ONLY the text after \"Resume:\" on its first occurrence. No preamble."
  case "${HOST}" in
    claude-code) OUT="$("${BIN}" -p "${PROMPT}" 2>&1)" ;;
    codex)       OUT="$("${BIN}" exec "${PROMPT}" 2>&1)" ;;
    cursor)      OUT="$("${BIN}" -p "${PROMPT}" 2>&1)" ;;
  esac
  EXPECTED="$("${ROOT}/bin/shadow" status 2>/dev/null | sed -n 's/^ *Resume: //p' | head -1)"
  if [[ -n "${EXPECTED}" ]] && grep -qF "${EXPECTED:0:40}" <<<"${OUT}"; then
    ok "a cold ${HOST} session reached the board and named the resume row"
  else
    bad "a cold ${HOST} session did not return the resume row — it may not be loading the skill"
  fi
fi

if [[ "${FAILURES}" -gt 0 ]]; then
  echo "verify-host: ${HOST} — ${FAILURES} failure(s)"
  exit 1
fi
echo "verify-host: ${HOST} — wiring verified"
