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
  previewButton: null,
  previewAbort: null,
  previewContext: null,
  cloneButton: null,
  cloneFileInput: null,
  state: "idle", // idle | loading | playing | error
  abortController: null,
  audioContext: null,
  highlightedSpans: [],
};

const ENDPOINT = "http://127.0.0.1:8000/v1/audio/speech";
const UPLOAD_ENDPOINT = "/api/upload-ref-audio"; // same-origin (vidux-browse)
const MODEL = "mlx-community/Voxtral-4B-TTS-2603-mlx-bf16";
const DEFAULT_VOICE = "casual_male";
const VOICE_STORAGE_KEY = "vidux.readaloud.voice";
const CLONE_PATH_KEY = "vidux.readaloud.cloneRefPath";
const CLONE_TEXT_KEY = "vidux.readaloud.cloneRefText";
const PREVIEW_TEXT = "This is a sample of the selected voice.";
const MAX_INPUT_CHARS = 5000;
const TARGET_CHUNK_CHARS = 320;

function readaloudCloneState() {
  let path = null, text = null;
  try {
    path = localStorage.getItem(CLONE_PATH_KEY) || null;
    text = localStorage.getItem(CLONE_TEXT_KEY) || null;
  } catch (_) { /* private mode */ }
  return { path, text };
}

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

  READALOUD.previewButton = document.getElementById("root-readaloud-preview");
  if (READALOUD.previewButton) {
    READALOUD.previewButton.addEventListener("click", readaloudOnPreviewClick);
  }

  READALOUD.cloneButton = document.getElementById("root-readaloud-clone");
  READALOUD.cloneFileInput = document.getElementById("root-readaloud-clone-file");
  if (READALOUD.cloneButton) {
    READALOUD.cloneButton.addEventListener("click", readaloudOnCloneClick);
  }
  if (READALOUD.cloneFileInput) {
    READALOUD.cloneFileInput.addEventListener("change", readaloudOnCloneFile);
  }
  readaloudUpdateCloneButton();

  readaloudSetState("idle");
  console.log("[readaloud] initialized (mlx-audio HTTP client, voice =", readaloudCurrentVoice(), ")");
}

function readaloudUpdateCloneButton() {
  const btn = READALOUD.cloneButton;
  if (!btn) return;
  const { path } = readaloudCloneState();
  if (path) {
    const fname = path.split("/").pop();
    btn.textContent = "🎤 Cloned";
    btn.title = `Voice clone active: ${fname} — click to clear and revert to picker voice`;
    btn.classList.add("is-active");
  } else {
    btn.textContent = "🎤 Clone";
    btn.title = "Upload a 5-30s audio sample + transcript to clone the voice";
    btn.classList.remove("is-active");
  }
}

function readaloudOnCloneClick() {
  const { path } = readaloudCloneState();
  if (path) {
    const fname = path.split("/").pop();
    if (!confirm(`Clear cloned voice (${fname})?`)) return;
    try {
      localStorage.removeItem(CLONE_PATH_KEY);
      localStorage.removeItem(CLONE_TEXT_KEY);
    } catch (_) { /* ignore */ }
    readaloudUpdateCloneButton();
    return;
  }
  const inp = READALOUD.cloneFileInput;
  if (!inp) return;
  inp.value = ""; // reset so the change event fires even if same file picked twice
  inp.click();
}

