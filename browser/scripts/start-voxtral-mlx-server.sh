#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${REPO_ROOT}"

exec uv run \
  --with "git+https://github.com/redseaplume/Voxtral-4B-TTS-2603-MLX.git" \
  "${SCRIPT_DIR}/voxtral_mlx_server.py" "$@"
