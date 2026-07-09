const sidebarSort = window.ViduxSidebarSort;
const sidebarFilters = window.ViduxSidebarFilters;
const annotationState = window.ViduxAnnotationState;
const commentRail = window.ViduxCommentRail;
const commentMarkers = window.ViduxCommentMarkers;
const ANNOTATION_STATES = annotationState.STATES;
const AS = ANNOTATION_STATES;

const state = {
  plans: [],
  artifacts: [],
  dashboard: null,
  fleetSummary: null,
  opsTruth: null,
  filter: "",
  sort: sidebarSort.getStored(),
  filterChips: sidebarFilters.getStored(),
  active: null,        // {kind: 'dashboard'|'plan'|'artifact', ...metadata}
  activeTab: "PLAN.md",
  annotation: {
    capture: false,
    targetPath: "",
    anchor: null,
    phase: "idle",
  },
  comments: {
    targetPath: "",
    items: [],
  },
  commentMarkersHidden: commentMarkers.getStoredHidden(),
};
let activePopoverTarget = null;
let opsTruthRetryTimer = null;
let commentMarkerRenderFrame = 0;

const DECISION_LOG_TAB = "Decision Log";
const SESSION_TAB = "Sessions";
const LEDGER_TAB = "Ledger";
const DEFAULT_AUTO_REFRESH_INTERVAL_MS = 30000;
const AUTO_REFRESH_INTERVAL_MS = (() => {
  const configured = Number(window.__VIDUX_AUTO_REFRESH_INTERVAL_MS);
  return Number.isFinite(configured) && configured >= 0
    ? configured
    : DEFAULT_AUTO_REFRESH_INTERVAL_MS;
})();
let autoRefreshInFlight = false;

function currentParams() {
  return new URLSearchParams(window.location.search);
}

function pushUrl(params) {
  const search = params.toString();
  const newUrl = window.location.pathname + (search ? `?${search}` : "") + window.location.hash;
  // Avoid no-op history entries when the URL didn't actually change.
  if (newUrl === window.location.pathname + window.location.search + window.location.hash) return;
  window.history.pushState(null, "", newUrl);
}

function applyUrlSelection() {
  const params = currentParams();
  const artifactSlug = params.get("artifact");
  const planRel = params.get("plan");
  const tab = params.get("tab");

  if (artifactSlug) {
    const a = state.artifacts.find(x => x.slug === artifactSlug);
    if (a) { selectArtifact(a, { skipUrl: true, scrollIntoView: true }); return true; }
  }
  if (planRel) {
    const plan = state.plans.find(p => p.rel === planRel);
    if (plan) {
      selectPlan(plan, { skipUrl: true, tab: tab || "PLAN.md", scrollIntoView: true });
      return true;
    }
  }
  return false;
}

function scrollActiveRowIntoView() {
  // Wait one tick for the sidebar to re-render, then scroll the active row
  // into view if it's offscreen. Use 'nearest' so we don't yank the page on
  // already-visible items.
  requestAnimationFrame(() => {
    const row = els.list.querySelector(".plan-row.is-active");
    if (row) row.scrollIntoView({ block: "nearest", behavior: "smooth" });
  });
}

const els = {
  list: document.getElementById("sidebar-list"),
  filter: document.getElementById("filter"),
  sort: document.getElementById("sort"),
  filterChips: Array.from(document.querySelectorAll("[data-filter-chip]")),
  pane: document.getElementById("pane"),
  count: document.getElementById("meta-count"),
  refresh: document.getElementById("refresh"),
  annotate: document.getElementById("root-annotation-toggle"),
};

const COMMENT_AUTHOR_KEY = "vidux-browser-comment-author";
const RENDERED_ANCHOR_SELECTORS = [
  "h1", "h2", "h3", "h4", "h5", "h6",
  "p", "li", "blockquote", "pre", "table", "thead", "tbody", "tr", "th", "td",
  "article", "section", "aside", "header", "footer", "figure", "figcaption",
  "details", "summary", "dl", "dt", "dd", "div", "span", "a", "button",
];
const APP_ANCHOR_SELECTOR = [
  ".topbar",
  ".topbar h1",
  "#meta-count",
  ".ops-truth",
  ".ops-truth-item",
  ".repo-group h2",
  ".plan-row",
  ".pane-header",
  ".pane-header .breadcrumb",
  ".pane-header h2",
  ".pane-header .meta",
  ".pane-progress",
  ".pane-tabs",
  ".pane-tabs button",
  ".pane-investigations-strip",
  ".pane-investigations-strip button",
  ".dashboard-panel",
  ".dashboard-card",
  ".dashboard-list",
  ".dashboard-item",
  ".ledger-panel",
  ".ledger-entry",
  ".session-panel",
  ".session-turn",
  ".comments-panel",
  ".comments-head",
  ".comment-list .comment-item",
  ...RENDERED_ANCHOR_SELECTORS.map(selector => `#md-body ${selector}`),
].join(",");
const ANNOTATION_CAPTURE_EXCLUDE_SELECTOR = [
  "#refresh",
  "#sidebar-toggle",
  "#filter",
  ".plan-steering",
  ".plan-steering *",
  "#annotation-popover",
  "#annotation-popover *",
  ".comment-anchor button",
  "#comment-markers-toggle",
  ".comment-marker-layer",
  ".comment-marker-layer *",
  ".comment-target-map button",
].join(",");

function fmtAge(days) {
  if (days < 1) return "today";
  if (days < 2) return "1d";
  if (days < 30) return `${Math.round(days)}d`;
  if (days < 365) return `${Math.round(days / 30)}mo`;
  return `${(days / 365).toFixed(1)}y`;
}

// UI state (localStorage): collapsed sidebar keys + recent views.
const UI_STATE_KEY = "vidux:ui-state";
const RECENTS_MAX = 5;
const uiState = (() => {
  try {
    const raw = localStorage.getItem(UI_STATE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return {
      collapsed: new Set(Array.isArray(parsed.collapsed) ? parsed.collapsed : []),
      recents: Array.isArray(parsed.recents) ? parsed.recents : [],
    };
  } catch (e) {
    return { collapsed: new Set(), recents: [] };
  }
})();
function saveUiState() {
  try {
    localStorage.setItem(UI_STATE_KEY, JSON.stringify({
      collapsed: [...uiState.collapsed],
      recents: uiState.recents.slice(0, RECENTS_MAX * 2),
    }));
  } catch (e) { /* localStorage full or disabled — silently ignore */ }
}
function trackRecent(kind, key) {
  const id = `${kind}:${key}`;
  uiState.recents = uiState.recents.filter(r => r.id !== id);
  uiState.recents.unshift({ id, ts: Date.now() });
  uiState.recents = uiState.recents.slice(0, RECENTS_MAX * 2);
  saveUiState();
}
function toggleCollapsed(key) {
  if (uiState.collapsed.has(key)) uiState.collapsed.delete(key);
  else uiState.collapsed.add(key);
  saveUiState();
}
function isCollapsed(key) { return uiState.collapsed.has(key); }

const THEME_KEY = "vidux:theme";
function getStoredTheme() {
  try { return localStorage.getItem(THEME_KEY) || "system"; }
  catch (e) { return "system"; }
}
function resolveTheme(stored) {
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}
function applyTheme(stored) {
  const resolved = resolveTheme(stored);
  const root = document.documentElement;
  root.classList.toggle("theme-dark", resolved === "dark");
  root.classList.toggle("theme-light", resolved === "light");
  // Update button label/aria — moon for light (clicks to dark), sun for dark.
  const btn = document.getElementById("theme-toggle");
  if (btn) {
    btn.textContent = resolved === "dark" ? "☀" : "☾";
    const nextLabel = resolved === "dark" ? "Switch to light theme" : "Switch to dark theme";
    btn.setAttribute("aria-label", nextLabel);
    btn.setAttribute("title", nextLabel);
  }
}
function cycleTheme() {
  // light ↔ dark; system is only the unset default.
  const current = resolveTheme(getStoredTheme());
  const next = current === "dark" ? "light" : "dark";
  try { localStorage.setItem(THEME_KEY, next); }
  catch (e) { /* localStorage full or disabled */ }
  applyTheme(next);
}
// Apply on script load (before render) to avoid FOUC.
applyTheme(getStoredTheme());
// Track OS preference changes when no explicit override is set.
if (window.matchMedia) {
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (getStoredTheme() === "system") applyTheme("system");
  });
}

// Simple/Advanced mode — default Simple. vidux started as a plan browser and
// accreted AI-agent-operator tooling (raw session transcripts, JSONL ledger
// rows, local-runtime diagnostics, a cross-repo fleet view) into the same
// default surface; someone who isn't the engineer who built it should be
// able to open this and see their plan/tasks/progress without wading through
// any of that. Advanced mode restores it all for the operator use case.
const ADVANCED_MODE_KEY = "vidux:advancedMode";
function isAdvancedMode() {
  try { return localStorage.getItem(ADVANCED_MODE_KEY) === "1"; }
  catch (e) { return false; }
}
function applyAdvancedModeUI() {
  const advanced = isAdvancedMode();
  // Toggle on <html> (documentElement), matching the inline FOUC guard in
  // index.html's <head> -- that guard sets the class before <body> exists,
  // so both must target the same element or the class fights itself.
  document.documentElement.classList.toggle("advanced-mode", advanced);
  const btn = document.getElementById("mode-toggle");
  if (btn) {
    btn.textContent = advanced ? "Simple view" : "Advanced view";
    btn.setAttribute("aria-pressed", String(advanced));
    btn.title = advanced
      ? "Switch to the simple plan/progress view"
      : "Switch to the advanced view (session logs, ledger, local diagnostics, fleet dashboard)";
  }
}
function toggleAdvancedMode() {
  const next = !isAdvancedMode();
  try { localStorage.setItem(ADVANCED_MODE_KEY, next ? "1" : "0"); }
  catch (e) { /* localStorage full or disabled */ }
  applyAdvancedModeUI();
  // Dropping to Simple while parked on an advanced-only tab would otherwise
  // still render that tab's content with no visible tab button pointing at
  // it (the tabs array excludes it, but activeTab/isSessionActive etc. don't
  // know that) — snap back to PLAN.md so the UI stays consistent.
  if (!next && [DECISION_LOG_TAB, SESSION_TAB, LEDGER_TAB].includes(state.activeTab)) {
    state.activeTab = "PLAN.md";
  }
  // Re-render whatever's on screen so the newly shown/hidden panels take
  // effect immediately instead of waiting for the next navigation.
  if (state.active && state.active.kind === "dashboard") selectDashboard({ skipUrl: true, preserveScroll: true });
  else if (state.active && state.active.kind === "plan") renderPane({ preserveScroll: true, preserveAnnotation: true });
}
applyAdvancedModeUI();

// Parent plan that lists `child` in children, or null.
function findParentPlan(child) {
  if (!child || !child.parent_rel) return null;
  for (const p of state.plans) {
    if (p.children && p.children.some(c => c.path === child.path)) return p;
  }
  return null;
}

// Root→leaf ancestor chain; cycle-safe, max depth 8.
function ancestorChain(plan) {
  const chain = [];
  const seen = new Set();
  let current = plan;
  while (current && chain.length < 8) {
    const parent = findParentPlan(current);
    if (!parent || seen.has(parent.path)) break;
    seen.add(parent.path);
    chain.unshift(parent);
    current = parent;
  }
  return chain;
}

// Completion bar: segments by status; 100% = shipped gold.
const PROGRESS_ORDER = ["completed", "in_progress", "in_review", "blocked", "pending"];
const PROGRESS_LABELS = {
  completed: "done",
  in_progress: "in flight",
  in_review: "in review",
  blocked: "blocked",
  pending: "pending",
};

function pct(done, total) {
  if (!total) return 0;
  return Math.round((done / total) * 100);
}

function renderProgressBar(stats, klass = "") {
  const total = stats?.total || 0;
  if (!total) return `<div class="progress-bar is-empty ${klass}"></div>`;
  const c = stats.counts || {};
  const isShipped = (c.completed || 0) === total;
  const cls = `progress-bar ${isShipped ? "is-shipped" : ""} ${klass}`.trim();
  const segs = PROGRESS_ORDER.map(k => {
    const n = c[k] || 0;
    if (!n) return "";
    return `<div class="segment segment-${k}" style="flex-grow: ${n}" title="${n} ${PROGRESS_LABELS[k]}"></div>`;
  }).join("");
  return `<div class="${cls}">${segs}</div>`;
}

function renderProgressLabel(stats, invCount = 0) {
  const total = stats?.total || 0;
  const done = stats?.counts?.completed || 0;
  const invHTML = invCount ? `<span class="inv-count">⨠ ${invCount} inv</span>` : "";
  if (!total) {
    return `<div class="progress-label is-empty">no tasks yet${invHTML ? "" : ""}${invHTML}</div>`;
  }
  const isShipped = done === total;
  const head = isShipped
    ? `<span class="shipped-mark">shipped ✓</span>`
    : `<span class="pct">${pct(done, total)}%</span>`;
  return `<div class="progress-label">${head}<span>${done}/${total} done</span>${invHTML}</div>`;
}

