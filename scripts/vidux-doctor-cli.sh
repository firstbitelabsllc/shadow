#!/usr/bin/env bash
# vidux-doctor-cli — installation + toolchain diagnostics for the `vidux` CLI.
#
# This complements scripts/vidux-doctor.sh (which inspects runtime state across
# plans, automations, browsers, and codex threads). This script checks the
# subset a fresh `git clone` user needs to know works:
#
#   1. python3 >= 3.10
#   2. gh installed + logged in (gh auth status)
#   3. ~/.config/vidux/*.token files (if any) are chmod 600
#   4. $HOME/Development directory exists
#   5. No stale ${TMPDIR:-/tmp}/vidux-browser.pid pointing to a dead PID
#   6. `npm test` passes (contract bundle count is reported dynamically)
#
# Each check prints `[PASS] <name>` or `[FAIL] <name>: <reason>`. Exit 0 if all
# pass, exit 1 if any fail. Pure POSIX bash, stdlib + system tools only — no
# python startup tax beyond optional version probing.
#
set -euo pipefail

VIDUX_ROOT="${VIDUX_ROOT:-$HOME/Development/vidux}"
SKIP_NPM_TEST="${VIDUX_DOCTOR_SKIP_NPM_TEST:-0}"

print_help() {
  cat <<EOF
vidux doctor — diagnose local toolchain + auth.

usage: vidux doctor [--help|-h]

Runs the following checks in order, printing [PASS] / [FAIL] for each:
  1. python3 >= 3.10
  2. gh installed + 'gh auth status' shows logged in
  3. ~/.config/vidux/*.token files have chmod 600 (if any exist)
  4. \$HOME/Development directory exists
  5. No stale browser pidfile at \${TMPDIR:-/tmp}/vidux-browser.pid
  6. 'npm test' passes (contract suite — 182 tests)

Exit codes:
  0   all checks pass
  1   one or more checks failed

environment:
  VIDUX_ROOT                       Override vidux checkout root
                                   (default: \$HOME/Development/vidux)
  VIDUX_DOCTOR_SKIP_NPM_TEST=1     Skip the npm-test gate (check 6)
                                   useful when the dev loop already runs it
EOF
}

# Parse flags. The doctor takes no positional args.
while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      print_help
      exit 0 ;;
    *)
      echo "vidux doctor: unknown flag: $1" >&2
      print_help >&2
      exit 2 ;;
  esac
done

PASS_COUNT=0
FAIL_COUNT=0
TOTAL=0

_pass() {
  TOTAL=$((TOTAL + 1))
  PASS_COUNT=$((PASS_COUNT + 1))
  printf '[PASS] %s\n' "$1"
}

_fail() {
  TOTAL=$((TOTAL + 1))
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf '[FAIL] %s: %s\n' "$1" "$2"
}

# ----------------------------------------------------------------------------
# Check 1: python3 >= 3.10
# ----------------------------------------------------------------------------
check_python_version() {
  local name="python3 >= 3.10"
  if ! command -v python3 >/dev/null 2>&1; then
    _fail "$name" "python3 not found on PATH"
    return
  fi
  local raw major minor
  if ! raw="$(python3 --version 2>&1)"; then
    _fail "$name" "python3 --version exited non-zero"
    return
  fi
  # Expected format: "Python 3.X.Y" — extract X and Y
  local ver
  ver="${raw#Python }"
  major="${ver%%.*}"
  local rest="${ver#*.}"
  minor="${rest%%.*}"
  if ! [[ "$major" =~ ^[0-9]+$ ]] || ! [[ "$minor" =~ ^[0-9]+$ ]]; then
    _fail "$name" "could not parse version string: $raw"
    return
  fi
  if [[ "$major" -lt 3 ]] || { [[ "$major" -eq 3 ]] && [[ "$minor" -lt 10 ]]; }; then
    _fail "$name" "found python $major.$minor, need >= 3.10"
    return
  fi
  _pass "$name (found python $major.$minor)"
}

# ----------------------------------------------------------------------------
# Check 2: gh installed + authenticated
# ----------------------------------------------------------------------------
check_gh_auth() {
  local name="gh authenticated"
  if ! command -v gh >/dev/null 2>&1; then
    _fail "$name" "gh not found on PATH (install: brew install gh)"
    return
  fi
  # gh auth status prints to stderr and exits non-zero when not logged in.
  local out
  if ! out="$(gh auth status 2>&1)"; then
    _fail "$name" "gh auth status failed (run: gh auth login)"
    return
  fi
  # Confirm at least one host shows "Logged in" — older gh versions phrase this
  # differently, so accept either "Logged in" or "✓ Logged in".
  if ! printf '%s\n' "$out" | grep -qi "logged in"; then
    _fail "$name" "gh auth status output did not include 'Logged in'"
    return
  fi
  _pass "$name"
}

# ----------------------------------------------------------------------------
# Check 3: token files chmod 600
# ----------------------------------------------------------------------------
check_token_perms() {
  # shellcheck disable=SC2088 # display text, not a path expansion
  local name="~/.config/vidux/*.token chmod 600"
  local dir="$HOME/.config/vidux"
  if [[ ! -d "$dir" ]]; then
    _pass "$name (no $dir directory; nothing to check)"
    return
  fi
  # Use a glob with nullglob behavior via shopt — fall back if directory
  # has no .token files.
  shopt -s nullglob
  local tokens=( "$dir"/*.token )
  shopt -u nullglob
  if [[ ${#tokens[@]} -eq 0 ]]; then
    _pass "$name (no .token files found)"
    return
  fi
  local bad=()
  local f mode
  for f in "${tokens[@]}"; do
    # Portable stat: macOS uses -f, Linux uses -c. Try macOS form first.
    if mode="$(stat -f '%Lp' "$f" 2>/dev/null)"; then
      :
    elif mode="$(stat -c '%a' "$f" 2>/dev/null)"; then
      :
    else
      bad+=("$(basename "$f"):stat-failed")
      continue
    fi
    if [[ "$mode" != "600" ]]; then
      bad+=("$(basename "$f"):$mode")
    fi
  done
  if [[ ${#bad[@]} -gt 0 ]]; then
    _fail "$name" "non-600 perms: ${bad[*]} (fix: chmod 600 $dir/*.token)"
    return
  fi
  _pass "$name (${#tokens[@]} token file(s) verified)"
}

# ----------------------------------------------------------------------------
# Check 4: $HOME/Development exists
# ----------------------------------------------------------------------------
check_development_dir() {
  local name="\$HOME/Development exists"
  if [[ ! -d "$HOME/Development" ]]; then
    _fail "$name" "$HOME/Development not found (mkdir -p ~/Development)"
    return
  fi
  _pass "$name"
}

# ----------------------------------------------------------------------------
# Check 5: stale browser pidfile
# ----------------------------------------------------------------------------
check_stale_browser_pidfile() {
  local name="no stale browser pidfile"
  # macOS TMPDIR has a trailing slash; strip it before joining the basename
  # so the resulting path is clean (e.g. /var/.../T/vidux-browser.pid).
  local tmp="${TMPDIR:-/tmp}"
  tmp="${tmp%/}"
  local pidfile="${tmp}/vidux-browser.pid"
  if [[ ! -f "$pidfile" ]]; then
    _pass "$name (no pidfile at $pidfile)"
    return
  fi
  local pid
  pid="$(tr -d '[:space:]' < "$pidfile" 2>/dev/null || true)"
  if [[ -z "$pid" ]]; then
    _fail "$name" "pidfile $pidfile is empty (rm $pidfile)"
    return
  fi
  if ! [[ "$pid" =~ ^[0-9]+$ ]]; then
    _fail "$name" "pidfile $pidfile contains non-numeric content (rm $pidfile)"
    return
  fi
  # `kill -0` returns 0 if the process exists and the caller may signal it.
  # On macOS / Linux it also returns 0 for processes we cannot signal but
  # which exist, so a true 0 is "alive enough".
  if kill -0 "$pid" 2>/dev/null; then
    _pass "$name (pid $pid alive)"
    return
  fi
  _fail "$name" "pidfile $pidfile points to dead pid $pid (rm $pidfile)"
}

# ----------------------------------------------------------------------------
# Check 6: npm test (contract suite)
# ----------------------------------------------------------------------------
check_npm_test() {
  local name="npm test (contract suite)"
  if [[ "$SKIP_NPM_TEST" = "1" ]]; then
    _pass "$name (skipped via VIDUX_DOCTOR_SKIP_NPM_TEST=1)"
    return
  fi
  if [[ ! -d "$VIDUX_ROOT" ]]; then
    _fail "$name" "VIDUX_ROOT $VIDUX_ROOT does not exist"
    return
  fi
  if [[ ! -f "$VIDUX_ROOT/package.json" ]]; then
    _fail "$name" "$VIDUX_ROOT/package.json missing"
    return
  fi
  if ! command -v npm >/dev/null 2>&1; then
    _fail "$name" "npm not found on PATH"
    return
  fi
  local out rc
  # Capture output and exit code; on success show test count, on failure
  # surface the first failing line.
  set +e
  out="$(cd "$VIDUX_ROOT" && npm test 2>&1)"
  rc=$?
  set -e
  if [[ "$rc" -ne 0 ]]; then
    local first_fail
    first_fail="$(printf '%s\n' "$out" | grep -E '^(FAIL|ERROR|FAILED)' | head -1 || true)"
    [[ -z "$first_fail" ]] && first_fail="exit code $rc"
    _fail "$name" "$first_fail"
    return
  fi
  # Look for the unittest summary like "Ran 182 tests in" to surface the count.
  local count
  count="$(printf '%s\n' "$out" | grep -oE 'Ran [0-9]+ tests' | tail -1 || true)"
  if [[ -n "$count" ]]; then
    _pass "$name ($count)"
  else
    _pass "$name"
  fi
}

# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
check_python_version
check_gh_auth
check_token_perms
check_development_dir
check_stale_browser_pidfile
check_npm_test

echo ""
echo "${PASS_COUNT}/${TOTAL} checks passed"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 1
fi
exit 0
