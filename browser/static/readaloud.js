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
  // M19: per-section playback. Independent of main read-aloud — clicking a
  // section button aborts main playback (and any other section) and plays
  // ONLY that section's text. Reuses readaloudFetchChunkAudio so M16 cache
  // makes re-clicks instant.
  sectionPlayback: null, // { abort, context, button } | null
  sectionObserver: null,
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
// M12: Voxtral default cadence is conversational; Leo's morning M5 verdict
// flagged "talks a bit slow." mlx-audio's OpenAI-compatible endpoint accepts
// `speed` (server-side resample, NOT a client-side playbackRate chipmunk hack).
// Verified 2026-05-02: speed=1.25 returns ~72% of the bytes for the same text.
const SPEED = 1.25;

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
      // M17 — drop stale localStorage if the saved voice was removed (e.g. multilingual
      // options dropped). Without this, the picker silently falls back to default but
      // the stale value lingers in storage forever.
      else { try { localStorage.removeItem(VOICE_STORAGE_KEY); } catch (_) { /* ignore */ } }
    }
    READALOUD.voiceSelect.addEventListener("change", () => {
      try { localStorage.setItem(VOICE_STORAGE_KEY, READALOUD.voiceSelect.value); } catch (_) { /* ignore */ }
    });
  }

  READALOUD.previewButton = document.getElementById("root-readaloud-preview");
  if (READALOUD.previewButton) {
    READALOUD.previewButton.addEventListener("click", readaloudOnPreviewClick);
    readaloudUpdatePreviewButton();
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
  readaloudWatchMarkdownBody();
  console.log("[readaloud] initialized (mlx-audio HTTP client, voice =", readaloudCurrentVoice(), ")");
}

// M19: per-section playback. Inject a small ▶ button before each
// <p>/<h*>/<li> in #md-body. Click → synth + play that section only.
// Re-injection is idempotent (checks for an existing direct-child button).
function readaloudInjectSectionButtons() {
  const body = document.getElementById("md-body");
  if (!body) return;
  const sections = body.querySelectorAll("p, h1, h2, h3, h4, h5, h6, li");
  for (const section of sections) {
    if (section.querySelector(":scope > .ra-section-play")) continue;
    const text = (section.innerText || section.textContent || "").trim();
    if (!text || text.length < 4) continue; // skip empty / trivial
    const btn = document.createElement("button");
    btn.className = "ra-section-play";
    btn.type = "button";
    btn.textContent = "▶";
    btn.title = "Read this section aloud";
    btn.setAttribute("aria-label", "Read this section aloud");
    btn.addEventListener("click", readaloudOnSectionPlay);
    section.classList.add("ra-section-host");
    section.insertBefore(btn, section.firstChild);
  }
}

function readaloudExtractSectionText(section) {
  // Clone so we can strip the button + any active word/highlight spans
  // without mutating the live DOM.
  const clone = section.cloneNode(true);
  clone.querySelectorAll(".ra-section-play").forEach(b => b.remove());
  clone.querySelectorAll(".ra-word").forEach(w => {
    w.replaceWith(document.createTextNode(w.textContent || ""));
  });
  return (clone.innerText || clone.textContent || "").trim();
}

function readaloudStopSectionPlayback() {
  const sp = READALOUD.sectionPlayback;
  if (!sp) return;
  try { if (sp.abort) sp.abort.abort(); } catch (_) { /* ignore */ }
  if (sp.context) {
    try { sp.context.close(); } catch (_) { /* ignore */ }
  }
  if (sp.button) {
    sp.button.classList.remove("is-loading", "is-playing");
    sp.button.textContent = "▶";
    sp.button.title = "Read this section aloud";
  }
  READALOUD.sectionPlayback = null;
}

