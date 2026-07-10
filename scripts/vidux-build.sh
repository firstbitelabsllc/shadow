#!/usr/bin/env bash
# vidux-build.sh — sanity gate before release.
#
# Runs three steps in order:
#   1. npm run docs:build  (vitepress build for docs/)
#   2. npm test            (python contract test suite per package.json)
#   3. npm run release:verify (installable package boundary)
#
# Exits 0 only if all three pass. On failure, prints which step failed and the
# tail of its captured output so the caller doesn't have to re-run to see.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

print_help() {
  cat <<'EOF'
vidux build — run docs, tests, and package verification as a release gate.

usage: vidux build [--help|-h]

Steps (in order; abort on first failure):
  1. npm run docs:build   — vitepress build of docs/
  2. npm test             — python contract test suite
  3. npm run release:verify — inspect the exact npm package candidate

Exits 0 only when all steps pass. On failure, prints which step failed
and the tail of its captured output.

flags:
  --help, -h    Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      print_help
      exit 0
      ;;
    *)
      echo "vidux build: unknown flag: $1" >&2
      print_help >&2
      exit 2
      ;;
  esac
done

cd "${REPO_ROOT}"

# Run one named step. Streams output live AND captures it so we can replay
# the tail on failure without forcing the caller to re-run.
run_step() {
  local label="$1"
  shift
  local log
  log="$(mktemp -t "vidux-build-${label}.XXXXXX")"
  echo "==> ${label}: $*"
  if ! "$@" 2>&1 | tee "${log}"; then
    echo >&2
    echo "vidux build: step '${label}' FAILED" >&2
    echo "----- tail of ${label} output -----" >&2
    tail -n 40 "${log}" >&2
    echo "-----------------------------------" >&2
    rm -f "${log}"
    exit 1
  fi
  rm -f "${log}"
  echo
}

run_step "docs:build" npm run docs:build
run_step "test" npm test
run_step "release:verify" npm run release:verify

echo "vidux build: OK (docs + tests + release package passed)"