function renderPaneProgress(stats) {
  const total = stats?.total || 0;
  if (!total) {
    return `<div class="pane-progress no-tasks">no tasks defined yet — add a <code>## Tasks</code> section to drive the bar</div>`;
  }
  const c = stats.counts || {};
  const done = c.completed || 0;
  const isShipped = done === total;
  const summary = PROGRESS_ORDER.map(k => {
    const n = c[k] || 0;
    const cls = `stat-${k}${n ? "" : " stat-zero"}`;
    return `<span class="${cls}">${n} ${PROGRESS_LABELS[k]}</span>`;
  }).join("");
  const pctText = isShipped
    ? `<span class="pct-large is-shipped">shipped ✓</span>`
    : `<span class="pct-large">${pct(done, total)}%</span>`;
  return `
    <div class="pane-progress ${isShipped ? "is-shipped" : ""}">
      <div class="progress-headline">
        <div>
          <div class="label">Completion</div>
          <div class="ratio">${done} of ${total} tasks</div>
        </div>
        ${pctText}
      </div>
      ${renderProgressBar(stats)}
      <div class="progress-summary">${summary}</div>
    </div>`;
}

// Render the parent's aggregate (rolled-up across sub-plans) progress block.
// Only emitted when the plan actually has children — a leaf plan would just
// repeat its own bar, which is noise.
function renderPaneAggregateProgress(plan, aggregate) {
  if (!planHasChildren(plan)) return "";
  const total = aggregate?.total || 0;
  if (!total) return "";
  const c = aggregate.counts || {};
  const done = c.completed || 0;
  const isShipped = done === total;
  const pctText = isShipped
    ? `<span class="pct-large is-shipped">shipped ✓</span>`
    : `<span class="pct-large">${pct(done, total)}%</span>`;
  const summary = PROGRESS_ORDER.map(k => {
    const n = c[k] || 0;
    const cls = `stat-${k}${n ? "" : " stat-zero"}`;
    return `<span class="${cls}">${n} ${PROGRESS_LABELS[k]}</span>`;
  }).join("");
  return `
    <div class="pane-progress pane-progress-rollup ${isShipped ? "is-shipped" : ""}">
      <div class="progress-headline">
        <div>
          <div class="label">With sub-plans (${aggregate.descendants || 0})</div>
          <div class="ratio">${done} of ${total} tasks across this branch</div>
        </div>
        ${pctText}
      </div>
      ${renderProgressBar(aggregate)}
      <div class="progress-summary">${summary}</div>
    </div>`;
}

function doctorStatusClass(status) {
  if (status === "block") return "is-blocked";
  if (status === "warn") return "is-warn";
  if (status === "pass" || status === "ok") return "is-ok";
  return "is-muted";
}

function cacheStatusClass(status) {
  if (status === "fresh") return "is-ok";
  if (status === "stale") return "is-warn";
  return "is-muted";
}

function shortLocalPath(path) {
  const value = String(path || "");
  if (!value) return "";
  const homeMatch = value.match(/^\/Users\/[^/]+/);
  if (homeMatch) return `~${value.slice(homeMatch[0].length)}`;
  return value;
}

function renderOpsTruth() {
  if (!isAdvancedMode()) return "";
  const truth = state.opsTruth;
  if (!truth) {
    return `
      <section class="ops-truth is-loading" id="ops-truth" aria-label="Vidux local truth">
        <div class="ops-truth-head">
          <span class="ops-kicker">Local truth</span>
          <span class="ops-chip is-muted">loading</span>
        </div>
      </section>`;
  }
  if (truth.error) {
    return `
      <section class="ops-truth is-error" id="ops-truth" aria-label="Vidux local truth">
        <div class="ops-truth-head">
          <span class="ops-kicker">Local truth</span>
          <span class="ops-chip is-blocked">error</span>
        </div>
        <div class="ops-truth-error">${escapeText(truth.error)}</div>
      </section>`;
  }

  const config = truth.config || {};
  const installDoctor = truth.install_doctor || {};
  const runtime = truth.runtime_doctor || {};
  const signposts = truth.signposts || {};
  const cache = truth.cache || {};
  const configStatus = config.ok ? "ok" : (config.status || "unknown");
  const runtimeStatus = runtime.status || "unknown";
  const cacheStatus = cache.status || "sync";
  const cacheLabel = cache.refreshing ? `${cacheStatus} refresh` : cacheStatus;
  const warningCount = Array.isArray(runtime.warnings) ? runtime.warnings.length : 0;
  const blockerCount = Array.isArray(runtime.blockers) ? runtime.blockers.length : 0;
  const systemMemory = runtime.system_memory || {};
  const memoryPct = Number(systemMemory.memory_pressure_free_pct);
  const vmFree = Number(systemMemory.vm_free_mb);
  const vmSpeculative = Number(systemMemory.vm_speculative_mb);
  const runtimeNote = blockerCount
    ? `${blockerCount} blocker${blockerCount === 1 ? "" : "s"}`
    : (warningCount ? `${warningCount} warning${warningCount === 1 ? "" : "s"}` : "no blockers");
  const memoryNote = Number.isFinite(memoryPct)
    ? `${runtimeNote} | memory_pressure ${memoryPct}%`
    : runtimeNote;
  const memoryTitleParts = [
    Number.isFinite(memoryPct)
      ? `${systemMemory.memory_pct_source || "memory_pressure"}: ${memoryPct}%`
      : "",
    Number.isFinite(vmFree)
      ? `${systemMemory.vm_pages_source || "vm_stat"} free ${vmFree} MB`
      : "",
    Number.isFinite(vmSpeculative)
      ? `speculative ${vmSpeculative} MB`
      : "",
  ].filter(Boolean);
  const memoryTitle = memoryTitleParts.join("; ");
  const configNote = config.live_config_present
    ? "live config"
    : (config.using_example ? "example fallback" : "no config");
  const signpostEvents = Number(signposts.total_events || 0);
  const latestSignpostRun = signposts.latest_run || {};
  const latestCallStack = latestSignpostRun.call_stack || "";
  const signpostDetail = latestCallStack || shortLocalPath(signposts.log_path);
  const signpostTitle = latestCallStack
    ? [
        `run ${latestSignpostRun.run_id || "unknown"}`,
        latestSignpostRun.complete_lifecycle ? "complete lifecycle" : "partial lifecycle",
        Array.isArray(latestSignpostRun.actions) ? latestSignpostRun.actions.join(" > ") : "",
        shortLocalPath(signposts.log_path),
      ].filter(Boolean).join("; ")
    : shortLocalPath(signposts.log_path);
  const updated = truth.generated_at ? truth.generated_at.replace("T", " ").replace("Z", "Z") : "";
  return `
    <section class="ops-truth" id="ops-truth" aria-label="Vidux local truth">
      <div class="ops-truth-head">
        <span class="ops-kicker">Local truth</span>
        <span class="ops-chip ${doctorStatusClass(configStatus)}">config ${escapeText(configStatus)}</span>
        <span class="ops-chip ${doctorStatusClass(runtimeStatus)}">runtime ${escapeText(runtimeStatus)}</span>
        <span class="ops-chip ${cacheStatusClass(cacheStatus)}">${escapeText(cacheLabel)}</span>
        <span class="ops-chip is-muted">${escapeText(updated)}</span>
      </div>
      <div class="ops-truth-grid">
        <div class="ops-truth-item">
          <span>Config</span>
          <strong>${escapeText(config.source || "unknown")}</strong>
          <small title="${escapeAttr(config.path || "")}">${escapeText(configNote)}</small>
        </div>
        <div class="ops-truth-item">
          <span>Runtime doctor</span>
          <strong>${Number(runtime.pass || 0)}/${Number(runtime.total || 0)}</strong>
          <small title="${escapeAttr(memoryTitle)}">${escapeText(memoryNote)}</small>
        </div>
        <div class="ops-truth-item">
          <span>Pre-hook</span>
          <strong>${escapeText(runtime.command || "scripts/vidux-doctor.sh --json")}</strong>
          <small>${installDoctor.browser_status === "not_run" ? "install doctor not run here" : "runtime JSON"}</small>
        </div>
        <div class="ops-truth-item">
          <span>Signposts</span>
          <strong>${signpostEvents}</strong>
          <small title="${escapeAttr(signpostTitle)}">${escapeText(signpostDetail)}</small>
        </div>
      </div>
    </section>`;
}

function dashboardCategories() {
  return state.dashboard?.categories || {};
}

function dashboardCategory(key) {
  return dashboardCategories()[key] || { label: key, items: [], total: 0, truncated: false, limit: 0 };
}

function dashboardTotalOpen() {
  const cats = dashboardCategories();
  return Object.values(cats).reduce((sum, cat) => sum + Number(cat?.total || 0), 0);
}

function renderDashboardCard(key, label) {
  const cat = dashboardCategory(key);
  const total = Number(cat.total || 0);
  const shown = Array.isArray(cat.items) ? cat.items.length : 0;
  const note = cat.truncated ? `${shown}/${total} shown` : `${total} total`;
  return `
    <div class="dashboard-card dashboard-card-${escapeAttr(key)}">
      <span>${escapeText(label)}</span>
      <strong>${total}</strong>
      <small>${escapeText(note)}</small>
    </div>`;
}

function renderDashboardItem(item) {
  const proof = item.proof_rel || item.proof_path || "";
  const meta = [
    item.repo || "",
    item.source_rel ? `${item.source_rel}${item.line ? `:${item.line}` : ""}` : "",
    proof ? `proof ${shortLocalPath(proof)}` : "",
  ].filter(Boolean).join(" · ");
  const status = item.status || item.kind || "open";
  return `
    <article class="dashboard-item dashboard-item-${escapeAttr(item.kind || "item")}" tabindex="0" role="button"
      data-dashboard-rel="${escapeAttr(item.rel || "")}"
      data-dashboard-tab="${escapeAttr(item.tab || "PLAN.md")}"
      aria-label="${escapeAttr(`${status}: ${item.label || ""}`)}">
      <div class="dashboard-item-head">
        <span class="dashboard-status status-${escapeAttr(status)}">${escapeText(status)}</span>
        <span class="dashboard-label">${escapeText(item.label || "Untitled item")}</span>
      </div>
      <div class="dashboard-meta">${escapeText(meta)}</div>
    </article>`;
}

function renderDashboardList(key, title, emptyText) {
  const cat = dashboardCategory(key);
  const items = Array.isArray(cat.items) ? cat.items : [];
  const total = Number(cat.total || 0);
  const countLabel = cat.truncated ? `${items.length}/${total}` : `${total}`;
  const body = items.length
    ? items.map(renderDashboardItem).join("")
    : `<p class="muted dashboard-empty">${escapeText(emptyText)}</p>`;
  return `
    <section class="dashboard-list dashboard-list-${escapeAttr(key)}">
      <div class="dashboard-list-head">
        <h3>${escapeText(title)}</h3>
        <span>${escapeText(countLabel)}</span>
      </div>
      <div class="dashboard-items">${body}</div>
    </section>`;
}

function openDashboardItem(row) {
  const rel = row.getAttribute("data-dashboard-rel");
  const tab = row.getAttribute("data-dashboard-tab") || "PLAN.md";
  const plan = state.plans.find(p => p.rel === rel);
  if (plan) selectPlan(plan, { tab, scrollIntoView: true });
}

function setupDashboardPane() {
  els.pane.querySelectorAll(".dashboard-item").forEach(row => {
    row.addEventListener("click", () => openDashboardItem(row));
    row.addEventListener("keydown", e => {
      if (e.key !== "Enter" && e.key !== " ") return;
      e.preventDefault();
      openDashboardItem(row);
    });
  });
}

function renderDashboardPane(opts = {}) {
  const scrollTop = opts.preserveScroll ? els.pane.scrollTop : 0;
  if (!opts.preserveAnnotation) clearAnnotationState();
  const dashboard = state.dashboard || {};
  const generated = dashboard.generated_at ? dashboard.generated_at.replace("T", " ").replace("Z", "Z") : "";
  els.pane.innerHTML = `
    ${renderOpsTruth()}
    <section class="dashboard-panel">
      <div class="dashboard-header">
        <div>
          <div class="label">Fleet dashboard</div>
          <h2>Cross-plan queue</h2>
        </div>
        <div class="dashboard-header-meta">
          <span>${Number(dashboard.plans_scanned || state.plans.length)} plans</span>
          <span>${Number(dashboard.repos || new Set(state.plans.map(p => p.repo)).size)} repos</span>
          ${generated ? `<span>${escapeText(generated)}</span>` : ""}
        </div>
      </div>
      <div class="dashboard-cards">
        ${renderDashboardCard("in_progress", "In progress")}
        ${renderDashboardCard("blocked", "Blocked")}
        ${renderDashboardCard("verdicts", "Verdicts")}
        ${renderDashboardCard("decisions", "Decisions")}
        ${renderDashboardCard("ask_leo", "ASK-LEO")}
        ${renderDashboardCard("inbox", "INBOX")}
      </div>
      <div class="dashboard-grid">
        ${renderDashboardList("in_progress", "In Progress", "No in-progress tasks found.")}
        ${renderDashboardList("blocked", "Blocked", "No blocked tasks found.")}
        ${renderDashboardList("verdicts", "Recent Verdicts", "No verdict receipts found.")}
        ${renderDashboardList("decisions", "Recent Decisions", "No recent decisions found.")}
        ${renderDashboardList("ask_leo", "ASK-LEO", "No open ASK-LEO entries found.")}
        ${renderDashboardList("inbox", "INBOX", "No open INBOX entries found.")}
      </div>
    </section>`;
  if (opts.preserveScroll) els.pane.scrollTop = scrollTop;
  else els.pane.scrollTop = 0;
  setupDashboardPane();
  refreshAnnotationTargets();
}