async function readaloudOnSectionPlay(ev) {
  ev.stopPropagation();
  ev.preventDefault();
  const btn = ev.currentTarget;
  const section = btn.parentElement;
  if (!section) return;

  // Toggle off if THIS section is already playing.
  if (READALOUD.sectionPlayback && READALOUD.sectionPlayback.button === btn) {
    readaloudStopSectionPlayback();
    return;
  }

  // Abort any other playback (main or other section) so we never have two
  // streams competing for the user's ears.
  if (READALOUD.abortController) {
    try { READALOUD.abortController.abort(); } catch (_) { /* ignore */ }
    if (READALOUD.audioContext) {
      try { await READALOUD.audioContext.close(); } catch (_) { /* ignore */ }
      READALOUD.audioContext = null;
    }
    readaloudClearHighlights();
    readaloudSetState("idle");
  }
  if (READALOUD.sectionPlayback) {
    readaloudStopSectionPlayback();
  }

  const text = readaloudExtractSectionText(section);
  if (!text) return;

  const voice = readaloudCurrentVoice();
  const abort = new AbortController();
  const context = new AudioContext({ sampleRate: 24000 });
  READALOUD.sectionPlayback = { abort, context, button: btn };

  btn.classList.add("is-loading");
  btn.textContent = "…";
  btn.title = "Synthesizing…";

  try {
    const arrayBuf = await readaloudFetchChunkAudio(text, voice, abort.signal);
    if (abort.signal.aborted) return;
    const audioBuf = await context.decodeAudioData(arrayBuf);
    if (abort.signal.aborted) return;
    const source = context.createBufferSource();
    source.buffer = audioBuf;
    source.connect(context.destination);
    btn.classList.remove("is-loading");
    btn.classList.add("is-playing");
    btn.textContent = "■";
    btn.title = "Stop section playback";
    source.onended = () => {
      if (READALOUD.sectionPlayback && READALOUD.sectionPlayback.button === btn) {
        readaloudStopSectionPlayback();
      }
    };
    source.start();
  } catch (err) {
    if (err.name !== "AbortError") {
      console.error("[readaloud] section play", err);
      btn.title = err.message || "Section playback failed";
    }
    readaloudStopSectionPlayback();
  }
}

function readaloudWatchMarkdownBody() {
  // #md-body is sometimes replaced wholesale (when the pane re-renders for
  // a new plan) and sometimes its innerHTML is updated in place. Observe
  // the #pane subtree so we catch both cases. Injection is idempotent so
  // re-firing on every mutation is safe.
  const pane = document.getElementById("pane");
  if (!pane) return;
  if (READALOUD.sectionObserver) {
    try { READALOUD.sectionObserver.disconnect(); } catch (_) { /* ignore */ }
  }
  let raId = 0;
  const observer = new MutationObserver(() => {
    if (raId) cancelAnimationFrame(raId);
    raId = requestAnimationFrame(() => {
      raId = 0;
      // Stop any section playback if the body changed under us.
      const body = document.getElementById("md-body");
      if (!body) return;
      if (READALOUD.sectionPlayback && !body.contains(READALOUD.sectionPlayback.button)) {
        readaloudStopSectionPlayback();
      }
      readaloudInjectSectionButtons();
    });
  });
  observer.observe(pane, { childList: true, subtree: true });
  READALOUD.sectionObserver = observer;
  // Initial pass in case content is already rendered.
  readaloudInjectSectionButtons();
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
  // Keep preview button title in sync — clone state determines whether ▶
  // hears the picker voice or the cloned timbre.
  readaloudUpdatePreviewButton();
}

function readaloudUpdatePreviewButton() {
  const btn = READALOUD.previewButton;
  if (!btn) return;
  // Don't clobber transient labels (…/■) mid-preview.
  if (btn.textContent !== "▶") return;
  const { path } = readaloudCloneState();
  if (path) {
    btn.title = "Preview cloned voice (sample sentence)";
  } else {
    btn.title = "Preview selected voice with a sample sentence";
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
          "  launchctl kickstart -k gui/$(id -u)/<your-vidux-browser-label>",
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
      readaloudUpdatePreviewButton();
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
      b.style.removeProperty("--ra-progress");
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
    if (span.parentNode) {
      const parent = span.parentNode;
      // First flatten any .ra-word children to plain text so we don't leave
      // orphaned per-word spans floating in the DOM.
      const wordSpans = span.querySelectorAll(".ra-word");
      for (const ws of wordSpans) {
        if (ws.parentNode) {
          ws.parentNode.replaceChild(document.createTextNode(ws.textContent || ""), ws);
        }
      }
      // Then unwrap the .ra-active wrapper itself.
      while (span.firstChild) parent.insertBefore(span.firstChild, span);
      parent.removeChild(span);
      // Coalesce adjacent text nodes so subsequent walks see one node again.
      parent.normalize();
    } else {
      span.classList.remove("ra-active");
    }
  }
  READALOUD.highlightedSpans = [];
}

function readaloudHighlightChunk(chunkText, body) {
  // Legacy chunk-level highlight (no per-word migration). Kept as fallback for
  // chunks that span multiple text nodes (rich-text in markdown body).
  if (!chunkText || !body) return false;
  readaloudClearHighlights();
  const needle = chunkText.trim();
  if (!needle) return false;
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
      try { span.scrollIntoView({ block: "nearest", behavior: "smooth" }); } catch (_) {}
      return true;
    } catch (e) {
      console.debug("[readaloud] highlight range skipped:", e.message);
      return false;
    }
  }
  return false;
}

