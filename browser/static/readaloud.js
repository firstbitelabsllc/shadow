/**
 * Read-aloud add-on for vidux-browse.
 *
 * Preferred engine: local Voxtral 4B TTS over MLX, served by
 * browser/scripts/voxtral_mlx_server.py on http://127.0.0.1:8765.
 *
 * Voxtral's HF weights are public and ungated, but they are not a
 * Transformers.js/WebGPU browser model. The browser talks to a local
 * Apple-Silicon MLX process instead. Generated WAVs are cached in IndexedDB
 * by text/model/voice so unchanged documents replay without re-synthesis.
 */

const READALOUD = {
  button: null,
  engineBadge: null,
  cacheButton: null,
  speedButton: null,
  player: null,
  playerToggle: null,
  playerSeek: null,
  playerStatus: null,
  serverCommandButton: null,
  playerTime: null,
  audio: null,
  abortController: null,
  activeSpan: null,
  highlightedSpans: [],
  objectUrl: null,
  currentCacheKey: null,
  currentCacheSource: null,
  currentSegments: [],
  currentSegmentDurations: [],
  currentSegmentCacheKeys: [],
  currentCachePrune: null,
  sectionObserver: null,
  sectionRefreshTimer: null,
  sectionRefreshInProgress: false,
  engineProbeTimer: null,
  engineProbeDeadline: 0,
  cacheDbPromise: null,
  state: "idle", // idle | loading | playing | paused | error
  activeEngine: null,
  voxtralBaseUrl: "http://127.0.0.1:8765",
  modelId: "redseaplume/Voxtral-4B-TTS-2603-MLX-4bit",
  defaultVoice: "cheerful_female",
  speedIndex: 1,
  speeds: [1, 1.12, 1.25],
};

const READALOUD_SECTION_CONTROL_KINDS = new Set([
  "paragraph",
  "list-item",
  "quote",
  "artifact-block",
]);

const READALOUD_ENGINE_CANDIDATES = [
  {
    id: "voxtral-mlx-script",
    label: "Voxtral MLX script server",
    baseUrl: "http://127.0.0.1:8765",
    probePath: "/health",
    modelId: "redseaplume/Voxtral-4B-TTS-2603-MLX-4bit",
    command: "browser/scripts/start-voxtral-mlx-server.sh",
  },
];
const READALOUD_SERVER_COMMAND = "browser/scripts/start-voxtral-mlx-server.sh";
const READALOUD_OFFLINE_REPROBE_INTERVAL_MS = 3000;
const READALOUD_OFFLINE_REPROBE_WINDOW_MS = 90000;
const READALOUD_CACHE_MAX_BYTES = 160 * 1024 * 1024;
const READALOUD_CACHE_MAX_ENTRIES = 120;
const READALOUD_SYNTH_BATCH_TARGET_CHARS = 700;
const READALOUD_SYNTH_BATCH_MAX_SEGMENTS = 6;

function readaloudInit() {
  READALOUD.button = document.getElementById("root-readaloud-toggle");
  if (!READALOUD.button) return;
  READALOUD.engineBadge = document.getElementById("root-readaloud-engine");
  READALOUD.cacheButton = document.getElementById("readaloud-cache-clear");
  READALOUD.speedButton = document.getElementById("root-readaloud-speed");
  READALOUD.player = document.getElementById("readaloud-player");
  READALOUD.playerToggle = document.getElementById("readaloud-player-toggle");
  READALOUD.playerSeek = document.getElementById("readaloud-player-seek");
  READALOUD.playerStatus = document.getElementById("readaloud-player-status");
  READALOUD.serverCommandButton = document.getElementById("readaloud-server-command");
  READALOUD.playerTime = document.getElementById("readaloud-player-time");

  READALOUD.button.addEventListener("click", readaloudOnClick);
  if (READALOUD.playerToggle) {
    READALOUD.playerToggle.addEventListener("click", readaloudTogglePlayer);
  }
  if (READALOUD.playerSeek) {
    READALOUD.playerSeek.addEventListener("input", readaloudSeekFromPlayer);
  }
  if (READALOUD.engineBadge) {
    READALOUD.engineBadge.addEventListener("click", readaloudCopyServerCommand);
  }
  if (READALOUD.serverCommandButton) {
    READALOUD.serverCommandButton.addEventListener("click", readaloudCopyServerCommand);
  }

  readaloudSetEngineStatus("unknown");
  readaloudProbeEngine();
  if (READALOUD.speedButton) {
    readaloudRestoreSpeed();
    READALOUD.speedButton.addEventListener("click", readaloudCycleSpeed);
  }
  if (READALOUD.cacheButton) {
    READALOUD.cacheButton.addEventListener("click", readaloudClearCurrentCache);
  }
  readaloudShowPlayer(true);
  readaloudSetState("idle");
  readaloudUpdatePlayerProgress();
  readaloudUpdateCacheButton();
  readaloudInstallSectionObserver();
  console.log("[readaloud] initialized (local Voxtral MLX)");
}

function readaloudAdvanced() {
  try { return typeof window.isAdvancedMode === "function" && window.isAdvancedMode(); }
  catch (e) { return false; }
}

function readaloudSetEngineStatus(status, detail) {
  const badge = READALOUD.engineBadge;
  if (!badge) return;
  badge.classList.toggle("is-online", status === "online");
  badge.classList.toggle("is-offline", status === "offline");
  const advanced = readaloudAdvanced();
  badge.textContent = advanced
    ? (status === "online" ? "MLX on" : status === "offline" ? "MLX off" : "MLX")
    : (status === "online" ? "Voice on" : status === "offline" ? "Voice off" : "Voice");
  const engine = READALOUD.activeEngine || READALOUD_ENGINE_CANDIDATES[0];
  const suffix = detail ? ` (${detail})` : "";
  badge.title = advanced
    ? `Audio source: ${engine.label} at ${READALOUD.voxtralBaseUrl}${suffix}. ` +
      `Click to copy: ${readaloudServerCommand()}`
    : `Read-aloud voice status${suffix}. Click for the local setup command.`;
  badge.setAttribute(
    "aria-label",
    advanced
      ? `Audio source: ${engine.label} ${badge.textContent}${suffix}. Click to copy launch command.`
      : `Read-aloud voice status: ${badge.textContent}${suffix}. Click for setup command.`,
  );
  if (status === "offline" && (READALOUD.state === "idle" || READALOUD.state === "error")) {
    if (!READALOUD.engineProbeDeadline) {
      readaloudSetPlayerStatus(
        advanced
          ? `Server offline. Start ${readaloudOfflineServerLabel()}`
          : "Read-aloud isn't running right now.",
      );
    }
    readaloudShowServerCommand(true);
    readaloudStartOfflineReprobe();
  } else if (status === "online") {
    readaloudStopOfflineReprobe();
    if (READALOUD.state === "idle" || READALOUD.state === "error") {
      readaloudSetState("idle");
      readaloudSetPlayerStatus("Ready");
      readaloudShowServerCommand(false);
    }
  }
}

async function readaloudProbeEngine() {
  try {
    await readaloudResolveEngine(null, 800);
    readaloudSetEngineStatus("online");
  } catch (err) {
    readaloudSetEngineStatus("offline", err.message || "server not reachable");
  }
}

function readaloudSetState(state, label) {
  READALOUD.state = state;
  const b = READALOUD.button;
  if (!b) return;
  b.classList.toggle("is-active", state === "playing" || state === "paused");
  b.classList.toggle("is-loading", state === "loading");
  b.setAttribute("aria-busy", state === "loading" ? "true" : "false");
  if (READALOUD.player) {
    READALOUD.player.dataset.state = state;
    READALOUD.player.setAttribute("aria-busy", state === "loading" ? "true" : "false");
  }
  switch (state) {
    case "idle":
      b.textContent = "Read";
      b.disabled = false;
      b.title = readaloudAdvanced()
        ? "Read selected text or current pane with local Voxtral MLX"
        : "Read selected text or current pane aloud";
      b.setAttribute("aria-label", "Read current selection or pane aloud");
      break;
    case "loading":
      b.textContent = label || "Loading...";
      b.disabled = false;
      b.title = "Click to cancel";
      b.setAttribute("aria-label", "Cancel read-aloud loading");
      break;
    case "playing":
    case "paused":
      b.textContent = "Stop";
      b.disabled = false;
      b.title = "Stop playback";
      b.setAttribute("aria-label", "Stop read-aloud playback");
      break;
    case "error":
      b.textContent = "Retry";
      b.disabled = false;
      b.title = label || "Read-aloud failed";
      b.setAttribute("aria-label", "Retry read-aloud");
      break;
  }
  readaloudUpdatePlayerProgress();
}

