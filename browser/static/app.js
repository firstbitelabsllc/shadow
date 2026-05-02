// vidux browser — vanilla JS, no framework. Reads /api/* from the local server.

const state = {
  plans: [],
  artifacts: [],
  filter: "",
  active: null,        // {kind: 'plan'|'artifact', ...metadata}
  activeTab: "PLAN.md",
  annotation: {
    capture: false,
    targetPath: "",
    anchor: null,
  },
};
let activePopoverTarget = null;

// ─── URL deep-linking ─────────────────────────────────────────────────────
// Selection is reflected in the URL via query params so any view is bookmarkable
// and back/forward navigation works:
//   ?artifact=<slug>                 → load that artifact
//   ?plan=<rel-path>                 → load that plan (PLAN.md tab by default)
//   ?plan=<rel-path>&tab=PROGRESS.md → load plan + open a sibling tab
//   ?plan=<rel-path>&tab=INV:<path>  → load plan + open an investigation
// `rel` is the plan's path relative to DEV_ROOT (stable, readable, comes from
// /api/plans). Selection updates use pushState so each navigation lands in the
// browser's history; popstate restores state on back/forward.

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
  ".comments-panel",
  ".comments-head",
  ".comment-list .comment-item",
  ...RENDERED_ANCHOR_SELECTORS.map(selector => `#md-body ${selector}`),
].join(",");
const ANNOTATION_CAPTURE_EXCLUDE_SELECTOR = [
  "#root-annotation-toggle",
  "#root-readaloud-toggle",
  "#root-readaloud-voice",
  "#root-readaloud-voice *",
  "#refresh",
  "#sidebar-toggle",
  "#filter",
  "#annotation-popover",
  "#annotation-popover *",
  ".comment-anchor button",
].join(",");

function fmtAge(days) {
  if (days < 1) return "today";
  if (days < 2) return "1d";
  if (days < 30) return `${Math.round(days)}d`;
  if (days < 365) return `${Math.round(days / 30)}mo`;
  return `${(days / 365).toFixed(1)}y`;
}

// ─── UI state (per-browser, localStorage) ───────────────────────────────────
// Persists sidebar expand/collapse + recently-viewed across page reloads.
// Schema: { collapsed: ["repo:resplit-ios", "section:artifacts", ...],
//           recents:   [{id: "plan:<rel>"|"artifact:<slug>", ts: <ms>}] }
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

// Find the plan that lists `child` in its children array. O(n) per lookup but
// n=70 in practice, fine. Returns null if no parent indexed (parent_rel pointed
// at a path the discovery sweep didn't pick up, or there's no parent_rel).
function findParentPlan(child) {
  if (!child || !child.parent_rel) return null;
  for (const p of state.plans) {
    if (p.children && p.children.some(c => c.path === child.path)) return p;
  }
  return null;
}

// Walk up the parent chain from `plan` to root. Returns the ancestor list
// in root → leaf order (so [root, A, B] for a leaf C). Cycle-safe via
// visited-set; bails after 8 levels because deeper than that is almost
// certainly a config bug, not a real plan tree.
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

// Completion bar — per /vidux, completion (X/Y) is the headline. Bar segments
// are proportional to status counts. 100% gets a "shipped" gold treatment.
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

