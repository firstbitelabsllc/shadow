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
- [Source: browser diff comment 2026-05-03] Annotate is no longer a small top-bar button; Leo called it "a large overall feature per page" that probably belongs as a floating action / page-level mode.
- [Source: browser diff comment 2026-05-03] Read-aloud is also too large for the top bar and now lives in a sticky footer player. The annotation surface must coexist with that footer instead of competing for header chrome.
- [Source: Leo request 2026-05-03] "two huge projects ... please plan yourself" after reviewing read-aloud and Annotate. Interpretation: keep reader transcript/player work in `projects/voxtral-reader-addon/PLAN.md`; plan annotation/app-action work here as vidux-browser core.

## Constraints

**ALWAYS:**
- Read-only against plan source — viewer never edits PLAN.md / PROGRESS.md / etc.
- Localhost by default (`127.0.0.1:7191`); LAN bind only when launcher/LaunchAgent explicitly sets `VIDUX_BROWSER_HOST=0.0.0.0`
- Python stdlib only for v1 (no Flask, no FastAPI, no Node) — matches Leo's "simple css html" ask
- Plain HTML + CSS + vanilla JS — no React/Vue/Svelte/Tailwind/etc.
- One stable URL Leo can bookmark
- Survives PLAN.md schema drift (renders any markdown gracefully even if structure varies)
- Comments are separate app data (`~/.vidux-browser/comments.jsonl` by default), never mutations to plan or artifact source files
- Top bar stays status/navigation chrome. Large page-level features (read-aloud, annotate, future app modes) get dedicated footer/FAB/drawer surfaces with explicit z-index and mobile coexistence rules.
- If React/Storybook enters vidux-browse, it starts as an isolated visual-state harness or mounted component island; no wholesale rewrite until the vanilla app proves the boundaries and the maintenance win is explicit.

**NEVER:**
- New repo (extend vidux core)
- AWS/GCP/Firebase / paid SaaS
- Editing plan files from the browser (read-only contract is load-bearing)
- Treat LAN comments as plan writes, task claims, repo writes, or inbox mutation
- Heavy framework (Leo asked for simple)
- Re-hide Annotate inside the comments card or top bar. It is a page action with its own mode, composer, and review/readback surface.

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
Phase 1: MVP
Phase 2: v1 — plan-viewer enrichment
- [pending] T2a Discovery upgrades — handle missing files gracefully, surface broken markdown [ETA: 0.5h]
- [pending] T2c Session panel — read latest JSONL per repo from `~/.claude/projects/`, parse summary [ETA: 1.5h]
- [completed] T2d Auto-poll every 5s — refresh plan/task metadata, artifact metadata/content, and current-view comments without losing the selected plan/artifact or active tab. [Evidence: user request 2026-05-24 for lightweight auto-refresh covering comment threads, plan task stats, and artifact changes] [Done: 2026-05-24; verified by JS syntax check, default test gate, and Playwright polling smoke] [ETA: 0.25h]
- [completed] T2h Evidence directory viewer — `evidence/YYYY-MM-DD-<slug>.md` rendered as a chronological timeline tab per plan, with graceful empty/odd-name handling and comments/annotations targeting the selected evidence file. [Done: 2026-05-24; verified `npm test`, `git diff --check`, and Playwright smoke on `127.0.0.1:7391` against `projects/voxtral-reader-addon/PLAN.md` showing 29 evidence files, markdown render, and evidence-targeted annotation comment] [ETA: 0.75h]
- [completed] T2i Decision Log promoted to first-class — Doctrine: agents MUST NOT contradict logged directions; surface this prominently, not buried inside PLAN.md. [Done: 2026-05-24; verified by parser tests for missing/messy sections, static pane contract, browser-server suite, JS unit smoke, and Playwright proof on `127.0.0.1:7294/?plan=vidux%2Fprojects%2Fvidux-browser%2FPLAN.md&tab=Decision%20Log`] [ETA: 0.5h]
- [pending] T2k Cross-plan dashboard — "all in_progress across the fleet", "all blocked", "all open ASK-LEO", "all INBOX entries" [ETA: 1.5h]