function readaloudShowPlayer(show) {
  if (!READALOUD.player) return;
  READALOUD.player.hidden = false;
  document.body.classList.add("is-readaloud-player-visible");
}

function readaloudSetPlayerStatus(text) {
  if (!READALOUD.playerStatus) return;
  READALOUD.playerStatus.textContent = text || "";
  READALOUD.playerStatus.title = text || "";
}

async function readaloudTrackLoading(label, status, work, options = {}) {
  const startedAt = Date.now();
  const hintAfterSeconds = options.hintAfterSeconds || 8;
  const hint = options.hint || "";
  const update = () => {
    const elapsed = Math.floor((Date.now() - startedAt) / 1000);
    const elapsedText = elapsed > 0 ? ` (${elapsed}s elapsed)` : "";
    const hintText = hint && elapsed >= hintAfterSeconds ? ` ${hint}` : "";
    readaloudSetState("loading", label);
    readaloudSetPlayerStatus(`${status}${elapsedText}${hintText}`);
  };

  update();
  const timer = window.setInterval(update, 1000);
  try {
    return await work();
  } finally {
    window.clearInterval(timer);
  }
}

function readaloudActivateEngine(engine) {
  READALOUD.activeEngine = engine;
  READALOUD.voxtralBaseUrl = engine.baseUrl;
  READALOUD.modelId = engine.modelId;
}

function readaloudServerCommand() {
  return (READALOUD.activeEngine && READALOUD.activeEngine.command) || READALOUD_SERVER_COMMAND;
}

function readaloudOfflineServerLabel() {
  return `${READALOUD_ENGINE_CANDIDATES[0].label}: ${READALOUD_SERVER_COMMAND}`;
}

async function readaloudCheckEngine(engine, outerSignal, timeoutMs) {
  const response = await readaloudFetchWithTimeout(
    `${engine.baseUrl}${engine.probePath}`,
    { method: "GET", signal: outerSignal || undefined },
    timeoutMs,
  );
  if (!response.ok) throw new Error(`${engine.label} HTTP ${response.status}`);
  return response;
}

async function readaloudResolveEngine(outerSignal, timeoutMs) {
  const candidates = READALOUD.activeEngine ?
    [
      READALOUD.activeEngine,
      ...READALOUD_ENGINE_CANDIDATES.filter((engine) => engine.id !== READALOUD.activeEngine.id),
    ] :
    READALOUD_ENGINE_CANDIDATES;
  const failures = [];
  for (const engine of candidates) {
    try {
      await readaloudCheckEngine(engine, outerSignal, timeoutMs);
      readaloudActivateEngine(engine);
      return engine;
    } catch (err) {
      failures.push(`${engine.label}: ${err.message || err}`);
    }
  }
  throw new Error(failures.join("; ") || "server not reachable");
}

function readaloudStartOfflineReprobe() {
  if (READALOUD.engineProbeTimer) return;
  const now = Date.now();
  if (!READALOUD.engineProbeDeadline || now > READALOUD.engineProbeDeadline) {
    READALOUD.engineProbeDeadline = now + READALOUD_OFFLINE_REPROBE_WINDOW_MS;
  }
  readaloudShowServerCommand(true);
  if (READALOUD.state === "idle" || READALOUD.state === "error") {
    readaloudSetPlayerStatus(
      `Waiting for local server... ${readaloudOfflineServerLabel()}`,
    );
  }
  READALOUD.engineProbeTimer = window.setTimeout(
    readaloudRunOfflineReprobe,
    READALOUD_OFFLINE_REPROBE_INTERVAL_MS,
  );
}

async function readaloudRunOfflineReprobe() {
  READALOUD.engineProbeTimer = null;
  if (Date.now() > READALOUD.engineProbeDeadline) {
    READALOUD.engineProbeDeadline = 0;
    if (READALOUD.state === "idle" || READALOUD.state === "error") {
      readaloudSetPlayerStatus(
        `Server still offline. Start ${readaloudOfflineServerLabel()}`,
      );
      readaloudShowServerCommand(true);
    }
    return;
  }
  await readaloudProbeEngine();
}

function readaloudStopOfflineReprobe() {
  if (READALOUD.engineProbeTimer) {
    window.clearTimeout(READALOUD.engineProbeTimer);
    READALOUD.engineProbeTimer = null;
  }
  READALOUD.engineProbeDeadline = 0;
}

function readaloudShowServerCommand(show) {
  const b = READALOUD.serverCommandButton;
  if (!b) return;
  const command = readaloudServerCommand();
  const advanced = readaloudAdvanced();
  // Simple mode never surfaces the raw shell command inline -- the engine
  // badge (READALOUD.engineBadge) still copies it to clipboard on click
  // either way, this button just avoids dangling a path someone in Simple
  // mode has no context to run.
  b.hidden = !show || !advanced;
  b.textContent = command;
  b.title = `Copy: ${command}`;
  b.setAttribute("aria-label", `Copy local Voxtral MLX server command: ${command}`);
}

async function readaloudCopyServerCommand(event) {
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }

  const command = readaloudServerCommand();
  try {
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      throw new Error("Clipboard unavailable");
    }
    await navigator.clipboard.writeText(command);
    readaloudSetPlayerStatus(`Copied server command: ${command}`);
    readaloudShowServerCommand(true);
    if (readaloudShouldReprobeOffline()) readaloudStartOfflineReprobe();
  } catch (_) {
    readaloudSetPlayerStatus(`Run from the vidux repo root: ${command}`);
    readaloudShowServerCommand(true);
    if (readaloudShouldReprobeOffline()) readaloudStartOfflineReprobe();
  }
}

function readaloudShouldReprobeOffline() {
  return (
    READALOUD.state === "error" ||
    !READALOUD.engineBadge ||
    READALOUD.engineBadge.classList.contains("is-offline")
  );
}

function readaloudUpdatePlayerProgress() {
  const audio = READALOUD.audio;
  const hasDuration = audio && Number.isFinite(audio.duration) && audio.duration > 0;

  if (READALOUD.playerSeek) {
    const progress = hasDuration ? audio.currentTime / audio.duration : 0;
    READALOUD.playerSeek.value = String(Math.round(progress * 1000));
    READALOUD.playerSeek.disabled = !hasDuration;
    READALOUD.playerSeek.setAttribute(
      "aria-valuetext",
      `${readaloudFormatTime(hasDuration ? audio.currentTime : 0)} of ${readaloudFormatTime(hasDuration ? audio.duration : 0)}`,
    );
  }

  if (READALOUD.playerTime) {
    const current = hasDuration ? audio.currentTime : 0;
    const duration = hasDuration ? audio.duration : 0;
    READALOUD.playerTime.textContent =
      `${readaloudFormatTime(current)} / ${readaloudFormatTime(duration)}`;
  }

  if (READALOUD.playerToggle) {
    const canPlay = Boolean(audio);
    const isPlaying = Boolean(audio && !audio.paused && !audio.ended);
    READALOUD.playerToggle.disabled = !canPlay;
    READALOUD.playerToggle.textContent =
      isPlaying ? "Ⅱ" : audio && audio.ended ? "↺" : "▶";
    READALOUD.playerToggle.title =
      isPlaying ? "Pause" : audio && audio.ended ? "Replay" : "Play";
    READALOUD.playerToggle.setAttribute(
      "aria-label",
      isPlaying ? "Pause read-aloud" : audio && audio.ended ? "Replay read-aloud" : "Play read-aloud",
    );
    READALOUD.playerToggle.setAttribute("aria-pressed", isPlaying ? "true" : "false");
  }
  readaloudUpdateCacheButton();
}

function readaloudUpdateCacheButton(source = READALOUD.currentCacheSource) {
  const b = READALOUD.cacheButton;
  if (!b) return;

  const keys = (READALOUD.currentSegmentCacheKeys || []).filter(Boolean);
  const hasKeys = keys.length > 0;
  const sourceLabel =
    source === "cached" ? "Cached" :
    source === "mixed" ? "Mixed" :
    source === "generated" ? "Fresh" :
    source === "cleared" ? "Cleared" :
    "Cache";
  const disabled = !hasKeys || READALOUD.state === "loading";

  b.textContent = sourceLabel;
  b.disabled = disabled;
  b.classList.toggle("is-cached", source === "cached");
  b.classList.toggle("is-mixed", source === "mixed");
  b.classList.toggle("is-generated", source === "generated");
  b.classList.toggle("is-cleared", source === "cleared");

  if (hasKeys) {
    b.title = `${sourceLabel} playback. Clear ${keys.length} cached segment${keys.length === 1 ? "" : "s"} so the next read regenerates this document.`;
    b.setAttribute(
      "aria-label",
      `${sourceLabel} playback. Clear cached read-aloud audio for the current document.`,
    );
  } else {
    b.title = "No cached read-aloud segments for the current playback";
    b.setAttribute("aria-label", "No cached read-aloud segments to clear");
  }
}