// M13: per-word highlight via heuristic even-distribution across the chunk's
// audio duration. setTimeout per word at audioDur/wordCount intervals migrates
// the .ra-word-active class. Inaccurate when speech rate varies WITHIN a chunk
// (which is rare for Voxtral at conversational cadence) but free + zero-latency.
//
// Real markdown bodies split text across paragraphs/headings/list items, so
// the FULL chunk text (e.g., 320 chars spanning 3 paragraphs) is never found
// in a single DOM text node. We shorten the needle progressively until one
// fits: first sentence → first 60 chars → first 30 chars. The wrapper still
// represents "where this chunk's audio is currently anchored visually," even
// if it covers only the chunk's first sentence.
function readaloudFindChunkRange(chunkText, body) {
  const trimmed = chunkText.trim();
  if (!trimmed) return null;
  // Candidate needles, longest first (most informative match wins).
  const candidates = [];
  candidates.push(trimmed);
  // First sentence (split on . ! ? followed by space or end).
  const firstSentMatch = trimmed.match(/^[^.!?\n]+[.!?]/);
  if (firstSentMatch && firstSentMatch[0].length < trimmed.length) {
    candidates.push(firstSentMatch[0]);
  }
  // Up to first newline.
  const firstLine = trimmed.split(/\n/)[0];
  if (firstLine && firstLine.length < trimmed.length) candidates.push(firstLine);
  // Hard fallbacks.
  if (trimmed.length > 80) candidates.push(trimmed.slice(0, 80).replace(/\s\S*$/, ""));
  if (trimmed.length > 30) candidates.push(trimmed.slice(0, 30).replace(/\s\S*$/, ""));
  for (const needle of candidates) {
    if (!needle) continue;
    const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const idx = node.nodeValue.indexOf(needle);
      if (idx === -1) continue;
      const range = document.createRange();
      try {
        range.setStart(node, idx);
        range.setEnd(node, idx + needle.length);
        return { range, matched: needle };
      } catch (_) { continue; }
    }
  }
  return null;
}

function readaloudHighlightChunkWords(chunkText, audioDur, body, signal) {
  if (!chunkText || !body) return false;
  readaloudClearHighlights();
  const found = readaloudFindChunkRange(chunkText, body);
  if (!found) return false;
  const { range, matched } = found;
  try {
    const wrapper = document.createElement("span");
    wrapper.className = "ra-active";
    const tokens = matched.split(/(\s+)/);
    const wordSpans = [];
    for (const t of tokens) {
      if (!t) continue;
      if (/^\s+$/.test(t)) {
        wrapper.appendChild(document.createTextNode(t));
      } else {
        const ws = document.createElement("span");
        ws.className = "ra-word";
        ws.textContent = t;
        wrapper.appendChild(ws);
        wordSpans.push(ws);
      }
    }
    range.deleteContents();
    range.insertNode(wrapper);
    READALOUD.highlightedSpans.push(wrapper);
    try { wrapper.scrollIntoView({ block: "nearest", behavior: "smooth" }); } catch (_) {}
    if (wordSpans.length > 0 && audioDur > 0) {
      const ms = (audioDur * 1000) / wordSpans.length;
      for (let i = 0; i < wordSpans.length; i++) {
        setTimeout(() => {
          if (signal && signal.aborted) return;
          for (const w of wordSpans) w.classList.remove("ra-word-active");
          wordSpans[i].classList.add("ra-word-active");
        }, i * ms);
      }
    }
    return true;
  } catch (e) {
    console.debug("[readaloud] word-highlight skipped:", e.message);
    return false;
  }
}

