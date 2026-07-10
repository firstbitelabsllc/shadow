#!/usr/bin/env bash
# vidux-init.sh — scaffold a cockpit-ready PLAN.md from the canonical template.
#
set -euo pipefail

VIDUX_ROOT="${VIDUX_ROOT:-$HOME/Development/vidux}"

usage() {
  cat <<'USAGE'
vidux init — bootstrap a new plan.

usage: vidux init <slug>
       vidux init --here
       vidux init --help|-h

With <slug>, creates projects/<slug>/PLAN.md inside the Vidux checkout.
With --here, creates PLAN.md in the current project directory. The slug must
be lowercase letters, digits, and hyphens only (matching ^[a-z0-9-]+$).
Refuses to overwrite an existing PLAN.md.

The template includes plan authority, a starter Operator Brief, an honest
unproven scorecard, and the canonical task/decision/progress sections.

exit codes:
  0   plan created
  1   target PLAN.md already exists
  2   invalid usage (no slug, bad slug, unknown flag)
USAGE
}

# Title-case helper: turn "my-cool-slug" into "My Cool Slug".
slug_to_title() {
  local slug="$1"
  local out=""
  local part
  local IFS='-'
  # shellcheck disable=SC2206
  local parts=( $slug )
  for part in "${parts[@]}"; do
    [[ -z "${part}" ]] && continue
    local head="${part:0:1}"
    local tail="${part:1}"
    out+="$(printf '%s' "${head}" | tr '[:lower:]' '[:upper:]')${tail} "
  done
  # Trim the trailing space.
  printf '%s' "${out% }"
}

emit_template() {
  local title="$1"
  local today="$2"
  cat <<EOF
# ${title}

## Purpose

Keep ${title}'s next work, decisions, and proof resumable across agent sessions.

## Evidence

- [Source: PLAN.md, ${today}] Plan initialized; product evidence is not established yet.

## Constraints

**ALWAYS:**
- Update this plan when the next move or result changes.
- Attach a command result or artifact before marking work complete.

**NEVER:**
- Treat an unverified result as shipped.

## Operator Brief

- Status: watching
- Priority: 50
- Outcome: Ship the first evidence-backed result for ${title}.
- Next: Replace the starter task with the first concrete deliverable.
- Why: This plan is new and its first result is not defined yet.
- Validation: Attach one command result or artifact to the completed task.
- Cost: Keep the first cycle under 30 minutes.
- Evidence: evidence/first-result.md
- Updated: ${today}

## Outcome Scorecard

| Metric | Baseline | Current | Target | Status | Proof |
|---|---|---|---|---|---|
| First evidence-backed result | Not defined | Not started | One completed task with proof | unproven | evidence/first-result.md |

## Tasks

- [pending] T-1: Define and ship the first evidence-backed result [ETA: 0.5h]

## Decision Log

- [DIRECTION] [${today}] Start with one bounded, evidence-backed deliverable. Reason: make the first resume point concrete.

## Progress

- [${today}] Plan initialized with an unproven starter outcome.
EOF
}

main() {
  if [[ $# -eq 0 ]]; then
    echo "vidux init: missing <slug>" >&2
    echo >&2
    usage >&2
    exit 2
  fi

  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    --here)
      if [[ $# -gt 1 ]]; then
        echo "vidux init: --here does not accept additional arguments" >&2
        exit 2
      fi
      ;;
    --*|-*)
      echo "vidux init: unknown flag: $1" >&2
      echo >&2
      usage >&2
      exit 2
      ;;
  esac

  if [[ "$1" != "--here" && $# -gt 1 ]]; then
    echo "vidux init: too many arguments (expected 1 slug, got $#)" >&2
    echo >&2
    usage >&2
    exit 2
  fi

  local slug
  local target_dir
  if [[ "$1" == "--here" ]]; then
    target_dir="$(pwd -P)"
    slug="$(basename "${target_dir}")"
  else
    slug="$1"
    if ! [[ "${slug}" =~ ^[a-z0-9-]+$ ]]; then
      echo "vidux init: invalid slug: ${slug}" >&2
      echo "slug must match ^[a-z0-9-]+\$ (lowercase letters, digits, hyphens)" >&2
      exit 2
    fi
    target_dir="${VIDUX_ROOT}/projects/${slug}"
  fi
  local target_file="${target_dir}/PLAN.md"

  if [[ -e "${target_file}" || -L "${target_file}" ]]; then
    echo "vidux init: ${target_file} already exists — refusing to overwrite" >&2
    exit 1
  fi

  mkdir -p "${target_dir}"

  local title
  title="$(slug_to_title "${slug}")"
  emit_template "${title}" "$(date -u +%F)" > "${target_file}"

  # Print the real absolute path, not a bare "projects/<slug>/PLAN.md" --
  # that reads as relative to $PWD but it's actually relative to VIDUX_ROOT
  # (this vidux checkout), which is the exact confusion a round-3
  # open-source-readiness panel caught: a user running this from their own
  # project directory saw a misleading message and no file where they
  # expected one.
  echo "created ${target_file}"
}

main "$@"