function renderEmptyPane() {
  els.pane.innerHTML = `
    ${renderOpsTruth()}
    <div class="pane-empty muted">
      <p>Select a plan from the sidebar.</p>
      <p>40+ PLAN.md files indexed across <code>~/Development/</code>.</p>
    </div>`;
}

function updateOpsTruthSurface() {
  const el = document.getElementById("ops-truth");
  if (el) el.outerHTML = renderOpsTruth();
}

async function refreshOpsTruth() {
  if (opsTruthRetryTimer) {
    window.clearTimeout(opsTruthRetryTimer);
    opsTruthRetryTimer = null;
  }
  try {
    const res = await fetch("/api/vidux/truth");
    if (!res.ok) {
      state.opsTruth = { error: `${res.status}: ${await res.text()}` };
    } else {
      state.opsTruth = await res.json();
    }
  } catch (e) {
    state.opsTruth = { error: String(e) };
  }
  updateOpsTruthSurface();
  const cache = state.opsTruth?.cache || {};
  if (cache.status === "warming" || cache.refreshing) {
    opsTruthRetryTimer = window.setTimeout(refreshOpsTruth, 1200);
  }
}

function renderPlanBrief(plan, stats, aggregate) {
  const brief = plan.brief || {};
  const counts = stats?.counts || {};
  const total = stats?.total || 0;
  const done = counts.completed || 0;
  const openCount = Number.isFinite(Number(brief.open_count))
    ? Number(brief.open_count)
    : Math.max(total - done, 0);
  const stateLabel = brief.state || (total ? `${pct(done, total)}%` : plan.status);
  const rollupText = planHasChildren(plan) && aggregate?.total
    ? `${aggregate.counts?.completed || 0}/${aggregate.total} with sub-plans`
    : "";
  const focusTasks = Array.isArray(brief.focus_tasks) ? brief.focus_tasks : [];
  const focusHTML = focusTasks.length
    ? focusTasks.map(task => `
        <li class="plan-brief-task">
          <span class="plan-brief-status status-${escapeAttr(task.status || "pending")}">${escapeText(task.status || "pending")}</span>
          <span class="plan-brief-task-label">${escapeText(task.label || "")}</span>
          ${isAdvancedMode() ? `<a class="plan-brief-code-link" href="${escapeAttr(codingWorkbenchUrl(plan, task))}" target="_blank" rel="noreferrer" title="Open in Moussey coding workbench">Code lane</a>` : ""}
        </li>`).join("")
    : `<li class="plan-brief-task is-empty">No active task rows yet.</li>`;
  const latestHTML = [
    brief.latest_progress ? `<p><span>Progress</span>${escapeText(brief.latest_progress)}</p>` : "",
    brief.latest_decision ? `<p><span>Decision</span>${escapeText(brief.latest_decision)}</p>` : "",
  ].filter(Boolean).join("");
  return `
    <section class="plan-brief" aria-label="Plan now">
      <div class="plan-brief-main">
        <div class="plan-brief-kicker">Now</div>
        <p class="plan-brief-summary">${escapeText(brief.summary || plan.purpose || "No purpose summary yet.")}</p>
        <div class="plan-brief-stats">
          <span>${escapeText(stateLabel)}</span>
          <span>${openCount} open</span>
          <span>${done}/${total} done</span>
          ${rollupText ? `<span>${escapeText(rollupText)}</span>` : ""}
        </div>
        ${latestHTML ? `<div class="plan-brief-latest">${latestHTML}</div>` : ""}
      </div>
      <div class="plan-brief-side">
        <div class="plan-brief-focus">
          <div class="plan-brief-side-label">Focus</div>
          <ul>${focusHTML}</ul>
        </div>
        <form class="plan-steering" data-plan-path="${escapeAttr(plan.path)}">
          <label for="plan-steering-body">Steer this plan</label>
          <textarea id="plan-steering-body" name="body" rows="3" maxlength="8192" placeholder="Drop direction here"></textarea>
          <div class="plan-steering-actions">
            <span class="plan-steering-status" role="status" aria-live="polite"></span>
            <button type="submit">Send</button>
          </div>
        </form>
      </div>
    </section>`;
}

function codingWorkbenchUrl(plan, task) {
  const params = new URLSearchParams();
  params.set("viduxPlan", plan.rel || plan.path || "");
  params.set("viduxTask", task?.label || "");
  params.set("viduxTaskStatus", task?.status || "pending");
  return `http://127.0.0.1:4321/coding?${params.toString()}`;
}

// Render an at-a-glance list of immediate children with their own mini bars.
// Each row has an "open" button that re-uses selectPlan() — same code path
// the sidebar takes — so the URL deep-link behavior stays consistent.
function renderPaneSubplans(plan) {
  if (!planHasChildren(plan)) return "";
  const rows = plan.children.map(child => {
    const stats = child.task_stats || { counts: {}, total: 0 };
    const childAgg = child.aggregate_stats || stats;
    const slug = child.slug === "_root_" ? "(root)" : child.slug;
    const total = stats?.total || 0;
    const done = stats?.counts?.completed || 0;
    const subplanCount = (child.aggregate_stats?.descendants) || 0;
    return `
      <div class="subplan-row" data-subplan-rel="${escapeAttr(child.rel)}">
        <div class="subplan-row-head">
          <span class="pill pill-${child.status}" title="${child.status} · ${fmtAge(child.age_days)}"></span>
          <span class="subplan-row-slug">${escapeText(slug)}</span>
          ${subplanCount ? `<span class="child-count" title="${subplanCount} descendant${subplanCount === 1 ? "" : "s"}">⌐${subplanCount}</span>` : ""}
          <span class="subplan-open-hint" aria-hidden="true">→ open</span>
        </div>
        ${child.purpose ? `<div class="subplan-row-purpose">${escapeText(child.purpose)}</div>` : ""}
        <div class="subplan-row-progress">
          ${renderProgressBar(stats)}
          <span class="subplan-row-label">${total ? `${done}/${total} done` : "no tasks"}</span>
        </div>
      </div>`;
  }).join("");
  return `
    <section class="pane-subplans">
      <h3>Sub-plans <span class="muted">(${plan.children.length})</span></h3>
      ${rows}
    </section>`;
}

function formatEtaHours(hours) {
  const value = Math.round(Number(hours || 0) * 100) / 100;
  if (Number.isInteger(value)) return `${value}h`;
  return `${value.toFixed(2).replace(/\.?0+$/, "")}h`;
}

function fallbackFleetSummary(plans, repoCount) {
  let done = 0, total = 0;
  let etaRemaining = 0;
  let etaTagged = 0;
  let etaEligible = 0;
  for (const p of plans) {
    const t = p.task_stats;
    if (!t) continue;
    done += t.counts?.completed || 0;
    total += t.total || 0;
    etaRemaining += Number(t.eta_total || 0);
    etaTagged += Number(t.eta_tagged || 0);
    etaEligible += Number(t.eta_eligible || 0);
  }
  etaRemaining = Math.round(etaRemaining * 100) / 100;
  return {
    plans: plans.length,
    repos: repoCount,
    tasks_completed: done,
    tasks_total: total,
    completion_pct: pct(done, total),
    eta_remaining_hours: etaRemaining,
    eta_remaining_label: `${formatEtaHours(etaRemaining)} remaining`,
    eta_tagged: etaTagged,
    eta_eligible: etaEligible,
  };
}

function topbarFleetSummary(plans, artifacts, repoCount) {
  const summary = state.fleetSummary || fallbackFleetSummary(plans, repoCount);
  const planCount = Number(summary.plans ?? plans.length);
  const summaryRepoCount = Number(summary.repos ?? repoCount);
  const artifactCount = artifacts.length;
  const total = Number(summary.tasks_total || 0);
  const done = Number(summary.tasks_completed || 0);
  const completionPct = Number(summary.completion_pct ?? pct(done, total));
  const etaLabel = summary.eta_remaining_label
    || `${formatEtaHours(summary.eta_remaining_hours || 0)} remaining`;
  const taskStat = total ? ` · ${done}/${total} tasks (${completionPct}%)` : "";
  return `${planCount} plans · ${summaryRepoCount} repos · ${artifactCount} artifacts${taskStat} · ${etaLabel}`;
}

// Plans whose `parent_rel` matches another plan's `rel` are surfaced as
// indented children under that parent in the sidebar. Children are rendered
// immediately after their parent so the visual lineage matches the data.
function planHasChildren(plan) {
  return Array.isArray(plan.children) && plan.children.length > 0;
}

function isOrphanChild(plan, byRel) {
  const parentRel = plan?.parent_rel;
  if (!parentRel) return false;
  return byRel.has(parentRel);
}

function hydratePlanChildren() {
  const byRel = new Map(state.plans.map(plan => [plan.rel, plan]));
  for (const plan of state.plans) {
    const childRels = Array.isArray(plan.child_rels) ? plan.child_rels : [];
    plan.children = childRels.map(rel => byRel.get(rel)).filter(Boolean);
  }
}

function activateSidebarRow(row) {
  const kind = row.getAttribute("data-kind");
  const path = row.getAttribute("data-path");
  if (kind === "dashboard") {
    selectDashboard();
  } else if (kind === "artifact") {
    const a = state.artifacts.find(x => x.path === path);
    if (a) selectArtifact(a);
  } else {
    const plan = state.plans.find(p => p.path === path);
    if (plan) selectPlan(plan);
  }
}

