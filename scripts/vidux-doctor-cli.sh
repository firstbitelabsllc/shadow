#!/usr/bin/env bash
# vidux-doctor-cli — installation + toolchain diagnostics for the `vidux` CLI.
#
# This complements scripts/vidux-doctor.sh (which inspects runtime state across
# plans, automations, browsers, and codex threads). This script checks both
# source checkouts and installable release packages:
#
#   1. python3 >= 3.10
#   2. gh installed + logged in (optional integration; warning when absent)
#   3. ~/.config/vidux/*.token files (if any) are chmod 600
#   4. configured development root exists (warning when absent)
#   5. No stale ${TMPDIR:-/tmp}/vidux-browser.pid pointing to a dead PID
#   6. `vidux config check --json` passes
#   7. `npm test` passes in a source checkout (warning in a packaged install)
#
# Each check prints `[PASS]`, `[WARN]`, or `[FAIL]`. Exit 0 when no hard check
# fails, exit 1 on a hard failure. Pure POSIX bash, stdlib + system tools — no
# extra dependencies beyond system shell, python3, and the repo scripts.
#
set -euo pipefail

VIDUX_ROOT="${VIDUX_ROOT:-$HOME/Development/vidux}"
SKIP_NPM_TEST="${VIDUX_DOCTOR_SKIP_NPM_TEST:-0}"

print_help() {
  cat <<EOF
vidux doctor — install/readiness doctor for the local CLI.

usage: vidux doctor [--help|-h]

This is the terminal user doctor for a checkout/fresh clone. For hook-safe
runtime state checks, use: scripts/vidux-doctor.sh --json

Runs the following checks in order, printing [PASS] / [WARN] / [FAIL]:
  1. python3 >= 3.10
  2. gh installed + authenticated (optional integration)
  3. ~/.config/vidux/*.token files have chmod 600 (if any exist)
  4. configured development root exists
  5. No stale browser pidfile at \${TMPDIR:-/tmp}/vidux-browser.pid
  6. 'vidux config check --json' validates the selected config
  7. 'npm test' passes in source checkouts; packaged installs report a warning

Exit codes:
  0   no hard check failed (optional warnings may remain)
  1   one or more checks failed
  2   invalid usage, such as an unknown flag

environment:
  VIDUX_ROOT                       Override vidux checkout root
                                   (default: \$HOME/Development/vidux)
  VIDUX_DOCTOR_SKIP_NPM_TEST=1     Skip the npm-test gate (check 7);
                                   useful in fast loops because full doctor
                                   can be slow when it runs npm test
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
WARN_COUNT=0
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

_warn() {
  TOTAL=$((TOTAL + 1))
  WARN_COUNT=$((WARN_COUNT + 1))
  printf '[WARN] %s: %s\n' "$1" "$2"
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
    _warn "$name" "optional GitHub integration unavailable; install gh to use PR/release helpers"
    return
  fi
  # gh auth status prints to stderr and exits non-zero when not logged in.
  local out
  if ! out="$(gh auth status 2>&1)"; then
    _warn "$name" "optional GitHub integration is signed out (run: gh auth login)"
    return
  fi
  # Confirm at least one host shows "Logged in" — older gh versions phrase this
  # differently, so accept either "Logged in" or "✓ Logged in".
  if ! printf '%s\n' "$out" | grep -qi "logged in"; then
    _warn "$name" "optional GitHub integration did not report a logged-in account"
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
  local dev_root="${VIDUX_DEV_ROOT:-$HOME/Development}"
  local name="development root exists"
  if [[ ! -d "$dev_root" ]]; then
    _warn "$name" "$dev_root not found (create it or set VIDUX_DEV_ROOT before browsing)"
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
# Check 6: vidux config check
# ----------------------------------------------------------------------------
check_vidux_config() {
  local name="vidux config check"
  if [[ ! -d "$VIDUX_ROOT" ]]; then
    _fail "$name" "VIDUX_ROOT $VIDUX_ROOT does not exist"
    return
  fi
  if [[ ! -f "$VIDUX_ROOT/scripts/vidux-config.py" ]]; then
    _fail "$name" "$VIDUX_ROOT/scripts/vidux-config.py missing"
    return
  fi
  local out rc
  set +e
  out="$(cd "$VIDUX_ROOT" && python3 "$VIDUX_ROOT/scripts/vidux-config.py" check --json 2>&1)"
  rc=$?
  set -e
  if [[ "$rc" -ne 0 ]]; then
    local reason
    reason="$(printf '%s\n' "$out" | python3 -c 'import json,sys
try:
    payload=json.load(sys.stdin)
    issues=payload.get("issues") or []
    if issues:
        first=issues[0]
        code=first.get("code", "error")
        message=first.get("message", "config check failed")
        print(f"{code}: {message}")
    else:
        print(payload.get("status", "config check failed"))
except Exception:
    print("config check failed")
' 2>/dev/null || true)"
    [[ -z "$reason" ]] && reason="config check exited $rc"
    _fail "$name" "$reason"
    return
  fi
  local source live using_example
  source="$(printf '%s\n' "$out" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("source", "unknown"))' 2>/dev/null || true)"
  live="$(printf '%s\n' "$out" | python3 -c 'import json,sys; print("yes" if json.load(sys.stdin).get("live_config_present") else "no")' 2>/dev/null || true)"
  using_example="$(printf '%s\n' "$out" | python3 -c 'import json,sys; print("yes" if json.load(sys.stdin).get("using_example") else "no")' 2>/dev/null || true)"
  [[ -z "$source" ]] && source="unknown"
  [[ -z "$live" ]] && live="unknown"
  [[ -z "$using_example" ]] && using_example="unknown"
  _pass "$name (source=$source live=$live example=$using_example)"
}

# ----------------------------------------------------------------------------
# Check 7: npm test (contract suite)
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
  if [[ ! -d "$VIDUX_ROOT/.git" && ! -f "$VIDUX_ROOT/.git" ]]; then
    _warn "$name" "source-only check unavailable in packaged install; release package verification ran before publish"
    return
  fi
  if [[ ! -d "$VIDUX_ROOT/tests" || ! -d "$VIDUX_ROOT/node_modules" ]]; then
    _fail "$name" "source checkout dependencies missing (run: npm install)"
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
check_vidux_config
check_npm_test

echo ""
if [[ "$WARN_COUNT" -gt 0 ]]; then
  echo "${PASS_COUNT}/${TOTAL} checks passed, ${WARN_COUNT} warning(s)"
else
  echo "${PASS_COUNT}/${TOTAL} checks passed"
fi

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 1
fi
exit 0
