"""Higgs Audio V2 Modal endpoint - Phase 0 quality PoC.

Endpoint:  POST /generate  with body {"text": "...", "voice_ref": null}
Returns:   {"audio_b64": "...", "duration_s": float, "sample_rate": int}

Phase 0 constraints (per ../PLAN.md):
- A100 GPU (24GB+ VRAM required for Higgs).
- Apache 2.0 model weights cached in a Modal Volume so cold starts only
  pay the ~6GB download once.
- No whisperx alignment yet - that comes in T4. T2 is plain TTS.

Workflow:
    modal deploy modal_app/higgs.py                     # T3: deploy
    modal run modal_app/higgs.py::smoke_test            # T3: smoke test
    curl -X POST <web-url> -d '{"text": "..."}'         # T3: HTTP path
"""

import modal

APP_NAME = "higgs-reader-poc"
MODEL_PATH = "bosonai/higgs-audio-v2-generation-3B-base"
AUDIO_TOKENIZER_PATH = "bosonai/higgs-audio-v2-tokenizer"
HF_CACHE_DIR = "/root/hf_cache"

image = (
    modal.Image.from_registry("nvcr.io/nvidia/pytorch:25.02-py3", add_python="3.11")
    .apt_install("git", "ffmpeg", "libsndfile1")
    .run_commands(
        "git clone https://github.com/boson-ai/higgs-audio.git /opt/higgs-audio",
        "cd /opt/higgs-audio && pip install -r requirements.txt",
        "cd /opt/higgs-audio && pip install -e .",
    )
    .pip_install("fastapi[standard]")
    .env({"HF_HOME": HF_CACHE_DIR, "HUGGINGFACE_HUB_CACHE": HF_CACHE_DIR})
)

app = modal.App(APP_NAME, image=image)
hf_volume = modal.Volume.from_name("higgs-hf-cache", create_if_missing=True)


@app.cls(
    gpu="A100",
    volumes={HF_CACHE_DIR: hf_volume},
    timeout=600,
)
class HiggsReader:
    @modal.enter()
    def load(self):
        import torch
        from boson_multimodal.serve.serve_engine import HiggsAudioServeEngine

        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.engine = HiggsAudioServeEngine(
            MODEL_PATH, AUDIO_TOKENIZER_PATH, device=device
        )
        hf_volume.commit()

    @modal.method()
    def generate(self, text: str, voice_ref: str | None = None) -> dict:
        import base64
        import io

        import torch
        import torchaudio
        from boson_multimodal.data_types import ChatMLSample, Message
        from boson_multimodal.serve.serve_engine import HiggsAudioResponse

        messages = [Message(role="user", content=text)]
        sample = ChatMLSample(messages=messages)

        output: HiggsAudioResponse = self.engine.generate(
            chat_ml_sample=sample,
            max_new_tokens=1024,
            temperature=0.3,
            top_p=0.95,
            top_k=50,
            stop_strings=["<|end_of_text|>", "<|eot_id|>"],
        )

        buf = io.BytesIO()
        torchaudio.save(
            buf,
            torch.from_numpy(output.audio)[None, :],
            output.sampling_rate,
            format="wav",
        )
        wav_bytes = buf.getvalue()
        duration_s = float(output.audio.shape[-1]) / float(output.sampling_rate)

        return {
            "audio_b64": base64.b64encode(wav_bytes).decode("ascii"),
            "duration_s": duration_s,
            "sample_rate": int(output.sampling_rate),
        }


@app.function(timeout=600)
@modal.fastapi_endpoint(method="POST")
def generate(item: dict) -> dict:
    text = (item.get("text") or "").strip()
    if not text:
        return {"error": "text is required"}
    voice_ref = item.get("voice_ref")
    return HiggsReader().generate.remote(text, voice_ref)


@app.local_entrypoint()
def smoke_test():
    """Local entrypoint - writes evidence/2026-05-01-smoke-test.wav."""
    import base64
    import time
    from pathlib import Path

    text = "Hello from Leo's Higgs PoC. This is the smoke test."
    print(f"[smoke] generating: {text!r}")
    t0 = time.time()
    result = HiggsReader().generate.remote(text)
    elapsed = time.time() - t0

    wav_bytes = base64.b64decode(result["audio_b64"])
    out = Path(__file__).resolve().parent.parent / "evidence" / "2026-05-01-smoke-test.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(wav_bytes)

    print(
        f"[smoke] wrote {out} "
        f"({result['duration_s']:.2f}s audio @ {result['sample_rate']}Hz, "
        f"end-to-end {elapsed:.1f}s)"
    )