function renderSidebar() {
  const filter = state.filter.toLowerCase();
  const chipFilterActive = sidebarFilters.active(state.filterChips);

  const filteredPlans = state.plans.filter(p => {
    const textMatch = !filter ||
        p.repo.toLowerCase().includes(filter) ||
        p.slug.toLowerCase().includes(filter) ||
        (p.purpose || "").toLowerCase().includes(filter);
    return textMatch && sidebarFilters.matches(p, state.filterChips);
  });

  const filteredArtifacts = chipFilterActive ? [] : (filter
    ? state.artifacts.filter(a =>
        a.slug.toLowerCase().includes(filter) ||
        (a.title || "").toLowerCase().includes(filter))
    : state.artifacts);
  const visiblePlanRels = new Set(filteredPlans.map(p => p.rel));
  const visibleArtifactSlugs = new Set(filteredArtifacts.map(a => a.slug));

  // Build a rel→plan lookup over the FILTERED set so child indentation only
  // happens when both parent and child survive the filter. A child whose
  // parent was filtered out shows up at the top level instead of orphaned
  // under nothing.
  const byRel = new Map();
  for (const plan of filteredPlans) byRel.set(plan.rel, plan);
  // Only include plans at the "top level" (no surviving parent) in repo
  // grouping. Surviving children are rendered inline below their parent.
  const topLevelPlans = filteredPlans.filter(p => !isOrphanChild(p, byRel));

  const groups = new Map();
  for (const plan of topLevelPlans) {
    if (!groups.has(plan.repo)) groups.set(plan.repo, []);
    groups.get(plan.repo).push(plan);
  }

  els.count.textContent = topbarFleetSummary(state.plans, state.artifacts, groups.size);

  if (filteredPlans.length === 0 && filteredArtifacts.length === 0) {
    // Differentiate "no filter match" from "nothing indexed at all". The
    // latter is a first-run / wrong-VIDUX_DEV_ROOT signal that deserves
    // a hint, not a one-word "no matches".
    const noResults = state.plans.length === 0 && state.artifacts.length === 0;
    const activeFilterLabel = state.filter
      ? `"${escapeText(state.filter)}"`
      : escapeText(sidebarFilters.summary(state.filterChips) || "current filters");
    els.list.innerHTML = noResults
      ? `<div class="empty-state">
          <p><strong>No plans or artifacts found.</strong></p>
          <p>vidux-browse looks for <code>PLAN.md</code> files under the dev-root directory.</p>
          <p>Try:</p>
          <ul>
            <li>Add a <code>PLAN.md</code> to a project inside your dev-root</li>
            <li>Set <code>VIDUX_DEV_ROOT</code> or pass <code>--root &lt;path&gt;</code> when launching</li>
            <li>Click <strong>↻ refresh</strong> after adding plans</li>
          </ul>
        </div>`
      : `<p class="muted" style="padding:12px">no matches for ${activeFilterLabel}</p>`;
    refreshAnnotationTargetsIfNeeded();
    return;
  }

  // Helpers for collapsible group headers — used by recents, artifacts, repos.
  // Disclosure caret on left, count on right. Click toggles persisted state.
  // Keyboard parity (WCAG 2.1.1): tabindex + role=button + Enter/Space toggle
  // the same as click, matching the .plan-row keyboard-activation pattern.
  function groupHeaderHTML(key, label, count) {
    const collapsed = isCollapsed(key);
    const caret = collapsed ? "▸" : "▾";
    const cls = collapsed ? "is-collapsed" : "";
    return `<div class="repo-group ${cls}" data-collapse-key="${escapeAttr(key)}">
      <h2 tabindex="0" role="button" aria-expanded="${collapsed ? "false" : "true"}" aria-label="${escapeAttr(`${label}, ${count} items, ${collapsed ? "collapsed" : "expanded"}`)}"><span class="caret">${caret}</span>${escapeText(label)} <span class="repo-count">(${count})</span></h2>
    </div>`;
  }
  function artifactRow(a) {
    const active = state.active && state.active.kind === "artifact" && state.active.path === a.path ? "is-active" : "";
    const fullSlug = `${a.slug}.html`;
    return `
      <div class="plan-row ${active}" data-kind="artifact" data-path="${escapeAttr(a.path)}" tabindex="${active ? "0" : "-1"}" role="option" aria-selected="${active ? "true" : "false"}" aria-label="${escapeAttr(`Artifact: ${a.title || a.slug}, ${fmtAge(a.age_days)}`)}">
        <div class="plan-row-head">
          <span class="pill pill-artifact" title="artifact · ${fmtAge(a.age_days)}"></span>
          <span>${escapeText(a.title || a.slug)}</span>
        </div>
        <div class="plan-row-meta">
          <span title="${escapeAttr(fullSlug)}">${escapeText(fullSlug)}</span>
          <span>${fmtAge(a.age_days)}</span>
          <span>${(a.size / 1024).toFixed(1)}KB</span>
        </div>
      </div>`;
  }

  function dashboardRow() {
    // Fleet dashboard spans every PLAN.md vidux can find under
    // ~/Development/ -- i.e. every project, not "my plan." Advanced-only.
    if (!isAdvancedMode()) return "";
    const active = state.active && state.active.kind === "dashboard" ? "is-active" : "";
    const total = dashboardTotalOpen();
    const cats = dashboardCategories();
    const meta = [
      `${Number(cats.in_progress?.total || 0)} in progress`,
      `${Number(cats.blocked?.total || 0)} blocked`,
      `${Number(cats.verdicts?.total || 0)} verdicts`,
      `${Number(cats.decisions?.total || 0)} decisions`,
      `${Number(cats.ask_leo?.total || 0)} ask`,
      `${Number(cats.inbox?.total || 0)} inbox`,
    ].join(" · ");
    return `
      <div class="plan-row dashboard-row ${active}" data-kind="dashboard" data-path="dashboard" tabindex="${active ? "0" : "-1"}" role="option" aria-selected="${active ? "true" : "false"}" aria-label="${escapeAttr(`Fleet dashboard, ${total} items`)}">
        <div class="plan-row-head">
          <span class="pill pill-artifact" title="fleet dashboard"></span>
          <span>Fleet dashboard</span>
        </div>
        <div class="plan-row-purpose">Cross-plan queue</div>
        <div class="plan-row-meta">
          <span>${escapeText(meta)}</span>
        </div>
      </div>`;
  }

  // Recently viewed — top of sidebar. Drawn from localStorage. Shows up to
  // RECENTS_MAX items that still resolve to a plan/artifact in current state.
  let recentsHTML = "";
  const recentItems = uiState.recents
    .map(r => {
      const colon = r.id.indexOf(":");
      if (colon < 0) return null;
      const kind = r.id.slice(0, colon);
      const key = r.id.slice(colon + 1);
      if (kind === "plan") {
        const plan = state.plans.find(p => p.rel === key);
        return plan && visiblePlanRels.has(plan.rel) ? { kind, plan } : null;
      } else if (kind === "artifact") {
        const a = state.artifacts.find(x => x.slug === key);
        return a && visibleArtifactSlugs.has(a.slug) ? { kind, a } : null;
      }
      return null;
    })
    .filter(Boolean)
    .slice(0, RECENTS_MAX);
  if (recentItems.length) {
    const header = groupHeaderHTML("section:recents", "recently viewed", recentItems.length);
    if (isCollapsed("section:recents")) {
      recentsHTML = header;
    } else {
      const rows = recentItems.map(r => {
        if (r.kind === "plan") return renderPlanRow(r.plan, 0);
        return artifactRow(r.a);
      }).join("");
      recentsHTML = header + rows;
    }
  }

  // Artifacts section.
  let artifactsHTML = "";
  if (filteredArtifacts.length) {
    const header = groupHeaderHTML("section:artifacts", "artifacts", filteredArtifacts.length);
    if (isCollapsed("section:artifacts")) {
      artifactsHTML = header;
    } else {
      artifactsHTML = header + filteredArtifacts.map(artifactRow).join("");
    }
  }

  // Recursive row renderer — emits a parent followed by its children at one
  // higher indent depth. A child whose own children survive the filter keeps
  // recursing. depth=0 is the top-level repo-row look; depth>=1 gets the
  // `.is-child` modifier styled in style.css.
  function renderPlanRow(plan, depth) {
    const active = state.active && state.active.kind === "plan" && state.active.path === plan.path ? "is-active" : "";
    const isRoot = plan.slug === "_root_";
    const slug = isRoot ? `${plan.repo}/PLAN.md` : plan.slug;
    const stats = plan.task_stats || { counts: {}, total: 0 };
    const agg = plan.aggregate_stats || stats;
    const hasChildren = planHasChildren(plan);
    const invCount = (plan.investigations || []).length;
    const childModifier = depth > 0 ? `is-child is-child-${Math.min(depth, 4)}` : "";
    const indentStyle = depth > 0 ? `style="--child-depth:${depth}"` : "";
    // Parent rows show an own-tasks bar AND an aggregate (with-sub-plans) bar.
    // Plans without children only need one bar — use the existing single-bar
    // treatment so leaf rows look unchanged from the pre-rollup UI.
    // Always render the same wrapper structure so leaf and parent plans have
    // identical inter-item vertical rhythm. The rollup line is conditional;
    // the wrapper + first .progress-row-line is invariant. This kills the
    // ~24px height delta that produced visible gutter inconsistency.
    const progressHTML = `
          <div class="progress-row${hasChildren ? " progress-row-with-rollup" : ""}">
            <div class="progress-row-line">
              ${hasChildren ? `<span class="progress-row-tag">this plan</span>` : ""}
              ${renderProgressBar(stats, hasChildren ? "is-self" : "")}
              ${renderProgressLabel(stats, invCount)}
            </div>
            ${hasChildren ? `
            <div class="progress-row-line">
              <span class="progress-row-tag is-rollup">+ sub-plans (${agg.descendants || 0})</span>
              ${renderProgressBar(agg, "is-rollup")}
              ${renderProgressLabel(agg, 0)}
            </div>` : ""}
          </div>`;
    const ariaSummary = `${plan.status} plan: ${slug}${plan.purpose ? `, ${plan.purpose.slice(0, 80)}` : ""}, ${fmtAge(plan.age_days)}${hasChildren ? `, ${plan.children.length} sub-plan${plan.children.length === 1 ? "" : "s"}` : ""}`;
    const rowHTML = `
      <div class="plan-row ${active} ${childModifier}" data-kind="plan" data-path="${escapeAttr(plan.path)}" ${indentStyle} tabindex="${active ? "0" : "-1"}" role="option" aria-selected="${active ? "true" : "false"}" aria-label="${escapeAttr(ariaSummary)}" title="${escapeAttr(slug)}">
        <div class="plan-row-head">
          <span class="pill pill-${plan.status}" title="${plan.status} · ${fmtAge(plan.age_days)}"></span>
          <span>${escapeText(slug)}</span>
          ${hasChildren ? `<span class="child-count" title="${plan.children.length} sub-plan${plan.children.length === 1 ? "" : "s"}">⌐${plan.children.length}</span>` : ""}
        </div>
        ${plan.purpose ? `<div class="plan-row-purpose">${escapeText(plan.purpose)}</div>` : ""}
        <div class="plan-row-meta">
          <span>${fmtAge(plan.age_days)}</span>
          <span>${(plan.size / 1024).toFixed(1)}KB</span>
          ${plan.siblings.length ? `<span>+${plan.siblings.length}</span>` : ""}
        </div>
        ${progressHTML}
      </div>`;
    // Only render children that survived the filter — a filter that drops
    // a child plan should hide it from the indented list under its parent.
    const childRowsHTML = hasChildren
      ? sidebarSort.sortedPlans(plan.children.filter(child => byRel.has(child.rel)), state.sort)
          .map(child => renderPlanRow(child, depth + 1))
          .join("")
      : "";
    return rowHTML + childRowsHTML;
  }

  // Sort repos and rows by the selected sidebar mode. mtime remains the
  // default because recency reflects what the operator is actually touching;
  // ETA/status are explicit scan modes for queue-shaping.
  const repoOrder = [...groups.keys()].sort(sidebarSort.repoComparator(groups, state.sort));
  const plansHTML = repoOrder.map(repo => {
    const rows = sidebarSort.sortedPlans(groups.get(repo) || [], state.sort);
    const key = `repo:${repo}`;
    const header = groupHeaderHTML(key, repo, rows.length);
    if (isCollapsed(key)) return header;
    const inner = rows.map(plan => renderPlanRow(plan, 0)).join("");
    return header + inner;
  }).join("");

  els.list.innerHTML = dashboardRow() + recentsHTML + artifactsHTML + plansHTML;

  // Roving tabindex (ARIA APG listbox pattern): rows render tabindex="-1"
  // except the active one, so Tab has exactly one stop for the whole list
  // (arrow keys move within it) instead of stopping at every row. Nothing is
  // active on first load / after a filter clears the active row, so fall
  // back to the first row -- otherwise the list has zero tab stops and
  // becomes keyboard-unreachable.
  if (!els.list.querySelector('.plan-row[tabindex="0"]')) {
    els.list.querySelector(".plan-row")?.setAttribute("tabindex", "0");
  }

  // Click on group header → toggle collapsed state for that section/repo.
  // Enter/Space does the same (WCAG 2.1.1) -- these headers were mouse-only
  // before despite carrying role=button.
  els.list.querySelectorAll(".repo-group[data-collapse-key]").forEach(grp => {
    const h2 = grp.querySelector("h2");
    if (!h2) return;
    h2.addEventListener("click", () => {
      const key = grp.getAttribute("data-collapse-key");
      if (key) { toggleCollapsed(key); renderSidebar(); }
    });
    h2.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" && e.key !== " ") return;
      e.preventDefault();
      const key = grp.getAttribute("data-collapse-key");
      if (key) { toggleCollapsed(key); renderSidebar(); }
    });
  });

  if (!els.list.dataset.activationBound) {
    els.list.dataset.activationBound = "1";
    els.list.addEventListener("click", e => {
      const row = e.target.closest(".plan-row");
      if (!row || !els.list.contains(row)) return;
      activateSidebarRow(row);
    });
    // Keyboard parity (WCAG 2.1.1): Enter or Space activates the focused row,
    // matching click behavior. Space is preventDefault'd to stop page scroll.
    els.list.addEventListener("keydown", e => {
      if (e.key !== "Enter" && e.key !== " ") return;
      const row = e.target.closest(".plan-row");
      if (!row || !els.list.contains(row)) return;
      e.preventDefault();
      activateSidebarRow(row);
    });
  }

  // Arrow-key navigation within the sidebar list. Up/Down move focus to the
  // prev/next .plan-row (skipping group headers); Home/End jump to first/last;
  // Cmd/Ctrl+Enter focuses the pane after activating. Listener is delegated on
  // the list (not per-row) so it survives re-renders without re-binding.
  if (!els.list.dataset.kbdBound) {
    els.list.dataset.kbdBound = "1";
    els.list.addEventListener("keydown", (e) => {
      if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
      const target = e.target.closest(".plan-row");
      const rows = [...els.list.querySelectorAll(".plan-row")];
      if (!rows.length) return;
      let next;
      if (e.key === "Home") next = rows[0];
      else if (e.key === "End") next = rows[rows.length - 1];
      else {
        const idx = target ? rows.indexOf(target) : -1;
        const delta = e.key === "ArrowDown" ? 1 : -1;
        next = rows[Math.max(0, Math.min(rows.length - 1, idx + delta))];
      }
      if (next) {
        e.preventDefault();
        // Move the roving tabindex with focus (ARIA APG listbox pattern) --
        // exactly one row is a tab stop at any time.
        rows.forEach(r => r.setAttribute("tabindex", r === next ? "0" : "-1"));
        next.focus();
      }
    });
  }
  refreshAnnotationTargetsIfNeeded();
}

function currentSelectionSnapshot() {
  if (!state.active) return null;
  if (state.active.kind === "dashboard") {
    return { kind: "dashboard" };
  }
  if (state.active.kind === "plan") {
    return {
      kind: "plan",
      rel: state.active.rel,
      path: state.active.path,
      tab: state.activeTab || "PLAN.md",
    };
  }
  if (state.active.kind === "artifact") {
    return {
      kind: "artifact",
      slug: state.active.slug,
      path: state.active.path,
    };
  }
  return null;
}

function annotationIsBusy() {
  return Boolean(state.annotation.capture || state.annotation.anchor || document.getElementById("annotation-popover"));
}

async function restoreSelection(snapshot, opts = {}) {
  if (!snapshot) return false;
  if (snapshot.kind === "dashboard") {
    selectDashboard({
      skipUrl: true,
      preserveScroll: opts.preserveScroll,
      preserveAnnotation: opts.preserveAnnotation,
    });
    return true;
  }
  if (snapshot.kind === "plan") {
    const plan = state.plans.find(p => p.rel === snapshot.rel || p.path === snapshot.path);
    if (!plan) return false;
    await selectPlan(plan, {
      skipUrl: true,
      skipRecent: true,
      tab: snapshot.tab || "PLAN.md",
      preserveScroll: opts.preserveScroll,
      preserveAnnotation: opts.preserveAnnotation,
    });
    return true;
  }
  if (snapshot.kind === "artifact") {
    const artifact = state.artifacts.find(a => a.slug === snapshot.slug || a.path === snapshot.path);
    if (!artifact) return false;
    await selectArtifact(artifact, {
      skipUrl: true,
      skipRecent: true,
      preserveScroll: opts.preserveScroll,
      preserveAnnotation: opts.preserveAnnotation,
    });
    return true;
  }
  return false;
}

