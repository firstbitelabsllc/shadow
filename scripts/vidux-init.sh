#!/usr/bin/env bash
# vidux-init.sh — scaffold a new plan's projects/<slug>/PLAN.md from
# the canonical template (Purpose / Evidence / Constraints / Tasks /
# Decision Log / Progress).
#
set -euo pipefail

VIDUX_ROOT="${VIDUX_ROOT:-$HOME/Development/vidux}"

usage() {
  cat <<'USAGE'
vidux init — bootstrap a new plan.

usage: vidux init <slug>
       vidux init --help|-h

Creates projects/<slug>/PLAN.md from the canonical template. The slug
must be lowercase letters, digits, and hyphens only (matching
^[a-z0-9-]+$). Refuses to overwrite an existing PLAN.md.

The template ships with the six canonical sections:
  Purpose · Evidence · Constraints · Tasks · Decision Log · Progress

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
  cat <<EOF
# ${title}

## Purpose

<one-paragraph purpose of this plan>

## Evidence

- [Source: <where>] <what you learned>

## Constraints

**ALWAYS:**
- <invariant 1>

**NEVER:**
- <anti-pattern 1>

## Tasks

- [pending] T-1: <first task> [ETA: 0.5h]

## Decision Log

- [DIRECTION] [<YYYY-MM-DD>] <decision>. Reason: <why>.

## Progress

- [<YYYY-MM-DD>] Plan opened.
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
    --*|-*)
      echo "vidux init: unknown flag: $1" >&2
      echo >&2
      usage >&2
      exit 2
      ;;
  esac

  if [[ $# -gt 1 ]]; then
    echo "vidux init: too many arguments (expected 1 slug, got $#)" >&2
    echo >&2
    usage >&2
    exit 2
  fi

  local slug="$1"

  if ! [[ "${slug}" =~ ^[a-z0-9-]+$ ]]; then
    echo "vidux init: invalid slug: ${slug}" >&2
    echo "slug must match ^[a-z0-9-]+\$ (lowercase letters, digits, hyphens)" >&2
    exit 2
  fi

  local target_dir="${VIDUX_ROOT}/projects/${slug}"
  local target_file="${target_dir}/PLAN.md"

  if [[ -e "${target_file}" ]]; then
    echo "vidux init: projects/${slug}/PLAN.md already exists — refusing to overwrite" >&2
    exit 1
  fi

  mkdir -p "${target_dir}"

  local title
  title="$(slug_to_title "${slug}")"
  emit_template "${title}" > "${target_file}"

  echo "created projects/${slug}/PLAN.md"
}

main "$@"