Phase 2 — completion bar elevation (added 2026-04-25 per Leo "make a pretty bar … completion and a moving target key to vidux plans")
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
- [completed] VB-COM-3 Root annotation control + comment UX pass — move `Annotate` out of the comments card into the root top bar, improve count/empty/submit/target affordances, and ignore annotation/filter shortcuts while typing in inputs, textareas, selects, or contenteditable fields. [Done: 2026-04-29] [Evidence: Leo 2026-04-29: "move it to root vidux browser" and "if we are typing in a text box then dont' respect the c command"]
- [completed] VB-COM-4 App-wide annotation targets — make the root Annotate mode decorate and capture the whole vidux-browse shell (header, sidebar rows, pane header, tabs, comments, and rendered plan/artifact content) without requiring hardcoded artifact HTML hooks. [Done: 2026-04-29; verified `node --check browser/static/app.js`, `python3 -m unittest tests.test_browser_server`, `npm test`, `npm run docs:build`, and Playwright smoke on `127.0.0.1:7193` covering header, sidebar row, pane header, generic artifact span, artifact button, and textarea shortcut immunity] [Evidence: Leo 2026-04-29: "everything in browser should be annotatable with commments dont bake it into every html hardcoded it should be in the header as a core feature"]
- [completed] VB-COM-5 Popover annotation composer — replace the always-visible comment form with an inline popover composer that opens at the selected annotation target, while keeping the comments list/readback separate and lightweight. [Done: 2026-04-29; verified `node --check browser/static/app.js`, `python3 -m unittest tests.test_browser_server`, `npm test`, `npm run docs:build`, `git diff --check`, and Playwright smoke on `127.0.0.1:7193` covering no baked form, target popover, submit, comment list refresh, Target jump, and shortcut guard inside the popover textarea] [Evidence: Leo 2026-04-29: "please work on a popover annotation instead of having a baked comment box up top this is a p0 feature"]