function refreshActiveMetadata(snapshot) {
  if (!snapshot) return false;
  if (snapshot.kind === "dashboard") {
    state.active = { kind: "dashboard" };
    state.activeTab = null;
    return true;
  }
  if (snapshot.kind === "plan") {
    const plan = state.plans.find(p => p.rel === snapshot.rel || p.path === snapshot.path);
    if (!plan) return false;
    state.active = { kind: "plan", ...plan };
    state.activeTab = snapshot.tab || state.activeTab || "PLAN.md";
    return true;
  }
  if (snapshot.kind === "artifact") {
    const artifact = state.artifacts.find(a => a.slug === snapshot.slug || a.path === snapshot.path);
    if (!artifact) return false;
    state.active = { kind: "artifact", ...artifact };
    state.activeTab = null;
    return true;
  }
  return false;
}

async function refreshVisibleComments() {
  const targetPath = currentCommentTargetPath();
  if (targetPath) await loadComments(targetPath);
}

async function loadAll(opts = {}) {
  const preserveSelection = Boolean(opts.preserveSelection);
  const snapshot = preserveSelection ? currentSelectionSnapshot() : null;
  const busy = annotationIsBusy();
  if (!opts.quiet) els.count.textContent = "loading…";
  try {
    const [plansRes, artifactsRes] = await Promise.all([
      fetch("/api/plans"),
      fetch("/api/artifacts"),
    ]);
    const plansData = await plansRes.json();
    const artifactsData = await artifactsRes.json();
    state.plans = plansData.plans || [];
    hydratePlanChildren();
    state.dashboard = plansData.dashboard || null;
    state.fleetSummary = plansData.summary || null;
    state.artifacts = artifactsData.artifacts || [];
    renderSidebar();
    if (preserveSelection && snapshot) {
      if (busy) {
        refreshActiveMetadata(snapshot);
        renderSidebar();
      } else {
        const restored = await restoreSelection(snapshot, {
          preserveScroll: opts.preserveScroll,
          preserveAnnotation: false,
        });
        if (!restored) {
          state.active = null;
          state.activeTab = "PLAN.md";
          els.pane.innerHTML = `
            ${renderOpsTruth()}
            <div class="pane-empty muted">
              <p>The selected item disappeared during refresh.</p>
              <p>Pick another plan or artifact from the sidebar.</p>
            </div>`;
        }
      }
    } else {
      // Restore selection from URL on initial load. In Simple mode, don't
      // default-land on the fleet dashboard (every plan across every repo
      // vidux can find under ~/Development/) -- that's an operator console
      // view, not "see my plan." Leave the sidebar-prompt empty state
      // (already in the static HTML) so the first thing anyone sees is
      // "pick a plan," not 40 unrelated engineering projects.
      if (!applyUrlSelection() && isAdvancedMode()) selectDashboard({ skipUrl: true });
    }
    refreshOpsTruth();
  } catch (e) {
    els.count.textContent = "error";
    els.list.innerHTML = `<div class="error">failed to load: ${escapeText(String(e))}</div>`;
    renderEmptyPane();
  }
}

function selectDashboard(opts = {}) {
  state.active = { kind: "dashboard" };
  state.activeTab = null;
  if (!opts.skipUrl) pushUrl(new URLSearchParams());
  renderSidebar();
  renderDashboardPane({
    preserveScroll: opts.preserveScroll,
    preserveAnnotation: opts.preserveAnnotation,
  });
}

async function selectPlan(plan, opts = {}) {
  state.active = { kind: "plan", ...plan };
  state.activeTab = opts.tab || "PLAN.md";
  if (!opts.skipRecent) trackRecent("plan", plan.rel);
  if (!opts.skipUrl) {
    const p = new URLSearchParams();
    p.set("plan", plan.rel);
    if (state.activeTab && state.activeTab !== "PLAN.md") p.set("tab", state.activeTab);
    pushUrl(p);
  }
  renderSidebar();
  if (opts.scrollIntoView) scrollActiveRowIntoView();
  await renderPane({ preserveScroll: opts.preserveScroll, preserveAnnotation: opts.preserveAnnotation });
}

async function selectArtifact(a, opts = {}) {
  state.active = { kind: "artifact", ...a };
  state.activeTab = null;
  if (!opts.skipRecent) trackRecent("artifact", a.slug);
  if (!opts.skipUrl) {
    const p = new URLSearchParams();
    p.set("artifact", a.slug);
    pushUrl(p);
  }
  renderSidebar();
  if (opts.scrollIntoView) scrollActiveRowIntoView();
  await renderArtifactPane({ preserveScroll: opts.preserveScroll, preserveAnnotation: opts.preserveAnnotation });
}

function setActiveTab(tab) {
  state.activeTab = tab;
  if (state.active && state.active.kind === "plan") {
    const p = new URLSearchParams();
    p.set("plan", state.active.rel);
    if (tab && tab !== "PLAN.md") p.set("tab", tab);
    pushUrl(p);
  }
  renderPane();
}

async function renderArtifactPane(opts = {}) {
  const a = state.active;
  if (!a || a.kind !== "artifact") return;
  const scrollTop = opts.preserveScroll ? els.pane.scrollTop : 0;
  if (!opts.preserveAnnotation) clearAnnotationState();
  els.pane.innerHTML = `
    ${renderOpsTruth()}
    <div class="pane-header">
      <div class="breadcrumb">artifact · ${escapeText(a.slug)}.html</div>
      <h2>${escapeText(a.title || a.slug)}</h2>
      <div class="meta">
        <span><span class="pill pill-artifact"></span>artifact</span>
        <span>${fmtAge(a.age_days) === "today" ? "modified today" : `modified ${fmtAge(a.age_days)} ago`}</span>
        <span>${(a.size / 1024).toFixed(1)}KB</span>
        <span class="muted">${escapeText(a.path)}</span>
      </div>
    </div>
    ${renderCommentsPanel(a.path)}
    <div class="markdown" id="md-body"><p class="muted">loading…</p></div>
  `;
  if (!opts.preserveScroll) els.pane.scrollTop = 0;
  setupCommentsPanel(a.path);
  refreshAnnotationTargets();
  try {
    const res = await fetch(`/api/file?path=${encodeURIComponent(a.path)}`);
    if (!res.ok) {
      document.getElementById("md-body").innerHTML =
        `<div class="error">${res.status}: ${escapeText(await res.text())}</div>`;
      if (opts.preserveScroll) els.pane.scrollTop = scrollTop;
      refreshAnnotationTargets();
      return;
    }
    const html = await res.text();
    // Sandboxed iframe so artifact <style>/<script> can't leak into host.
    const body = document.getElementById("md-body");
    body.innerHTML = `<iframe class="artifact-frame" sandbox="allow-same-origin allow-popups" srcdoc="${escapeAttr(html)}" title="Artifact: ${escapeAttr(a.title || a.slug)}"></iframe>`;
    const frame = body.querySelector("iframe.artifact-frame");
    // Auto-grow frame so host page scrolls (re-measure after fonts settle).
    const resizeFrame = () => {
      try {
        const doc = frame.contentDocument;
        if (!doc) return;
        const h = Math.max(
          doc.documentElement.scrollHeight,
          doc.body ? doc.body.scrollHeight : 0,
          480
        );
        frame.style.height = `${h + 24}px`;
      } catch (e) { /* cross-origin guard, shouldn't fire for srcdoc */ }
    };
    frame.addEventListener("load", () => {
      resizeFrame();
      if (opts.preserveScroll) els.pane.scrollTop = scrollTop;
      // Fonts/images can change height after first load — re-measure shortly.
      setTimeout(resizeFrame, 200);
      setTimeout(resizeFrame, 800);
    });
    if (opts.preserveScroll) els.pane.scrollTop = scrollTop;
    refreshAnnotationTargets();
  } catch (e) {
    document.getElementById("md-body").innerHTML =
      `<div class="error">failed to load artifact: ${escapeText(String(e))}</div>`;
    if (opts.preserveScroll) els.pane.scrollTop = scrollTop;
    refreshAnnotationTargets();
  }
}

async function renderPane(opts = {}) {
  if (!state.active) return;
  const scrollTop = opts.preserveScroll ? els.pane.scrollTop : 0;
  if (!opts.preserveAnnotation) clearAnnotationState();
  const plan = state.active;
  const tabs = ["PLAN.md", ...(isAdvancedMode() ? [DECISION_LOG_TAB, SESSION_TAB, LEDGER_TAB] : []), ...plan.siblings];
  const investigations = plan.investigations || [];
  const evidence = plan.evidence || [];
  const decisionLog = plan.decision_log || { present: false, count: 0, entries: [], recent_directions: [] };
  const session = plan.session || { available: false, status: "missing", turns: [] };
  const activeTab = state.activeTab || "PLAN.md";
  const isDecisionLogActive = activeTab === DECISION_LOG_TAB;
  const isSessionActive = activeTab === SESSION_TAB;
  const isLedgerActive = activeTab === LEDGER_TAB;
  const isInvActive = activeTab.startsWith("INV:");
  const isEvidenceActive = activeTab.startsWith("EVD:");
  // Investigations/evidence strips are agent-forensics artifacts (INV:/EVD:
  // file conventions, raw bullet parsing) -- audit-flagged hide_behind_advanced_mode.
  const showFileStrips = isAdvancedMode() && !isDecisionLogActive && !isSessionActive && !isLedgerActive;
  const activeInvPath = isInvActive ? state.activeTab.slice(4) : null;
  const activeEvidencePath = isEvidenceActive ? state.activeTab.slice(4) : null;

  let tabPath;
  if (isDecisionLogActive || isSessionActive || isLedgerActive) {
    tabPath = plan.path;
  } else if (isInvActive) {
    tabPath = activeInvPath;
  } else if (isEvidenceActive) {
    tabPath = activeEvidencePath;
  } else if (activeTab === "PLAN.md") {
    tabPath = plan.path;
  } else {
    tabPath = plan.path.replace(/\/PLAN\.md$/, `/${activeTab}`);
  }

  const stats = plan.task_stats || { counts: {}, total: 0 };
  const aggregate = plan.aggregate_stats || stats;
  const invStripHTML = showFileStrips && investigations.length ? `
    <div class="pane-investigations-strip">
      <span class="label">Investigations (${investigations.length}):</span>
      ${investigations.map(p => {
        const name = p.split("/").pop().replace(/\.md$/, "");
        const isActive = activeInvPath === p ? "is-active" : "";
        return `<button data-inv="${escapeAttr(p)}" class="${isActive}">${escapeText(name)}</button>`;
      }).join("")}
    </div>` : "";
  const evidenceStripHTML = showFileStrips && evidence.length ? `
    <div class="pane-evidence-strip" aria-label="Evidence timeline">
      <span class="label">Evidence (${evidence.length}):</span>
      ${evidence.map(item => {
        const isActive = activeEvidencePath === item.path ? "is-active" : "";
        const label = item.label || item.name || item.path.split("/").pop();
        const title = item.name && item.name !== label ? item.name : label;
        return `<button data-evidence="${escapeAttr(item.path)}" class="${isActive}" title="${escapeAttr(title)}">${escapeText(label)}</button>`;
      }).join("")}
    </div>` : "";

  // Ancestor breadcrumb — each segment is a clickable link back up the tree.
  // For a leaf C in (root → A → B → C), shows: ← root · A · B
  // Replaces the prior single-parent "← Parent" link (which made you click
  // N times to reach root in deep chains).
  const ancestors = ancestorChain(plan);
  const parentLinkHTML = ancestors.length
    ? `<div class="parent-link">← ${ancestors.map((p, i) => {
        const label = p.slug === "_root_" ? p.repo : p.slug;
        const sep = i < ancestors.length - 1 ? `<span class="parent-link-sep">·</span>` : "";
        return `<a href="?plan=${encodeURIComponent(p.rel)}" data-parent-rel="${escapeAttr(p.rel)}">${escapeText(label)}</a>${sep}`;
      }).join("")}</div>`
    : "";
  const headerHTML = `
    ${renderOpsTruth()}
    <div class="pane-header">
      ${parentLinkHTML}
      <div class="breadcrumb">${escapeText(plan.rel)}</div>
      <div class="pane-title-row">
        <h2>${escapeText(plan.slug === "_root_" ? plan.repo : `${plan.repo} · ${plan.slug}`)}</h2>
        ${isAdvancedMode() ? `
        <div class="pane-coding-actions">
          <button type="button" id="pane-coding-button" class="pane-coding-button" title="Open in Moussey coding workbench">Code</button>
          <span id="pane-coding-status" class="pane-coding-status" role="status" aria-live="polite"></span>
        </div>` : ""}
      </div>
      <div class="meta">
        <span><span class="pill pill-${plan.status}"></span>${plan.status}</span>
        <span>${fmtAge(plan.age_days) === "today" ? "modified today" : `modified ${fmtAge(plan.age_days)} ago`}</span>
        <span>${(plan.size / 1024).toFixed(1)}KB</span>
        <span class="muted">${escapeText(plan.path)}</span>
      </div>
    </div>
    ${renderPlanBrief(plan, stats, aggregate)}
    ${renderPaneProgress(stats)}
    ${renderPaneAggregateProgress(plan, aggregate)}
    ${renderPaneSubplans(plan)}
    <div class="pane-tabs">
      ${tabs.map(t => `
        <button data-tab="${escapeAttr(t)}" class="${t === activeTab ? "is-active" : ""}">${escapeText(t)}</button>
      `).join("")}
    </div>
    ${invStripHTML}
    ${evidenceStripHTML}
    ${isSessionActive || isLedgerActive ? "" : renderCommentsPanel(tabPath)}
    <div class="markdown" id="md-body"><p class="muted">loading…</p></div>
  `;
  els.pane.innerHTML = headerHTML;
  if (!opts.preserveScroll) els.pane.scrollTop = 0;
  refreshAnnotationTargets();

  // Parent backlink → navigate to parent plan in-app (preserves SPA flow,
  // doesn't trigger a page reload; href is there for opening-in-new-tab).
  els.pane.querySelectorAll(".parent-link a[data-parent-rel]").forEach(a => {
    a.addEventListener("click", e => {
      e.preventDefault();
      const rel = a.getAttribute("data-parent-rel");
      const target = state.plans.find(p => p.rel === rel);
      if (target) selectPlan(target, { scrollIntoView: true });
    });
  });
  els.pane.querySelectorAll(".pane-tabs button").forEach(b => {
    b.addEventListener("click", () => {
      setActiveTab(b.getAttribute("data-tab"));
    });
  });
  els.pane.querySelectorAll(".pane-investigations-strip button").forEach(b => {
    b.addEventListener("click", () => {
      setActiveTab(`INV:${b.getAttribute("data-inv")}`);
    });
  });
  els.pane.querySelectorAll(".pane-evidence-strip button").forEach(b => {
    b.addEventListener("click", () => {
      setActiveTab(`EVD:${b.getAttribute("data-evidence")}`);
    });
  });
  els.pane.querySelectorAll(".subplan-row").forEach(row => {
    row.addEventListener("click", () => {
      const rel = row.getAttribute("data-subplan-rel");
      const target = state.plans.find(p => p.rel === rel);
      if (target) selectPlan(target, { scrollIntoView: true });
    });
  });
  if (!isSessionActive && !isLedgerActive) setupCommentsPanel(tabPath);
  setupPlanSteering(plan);
  setupCodingHandoff(plan);
  refreshAnnotationTargets();

  if (isDecisionLogActive) {
    document.getElementById("md-body").innerHTML = renderDecisionLogPane(decisionLog);
    if (opts.preserveScroll) els.pane.scrollTop = scrollTop;
    refreshAnnotationTargets();
    return;
  }

  if (isSessionActive) {
    document.getElementById("md-body").innerHTML = renderSessionPanel(session);
    if (opts.preserveScroll) els.pane.scrollTop = scrollTop;
    refreshAnnotationTargets();
    return;
  }

  if (isLedgerActive) {
    const body = document.getElementById("md-body");
    try {
      const res = await fetch(`/api/ledger?path=${encodeURIComponent(plan.path)}`);
      if (!res.ok) {
        body.innerHTML = `<div class="error">${res.status}: ${escapeText(await res.text())}</div>`;
      } else {
        body.innerHTML = renderLedgerPanel(await res.json());
      }
    } catch (e) {
      body.innerHTML = `<div class="error">failed to load ledger: ${escapeText(String(e))}</div>`;
    }
    if (opts.preserveScroll) els.pane.scrollTop = scrollTop;
    refreshAnnotationTargets();
    return;
  }

  try {
    const res = await fetch(`/api/file?path=${encodeURIComponent(tabPath)}`);
    if (!res.ok) {
      const txt = await res.text();
      document.getElementById("md-body").innerHTML =
        `<div class="error">${res.status}: ${escapeText(txt)}</div>`;
      if (opts.preserveScroll) els.pane.scrollTop = scrollTop;
      refreshAnnotationTargets();
      return;
    }
    const md = stripParentMetadata(await res.text());
    const body = document.getElementById("md-body");
    body.innerHTML = renderMarkdownBody(md);
    if (opts.preserveScroll) els.pane.scrollTop = scrollTop;
    refreshAnnotationTargets();
  } catch (e) {
    document.getElementById("md-body").innerHTML =
      `<div class="error">failed to load file: ${escapeText(String(e))}</div>`;
    if (opts.preserveScroll) els.pane.scrollTop = scrollTop;
    refreshAnnotationTargets();
  }
}

