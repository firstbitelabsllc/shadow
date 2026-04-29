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
const ANCHOR_SELECTOR = "h1,h2,h3,h4,h5,h6,p,li,blockquote,pre,table,tr,.contact-card,.lead-row";

function fmtAge(days) {
  if (days < 1) return "today";
  if (days < 2) return "1d";
  if (days < 30) return `${Math.round(days)}d`;
  if (days < 365) return `${Math.round(days / 30)}mo`;
  return `${(days / 365).toFixed(1)}y`;
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

  const groups = new Map();
  for (const plan of filteredPlans) {
    if (!groups.has(plan.repo)) groups.set(plan.repo, []);
    groups.get(plan.repo).push(plan);
  }

  els.count.textContent =
    `${state.plans.length} plans · ${groups.size} repos · ${state.artifacts.length} artifacts${fleetCompletionStat(state.plans)}`;

  if (filteredPlans.length === 0 && filteredArtifacts.length === 0) {
    els.list.innerHTML = `<p class="muted" style="padding:12px">no matches</p>`;
    return;
  }

  // Artifacts section (top — decoupled from plans).
  let artifactsHTML = "";
  if (filteredArtifacts.length) {
    const rows = filteredArtifacts.map(a => {
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
    }).join("");
    artifactsHTML = `
      <div class="repo-group">
        <h2>artifacts <span class="repo-count">(${filteredArtifacts.length})</span></h2>
      </div>
      ${rows}`;
  }

  const repoOrder = [...groups.keys()].sort();
  const plansHTML = repoOrder.map(repo => {
    const rows = groups.get(repo);
    const inner = rows.map(plan => {
      const active = state.active && state.active.kind === "plan" && state.active.path === plan.path ? "is-active" : "";
      const slug = plan.slug === "_root_" ? "(root)" : plan.slug;
      const stats = plan.task_stats || { counts: {}, total: 0 };
      const invCount = (plan.investigations || []).length;
      return `
        <div class="plan-row ${active}" data-kind="plan" data-path="${escapeAttr(plan.path)}">
          <div class="plan-row-head">
            <span class="pill pill-${plan.status}" title="${plan.status} · ${fmtAge(plan.age_days)}"></span>
            <span>${escapeText(slug)}</span>
          </div>
          ${plan.purpose ? `<div class="plan-row-purpose">${escapeText(plan.purpose)}</div>` : ""}
          <div class="plan-row-meta">
            <span>${fmtAge(plan.age_days)}</span>
            <span>${(plan.size / 1024).toFixed(1)}KB</span>
            ${plan.siblings.length ? `<span>+${plan.siblings.length}</span>` : ""}
          </div>
          <div class="progress-row">
            ${renderProgressBar(stats)}
            ${renderProgressLabel(stats, invCount)}
          </div>
        </div>`;
    }).join("");
    return `
      <div class="repo-group">
        <h2>${escapeText(repo)} <span class="repo-count">(${rows.length})</span></h2>
      </div>
      ${inner}`;
  }).join("");

  els.list.innerHTML = artifactsHTML + plansHTML;

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
        <span>modified ${fmtAge(a.age_days)} ago</span>
        <span>${(a.size / 1024).toFixed(1)}KB</span>
        <span class="muted">${escapeText(a.path)}</span>
      </div>
    </div>
    ${renderCommentsPanel(a.path)}
    <div class="markdown" id="md-body"><p class="muted">loading…</p></div>
  `;
  setupCommentsPanel(a.path);
  try {
    const res = await fetch(`/api/file?path=${encodeURIComponent(a.path)}`);
    if (!res.ok) {
      document.getElementById("md-body").innerHTML =
        `<div class="error">${res.status}: ${escapeText(await res.text())}</div>`;
      return;
    }
    const html = await res.text();
    // Artifacts are local files; write endpoints are loopback + same-origin only.
    const body = document.getElementById("md-body");
    body.innerHTML = html;
    decorateAnchorTargets(body);
  } catch (e) {
    document.getElementById("md-body").innerHTML =
      `<div class="error">failed to load artifact: ${escapeText(String(e))}</div>`;
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
  const headerHTML = `
    <div class="pane-header">
      <div class="breadcrumb">${escapeText(plan.rel)}</div>
      <h2>${escapeText(plan.repo)} · ${escapeText(plan.slug === "_root_" ? "(root)" : plan.slug)}</h2>
      <div class="meta">
        <span><span class="pill pill-${plan.status}"></span>${plan.status}</span>
        <span>modified ${fmtAge(plan.age_days)} ago</span>
        <span>${(plan.size / 1024).toFixed(1)}KB</span>
        <span class="muted">${escapeText(plan.path)}</span>
      </div>
    </div>
    ${renderPaneProgress(stats)}
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
  setupCommentsPanel(tabPath);

  try {
    const res = await fetch(`/api/file?path=${encodeURIComponent(tabPath)}`);
    if (!res.ok) {
      const txt = await res.text();
      document.getElementById("md-body").innerHTML =
        `<div class="error">${res.status}: ${escapeText(txt)}</div>`;
      return;
    }
    const md = await res.text();
    const html = window.marked
      ? window.marked.parse(md, { breaks: false, gfm: true })
      : naiveMarkdown(md);
    const body = document.getElementById("md-body");
    body.innerHTML = html;
    decorateAnchorTargets(body);
  } catch (e) {
    document.getElementById("md-body").innerHTML =
      `<div class="error">failed to load file: ${escapeText(String(e))}</div>`;
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
  const author = getStoredCommentAuthor();
  return `
    <section class="comments-panel" id="comments-panel" data-target-path="${escapeAttr(targetPath)}">
      <div class="comments-head">
        <div>
          <h3>Comments</h3>
          <p>Notes for this view. Use the top-bar Annotate control for exact targets.</p>
        </div>
        <div class="comments-tools">
          <span class="comment-count" id="comment-count">loading</span>
        </div>
      </div>
      <form class="comment-form" id="comment-form">
        <input id="comment-author" class="comment-author" name="author" maxlength="80" placeholder="Name" value="${escapeAttr(author)}" autocomplete="name">
        <textarea id="comment-body" name="body" rows="2" maxlength="8192" placeholder="Add a comment. Annotate first to attach it to a rendered line."></textarea>
        <div class="comment-anchor-preview" id="comment-anchor-preview" hidden></div>
        <div class="comment-actions">
          <span class="comment-status" id="comment-status"></span>
          <button type="submit">Add comment</button>
        </div>
      </form>
      <div class="comment-list" id="comment-list"></div>
    </section>`;
}

function setupCommentsPanel(targetPath) {
  const panel = document.getElementById("comments-panel");
  if (!panel) return;
  const form = document.getElementById("comment-form");
  const authorInput = document.getElementById("comment-author");
  const bodyInput = document.getElementById("comment-body");
  const status = document.getElementById("comment-status");

  loadComments(targetPath);
  updateAnnotationUI();

  authorInput.addEventListener("input", () => setStoredCommentAuthor(authorInput.value.trim()));
  form.addEventListener("submit", async e => {
    e.preventDefault();
    const author = authorInput.value.trim();
    const body = bodyInput.value.trim();
    if (!body) {
      status.textContent = "write a comment first";
      return;
    }
    setStoredCommentAuthor(author);
    status.textContent = "sending…";
    try {
      const res = await fetch("/api/comments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_path: targetPath,
          author,
          body,
          anchor: state.annotation.targetPath === targetPath ? state.annotation.anchor : null,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      bodyInput.value = "";
      clearAnnotationState();
      status.textContent = "added";
      await loadComments(targetPath);
      setTimeout(() => {
        if (status.textContent === "added") status.textContent = "";
      }, 1800);
    } catch (err) {
      status.textContent = `failed: ${String(err.message || err)}`;
    }
  });
}

function clearAnnotationState() {
  state.annotation.capture = false;
  state.annotation.targetPath = "";
  state.annotation.anchor = null;
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
  const panel = document.getElementById("comments-panel");
  const currentTarget = currentCommentTargetPath();
  const captureActive = state.annotation.capture && state.annotation.targetPath === currentTarget;
  const anchorActive = state.annotation.anchor && state.annotation.targetPath === currentTarget;
  const body = document.getElementById("md-body");
  const preview = document.getElementById("comment-anchor-preview");
  const status = document.getElementById("comment-status");
  const rootToggle = els.annotate;

  document.body.classList.toggle("is-annotation-mode", Boolean(captureActive));
  if (body) body.classList.toggle("is-annotation-capture", Boolean(captureActive));
  if (rootToggle) {
    rootToggle.disabled = !currentTarget;
    rootToggle.textContent = captureActive ? "Cancel" : (anchorActive ? "Retarget" : "Annotate");
    rootToggle.classList.toggle("is-active", Boolean(captureActive || anchorActive));
    rootToggle.setAttribute("aria-pressed", String(Boolean(captureActive)));
    rootToggle.title = currentTarget
      ? "Annotate selected view (Cmd/Ctrl+Shift+C)"
      : "Select a plan or artifact to annotate";
  }
  if (status && captureActive) {
    status.textContent = "select target in document";
  } else if (status && status.textContent === "select target in document") {
    status.textContent = "";
  }
  if (!preview) return;
  if (!anchorActive) {
    preview.hidden = true;
    preview.innerHTML = "";
    return;
  }
  preview.hidden = false;
  preview.innerHTML = `
    <span class="anchor-label">Selected target</span>
    <span class="anchor-text">${escapeText(state.annotation.anchor.label || state.annotation.anchor.excerpt || "")}</span>
    <button type="button" id="comment-anchor-clear">Clear</button>
  `;
  const clear = document.getElementById("comment-anchor-clear");
  if (clear) {
    clear.addEventListener("click", () => {
      state.annotation.anchor = null;
      state.annotation.capture = false;
      updateAnnotationUI();
    });
  }
}

function decorateAnchorTargets(container) {
  if (!container) return;
  let index = 0;
  container.querySelectorAll(ANCHOR_SELECTOR).forEach(el => {
    const text = compactText(el.innerText || el.textContent || "", 24);
    if (!text) return;
    index += 1;
    el.dataset.viduxAnchor = `a${index}`;
    el.dataset.viduxAnchorIndex = String(index);
  });
}

function compactText(value, limit = 360) {
  return String(value || "").replace(/\s+/g, " ").trim().slice(0, limit);
}

function describeAnchorTarget(rawTarget) {
  const container = document.getElementById("md-body");
  const target = rawTarget && rawTarget.closest ? rawTarget.closest("[data-vidux-anchor]") : null;
  if (!container || !target || !container.contains(target)) return null;
  const excerpt = compactText(target.innerText || target.textContent || "");
  const tag = target.tagName.toLowerCase();
  const index = Number.parseInt(target.dataset.viduxAnchorIndex || "0", 10);
  const heading = nearestHeadingText(target, container);
  const label = compactText(heading && heading !== excerpt ? `${heading} / ${excerpt}` : excerpt, 180);
  return {
    kind: "rendered",
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

function captureAnnotationTarget(rawTarget) {
  const anchor = describeAnchorTarget(rawTarget);
  if (!anchor) return;
  state.annotation.capture = false;
  state.annotation.anchor = anchor;
  updateAnnotationUI();
  const body = document.getElementById("comment-body");
  if (body) body.focus();
}

function findAnchorElement(anchor) {
  const body = document.getElementById("md-body");
  if (!body || !anchor) return null;
  if (anchor.selector) {
    try {
      const found = body.querySelector(anchor.selector);
      if (found) return found;
    } catch {
      // Fall back to excerpt matching if old stored selectors become invalid.
    }
  }
  const excerpt = compactText(anchor.excerpt || anchor.label || "", 120);
  if (!excerpt) return null;
  return [...body.querySelectorAll("[data-vidux-anchor]")].find(el => {
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
  } catch (err) {
    count.textContent = "error";
    list.innerHTML = `<div class="error">failed to load comments: ${escapeText(String(err.message || err))}</div>`;
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

els.pane.addEventListener("click", e => {
  if (!state.annotation.capture) return;
  const body = e.target && e.target.closest ? e.target.closest("#md-body") : null;
  if (!body) return;
  e.preventDefault();
  e.stopPropagation();
  captureAnnotationTarget(e.target);
}, true);

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
