#!/usr/bin/env bash
# vidux-release.sh — semver bump + CHANGELOG cut + tag + push.
#
# Default mode is DRY-RUN: prints every mutation it would perform but
# touches nothing. Pass `--apply` to actually run.
#
# Usage:
#   bash scripts/vidux-release.sh [--apply] [--bump <major|minor|patch>] [--allow-dirty]
#
# Steps in --apply mode:
#   1. Read VERSION, compute NEW_VERSION per --bump (default: patch).
#   2. Write NEW_VERSION to VERSION (preserving any trailing comment lines).
#   3. In CHANGELOG.md, rename `## [Unreleased]` -> `## [NEW_VERSION] - YYYY-MM-DD`
#      and insert a fresh `## [Unreleased]` block above it.
#   4. git add VERSION CHANGELOG.md
#   5. git commit -m "release: v<NEW_VERSION>"
#   6. git tag v<NEW_VERSION>
#   7. git push origin main --tags
#
# Refuses to run if:
#   - git status is not clean (override: --allow-dirty)
#   - current branch is not `main`
#
set -euo pipefail

# ---------------------------------------------------------------------------
# Locate repo root (this script lives in scripts/ inside the repo)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VIDUX_ROOT="${VIDUX_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"

VERSION_FILE="${VIDUX_ROOT}/VERSION"
CHANGELOG_FILE="${VIDUX_ROOT}/CHANGELOG.md"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
APPLY=0
BUMP="patch"
ALLOW_DIRTY=0
BRANCH_OVERRIDE=""

usage() {
  cat <<EOF
vidux-release.sh — semver bump + CHANGELOG cut + tag + push.

usage: bash scripts/vidux-release.sh [--apply] [--bump <major|minor|patch>]
                                     [--allow-dirty] [--branch-name <name>]
                                     [--help|-h]

flags:
  --apply              Actually run. Without this, dry-run is the default.
  --bump <part>        Which semver part to bump: major | minor | patch.
                       Defaults to patch.
  --allow-dirty        Skip the clean-working-tree precheck.
  --branch-name <n>    Override the detected branch name (testing aid).
                       Useful for confirming the main-branch guard fires.
  --help, -h           Show this help and exit.

Refuses to run on any branch other than 'main' (override only via
--branch-name for tests, not for real releases).
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      APPLY=1; shift ;;
    --bump)
      if [[ $# -lt 2 ]]; then
        echo "vidux-release: --bump requires an argument" >&2
        exit 2
      fi
      BUMP="$2"; shift 2 ;;
    --bump=*)
      BUMP="${1#--bump=}"; shift ;;
    --allow-dirty)
      ALLOW_DIRTY=1; shift ;;
    --branch-name)
      if [[ $# -lt 2 ]]; then
        echo "vidux-release: --branch-name requires an argument" >&2
        exit 2
      fi
      BRANCH_OVERRIDE="$2"; shift 2 ;;
    --branch-name=*)
      BRANCH_OVERRIDE="${1#--branch-name=}"; shift ;;
    --help|-h)
      usage; exit 0 ;;
    *)
      echo "vidux-release: unknown flag: $1" >&2
      usage >&2
      exit 2 ;;
  esac
done

case "${BUMP}" in
  major|minor|patch) ;;
  *)
    echo "vidux-release: invalid --bump '${BUMP}' (want major|minor|patch)" >&2
    exit 2 ;;
esac

# ---------------------------------------------------------------------------
# Dry-run runner
# ---------------------------------------------------------------------------
# In --apply mode, runs the command. In dry-run mode, prints what would be
# run. Args are shell-quoted via printf %q so the printed line is copy/paste
# safe.
run() {
  if [[ "${APPLY}" -eq 1 ]]; then
    "$@"
  else
    local rendered=""
    local arg
    for arg in "$@"; do
      # shellcheck disable=SC2059
      rendered+=$(printf ' %q' "${arg}")
    done
    printf '[DRY] would run:%s\n' "${rendered}"
  fi
}

# Logical step describer — used for higher-level "edits" (file rewrites)
# that don't map to a single shell command.
say_step() {
  if [[ "${APPLY}" -eq 1 ]]; then
    printf '[apply] %s\n' "$*"
  else
    printf '[DRY] would do: %s\n' "$*"
  fi
}

# ---------------------------------------------------------------------------
# Precheck: branch + clean tree
# ---------------------------------------------------------------------------
detect_branch() {
  if [[ -n "${BRANCH_OVERRIDE}" ]]; then
    echo "${BRANCH_OVERRIDE}"
    return 0
  fi
  git -C "${VIDUX_ROOT}" rev-parse --abbrev-ref HEAD
}

CURRENT_BRANCH="$(detect_branch)"
if [[ "${CURRENT_BRANCH}" != "main" ]]; then
  echo "vidux-release: refusing to run on branch '${CURRENT_BRANCH}' (need 'main')" >&2
  exit 1
fi

if [[ "${ALLOW_DIRTY}" -eq 0 ]]; then
  if ! git -C "${VIDUX_ROOT}" diff --quiet --ignore-submodules HEAD 2>/dev/null; then
    echo "vidux-release: working tree is dirty — commit or stash, or pass --allow-dirty" >&2
    git -C "${VIDUX_ROOT}" status --short >&2
    exit 1
  fi
  if [[ -n "$(git -C "${VIDUX_ROOT}" ls-files --others --exclude-standard)" ]]; then
    echo "vidux-release: untracked files present — clean them or pass --allow-dirty" >&2
    git -C "${VIDUX_ROOT}" status --short >&2
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Read VERSION + compute NEW_VERSION
# ---------------------------------------------------------------------------
if [[ ! -f "${VERSION_FILE}" ]]; then
  echo "vidux-release: VERSION file not found at ${VERSION_FILE}" >&2
  exit 1
