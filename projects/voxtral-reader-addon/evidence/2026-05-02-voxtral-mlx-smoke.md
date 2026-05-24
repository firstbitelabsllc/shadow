# Voxtral MLX Smoke — 2026-05-02

## Command

Started the local MLX server:

```bash
browser/scripts/start-voxtral-mlx-server.sh
```

Then generated a short smoke sample:

```bash
curl -sS -X POST http://127.0.0.1:8765/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"input":"Hello from vidux. Voxtral is running locally on Apple Silicon through MLX. This is a short smoke test for the read aloud button.","voice":"cheerful_female","response_format":"wav"}' \
  --output projects/voxtral-reader-addon/evidence/2026-05-02-voxtral-mlx-smoke.wav
```

## Result

- Output: `evidence/2026-05-02-voxtral-mlx-smoke.wav`
- Format: WAVE, 1 channel, 24000 Hz, Int16
- Duration: 13.84s
- Size: 649KB
- Voice: `cheerful_female`
- Server health after synthesis: `{"ok": true, "engine": "voxtral-mlx", "loaded": true}`

## Server Log Excerpt

```text
First run downloaded redseaplume/Voxtral-4B-TTS-2603-MLX-4bit from HuggingFace Hub.
Download complete: 3.71GB in 43s.
Voxtral MLX model loaded.
Prompt: 167 tokens.
Generated 173 frames.
Per-frame avg: backbone 8.0ms, acoustic 38.0ms, total 46.1ms.
Done: 173 frames, 13.84s audio, 10.7s total (prompt 0.7s, generation 8.0s, vocoder 0.5s).
generated 13.84s audio in 10708ms voice=cheerful_female
POST /v1/audio/speech HTTP/1.1 200
```

## Verdict

Runtime is proven on this Mac: local Voxtral MLX can synthesize and return WAV audio with no Modal, no cloud API, and no browser WebGPU dependency.

Quality verdict is still pending Leo's ears.
