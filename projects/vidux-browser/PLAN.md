# Vidux Browser

## Purpose

Two surfaces, one tool, for any /vidux user (not Leo-specific):

1. **Plan viewer** — localhost web UI that visualizes every `PLAN.md` + canonical sibling artifacts (`INBOX.md`, `investigations/`, `evidence/`) across the user's repo fleet at a glance. Answers "where am I" without grepping markdown.
2. **Ad-hoc artifact surface** — anytime, anywhere in any session, an agent can drop an HTML artifact into a known directory and it appears in the browser as a top-level "Artifacts" section. Decoupled from any specific plan. The artifact creator is "in chat" — agents POST or write files; the browser surfaces them.

The plan files ARE the source of truth (per `/vidux` discipline). The browser is **read-only against plans**, **append-only against artifacts**.

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
- Read-only — viewer never edits PLAN.md / PROGRESS.md / etc.
- Localhost only (`127.0.0.1:7191`)
- Python stdlib only for v1 (no Flask, no FastAPI, no Node) — matches Leo's "simple css html" ask
- Plain HTML + CSS + vanilla JS — no React/Vue/Svelte/Tailwind/etc.
- One stable URL Leo can bookmark
- Survives PLAN.md schema drift (renders any markdown gracefully even if structure varies)

**NEVER:**
- New repo (extend vidux core)
- AWS/GCP/Firebase / paid SaaS
- Editing plan files from the browser (read-only contract is load-bearing)
- Auth (it's localhost; trust the boundary)
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
- [pending] T2a Discovery upgrades — handle missing files gracefully, surface broken markdown
- [completed] T2b PROGRESS / INBOX / ASK-LEO tabs in pane (shipped early as T1f)
- [pending] T2c Session panel — read latest JSONL per repo from `~/.claude/projects/`, parse summary
- [pending] T2d Auto-poll every 5s
- [completed] T2e Status pill heuristic — "hot" ≤7d, "stale" 7-30d, "cold" >30d (shipped with MVP)
- [completed] T2f Filter across plans (shipped with MVP — searchbox over repo/slug/purpose)
- [pending] T2g Investigations sub-page — when a task carries `[Investigation: investigations/<slug>.md]`, render the investigation file as a linked sub-view with its 6 canonical sections
- [pending] T2h Evidence directory viewer — `evidence/YYYY-MM-DD-<slug>.md` rendered as a chronological timeline tab per plan
- [pending] T2i Decision Log promoted to first-class — Doctrine: agents MUST NOT contradict logged directions; surface this prominently, not buried inside PLAN.md
- [pending] T2j Tasks rendered as structured FSM, not opaque markdown — parse `[pending]/[in_progress]/[completed]/[blocked]` + `[P]/[Depends:]/[Investigation:]` markers into queue UI with status counts in sidebar
- [pending] T2k Cross-plan dashboard — "all in_progress across the fleet", "all blocked", "all open ASK-LEO", "all INBOX entries"

Phase 3: Ad-hoc artifact surface (Leo's "anytime anywhere" ask 2026-04-25)
- [in_progress] T3a `~/Development/vidux/browser/artifacts/` directory — convention dir, drop `.html` files here from any session
- [in_progress] T3b `/api/artifacts` endpoint — scans the artifacts dir, returns list with `{slug, path, mtime, size, title}` (title pulled from `<title>` or first `<h1>`)
- [in_progress] T3c Top-level "Artifacts" section in sidebar — distinct from "Plans", grouped chronologically (newest first), no repo grouping (artifacts are decoupled from any single plan)
- [in_progress] T3d Render `.html` artifacts via direct innerHTML in pane (trust boundary: localhost, Leo's own filesystem, no XSS surface)
- [in_progress] T3e Components CSS shim — `.contact-card`, `.card-grid`, `.lead-row`, `.person-chip` extending the paper-ink palette so dropped artifacts inherit the look
- [in_progress] T3f Dogfood: drop a real `cube-vendors.html` artifact from this very session — render the 7 Tier A vendors as cards, prove the "anytime anywhere" loop works
- [in_progress] T3g `/api/artifact` POST endpoint — agents POST `{slug, html}` from any session; server writes to `artifacts/<slug>.html`; browser auto-surfaces. (Even simpler shape than file-write because no shell access required.)

Phase 4: Polish (formerly Phase 3)
- [pending] T4a Memory viewer
- [pending] T4b Ledger entries
- [pending] T4c launchd plist
- [pending] T4d Decision Log diff highlighter
- [pending] T4e Components inside markdown — `:::person` shorthand syntax that renders as a card without hand-writing HTML

Phase 3: Polish
- [pending] T3a Memory viewer
- [pending] T3b Ledger entries
- [pending] T3c launchd plist
- [pending] T3d Decision Log diff highlighter

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