function renderMarkdownBody(md) {
  try {
    if (!window.marked) return naiveMarkdown(md);
    const html = window.marked.parse(md, { breaks: false, gfm: true });
    // marked renders embedded raw HTML/script verbatim by design (CommonMark/
    // GFM behavior, not a marked bug) -- md is arbitrary file content sourced
    // from anywhere under DEV_ROOT via /api/file, so this MUST be sanitized
    // before ever reaching innerHTML. If the sanitizer failed to load, fall
    // back to the escaping naiveMarkdown path rather than risk raw HTML.
    if (!window.DOMPurify) return naiveMarkdown(md);
    return window.DOMPurify.sanitize(html);
  } catch (e) {
    return `
      <div class="error">markdown render failed: ${escapeText(String(e))}</div>
      <pre class="markdown-source-fallback">${escapeText(md.slice(0, 12000))}</pre>`;
  }
}

function renderDecisionLogPane(decisionLog) {
  const entries = Array.isArray(decisionLog.entries) ? decisionLog.entries : [];
  const recentDirections = Array.isArray(decisionLog.recent_directions)
    ? decisionLog.recent_directions
    : [];
  if (!decisionLog.present) {
    return `
      <section class="decision-log decision-log-empty">
        <div class="decision-log-summary">
          <div>
            <div class="label">Decision Log</div>
            <h3>No Decision Log section</h3>
          </div>
          <span class="decision-log-count">0 entries</span>
        </div>
        <p class="muted">This plan does not define a <code>## Decision Log</code> section yet.</p>
      </section>`;
  }
  const recentHTML = recentDirections.length
    ? recentDirections.map(renderDecisionLogEntry).join("")
    : `<p class="muted">No recent direction-tagged entries yet.</p>`;
  const entriesHTML = entries.length
    ? entries.map(renderDecisionLogEntry).join("")
    : `<p class="muted">The section exists, but it has no bullet entries yet.</p>`;
  return `
    <section class="decision-log">
      <div class="decision-log-summary">
        <div>
          <div class="label">Decision Log</div>
          <h3>${entries.length} ${entries.length === 1 ? "entry" : "entries"}</h3>
        </div>
        <span class="decision-log-count">line ${escapeText(decisionLog.heading_line || "?")}</span>
      </div>
      <section class="decision-log-recent">
        <h4>Recent Directions</h4>
        <div class="decision-entry-list">${recentHTML}</div>
      </section>
      <section class="decision-log-all">
        <h4>All Entries</h4>
        <div class="decision-entry-list">${entriesHTML}</div>
      </section>
    </section>`;
}

function renderDecisionLogEntry(entry) {
  const kind = entry.kind || "NOTE";
  const cls = [
    "decision-entry",
    entry.is_direction ? "is-direction" : "",
    entry.is_recent ? "is-recent" : "",
  ].filter(Boolean).join(" ");
  const meta = [
    entry.date ? escapeText(entry.date) : "",
    entry.line ? `line ${escapeText(entry.line)}` : "",
  ].filter(Boolean).join(" · ");
  return `
    <article class="${cls}">
      <div class="decision-entry-head">
        <span class="decision-kind">${escapeText(kind)}</span>
        ${entry.is_recent ? `<span class="decision-recent">recent</span>` : ""}
        ${meta ? `<span class="decision-meta">${meta}</span>` : ""}
      </div>
      <p>${escapeText(entry.body || entry.raw || "")}</p>
    </article>`;
}

function renderSessionPanel(session) {
  const turns = Array.isArray(session.turns) ? session.turns : [];
  const status = session.status || (session.available ? "ok" : "missing");
  if (!session.available) {
    return `
      <section class="session-panel session-empty">
        <div class="session-summary">
          <div>
            <div class="label">Sessions</div>
            <h3>No Claude session found</h3>
          </div>
          <span class="session-status">${escapeText(status)}</span>
        </div>
        <p class="muted">No latest JSONL was found for this repo under <code>${escapeText(session.project_dir || "~/.claude/projects")}</code>.</p>
      </section>`;
  }
  const meta = [
    session.file || "",
    session.age_days == null ? "" : `modified ${fmtAge(Number(session.age_days))} ago`,
    session.tail_truncated ? "tail scan" : "",
    `${Number(session.turns_seen || turns.length)} text turns seen`,
  ].filter(Boolean).join(" · ");
  const turnsHTML = turns.length
    ? turns.map(turn => `
      <article class="session-turn session-turn-${escapeAttr(turn.role || "unknown")}">
        <div class="session-turn-head">
          <span class="session-role">${escapeText(turn.role || "unknown")}</span>
          ${turn.timestamp ? `<span class="session-time">${escapeText(turn.timestamp)}</span>` : ""}
        </div>
        <p>${escapeText(turn.text || "")}</p>
      </article>`).join("")
    : `<p class="muted">Latest session file had no user/assistant text blocks in the scanned tail.</p>`;
  return `
    <section class="session-panel">
      <div class="session-summary">
        <div>
          <div class="label">Sessions</div>
          <h3>Latest Claude session</h3>
        </div>
        <span class="session-status">${escapeText(status)}</span>
      </div>
      <div class="session-meta">
        <span>${escapeText(meta)}</span>
        <code>${escapeText(session.path || "")}</code>
      </div>
      <div class="session-turns">${turnsHTML}</div>
    </section>`;
}

function renderLedgerPanel(ledger) {
  const items = Array.isArray(ledger.items) ? ledger.items : [];
  const status = ledger.status || (ledger.available ? "ok" : "missing");
  const total = Number(ledger.plan_total || 0) + Number(ledger.repo_total || 0);
  if (!ledger.available) {
    return `
      <section class="ledger-panel ledger-empty">
        <div class="ledger-summary">
          <div>
            <div class="label">Ledger</div>
            <h3>No activity ledger found</h3>
          </div>
          <span class="ledger-status">${escapeText(status)}</span>
        </div>
        <p class="muted">No append-only ledger was found at <code>${escapeText(ledger.source || "~/.agent-ledger/activity.jsonl")}</code>.</p>
      </section>`;
  }
  const meta = [
    `${Number(ledger.plan_total || 0)} plan rows`,
    `${Number(ledger.repo_total || 0)} repo rows`,
    `${Number(ledger.returned || items.length)} shown`,
    ledger.truncated ? "truncated" : "",
    `${Number(ledger.scanned_rows || 0)} scanned`,
  ].filter(Boolean).join(" · ");
  const itemsHTML = items.length
    ? items.map(renderLedgerEntry).join("")
    : `<p class="muted">No publish or checkpoint rows matched this plan or repo in the scanned ledger tail.</p>`;
  return `
    <section class="ledger-panel">
      <div class="ledger-summary">
        <div>
          <div class="label">Ledger</div>
          <h3>Recent publish proof</h3>
        </div>
        <span class="ledger-status">${escapeText(status)}</span>
      </div>
      <div class="ledger-meta">
        <span>${escapeText(meta)}</span>
        <code>${escapeText(ledger.source || "")}</code>
      </div>
      ${total > 0 && items.length === 0 ? `<p class="muted">Rows matched, but the item limit is currently 0.</p>` : ""}
      <div class="ledger-entries">${itemsHTML}</div>
    </section>`;
}

function renderLedgerEntry(entry) {
  const scope = entry.scope || "repo";
  const headMeta = [
    entry.event || "",
    entry.handoff_status ? `handoff ${entry.handoff_status}` : "",
    entry.ts || "",
    entry.line ? `line ${entry.line}` : "",
  ].filter(Boolean).join(" · ");
  const detailMeta = [
    entry.repo || "",
    entry.lane || "",
    entry.task_id ? `task ${entry.task_id}` : "",
    entry.files_claimed_count ? `${Number(entry.files_claimed_count)} claimed` : "",
    entry.files_count ? `${Number(entry.files_count)} files` : "",
  ].filter(Boolean).join(" · ");
  return `
    <article class="ledger-entry ledger-entry-${escapeAttr(scope)}">
      <div class="ledger-entry-head">
        <span class="ledger-scope">${escapeText(scope)}</span>
        ${headMeta ? `<span class="ledger-entry-meta">${escapeText(headMeta)}</span>` : ""}
      </div>
      <h4>${escapeText(entry.summary || entry.eid || "ledger row")}</h4>
      ${detailMeta ? `<div class="ledger-detail-meta">${escapeText(detailMeta)}</div>` : ""}
      ${entry.eid ? `<code class="ledger-eid">${escapeText(entry.eid)}</code>` : ""}
      ${entry.proof ? `<p><strong>Proof</strong> ${escapeText(entry.proof)}</p>` : ""}
      ${entry.next_agent_resume ? `<p><strong>Resume</strong> ${escapeText(entry.next_agent_resume)}</p>` : ""}
      ${entry.plan_path ? `<p class="ledger-plan-path">${escapeText(entry.plan_path)}</p>` : ""}
    </article>`;
}

function getStoredCommentAuthor() {
  try {
    return window.localStorage.getItem(COMMENT_AUTHOR_KEY) || "";
  } catch {
    return "";
  }
}

function setStoredCommentAuthor(value) {
  try {
    window.localStorage.setItem(COMMENT_AUTHOR_KEY, value);
  } catch {
    // localStorage can be unavailable in constrained browser contexts.
  }
}