fi

# First non-empty, non-comment line is the version string. Matches the
# parsing used by bin/vidux print_version().
CURRENT_VERSION="$(awk 'NF && $1 !~ /^#/ { print; exit }' "${VERSION_FILE}")"
if [[ -z "${CURRENT_VERSION}" ]]; then
  echo "vidux-release: could not read current version from ${VERSION_FILE}" >&2
  exit 1
fi

if ! [[ "${CURRENT_VERSION}" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
  echo "vidux-release: current version '${CURRENT_VERSION}' is not a semver MAJOR.MINOR.PATCH" >&2
  exit 1
fi

MAJOR="${BASH_REMATCH[1]}"
MINOR="${BASH_REMATCH[2]}"
PATCH="${BASH_REMATCH[3]}"

case "${BUMP}" in
  major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
  minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
  patch) PATCH=$((PATCH + 1)) ;;
esac

NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"
TODAY="$(date -u +%Y-%m-%d)"

# ---------------------------------------------------------------------------
# Pre-flight: confirm CHANGELOG has an [Unreleased] block to cut
# ---------------------------------------------------------------------------
if [[ ! -f "${CHANGELOG_FILE}" ]]; then
  echo "vidux-release: CHANGELOG.md not found at ${CHANGELOG_FILE}" >&2
  exit 1
fi

if ! grep -q '^## \[Unreleased\]' "${CHANGELOG_FILE}"; then
  echo "vidux-release: CHANGELOG.md has no '## [Unreleased]' heading — refusing to cut a release" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Plan summary (always printed)
# ---------------------------------------------------------------------------
printf '\n'
printf 'vidux release plan\n'
printf '  current version : %s\n' "${CURRENT_VERSION}"
printf '  bump            : %s\n' "${BUMP}"
printf '  new version     : %s\n' "${NEW_VERSION}"
printf '  release date    : %s\n' "${TODAY}"
printf '  branch          : %s\n' "${CURRENT_BRANCH}"
printf '  mode            : %s\n' "$([[ "${APPLY}" -eq 1 ]] && echo APPLY || echo DRY-RUN)"
printf '\n'

# ---------------------------------------------------------------------------
# Step 1: VERSION file
# ---------------------------------------------------------------------------
say_step "rewrite ${VERSION_FILE#"${VIDUX_ROOT}/"} from '${CURRENT_VERSION}' to '${NEW_VERSION}'"

if [[ "${APPLY}" -eq 1 ]]; then
  # Preserve trailing comment / blank lines after the version line.
  tmp_version="$(mktemp -t vidux-release.version.XXXXXX)"
  trap 'rm -f "${tmp_version}" "${tmp_changelog:-}"' EXIT
  awk -v new="${NEW_VERSION}" '
    BEGIN { replaced = 0 }
    {
      if (!replaced && NF && $1 !~ /^#/) {
        print new
        replaced = 1
      } else {
        print
      }
    }
  ' "${VERSION_FILE}" > "${tmp_version}"
  mv "${tmp_version}" "${VERSION_FILE}"
fi

# ---------------------------------------------------------------------------
# Step 2: CHANGELOG cut — rename [Unreleased] -> [NEW] - DATE,
#                         insert fresh empty [Unreleased] above it.
# ---------------------------------------------------------------------------
say_step "rewrite CHANGELOG.md — rename '## [Unreleased]' to '## [${NEW_VERSION}] - ${TODAY}' and add a fresh '## [Unreleased]' block above it"

if [[ "${APPLY}" -eq 1 ]]; then
  tmp_changelog="$(mktemp -t vidux-release.changelog.XXXXXX)"
  awk -v new="${NEW_VERSION}" -v today="${TODAY}" '
    BEGIN { replaced = 0 }
    {
      if (!replaced && $0 ~ /^## \[Unreleased\]/) {
        print "## [Unreleased]"
        print ""
        print "### Added"
        print "- _Nothing yet._"
        print ""
        print "---"
        print ""
        print "## [" new "] - " today
        replaced = 1
      } else {
        print
      }
    }
  ' "${CHANGELOG_FILE}" > "${tmp_changelog}"
  mv "${tmp_changelog}" "${CHANGELOG_FILE}"
fi

# ---------------------------------------------------------------------------
# Step 3-6: git add / commit / tag / push
# ---------------------------------------------------------------------------
run git -C "${VIDUX_ROOT}" add VERSION CHANGELOG.md
run git -C "${VIDUX_ROOT}" commit -m "release: v${NEW_VERSION}"
run git -C "${VIDUX_ROOT}" tag "v${NEW_VERSION}"
run git -C "${VIDUX_ROOT}" push origin main --tags

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
printf '\n'
if [[ "${APPLY}" -eq 1 ]]; then
  printf 'vidux-release: applied v%s. Tag pushed to origin.\n' "${NEW_VERSION}"
else
  printf 'vidux-release: dry-run complete. No files written, no git ops performed.\n'
  printf '              Re-run with --apply to actually cut v%s.\n' "${NEW_VERSION}"
fi
