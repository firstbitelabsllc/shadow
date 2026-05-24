#!/usr/bin/env python3
"""Local Voxtral MLX TTS server for vidux-browse.

This intentionally mirrors the OpenAI/vLLM `/v1/audio/speech` shape so the
browser add-on can swap between local MLX and a future hosted endpoint without
rewriting the UI.
"""

from __future__ import annotations

import argparse
import json
import logging
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "redseaplume/Voxtral-4B-TTS-2603-MLX-4bit"
DEFAULT_VOICE = "cheerful_female"
VOICES = [
    "neutral_male",
    "neutral_female",
    "casual_male",
    "casual_female",
    "cheerful_female",
    "es_male",
    "es_female",
    "fr_male",
    "fr_female",
    "de_male",
    "de_female",
    "it_male",
    "it_female",
    "pt_male",
    "pt_female",
    "nl_male",
    "nl_female",
    "ar_male",
    "hi_male",
    "hi_female",
]
CAPABILITIES = {
    "engine": "voxtral-mlx",
    "supports_preset_voices": True,
    "supports_reference_audio": False,
    "supports_word_timestamps": False,
    "supports_streaming": False,
}

log = logging.getLogger("vidux.voxtral")


class State:
    def __init__(self, model_path: str, default_voice: str) -> None:
        self.model_path = model_path
        self.default_voice = default_voice
        self.models: Any | None = None

    def load(self) -> Any:
        if self.models is None:
            from voxtral_mlx import load_all_models

            log.info("loading Voxtral MLX model: %s", self.model_path)
            self.models = load_all_models(self.model_path)
            log.info("Voxtral MLX model loaded")
        return self.models


class Handler(BaseHTTPRequestHandler):
    server_version = "ViduxVoxtralMLX/0.1"

    @property
    def state(self) -> State:
        return self.server.state  # type: ignore[attr-defined]

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            return self.write_json(
                {
                    "ok": True,
                    "engine": "voxtral-mlx",
                    "model": self.state.model_path,
                    "loaded": self.state.models is not None,
                    "voices": VOICES,
                    "capabilities": CAPABILITIES,
                }
            )
        if self.path == "/v1/audio/voices":
            return self.write_json({"voices": VOICES})
        if self.path == "/v1/audio/capabilities":
            return self.write_json({"voices": VOICES, "capabilities": CAPABILITIES})
        self.send_error(HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/audio/speech":
            self.send_error(HTTPStatus.NOT_FOUND, "not found")
            return

        try:
            payload = self.read_json()
            text = str(payload.get("input") or payload.get("text") or "").strip()
            if not text:
                raise ValueError("missing input")
            voice = str(payload.get("voice") or self.state.default_voice)
            if voice not in VOICES:
                raise ValueError(f"unknown voice {voice!r}")

            with tempfile.TemporaryDirectory(prefix="vidux-voxtral-") as tmp:
                wav_path = Path(tmp) / "speech.wav"
                from voxtral_mlx import generate

                result = generate(
                    text=text,
                    voice=voice,
                    output_path=str(wav_path),
                    model_path=self.state.model_path,
                    models=self.state.load(),
                )
                log.info(
                    "generated %.2fs audio in %.0fms voice=%s",
                    result.duration_seconds,
                    result.timing.get("total_ms", 0),
                    voice,
                )
                audio = wav_path.read_bytes()
        except Exception as exc:  # noqa: BLE001
            log.exception("speech request failed")
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(audio)))
        self.end_headers()
        self.wfile.write(audio)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8")) if raw else {}

    def write_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        log.info("%s - %s", self.address_string(), fmt % args)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model-path", default=DEFAULT_MODEL)
    parser.add_argument("--voice", default=DEFAULT_VOICE, choices=VOICES)
    parser.add_argument("--preload", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    state = State(args.model_path, args.voice)
    if args.preload:
        state.load()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.state = state  # type: ignore[attr-defined]
    log.info("serving Voxtral MLX on http://%s:%s", args.host, args.port)
    log.info("model=%s voice=%s", args.model_path, args.voice)
    server.serve_forever()


if __name__ == "__main__":
    main()
