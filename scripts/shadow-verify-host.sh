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
BOARD="$(cd "${SCRATCH}" && "${SHADOW_CMD}" status 2>/dev/null)"
rmdir "${SCRATCH}" 2>/dev/null || true
if [[ -z "${BOARD}" ]]; then
  bad "the board is empty from an unrelated directory — a cold session has nothing to open"
elif ! grep -q 'Resume:' <<<"${BOARD}"; then
  bad "the board names no resume row — a session would have nothing to take"
else
  ok "the board is reachable from an unrelated directory, with a resume row"
fi

# 7. The live tier. Only this proves a SESSION loads the skill; everything
#    above proves the pieces are in place for it to.
if [[ "${LIVE}" -eq 0 ]]; then
  skip "session check (costs model quota) — re-run with --live to prove a cold session resolves the skill"
elif ! command -v "${BIN}" >/dev/null 2>&1; then
  bad "${BIN} is not installed, so the session check cannot run"
else
  # The prompt names no command on purpose. Spelling out `shadow status` would
  # let any generic session pass by following instructions; asking only what
  # the work is means the answer can arrive one way — the skill and standing
  # goal loaded, and the session went to the board on its own.
  PROMPT='What am I working on right now? Reply with ONLY the single line you would resume, and nothing else.'
  case "${HOST}" in
    claude-code) OUT="$("${BIN}" -p "${PROMPT}" 2>&1)" ;;
    codex)       OUT="$("${BIN}" exec "${PROMPT}" 2>&1)" ;;
    cursor)      OUT="$("${BIN}" -p "${PROMPT}" 2>&1)" ;;
  esac
  EXPECTED="$("${SHADOW_CMD}" status 2>/dev/null | sed -n 's/^ *Resume: //p' | head -1)"
  if [[ -n "${EXPECTED}" ]] && grep -qF "${EXPECTED:0:40}" <<<"${OUT}"; then
    ok "a cold ${HOST} session found the board unprompted and named the resume row"
  else
    bad "a cold ${HOST} session did not name the resume row unprompted — it is not loading the skill"
  fi
fi

if [[ "${FAILURES}" -gt 0 ]]; then
  echo "verify-host: ${HOST} — ${FAILURES} failure(s)"
  exit 1
fi
echo "verify-host: ${HOST} — wiring verified"