function readaloudFormatTime(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const total = Math.floor(seconds);
  const mins = Math.floor(total / 60);
  const secs = String(total % 60).padStart(2, "0");
  return `${mins}:${secs}`;
}

async function readaloudTogglePlayer() {
  const audio = READALOUD.audio;
  if (!audio) return;
  try {
    if (audio.paused || audio.ended) {
      if (audio.ended) audio.currentTime = 0;
      await audio.play();
    } else {
      audio.pause();
    }
  } catch (err) {
    console.error("[readaloud]", err);
    readaloudSetState("error", err.message || "Playback failed");
    readaloudSetPlayerStatus("Playback failed");
  }
  readaloudUpdatePlayerProgress();
}

function readaloudSeekFromPlayer() {
  const audio = READALOUD.audio;
  if (!audio || !Number.isFinite(audio.duration) || audio.duration <= 0) return;
  const raw = Number(READALOUD.playerSeek && READALOUD.playerSeek.value);
  const progress = Number.isFinite(raw) ? Math.max(0, Math.min(1000, raw)) / 1000 : 0;
  audio.currentTime = readaloudTimelineTimeForProgress(progress, audio.duration);
  readaloudUpdateWordHighlight();
  readaloudUpdatePlayerProgress();
}

function readaloudRestoreSpeed() {
  const saved = Number(localStorage.getItem("vidux.readaloud.speed") || "");
  const idx = READALOUD.speeds.findIndex((speed) => Math.abs(speed - saved) < 0.001);
  READALOUD.speedIndex = idx >= 0 ? idx : 1;
  readaloudUpdateSpeedButton();
}

function readaloudCycleSpeed() {
  READALOUD.speedIndex = (READALOUD.speedIndex + 1) % READALOUD.speeds.length;
  localStorage.setItem("vidux.readaloud.speed", String(readaloudPlaybackRate()));
  if (READALOUD.audio) READALOUD.audio.playbackRate = readaloudPlaybackRate();
  readaloudUpdateSpeedButton();
}

function readaloudPlaybackRate() {
  return READALOUD.speeds[READALOUD.speedIndex] || 1.12;
}

function readaloudSpeedLabel(speed) {
  return speed === 1 ? "1x" : `${speed.toFixed(2)}x`;
}

function readaloudUpdateSpeedButton() {
  const b = READALOUD.speedButton;
  if (!b) return;
  const speed = readaloudPlaybackRate();
  b.textContent = readaloudSpeedLabel(speed);
  b.title = `Read-aloud speed: ${readaloudSpeedLabel(speed)}. Click to cycle.`;
  b.setAttribute("aria-label", b.title);
  b.classList.toggle("is-default", Math.abs(speed - 1.12) < 0.001);
}

async function readaloudOnClick() {
  if (READALOUD.state === "playing" || READALOUD.state === "loading" || READALOUD.state === "paused") {
    readaloudStop();
    return;
  }

  const body =
    document.getElementById("md-body") ||
    document.querySelector(".pane > div:not(.pane-empty)");
  const source = readaloudGetSource(body);
  if (!source.text) {
    readaloudSetState("error", "No content to read");
    return;
  }

  try {
    await readaloudPlaySource(body, source);
  } catch (err) {
    readaloudHandlePlaybackError(err);
  }
}

async function readaloudPlaySource(body, source) {
  const playbackSource = readaloudPreparePlaybackSource(source, 3000);
  const text = playbackSource.text;
  if (!text) {
    readaloudSetState("error", "No content to read");
    return;
  }

  READALOUD.abortController = new AbortController();
  readaloudShowPlayer(true);

  readaloudSetState("loading", "Preparing...");
  readaloudSetPlayerStatus("Preparing text...");
  const cacheKey = await readaloudSegmentsPlaybackKey(playbackSource.segments);

  if (READALOUD.audio && READALOUD.currentCacheKey === cacheKey) {
    readaloudSetPlayerStatus("Replaying cached audio");
    READALOUD.audio.currentTime = 0;
    await READALOUD.audio.play();
    return;
  }

  const result = await readaloudGetSegmentAudio(
    playbackSource.segments,
    READALOUD.abortController.signal,
  );
  await readaloudPlayBlob(result.blob, body, text, source.range, {
    cacheKey,
    cacheSource: result.source,
    segments: playbackSource.segments,
    segmentDurations: result.segmentDurations,
    segmentCacheKeys: result.segmentCacheKeys,
  });
}

function readaloudHandlePlaybackError(err) {
  if (err.name === "AbortError") return;
  console.error("[readaloud]", err);
  const msg = String(err.message || err);
  if (msg.includes("fetch") || msg.includes("NetworkError") || msg.includes("Voxtral server")) {
    readaloudSetState("error", "Start Voxtral server");
    readaloudSetPlayerStatus(
      `Start local Voxtral MLX server: ${readaloudOfflineServerLabel()}`,
    );
    readaloudShowServerCommand(true);
    readaloudStartOfflineReprobe();
    READALOUD.button.title =
      `Run: ${readaloudServerCommand()}, then retry`;
    return;
  }
  readaloudSetState("error", msg);
  readaloudSetPlayerStatus(msg);
}

function readaloudGetSource(body) {
  if (!body) return { text: "", range: null, segments: [] };

  const selectionSource = readaloudGetSelectionSource(body);
  if (selectionSource) return selectionSource;

  const segments = readaloudCollectSegments(body);
  const text = readaloudSegmentsToText(segments) || (body.innerText || "").trim();
  return {
    text,
    range: null,
    segments,
  };
}

function readaloudGetSelectionSource(body) {
  const selection = window.getSelection && window.getSelection();
  if (!selection || selection.isCollapsed || selection.rangeCount === 0) return null;

  const range = selection.getRangeAt(0);
  if (!readaloudNodeInside(body, range.commonAncestorContainer)) return null;

  const text = selection.toString().trim();
  if (!text) return null;

  return {
    text,
    range: range.cloneRange(),
    segments: readaloudCollectSegments(body, range),
  };
}

function readaloudNodeInside(root, node) {
  if (!root || !node) return false;
  const element = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
  return element === root || (element ? root.contains(element) : false);
}

function readaloudPreparePlaybackSource(source, maxChars) {
  const rawSegments =
    source && source.segments && source.segments.length
      ? source.segments
      : [readaloudCreateSegment("block", source ? source.text : "", null, source ? source.range : null, 0)];
  const segments = [];
  let usedChars = 0;
  for (const rawSegment of rawSegments) {
    const normalized = readaloudNormalizeSegmentText(rawSegment.text);
    if (!normalized) continue;
    const separatorChars = segments.length ? 2 : 0;
    const remaining = maxChars - usedChars - separatorChars;
    if (remaining <= 0) break;

    let text = normalized;
    if (text.length > remaining) {
      const sliceLength = Math.max(1, remaining - 3);
      text = `${text.slice(0, sliceLength).trim()}...`;
    }
    if (!text) continue;

    segments.push(readaloudCloneSegment(rawSegment, text, segments.length));
    usedChars += separatorChars + text.length;
  }

  return {
    text: readaloudSegmentsToText(segments),
    segments,
  };
}

function readaloudCloneSegment(segment, text, index) {
  const kind = segment.kind || "block";
  const hash = readaloudStableHash(`${kind}\n${text}`);
  return {
    ...segment,
    id: `ra-seg-${index}-${kind}-${hash.slice(0, 8)}`,
    kind,
    text,
    hash,
  };
}

function readaloudInstallSectionObserver() {
  const pane = document.getElementById("pane");
  if (!pane) return;

  if (READALOUD.sectionObserver) READALOUD.sectionObserver.disconnect();
  READALOUD.sectionObserver = new MutationObserver((mutations) => {
    if (READALOUD.sectionRefreshInProgress) return;
    if (readaloudMutationsAreReadaloudUiOnly(mutations)) return;
    readaloudQueueSectionRefresh();
  });
  READALOUD.sectionObserver.observe(pane, { childList: true, subtree: true });
  readaloudQueueSectionRefresh();
}

