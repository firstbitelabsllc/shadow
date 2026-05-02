/**
 * Kokoro Read-aloud — OFFLINE FALLBACK for vidux-browse
 *
 * NOT loaded by default. The default `readaloud.js` is an HTTP client
 * for mlx-audio.server (Voxtral 4B-TTS on Apple Silicon, see PLAN.md
 * Phase 1). This file is kept for two cases:
 *
 *   1. Operators on machines without mlx-audio installed (lower-RAM
 *      Macs that can't hold the ~9 GB Voxtral working set).
 *   2. Commercial Leo properties (Snowcubes / Resplit / StrongYes) that
 *      can't use the CC-BY-NC-4.0 Voxtral weights — Kokoro is Apache 2.0.
 *
 * To use this fallback, change index.html's <script> src from
 * `readaloud.js` to `readaloud-kokoro.js`.
 *
 * Kokoro 82M TTS via kokoro-js, running 100% in the browser via WebGPU
 * (WASM fallback). ~80 MB Q8 weights cached in IndexedDB on first click.
 *
 * Plan: ~/Development/vidux/projects/voxtral-reader-addon/PLAN.md
 */

const READALOUD = {
  button: null,
  ttsPromise: null,
  state: "idle", // idle | loading | playing | error
  abortController: null,
  audioContext: null,
  highlightedSpans: [],
};

function readaloudInit() {
  READALOUD.button = document.getElementById("root-readaloud-toggle");
  if (!READALOUD.button) return;
  READALOUD.button.addEventListener("click", readaloudOnClick);
  readaloudSetState("idle");
  console.log("[readaloud] initialized (kokoro-js)");
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
      b.title = "Read aloud (Kokoro 82M, WebGPU/WASM)";
      break;
    case "loading":
      b.textContent = label || "🔊 Loading…";
      b.disabled = false; // keep clickable so user can cancel
      b.title = label || "Loading Kokoro…";
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

async function readaloudGetTTS() {
  if (READALOUD.ttsPromise) return READALOUD.ttsPromise;
  READALOUD.ttsPromise = (async () => {
    // esm.sh gives clean ESM with deps resolved; jsdelivr +esm path is finicky
    // for kokoro-js's transformers.js peer dep
    const url = "https://esm.sh/kokoro-js@1.2.0";
    const mod = await import(url);
    const { KokoroTTS, TextSplitterStream } = mod;
    if (!KokoroTTS) {
      throw new Error("kokoro-js missing KokoroTTS export — check CDN URL");
    }
    const modelId = "onnx-community/Kokoro-82M-v1.0-ONNX";
    let device = "webgpu";
    try {
      // Probe WebGPU; fall back to WASM if not available.
      if (!navigator.gpu) {
        console.warn("[readaloud] no navigator.gpu — falling back to WASM");
        device = "wasm";
      }
    } catch (_) {
      device = "wasm";
    }
    readaloudSetState("loading", `🔊 Init (${device})…`);
    const tts = await KokoroTTS.from_pretrained(modelId, {
      dtype: "q8",
      device,
      progress_callback: (p) => {
        if (p && typeof p.progress === "number") {
          readaloudSetState("loading", `🔊 ${Math.round(p.progress)}%`);
        }
      },
    });
    return { tts, TextSplitterStream };
  })();
  return READALOUD.ttsPromise;
}

function readaloudClearHighlights() {
  for (const span of READALOUD.highlightedSpans) {
    span.classList.remove("ra-active");
  }
  READALOUD.highlightedSpans = [];
}

function readaloudHighlightChunk(chunkText, body) {
  // Find the contiguous innerText range matching chunkText, wrap in highlight.
  // Naive: find first occurrence of trimmed chunk in body.innerText, locate
  // the corresponding text node via Range, wrap that range with a marker class.
  if (!chunkText || !body) return;
  readaloudClearHighlights();
  const needle = chunkText.trim();
  if (!needle) return;
  const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const idx = node.nodeValue.indexOf(needle);
    if (idx === -1) continue;
    try {
      const range = document.createRange();
      range.setStart(node, idx);
      range.setEnd(node, idx + needle.length);
      const span = document.createElement("span");
      span.className = "ra-active";
      range.surroundContents(span);
      READALOUD.highlightedSpans.push(span);
      span.scrollIntoView({ block: "nearest", behavior: "smooth" });
      return;
    } catch (e) {
      // Range straddled element boundaries — skip this chunk's highlight,
      // keep playing audio. Long chunks across <p> boundaries get no highlight.
      console.debug("[readaloud] highlight range skipped:", e.message);
      return;
    }
  }
}