async function readaloudOnCloneFile(ev) {
  const file = ev.target.files && ev.target.files[0];
  if (!file) return;
  const transcript = window.prompt(
    "Transcript of the audio clip (5-30s recommended). Used as ref_text so Voxtral knows what was said:",
    "",
  );
  if (transcript === null) return; // cancelled
  const trimmed = transcript.trim();
  if (!trimmed) {
    alert("Transcript is required for voice cloning — Voxtral needs to know what the audio says.");
    return;
  }
  const btn = READALOUD.cloneButton;
  const prevText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "🎤 Uploading…";
  try {
    const arrayBuf = await file.arrayBuffer();
    const u8 = new Uint8Array(arrayBuf);
    // Chunked btoa to avoid call-stack overflow on large files
    let bin = "";
    const CHUNK = 0x8000;
    for (let i = 0; i < u8.length; i += CHUNK) {
      bin += String.fromCharCode.apply(null, u8.subarray(i, i + CHUNK));
    }
    const b64 = btoa(bin);
    const ext = (file.name.split(".").pop() || "wav").toLowerCase();
    const resp = await fetch(UPLOAD_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ audio_base64: b64, ext }),
    });
    if (!resp.ok) {
      let detail = "";
      try { detail = await resp.text(); } catch (_) { /* ignore */ }
      if (resp.status === 404) {
        throw new Error(
          "Upload endpoint missing — restart vidux-browse so M8 server changes take effect:\n" +
          "  launchctl kickstart -k gui/$(id -u)/com.leokwan.vidux-browser",
        );
      }
      throw new Error(`HTTP ${resp.status} ${resp.statusText}${detail ? ` — ${detail.slice(0, 120)}` : ""}`);
    }
    const data = await resp.json();
    if (!data.ok || !data.path) throw new Error("upload returned no path");
    try {
      localStorage.setItem(CLONE_PATH_KEY, data.path);
      localStorage.setItem(CLONE_TEXT_KEY, trimmed);
    } catch (_) { /* ignore */ }
  } catch (err) {
    console.error("[readaloud] clone upload", err);
    alert(`Voice clone upload failed:\n${err.message || err}`);
    btn.textContent = prevText;
  } finally {
    btn.disabled = false;
    readaloudUpdateCloneButton();
  }
}

async function readaloudOnPreviewClick() {
  const btn = READALOUD.previewButton;
  if (!btn) return;
  // If already previewing, abort + reset.
  if (READALOUD.previewAbort) {
    READALOUD.previewAbort.abort();
    READALOUD.previewAbort = null;
    if (READALOUD.previewContext) {
      try { await READALOUD.previewContext.close(); } catch (_) { /* ignore */ }
      READALOUD.previewContext = null;
    }
    btn.textContent = "▶";
    btn.disabled = false;
    btn.title = "Preview selected voice with a sample sentence";
    return;
  }

  const voice = readaloudCurrentVoice();
  READALOUD.previewAbort = new AbortController();
  const signal = READALOUD.previewAbort.signal;

  btn.textContent = "…";
  btn.disabled = true;
  btn.title = `Synthesizing preview (${voice})…`;

  try {
    const arrayBuf = await readaloudFetchChunkAudio(PREVIEW_TEXT, voice, signal);
    if (signal.aborted) return;
    READALOUD.previewContext = new AudioContext({ sampleRate: 24000 });
    const audioBuf = await READALOUD.previewContext.decodeAudioData(arrayBuf);
    if (signal.aborted) return;
    const source = READALOUD.previewContext.createBufferSource();
    source.buffer = audioBuf;
    source.connect(READALOUD.previewContext.destination);
    btn.textContent = "■";
    btn.disabled = false;
    btn.title = "Stop preview";
    source.onended = async () => {
      btn.textContent = "▶";
      btn.disabled = false;
      btn.title = "Preview selected voice with a sample sentence";
      if (READALOUD.previewContext) {
        try { await READALOUD.previewContext.close(); } catch (_) { /* ignore */ }
        READALOUD.previewContext = null;
      }
      READALOUD.previewAbort = null;
    };
    source.start();
  } catch (err) {
    if (err.name === "AbortError") return;
    console.error("[readaloud] preview", err);
    btn.textContent = "▶";
    btn.disabled = false;
    btn.title = err.message || "Preview failed";
    READALOUD.previewAbort = null;
    if (READALOUD.previewContext) {
      try { await READALOUD.previewContext.close(); } catch (_) { /* ignore */ }
      READALOUD.previewContext = null;
    }
  }
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
  const body = {
    model: MODEL,
    input: chunkText,
    voice,
    response_format: "wav",
  };
  // When voice clone is set, include the server-local ref_audio path + transcript.
  // Voxtral requires BOTH `voice` and `ref_audio` set (verified 2026-05-02 — passing
  // ref_audio alone yields "Either ref_audio or voice must be defined" assertion).
  const clone = readaloudCloneState();
  if (clone.path && clone.text) {
    body.ref_audio = clone.path;
    body.ref_text = clone.text;
  }
  const resp = await fetch(ENDPOINT, {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
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