function readaloudQueueSectionRefresh() {
  if (READALOUD.state === "loading" || READALOUD.state === "playing" || READALOUD.state === "paused") {
    return;
  }
  if (READALOUD.sectionRefreshTimer) window.clearTimeout(READALOUD.sectionRefreshTimer);
  READALOUD.sectionRefreshTimer = window.setTimeout(readaloudRefreshSectionControls, 60);
}

function readaloudMutationsAreReadaloudUiOnly(mutations) {
  let sawMutationNode = false;
  for (const mutation of mutations || []) {
    const nodes = [...Array.from(mutation.addedNodes || []), ...Array.from(mutation.removedNodes || [])];
    if (!nodes.length) return false;
    sawMutationNode = true;
    if (!nodes.every(readaloudNodeIsReadaloudUi)) return false;
  }
  return sawMutationNode;
}

function readaloudNodeIsReadaloudUi(node) {
  if (!node) return false;
  if (node.nodeType === Node.TEXT_NODE) {
    return Boolean(node.parentElement && node.parentElement.closest(".ra-word,.ra-section-play"));
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return false;
  return Boolean(
    node.matches(".ra-word,.ra-section-play") ||
      node.querySelector(".ra-word,.ra-section-play"),
  );
}

function readaloudRefreshSectionControls() {
  const body = document.getElementById("md-body");
  if (!body) return;
  if (READALOUD.state === "loading" || READALOUD.state === "playing" || READALOUD.state === "paused") {
    return;
  }

  READALOUD.sectionRefreshInProgress = true;
  try {
    for (const button of body.querySelectorAll(".ra-section-play")) button.remove();
    for (const host of body.querySelectorAll(".ra-section-play-host")) {
      host.classList.remove("ra-section-play-host");
    }

    const segments = readaloudCollectSegments(body).filter(readaloudSegmentCanUseSectionControl);
    for (const segment of segments.slice(0, 80)) {
      readaloudAddSectionControl(segment);
    }
  } finally {
    READALOUD.sectionRefreshInProgress = false;
  }
}

function readaloudSegmentCanUseSectionControl(segment) {
  const element = segment && segment.element;
  if (!element || !READALOUD_SECTION_CONTROL_KINDS.has(segment.kind)) return false;
  if (element.closest("pre,code,button,input,textarea,select,.topbar,.sidebar,.readaloud-player")) {
    return false;
  }
  const text = readaloudNormalizeSegmentText(segment.text);
  return text.length >= 36;
}

function readaloudAddSectionControl(segment) {
  const element = segment.element;
  if (!element || element.querySelector(":scope > .ra-section-play")) return;

  const button = document.createElement("button");
  button.type = "button";
  button.className = "ra-section-play";
  button.dataset.raSegmentId = segment.id;
  button.textContent = "Read";
  button.title = `Read this section: ${readaloudSegmentTitle(segment)}`;
  button.setAttribute("aria-label", `Read this section: ${readaloudSegmentTitle(segment)}`);
  button.addEventListener("click", readaloudPlaySection);

  element.classList.add("ra-section-play-host");
  element.insertBefore(button, element.firstChild);
}

async function readaloudPlaySection(event) {
  event.preventDefault();
  event.stopPropagation();

  const button = event.currentTarget;
  const body = document.getElementById("md-body");
  if (!button || !body) return;

  if (READALOUD.state === "playing" || READALOUD.state === "loading" || READALOUD.state === "paused") {
    readaloudStop();
  }

  const segment = readaloudFindSectionSegment(body, button);
  if (!segment) {
    readaloudSetState("error", "Section unavailable");
    readaloudSetPlayerStatus("Section unavailable");
    return;
  }

  const originalText = button.textContent;
  button.textContent = "Loading";
  button.classList.add("is-loading");
  button.setAttribute("aria-busy", "true");
  button.disabled = true;
  try {
    await readaloudPlaySource(body, {
      text: segment.text,
      range: readaloudSegmentRange(segment),
      segments: [segment],
    });
  } catch (err) {
    readaloudHandlePlaybackError(err);
  } finally {
    button.textContent = originalText || "Read";
    button.classList.remove("is-loading");
    button.setAttribute("aria-busy", "false");
    button.disabled = false;
  }
}

function readaloudFindSectionSegment(body, button) {
  const id = button.dataset.raSegmentId;
  const host = button.closest(".ra-section-play-host");
  const segments = readaloudCollectSegments(body);
  return (
    segments.find((segment) => segment.id === id) ||
    segments.find((segment) => segment.element === host) ||
    null
  );
}

function readaloudSegmentRange(segment) {
  if (segment && segment.range) return segment.range.cloneRange();
  if (!segment || !segment.element) return null;
  const range = document.createRange();
  range.selectNodeContents(segment.element);
  return range;
}

export function readaloudCollectSegments(body, sourceRange = null) {
  if (!body) return [];

  if (sourceRange) {
    const text = readaloudNormalizeSegmentText(sourceRange.toString());
    if (!text) return [];
    const node =
      sourceRange.commonAncestorContainer.nodeType === Node.ELEMENT_NODE
        ? sourceRange.commonAncestorContainer
        : sourceRange.commonAncestorContainer.parentElement;
    return [readaloudCreateSegment("selection", text, node || body, sourceRange.cloneRange(), 0)];
  }

  const primarySelector = [
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "li",
    "pre",
    "blockquote",
    "td",
    "th",
    "figcaption",
    "summary",
  ].join(",");
  const containerSelector = [
    ".contact-card",
    ".lead-row",
    "article",
    "section",
  ].join(",");

  const candidates = [];
  for (const element of body.querySelectorAll(primarySelector)) {
    if (element.closest("li,pre,blockquote") !== element) {
      const parentBlock = element.parentElement && element.parentElement.closest("li,pre,blockquote");
      if (parentBlock && body.contains(parentBlock)) continue;
    }
    candidates.push(element);
  }

  for (const element of body.querySelectorAll(containerSelector)) {
    if (element.querySelector(primarySelector)) continue;
    candidates.push(element);
  }

  for (const element of Array.from(body.children || [])) {
    if (candidates.some((candidate) => candidate === element || element.contains(candidate))) continue;
    if (!readaloudLooksLikeFallbackSegment(element)) continue;
    candidates.push(element);
  }

  candidates.sort((a, b) => {
    if (a === b) return 0;
    return a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
  });

  const segments = [];
  for (const element of candidates) {
    if (!readaloudElementIsReadable(element)) continue;
    const text = readaloudNormalizeSegmentText(readaloudElementText(element));
    if (!text) continue;
    const kind = readaloudSegmentKind(element);
    segments.push(readaloudCreateSegment(kind, text, element, null, segments.length));
  }
  return segments;
}

function readaloudSegmentsToText(segments) {
  return (segments || [])
    .map((segment) => segment.text)
    .filter(Boolean)
    .join("\n\n")
    .trim();
}

function readaloudCreateSegment(kind, text, element, range, index) {
  const hash = readaloudStableHash(`${kind}\n${text}`);
  return {
    id: `ra-seg-${index}-${kind}-${hash.slice(0, 8)}`,
    kind,
    text,
    hash,
    element,
    range,
  };
}

function readaloudStableHash(value) {
  let hash = 0x811c9dc5;
  for (let i = 0; i < value.length; i++) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, "0");
}

function readaloudNormalizeSegmentText(text) {
  return String(text || "")
    .replace(/\s+/g, " ")
    .trim();
}

function readaloudElementText(element) {
  if (!element) return "";
  const clone = element.cloneNode(true);
  for (const word of clone.querySelectorAll(".ra-word")) {
    word.replaceWith(document.createTextNode(word.textContent || ""));
  }
  clone
    .querySelectorAll(
      ".ra-section-play,.readaloud-player,.annotation-fab,button,input,textarea,select,script,style",
    )
    .forEach((node) => node.remove());
  return clone.innerText || clone.textContent || "";
}

function readaloudSegmentKind(element) {
  if (!element || !element.tagName) return "block";
  const tag = element.tagName.toLowerCase();
  if (/^h[1-6]$/.test(tag)) return "heading";
  if (tag === "li") return "list-item";
  if (tag === "pre") return "code-block";
  if (tag === "blockquote") return "quote";
  if (tag === "td" || tag === "th") return "table-cell";
  if (element.matches && element.matches(".contact-card,.lead-row,article,section")) {
    return "artifact-block";
  }
  return tag === "p" ? "paragraph" : "block";
}

function readaloudElementIsReadable(element) {
  if (!element || !element.isConnected) return false;
  if (
    element.closest(
      "button,input,textarea,select,script,style,.ra-word,.ra-section-play,.readaloud-player,.annotation-fab,.topbar,.sidebar,[hidden],[aria-hidden='true']",
    )
  ) {
    return false;
  }
  const style = window.getComputedStyle ? window.getComputedStyle(element) : null;
  if (style && (style.display === "none" || style.visibility === "hidden")) return false;
  return Boolean(readaloudNormalizeSegmentText(readaloudElementText(element)));
}

