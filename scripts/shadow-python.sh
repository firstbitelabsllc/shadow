#!/usr/bin/env bash
set -euo pipefail

# Resolve the Python floor once for the CLI, direct browser launcher, and npm
# gates. A machine may keep a project-incompatible bare `python3` while a
# versioned Python 3.10+ interpreter is available on the same PATH.
python3_satisfies_floor() {
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
}

resolve_python() {
  local command_name="${SHADOW_PYTHON_COMMAND:-python}"
  if [[ -n "${SHADOW_PYTHON:-}" ]]; then
    if python3_satisfies_floor "${SHADOW_PYTHON}"; then
      printf '%s\n' "${SHADOW_PYTHON}"
      return 0
    fi
    echo "shadow ${command_name}: SHADOW_PYTHON (${SHADOW_PYTHON}) is not a Python 3.10+ interpreter." >&2
    echo "  Unset it or point it at one, then re-run." >&2
    return 127
  fi

  local candidate minor
  # Probe the known floor names directly. `compgen -c` hashes every command on
  # PATH, which is the slow path on a machine whose bare python3 is below 3.10
  # and whose shims make that hash large. Fall through only if none of these
  # names is a usable interpreter, so a newer minor still resolves.
  for minor in 14 13 12 11 10; do
    candidate="python3.${minor}"
    if command -v "${candidate}" >/dev/null 2>&1 && python3_satisfies_floor "${candidate}"; then
      command -v "${candidate}"
      return 0
    fi
  done
  for candidate in $(compgen -c python3. | grep -E '^python3\.[0-9]+$' | sort -t. -k2,2nr -u) python3; do
    if command -v "${candidate}" >/dev/null 2>&1 && python3_satisfies_floor "${candidate}"; then
      command -v "${candidate}"
      return 0
    fi
  done

  if command -v python3 >/dev/null 2>&1; then
    echo "shadow ${command_name}: python3 on PATH is $(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null || echo 'unreadable'); this subcommand requires Python 3.10+." >&2
    echo "  Install a newer interpreter (kept alongside the existing one is fine) and re-run." >&2
  else
    echo "shadow ${command_name}: python3 not found on PATH." >&2
    echo "  This subcommand requires Python 3.10+. Install it, then re-run." >&2
  fi
  echo "  'shadow doctor' runs a full readiness check once python3 is installed." >&2
  return 127
}

if [[ "${1:-}" == "--print" ]]; then
  shift
  if (($#)); then
    echo "shadow python: --print does not accept command arguments." >&2
    exit 2
  fi
  resolve_python
  exit $?
fi

interpreter="$(resolve_python)"
exec "${interpreter}" "$@"
