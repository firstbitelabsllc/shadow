# Vidux Browser

## Purpose

Two surfaces, one tool, for any /vidux user (not Leo-specific):

1. **Plan viewer** — localhost web UI that visualizes every `PLAN.md` + canonical sibling artifacts (`INBOX.md`, `investigations/`, `evidence/`) across the user's repo fleet at a glance. Answers "where am I" without grepping markdown.
2. **Ad-hoc artifact surface** — anytime, anywhere in any session, an agent can drop an HTML artifact into a known directory and it appears in the browser as a top-level "Artifacts" section. Decoupled from any specific plan. The artifact creator is "in chat" — agents POST or write files; the browser surfaces them.
3. **Named comment surface** — LAN viewers can leave named comments on a plan tab or artifact, like lightweight annotations. Comments are vidux-browse app data, not plan/artifact source edits.

The plan files ARE the source of truth (per `/vidux` discipline). The browser is **read-only against plans**, **append-only against artifacts**, and **append-only against comments**.

### Audience clarifier (added 2026-04-25)

This is a **generic /vidux user tool**. Default schema = canonical /vidux only (PLAN.md sections, INBOX.md, investigations/, evidence/). Leo-fleet conventions (`PROGRESS.md` as separate file, `ASK-LEO.md` per `/vidux-leo` overlay) render when present but are not required. A clean-vidux-schema repo with no Leo extensions still works.

## Evidence

- [Source: filesystem sweep 2026-04-25] **40+ PLAN.md files** found across `~/Development/`, in 3 different conventions:
  - `<repo>/ai/plans/<slug>/PLAN.md` — trysnowcubes-web, expenses-web, expenses-web-switchboard, `~/Development/ai/vidux/`
  - `<repo>/vidux/<slug>/PLAN.md` — strongyes-web (5 plans)
  - `<repo>/projects/<slug>/PLAN.md` — `~/Development/vidux/` core (15 plans)
  - `<repo>/PLAN.md` — root-level (vidux, expenses-web, everything, strongyes-web)
