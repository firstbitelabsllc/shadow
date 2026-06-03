# V1 Local STT Install + Smoke

Date: 2026-05-24
Host: `Leos-Mac-Studio-10442.local`
Arch: `arm64`
Repo: `/Users/leokwan/.codex/worktrees/d4e3/vidux`

## What changed on this Mac

- `uv` already existed at `/Users/leokwan/.local/bin/uv`.
- `ffmpeg` already existed at `/opt/homebrew/bin/ffmpeg`.
- `mlx-whisper` was missing before this run.
- Installed with `uv tool install mlx-whisper`.
- Installed executable is `/Users/leokwan/.local/bin/mlx_whisper`.

`uv tool list` now includes:

```text
mlx-whisper v0.4.3
- mlx_whisper
```

## Model-name correction

The plan's original `mlx-community/whisper-base.en` model name failed:

```text
Repository Not Found for url: https://huggingface.co/api/models/mlx-community/whisper-base.en/revision/main
```

The public MLX model names include the `-mlx` suffix. The default used here is:

```text
mlx-community/whisper-base.en-mlx
```

Low-disk fallback:

```text
mlx-community/whisper-base.en-mlx-q4
```

## Smoke input

Generated a local spoken fixture with macOS `say`, then converted it with
ffmpeg to mono 16 kHz WAV:

```text
hello local transcription smoke test number four seven two
```

## Warm smoke result

Command:

```bash
scripts/smoke-local-transcription.sh
```

Result:

```text
[PASS] mlx_whisper transcription
model=mlx-community/whisper-base.en-mlx
duration_s=3.35
elapsed_s=2.11
rtf=0.63
transcript=Hello local transcription smoke test number 472
```

Canonical rerun after mirroring the setup script:

```text
[PASS] mlx_whisper transcription
model=mlx-community/whisper-base.en-mlx
duration_s=3.35
elapsed_s=3.31
rtf=0.99
transcript=Hello local transcription smoke test number 472
```

Manual timing on the same local path showed warm inference itself much faster
than real time; most visible delay is CLI startup/model load, not decoding.
Repeat warm subprocess runs varied from 2.11s to 3.85s total for this 3.35s
fixture on the Studio. That is acceptable for proving install + local STT, but
strict sub-2s UX should keep the model warm in a persistent worker rather than
spawn `mlx_whisper` for each request.

## Cache + RAM notes

```text
models--mlx-community--whisper-base.en-mlx     146M
models--mlx-community--whisper-base.en-mlx-q4   77M
```

Measured warm-process memory during manual runs:

- `whisper-base.en-mlx`: about 491 MB max resident set; about 847 MB peak memory footprint.
- `whisper-base.en-mlx-q4`: about 426 MB max resident set; about 782 MB peak memory footprint.

Disk is tight on this Studio:

```text
/dev/disk3s5   926Gi   845Gi    11Gi    99%   /System/Volumes/Data
```

This is enough for the Whisper path but too tight for casual large-model TTS
downloads. Keep the 20 GB preflight for Voxtral.

## Negative path checked

`mlx_audio.stt.generate --stream` is not a drop-in replacement for this STT
path. With the cached `mlx-community/whisper-base.en-mlx-q4` model it failed
with:

```text
ValueError: Processor not found. Make sure the model was loaded with a HuggingFace processor.
```

Use `mlx_whisper` for the current voice-agent transcription contract.

## UX implication

The per-request CLI writes a complete transcript after the clip is decoded. It
does not emit partial text for a short clip. The UI should make buffering states
visible: recording, converting, first-run model download/load, transcribing, and
transcript ready. If partial transcripts become a hard requirement, move to a
persistent STT worker or a streaming runtime rather than spawning the CLI.