function readaloudLooksLikeFallbackSegment(element) {
  if (!element || !element.tagName) return false;
  const tag = element.tagName.toLowerCase();
  if (!["div", "article", "section", "main"].includes(tag)) return false;
  if (element.children && element.children.length > 8) return false;
  return readaloudNormalizeSegmentText(readaloudElementText(element)).length >= 2;
}

async function readaloudGetSegmentAudio(segments, outerSignal) {
  if (!segments || !segments.length) {
    throw new Error("No readable segments found");
  }

  readaloudSetState("loading", "Checking MLX...");
  readaloudSetPlayerStatus("Checking local MLX server...");
  await readaloudEnsureVoxtralHealthy(outerSignal);

  const ordered = new Array(segments.length);
  const misses = [];
  let cachedCount = 0;

  for (let i = 0; i < segments.length; i++) {
    const segment = segments[i];
    const cacheKey = await readaloudSegmentCacheKey(segment);
    readaloudSetState("loading", "Cache...");
    readaloudSetPlayerStatus(
      `Checking segment ${i + 1}/${segments.length}: ${readaloudSegmentTitle(segment)}`,
    );
    const cached = await readaloudCacheGet(cacheKey);
    if (cached) {
      cachedCount += 1;
      ordered[i] = { segment, blob: cached, cacheKey, source: "cached" };
    } else {
      misses.push({ index: i, segment, cacheKey });
    }
  }

  const batches = readaloudBuildSynthesisBatches(misses);

  if (misses.length) {
    const batchWord = batches.length === 1 ? "batch" : "batches";
    readaloudSetPlayerStatus(
      `${cachedCount} cached, ${misses.length} missing in ${batches.length} ${batchWord}`,
    );
  } else {
    readaloudSetPlayerStatus(`${cachedCount} cached, 0 generating audio`);
  }

  for (let i = 0; i < batches.length; i++) {
    const batch = batches[i];
    const progress = `${i + 1}/${batches.length}`;
    const title = readaloudSynthesisBatchTitle(batch);
    const blob = await readaloudTrackLoading(
      `Generate ${progress}`,
      `${cachedCount} cached, generating audio batch ${progress}: ${title}`,
      () => readaloudFetchVoxtral(batch.text, outerSignal),
      {
        hintAfterSeconds: 8,
        hint: "Local Voxtral returns one WAV when generation finishes; this is still working.",
      },
    );
    const items = await readaloudMaterializeBatchSegments(batch, blob, progress);
    for (const item of items) {
      await readaloudCachePut(item.cacheKey, item.blob, {
        type: "segment",
        model: READALOUD.modelId,
        voice: READALOUD.defaultVoice,
        segment_id: item.segment.id,
        segment_kind: item.segment.kind,
        segment_hash: item.segment.hash,
        text: item.segment.text,
        synthesis_batch_size: batch.misses.length,
      });
      ordered[item.index] = {
        segment: item.segment,
        blob: item.blob,
        cacheKey: item.cacheKey,
        source: "generated",
      };
    }
  }

  const protectedKeys = ordered.map((item) => item && item.cacheKey).filter(Boolean);
  const cachePrune = await readaloudCachePrune({ protectedKeys });
  readaloudReportCachePrune(cachePrune);

  const merged = await readaloudTrackLoading(
    "Decoding...",
    "Decoding and stitching segment audio",
    () => readaloudMergeSegmentAudio(ordered),
    {
      hintAfterSeconds: 4,
      hint: "Browser is preparing the playable WAV.",
    },
  );
  const source =
    misses.length === 0 ? "cached" : cachedCount > 0 ? "mixed" : "generated";
  return {
    blob: merged.blob,
    source,
    segmentDurations: merged.segmentDurations,
    segmentCacheKeys: protectedKeys,
    cachePrune,
  };
}

function readaloudBuildSynthesisBatches(misses) {
  const batches = [];
  for (const miss of misses || []) {
    const text = readaloudNormalizeSegmentText(miss.segment && miss.segment.text);
    if (!text) continue;

    const last = batches[batches.length - 1];
    const candidateText = last ? `${last.text}\n\n${text}` : text;
    const canAppend =
      last &&
      last.misses.length < READALOUD_SYNTH_BATCH_MAX_SEGMENTS &&
      miss.index === last.misses[last.misses.length - 1].index + 1 &&
      candidateText.length <= READALOUD_SYNTH_BATCH_TARGET_CHARS;

    if (canAppend) {
      last.misses.push(miss);
      last.text = candidateText;
    } else {
      batches.push({ misses: [miss], text });
    }
  }
  return batches;
}

function readaloudSynthesisBatchTitle(batch) {
  if (!batch || !batch.misses || !batch.misses.length) return "empty batch";
  if (batch.misses.length === 1) return readaloudSegmentTitle(batch.misses[0].segment);
  const first = batch.misses[0];
  const last = batch.misses[batch.misses.length - 1];
  return `${batch.misses.length} segments ${first.index + 1}-${last.index + 1}: ${readaloudSegmentTitle(first.segment)}`;
}

async function readaloudMaterializeBatchSegments(batch, blob, progress) {
  if (!batch || !Array.isArray(batch.misses) || !batch.misses.length) {
    throw new Error("Empty synthesis batch");
  }
  if (batch.misses.length === 1) {
    const miss = batch.misses[0];
    readaloudSetPlayerStatus(
      `Buffered ${readaloudFormatBytes(blob.size)} WAV for batch ${progress}; caching segment...`,
    );
    return [
      {
        index: miss.index,
        segment: miss.segment,
        cacheKey: miss.cacheKey,
        blob,
      },
    ];
  }

  return readaloudTrackLoading(
    "Splitting...",
    `Buffered ${readaloudFormatBytes(blob.size)} WAV for batch ${progress}; splitting/decoding ${batch.misses.length} cached segments`,
    () => readaloudSplitBatchAudio(batch, blob),
    {
      hintAfterSeconds: 4,
      hint: "Keeping one fast MLX call while preserving per-section replay cache.",
    },
  );
}

async function readaloudSplitBatchAudio(batch, blob) {
  if (!batch || !Array.isArray(batch.misses) || !batch.misses.length) {
    throw new Error("Empty synthesis batch");
  }
  if (!blob || !blob.size) {
    throw new Error("Empty batch audio");
  }
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) throw new Error("AudioContext unavailable");
  const context = new AudioCtx();
  let buffer;
  try {
    buffer = await context.decodeAudioData(await blob.arrayBuffer());
  } finally {
    if (context.close) context.close().catch(() => {});
  }

  const sampleRate = buffer.sampleRate || 24000;
  const totalLength = buffer.length;
  if (!totalLength) {
    throw new Error("Decoded batch audio is empty");
  }
  if (totalLength < batch.misses.length) {
    throw new Error("Decoded batch audio is too short to split");
  }
  const weights = batch.misses.map((miss) =>
    Math.max(1, readaloudNormalizeSegmentText(miss.segment && miss.segment.text).length),
  );
  const totalWeight = weights.reduce((sum, weight) => sum + weight, 0) || weights.length;
  const items = [];
  let offset = 0;

  for (let i = 0; i < batch.misses.length; i++) {
    const miss = batch.misses[i];
    const remainingSamples = totalLength - offset;
    const remainingSegments = batch.misses.length - i;
    if (remainingSamples < remainingSegments) {
      throw new Error("Decoded batch audio is too short to split");
    }
    const maxLength = remainingSamples - (remainingSegments - 1);
    const length =
      i === batch.misses.length - 1
        ? remainingSamples
        : Math.max(1, Math.min(
          maxLength,
          Math.round((totalLength * weights[i]) / totalWeight),
        ));
    const samples = new Float32Array(length);
    buffer.copyFromChannel(samples, 0, offset);
    offset += length;
    items.push({
      index: miss.index,
      segment: miss.segment,
      cacheKey: miss.cacheKey,
      blob: readaloudFloatToWavBlob(samples, sampleRate),
    });
  }

  return items;
}

async function readaloudEnsureVoxtralHealthy(outerSignal) {
  const engine = await readaloudResolveEngine(outerSignal, 1200);
  readaloudSetEngineStatus("online");
  readaloudShowServerCommand(false);
  return engine;
}

