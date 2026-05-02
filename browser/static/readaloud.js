/**
 * Voxtral Read-aloud add-on for vidux-browse (optional)
 *
 * Mistral Voxtral 4B TTS via Transformers.js v4, running entirely in the
 * browser via WebGPU. CC BY NC 4.0 — personal use only. Do NOT enable for
 * commercial UIs (Snowcubes, Resplit, StrongYes).
 *
 * First click triggers ~2.5GB Q4 weights download from HF CDN, cached in
 * IndexedDB by ORT. Subsequent clicks are instant.
 *
 * To disable: delete this file and remove its <script> tag from index.html
 * + the #root-readaloud-toggle button entry. ANNOTATION_CAPTURE_EXCLUDE_SELECTOR
 * in app.js can keep the entry — harmless if the button is gone.
 *
 * Plan: ~/Development/vidux/projects/voxtral-reader-addon/PLAN.md
 */

const READALOUD = {
  button: null,
  audio: null,
  pipelinePromise: null,
  state: "idle", // idle | loading | playing | error
};

function readaloudInit() {
  READALOUD.button = document.getElementById("root-readaloud-toggle");
  if (!READALOUD.button) return;
  READALOUD.audio = new Audio();
  READALOUD.audio.addEventListener("ended", () => readaloudSetState("idle"));
  READALOUD.audio.addEventListener("error", () =>
    readaloudSetState("error", "Playback failed"),
  );
  READALOUD.button.addEventListener("click", readaloudOnClick);
  readaloudSetState("idle");
  console.log("[readaloud] initialized");
}

function readaloudSetState(state, label) {
  READALOUD.state = state;
  const b = READALOUD.button;
  if (!b) return;
  b.classList.toggle("is-active", state === "playing");
  b.classList.toggle("is-loading", state === "loading");
  switch (state) {
    case "idle":
      b.textContent = "🔊 Read";
      b.disabled = false;
      b.title = "Read aloud (Voxtral, WebGPU)";
      break;
    case "loading":
      b.textContent = label || "🔊 Loading…";
      b.disabled = true;
      b.title = label || "Loading Voxtral…";
      break;
    case "playing":
      b.textContent = "■ Stop";
      b.disabled = false;
      b.title = "Stop playback";
      break;
    case "error":
      b.textContent = "🔊 Retry";
      b.disabled = false;
      b.title = label || "Error";
      break;
  }
}

async function readaloudGetPipeline() {
  if (READALOUD.pipelinePromise) return READALOUD.pipelinePromise;
  READALOUD.pipelinePromise = (async () => {
    const url = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@4";
    const tx = await import(url);
    const { VoxtralForConditionalGeneration, VoxtralProcessor } = tx;
    if (!VoxtralForConditionalGeneration || !VoxtralProcessor) {
      throw new Error(
        "Transformers.js v4 missing Voxtral exports — check CDN version",
      );
    }
    const progress_callback = (p) => {
      if (p && typeof p.progress === "number") {
        readaloudSetState("loading", `🔊 ${Math.round(p.progress)}%`);
      }
    };
    const modelId = "mistralai/Voxtral-4B-TTS-2603";
    const model = await VoxtralForConditionalGeneration.from_pretrained(modelId, {
      device: "webgpu",
      dtype: "q4",
      progress_callback,
    });
    const processor = await VoxtralProcessor.from_pretrained(modelId);
    return { model, processor };
  })();
  return READALOUD.pipelinePromise;
}

async function readaloudOnClick() {
  if (READALOUD.state === "playing") {
    READALOUD.audio.pause();
    READALOUD.audio.currentTime = 0;
    readaloudSetState("idle");
    return;
  }

  // Source text: prefer the markdown body; fall back to the active pane's
  // first content div. Works for both PLAN.md (renderPane) and artifact
  // (renderArtifactPane) surfaces.
  const body =
    document.getElementById("md-body") ||
    document.querySelector(".pane > div:not(.pane-empty)");
  const text = (body && body.innerText ? body.innerText : "").trim();
  if (!text) {
    readaloudSetState("error", "No content to read");
    return;
  }
  // Cap to ~2000 chars for first-pass UX (Voxtral handles longer, but
  // long input on first cold-start GPU pass is a bad first impression).
  const capped = text.length > 2000 ? text.slice(0, 2000) + "…" : text;

  try {
    readaloudSetState("loading", "🔊 Loading model…");
    const { model, processor } = await readaloudGetPipeline();
    readaloudSetState("loading", "🔊 Synthesizing…");

    const inputs = await processor(capped);
    const output = await model.generate(inputs);
    const samples = output.audio || output.audio_values || output.waveform;
    const sampleRate = output.sampling_rate || 24000;
    if (!samples) {
      throw new Error(
        "Voxtral output missing audio field — API surface may have changed",
      );
    }

    const wavBlob = floatToWavBlob(samples, sampleRate);
    READALOUD.audio.src = URL.createObjectURL(wavBlob);
    await READALOUD.audio.play();
    readaloudSetState("playing");
  } catch (err) {
    console.error("[readaloud]", err);
    readaloudSetState("error", err.message || "Failed");
  }
}

function floatToWavBlob(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(view, 36, "data");
  view.setUint32(40, samples.length * 2, true);
  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

function writeString(view, offset, str) {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i));
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", readaloudInit);
} else {
  readaloudInit();
}
