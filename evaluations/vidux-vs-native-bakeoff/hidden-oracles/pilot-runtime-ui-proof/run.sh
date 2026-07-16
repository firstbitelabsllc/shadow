#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:?run_cwd required}"
python3 "$(cd "$(dirname "$0")/../.." && pwd)/scripts/pilot_oracle.py" "pilot-runtime-ui-proof" "$ROOT"