async function readaloudSegmentsPlaybackKey(segments) {
  const fingerprint = (segments || [])
    .map((segment) => `${segment.kind}:${segment.hash}`)
    .join("|");
  return readaloudCacheKey(`segments:${fingerprint}`);
}

async function readaloudSegmentCacheKey(segment) {
  return readaloudCacheKey(`segment:${segment.kind}:${segment.hash}:${segment.text}`);
}

function readaloudSegmentTitle(segment) {
  const text = readaloudNormalizeSegmentText(segment && segment.text);
  if (!text) return "empty segment";
  return text.length > 56 ? `${text.slice(0, 53)}...` : text;
}

async function readaloudMergeSegmentAudio(items) {
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) throw new Error("AudioContext unavailable");
  const context = new AudioCtx();
  const decoded = [];
  try {
    for (const item of items) {
      const arrayBuffer = await item.blob.arrayBuffer();
      const buffer = await context.decodeAudioData(arrayBuffer.slice(0));
      decoded.push({ ...item, buffer });
    }
  } finally {
    if (context.close) context.close().catch(() => {});
  }

  if (!decoded.length) throw new Error("No segment audio decoded");
  const sampleRate = decoded[0].buffer.sampleRate || 24000;
  const segmentDurations = decoded.map((item) => item.buffer.duration);
  const totalLength = decoded.reduce((sum, item) => {
    if (item.buffer.sampleRate !== sampleRate) {
      throw new Error("Segment audio sample-rate mismatch");
    }
    return sum + item.buffer.length;
  }, 0);
  const samples = new Float32Array(totalLength);
  let offset = 0;
  for (const item of decoded) {
    samples.set(item.buffer.getChannelData(0), offset);
    offset += item.buffer.length;
  }
  return {
    blob: readaloudFloatToWavBlob(samples, sampleRate),
    segmentDurations,
  };
}

function readaloudFloatToWavBlob(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  readaloudWriteAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  readaloudWriteAscii(view, 8, "WAVE");
  readaloudWriteAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  readaloudWriteAscii(view, 36, "data");
  view.setUint32(40, samples.length * 2, true);
  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const sample = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

function readaloudWriteAscii(view, offset, value) {
  for (let i = 0; i < value.length; i++) {
    view.setUint8(offset + i, value.charCodeAt(i));
  }
}

async function readaloudFetchVoxtral(text, outerSignal) {
  const response = await fetch(`${READALOUD.voxtralBaseUrl}/v1/audio/speech`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      input: text,
      model: READALOUD.modelId,
      response_format: "wav",
      stream: false,
      voice: READALOUD.defaultVoice,
    }),
    signal: outerSignal,
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(`Voxtral synthesis failed: ${response.status} ${detail}`);
  }
  readaloudSetPlayerStatus("Voxtral responded; buffering WAV blob...");
  const blob = await response.blob();
  readaloudSetPlayerStatus(`Buffered ${readaloudFormatBytes(blob.size)} WAV from Voxtral`);
  return blob;
}

async function readaloudFetchWithTimeout(url, options, timeoutMs) {
  const timeout = new AbortController();
  const timer = setTimeout(() => timeout.abort(), timeoutMs);
  const outerSignal = options && options.signal;
  const abortFromOuter = () => timeout.abort();
  if (outerSignal) outerSignal.addEventListener("abort", abortFromOuter, { once: true });
  try {
    return await fetch(url, { ...options, signal: timeout.signal });
  } finally {
    clearTimeout(timer);
    if (outerSignal) outerSignal.removeEventListener("abort", abortFromOuter);
  }
}

async function readaloudCacheKey(text) {
  const payload = JSON.stringify({
    engine: READALOUD.activeEngine ? READALOUD.activeEngine.id : READALOUD.voxtralBaseUrl,
    model: READALOUD.modelId,
    voice: READALOUD.defaultVoice,
    text,
  });
  if (window.crypto && window.crypto.subtle && window.TextEncoder) {
    const data = new TextEncoder().encode(payload);
    const digest = await window.crypto.subtle.digest("SHA-256", data);
    return Array.from(new Uint8Array(digest))
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("");
  }
  let hash = 0;
  for (let i = 0; i < payload.length; i++) {
    hash = (Math.imul(31, hash) + payload.charCodeAt(i)) | 0;
  }
  return `fallback-${Math.abs(hash)}`;
}

