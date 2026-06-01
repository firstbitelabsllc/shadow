#!/usr/bin/env bash
# vidux-release.sh — semver bump + CHANGELOG cut + tag + push.
#
# Default mode is DRY-RUN: prints every mutation it would perform but
# touches nothing. Pass `--apply` to actually run.
#
# Usage:
#   bash scripts/vidux-release.sh [--apply] [--bump <major|minor|patch>] [--allow-dirty]
#                                [--plan-path <PLAN.md>] [--proof <command/artifact>]
#
# Steps in --apply mode:
#   1. Read VERSION, compute NEW_VERSION per --bump (default: patch).
#   2. Write NEW_VERSION to VERSION (preserving any trailing comment lines).
#   3. In CHANGELOG.md, rename `## [Unreleased]` -> `## [NEW_VERSION] - YYYY-MM-DD`
#      and insert a fresh `## [Unreleased]` block above it.
#   4. Append a release Progress note to the owning PLAN.md.
#   5. git add VERSION CHANGELOG.md <PLAN.md>
#   6. git commit -m "release: v<NEW_VERSION>"
#   7. git tag v<NEW_VERSION>
#   8. emit an in-progress publish ledger row with plan/proof/handoff fields
#   9. git push origin main --tags
#   10. emit a final publish ledger row after the push succeeds
#
# Refuses to run if:
#   - git status is not clean (override: --allow-dirty)
#   - current branch is not `main`
#   - --apply is used without --plan-path and --proof
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
PLAN_PATH=""
PROOF=""
HANDOFF_STATUS="done"
LANE="vidux-release"
LEDGER_EMIT="${LEDGER_EMIT:-${HOME}/Development/ai/hooks/ledger-emit.sh}"
PUBLISH_FILES=()
CLAIMS=()
PLAN_PATH_ABS=""
PLAN_PATH_REL=""
PUBLISH_LEDGER_ENABLED=0

usage() {
  cat <<EOF
vidux-release.sh — semver bump + CHANGELOG cut + tag + push.

usage: bash scripts/vidux-release.sh [--apply] [--bump <major|minor|patch>]
                                     [--allow-dirty] [--branch-name <name>]
                                     [--plan-path <PLAN.md>] [--proof <text>]
                                     [--handoff-status <status>] [--lane <name>]
                                     [--file <path>] [--claim <path>]
                                     [--help|-h]

flags:
  --apply              Actually run. Without this, dry-run is the default.
  --bump <part>        Which semver part to bump: major | minor | patch.
                       Defaults to patch.
  --allow-dirty        Skip the clean-working-tree precheck.
  --branch-name <n>    Override the detected branch name (testing aid).
                       Useful for confirming the main-branch guard fires.
  --plan-path <path>   Owning PLAN.md. Required with --apply.
  --proof <text>       Command/artifact proof for this release. Required with
                       --apply.
  --handoff-status <s> Final handoff status: done | in_progress | blocked |
                       needs_review. Defaults to done.
  --lane <name>        Ledger lane. Defaults to vidux-release.
  --file <path>        Extra changed file to include in publish ledger rows.
                       VERSION and CHANGELOG.md are always included.
  --claim <path>       Claim/resume path to include in publish ledger rows.
                       Defaults to the plan and scripts/vidux-release.sh.
  --ledger-emit <path> Ledger emit helper. Defaults to
                       ~/Development/ai/hooks/ledger-emit.sh or LEDGER_EMIT.
  --help, -h           Show this help and exit.

Refuses to run on any branch other than 'main' (override only via
--branch-name for tests, not for real releases). In --apply mode, also
refuses to publish without plan and ledger propagation inputs.
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
    --plan-path)
      if [[ $# -lt 2 ]]; then
        echo "vidux-release: --plan-path requires an argument" >&2
        exit 2
      fi
      PLAN_PATH="$2"; shift 2 ;;
    --plan-path=*)
      PLAN_PATH="${1#--plan-path=}"; shift ;;
    --proof)
      if [[ $# -lt 2 ]]; then
        echo "vidux-release: --proof requires an argument" >&2
        exit 2
      fi
      PROOF="$2"; shift 2 ;;
    --proof=*)
      PROOF="${1#--proof=}"; shift ;;
    --handoff-status)
      if [[ $# -lt 2 ]]; then
        echo "vidux-release: --handoff-status requires an argument" >&2
        exit 2
      fi
      HANDOFF_STATUS="$2"; shift 2 ;;
    --handoff-status=*)
      HANDOFF_STATUS="${1#--handoff-status=}"; shift ;;
    --lane)
      if [[ $# -lt 2 ]]; then
        echo "vidux-release: --lane requires an argument" >&2
        exit 2
      fi
      LANE="$2"; shift 2 ;;
    --lane=*)
      LANE="${1#--lane=}"; shift ;;
    --file)
      if [[ $# -lt 2 ]]; then
        echo "vidux-release: --file requires an argument" >&2
        exit 2
      fi
      PUBLISH_FILES+=("$2"); shift 2 ;;
    --file=*)
      PUBLISH_FILES+=("${1#--file=}"); shift ;;
    --claim)
      if [[ $# -lt 2 ]]; then
        echo "vidux-release: --claim requires an argument" >&2
        exit 2
      fi
      CLAIMS+=("$2"); shift 2 ;;
    --claim=*)
      CLAIMS+=("${1#--claim=}"); shift ;;
    --ledger-emit)
      if [[ $# -lt 2 ]]; then
        echo "vidux-release: --ledger-emit requires an argument" >&2
        exit 2
      fi
      LEDGER_EMIT="$2"; shift 2 ;;
    --ledger-emit=*)
      LEDGER_EMIT="${1#--ledger-emit=}"; shift ;;
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

case "${HANDOFF_STATUS}" in
  done|in_progress|blocked|needs_review) ;;
  *)
    echo "vidux-release: invalid --handoff-status '${HANDOFF_STATUS}' (want done|in_progress|blocked|needs_review)" >&2
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