// M14: keep the button label informative through playback. After chunk 1 starts
// playing the button used to freeze on "■ Stop" for ~95s on a 19-chunk plan.
// Now it shows the current chunk index and a fill on the bottom CSS bar.
function readaloudUpdatePlayingLabel(idx, total) {
  const b = READALOUD.button;
  if (!b || READALOUD.state !== "playing") return;
  b.textContent = `■ ${idx}/${total}`;
  b.title = `Playing chunk ${idx} of ${total} — click to stop`;
  b.style.setProperty("--ra-progress", `${(idx / total) * 100}%`);
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

// M16 — localStorage audio cache. Keyed by sha256(text+voice+speed+clone state)
// so any change forces a fresh synth, but unchanged content replays instantly
// instead of paying the ~5–10 s/chunk Voxtral synthesis cost. localStorage cap
// is ~5 MB per origin in Chrome; the cache LRU-evicts oldest when the index
// total exceeds CACHE_MAX_BYTES. base64 encoding adds ~33% overhead vs raw
// bytes, so 4 MB of base64 ≈ 3 MB of WAV ≈ ~80–150 chunks at speed 1.25.
const CACHE_INDEX_KEY = "vidux.readaloud.cache.index";
const CACHE_VALUE_PREFIX = "vidux.readaloud.cache.v.";
const CACHE_MAX_BYTES = 4 * 1024 * 1024; // 4 MB of base64 (Chrome quota leeway)

async function readaloudCacheKey(text, voice, speed, clonePath, cloneText) {
  const enc = new TextEncoder();
  const data = enc.encode(JSON.stringify({ text, voice, speed, clonePath, cloneText }));
  const hashBuf = await crypto.subtle.digest("SHA-256", data);
  const hashArr = Array.from(new Uint8Array(hashBuf));
  return hashArr.map(b => b.toString(16).padStart(2, "0")).join("");
}

function readaloudCacheGetIndex() {
  try { return JSON.parse(localStorage.getItem(CACHE_INDEX_KEY) || "[]"); }
  catch (_) { return []; }
}

function readaloudCacheSetIndex(idx) {
  try { localStorage.setItem(CACHE_INDEX_KEY, JSON.stringify(idx)); } catch (_) { /* ignore */ }
}

function readaloudCacheGet(key) {
  try {
    const b64 = localStorage.getItem(CACHE_VALUE_PREFIX + key);
    if (!b64) return null;
    const bin = atob(b64);
    const u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    // Bump LRU timestamp on hit
    const idx = readaloudCacheGetIndex();
    const found = idx.find(e => e.k === key);
    if (found) { found.t = Date.now(); readaloudCacheSetIndex(idx); }
    return u8.buffer;
  } catch (_) { return null; }
}

function readaloudCacheSet(key, arrayBuf) {
  try {
    const u8 = new Uint8Array(arrayBuf);
    let bin = "";
    const CHUNK = 0x8000;
    for (let i = 0; i < u8.length; i += CHUNK) {
      bin += String.fromCharCode.apply(null, u8.subarray(i, i + CHUNK));
    }
    const b64 = btoa(bin);
    const size = b64.length;

    let idx = readaloudCacheGetIndex();
    const existing = idx.find(e => e.k === key);
    if (existing) { existing.t = Date.now(); existing.s = size; }
    else { idx.push({ k: key, t: Date.now(), s: size }); }

    // LRU evict until under cap
    let total = idx.reduce((a, e) => a + e.s, 0);
    if (total > CACHE_MAX_BYTES) {
      idx.sort((a, b) => a.t - b.t);
      while (total > CACHE_MAX_BYTES && idx.length > 1) {
        const ev = idx.shift();
        try { localStorage.removeItem(CACHE_VALUE_PREFIX + ev.k); } catch (_) { /* ignore */ }
        total -= ev.s;
      }
    }

    localStorage.setItem(CACHE_VALUE_PREFIX + key, b64);
    readaloudCacheSetIndex(idx);
  } catch (e) {
    // QuotaExceededError: drop oldest half + skip caching this chunk.
    console.warn("[readaloud] cache.set failed (likely quota):", e.message);
    try {
      const idx = readaloudCacheGetIndex();
      idx.sort((a, b) => a.t - b.t);
      const half = Math.ceil(idx.length / 2);
      for (let i = 0; i < half; i++) {
        try { localStorage.removeItem(CACHE_VALUE_PREFIX + idx[i].k); } catch (_) { /* ignore */ }
      }
      readaloudCacheSetIndex(idx.slice(half));
    } catch (_) { /* ignore */ }
  }
}

async function readaloudFetchChunkAudio(chunkText, voice, signal) {
  const clone = readaloudCloneState();
  // Cache key includes ALL inputs that influence the audio. Hand-test by
  // changing any of them — the cache miss + re-synth proves the boundary.
  const cacheKey = await readaloudCacheKey(chunkText, voice, SPEED, clone.path, clone.text);
  const cached = readaloudCacheGet(cacheKey);
  if (cached) {
    console.log("[readaloud] cache HIT", cacheKey.slice(0, 8), `${cached.byteLength}B`);
    return cached;
  }

  const body = {
    model: MODEL,
    input: chunkText,
    voice,
    response_format: "wav",
    speed: SPEED,
  };
  // When voice clone is set, include the server-local ref_audio path + transcript.
  // Voxtral requires BOTH `voice` and `ref_audio` set (verified 2026-05-02 — passing
  // ref_audio alone yields "Either ref_audio or voice must be defined" assertion).
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
  const arrayBuf = await resp.arrayBuffer();
  // Cache the synthesized audio so the next play of the same content is instant.
  readaloudCacheSet(cacheKey, arrayBuf);
  return arrayBuf;
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
      const chunkIdx = i + 1;
      const chunkDur = audioBuf.duration;
      setTimeout(() => {
        if (signal.aborted) return;
        readaloudUpdatePlayingLabel(chunkIdx, chunks.length);
        readaloudHighlightChunkWords(chunkText, chunkDur, body, signal);
      }, startsInMs);

      if (!firstChunkScheduled) {
        readaloudSetState("playing");
        readaloudUpdatePlayingLabel(chunkIdx, chunks.length);
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
