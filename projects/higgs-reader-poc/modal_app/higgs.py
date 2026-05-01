"""Higgs Audio V2 Modal endpoint - Phase 0 quality PoC.

Endpoint:  POST /generate  with body {"text": "...", "voice_ref": null, "with_alignment": true}
Returns:   {
              "audio_b64": str,           # base64-encoded WAV, 24kHz mono
              "duration_s": float,
              "sample_rate": int,         # 24000
              "words": [                  # only when with_alignment=true
                {"w": str, "t0": float, "t1": float},
                ...
              ],
           }

Phase 0 constraints (per ../PLAN.md):
- A100 GPU (24GB+ VRAM required for Higgs).
- Higgs weights + whisperx alignment model both cached in a Modal Volume so
  cold starts only pay download once.
- whisperx does FORCED ALIGNMENT (wav2vec2) of the known text against the
  Higgs-generated audio. Higgs is an acoustic-token LLM with no native
  per-word timestamps; whisperx fills that gap.

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
    .pip_install("fastapi[standard]", "whisperx")
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
        import whisperx
        from boson_multimodal.serve.serve_engine import HiggsAudioServeEngine

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.engine = HiggsAudioServeEngine(
            MODEL_PATH, AUDIO_TOKENIZER_PATH, device=self.device
        )
        self.align_model, self.align_metadata = whisperx.load_align_model(
            language_code="en", device=self.device
        )
        hf_volume.commit()

    @modal.method()
    def generate(
        self,
        text: str,
        voice_ref: str | None = None,
        with_alignment: bool = True,
    ) -> dict:
        import base64
        import io
        import tempfile

        import torch
        import torchaudio
        import whisperx
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

        audio_np = output.audio
        sample_rate = int(output.sampling_rate)
        duration_s = float(audio_np.shape[-1]) / float(sample_rate)

        buf = io.BytesIO()
        torchaudio.save(
            buf,
            torch.from_numpy(audio_np)[None, :],
            sample_rate,
            format="wav",
        )
        wav_bytes = buf.getvalue()

        response = {
            "audio_b64": base64.b64encode(wav_bytes).decode("ascii"),
            "duration_s": duration_s,
            "sample_rate": sample_rate,
        }

        if with_alignment:
            with tempfile.NamedTemporaryFile(suffix=".wav") as tf:
                tf.write(wav_bytes)
                tf.flush()
                audio_for_align = whisperx.load_audio(tf.name)

            segments = [{"start": 0.0, "end": duration_s, "text": text}]
            align_result = whisperx.align(
                segments,
                self.align_model,
                self.align_metadata,
                audio_for_align,
                self.device,
                return_char_alignments=False,
            )

            words = []
            for seg in align_result.get("segments", []):
                for w in seg.get("words", []):
                    words.append(
                        {
                            "w": str(w.get("word", "")),
                            "t0": float(w.get("start", 0.0)),
                            "t1": float(w.get("end", 0.0)),
                        }
                    )
            response["words"] = words

        return response


@app.function(timeout=600)
@modal.fastapi_endpoint(method="POST")
def generate(item: dict) -> dict:
    text = (item.get("text") or "").strip()
    if not text:
        return {"error": "text is required"}
    voice_ref = item.get("voice_ref")
    with_alignment = bool(item.get("with_alignment", True))
    return HiggsReader().generate.remote(text, voice_ref, with_alignment)


@app.local_entrypoint()
def smoke_test():
    """Local entrypoint - writes evidence/2026-05-01-smoke-test.{wav,json}."""
    import base64
    import json
    import time
    from pathlib import Path

    text = "Hello from Leo's Higgs PoC. This is the smoke test."
    print(f"[smoke] generating: {text!r}")
    t0 = time.time()
    result = HiggsReader().generate.remote(text, None, True)
    elapsed = time.time() - t0

    wav_bytes = base64.b64decode(result["audio_b64"])
    evidence = Path(__file__).resolve().parent.parent / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)

    wav_path = evidence / "2026-05-01-smoke-test.wav"
    wav_path.write_bytes(wav_bytes)

    json_path = evidence / "2026-05-01-smoke-test.json"
    json_path.write_text(
        json.dumps(
            {
                "text": text,
                "duration_s": result["duration_s"],
                "sample_rate": result["sample_rate"],
                "words": result.get("words", []),
            },
            indent=2,
        )
    )

    n_words = len(result.get("words", []))
    print(
        f"[smoke] wrote {wav_path} "
        f"({result['duration_s']:.2f}s @ {result['sample_rate']}Hz, "
        f"{n_words} aligned words, "
        f"end-to-end {elapsed:.1f}s)"
    )