resolve_repo_path() {
  local path="$1"
  if [[ "${path}" = /* ]]; then
    printf '%s\n' "${path}"
  else
    printf '%s/%s\n' "${VIDUX_ROOT}" "${path}"
  fi
}

configure_publish_gate() {
  if [[ -n "${PLAN_PATH}" ]]; then
    PLAN_PATH_ABS="$(resolve_repo_path "${PLAN_PATH}")"
    PLAN_PATH_REL="${PLAN_PATH_ABS#"${VIDUX_ROOT}/"}"
  fi

  if [[ "${APPLY}" -eq 1 || -n "${PLAN_PATH}" || -n "${PROOF}" ]]; then
    if [[ -z "${PLAN_PATH}" ]]; then
      echo "vidux-release: --apply requires --plan-path <PLAN.md> for publish propagation" >&2
      exit 1
    fi
    if [[ -z "${PROOF}" ]]; then
      echo "vidux-release: --apply requires --proof <command/artifact> for publish propagation" >&2
      exit 1
    fi
    if [[ ! -f "${PLAN_PATH_ABS}" ]]; then
      echo "vidux-release: --plan-path does not exist: ${PLAN_PATH_ABS}" >&2
      exit 1
    fi
    case "${PLAN_PATH_ABS}" in
      "${VIDUX_ROOT}"/*) ;;
      *)
        echo "vidux-release: --plan-path must be inside the Vidux repo: ${PLAN_PATH_ABS}" >&2
        exit 1 ;;
    esac
    if [[ ! -x "${LEDGER_EMIT}" ]]; then
      echo "vidux-release: ledger emit helper is not executable: ${LEDGER_EMIT}" >&2
      exit 1
    fi
    PUBLISH_LEDGER_ENABLED=1
  fi
}

emit_release_publish() {
  local status="$1"
  local phase="$2"
  local summary="Vidux release v${NEW_VERSION} ${phase}"
  local proof_text="release v${NEW_VERSION} ${phase}; ${PROOF}"
  local args=(
    --event publish
    --summary "${summary}"
    --repo-path "${VIDUX_ROOT}"
    --lane "${LANE}"
    --plan-path "${PLAN_PATH_ABS}"
    --proof "${proof_text}"
    --handoff-status "${status}"
    --skills vidux,pilot-leo,ledger
    --file VERSION
    --file CHANGELOG.md
    --file "${PLAN_PATH_REL}"
  )
  if [[ "${#PUBLISH_FILES[@]}" -gt 0 ]]; then
    local publish_file
    for publish_file in "${PUBLISH_FILES[@]}"; do
      args+=(--file "${publish_file}")
    done
  fi

  if [[ "${#CLAIMS[@]}" -eq 0 ]]; then
    args+=(--claim "${PLAN_PATH_ABS}" --claim scripts/vidux-release.sh)
  else
    local claim
    for claim in "${CLAIMS[@]}"; do
      args+=(--claim "${claim}")
    done
  fi

  run "${LEDGER_EMIT}" "${args[@]}"
}

append_plan_progress_note() {
  local safe_proof="${PROOF//$'\n'/ }"
  local note="- [${TODAY}] Release v${NEW_VERSION}: ${safe_proof} [handoff=${HANDOFF_STATUS}]"
  say_step "append release Progress note to ${PLAN_PATH_REL}"
  if [[ "${APPLY}" -eq 1 ]]; then
    tmp_plan="$(mktemp -t vidux-release.plan.XXXXXX)"
    awk -v note="${note}" '
      {
        print
        if (!inserted && $0 ~ /^## Progress[[:space:]]*$/) {
          print ""
          print note
          inserted = 1
        }
      }
      END {
        if (!inserted) {
          print ""
          print "## Progress"
          print ""
          print note
        }
      }
    ' "${PLAN_PATH_ABS}" > "${tmp_plan}"
    mv "${tmp_plan}" "${PLAN_PATH_ABS}"
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

configure_publish_gate

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
printf '  plan path       : %s\n' "${PLAN_PATH_ABS:-<required with --apply>}"
printf '  ledger lane     : %s\n' "${LANE}"
printf '  handoff status  : %s\n' "${HANDOFF_STATUS}"
printf '  mode            : %s\n' "$([[ "${APPLY}" -eq 1 ]] && echo APPLY || echo DRY-RUN)"
if [[ "${PUBLISH_LEDGER_ENABLED}" -eq 0 ]]; then
  printf '  publish ledger  : dry-run only; --apply requires --plan-path and --proof\n'
else
  printf '  publish ledger  : %s\n' "${LEDGER_EMIT}"
fi
printf '\n'

# ---------------------------------------------------------------------------
# Step 1: VERSION file
# ---------------------------------------------------------------------------
say_step "rewrite ${VERSION_FILE#"${VIDUX_ROOT}/"} from '${CURRENT_VERSION}' to '${NEW_VERSION}'"

if [[ "${APPLY}" -eq 1 ]]; then
  # Preserve trailing comment / blank lines after the version line.
  tmp_version="$(mktemp -t vidux-release.version.XXXXXX)"
  trap 'rm -f "${tmp_version:-}" "${tmp_changelog:-}" "${tmp_plan:-}"' EXIT
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
# Step 3: owning PLAN.md Progress note
# ---------------------------------------------------------------------------
if [[ "${PUBLISH_LEDGER_ENABLED}" -eq 1 ]]; then
  append_plan_progress_note
else
  say_step "append release Progress note to the owning PLAN.md (requires --plan-path and --proof in --apply mode)"
fi

# ---------------------------------------------------------------------------
# Step 4-8: git add / commit / tag / push
# ---------------------------------------------------------------------------
if [[ "${PUBLISH_LEDGER_ENABLED}" -eq 1 ]]; then
  run git -C "${VIDUX_ROOT}" add VERSION CHANGELOG.md "${PLAN_PATH_REL}"
else
  run git -C "${VIDUX_ROOT}" add VERSION CHANGELOG.md
fi
run git -C "${VIDUX_ROOT}" commit -m "release: v${NEW_VERSION}"
run git -C "${VIDUX_ROOT}" tag "v${NEW_VERSION}"
if [[ "${PUBLISH_LEDGER_ENABLED}" -eq 1 ]]; then
  emit_release_publish "in_progress" "ready to push origin main --tags"
else
  say_step "emit publish ledger rows before and after push (requires --plan-path and --proof in --apply mode)"
fi
run git -C "${VIDUX_ROOT}" push origin main --tags
if [[ "${PUBLISH_LEDGER_ENABLED}" -eq 1 ]]; then
  emit_release_publish "${HANDOFF_STATUS}" "pushed origin main --tags"
fi

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
