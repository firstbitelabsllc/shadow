#!/usr/bin/env bash
# Focused health check for Vidux plan/proof/resume changes.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  echo "usage: bash scripts/vidux-thin-loop-verify.sh"
  echo "Runs focused JavaScript, Python, documentation-target, and public-boundary gates."
  exit 0
fi
[[ $# -gt 0 ]] && { echo "Unknown argument: $1" >&2; exit 2; }

npm run test:js

python3 -m unittest \
  tests.test_checkpoint_telemetry \
  tests.test_documented_targets \
  tests.test_plan_guard \
  tests.test_public_ready_grep_gate \
  tests.test_step_journal \
  -q

python3 scripts/vidux-public-ready-grep-gate.py --metadata
test -f guides/thin-token.md

echo "THIN_LOOP_VERIFY_PASS"
