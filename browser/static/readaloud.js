/**
 * Voxtral Read-aloud HTTP client for vidux-browse
 *
 * Thin client that POSTs the active artifact's text to a local
 * mlx-audio.server (Mistral Voxtral 4B-TTS on Apple Silicon) and
 * streams the resulting WAV chunks through the Web Audio API.
 *
 * No model state in the browser — all inference happens in the
 * mlx_audio.server process listening on http://127.0.0.1:8000.
 *
 *   Architecture: vidux/projects/voxtral-reader-addon/evidence/2026-05-01-architecture.md
 *   Plan:         vidux/projects/voxtral-reader-addon/PLAN.md (M3)
 *   Server install: see /moussey skill, "Voxtral Reader add-on" section.
 *
 * Offline fallback: see `readaloud-kokoro.js` (kokoro-js + WebGPU,
 * Apache-2.0, ~80 MB Q8 weights). Swap the <script src> in index.html.
 */

const READALOUD = {
  button: null,
  voiceSelect: null,
  state: "idle", // idle | loading | playing | error
  abortController: null,
  audioContext: null,
  highlightedSpans: [],
};

const ENDPOINT = "http://127.0.0.1:8000/v1/audio/speech";
const MODEL = "mlx-community/Voxtral-4B-TTS-2603-mlx-bf16";
const DEFAULT_VOICE = "casual_male";
const VOICE_STORAGE_KEY = "vidux.readaloud.voice";
const MAX_INPUT_CHARS = 5000;
const TARGET_CHUNK_CHARS = 320;

function readaloudCurrentVoice() {
  if (READALOUD.voiceSelect && READALOUD.voiceSelect.value) {
    return READALOUD.voiceSelect.value;
  }
  return DEFAULT_VOICE;
}

function readaloudInit() {
  READALOUD.button = document.getElementById("root-readaloud-toggle");
  if (!READALOUD.button) return;
  READALOUD.button.addEventListener("click", readaloudOnClick);
  READALOUD.button.title = "Read aloud (Voxtral via local mlx-audio.server)";

  READALOUD.voiceSelect = document.getElementById("root-readaloud-voice");
  if (READALOUD.voiceSelect) {
    let saved = null;
    try { saved = localStorage.getItem(VOICE_STORAGE_KEY); } catch (_) { /* private mode */ }
    if (saved) {
      const valid = Array.from(READALOUD.voiceSelect.options).some(o => o.value === saved);
      if (valid) READALOUD.voiceSelect.value = saved;
    }
    READALOUD.voiceSelect.addEventListener("change", () => {
      try { localStorage.setItem(VOICE_STORAGE_KEY, READALOUD.voiceSelect.value); } catch (_) { /* ignore */ }
    });
  }

  readaloudSetState("idle");
  console.log("[readaloud] initialized (mlx-audio HTTP client, voice =", readaloudCurrentVoice(), ")");
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
      b.title = "Read aloud (Voxtral via local mlx-audio.server)";
      break;
    case "loading":
      b.textContent = label || "🔊 Synthesizing…";
      b.disabled = false;
      b.title = label || "Synthesizing…";
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

function readaloudClearHighlights() {
  for (const span of READALOUD.highlightedSpans) {
    span.classList.remove("ra-active");
  }
  READALOUD.highlightedSpans = [];
}

function readaloudHighlightChunk(chunkText, body) {
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
      // Range straddled element boundaries; skip the highlight, keep playing.
      console.debug("[readaloud] highlight range skipped:", e.message);
      return;
    }
  }
}

// Split text into ~TARGET_CHUNK_CHARS-sized chunks at sentence boundaries.
// Falls back to paragraph splits, then to fixed-width slices for content
// without sentence terminators (code blocks, lists). Each chunk is sent as
// one /v1/audio/speech request.
function readaloudSplitText(text) {
  const sentenceRegex = /[^.!?\n]+[.!?]+["')\]]?|[^.!?\n]+(?=\n|$)/g;
  const sentences = text.match(sentenceRegex) || [text];
  const chunks = [];
  let buffer = "";
  for (const s of sentences) {
    const trimmed = s.trim();
    if (!trimmed) continue;
    if (!buffer) {
      buffer = trimmed;
    } else if ((buffer + " " + trimmed).length <= TARGET_CHUNK_CHARS) {
      buffer += " " + trimmed;
    } else {
      chunks.push(buffer);
      buffer = trimmed;
    }
  }
  if (buffer) chunks.push(buffer);
  // Ultra-long single-sentence pathological case: hard-split.
  const safe = [];
  for (const c of chunks) {
    if (c.length <= TARGET_CHUNK_CHARS * 2) {
      safe.push(c);
    } else {
      for (let i = 0; i < c.length; i += TARGET_CHUNK_CHARS) {
        safe.push(c.slice(i, i + TARGET_CHUNK_CHARS));
      }
    }
  }
  return safe;
}

async function readaloudFetchChunkAudio(chunkText, voice, signal) {
  const resp = await fetch(ENDPOINT, {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: MODEL,
      input: chunkText,
      voice,
      response_format: "wav",
    }),
  });
  if (!resp.ok) {
    let detail = "";
    try {
      const text = await resp.text();
      detail = text.slice(0, 200);
    } catch (_) { /* ignore */ }
    throw new Error(`HTTP ${resp.status} ${resp.statusText}${detail ? ` — ${detail}` : ""}`);
  }
  return resp.arrayBuffer();
}

