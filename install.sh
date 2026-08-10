#!/usr/bin/env bash
# Shadow installer — Git, Bash, Python. No Node, no npm, no package manager.
#
# Ruled 2026-08-09: Shadow is Python and Bash; a JavaScript package manager
# was never a dependency of the product, only of a docs build and four
# substring tests. Installing is now: clone, link the command, mount the
# skill. Updating is `git pull` — the clone IS the install.
#
#   bash install.sh                 # link into ~/.local/bin + all three hosts
#   bash install.sh --bin-dir DIR   # put the `shadow` command somewhere else
#   bash install.sh --no-skills     # command only, skip the host mounts
#
set -euo pipefail

ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
LINK_SKILLS=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bin-dir) BIN_DIR="$2"; shift 2 ;;
    --no-skills) LINK_SKILLS=0; shift ;;
    -h|--help) sed -n '2,12p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "install.sh: unknown argument: $1" >&2; exit 2 ;;
  esac
done

# A relative --bin-dir names a directory in the install tree, not in whatever
# cwd the installer happened to be invoked from.
case "${BIN_DIR}" in
  /*) ;;
  *) BIN_DIR="${ROOT}/${BIN_DIR}" ;;
esac

fail() { echo "install.sh: $*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || fail "git is required"
# Resolve the same interpreter every installed command uses.  A machine may
# deliberately keep an old bare `python3` for another project while exposing a
# compatible versioned interpreter such as `python3.12` on PATH.
PYTHON="$(SHADOW_PYTHON_COMMAND=install "${ROOT}/scripts/shadow-python.sh" --print)" \
  || fail "a Python 3.10+ interpreter is required"
[[ -f "${ROOT}/bin/shadow" ]] || fail "run this from a Shadow checkout (bin/shadow not found)"

mkdir -p "${BIN_DIR}"
# The same two traps the skill mount guards against, which this line did not.
# `ln -sfn` into an existing real DIRECTORY silently creates
# ${BIN_DIR}/shadow/shadow, prints "installed", exits 0 — and running `shadow`
# then gives "permission denied".
if [[ -d "${BIN_DIR}/shadow" && ! -L "${BIN_DIR}/shadow" ]]; then
  fail "${BIN_DIR}/shadow is a directory, not a command — move or delete it, then re-run"
fi
# And a real file here belongs to something else. Replacing another tool's
# binary without a word is not an install, it is a theft.
if [[ -e "${BIN_DIR}/shadow" && ! -L "${BIN_DIR}/shadow" ]]; then
  fail "${BIN_DIR}/shadow already exists and is not a symlink — another tool may own it.
           Move it aside, or choose a different --bin-dir."
fi
ln -sfn "${ROOT}/bin/shadow" "${BIN_DIR}/shadow"
echo "installed: ${BIN_DIR}/shadow -> ${ROOT}/bin/shadow"

if [[ "${LINK_SKILLS}" -eq 1 ]]; then
  for host in "${HOME}/.claude/skills" "${HOME}/.agents/skills" "${HOME}/.cursor/skills"; do
    if [[ -d "$(dirname "${host}")" ]]; then
      mkdir -p "${host}"
      # `ln -sfn` into an existing REAL directory silently creates
      # ${host}/shadow/shadow and leaves the stale mount loaded, so an old
      # copied-in skill would keep serving while the installer claimed success.
      if [[ -d "${host}/shadow" && ! -L "${host}/shadow" ]]; then
        echo "skipped:   ${host}/shadow is a real directory, not a mount — move or delete it," >&2
        echo "           then re-run: rm -rf '${host}/shadow' && bash install.sh" >&2
        continue
      fi
      ln -sfn "${ROOT}" "${host}/shadow"
      echo "mounted:   ${host}/shadow -> ${ROOT}"
    fi
  done
fi

if [[ "${LINK_SKILLS}" -eq 1 ]]; then
  # The standing goal is what makes a cold host open the board instead of
  # asking "which project?". Pasting it by hand was the step everyone skipped:
  # adoption on the reference machine was 0 of 3 hosts and nothing noticed.
  # This owns only its own marker-delimited block — the rest of the file is
  # untouched, an unmarked copy is adopted rather than duplicated, and
  # `shadow goal --remove` takes it back out.
  "${PYTHON}" "${ROOT}/scripts/shadow-host-directives.py" \
    || echo "note:      some hosts did not take the standing goal — see the failed: lines above; fix and run: shadow goal --install" >&2
fi

case ":${PATH}:" in
  *":${BIN_DIR}:"*) ;;
  *) echo "note:      ${BIN_DIR} is not on PATH — add it to your shell profile" ;;
esac

echo
printf 'next: PATH=%q:$PATH shadow doctor\n' "${BIN_DIR}"
