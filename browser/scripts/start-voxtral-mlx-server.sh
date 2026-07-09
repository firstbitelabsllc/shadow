#!/usr/bin/env bash
# Optional, off-by-default local TTS server for vidux-browse read-aloud.
#
# LICENSE NOTE: redseaplume/Voxtral-4B-TTS-2603-MLX's code is MIT, but the
# Voxtral model weights it downloads at run time are Mistral's
# CC-BY-NC-4.0 (non-commercial only) -- not covered by Vidux's own MIT
# grant. Do not run this in a commercial deployment without separately
# licensing the weights, or swap in a TTS backend whose license fits your
# use. See SETUP_NEW_MACHINE.md's Read-Aloud TTS section.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${REPO_ROOT}"

exec uv run \
  --with "git+https://github.com/redseaplume/Voxtral-4B-TTS-2603-MLX.git" \
  "${SCRIPT_DIR}/voxtral_mlx_server.py" "$@"