function readaloudOpenCacheDb() {
  if (READALOUD.cacheDbPromise) return READALOUD.cacheDbPromise;
  READALOUD.cacheDbPromise = new Promise((resolve) => {
    if (!window.indexedDB) {
      resolve(null);
      return;
    }
    const request = window.indexedDB.open("vidux-readaloud-cache", 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("audio")) {
        db.createObjectStore("audio", { keyPath: "key" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => {
      console.warn("[readaloud] IndexedDB unavailable", request.error);
      resolve(null);
    };
  });
  return READALOUD.cacheDbPromise;
}

async function readaloudCacheGet(key) {
  const db = await readaloudOpenCacheDb();
  if (!db) return null;
  return new Promise((resolve) => {
    let blob = null;
    const tx = db.transaction("audio", "readwrite");
    tx.oncomplete = () => resolve(blob);
    tx.onerror = () => resolve(blob);
    const request = tx.objectStore("audio").get(key);
    request.onsuccess = () => {
      const record = request.result;
      if (!record) return;
      blob = record.blob || null;
      record.last_used_at = readaloudCacheNow();
      record.bytes = readaloudCacheRecordBytes(record);
      tx.objectStore("audio").put(record);
    };
    request.onerror = () => resolve(null);
  });
}

async function readaloudCachePut(key, blob, metadata = {}) {
  const db = await readaloudOpenCacheDb();
  if (!db) return;
  const now = readaloudCacheNow();
  return new Promise((resolve) => {
    const tx = db.transaction("audio", "readwrite");
    tx.oncomplete = () => resolve();
    tx.onerror = () => resolve();
    tx.objectStore("audio").put({
      key,
      blob,
      bytes: blob.size,
      type: metadata.type || null,
      model: metadata.model || READALOUD.modelId,
      voice: metadata.voice || READALOUD.defaultVoice,
      metadata,
      created_at: now,
      last_used_at: now,
    });
  });
}

async function readaloudCachePrune(options = {}) {
  const db = await readaloudOpenCacheDb();
  const protectedKeys = new Set((options.protectedKeys || []).filter(Boolean));
  const maxBytes = options.maxBytes || READALOUD_CACHE_MAX_BYTES;
  const maxEntries = options.maxEntries || READALOUD_CACHE_MAX_ENTRIES;
  if (!db) return { deleted: 0, bytes: 0, totalEntries: 0, totalBytes: 0 };

  return new Promise((resolve) => {
    const records = [];
    let result = { deleted: 0, bytes: 0, totalEntries: 0, totalBytes: 0 };
    const tx = db.transaction("audio", "readwrite");
    tx.oncomplete = () => resolve(result);
    tx.onerror = () => resolve(result);
    const store = tx.objectStore("audio");
    const cursorRequest = store.openCursor();
    cursorRequest.onerror = () => {};
    cursorRequest.onsuccess = (event) => {
      const cursor = event.target.result;
      if (cursor) {
        const record = cursor.value;
        if (readaloudCacheRecordPrunable(record)) {
          records.push({
            key: cursor.key,
            bytes: readaloudCacheRecordBytes(record),
            lastUsedMs: readaloudCacheRecordLastUsedMs(record),
          });
        }
        cursor.continue();
        return;
      }

      result.totalEntries = records.length;
      result.totalBytes = records.reduce((sum, record) => sum + record.bytes, 0);
      let remainingEntries = result.totalEntries;
      let remainingBytes = result.totalBytes;
      const sorted = records
        .filter((record) => !protectedKeys.has(record.key))
        .sort((a, b) => a.lastUsedMs - b.lastUsedMs);
      for (const record of sorted) {
        if (remainingEntries <= maxEntries && remainingBytes <= maxBytes) break;
        store.delete(record.key);
        remainingEntries -= 1;
        remainingBytes -= record.bytes;
        result.deleted += 1;
        result.bytes += record.bytes;
      }
    };
  });
}

function readaloudCacheRecordPrunable(record) {
  if (!record) return false;
  const metadata = record.metadata || {};
  const type = record.type || metadata.type;
  const model = record.model || metadata.model;
  return type === "segment" && model === READALOUD.modelId;
}

function readaloudCacheRecordBytes(record) {
  if (!record) return 0;
  if (Number.isFinite(record.bytes)) return Math.max(0, record.bytes);
  if (record.blob && Number.isFinite(record.blob.size)) return Math.max(0, record.blob.size);
  return 0;
}

function readaloudCacheRecordLastUsedMs(record) {
  const raw = record && (record.last_used_at || record.created_at);
  const parsed = raw ? Date.parse(raw) : NaN;
  return Number.isFinite(parsed) ? parsed : 0;
}

function readaloudCacheNow() {
  return new Date().toISOString();
}

function readaloudReportCachePrune(result) {
  if (!result || !result.deleted) return;
  console.info("[readaloud]", readaloudCachePruneMessage(result));
}

function readaloudCachePruneMessage(result) {
  return `Pruned ${result.deleted} old cached segment${result.deleted === 1 ? "" : "s"} (${readaloudFormatBytes(result.bytes)})`;
}

function readaloudFormatBytes(bytes) {
  const value = Number(bytes) || 0;
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  if (value >= 1024) return `${Math.round(value / 1024)} KB`;
  return `${Math.round(value)} B`;
}

async function readaloudCacheDeleteMany(keys) {
  const db = await readaloudOpenCacheDb();
  const uniqueKeys = [...new Set((keys || []).filter(Boolean))];
  if (!db || !uniqueKeys.length) return 0;
  return new Promise((resolve) => {
    let deleted = 0;
    const tx = db.transaction("audio", "readwrite");
    tx.oncomplete = () => resolve(deleted);
    tx.onerror = () => resolve(deleted);
    const store = tx.objectStore("audio");
    for (const key of uniqueKeys) {
      store.delete(key);
      deleted += 1;
    }
  });
}

async function readaloudClearCurrentCache(event) {
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }
  if (READALOUD.state === "loading") {
    readaloudSetPlayerStatus("Wait for synthesis to finish before clearing cache");
    return;
  }

  const keys = (READALOUD.currentSegmentCacheKeys || []).filter(Boolean);
  if (!keys.length) {
    READALOUD.currentCacheSource = null;
    readaloudUpdateCacheButton();
    readaloudSetPlayerStatus("No cached segments to clear");
    return;
  }

  readaloudSetPlayerStatus("Clearing cached segments...");
  const deleted = await readaloudCacheDeleteMany(keys);
  READALOUD.currentCacheKey = null;
  READALOUD.currentSegmentCacheKeys = [];
  READALOUD.currentCacheSource = "cleared";
  readaloudUpdateCacheButton("cleared");
  readaloudSetPlayerStatus(
    `Cleared ${deleted} cached segment${deleted === 1 ? "" : "s"}`,
  );
}

async function readaloudPlayBlob(blob, body, text, sourceRange, meta = {}) {
  readaloudClearAudio();
  READALOUD.currentSegments = meta.segments || [];
  READALOUD.currentSegmentDurations = meta.segmentDurations || [];
  readaloudBuildWordHighlights(body, text, sourceRange);
  readaloudAssignWordSegments();
  readaloudShowPlayer(true);

  READALOUD.objectUrl = URL.createObjectURL(blob);
  READALOUD.currentCacheKey = meta.cacheKey || null;
  READALOUD.currentCacheSource = meta.cacheSource || "generated";
  READALOUD.currentSegmentCacheKeys = meta.segmentCacheKeys || [];
  READALOUD.currentCachePrune = meta.cachePrune || null;
  readaloudUpdateCacheButton();

  const audio = new Audio(READALOUD.objectUrl);
  READALOUD.audio = audio;
  audio.playbackRate = readaloudPlaybackRate();
  let playbackConfirmed = false;

  audio.addEventListener("timeupdate", () => {
    readaloudUpdateWordHighlight();
    readaloudUpdatePlayerProgress();
  });
  audio.addEventListener("loadstart", () => {
    if (!playbackConfirmed) readaloudSetPlayerStatus("Loading WAV into browser audio...");
  });
  audio.addEventListener("loadedmetadata", () => {
    readaloudUpdateWordHighlight();
    readaloudUpdatePlayerProgress();
  });
  audio.addEventListener("canplay", () => {
    if (!playbackConfirmed) readaloudSetPlayerStatus("Audio decoded; starting playback...");
  });
  audio.addEventListener("waiting", () => {
    readaloudSetPlayerStatus("Browser audio buffering...");
  });
  audio.addEventListener("play", () => {
    readaloudSetState("playing");
    if (!playbackConfirmed) readaloudSetPlayerStatus("Starting browser playback...");
  });
  audio.addEventListener("playing", () => {
    playbackConfirmed = true;
    readaloudSetState("playing");
    readaloudSetPlayerStatus(
      readaloudPlaybackStatusLabel(
        READALOUD.currentCacheSource,
        READALOUD.currentCachePrune,
      ),
    );
  });
  audio.addEventListener("pause", () => {
    if (audio.ended || READALOUD.audio !== audio) return;
    readaloudSetState("paused");
    readaloudSetPlayerStatus("Paused");
  });
  audio.addEventListener("ended", () => {
    readaloudSetState("idle");
    readaloudSetPlayerStatus("Finished");
    readaloudUpdatePlayerProgress();
    readaloudQueueSectionRefresh();
  });
  audio.addEventListener("error", () => {
    readaloudClearHighlights();
    readaloudClearAudio();
    readaloudSetState("error", "Playback failed");
    readaloudSetPlayerStatus("Playback failed");
  });

  readaloudSetState("loading", "Starting...");
  readaloudSetPlayerStatus(
    readaloudPlaybackStatusWithPrune(
      readaloudStartingStatusLabel(meta.cacheSource),
      meta.cachePrune,
    ),
  );
  try {
    await audio.play();
  } catch (err) {
    readaloudClearHighlights();
    readaloudClearAudio();
    throw err;
  }
}

function readaloudStop() {
  if (READALOUD.abortController) {
    READALOUD.abortController.abort();
    READALOUD.abortController = null;
  }
  if (READALOUD.audio) {
    READALOUD.audio.pause();
    READALOUD.audio.currentTime = 0;
  }
  readaloudClearHighlights();
  readaloudClearAudio();
  readaloudSetPlayerStatus("Stopped");
  readaloudSetState("idle");
  readaloudQueueSectionRefresh();
}

function readaloudClearAudio() {
  if (READALOUD.audio) {
    READALOUD.audio.removeAttribute("src");
    READALOUD.audio.load();
    READALOUD.audio = null;
  }
  if (READALOUD.objectUrl) {
    URL.revokeObjectURL(READALOUD.objectUrl);
    READALOUD.objectUrl = null;
  }
  READALOUD.currentCacheKey = null;
  READALOUD.currentCacheSource = null;
  READALOUD.currentSegments = [];
  READALOUD.currentSegmentDurations = [];
  READALOUD.currentSegmentCacheKeys = [];
  READALOUD.currentCachePrune = null;
  readaloudUpdatePlayerProgress();
}

function readaloudPlaybackStatusLabel(source, prune) {
  const base =
    source === "cached" ? "Playing cached audio" :
    source === "mixed" ? "Playing cached/generated segments" :
    "Playing generated audio";
  return readaloudPlaybackStatusWithPrune(base, prune);
}

function readaloudStartingStatusLabel(source) {
  if (source === "cached") return "Starting cached audio...";
  if (source === "mixed") return "Starting cached/generated segments...";
  return "Starting generated audio...";
}

function readaloudPlaybackStatusWithPrune(base, prune) {
  if (!prune || !prune.deleted) return base;
  return `${base}. ${readaloudCachePruneMessage(prune)}`;
}

function readaloudSegmentTimeline() {
  const segments = READALOUD.currentSegments || [];
  const durations = READALOUD.currentSegmentDurations || [];
  if (!segments.length || segments.length !== durations.length) return null;

  const timeline = [];
  let start = 0;
  for (let i = 0; i < segments.length; i++) {
    const duration = Number(durations[i]);
    if (!Number.isFinite(duration) || duration <= 0) return null;
    timeline.push({
      index: i,
      segment: segments[i],
      start,
      end: start + duration,
      duration,
    });
    start += duration;
  }
  return timeline.length ? timeline : null;
}

function readaloudFindSegmentAtTime(time, timeline = readaloudSegmentTimeline()) {
  if (!timeline || !timeline.length || !Number.isFinite(time)) return null;
  const clamped = Math.max(0, time);
  for (const entry of timeline) {
    if (clamped >= entry.start && clamped < entry.end) return entry;
  }
  return timeline[timeline.length - 1];
}

function readaloudTimelineTimeForProgress(progress, fallbackDuration) {
  const timeline = readaloudSegmentTimeline();
  if (!timeline) return progress * fallbackDuration;
  const totalDuration = timeline[timeline.length - 1].end;
  return Math.max(0, Math.min(totalDuration, progress * totalDuration));
}

function readaloudAssignWordSegments() {
  const spans = READALOUD.highlightedSpans || [];
  const segments = READALOUD.currentSegments || [];
  if (!spans.length || !segments.length) return;

  let spanIndex = 0;
  for (let segmentIndex = 0; segmentIndex < segments.length; segmentIndex++) {
    const words = readaloudSegmentWords(segments[segmentIndex]);
    for (let wordIndex = 0; wordIndex < words.length && spanIndex < spans.length; wordIndex++) {
      const span = spans[spanIndex++];
      span.dataset.raSegmentIndex = String(segmentIndex);
      span.dataset.raSegmentWordIndex = String(wordIndex);
      span.dataset.raSegmentWordCount = String(words.length);
      span.dataset.raSegmentId = segments[segmentIndex].id || "";
    }
  }
}

function readaloudSegmentWords(segment) {
  return (readaloudNormalizeSegmentText(segment && segment.text).match(/\S+/g) || []);
}

function readaloudTimeForWordSpan(span, fallbackDuration, fallbackIndex, fallbackCount) {
  const timeline = readaloudSegmentTimeline();
  const segmentIndex = Number(span && span.dataset.raSegmentIndex);
  const wordIndex = Number(span && span.dataset.raSegmentWordIndex);
  const wordCount = Number(span && span.dataset.raSegmentWordCount);

  if (
    timeline &&
    Number.isFinite(segmentIndex) &&
    Number.isFinite(wordIndex) &&
    Number.isFinite(wordCount) &&
    timeline[segmentIndex]
  ) {
    const entry = timeline[segmentIndex];
    const localProgress = wordCount <= 1 ? 0 : Math.max(0, Math.min(1, wordIndex / (wordCount - 1)));
    return entry.start + localProgress * entry.duration;
  }

  const fallbackProgress = fallbackCount <= 1 ? 0 : fallbackIndex / (fallbackCount - 1);
  return Math.max(0, Math.min(fallbackDuration, fallbackProgress * fallbackDuration));
}

function readaloudWordForCurrentTime(audio, spans) {
  const timeline = readaloudSegmentTimeline();
  if (!timeline) {
    const idx = Math.min(
      spans.length - 1,
      Math.max(0, Math.floor((audio.currentTime / audio.duration) * spans.length)),
    );
    return spans[idx];
  }

  const entry = readaloudFindSegmentAtTime(audio.currentTime, timeline);
  if (!entry) return null;
  const segmentSpans = spans.filter(
    (span) => Number(span.dataset.raSegmentIndex) === entry.index,
  );
  if (!segmentSpans.length) return null;
  const localProgress =
    entry.duration <= 0 ? 0 : Math.max(0, Math.min(1, (audio.currentTime - entry.start) / entry.duration));
  const idx = Math.min(segmentSpans.length - 1, Math.floor(localProgress * segmentSpans.length));
  return segmentSpans[idx];
}

function readaloudBuildWordHighlights(body, text, sourceRange) {
  readaloudClearHighlights();
  if (!body || !text) return;

  if (sourceRange) {
    readaloudBuildRangeWordHighlights(body, text, sourceRange);
    return;
  }

  let remainingChars = text.length;
  const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
      const parent = node.parentElement;
      if (!parent) return NodeFilter.FILTER_REJECT;
      if (parent.closest("button,input,textarea,select,script,style,.ra-word,.ra-section-play,.readaloud-player")) {
        return NodeFilter.FILTER_REJECT;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });

  const nodes = [];
  let node;
  while ((node = walker.nextNode()) && remainingChars > 0) {
    nodes.push(node);
    remainingChars -= node.nodeValue.length;
  }

  remainingChars = text.length;
  for (const textNode of nodes) {
    if (remainingChars <= 0) break;
    const raw = textNode.nodeValue;
    const fragment = document.createDocumentFragment();
    remainingChars = readaloudAppendHighlightedWords(fragment, raw, remainingChars);
    textNode.replaceWith(fragment);
  }
}

function readaloudBuildRangeWordHighlights(body, text, sourceRange) {
  let remainingChars = text.length;
  const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
      const parent = node.parentElement;
      if (!parent) return NodeFilter.FILTER_REJECT;
      if (parent.closest("button,input,textarea,select,script,style,.ra-word,.ra-section-play,.readaloud-player")) {
        return NodeFilter.FILTER_REJECT;
      }
      try {
        return sourceRange.intersectsNode(node)
          ? NodeFilter.FILTER_ACCEPT
          : NodeFilter.FILTER_REJECT;
      } catch (_) {
        return NodeFilter.FILTER_REJECT;
      }
    },
  });

  const nodes = [];
  let node;
  while ((node = walker.nextNode()) && remainingChars > 0) nodes.push(node);

  for (const textNode of nodes) {
    if (remainingChars <= 0) break;
    const raw = textNode.nodeValue;
    const start = textNode === sourceRange.startContainer ? sourceRange.startOffset : 0;
    const end = textNode === sourceRange.endContainer ? sourceRange.endOffset : raw.length;
    if (end <= start) continue;

    const fragment = document.createDocumentFragment();
    if (start > 0) fragment.appendChild(document.createTextNode(raw.slice(0, start)));

    const target = raw.slice(start, end);
    remainingChars = readaloudAppendHighlightedWords(fragment, target, remainingChars);

    if (end < raw.length) fragment.appendChild(document.createTextNode(raw.slice(end)));
    textNode.replaceWith(fragment);
  }
}