- [Source: this session] Leo asked "where are we" 3-5x in the last week of resumes; symptom of the visualization gap
- [Source: corpus read of `~/Development/vidux/` 2026-04-25] Canonical /vidux artifacts (verified across SKILL.md + DOCTRINE.md + ENFORCEMENT.md + LOOP.md + INGREDIENTS.md + guides/*.md):
  - `PLAN.md` — sections: Purpose · Evidence · Constraints · Tasks · Decision Log · Open Questions · Surprises · Progress
  - `INBOX.md` — Radar→Writer queue bridge per `guides/fleet-ops.md:351-388`. Append-only for scanners, read-write for writers, max 20 entries. **Canonical core, not a Leo extension.**
  - `investigations/<slug>.md` — compound-task sub-plans per `guides/investigation.md`. Sections: Tickets · Evidence · Root Cause · Impact Map · Fix Spec · Tests · Gate
  - `evidence/YYYY-MM-DD-<slug>.md` — formal evidence files per `guides/evidence-format.md`. Sections: Goal · Sources · Findings · Recommendations
  - Status FSM markers: `[pending]`/`[in_progress]`/`[completed]`/`[blocked]`/`[P]`/`[Depends:]`/`[Investigation:]`/`[spawns:]`/`[Source:]`
- [Source: `/vidux-leo` Section 3 + this-session miscall correction] Leo-fleet extensions (NOT canonical /vidux):
  - `PROGRESS.md` as separate file — core has `## Progress` SECTION inside PLAN.md; splitting is a Leo pattern when log grows
  - `ASK-LEO.md` — Leo-specific human-sync gate, `/vidux-leo` overlay only
  - `RALPH.md` — separate `/ralph` skill, "queue contract absorbed into Vidux's PLAN.md task FSM" per INGREDIENTS.md:159
- [Source: vidux SKILL.md] PLAN.md is canonical state; browser must respect that (read-only)
- [Source: /auto Architecture row] Monolith-first → extend `~/Development/vidux/`, no new repo
- [Source: /auto "create a new repo?" → No until Sept 2026] Lives inside `vidux/browser/`, not standalone

## Constraints

**ALWAYS:**
- Read-only against plan source — viewer never edits PLAN.md / PROGRESS.md / etc.
- Localhost by default (`127.0.0.1:7191`); LAN bind only when launcher/LaunchAgent explicitly sets `VIDUX_BROWSER_HOST=0.0.0.0`
- Python stdlib only for v1 (no Flask, no FastAPI, no Node) — matches Leo's "simple css html" ask
- Plain HTML + CSS + vanilla JS — no React/Vue/Svelte/Tailwind/etc.
- One stable URL Leo can bookmark
- Survives PLAN.md schema drift (renders any markdown gracefully even if structure varies)
- Comments are separate app data (`~/.vidux-browser/comments.jsonl` by default), never mutations to plan or artifact source files

**NEVER:**
- New repo (extend vidux core)
- AWS/GCP/Firebase / paid SaaS
- Editing plan files from the browser (read-only contract is load-bearing)
- Treat LAN comments as plan writes, task claims, repo writes, or inbox mutation
- Heavy framework (Leo asked for simple)

## Decision table

Decisions to lock in Phase 0 sign-off. `/auto` modal-Leo column is the proposed default.

| Decision | Options | /auto modal-Leo |
|---|---|---|
| Where the code lives | `~/Development/vidux/browser/` (extend core) vs `~/.claude-automations/vidux-browser/` (automation pattern) vs new repo (banned) | **`~/Development/vidux/browser/`** — vidux SKILL.md cross-refs already point at vidux/. One mental model. |
| Tech stack | (a) Python stdlib `http.server`, (b) Python + Flask, (c) Node + Express, (d) Bun + Hono | **(a) Python stdlib** — zero deps, ships fastest, Leo said "simple" |
| Port | 7191 (VIDUX T9), 4242, 9999 | **7191** — mnemonic, no collision (Storybook 6006, Vercel 3000-3002, Snowcubes preview is remote) |
| Live vs static | (1) HTTP server reads files on each request, (2) static SSG rebuild | **(1) HTTP live** — Leo asked for "current chat" → fresh state every render |
| Markdown rendering | server-side (Python `markdown` package) vs client-side (`marked.js`) vs naive regex | **client-side `marked.js` from CDN** — zero Python deps; markdown.js is one `<script>` tag |
| Fleet discovery | hardcoded list / glob `~/Development/*/{ai/plans,vidux,projects}/*/PLAN.md` / config file | **glob with all 3 conventions** — handles trysnowcubes-web + strongyes-web + vidux core uniformly |
| Auto-refresh | manual / poll-every-5s / Server-Sent Events / WebSocket | **poll every 5s** — simplest, fine for ~50 files |
| Session view source | `~/.claude/projects/<repo-slug>/<sid>.jsonl` | **latest-modified JSONL per repo, parsed for last 5 user/assistant turns** — summary not firehose |
| Skill home | new `/vidux-browser` skill vs section in `/vidux` SKILL.md | **section in `/vidux` SKILL.md** — Leo's exact ask: "core /vidux create an extension" |

## Scope (MVP vs v1 vs polish)

### MVP (Phase 1) — single-day ship
The minimum surface that beats grepping:
- Server reads all `PLAN.md` files via the 3-convention glob
- Sidebar lists plans grouped by repo, with status pill (active / completed / blocked / unknown)
- Main pane renders selected PLAN.md (markdown → HTML)
- Refresh button to re-scan (no polling yet)
- One CLI: `vidux browse` opens `http://127.0.0.1:7191`

### v1 (Phase 2) — fleet-wide + sessions
- Add PROGRESS.md, INBOX.md, ASK-LEO.md as tabs per plan (when present)
- Add "Sessions" panel: latest Claude Code session per repo, with last 5 turns excerpted
- Auto-refresh poll every 5s
- Filter sidebar by repo / by status
- Search (Cmd+K) across all PLAN.md content

### Polish (Phase 3) — quality of life
- Memory file viewer (read MEMORY.md + linked entries from `~/.claude/projects/.../memory/`)
- Ledger entries (`.agent-ledger/activity.jsonl`) per repo, latest 10
- launchd plist auto-start on login
- Decision Log diffing (highlight new entries since last visit)
- Scheduled-task viewer (`.claude/scheduled_tasks.lock` + cron registry)

## Tasks

Phase 0: Sign-off
- [completed] T0a Leo reviewed PLAN.md, redirected to "please continue" → modal-Leo defaults applied (port 7191, Python stdlib, vidux/browser/, glob 3 conventions, section in /vidux SKILL.md)
- [completed] T0b Port 7191 confirmed (no collision with Storybook 6006, Vercel 3000-3002)

Phase 1: MVP
- [completed] T1a `~/Development/vidux/browser/server.py` — stdlib `ThreadingHTTPServer`, routes: `/`, `/static/*`, `/api/health`, `/api/plans`, `/api/file?path=…`. Path-traversal guard via `safe_resolve()` (path must resolve under `DEV_ROOT`).
- [completed] T1b `~/Development/vidux/browser/static/{index.html, style.css, app.js}` — sidebar + pane layout, `marked.js` from jsDelivr CDN, paper-and-ink palette, hot/stale/cold pills. Vanilla JS, no framework.
- [completed] T1c `~/Development/vidux/bin/vidux-browse` shell launcher — backgrounds server, polls `/api/health`, opens default browser. Symlinked to `~/bin/vidux-browse` (on PATH).
- [completed] T1d `~/Development/vidux/SKILL.md` got a `## Browser` section.
- [completed] T1e Verified: 40 plans across 7 repos discovered on first run (13 hot, 25 stale, 2 cold). Visual proof — `/tmp/vidux-browser-mvp.png` (sidebar), `/tmp/vidux-browser-render.png` (markdown), `/tmp/vidux-browser-tabs.png` (PROGRESS tab). Path-traversal guards verified (HTTP 403 for `/etc/passwd` and `~/.ssh/config`).
- [completed] T1f Bonus: sibling tabs (PLAN / PROGRESS / INBOX / ASK-LEO) shipped with MVP — was Phase 2 scope, but trivial once `plan_meta` was already surfacing siblings.

Phase 2: v1 — plan-viewer enrichment
- [pending] T2a Discovery upgrades — handle missing files gracefully, surface broken markdown [ETA: 0.5h]
- [completed] T2b PROGRESS / INBOX / ASK-LEO tabs in pane (shipped early as T1f)
- [pending] T2c Session panel — read latest JSONL per repo from `~/.claude/projects/`, parse summary [ETA: 1.5h]
- [pending] T2d Auto-poll every 5s [ETA: 0.25h]
- [completed] T2e Status pill heuristic — "hot" ≤7d, "stale" 7-30d, "cold" >30d (shipped with MVP)
- [completed] T2f Filter across plans (shipped with MVP — searchbox over repo/slug/purpose)
- [completed] T2g Investigations sub-page — investigations strip rendered below sibling tabs in the pane; clicks open the inv `.md`. Shipped via T2Q+T2R in #41.
- [pending] T2h Evidence directory viewer — `evidence/YYYY-MM-DD-<slug>.md` rendered as a chronological timeline tab per plan [ETA: 0.75h]
- [pending] T2i Decision Log promoted to first-class — Doctrine: agents MUST NOT contradict logged directions; surface this prominently, not buried inside PLAN.md [ETA: 0.5h]
- [completed] T2j Tasks rendered as structured FSM — `task_stats()` parser + sidebar progress bar + pane progress block + fleet completion stat. Shipped via T2L–T2P in #41.
- [pending] T2k Cross-plan dashboard — "all in_progress across the fleet", "all blocked", "all open ASK-LEO", "all INBOX entries" [ETA: 1.5h]

Phase 2 — completion bar elevation (added 2026-04-25 per Leo "make a pretty bar … completion and a moving target key to vidux plans")
- [completed] T2L `task_stats()` parser shipped on `/api/plans` (counts by FSM status + ETA total parsed but secondary). PR #41.
- [completed] T2M Pretty stacked progress bar in sidebar (rounded, status-colored segments + "X/Y done · N%" label). PR #41.
- [completed] T2N Completion treatment shipped — gold gradient + "shipped ✓" mark at 100%; dashed bar + "no tasks yet" hint at 0. PR #41.
- [completed] T2O Pane progress block shipped — large %, ratio, status legend above the tab strip. PR #41.
- [completed] T2P Fleet completion stat shipped — `278/404 tasks (69%)` in topbar meta-count. PR #41.
- [completed] T2Q Investigations + evidence parser shipped — `discover_investigations()` auto-lists + parses `[Investigation:]` refs; `safe_resolve()` whitelist extended to `.md` under `investigations/` and `evidence/` dirs. PR #41.
- [completed] T2R Investigations strip shipped — secondary chip row below sibling tabs, only renders when present. PR #41.

Phase 3: Ad-hoc artifact surface (Leo's "anytime anywhere" ask 2026-04-25)
- [completed] T3a `~/Development/vidux/browser/artifacts/` directory shipped 2026-04-25
- [completed] T3b `/api/artifacts` endpoint shipped (title parsed from `<title>` or first `<h1>`, B1 fallback to `path.stem` on whitespace titles)
- [completed] T3c Top-level "Artifacts" section in sidebar shipped (chronological, decoupled from plans)
- [completed] T3d `.html` artifacts render via direct innerHTML in pane (localhost trust boundary)
- [completed] T3e Components CSS shim shipped (`.contact-card`, `.card-grid`, `.lead-row`, `.person-chip`)
- [completed] T3f Dogfood: 3 artifacts shipped (`cube-tier-a-vendors.html`, `cafe-expansion-2026-research.html`, `fleet-attribution-audit.html`)
- [completed] T3g `/api/artifact` POST endpoint shipped (gated behind whitelist + `ARTIFACT_MAX_BYTES` cap per B3 review)

Phase 4: Polish
- [pending] T4a Memory viewer [ETA: 1h]
- [pending] T4b Ledger entries [ETA: 1h]
- [pending] T4c launchd plist [ETA: 2h]
- [pending] T4d Decision Log diff highlighter [ETA: 2h]
- [pending] T4e Components inside markdown — `:::person` shorthand syntax that renders as a card without hand-writing HTML [ETA: 2h]

Phase 5: LAN-share + dark-mode (added 2026-04-26 — Moussey integration made artifact-share-with-Nicole-on-LAN first-class)
- [completed] T5a `server.py` honors `VIDUX_BROWSER_HOST` env var with safe localhost fallback. LaunchAgent sets it to `0.0.0.0` so iPhone access works on M4 Pro. Previously hardcoded localhost-only bind broke LAN access on M4 Pro (Studio worked because someone there had patched it locally). Both Macs now converge from clean clone. Shipped commit `8fb81f7` (upstream-equivalent ~`f3382c2`).
- [completed] T5b Artifacts dark-mode patch — all 12 `~/Development/vidux/browser/artifacts/snowcubes-*.html` got a `prefers-color-scheme: dark` block (cream→#1d1a14 warm dark, ink→#f1ebd9 warm light) so they don't glare against the dark sidebar in OS dark mode. Same warm palette inverted brightness — preserves brand voice.
- [completed] T5c Snowcubes hub artifact + 9 per-plan Nicole-friendly cards live at `vidux/browser/artifacts/snowcubes-*.html`, served via `/api/file?path=...` deep-link.
- [completed] T5d Moussey integration — `:4321/snowcubes` (mux-snowcubes-tile commit `cc03589`) and `:4321/vidux` both 307-redirect to vidux-browse on `:7191` using request-header host derivation, so `.local` and IP both work. Moussey homepage tile shipped.
- [completed] T5e Fleet ETA backfill pass — 8 background agents tagged ~145h of fleet AI-hours across 10 plans; vidux-browser plan itself tagged at 13h via commit `ce64cbc`. Cumulative fleet view now meaningful.
- [pending] VB-NEW-1 Manual dark/light toggle in topbar — currently OS-driven only, add button override [ETA: 1h]
- [pending] VB-NEW-2 ETA fleet-total in topbar meta — append "· Nh remaining" to "X plans · Y repos · Z artifacts · W/V tasks (P%)", calculated server-side [ETA: 0.5h]
- [pending] VB-NEW-3 Sort options in sidebar — by ETA descending, by mtime, by status [ETA: 1.5h]
- [pending] VB-NEW-4 Filter chips — quick filter for hot only / has-tasks only / has-ETA only [ETA: 1h]
- [pending] VB-NEW-5 Artifact dark-mode CSS as shared file — ship `static/artifact-base.css` artifacts can `<link>` to (with offline-use fallback), replacing the per-artifact embedded `prefers-color-scheme: dark` block [ETA: 1h]
- [pending] VB-NEW-6 Cron lane that auto-regenerates Nicole-friendly per-plan artifacts when source PLAN.md changes — mtime-delta detection, LaunchAgent label `com.leokwan.snowcubes-artifact-refresh`. Captured in `snowcubes-lan-share/PLAN.md` W2.1 — cross-link from here [ETA: 2h]
- [completed] VB-SEC-1 Harden write endpoints before work-computer LAN use — require loopback client, JSON content-type, and same-origin browser posts for `/api/artifact` and `/api/local-plan-note`; add browser server tests to the default gate. [Evidence: 2026-04-27 code-review findings P1/P2 on unauthenticated artifact writes, CSRFable plan notes, and missing browser tests] [Done: 2026-04-27; verified `python3 -m unittest tests.test_browser_server`, `npm test`, extra unittest modules, `npm run docs:build`]
- [completed] VB-COM-1 Named comments for plan tabs and artifacts — add `/api/comments` GET/POST, append-only JSONL storage, LAN same-origin JSON guard, UI name field + comment form + comment list. Comments do not write `PLAN.md`, `INBOX.md`, repo code, or artifact HTML. [Done: 2026-04-29]
- [completed] VB-COM-2 Anchored annotation mode — added a keyboard-triggered capture mode (`Cmd/Ctrl+Shift+C`) plus `Annotate` button so users can click the exact rendered plan/artifact location for a comment; anchor metadata persists separately from source files and anchored comments render with jump-to-target context. [Done: 2026-04-29; verified `python3 -m py_compile browser/server.py`, `node --check browser/static/app.js`, `python3 -m unittest tests.test_browser_server`, `npm test`, `npm run docs:build`, and live browser smoke on `127.0.0.1:7192`] [Evidence: Leo 2026-04-29: "tap command C or command shift C to trigger annotation mode and we can get the exact place of ur comment"]
- [completed] VB-DOC-1 README and browser reference catch-up for anchored comments — document `vidux-browse`, trusted-LAN launch caveat, append-only comment storage, `Annotate` / `Cmd/Ctrl+Shift+C`, and the no-plan-mutation boundary in public core docs. [Done: 2026-04-29] [Evidence: Leo 2026-04-29: "some version of that feels P0" and "ensure our vidux core and readme is up to date"]

## UI sketch (MVP)

```
┌─ vidux browser ──────────────────────────── [↻ refresh] ─┐
│                                                            │
│  trysnowcubes-web (7)        # /cube — Wedding Szn 2026   │
│  ▶ /cube              ●hot                                 │
│    /food-fairs-2026   ●hot   Purpose                       │
│    /fpa-analysis      ○stale Snowcubes outreach lane.      │
│    /shopify-ai-toolkit       Tier A vendor pipeline +      │
│    /snowcubes-ops-2026       cafe expansion.               │
│    /summer-flavors-2026                                    │
│    /cafe-expansion-2026      Tasks                         │
│                              - [✓] T1 vendor seed list    │
│  vidux/projects (15)         - [→] T2 DM round 1 (in prog) │
│    /scan-index               - [ ] T3 press pitch          │
│    /resplit                  - [ ] T4 cafe round 2         │
│    /pickles-custody                                        │
│    …                         Progress (latest 5)           │
│                              [2026-04-25] C91 …            │
│  strongyes-web (5)           [2026-04-25] C90 …            │
│    /research                 [2026-04-25] C89 …            │
│    /frontend-redesign                                      │
│    …                         [PLAN] [PROGRESS] [INBOX]     │
│                              [ASK-LEO] [SESSION]           │
│  expenses-web (2)                                          │
│  leojkwan (1)                                              │
└────────────────────────────────────────────────────────────┘
```

## Decision Log

- [DIRECTION] [2026-04-25 /auto] Lives in `~/Development/vidux/browser/`. Reason: monolith-first; vidux SKILL.md is the cross-ref hub already.
- [DIRECTION] [2026-04-25 /auto] Python stdlib over Flask/Node. Reason: Leo verbatim "simple css html"; zero deps maximizes ship velocity.
- [DIRECTION] [2026-04-25 /auto] Live HTTP server, not static SSG. Reason: Leo asked for "current chat and stuff" — fresh state on each render.
- [DIRECTION] [2026-04-25 /auto] Read-only contract is load-bearing. Reason: PLAN.md is canonical per /vidux; the browser views, never writes.
- [DIRECTION] [2026-04-26] vidux-browse must bind 0.0.0.0 by default for LAN-share; honor VIDUX_BROWSER_HOST env var with safe localhost fallback. Reason: artifact-share-with-Nicole-on-LAN is now first-class use case via Moussey integration.
- [DIRECTION] [2026-04-29] Named LAN comments are app data, not plan/artifact writes. Reason: LAN viewers need annotation-style feedback without reopening cross-machine write holes.
- [DIRECTION] [2026-04-29] Annotation comments should support precise anchors. Reason: Leo wants command-key capture mode that records the exact rendered place being commented on, while still keeping comments outside `PLAN.md`, `INBOX.md`, repo files, and artifact HTML.

## Open Questions

- Q1: Port 7191 — confirm no collision. Storybook=6006, Vercel dev=3000/3001, Snowcubes preview=remote, Switchboard=?. Leo to confirm.
- Q2: Should the browser also surface `.claude/scheduled_tasks.lock` + active CronCreate / ScheduleWakeup state? Useful for "what's the loop doing right now". → Defer to Phase 3 to keep MVP small.
- Q3: Cross-machine sync — Leo has 2 Macs. The browser is per-machine (reads local filesystem). Acceptable, or do we need a way to view the OTHER machine's state? → Defer; same machine is the 80% use case.
- Q4: Should the skill be `/vidux-browser` (sibling to /vidux) vs a section in `/vidux` SKILL.md? Leo's wording suggests the latter ("core /vidux create an extension"). Going with section-in-SKILL.md unless Leo says otherwise.
- Q5: Plan file conventions across repos vary (3 known patterns). Should we propose a unification (everyone moves to `ai/plans/`)? Or keep the glob flexible? → Keep glob flexible. Forced refactor would block this from shipping today.

## Surprises

- [2026-04-25] T1f sibling tabs (PROGRESS / INBOX / ASK-LEO) shipped with MVP, not Phase 2 — once `plan_meta()` surfaced siblings as a list, the JS tab strip was 30 lines vs the 60-line refactor it would have been later.
- [2026-04-25] Hot/stale/cold mtime classifier (originally T2e) had to ship with MVP because the sidebar needs *some* status sort. Wasn't worth shipping a placeholder.
- [2026-04-25] Filter searchbox (originally T2f) shipped with MVP because 40 plans is already too many to scan visually without a filter.

## Progress

- [2026-04-25] PLAN.md drafted. 40+ PLAN.md files inventoried across fleet via 3-convention glob. Awaiting Phase 0 sign-off.
- [2026-04-25] Phase 1 MVP shipped: server.py + static/{html,css,js} + bin/vidux-browse + SKILL.md section. 40 plans / 7 repos surfaced, hot/stale/cold pills, sibling tabs, filter, path-traversal guards. Visual proof captured. `vidux-browse` symlinked onto PATH. Next: Phase 2 sessions panel + auto-poll.
- [2026-04-25] Post-merge code review surfaced four bugs (B1–B4); shipped as one bundled commit (`vidux/browser-security-gate`):
  - B2 (security): `safe_resolve()` accepted any file under `DEV_ROOT`. Tightened to a `{PLAN.md, *SIBLING_FILES}` whitelist + `.html`-only under `ARTIFACTS_DIR`. Closes the localhost CSRF/exfil hole — a malicious tab on Leo's machine can no longer GET `…/.env` / `.ssh/config` / Shopify tokens via `/api/file?path=…`. Smoke-tested 7 paths (legit / random-py / outside-DEV / traversal / artifact / static-traversal / static-asset).
  - B1: title regex captured whitespace → empty title; now falls back to `path.stem`.
  - B3: `write_artifact()` didn't catch `OSError`; wrapped to return `(False, "write failed: …")`.
  - B4: static-asset path-traversal used a stringy `"/" in name or ".."` check; now resolves against `STATIC_DIR.resolve()` and rejects on `relative_to` failure.
- [2026-04-27] VB-SEC-1 shipped from LAN-readiness review: `/api/artifact` and `/api/local-plan-note` now require loopback client, `Content-Type: application/json`, and matching Origin/Referer when browser headers are present. `npm test` now includes `tests.test_browser_server`, covering artifact write allow/reject, LAN-client reject, simple-content-type reject, cross-origin reject, and local plan-note allow/reject. Next: work computer can pull and test LAN read-only vidux-browse without exposing write endpoints.
- [2026-04-25] **Completion bar shipped (PR #41 + companions).** Per Leo: *"make a pretty bar and have the concept of completion and a moving target key to vidux plans"* + *"divide tasks remaining over total tasks, some tasks are way fucking harder."* Headline metric is now completion (X/Y done), not ETA. Sidebar gets stacked status-colored progress bar + label, with gold "shipped ✓" treatment at 100% and dashed "no tasks yet" at 0. Pane gets a prominent progress block above the tab strip. Topbar adds fleet completion stat. Investigations strip renders child .md files when present (canonical /vidux subplan nesting now visible). Plus a `pane.scrollTop = 0` reset on every render — fixes the "jump back to padding" bug from prior-view scroll persistence. T2L–T2R + T2j + T2g flipped to [completed].
- [2026-04-25] **Doctrine companion landed via parallel agents (PRs leojkwan/vidux #42 + #43, leojkwan/ai #47).** /vidux SKILL.md softened — `[ETA: Xh]` is now optional, not "mandatory plan defect". Headline doctrine codified: *"Completion (X/Y tasks done) is the headline; ETA is supplementary, useful when tasks are similar-sized, skip when they vary in difficulty."* CHANGELOG 2.18.0 reversal entry pairs with the SKILL.md change so the historical 2.12.0 "ETAs go mandatory" line stays accurate-as-of-its-date. `leojkwan/ai/.claude/settings.json` newly tracked for /auto §G compliance (was missing — fleet sweep gap).
- [2026-04-26] **ETA backfill pass — fleet audit gap closed.** Added `[ETA: Xh]` to all 5 untagged Phase 4 polish tasks per fleet ETA-coverage audit (T4a memory 1h, T4b ledger 1h, T4c launchd 2h, T4d decision-diff 2h, T4e components-shorthand 2h). All 11 pending tasks now carry ETA tags so `vidux-browse` surfaces real AI-hours-remaining (~13h: 5h Phase 2 + 8h Phase 4). Calibration applied: small Python edits 0.5-1h, feature work 2h, cron lane 2h. The 6 already-tagged Phase 2 tasks were not touched.
- [2026-04-26] **LAN-share + dark-mode + Moussey integration shipped.** Five-part landing:
  1. **`server.py` 0.0.0.0 bind fix** (commit `8fb81f7`, upstream-equivalent ~`f3382c2`) — `VIDUX_BROWSER_HOST` env var now honored with safe localhost fallback; LaunchAgent sets it to `0.0.0.0`. Previously hardcoded localhost-only bind broke iPhone access on M4 Pro (Studio worked because someone there had patched it locally). Both Macs now converge from clean clone.
  2. **Artifacts dark-mode patch** — all 12 `~/Development/vidux/browser/artifacts/snowcubes-*.html` got `prefers-color-scheme: dark` block (cream→#1d1a14 warm dark, ink→#f1ebd9 warm light) so they don't glare against the dark sidebar in OS dark mode. Same warm palette inverted brightness — preserves brand voice. Patched 12 artifacts in one shell pass.
  3. **Fleet ETA backfill** — 8 background agents tagged ~145h of fleet AI-hours across 10 plans. The vidux-browser plan itself was tagged at 13h via commit `ce64cbc`. Cumulative fleet view now meaningful.
  4. **Snowcubes hub artifact + 9 per-plan Nicole-friendly cards** live at `vidux/browser/artifacts/snowcubes-*.html`, served via `/api/file?path=...` deep-link.
  5. **Moussey integration** — Moussey at `:4321/snowcubes` (mux-snowcubes-tile commit `cc03589`) and `:4321/vidux` both 307-redirect to vidux-browse on `:7191` using request-header host derivation, so `.local` and IP both work. Moussey homepage tile shipped.
  Decision Log entry added: `[DIRECTION] [2026-04-26] vidux-browse must bind 0.0.0.0 by default for LAN-share; honor VIDUX_BROWSER_HOST env var with safe localhost fallback. Reason: artifact-share-with-Nicole-on-LAN is now first-class use case via Moussey integration.` Phase 5 added with 5 [completed] (T5a–T5e) + 6 [pending] (VB-NEW-1 through VB-NEW-6, ~7h). Updated fleet ETA: 13h → ~20h pending across 17 open tasks.
- [2026-04-29] **Named comments/annotations shipped in branch `codex/vidux-lan-comments-20260429`.** Added `/api/comments` GET/POST, separate JSONL app-data store, LAN same-origin JSON guard, comment UI with saved name field, and browser-server tests for plan/artifact comments plus cross-origin/simple-post rejects. Source files remain read-only: no `PLAN.md`, `INBOX.md`, repo, or artifact mutation from comments.
- [2026-04-29] Started VB-COM-2 after Leo asked for command-key annotation mode that captures exact comment placement. Plan: extend comment payloads with safe anchor metadata, add a keyboard/toolbar capture mode in vidux-browse, render anchored comments with target context, and add server + UI smoke coverage. Next: implement and verify on a branch worktree. Blocker: none.
- [2026-04-29] Completed VB-COM-2 on branch `codex/vidux-anchored-comments-20260429`. Added sanitized anchor metadata to `/api/comments`, decorated rendered markdown/artifact nodes as selectable annotation targets, added `Annotate`/`Cmd-Ctrl-Shift-C` capture mode, stored the selected anchor with comments, and made the `Target` pill jump/highlight the captured element. Verification: `python3 -m py_compile browser/server.py`, `node --check browser/static/app.js`, `python3 -m unittest tests.test_browser_server`, `npm test` (174 tests), `PATH=/Users/leokwan/Development/vidux/node_modules/.bin:$PATH npm run docs:build`, and live in-app-browser smoke on `127.0.0.1:7192` with anchor payload `selector=[data-vidux-anchor="a2"]`, `label=Purpose`, `tag=h2`, `index=2`. Next: merge to main and restart Studio vidux-browse. Blocker: none.
- [2026-04-29] Started VB-DOC-1 after Leo classified precise vidux-browse annotations as P0 for seamless computer setup. Scope is public-core docs only: README, `/vidux` browser section, docs/reference/browser, docs/reference/index, and this plan. Moussey/Snowcubes/private-facing guidance remains outside core vidux. Next: verify docs build and open PR. Blocker: none.