Phase 6: Project B — annotation workbench + app-action layer (added 2026-05-03)
- [pending] VB-ACT-1 App-action zoning contract — formalize the vidux-browse chrome map: header = status/filter/refresh only, bottom footer = read-aloud player, floating action layer = page modes like Annotate, right/inline drawer = mode detail. Add CSS variables / z-index constants and static tests so reader footer, annotation FAB, popovers, comments, and mobile layout do not collide. [Evidence: browser diff comments 2026-05-03; PR #87 V17.1 footer/FAB proof] [ETA: 0.75h]
- [pending] VB-COM-6 Annotation FAB state machine — graduate the current floating Annotate button from relocated top-bar control to real page-mode entry. States: unavailable, idle, capture-active, target-picked, composer-open, saving, saved, error. Keep `Cmd/Ctrl+Shift+C`, Escape, outside-click, and textarea shortcut immunity. [Evidence: browser diff comment 2026-05-03; VB-COM-2/VB-COM-5 shipped behavior] [Depends: VB-ACT-1] [ETA: 1.5h]
- [pending] VB-COM-7 Annotation drawer / review rail — add a compact page-level readback surface for comments independent of the inline composer. Must support current-view comments, target jump, empty state, comment count, and future filters without editing PLAN.md/artifact source. [Evidence: Leo 2026-05-03 "large overall feature per page"; named comments append-only contract] [Depends: VB-COM-6] [ETA: 2h]
- [pending] VB-COM-8 Anchor markers and target map — render unobtrusive markers/counts for existing anchored comments on the current view, with hover/click-to-jump behavior and a way to hide markers while reading. Must work for plan markdown, generic artifact HTML, sidebar rows, and browser chrome targets already covered by VB-COM-4. [Evidence: VB-COM-4 app-wide target coverage; browser diff comment 2026-05-03] [Depends: VB-COM-7] [ETA: 2h]
- [pending] VB-COM-9 Thread lifecycle event model investigation — decide whether reply/resolve belongs in v1. If yes, preserve append-only storage by writing lifecycle events (`reply`, `resolve`, `reopen`) instead of mutating prior comments. Investigation must map JSONL schema, UI affordances, server validation, and migration behavior before code. [Evidence: comments are app data and append-only; annotation is becoming an official workbench] [Depends: VB-COM-7] [ETA: 1h]
- [pending] VB-COM-10 Annotation visual-state harness / Storybook spike — capture annotation states before a framework commitment: FAB idle/active/error, composer beside target, drawer open/closed, markers visible/hidden, mobile viewport, and coexistence with read-aloud footer. Outcome may be a lightweight static fixture or a React+Storybook island proposal; do not rewrite vidux-browse wholesale. [Evidence: Leo 2026-05-03 "we may need to start introducing react storybook this is getting official"] [Depends: VB-ACT-1] [ETA: 2h]
- [pending] VB-COM-11 End-to-end annotation proof gate — Playwright/browser proof for the official annotation workbench: activate FAB, pick target, submit comment, see marker/drawer update, jump back to target, verify textarea shortcut immunity, verify read-aloud footer coexistence, and capture desktop + mobile screenshots. [Evidence: vidux Principle 5 visual proof; browser diff comments 2026-05-03] [Depends: VB-COM-8] [ETA: 1h]

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
- [DIRECTION] [2026-04-29] Annotation composition should be contextual, not a persistent top-of-view form. Reason: comments are annotations on specific browser surfaces; the composer belongs next to the selected target.
- [DIRECTION] [2026-05-03 two-project split] Annotate is now **Project B: annotation workbench + app-action layer** in this plan. The reader footer/transcript engine remains in `projects/voxtral-reader-addon/PLAN.md`. Shared browser chrome decisions land here because vidux-browser owns header/footer/FAB/drawer zoning.
- [DIRECTION] [2026-05-03 app chrome] Topbar is not a feature dock. After PR #87 V17.1, header controls should stay status/navigation-level; large modes get footer/FAB/drawer surfaces with tests preventing regression.

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
- [2026-04-29] Started VB-COM-3 after Leo asked for root-level annotation control and text-box-safe shortcuts. Scope: topbar annotate button, comments card UX cleanup, and keyboard guard for editable targets. Next: verify JS/tests/docs and live-browser smoke. Blocker: none.
- [2026-04-29] Completed VB-COM-4 on branch `codex/vidux-appwide-annotation-20260429`. Root Annotate now decorates the shared browser shell plus generic rendered HTML targets, not just markdown/body-specific selectors: header, sidebar rows, pane title/meta/progress/tabs, comments, arbitrary artifact spans/buttons, and plan/artifact content all capture anchor metadata from the same topbar mode. Verification: `node --check browser/static/app.js`, `python3 -m unittest tests.test_browser_server`, `npm test` (174 tests), `PATH=/Users/leokwan/Development/vidux/node_modules/.bin:$PATH npm run docs:build`, `git diff --check`, and Playwright smoke on `127.0.0.1:7193` with screenshot `/tmp/vidux-appwide-annotation-smoke.png`. Next: merge and restart live `:7191`. Blocker: none.
- [2026-04-29] Completed VB-COM-5 on branch `codex/vidux-popover-annotations-20260429`. Removed the persistent comments form from the comments panel and replaced it with a fixed-position popover composer that opens beside the selected annotation target. The popover carries name/body fields, posts the same append-only `/api/comments` payload, refreshes the comment list, closes on submit/cancel/outside click/Esc, and keeps annotation shortcuts ignored while typing. Verification: `node --check browser/static/app.js`, `python3 -m unittest tests.test_browser_server`, `npm test` (174 tests), `PATH=/Users/leokwan/Development/vidux/node_modules/.bin:$PATH npm run docs:build`, `git diff --check`, and Playwright smoke on `127.0.0.1:7193` with screenshot `/tmp/vidux-popover-annotation-smoke.png`. Next: merge and restart live `:7191`. Blocker: none.
- [2026-05-03] Planning cycle: Leo flagged Annotate as another huge page-level feature after PR #87 moved it into a FAB. Added Phase 6 Project B: app-action zoning, annotation FAB state machine, review drawer, anchor markers, lifecycle investigation, visual-state harness / Storybook spike, and e2e proof gate. No code shipped and no commit opened because `/vidux` prohibits plan-only PRs; these notes ride with the next code-bearing annotation/browser PR.
- [2026-05-24] Completed T2d auto-refresh pass. `vidux-browse` now polls plan/artifact metadata every 5s, refreshes current-view comments, preserves the selected plan/artifact plus active tab, restores scroll on auto-poll renders, and defers pane re-render while annotation capture/popover state is active. Added Playwright polling coverage that mutates mocked comments, task stats, and artifact HTML without a manual reload. Gate: `node --check browser/static/app.js` PASS; `npm run test:js` PASS (7/7); `npx playwright test browser/tests/e2e/smoke.spec.ts --project=desktop-chromium` PASS (10/10); `npm test` PASS (204 Python tests + 7 JS tests). Note: concurrent unrelated browser edits for evidence/decision-log surfaces were present and left intact.
- [2026-05-24] Completed T2h evidence timeline pass. `browser/server.py` now discovers each plan's `evidence/*.md` files as dated metadata, preserving odd markdown filenames after canonical dated receipts and returning `[]` when the directory is missing. `browser/static/app.js` adds an `EVD:<path>` evidence strip under the plan tabs, renders selected evidence through the existing markdown reader, updates URL tab state, and points the existing comments/annotation panel at the evidence file path. Tests cover missing evidence dirs, odd/non-md/nested evidence entries, and comments against evidence markdown. Gate: `python3 -m py_compile browser/server.py`, `node --check browser/static/app.js`, `python3 -m unittest tests.test_browser_server`, `npm test` (204 tests), `git diff --check`, and Playwright smoke on `127.0.0.1:7391` with screenshot `/tmp/vidux-evidence-timeline-smoke.png`.
- [2026-05-24] Completed T2i Decision Log pane pass. `/api/plans` now includes read-only `decision_log` metadata parsed from `PLAN.md`: missing sections return an empty state, messy `##` through `######` headings are tolerated, bullet/numbered entries and wrapped continuation lines are preserved, and recent direction-tagged entries are lifted into a prominent Recent Directions block. `browser/static/app.js` adds a first-class `Decision Log` tab beside `PLAN.md` and renders the full list below without writing to source files. Gate: `python3 -m py_compile browser/server.py`, `node --check browser/static/app.js`, `python3 -m unittest tests.test_browser_server` (40 tests), `npm run test:js` (7 tests), `git diff --check`, and Playwright proof on `127.0.0.1:7294` with screenshot `.playwright-cli/page-2026-05-24T05-39-02-817Z.png`.

Phase 6: Left-panel rework (added 2026-05-01 per Leo "the most annoying fucking thing" + "redo the whole left panel")
- [completed] VB-LP-1 localStorage state shim (`vidux:ui-state` key — collapsed Set + recents array, RECENTS_MAX=5, JSON-encoded). saveUiState debounce-implicit (called only on toggle/track). [Done: 2026-05-01]
- [completed] VB-LP-2 "Recently viewed" section at top of sidebar — drawn from `uiState.recents`, shows up to 5 items that still resolve in current state, mixes plans + artifacts, dedup-on-track. trackRecent() called from selectPlan/selectArtifact. [Done: 2026-05-01]
- [completed] VB-LP-3 "← Parent: <name>" backlink in pane header for child plans — uses findParentPlan() to walk state.plans for any plan that lists this one in its children array; navigates in-app via selectPlan, href present for cmd-click open-in-new-tab. [Done: 2026-05-01]
- [completed] VB-LP-4 Sort change: alphabetical-by-repo replaced with mtime descending. Repos sort by their freshest plan's mtime; within each repo, plans sort by mtime descending. The prior alphabetical default surfaced cold long-tail repos above active ones — the chronic friction Leo flagged. [Done: 2026-05-01]
- [completed] VB-LP-5 Collapsible group headers — recents, artifacts, and each repo. Click h2 → toggleCollapsed(key) → renderSidebar(). State persists across reloads via localStorage. Caret visual (`▾` open, `▸` collapsed). [Done: 2026-05-01]


---

## PSA — 2026-05-26 — Fleet UX/UI lane split codified

- **Claude Code owns ALL UX/UI work fleet-wide.** Codex agents must stay on backend / logic / lanes / workers / API.
- **Disambiguator:** "is this rendered to a human?" → Claude. "Does this read/write data, run a CLI, or expose an HTTP endpoint?" → Codex.
- **Canonical visualization layer:** [Litty](file:///Users/leokwan/Development/litty) at `http://localhost:4400` (the operator cockpit). Federates moussey's `/api/coding/*` APIs. Replaces the 12,062-line `moussey/app/coding/page.tsx` rot.
- **15 routes shipped 2026-05-26:** `/`, `/lanes`, `/lanes/[laneId]`, `/runs`, `/runs/[runId]`, `/runs/[runId]/patch`, `/runs/[runId]/stream`, `/workers`, `/workers/[workerId]`, `/handoffs`, `/handoffs/[handoffId]`, `/capabilities`, `/api/health`, `/api/proxy/coding/[...path]`, plus sibling-shipped `/api/operating-readout`, `/api/proofs`, `/api/repo-catalog`.
- **Plan:** `~/Development/vidux/projects/litty/PLAN.md` (canonical). Research at `~/Development/vidux/projects/litty/research/` (~30k words, 11 deep-research agents).
- **Codex agents seeing UX/UI work in this project's queue:** redirect to backend tasks (federation contracts, FirstBite lanes, MCP, repo-backed catalog snapshots, the moussey-side PRs documented as Phase 3.5 unblockers).
- **Reference:** `/pilot-leo § Agent lane splits — codify in the project, not here (2026-05-24)` (the disambiguator pattern).