function renderCommentsPanel(targetPath) {
  return commentMarkers.renderPanel(targetPath, state.commentMarkersHidden, commentRail.targetLabel(targetPath));
}

function setupPlanSteering(plan) {
  const form = document.querySelector(".plan-steering");
  if (!form || !plan?.path) return;
  const textarea = form.querySelector("textarea");
  const status = form.querySelector(".plan-steering-status");
  const button = form.querySelector("button[type='submit']");
  form.addEventListener("submit", async e => {
    e.preventDefault();
    const raw = textarea.value.trim();
    if (!raw) {
      status.textContent = "write direction first";
      textarea.focus();
      return;
    }
    const author = getStoredCommentAuthor() || "Leo";
    const body = raw.toLowerCase().startsWith("@pm") ? raw : `@pm ${raw}`;
    status.textContent = "sending...";
    button.disabled = true;
    try {
      const res = await fetch("/api/comments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_path: plan.path,
          author,
          body,
          anchor: {
            kind: "plan-steering",
            label: "Plan steering",
            excerpt: plan.rel,
            tag: "plan",
          },
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      textarea.value = "";
      status.textContent = "sent";
      if (currentCommentTargetPath() === plan.path) await loadComments(plan.path);
    } catch (err) {
      status.textContent = `failed: ${String(err.message || err)}`;
    } finally {
      button.disabled = false;
    }
  });
}

function setupCodingHandoff(plan) {
  const button = document.getElementById("pane-coding-button");
  const status = document.getElementById("pane-coding-status");
  if (!button || !status || !plan?.path) return;
  button.addEventListener("click", async () => {
    status.textContent = "staging...";
    button.disabled = true;
    try {
      const res = await fetch("/api/coding-handoff", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan_path: plan.path,
          proposedAction: "lane-status",
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.url) throw new Error(data.error || await res.text().catch(() => `HTTP ${res.status}`));
      status.textContent = "opened";
      window.open(data.url, "_blank", "noopener");
    } catch (err) {
      status.textContent = `failed: ${String(err.message || err)}`;
    } finally {
      button.disabled = false;
    }
  });
}

function setupCommentsPanel(targetPath) {
  const panel = document.getElementById("comments-panel");
  if (!panel) return;
  state.comments = { targetPath, items: [] };
  setupCommentMarkerToggle(panel);
  renderCommentMarkers();
  loadComments(targetPath);
  updateAnnotationUI();
}

function setupCommentMarkerToggle(panel) {
  commentMarkers.bindToggle(panel, state.commentMarkersHidden, hidden => {
    state.commentMarkersHidden = hidden;
    renderCommentMarkers();
  });
}

function clearAnnotationState() {
  state.annotation.capture = false;
  state.annotation.targetPath = "";
  state.annotation.anchor = null;
  state.annotation.phase = AS.IDLE;
  closeAnnotationPopover({ preserveState: true });
  updateAnnotationUI();
}

function toggleAnnotationCapture(targetPath) {
  if (state.annotation.capture && state.annotation.targetPath === targetPath) {
    clearAnnotationState();
    return;
  }
  closeAnnotationPopover({ preserveState: true });
  state.annotation.capture = true;
  state.annotation.targetPath = targetPath;
  state.annotation.anchor = null;
  state.annotation.phase = AS.CAPTURE_ACTIVE;
  refreshAnnotationTargets();
  updateAnnotationUI();
}

function currentCommentTargetPath() {
  const panel = document.getElementById("comments-panel");
  return panel ? panel.getAttribute("data-target-path") || "" : "";
}

function setAnnotationPhase(phase) {
  state.annotation.phase = phase;
  updateAnnotationUI();
}

function annotationUiState(currentTarget = currentCommentTargetPath()) {
  return annotationState.derive({
    currentTarget,
    targetPath: state.annotation.targetPath,
    phase: state.annotation.phase,
    capture: state.annotation.capture,
    anchor: state.annotation.anchor,
    popoverOpen: Boolean(document.getElementById("annotation-popover")),
  });
}

function updateAnnotationUI() {
  const currentTarget = currentCommentTargetPath();
  const uiState = annotationUiState(currentTarget);
  const rootToggle = els.annotate;

  document.body.classList.toggle("is-annotation-mode", uiState === AS.CAPTURE_ACTIVE);
  annotationState.paintButton(rootToggle, uiState);
}

function openAnnotationPopover(anchor, targetEl) {
  const targetPath = currentCommentTargetPath();
  if (!targetPath || !anchor) return;
  closeAnnotationPopover({ preserveState: true });

  state.annotation.capture = false;
  state.annotation.targetPath = targetPath;
  state.annotation.anchor = anchor;
  state.annotation.phase = AS.TARGET_PICKED;
  activePopoverTarget = targetEl || findAnchorElement(anchor);

  const author = getStoredCommentAuthor();
  const label = anchor.label || anchor.excerpt || "Selected target";
  // Remember which element had focus before the popover opened so we can
  // restore it on close (WCAG focus-management best practice for dialogs).
  const previouslyFocused = document.activeElement;
  const popover = document.createElement("aside");
  popover.id = "annotation-popover";
  popover.className = "annotation-popover";
  popover.setAttribute("data-vidux-zone", "mode-popover");
  popover.setAttribute("role", "dialog");
  popover.setAttribute("aria-modal", "true");
  popover.setAttribute("aria-labelledby", "annotation-popover-title");
  popover.innerHTML = `
    <div class="annotation-popover-head">
      <div>
        <span class="annotation-popover-kicker" id="annotation-popover-title">Annotating</span>
        <strong>${escapeText(label)}</strong>
      </div>
      <button type="button" class="annotation-popover-close" aria-label="Close annotation">&times;</button>
    </div>
    <form id="annotation-popover-form" class="annotation-popover-form">
      <label for="annotation-popover-author" class="visually-hidden">Your name</label>
      <input id="annotation-popover-author" name="author" maxlength="80" placeholder="Name" value="${escapeAttr(author)}" autocomplete="name" aria-label="Your name">
      <label for="annotation-popover-body" class="visually-hidden">Comment body</label>
      <textarea id="annotation-popover-body" name="body" rows="3" maxlength="8192" placeholder="Add a comment" aria-label="Comment body"></textarea>
      <div class="annotation-popover-actions">
        <span id="annotation-popover-status" class="annotation-popover-status" role="status" aria-live="polite"></span>
        <button type="button" class="annotation-popover-cancel">Cancel</button>
        <button type="submit">Add comment</button>
      </div>
    </form>`;
  document.body.appendChild(popover);

  const closeButton = popover.querySelector(".annotation-popover-close");
  const cancelButton = popover.querySelector(".annotation-popover-cancel");
  const form = popover.querySelector("#annotation-popover-form");
  const authorInput = popover.querySelector("#annotation-popover-author");
  const bodyInput = popover.querySelector("#annotation-popover-body");
  const status = popover.querySelector("#annotation-popover-status");
  const submitButton = popover.querySelector('button[type="submit"]');

  function setPopoverStatus(phase, message) {
    status.dataset.state = phase;
    status.textContent = message;
    setAnnotationPhase(phase);
  }

  // Close-and-restore-focus helper, used by Escape, Close button, and Cancel.
  const closeAndRestore = () => {
    clearAnnotationState();
    if (previouslyFocused && document.body.contains(previouslyFocused)) {
      try { previouslyFocused.focus(); } catch (e) { /* element no longer focusable */ }
    }
  };

  // Focus trap: keep Tab/Shift+Tab cycling within the popover's focusable
  // descendants. Escape closes. Both are WCAG 2.1.2 (No Keyboard Trap) and
  // WCAG 2.4.3 (Focus Order). Bound on the popover itself, not document, so
  // it dies cleanly when the popover is removed.
  popover.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      closeAndRestore();
      return;
    }
    if (e.key !== "Tab") return;
    const focusables = popover.querySelectorAll(
      'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    if (!focusables.length) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  });

  closeButton.addEventListener("click", closeAndRestore);
  cancelButton.addEventListener("click", closeAndRestore);
  authorInput.addEventListener("input", () => setStoredCommentAuthor(authorInput.value.trim()));
  form.addEventListener("submit", async e => {
    e.preventDefault();
    const authorValue = authorInput.value.trim();
    const bodyValue = bodyInput.value.trim();
    if (!bodyValue) {
      status.textContent = "write a comment first";
      bodyInput.focus();
      return;
    }
    setStoredCommentAuthor(authorValue);
    submitButton.disabled = true;
    setPopoverStatus(AS.SAVING, "saving...");
    try {
      const res = await fetch("/api/comments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_path: targetPath,
          author: authorValue,
          body: bodyValue,
          anchor,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      await loadComments(targetPath);
      if (!document.body.contains(popover)) return;
      setPopoverStatus(AS.SAVED, "saved");
      setTimeout(() => {
        if (document.body.contains(popover) && state.annotation.phase === AS.SAVED) {
          clearAnnotationState();
        }
      }, 350);
    } catch (err) {
      submitButton.disabled = false;
      setPopoverStatus(AS.ERROR, `failed: ${String(err.message || err)}`);
    }
  });

  setAnnotationPhase(AS.COMPOSER_OPEN);
  positionAnnotationPopover();
  bodyInput.focus();
}

function closeAnnotationPopover({ preserveState = false } = {}) {
  const popover = document.getElementById("annotation-popover");
  if (popover) popover.remove();
  activePopoverTarget = null;
  if (!preserveState) clearAnnotationState();
}

function positionAnnotationPopover() {
  const popover = document.getElementById("annotation-popover");
  if (!popover) return;
  const resolved = activePopoverTarget && document.body.contains(activePopoverTarget)
    ? { element: activePopoverTarget, rect: activePopoverTarget.getBoundingClientRect() }
    : resolveAnchorTarget(state.annotation.anchor);
  const target = resolved?.element || null;
  activePopoverTarget = target;
  const margin = 12;
  const width = Math.min(380, Math.max(280, window.innerWidth - margin * 2));
  popover.style.width = `${width}px`;
  const height = popover.offsetHeight || 230;
  let left = margin;
  let top = margin;
  if (target && resolved?.rect) {
    const rect = resolved.rect;
    left = Math.min(Math.max(rect.left, margin), window.innerWidth - width - margin);
    top = rect.bottom + 10;
    if (top + height > window.innerHeight - margin) top = rect.top - height - 10;
    if (top < margin) top = margin;
  }
  popover.style.left = `${Math.round(left)}px`;
  popover.style.top = `${Math.round(top)}px`;
}

function compactText(value, limit = 360) {
  return String(value || "").replace(/\s+/g, " ").trim().slice(0, limit);
}

function refreshAnnotationTargets() {
  document.querySelectorAll("[data-vidux-anchor]").forEach(el => {
    delete el.dataset.viduxAnchor;
    delete el.dataset.viduxAnchorIndex;
    delete el.dataset.viduxAnchorKind;
    delete el.dataset.viduxAnchorLabel;
  });

  let index = 0;
  document.querySelectorAll(APP_ANCHOR_SELECTOR).forEach(el => {
    if (!isAnnotationCandidate(el)) return;
    const label = annotationLabelForElement(el);
    const text = compactText(el.innerText || el.textContent || el.getAttribute("aria-label") || "", 24);
    if (!label && !text) return;
    index += 1;
    el.dataset.viduxAnchor = `a${index}`;
    el.dataset.viduxAnchorIndex = String(index);
    el.dataset.viduxAnchorKind = el.closest("#md-body") ? "rendered" : "browser";
    el.dataset.viduxAnchorLabel = label || text;
  });
  renderCommentMarkers();
}

function refreshAnnotationTargetsIfNeeded() {
  if (state.annotation.capture || state.annotation.anchor) refreshAnnotationTargets();
}

function isAnnotationCandidate(el) {
  if (!el || !document.body.contains(el)) return false;
  if (el.matches && el.matches(ANNOTATION_CAPTURE_EXCLUDE_SELECTOR)) return false;
  if (el.closest && el.closest("#annotation-popover")) return false;
  if (el.hidden || (el.closest && el.closest("[hidden]"))) return false;
  if (typeof window.getComputedStyle === "function") {
    const style = window.getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden") return false;
  }
  return true;
}

function annotationRegionForElement(el) {
  if (el.closest(".topbar")) return "Header";
  if (el.closest(".sidebar")) return "Sidebar";
  if (el.closest("#comments-panel")) return "Comments";
  if (el.closest("#md-body")) return "Content";
  if (el.closest(".pane")) return "View";
  return "Browser";
}

function annotationLabelForElement(el) {
  const region = annotationRegionForElement(el);
  if (el.matches(".plan-row")) {
    const kind = el.getAttribute("data-kind") === "artifact" ? "Artifact" : "Plan";
    const title = compactText(el.querySelector(".plan-row-head")?.innerText || el.innerText || "", 120);
    return `${region} / ${kind} row${title ? ` / ${title}` : ""}`;
  }
  if (el.matches(".repo-group h2")) {
    return `${region} / ${compactText(el.innerText || el.textContent || "group", 120)}`;
  }
  if (el.matches("#meta-count")) return `${region} / fleet summary`;
  if (el.matches(".topbar h1")) return `${region} / ${compactText(el.innerText || "vidux browser", 80)}`;
  if (el.matches(".topbar")) return `${region} / browser controls`;
  if (el.matches(".pane-header h2")) return `${region} title / ${compactText(el.innerText || el.textContent || "", 120)}`;
  if (el.matches(".pane-header .breadcrumb")) return `${region} breadcrumb / ${compactText(el.innerText || el.textContent || "", 120)}`;
  if (el.matches(".pane-header .meta")) return `${region} metadata / ${compactText(el.innerText || el.textContent || "", 120)}`;
  if (el.matches(".pane-header")) return `${region} header / ${compactText(el.innerText || el.textContent || "", 120)}`;
  if (el.matches(".pane-progress")) return `${region} completion / ${compactText(el.innerText || el.textContent || "", 120)}`;
  if (el.matches(".pane-tabs button")) return `${region} tab / ${compactText(el.innerText || el.textContent || "", 80)}`;
  if (el.matches(".pane-tabs")) return `${region} tabs`;
  if (el.matches(".pane-investigations-strip button")) return `${region} investigation / ${compactText(el.innerText || el.textContent || "", 80)}`;
  if (el.matches(".pane-investigations-strip")) return `${region} investigations`;
  if (el.matches(".comments-head")) return `${region} header`;
  if (el.matches(".comment-list .comment-item")) return `${region} item / ${compactText(el.innerText || el.textContent || "", 120)}`;
  if (el.matches(".comments-panel")) return `${region} panel`;
  return compactText(el.innerText || el.textContent || el.getAttribute("aria-label") || region, 120);
}

function describeAnchorTarget(rawTarget) {
  const rawEl = rawTarget && rawTarget.nodeType === Node.ELEMENT_NODE ? rawTarget : null;
  if (!rawEl || rawEl.closest(ANNOTATION_CAPTURE_EXCLUDE_SELECTOR)) return null;
  const target = rawEl.closest("[data-vidux-anchor]");
  if (!target || !document.body.contains(target)) return null;
  const body = document.getElementById("md-body");
  const excerpt = compactText(target.innerText || target.textContent || "");
  const tag = target.tagName.toLowerCase();
  const index = Number.parseInt(target.dataset.viduxAnchorIndex || "0", 10);
  const kind = target.dataset.viduxAnchorKind || (body && body.contains(target) ? "rendered" : "browser");
  const heading = kind === "rendered" && body ? nearestHeadingText(target, body) : "";
  const storedLabel = target.dataset.viduxAnchorLabel || "";
  const label = compactText(
    heading && heading !== excerpt ? `${heading} / ${excerpt}` : (storedLabel || excerpt),
    180
  );
  return {
    kind,
    selector: `[data-vidux-anchor="${target.dataset.viduxAnchor}"]`,
    label: label || `${tag} #${index}`,
    excerpt,
    tag,
    index,
  };
}

function nearestHeadingText(target, container) {
  let heading = "";
  container.querySelectorAll("h1,h2,h3,h4,h5,h6").forEach(h => {
    if (h === target || (h.compareDocumentPosition(target) & Node.DOCUMENT_POSITION_FOLLOWING)) {
      heading = compactText(h.innerText || h.textContent || "", 100);
    }
  });
  return heading;
}

function resolveAnchorTarget(anchor) {
  return commentMarkers.resolveAnchorTarget(anchor, {
    document,
    hostLabel: annotationLabelForElement,
  });
}

function findAnchorElement(anchor) {
  return resolveAnchorTarget(anchor)?.element || null;
}

function jumpToCommentAnchor(anchor) {
  commentMarkers.jumpToTarget(resolveAnchorTarget(anchor));
}

function setCommentMarkerPreview(target, enabled) {
  commentMarkers.setPreview(target, enabled);
}

function renderCommentMarkers() {
  const panel = document.getElementById("comments-panel");
  const targetMap = document.getElementById("comment-target-map");
  const targetPath = panel?.getAttribute("data-target-path") || "";
  if (!panel || targetPath !== state.comments.targetPath) {
    commentMarkers.clear({ document });
    return;
  }
  commentMarkers.render({
    document,
    panel,
    targetMap,
    comments: state.comments.items,
    hidden: state.commentMarkersHidden,
    resolve: resolveAnchorTarget,
    jump: jumpToCommentAnchor,
    preview: setCommentMarkerPreview,
  });
}

function scheduleCommentMarkerRender() {
  if (commentMarkerRenderFrame) return;
  commentMarkerRenderFrame = requestAnimationFrame(() => {
    commentMarkerRenderFrame = 0;
    renderCommentMarkers();
  });
}

async function loadComments(targetPath) {
  const list = document.getElementById("comment-list");
  const count = document.getElementById("comment-count");
  if (!list || !count) return;
  const panel = document.getElementById("comments-panel");
  if (!panel || panel.getAttribute("data-target-path") !== targetPath) return;
  panel.setAttribute("data-comment-state", "loading");
  try {
    const res = await fetch(`/api/comments?path=${encodeURIComponent(targetPath)}`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    const currentPanel = document.getElementById("comments-panel");
    if (!currentPanel || currentPanel.getAttribute("data-target-path") !== targetPath) return;
    const comments = data.comments || [];
    state.comments = { targetPath, items: comments };
    currentPanel.setAttribute("data-comment-state", "ready");
    currentPanel.setAttribute("data-comment-count", String(comments.length));
    currentPanel.classList.toggle("has-comments", comments.length > 0);
    count.textContent = commentRail.countLabel(comments.length);
    list.innerHTML = commentRail.renderList(comments);
    list.querySelectorAll("[data-comment-jump]").forEach(button => {
      button.addEventListener("click", () => {
        const id = button.getAttribute("data-comment-jump");
        const comment = comments.find(item => item.id === id);
        if (comment && comment.anchor) jumpToCommentAnchor(comment.anchor);
      });
    });
    refreshAnnotationTargets();
  } catch (err) {
    state.comments = { targetPath, items: [] };
    count.textContent = "error";
    panel.setAttribute("data-comment-state", "error");
    panel.setAttribute("data-comment-count", "0");
    panel.classList.remove("has-comments");
    list.innerHTML = `<div class="error">failed to load comments: ${escapeText(String(err.message || err))}</div>`;
    refreshAnnotationTargets();
  }
}

function naiveMarkdown(md) {
  // Tiny fallback if marked.js fails to load.
  return md
    .split(/\n\n+/)
    .map(p => `<p>${escapeText(p).replace(/\n/g, "<br>")}</p>`)
    .join("");
}

// The Parent: <relpath> line at the top of a child plan is metadata the
// pane header consumes for the breadcrumb; rendering it again as a
// blockquote in the body is duplicate clutter. Strip leading parent
// blockquotes / bold lines (with their trailing blank line) before render.
function stripParentMetadata(md) {
  const lines = md.split("\n");
  let i = 0;
  if (lines[i] && /^# /.test(lines[i])) i++;
  while (i < lines.length && lines[i].trim() === "") i++;
  if (i < lines.length && /^(?:>\s*Parent:|\*\*Parent:\*\*)/i.test(lines[i])) {
    lines.splice(i, 1);
    while (i < lines.length && lines[i].trim() === "") {
      lines.splice(i, 1);
      break;
    }
  }
  return lines.join("\n");
}

function escapeText(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
function escapeAttr(s) {
  return escapeText(s).replace(/"/g, "&quot;");
}

function isEditableShortcutTarget(target) {
  const el = target && target.nodeType === Node.ELEMENT_NODE ? target : document.activeElement;
  if (!el || el === document.body) return false;
  const tag = String(el.tagName || "").toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return true;
  if (el.isContentEditable) return true;
  return Boolean(el.closest && el.closest('[contenteditable]:not([contenteditable="false"])'));
}

els.filter.addEventListener("input", e => {
  state.filter = e.target.value;
  renderSidebar();
});
if (els.sort) {
  els.sort.value = state.sort;
  els.sort.addEventListener("change", e => {
    state.sort = sidebarSort.normalize(e.target.value);
    e.target.value = state.sort;
    sidebarSort.store(state.sort);
    renderSidebar();
  });
}
function syncFilterChipButtons() {
  sidebarFilters.syncButtons(els.filterChips, state.filterChips);
}
for (const button of els.filterChips) {
  button.addEventListener("click", () => {
    state.filterChips = sidebarFilters.toggle(state.filterChips, button.dataset.filterChip);
    sidebarFilters.store(state.filterChips);
    syncFilterChipButtons();
    renderSidebar();
  });
}
syncFilterChipButtons();
els.refresh.addEventListener("click", () => {
  loadAll({ preserveSelection: true });
});
if (els.annotate) {
  els.annotate.addEventListener("click", () => {
    const targetPath = currentCommentTargetPath();
    if (targetPath) toggleAnnotationCapture(targetPath);
  });
}

// Mobile sidebar drawer toggle (visible only at narrow widths via CSS).
const sidebarEl = document.getElementById("sidebar");
const sidebarToggleBtn = document.getElementById("sidebar-toggle");
if (sidebarToggleBtn && sidebarEl) {
  sidebarToggleBtn.addEventListener("click", () => sidebarEl.classList.toggle("is-open"));
  // Tap-in-pane closes the drawer on mobile.
  els.pane.addEventListener("click", () => {
    if (sidebarEl.classList.contains("is-open")) sidebarEl.classList.remove("is-open");
  });
}

// The mobile drawer (.sidebar, position:fixed at <=768px) needs a `top`
// matching wherever .topbar's real bottom edge lands. A hardcoded pixel value
// broke twice already (a topbar-wrap fix for one overlap silently changed the
// topbar's height at <=540px, orphaning the drawer's fixed offset and hiding
// its own search/sort/filter controls underneath it) -- track the real
// measured height instead of guessing a new constant that the next topbar
// content change would just break again.
const topbarEl = document.querySelector(".topbar");
if (topbarEl && typeof ResizeObserver !== "undefined") {
  const syncTopbarHeight = () => {
    document.documentElement.style.setProperty("--topbar-rendered-height", `${topbarEl.getBoundingClientRect().height}px`);
  };
  new ResizeObserver(syncTopbarHeight).observe(topbarEl);
  syncTopbarHeight();
}

// Theme toggle wiring — applyTheme() was already called at script load; this
// just hooks the button. The button's label updates via applyTheme().
const themeToggleBtn = document.getElementById("theme-toggle");
if (themeToggleBtn) themeToggleBtn.addEventListener("click", cycleTheme);

// Simple/Advanced mode toggle wiring — applyAdvancedModeUI() was already
// called at script load; this hooks the button the same way as theme.
const modeToggleBtn = document.getElementById("mode-toggle");
if (modeToggleBtn) modeToggleBtn.addEventListener("click", toggleAdvancedMode);

document.addEventListener("click", e => {
  if (!state.annotation.capture) return;
  const anchorTarget = e.target && e.target.closest ? e.target.closest("[data-vidux-anchor]") : null;
  const anchor = describeAnchorTarget(e.target);
  if (!anchor) return;
  e.preventDefault();
  e.stopPropagation();
  openAnnotationPopover(anchor, anchorTarget);
}, true);

document.addEventListener("mousedown", e => {
  const popover = document.getElementById("annotation-popover");
  if (!popover || popover.contains(e.target)) return;
  if (e.target && e.target.closest && e.target.closest("#root-annotation-toggle")) return;
  if (state.annotation.capture) return;
  clearAnnotationState();
}, true);

function refreshFloatingAnnotationSurfaces() {
  positionAnnotationPopover();
  scheduleCommentMarkerRender();
}

window.addEventListener("resize", refreshFloatingAnnotationSurfaces);
window.addEventListener("scroll", scheduleCommentMarkerRender, { passive: true });
els.pane.addEventListener("scroll", refreshFloatingAnnotationSurfaces, { passive: true });

// Keyboard shortcuts: `/` focuses filter, Esc clears or closes drawer.
document.addEventListener("keydown", e => {
  const editableTarget = isEditableShortcutTarget(e.target);
  if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "c") {
    if (editableTarget) return;
    const targetPath = currentCommentTargetPath();
    if (targetPath) {
      e.preventDefault();
      toggleAnnotationCapture(targetPath);
    }
  } else if (e.key === "/" && !editableTarget && document.activeElement !== els.filter) {
    e.preventDefault();
    els.filter.focus();
    els.filter.select();
  } else if (e.key === "Escape") {
    if (state.annotation.capture || state.annotation.anchor) {
      clearAnnotationState();
    } else if (sidebarEl && sidebarEl.classList.contains("is-open")) {
      sidebarEl.classList.remove("is-open");
    } else if (document.activeElement === els.filter && state.filter) {
      els.filter.value = "";
      state.filter = "";
      renderSidebar();
    }
  }
});

// Browser back/forward — restore the selection that matches the new URL.
// If the user navigates back past the first selection, return to dashboard.
window.addEventListener("popstate", () => {
  const matched = applyUrlSelection();
  if (!matched) {
    if (isAdvancedMode()) selectDashboard({ skipUrl: true });
    else { state.active = null; state.activeTab = "PLAN.md"; renderSidebar(); renderEmptyPane(); }
  }
});

async function autoRefreshTick() {
  if (autoRefreshInFlight) return;
  autoRefreshInFlight = true;
  try {
    await loadAll({
      preserveSelection: true,
      preserveScroll: true,
      quiet: true,
    });
    await refreshVisibleComments();
  } finally {
    autoRefreshInFlight = false;
  }
}

function startAutoRefresh() {
  if (!AUTO_REFRESH_INTERVAL_MS) return;
  window.setInterval(autoRefreshTick, AUTO_REFRESH_INTERVAL_MS);
}

// Initial load.
loadAll().then(startAutoRefresh);