function readaloudAppendHighlightedWords(fragment, raw, remainingChars) {
  const parts = raw.match(/\s+|\S+/g) || [];
  for (const part of parts) {
    if (!part.trim()) {
      fragment.appendChild(document.createTextNode(part));
      remainingChars -= part.length;
      continue;
    }
    if (remainingChars <= 0) {
      fragment.appendChild(document.createTextNode(part));
      continue;
    }
    const span = document.createElement("span");
    const index = READALOUD.highlightedSpans.length;
    span.className = "ra-word";
    span.dataset.raIndex = String(index);
    span.textContent = part;
    span.title = "Jump playback here";
    span.tabIndex = 0;
    span.setAttribute("role", "button");
    span.setAttribute("aria-label", `Jump playback to word ${index + 1}: ${part}`);
    span.addEventListener("click", readaloudSeekFromWord);
    span.addEventListener("keydown", readaloudSeekFromWordKeydown);
    fragment.appendChild(span);
    READALOUD.highlightedSpans.push(span);
    remainingChars -= part.length;
  }
  return remainingChars;
}

function readaloudSeekFromWordKeydown(event) {
  if (event.key !== "Enter" && event.key !== " ") return;
  readaloudSeekFromWord(event);
}

async function readaloudSeekFromWord(event) {
  event.preventDefault();
  event.stopPropagation();

  const audio = READALOUD.audio;
  const spans = READALOUD.highlightedSpans;
  const index = Number(event.currentTarget && event.currentTarget.dataset.raIndex);
  if (
    !audio ||
    !spans.length ||
    !Number.isFinite(audio.duration) ||
    audio.duration <= 0 ||
    !Number.isFinite(index)
  ) {
    return;
  }

  audio.currentTime = readaloudTimeForWordSpan(
    event.currentTarget,
    audio.duration,
    index,
    spans.length,
  );
  readaloudUpdateWordHighlight();
  readaloudUpdatePlayerProgress();
  if (audio.paused) {
    try {
      await audio.play();
    } catch (err) {
      console.error("[readaloud]", err);
    }
  }
}

function readaloudUpdateWordHighlight() {
  const audio = READALOUD.audio;
  const spans = READALOUD.highlightedSpans;
  if (!audio || !spans.length || !Number.isFinite(audio.duration) || audio.duration <= 0) {
    return;
  }

  const next = readaloudWordForCurrentTime(audio, spans);
  if (!next || next === READALOUD.activeSpan) return;
  if (READALOUD.activeSpan) READALOUD.activeSpan.classList.remove("ra-active");
  READALOUD.activeSpan = next;
  next.classList.add("ra-active");
  next.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function readaloudClearHighlights() {
  if (READALOUD.activeSpan) {
    READALOUD.activeSpan.classList.remove("ra-active");
    READALOUD.activeSpan = null;
  }
  const parents = new Set();
  for (const span of READALOUD.highlightedSpans) {
    const parent = span.parentNode;
    if (!parent) continue;
    parents.add(parent);
    span.replaceWith(document.createTextNode(span.textContent || ""));
  }
  for (const parent of parents) parent.normalize();
  READALOUD.highlightedSpans = [];
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", readaloudInit);
} else {
  readaloudInit();
}
