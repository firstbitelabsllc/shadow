#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:?run_cwd required}"
python3 "$(cd "$(dirname "$0")/../.." && pwd)/scripts/fixture_oracle.py" "full-cold-resume-dirty-03" "$ROOT"
