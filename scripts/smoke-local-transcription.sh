#!/usr/bin/env bash
# Smoke test Vidux's local Apple-Silicon transcription dependency.
#
# This proves the exact path used by the Moussey voice-agent plan:
# browser/audio route -> ffmpeg mono 16 kHz WAV -> mlx_whisper -> JSON text.
set -euo pipefail

MODEL="${VIDUX_STT_MODEL:-mlx-community/whisper-base.en-mlx}"
TEXT="${VIDUX_STT_TEXT:-hello local transcription smoke test number four seven two}"
OUT_DIR="${VIDUX_STT_OUT:-${TMPDIR:-/tmp}/vidux-stt-smoke}"
INSTALL=0
AUDIO=""
GENERATED_AUDIO=0

print_help() {
  cat <<EOF
smoke-local-transcription - install/repair mlx-whisper and transcribe a short WAV.

usage:
  scripts/smoke-local-transcription.sh [--install] [--model MODEL] [--audio FILE]

defaults:
  model: $MODEL
  text:  $TEXT
  out:   $OUT_DIR

examples:
  scripts/smoke-local-transcription.sh --install
  VIDUX_STT_MODEL=mlx-community/whisper-base.en-mlx scripts/smoke-local-transcription.sh
  scripts/smoke-local-transcription.sh --audio /path/to/recording.wav

notes:
  First run may download model weights from Hugging Face.
  Warm runs should be fast; the script prints total wall time and audio RTF.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install)
      INSTALL=1
      shift
      ;;
    --model)
      MODEL="${2:-}"
      if [[ -z "$MODEL" ]]; then
        echo "missing value for --model" >&2
        exit 2
      fi
      shift 2
      ;;
    --audio)
      AUDIO="${2:-}"
      if [[ -z "$AUDIO" ]]; then
        echo "missing value for --audio" >&2
        exit 2
      fi
      shift 2
      ;;
    --help|-h)
      print_help
      exit 0
      ;;
    *)
      echo "unknown flag: $1" >&2
      print_help >&2
      exit 2
      ;;
  esac
done

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[FAIL] missing $1" >&2
    return 1
  fi
}

log_stage() {
  printf '[stage] %s\n' "$*"
}

if [[ "$INSTALL" == "1" ]]; then
  log_stage "installing/repairing mlx-whisper with uv tool install --force"
  need_cmd uv
  uv tool install --force mlx-whisper
fi

log_stage "checking local transcription dependencies"
need_cmd ffmpeg
need_cmd ffprobe
need_cmd python3
need_cmd mlx_whisper

mkdir -p "$OUT_DIR"
log_stage "model=${MODEL}; out=${OUT_DIR}"

if [[ -z "$AUDIO" ]]; then
  need_cmd say
  SOURCE_AIFF="$OUT_DIR/source.aiff"
  AUDIO="$OUT_DIR/input.wav"
  GENERATED_AUDIO=1
  log_stage "generating short macOS speech sample with say"
  say -o "$SOURCE_AIFF" "$TEXT"
  log_stage "converting sample to mono 16 kHz WAV with ffmpeg"
  ffmpeg -hide_banner -loglevel error -y -i "$SOURCE_AIFF" -ac 1 -ar 16000 "$AUDIO"
else
  log_stage "using provided audio file: $AUDIO"
fi

if [[ ! -f "$AUDIO" ]]; then
  echo "[FAIL] audio file not found: $AUDIO" >&2
  exit 1
fi

rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.txt

log_stage "measuring WAV duration"
duration="$(ffprobe -v error -show_entries format=duration -of default=nk=1:nw=1 "$AUDIO")"
start="$(python3 -c 'import time; print(time.monotonic())')"
log_stage "transcribing with mlx_whisper; first run may download/load MLX weights"
mlx_whisper "$AUDIO" \
  --model "$MODEL" \
  --output-dir "$OUT_DIR" \
  --output-format json \
  --verbose False
end="$(python3 -c 'import time; print(time.monotonic())')"

json_path="$OUT_DIR/$(basename "${AUDIO%.*}").json"
if [[ ! -f "$json_path" ]]; then
  echo "[FAIL] expected JSON output missing: $json_path" >&2
  exit 1
fi

log_stage "parsing transcript JSON"
elapsed="$(python3 -c 'import sys; print(f"{float(sys.argv[2]) - float(sys.argv[1]):.2f}")' "$start" "$end")"
rtf="$(python3 -c 'import sys; d=float(sys.argv[1]); e=float(sys.argv[2]); print("n/a" if d <= 0 else f"{e / d:.2f}")' "$duration" "$elapsed")"
transcript="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1])).get("text", "").strip())' "$json_path")"

if [[ -z "$transcript" ]]; then
  echo "[FAIL] transcript was empty" >&2
  exit 1
fi

if [[ "$GENERATED_AUDIO" == "1" ]]; then
  transcript_lc="$(printf '%s' "$transcript" | tr '[:upper:]' '[:lower:]')"
  if [[ "$transcript_lc" != *"local"* || "$transcript_lc" != *"transcription"* ]]; then
    echo "[FAIL] generated smoke transcript did not match expected phrase: $transcript" >&2
    exit 1
  fi
fi

printf '[PASS] mlx_whisper transcription\n'
printf 'model=%s\n' "$MODEL"
printf 'audio=%s\n' "$AUDIO"
printf 'duration_s=%.2f\n' "$duration"
printf 'elapsed_s=%s\n' "$elapsed"
printf 'rtf=%s\n' "$rtf"
printf 'transcript=%s\n' "$transcript"