async function readaloudOnClick() {
  if (READALOUD.state === "playing" || READALOUD.state === "loading") {
    if (READALOUD.abortController) READALOUD.abortController.abort();
    if (READALOUD.audioContext) {
      try { await READALOUD.audioContext.close(); } catch (_) {}
      READALOUD.audioContext = null;
    }
    readaloudClearHighlights();
    readaloudSetState("idle");
    return;
  }

  const body =
    document.getElementById("md-body") ||
    document.querySelector(".pane > div:not(.pane-empty)");
  const text = (body && body.innerText ? body.innerText : "").trim();
  if (!text) {
    readaloudSetState("error", "No content to read");
    return;
  }
  // Cap to ~3000 chars; Kokoro streams chunks so longer is OK but UX gets
  // unwieldy past a single article-length read.
  const capped = text.length > 3000 ? text.slice(0, 3000) + "…" : text;

  READALOUD.abortController = new AbortController();
  const signal = READALOUD.abortController.signal;

  try {
    readaloudSetState("loading", "🔊 Loading model…");
    const { tts, TextSplitterStream } = await readaloudGetTTS();
    if (signal.aborted) return;

    readaloudSetState("playing");
    READALOUD.audioContext = new AudioContext({ sampleRate: 24000 });

    const splitter = new TextSplitterStream();
    const stream = tts.stream(splitter, { voice: "af_heart" });
    splitter.push(capped);
    splitter.close();

    let nextStartTime = READALOUD.audioContext.currentTime + 0.05;
    let lastChunkEndTime = nextStartTime;

    for await (const chunk of stream) {
      if (signal.aborted) break;
      const { text: chunkText, audio } = chunk;
      if (!audio) continue;

      // audio is a RawAudio with .audio (Float32Array) and .sampling_rate
      const samples = audio.audio || audio.data || audio;
      const sampleRate = audio.sampling_rate || audio.sample_rate || 24000;
      if (!samples || !samples.length) continue;

      // Schedule chunk playback contiguously.
      const buf = READALOUD.audioContext.createBuffer(1, samples.length, sampleRate);
      buf.copyToChannel(samples, 0);
      const source = READALOUD.audioContext.createBufferSource();
      source.buffer = buf;
      source.connect(READALOUD.audioContext.destination);
      source.start(nextStartTime);

      const chunkDuration = samples.length / sampleRate;
      const startsInMs = Math.max(0, (nextStartTime - READALOUD.audioContext.currentTime) * 1000);

      // Highlight this chunk when its audio actually starts playing.
      setTimeout(() => {
        if (!signal.aborted) readaloudHighlightChunk(chunkText, body);
      }, startsInMs);

      nextStartTime += chunkDuration;
      lastChunkEndTime = nextStartTime;
    }

    // After last chunk finishes, return to idle.
    const totalWaitMs = Math.max(
      0,
      (lastChunkEndTime - READALOUD.audioContext.currentTime) * 1000 + 200,
    );
    setTimeout(() => {
      if (signal.aborted) return;
      readaloudClearHighlights();
      readaloudSetState("idle");
      if (READALOUD.audioContext) {
        try { READALOUD.audioContext.close(); } catch (_) {}
        READALOUD.audioContext = null;
      }
    }, totalWaitMs);
  } catch (err) {
    if (err.name === "AbortError") return;
    console.error("[readaloud]", err);
    readaloudSetState("error", err.message || "Failed");
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", readaloudInit);
} else {
  readaloudInit();
}
