# Voxtral Runtime Research — 2026-05-02

## Finding

Voxtral 4B TTS **can be used locally**. The failed browser attempt was caused by choosing the wrong runtime, not by missing weights.

## Verified sources

### Hugging Face model API

`curl https://huggingface.co/api/models/mistralai/Voxtral-4B-TTS-2603` returned:

```json
{
  "id": "mistralai/Voxtral-4B-TTS-2603",
  "private": false,
  "gated": false,
  "disabled": false,
  "library_name": "vllm",
  "pipeline_tag": "text-to-speech",
  "license": "cc-by-nc-4.0"
}
```

The sibling file list includes:

- `consolidated.safetensors`
- `params.json`
- `tekken.json`
- `voice_embedding/*.pt`

Conclusion: the model is public and ungated. The earlier `config.json` 404 came from trying to load it like a Transformers.js model.

### Hugging Face model card

Model card: `https://huggingface.co/mistralai/Voxtral-4B-TTS-2603`

Key runtime facts:

- Official library: vLLM / vLLM-Omni.
- Command: `vllm serve mistralai/Voxtral-4B-TTS-2603 --omni`
- BF16 weights require a single GPU with >=16GB memory.
- API shape: `POST /v1/audio/speech` with `input`, `model`, `response_format`, and `voice`.
- 20 preset voices, 9 languages.
- License: CC BY-NC 4.0.

### vLLM-Omni

Docs: `https://docs.vllm.ai/projects/vllm-omni/en/latest/user_guide/examples/offline_inference/voxtral_tts/`

Nia/tracer read `vllm-project/vllm-omni/examples/offline_inference/voxtral_tts/end2end.py`:

- Supports streaming and non-streaming inference.
- Streaming yields audio chunks through `stage_output.multimodal_output["audio"]`.
- Writes 24kHz WAV output.

This is the official/prod server route, but it is NVIDIA-oriented.

### Apple Silicon MLX route

Nia/tracer read `redseaplume/Voxtral-4B-TTS-2603-MLX`:

- Runs Mistral Voxtral 4B TTS natively on Apple Silicon via MLX.
- Default weights: 7.5GB.
- 4-bit weights: 3.4GB via `redseaplume/Voxtral-4B-TTS-2603-MLX-4bit`.
- Python API:

```python
from voxtral_mlx import generate

generate(
    "Hello world.",
    voice="cheerful_female",
    output_path="hello.wav",
    model_path="redseaplume/Voxtral-4B-TTS-2603-MLX-4bit",
)
```

Nia/tracer also read `Blaizzy/mlx-audio`:

- `mlx-audio` supports Voxtral TTS through `mlx-community/Voxtral-4B-TTS-2603-mlx-bf16`.
- It documents streaming (`--stream`, `streaming_interval`) and a Python generator API.
- This may become the long-term implementation if we need chunk-level playback instead of one-shot WAV.

## Decision

Ship vidux-browse as:

1. Browser button/client.
2. Loopback local server at `127.0.0.1:8765`.
3. Server uses redseaplume's standalone MLX port + 4-bit weights for first proof.
4. Browser plays returned WAV and applies approximate word highlighting.

Do not use Transformers.js for Voxtral 4B TTS. Do not call it gated/API-only again.