function fleetCompletionStat(plans) {
  let done = 0, total = 0;
  for (const p of plans) {
    const t = p.task_stats;
    if (!t) continue;
    done += t.counts?.completed || 0;
    total += t.total || 0;
  }
  if (!total) return "";
  return ` · ${done}/${total} tasks (${pct(done, total)}%)`;
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

function renderSidebar() {
  const filter = state.filter.toLowerCase();

  const filteredPlans = filter
    ? state.plans.filter(p =>
        p.repo.toLowerCase().includes(filter) ||
        p.slug.toLowerCase().includes(filter) ||
        (p.purpose || "").toLowerCase().includes(filter))
    : state.plans;

  const filteredArtifacts = filter
    ? state.artifacts.filter(a =>
        a.slug.toLowerCase().includes(filter) ||
        (a.title || "").toLowerCase().includes(filter))
    : state.artifacts;

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

  els.count.textContent =
    `${state.plans.length} plans · ${groups.size} repos · ${state.artifacts.length} artifacts${fleetCompletionStat(state.plans)}`;

  if (filteredPlans.length === 0 && filteredArtifacts.length === 0) {
    els.list.innerHTML = `<p class="muted" style="padding:12px">no matches</p>`;
    refreshAnnotationTargets();
    return;
  }

  // Helpers for collapsible group headers — used by recents, artifacts, repos.
  // Disclosure caret on left, count on right. Click toggles persisted state.
  function groupHeaderHTML(key, label, count) {
    const collapsed = isCollapsed(key);
    const caret = collapsed ? "▸" : "▾";
    const cls = collapsed ? "is-collapsed" : "";
    return `<div class="repo-group ${cls}" data-collapse-key="${escapeAttr(key)}">
      <h2><span class="caret">${caret}</span>${escapeText(label)} <span class="repo-count">(${count})</span></h2>
    </div>`;
  }
  function artifactRow(a) {
    const active = state.active && state.active.kind === "artifact" && state.active.path === a.path ? "is-active" : "";
    return `
      <div class="plan-row ${active}" data-kind="artifact" data-path="${escapeAttr(a.path)}">
        <div class="plan-row-head">
          <span class="pill pill-artifact" title="artifact · ${fmtAge(a.age_days)}"></span>
          <span>${escapeText(a.title || a.slug)}</span>
        </div>
        <div class="plan-row-meta">
          <span>${escapeText(a.slug)}.html</span>
          <span>${fmtAge(a.age_days)}</span>
          <span>${(a.size / 1024).toFixed(1)}KB</span>
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
        return plan ? { kind, plan } : null;
      } else if (kind === "artifact") {
        const a = state.artifacts.find(x => x.slug === key);
        return a ? { kind, a } : null;
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
    const progressHTML = hasChildren
      ? `
          <div class="progress-row progress-row-with-rollup">
            <div class="progress-row-line">
              <span class="progress-row-tag">this plan</span>
              ${renderProgressBar(stats, "is-self")}
              ${renderProgressLabel(stats, invCount)}
            </div>
            <div class="progress-row-line">
              <span class="progress-row-tag is-rollup">+ sub-plans (${agg.descendants || 0})</span>
              ${renderProgressBar(agg, "is-rollup")}
              ${renderProgressLabel(agg, 0)}
            </div>
          </div>`
      : `
          <div class="progress-row">
            ${renderProgressBar(stats)}
            ${renderProgressLabel(stats, invCount)}
          </div>`;
    const rowHTML = `
      <div class="plan-row ${active} ${childModifier}" data-kind="plan" data-path="${escapeAttr(plan.path)}" ${indentStyle}>
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
      ? plan.children
          .filter(child => byRel.has(child.rel))
          .map(child => renderPlanRow(child, depth + 1))
          .join("")
      : "";
    return rowHTML + childRowsHTML;
  }

  // Sort repos by their freshest plan (mtime desc — recently-touched repos
  // rise to the top). Within each repo, sort plans by mtime desc too.
  // Alphabetical-by-repo-name was the prior default; recency reflects what
  // the user is actually working on, which is usually the right answer.
  const maxMtime = repo => Math.max(...groups.get(repo).map(p => p.mtime || 0));
  const repoOrder = [...groups.keys()].sort((a, b) => maxMtime(b) - maxMtime(a));
  const plansHTML = repoOrder.map(repo => {
    const rows = groups.get(repo);
    rows.sort((a, b) => (b.mtime || 0) - (a.mtime || 0));
    const key = `repo:${repo}`;
    const header = groupHeaderHTML(key, repo, rows.length);
    if (isCollapsed(key)) return header;
    const inner = rows.map(plan => renderPlanRow(plan, 0)).join("");
    return header + inner;
  }).join("");

  els.list.innerHTML = recentsHTML + artifactsHTML + plansHTML;

  // Click on group header → toggle collapsed state for that section/repo.
  els.list.querySelectorAll(".repo-group[data-collapse-key]").forEach(grp => {
    grp.querySelector("h2")?.addEventListener("click", () => {
      const key = grp.getAttribute("data-collapse-key");
      if (key) { toggleCollapsed(key); renderSidebar(); }
    });
  });

  els.list.querySelectorAll(".plan-row").forEach(row => {
    row.addEventListener("click", () => {
      const kind = row.getAttribute("data-kind");
      const path = row.getAttribute("data-path");
      if (kind === "artifact") {
        const a = state.artifacts.find(x => x.path === path);
        if (a) selectArtifact(a);
      } else {
        const plan = state.plans.find(p => p.path === path);
        if (plan) selectPlan(plan);
      }
    });
  });
  refreshAnnotationTargets();
}

async function loadAll() {
  els.count.textContent = "loading…";
  try {
    const [plansRes, artifactsRes] = await Promise.all([
      fetch("/api/plans"),
      fetch("/api/artifacts"),
    ]);
    const plansData = await plansRes.json();
    const artifactsData = await artifactsRes.json();
    state.plans = plansData.plans || [];
    state.artifacts = artifactsData.artifacts || [];
    renderSidebar();
    // Restore selection from URL on initial load (and after refresh).
    applyUrlSelection();
  } catch (e) {
    els.count.textContent = "error";
    els.list.innerHTML = `<div class="error">failed to load: ${escapeText(String(e))}</div>`;
  }
}

async function selectPlan(plan, opts = {}) {
  state.active = { kind: "plan", ...plan };
  state.activeTab = opts.tab || "PLAN.md";
  trackRecent("plan", plan.rel);
  if (!opts.skipUrl) {
    const p = new URLSearchParams();
    p.set("plan", plan.rel);
    if (state.activeTab && state.activeTab !== "PLAN.md") p.set("tab", state.activeTab);
    pushUrl(p);
  }
  renderSidebar();
  if (opts.scrollIntoView) scrollActiveRowIntoView();
  await renderPane();
}

async function selectArtifact(a, opts = {}) {
  state.active = { kind: "artifact", ...a };
  state.activeTab = null;
  trackRecent("artifact", a.slug);
  if (!opts.skipUrl) {
    const p = new URLSearchParams();
    p.set("artifact", a.slug);
    pushUrl(p);
  }
  renderSidebar();
  if (opts.scrollIntoView) scrollActiveRowIntoView();
  await renderArtifactPane();
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

async function renderArtifactPane() {
  const a = state.active;
  if (!a || a.kind !== "artifact") return;
  els.pane.scrollTop = 0;
  clearAnnotationState();
  els.pane.innerHTML = `
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
  setupCommentsPanel(a.path);
  refreshAnnotationTargets();
  try {
    const res = await fetch(`/api/file?path=${encodeURIComponent(a.path)}`);
    if (!res.ok) {
      document.getElementById("md-body").innerHTML =
        `<div class="error">${res.status}: ${escapeText(await res.text())}</div>`;
      refreshAnnotationTargets();
      return;
    }
    const html = await res.text();
    // Artifacts are local files; write endpoints are loopback + same-origin only.
    const body = document.getElementById("md-body");
    body.innerHTML = html;
    refreshAnnotationTargets();
  } catch (e) {
    document.getElementById("md-body").innerHTML =
      `<div class="error">failed to load artifact: ${escapeText(String(e))}</div>`;
    refreshAnnotationTargets();
  }
}

async function renderPane() {
  if (!state.active) return;
  clearAnnotationState();
  const plan = state.active;
  const tabs = ["PLAN.md", ...plan.siblings];
  const investigations = plan.investigations || [];
  const isInvActive = state.activeTab.startsWith("INV:");
  const activeInvPath = isInvActive ? state.activeTab.slice(4) : null;

  let tabPath;
  if (isInvActive) {
    tabPath = activeInvPath;
  } else if (state.activeTab === "PLAN.md") {
    tabPath = plan.path;
  } else {
    tabPath = plan.path.replace(/\/PLAN\.md$/, `/${state.activeTab}`);
  }

  const stats = plan.task_stats || { counts: {}, total: 0 };
  const aggregate = plan.aggregate_stats || stats;
  const invStripHTML = investigations.length ? `
    <div class="pane-investigations-strip">
      <span class="label">Investigations (${investigations.length}):</span>
      ${investigations.map(p => {
        const name = p.split("/").pop().replace(/\.md$/, "");
        const isActive = activeInvPath === p ? "is-active" : "";
        return `<button data-inv="${escapeAttr(p)}" class="${isActive}">${escapeText(name)}</button>`;
      }).join("")}
    </div>` : "";

  els.pane.scrollTop = 0;
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
    <div class="pane-header">
      ${parentLinkHTML}
      <div class="breadcrumb">${escapeText(plan.rel)}</div>
      <h2>${escapeText(plan.slug === "_root_" ? plan.repo : `${plan.repo} · ${plan.slug}`)}</h2>
      <div class="meta">
        <span><span class="pill pill-${plan.status}"></span>${plan.status}</span>
        <span>${fmtAge(plan.age_days) === "today" ? "modified today" : `modified ${fmtAge(plan.age_days)} ago`}</span>
        <span>${(plan.size / 1024).toFixed(1)}KB</span>
        <span class="muted">${escapeText(plan.path)}</span>
      </div>
    </div>
    ${renderPaneProgress(stats)}
    ${renderPaneAggregateProgress(plan, aggregate)}
    ${renderPaneSubplans(plan)}
    <div class="pane-tabs">
      ${tabs.map(t => `
        <button data-tab="${escapeAttr(t)}" class="${t === state.activeTab ? "is-active" : ""}">${escapeText(t)}</button>
      `).join("")}
    </div>
    ${invStripHTML}
    ${renderCommentsPanel(tabPath)}
    <div class="markdown" id="md-body"><p class="muted">loading…</p></div>
  `;
  els.pane.innerHTML = headerHTML;
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
  els.pane.querySelectorAll(".subplan-row").forEach(row => {
    row.addEventListener("click", () => {
      const rel = row.getAttribute("data-subplan-rel");
      const target = state.plans.find(p => p.rel === rel);
      if (target) selectPlan(target, { scrollIntoView: true });
    });
  });
  setupCommentsPanel(tabPath);
  refreshAnnotationTargets();

  try {
    const res = await fetch(`/api/file?path=${encodeURIComponent(tabPath)}`);
    if (!res.ok) {
      const txt = await res.text();
      document.getElementById("md-body").innerHTML =
        `<div class="error">${res.status}: ${escapeText(txt)}</div>`;
      refreshAnnotationTargets();
      return;
    }
    const md = stripParentMetadata(await res.text());
    const html = window.marked
      ? window.marked.parse(md, { breaks: false, gfm: true })
      : naiveMarkdown(md);
    const body = document.getElementById("md-body");
    body.innerHTML = html;
    refreshAnnotationTargets();
  } catch (e) {
    document.getElementById("md-body").innerHTML =
      `<div class="error">failed to load file: ${escapeText(String(e))}</div>`;
    refreshAnnotationTargets();
  }
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
  return `
    <section class="comments-panel" id="comments-panel" data-target-path="${escapeAttr(targetPath)}">
      <div class="comments-head">
        <div>
          <h3>Comments</h3>
          <p>Use Annotate, then click a target to open the popover composer.</p>
        </div>
        <div class="comments-tools">
          <span class="comment-count" id="comment-count">loading</span>
        </div>
      </div>
      <div class="comment-list" id="comment-list"></div>
    </section>`;
}

function setupCommentsPanel(targetPath) {
  const panel = document.getElementById("comments-panel");
  if (!panel) return;
  loadComments(targetPath);
  updateAnnotationUI();
}

function clearAnnotationState() {
  state.annotation.capture = false;
  state.annotation.targetPath = "";
  state.annotation.anchor = null;
  closeAnnotationPopover({ preserveState: true });
  updateAnnotationUI();
}

function toggleAnnotationCapture(targetPath) {
  if (state.annotation.capture && state.annotation.targetPath === targetPath) {
    clearAnnotationState();
    return;
  }
  state.annotation.capture = true;
  state.annotation.targetPath = targetPath;
  state.annotation.anchor = null;
  updateAnnotationUI();
}

function currentCommentTargetPath() {
  const panel = document.getElementById("comments-panel");
  return panel ? panel.getAttribute("data-target-path") || "" : "";
}

function updateAnnotationUI() {
  const currentTarget = currentCommentTargetPath();
  const captureActive = state.annotation.capture && state.annotation.targetPath === currentTarget;
  const anchorActive = state.annotation.anchor && state.annotation.targetPath === currentTarget;
  const rootToggle = els.annotate;

  document.body.classList.toggle("is-annotation-mode", Boolean(captureActive));
  if (rootToggle) {
    rootToggle.disabled = !currentTarget;
    rootToggle.textContent = captureActive ? "Cancel" : (anchorActive ? "Retarget" : "Annotate");
    rootToggle.classList.toggle("is-active", Boolean(captureActive || anchorActive));
    rootToggle.setAttribute("aria-pressed", String(Boolean(captureActive)));
    rootToggle.title = currentTarget
      ? "Annotate selected view (Cmd/Ctrl+Shift+C)"
      : "Select a plan or artifact to annotate";
  }
}

function openAnnotationPopover(anchor, targetEl) {
  const targetPath = currentCommentTargetPath();
  if (!targetPath || !anchor) return;
  closeAnnotationPopover({ preserveState: true });

  state.annotation.capture = false;
  state.annotation.targetPath = targetPath;
  state.annotation.anchor = anchor;
  activePopoverTarget = targetEl || findAnchorElement(anchor);

  const author = getStoredCommentAuthor();
  const label = anchor.label || anchor.excerpt || "Selected target";
  const popover = document.createElement("aside");
  popover.id = "annotation-popover";
  popover.className = "annotation-popover";
  popover.setAttribute("role", "dialog");
  popover.setAttribute("aria-label", "Add annotation");
  popover.innerHTML = `
    <div class="annotation-popover-head">
      <div>
        <span class="annotation-popover-kicker">Annotating</span>
        <strong>${escapeText(label)}</strong>
      </div>
      <button type="button" class="annotation-popover-close" aria-label="Close">&times;</button>
    </div>
    <form id="annotation-popover-form" class="annotation-popover-form">
      <input id="annotation-popover-author" name="author" maxlength="80" placeholder="Name" value="${escapeAttr(author)}" autocomplete="name">
      <textarea id="annotation-popover-body" name="body" rows="3" maxlength="8192" placeholder="Add a comment"></textarea>
      <div class="annotation-popover-actions">
        <span id="annotation-popover-status" class="annotation-popover-status"></span>
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

  closeButton.addEventListener("click", clearAnnotationState);
  cancelButton.addEventListener("click", clearAnnotationState);
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
    status.textContent = "sending…";
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
      clearAnnotationState();
    } catch (err) {
      status.textContent = `failed: ${String(err.message || err)}`;
    }
  });

  updateAnnotationUI();
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
  const target = activePopoverTarget && document.body.contains(activePopoverTarget)
    ? activePopoverTarget
    : findAnchorElement(state.annotation.anchor);
  activePopoverTarget = target;
  const margin = 12;
  const width = Math.min(380, Math.max(280, window.innerWidth - margin * 2));
  popover.style.width = `${width}px`;
  const height = popover.offsetHeight || 230;
  let left = margin;
  let top = margin;
  if (target) {
    const rect = target.getBoundingClientRect();
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

function findAnchorElement(anchor) {
  if (!anchor) return null;
  if (anchor.selector) {
    try {
      const found = document.querySelector(anchor.selector);
      if (found) return found;
    } catch {
      // Fall back to excerpt matching if old stored selectors become invalid.
    }
  }
  const excerpt = compactText(anchor.excerpt || anchor.label || "", 120);
  if (!excerpt) return null;
  return [...document.querySelectorAll("[data-vidux-anchor]")].find(el => {
    const text = compactText(el.innerText || el.textContent || "", 180);
    return text.includes(excerpt) || excerpt.includes(text);
  }) || null;
}

function jumpToCommentAnchor(anchor) {
  const target = findAnchorElement(anchor);
  if (!target) return;
  target.scrollIntoView({ block: "center", behavior: "smooth" });
  target.classList.add("is-anchor-highlight");
  setTimeout(() => target.classList.remove("is-anchor-highlight"), 2200);
}

async function loadComments(targetPath) {
  const list = document.getElementById("comment-list");
  const count = document.getElementById("comment-count");
  if (!list || !count) return;
  const panel = document.getElementById("comments-panel");
  if (!panel || panel.getAttribute("data-target-path") !== targetPath) return;
  try {
    const res = await fetch(`/api/comments?path=${encodeURIComponent(targetPath)}`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    const currentPanel = document.getElementById("comments-panel");
    if (!currentPanel || currentPanel.getAttribute("data-target-path") !== targetPath) return;
    const comments = data.comments || [];
    count.textContent = `${comments.length} ${comments.length === 1 ? "comment" : "comments"}`;
    if (!comments.length) {
      list.innerHTML = `<div class="comment-empty">No comments yet. Use Annotate for exact placement.</div>`;
      refreshAnnotationTargets();
      return;
    }
    list.innerHTML = comments.map(renderComment).join("");
    list.querySelectorAll("[data-comment-jump]").forEach(button => {
      button.addEventListener("click", () => {
        const id = button.getAttribute("data-comment-jump");
        const comment = comments.find(item => item.id === id);
        if (comment && comment.anchor) jumpToCommentAnchor(comment.anchor);
      });
    });
    refreshAnnotationTargets();
  } catch (err) {
    count.textContent = "error";
    list.innerHTML = `<div class="error">failed to load comments: ${escapeText(String(err.message || err))}</div>`;
    refreshAnnotationTargets();
  }
}

function renderComment(comment) {
  const anchorHTML = renderCommentAnchor(comment);
  return `
    <article class="comment-item">
      <div class="comment-meta">
        <strong>${escapeText(comment.author || "Anonymous")}</strong>
        <span>${escapeText(formatCommentTime(comment.created_at))}</span>
      </div>
      ${anchorHTML}
      <div class="comment-body">${escapeText(comment.body || "").replace(/\n/g, "<br>")}</div>
    </article>`;
}

function renderCommentAnchor(comment) {
  const anchor = comment.anchor;
  if (!anchor || typeof anchor !== "object") return "";
  const label = anchor.label || anchor.excerpt || "captured target";
  return `
    <div class="comment-anchor">
      <button type="button" data-comment-jump="${escapeAttr(comment.id || "")}">Target</button>
      <span>${escapeText(label)}</span>
    </div>`;
}

function formatCommentTime(raw) {
  if (!raw) return "";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
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
els.refresh.addEventListener("click", loadAll);
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

window.addEventListener("resize", positionAnnotationPopover);
els.pane.addEventListener("scroll", positionAnnotationPopover, { passive: true });

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
// If the user navigates back past the first selection, clear the pane.
window.addEventListener("popstate", () => {
  const matched = applyUrlSelection();
  if (!matched) {
    state.active = null;
    state.activeTab = "PLAN.md";
    renderSidebar();
    els.pane.innerHTML = "";
  }
});

// Initial load.
loadAll();