async function readaloudOnClick() {
  if (READALOUD.state === "playing" || READALOUD.state === "loading") {
    if (READALOUD.abortController) READALOUD.abortController.abort();
    if (READALOUD.audioContext) {
      try { await READALOUD.audioContext.close(); } catch (_) { /* ignore */ }
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
  const capped = text.length > MAX_INPUT_CHARS ? text.slice(0, MAX_INPUT_CHARS) + "…" : text;
  const chunks = readaloudSplitText(capped);
  if (chunks.length === 0) {
    readaloudSetState("error", "No content to read");
    return;
  }

  READALOUD.abortController = new AbortController();
  const signal = READALOUD.abortController.signal;
  // Snapshot voice at click-time so mid-playback voice changes don't desync chunks.
  const voice = readaloudCurrentVoice();

  try {
    readaloudSetState("loading", `🔊 Synthesizing 1/${chunks.length}…`);
    READALOUD.audioContext = new AudioContext({ sampleRate: 24000 });

    let nextStartTime = READALOUD.audioContext.currentTime + 0.1;
    let lastEndTime = nextStartTime;
    let firstChunkScheduled = false;

    for (let i = 0; i < chunks.length; i++) {
      if (signal.aborted) break;
      readaloudSetState(
        firstChunkScheduled ? "playing" : "loading",
        firstChunkScheduled ? undefined : `🔊 Synthesizing ${i + 1}/${chunks.length}…`,
      );

      const arrayBuf = await readaloudFetchChunkAudio(chunks[i], voice, signal);
      if (signal.aborted) break;

      let audioBuf;
      try {
        audioBuf = await READALOUD.audioContext.decodeAudioData(arrayBuf);
      } catch (decodeErr) {
        console.warn("[readaloud] decode failed for chunk", i, decodeErr);
        continue;
      }

      const source = READALOUD.audioContext.createBufferSource();
      source.buffer = audioBuf;
      source.connect(READALOUD.audioContext.destination);
      source.start(nextStartTime);

      const startsInMs = Math.max(
        0,
        (nextStartTime - READALOUD.audioContext.currentTime) * 1000,
      );
      const chunkText = chunks[i];
      setTimeout(() => {
        if (!signal.aborted) readaloudHighlightChunk(chunkText, body);
      }, startsInMs);

      if (!firstChunkScheduled) {
        readaloudSetState("playing");
        firstChunkScheduled = true;
      }

      nextStartTime += audioBuf.duration;
      lastEndTime = nextStartTime;
    }

    const totalWaitMs = Math.max(
      0,
      (lastEndTime - READALOUD.audioContext.currentTime) * 1000 + 200,
    );
    setTimeout(() => {
      if (signal.aborted) return;
      readaloudClearHighlights();
      readaloudSetState("idle");
      if (READALOUD.audioContext) {
        try { READALOUD.audioContext.close(); } catch (_) { /* ignore */ }
        READALOUD.audioContext = null;
      }
    }, totalWaitMs);
  } catch (err) {
    if (err.name === "AbortError") return;
    console.error("[readaloud]", err);
    let msg = err.message || "Failed";
    const networkish =
      err.message &&
      (err.message.includes("Failed to fetch") ||
        err.message.includes("NetworkError") ||
        err.message.includes("ECONNREFUSED") ||
        err.message.includes("Load failed"));
    if (networkish) {
      msg = "🔊 Server offline — start mlx-audio LaunchAgent (see /moussey)";
    }
    readaloudSetState("error", msg);
    if (READALOUD.audioContext) {
      try { await READALOUD.audioContext.close(); } catch (_) { /* ignore */ }
      READALOUD.audioContext = null;
    }
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", readaloudInit);
} else {
  readaloudInit();
}
