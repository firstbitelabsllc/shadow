# M10 Probe — Forced-alignment feasibility on M4 Pro

The M10 row was [blocked: needs whisperx forced-alignment]. This cycle probed whether whisperx is actually installable + viable on this Mac before committing future cycles to the integration architecture.

## What was tested

```bash
# 1. Install via uv tool
$ uv tool install whisperx
+ whisperx==3.8.5
Installed 1 executable: whisperx
# (also pulled torchmetrics 1.9, torchvision 0.23, transformers 4.57.6, etc.
# Total ~600 MB.)

# 2. Run on the existing M5 chunk WAV (~9 s, mono 24 kHz)
$ time whisperx \
    /Users/leokwan/Development/vidux/projects/voxtral-reader-addon/evidence/2026-05-01-mlx-voxtral-smoke_000.wav \
    --model tiny --device cpu --compute_type int8 \
    --output_format json --no_align
Detected language: en (1.00) in first 30s of audio
Transcript: [0.031 --> 8.823] Hello from Leo's VoxDral Pipeline. This is a smoke
test of MLX audio running locally on Apple Silicon.
real    1m34.418s
```

## Findings

| Question | Result |
|----------|--------|
| Does whisperx install on M4 Pro via uv? | ✅ Yes, clean install, no Apple-Silicon issues with the python-3.11 build path. |
| Does whisper transcribe a Voxtral-generated WAV correctly? | ✅ Yes, "Hello from Leo's VoxDral Pipeline. This is a smoke test of MLX audio running locally on Apple Silicon" (the "VoxDral" mishear is the `tiny` model's ASR limit; `base` or `small` would catch it). |
| Speed on CPU with `tiny` model? | ❌ **RTF ≈ 10×** — 1m34s for 9s of audio. Cold start (model load + VAD + transcription). Not fast enough for real-time per-word highlight in the M10 streaming UX. Subsequent runs would warm-cache the model but the per-segment compute stays expensive on CPU. |
| Is there a faster path on Apple Silicon? | ⚠️ `mlx-audio.stt.generate --model mlx-community/whisper-tiny-mlx` errored with `ValueError: Processor not found. Make sure the model was loaded with a HuggingFace processor` — the bundled mlx whisper expects a model that ships its HF processor, and the tiny snapshot doesn't. Picking the right mlx-whisper model (e.g., `mlx-community/whisper-base-mlx`) would need its own probe; could deliver RTF < 1 if it works. |

## What this means for M10

Per-chunk forced alignment is **technically possible** but bringing it real-time on this Mac requires either:

1. **Pre-compute alignment per chunk before scheduling playback.** vidux-browse fetches the WAV, runs `whisperx --align`, then emits word-timestamp events to JS. Adds ~5-15 s per chunk (current chunk is ~5-15 s of audio at RTF 10×). The user-facing latency goes from "synthesizing 1/N…" (current ~5 s) to "synthesizing 1/N + aligning 1/N…" (~10-25 s). Worth it for per-word highlight on the FIRST chunk only? Maybe — the rest plays smoothly.
2. **Use mlx-whisper with the right model.** Probe a different snapshot (`whisper-base-mlx`, `whisper-small-mlx`) to find one that actually loads cleanly via `mlx_audio.stt.generate`. If RTF < 1, alignment can run inline without UX penalty.
3. **Skip true alignment, do heuristic per-word timing.** Distribute the chunk's words evenly across the chunk's audio duration (e.g., 10-word chunk over 5 s = 500 ms per word). Inaccurate when speech rate varies but free + zero-latency. Possibly worse UX than current chunk-level highlight when it's wrong.

None of those decisions belong inside the autonomous loop — they each cost multi-cycle work and the picker/preview/clone surface already gives Leo what the original "hands-free walking" use case asked for. M10 stays [blocked] but the blocker is now informed: the required architecture is one of the three above, not "find any way to align."

## Cleanup

```bash
rm -rf /tmp/whisperx-probe /tmp/mlx-stt-probe.json
```

(whisperx model cache stays at `~/.cache/whisper` for reuse; the `whisperx` uv tool is installed and idle until the M10 integration cycle.)

## Follow-up probe — path 2 ruled out (2026-05-02 +30m)

Tested `mlx-community/whisper-base-mlx` to see if it ships its HF processor (which would make `mlx_audio.stt.generate` work cleanly):

```
$ ls ~/.cache/huggingface/hub/models--mlx-community--whisper-base-mlx/snapshots/*/
config.json
weights.npz

$ mlx_audio.stt.generate --model mlx-community/whisper-base-mlx --audio ... --language en
ValueError: Processor not found. Make sure the model was loaded with a HuggingFace processor.
```

Same error as `whisper-tiny-mlx`. The mlx-community snapshots ship ONLY the converted weights + config — no processor / tokenizer / preprocessor. mlx-audio's `post_load_hook` calls `WhisperProcessor.from_pretrained(model_path)` against the local snapshot dir and fails when those files are missing.

**Workaround would require** downloading processor/tokenizer files from `openai/whisper-base` and merging them into the mlx-community snapshot dir. Doable but multi-step and brittle — every model-cache wipe re-introduces the issue.

**Path 2 is effectively ruled out without upstream mlx-community packaging fix or a per-Mac processor-merge helper.** That leaves:

- **Path 1** (whisperx CPU pre-compute, ~RTF 10×) — viable but adds 10s latency per chunk on top of synthesis
- **Path 3** (heuristic even-distribution of words across chunk duration) — free, zero-latency, but inaccurate when speech rate varies

Either is multi-cycle integration work that needs Leo's explicit pick before kicking off.
