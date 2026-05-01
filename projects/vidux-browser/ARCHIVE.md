# Archived Tasks

Archived by `vidux-plan-gc.py`. Append-only — do not edit.
Tasks here are historical record; they were [completed] when archived.

## Archived 2026-05-01T12:56Z

- [completed] T0a Leo reviewed PLAN.md, redirected to "please continue" → modal-Leo defaults applied (port 7191, Python stdlib, vidux/browser/, glob 3 conventions, section in /vidux SKILL.md)
- [completed] T0b Port 7191 confirmed (no collision with Storybook 6006, Vercel 3000-3002)

- [completed] T1a `~/Development/vidux/browser/server.py` — stdlib `ThreadingHTTPServer`, routes: `/`, `/static/*`, `/api/health`, `/api/plans`, `/api/file?path=…`. Path-traversal guard via `safe_resolve()` (path must resolve under `DEV_ROOT`).
- [completed] T1b `~/Development/vidux/browser/static/{index.html, style.css, app.js}` — sidebar + pane layout, `marked.js` from jsDelivr CDN, paper-and-ink palette, hot/stale/cold pills. Vanilla JS, no framework.
- [completed] T1c `~/Development/vidux/bin/vidux-browse` shell launcher — backgrounds server, polls `/api/health`, opens default browser. Symlinked to `~/bin/vidux-browse` (on PATH).
- [completed] T1d `~/Development/vidux/SKILL.md` got a `## Browser` section.
- [completed] T1e Verified: 40 plans across 7 repos discovered on first run (13 hot, 25 stale, 2 cold). Visual proof — `/tmp/vidux-browser-mvp.png` (sidebar), `/tmp/vidux-browser-render.png` (markdown), `/tmp/vidux-browser-tabs.png` (PROGRESS tab). Path-traversal guards verified (HTTP 403 for `/etc/passwd` and `~/.ssh/config`).
- [completed] T1f Bonus: sibling tabs (PLAN / PROGRESS / INBOX / ASK-LEO) shipped with MVP — was Phase 2 scope, but trivial once `plan_meta` was already surfacing siblings.

- [completed] T2b PROGRESS / INBOX / ASK-LEO tabs in pane (shipped early as T1f)
- [completed] T2e Status pill heuristic — "hot" ≤7d, "stale" 7-30d, "cold" >30d (shipped with MVP)
- [completed] T2f Filter across plans (shipped with MVP — searchbox over repo/slug/purpose)
- [completed] T2g Investigations sub-page — investigations strip rendered below sibling tabs in the pane; clicks open the inv `.md`. Shipped via T2Q+T2R in #41.
- [completed] T2j Tasks rendered as structured FSM — `task_stats()` parser + sidebar progress bar + pane progress block + fleet completion stat. Shipped via T2L–T2P in #41.
- [completed] T2L `task_stats()` parser shipped on `/api/plans` (counts by FSM status + ETA total parsed but secondary). PR #41.
- [completed] T2M Pretty stacked progress bar in sidebar (rounded, status-colored segments + "X/Y done · N%" label). PR #41.
- [completed] T2N Completion treatment shipped — gold gradient + "shipped ✓" mark at 100%; dashed bar + "no tasks yet" hint at 0. PR #41.
- [completed] T2O Pane progress block shipped — large %, ratio, status legend above the tab strip. PR #41.
- [completed] T2P Fleet completion stat shipped — `278/404 tasks (69%)` in topbar meta-count. PR #41.
- [completed] T2Q Investigations + evidence parser shipped — `discover_investigations()` auto-lists + parses `[Investigation:]` refs; `safe_resolve()` whitelist extended to `.md` under `investigations/` and `evidence/` dirs. PR #41.

