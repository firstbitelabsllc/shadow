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

fail() { echo "install.sh: $*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || fail "git is required"
command -v python3 >/dev/null 2>&1 || fail "python3 is required (3.10+)"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || fail "python3 is older than 3.10"
[[ -f "${ROOT}/bin/shadow" ]] || fail "run this from a Shadow checkout (bin/shadow not found)"

mkdir -p "${BIN_DIR}"
ln -sfn "${ROOT}/bin/shadow" "${BIN_DIR}/shadow"
echo "installed: ${BIN_DIR}/shadow -> ${ROOT}/bin/shadow"

if [[ "${LINK_SKILLS}" -eq 1 ]]; then
  for host in "${HOME}/.claude/skills" "${HOME}/.agents/skills" "${HOME}/.cursor/skills"; do
    if [[ -d "$(dirname "${host}")" ]]; then
      mkdir -p "${host}"
      ln -sfn "${ROOT}" "${host}/shadow"
      echo "mounted:   ${host}/shadow -> ${ROOT}"
    fi
  done
fi

case ":${PATH}:" in
  *":${BIN_DIR}:"*) ;;
  *) echo "note:      ${BIN_DIR} is not on PATH — add it to your shell profile" ;;
esac

echo
echo "next: shadow doctor    (then paste the standing goal from docs/reference/host-integration.md)"
