# Browser UI

Vidux ships a local browser surface for inspecting plans across `DEV_ROOT`, scanning the cross-plan fleet queue, reading sibling docs, adding named or anchored comments to the current view, and dropping bounded local notes into a plan's `INBOX.md`.

## What ships

- `bin/vidux-browse` starts the local server and, by default, opens the UI in a browser.
- `browser/server.py` serves the read-mostly HTTP API and static frontend.
- `browser/static/` contains the frontend assets.
- `browser/artifacts/` stores ad-hoc HTML artifacts that the UI can list and open.
- `${VIDUX_BROWSER_COMMENTS_FILE:-~/.vidux-browser/comments.jsonl}` stores named comments and optional anchor metadata as append-only app data.

## Launching it

```bash
bin/vidux-browse
bin/vidux-browse --no-open
bin/vidux-browse --foreground
bin/vidux-browse --port 7291 --root ~/Development/vidux --no-open
```

Source-grounded defaults from the launcher and server:

- URL: `http://127.0.0.1:7191`
- Bind host: `VIDUX_BROWSER_HOST` defaults to `127.0.0.1`
- Port: `VIDUX_BROWSER_PORT` defaults to `7191`
- Browser-open host: `VIDUX_BROWSER_OPEN_HOST` defaults to `127.0.0.1`
- Repo root for the launcher: `VIDUX_ROOT` defaults to `~/Development/vidux`
- Scan root for the server: `VIDUX_DEV_ROOT` defaults to `~/Development`
- Activity ledger source: `VIDUX_LEDGER_FILE` defaults to `~/.agent-ledger/activity.jsonl`
- Ledger tab caps: `VIDUX_LEDGER_ITEM_LIMIT` defaults to `20`; `VIDUX_LEDGER_SCAN_LIMIT` defaults to `5000`

In background mode the launcher writes a PID file and log under `${TMPDIR:-/tmp}` and waits for `GET /api/health` before declaring success. If something is already listening on the target port, the launcher reuses it only when that health payload matches the requested `repo_root`, `dev_root`, `port`, and current `browser/server.py` file mtime fingerprint.

The launcher accepts `--port`, `--host`, `--root`/`--dev-root`, `--open-host`,
and `--comments-path`; unknown flags exit 2 instead of being silently ignored.

## HTTP surface

The server is stdlib-only and exposes these routes:

- `GET /api/health` returns `ok`, `dev_root`, `repo_root`, `port`, `server_path`, `server_mtime_ns`, and `artifacts_dir`; `bin/vidux-browse` uses those fields to avoid opening a stale, older-code, or foreign listener on the same port.
- `GET /api/vidux/truth` returns cached read-only config, runtime-doctor, and signpost status for the browser chrome. Cold calls return a warming payload and refresh the expensive truth bundle in the background so monitor probes do not block on runtime doctor.
- `GET /api/vidux/truth?refresh=sync` forces the synchronous config/runtime-doctor/signpost proof path for manual checks and tests.
- The truth payload includes `runtime_doctor.system_memory` as a compact copy of the runtime doctor's `system_memory_pressure` check: `memory_pressure_free_pct` and `memory_pct_source` come from `memory_pressure -Q`, while `vm_free_mb`, `vm_speculative_mb`, and `vm_pages_source` come from `vm_stat`.
- The truth payload includes `signposts.latest_run`, a compact call-stack summary from `vidux signpost trace --limit 12 --json`, so the browser can show the latest Codex/Claude/Cursor runtime chain instead of only total event counts.
- `GET /receipts` opens the local receipt corpus lab.
- `GET /api/plans` returns discovered plans plus plan metadata, a server-calculated `summary` for fleet counts/task completion/remaining ETA, and a bounded `dashboard` object for `in_progress` tasks, `blocked` tasks, open `ASK-LEO.md` entries, and open `INBOX.md` entries.
- `GET /api/ledger?path=<PLAN.md>` returns bounded, newest-first publish/checkpoint ledger rows for that plan, falling back to recent same-repo rows when plan-specific proof is absent.
- `GET /api/artifacts` returns the HTML artifact shelf under `browser/artifacts/`.
- `GET /api/file?path=...` returns an allowed markdown file or HTML artifact.
- `GET /api/comments?path=...` returns named comments attached to an allowed markdown file or HTML artifact.
- `GET /api/receipts/list` returns the local receipt corpus rows.
- `GET /api/receipts/<id>/image` returns a stored receipt image when the row is not private.
- `POST /api/artifact` writes a bounded HTML artifact (`slug` + `html` JSON payload).
- `POST /api/comments` appends a bounded named or anchored comment to the separate comments store.
- `POST /api/local-plan-note` appends a bounded local note to a plan directory's `INBOX.md`.
- `POST /api/upload-ref-audio` saves a bounded temporary read-aloud reference-audio sample for local voice cloning.
- `POST /api/receipts/upload` writes a bounded receipt-corpus row from base64 JPEG/PNG input.
- `POST /api/receipts/<id>/tag` patches receipt tags, known issues, or Leo notes.
- `POST /api/receipts/<id>/ocr` runs configured OCR for a stored receipt image.
- `POST /api/receipts/<id>/expected` validates and stores a contract-shaped expected receipt payload.
- `POST /api/receipts/<id>/delete` removes a receipt-corpus row.
- `POST /api/receipts/<id>/analyze` runs the configured receipt-analysis path for one row.

## Read/write safety model

The server is intentionally narrow:

- Reads are limited to `DEV_ROOT` and an allowlist of plan-adjacent files: `PLAN.md`, `PROGRESS.md`, `INBOX.md`, `ASK-LEO.md`, `DOCTRINE.md`, and `README.md`.
- Markdown files under `investigations/` and `evidence/` are also allowed.
- HTML reads are limited to files inside `browser/artifacts/`.
- `node_modules` paths are rejected even if the filename matches the allowlist.
- Artifact writes and local plan-note writes are loopback-only, require `Content-Type: application/json`, and reject cross-origin browser posts.
- Receipt writes, receipt OCR/analyze mutations, and read-aloud reference-audio upload are loopback-only JSON writes with explicit size caps.
- Comment writes may come from LAN viewers of the vidux-browse UI, but still require JSON and a same-origin `Origin` or `Referer` header.
- Comments never edit plan files, `INBOX.md`, or artifact HTML. They append JSONL records to the comments store; optional anchors point back to rendered elements only.
- The local truth band is read-only: the monitor-safe `GET /api/vidux/truth` route returns cached or warming state quickly, then refreshes `vidux config check --json`, `scripts/vidux-doctor.sh --json`, and `vidux signpost summary --json` in the background. Use `GET /api/vidux/truth?refresh=sync` when you need the synchronous proof path. Neither route runs `vidux doctor`, neither route runs runtime doctor `--fix`, and warning-only runtime state stays a warning instead of being treated as proof of a clean fleet.
- When system-memory truth is available, the Local truth band renders the runtime warning/blocker summary alongside the `memory_pressure` free percentage; the element title preserves the `memory_pressure -Q` and `vm_stat` source split.
- When a latest signpost run is available, the Local truth band renders the runtime chain, for example `codex > claude > cursor > codex`, and its title marks whether the expected lifecycle is complete.
- The `Ledger` tab is read-only. It scans the configured activity JSONL tail, ignores noisy non-publish rows, matches plan rows by `plan_path`, `files`, or `files_claimed`, and will not append, edit, or delete ledger data.

## Artifact styling

Artifacts are user-generated HTML, but shared visual scaffolding lives in `browser/static/artifact-base.css`. Put this link after the artifact's local `<style>` block:

```html
<link rel="stylesheet" href="../static/artifact-base.css" data-vidux-artifact-base>
```

The relative `../static/` path works in the vidux-browse iframe and when someone opens a local artifact file directly from `browser/artifacts/`. Keep OS dark-mode tokens in the shared CSS instead of copying a per-artifact `prefers-color-scheme: dark` block.

## Plan-note behavior

`POST /api/local-plan-note` is the only plan-writing endpoint. It does not edit `PLAN.md` directly.

Instead, it appends a timestamped entry to the target plan directory's `INBOX.md`:

- Creates `INBOX.md` if it does not exist.
- Inserts new notes under `## Open`.
- Preserves any existing `## Processed` section.
- Records `Source` and optional `Agent` metadata.

This behavior is covered by `tests/test_browser_server.py`.

## Comment behavior

`POST /api/comments` is an annotation endpoint, not a plan-writing endpoint. It accepts `target_path`, `author`, `body`, and optional `anchor` metadata, then appends a JSONL record to `${VIDUX_BROWSER_COMMENTS_FILE:-~/.vidux-browser/comments.jsonl}`.

- Targets must resolve through the same allowlist as `GET /api/file`.
- Plan-tab comments attach to the specific markdown file being viewed.
- Artifact comments attach to the specific artifact HTML file.
- The UI remembers the commenter name in browser `localStorage`.
- Cross-machine LAN viewers can comment when they are using the vidux-browse origin.
- For precise placement, use the top-bar `Annotate` control or `Cmd/Ctrl+Shift+C`, then click the browser surface the comment targets. Capture decorates the shared browser chrome plus generic rendered HTML elements, so artifact authors do not need to bake annotation hooks into each file. The composer opens as a target-positioned popover instead of a persistent form in the comments panel. Annotation/filter shortcuts are ignored while typing in inputs, textareas, selects, or contenteditable fields.
- Anchors store sanitized selector, label, excerpt, tag, kind, and index metadata. They are best-effort display pointers; the source markdown or artifact remains unchanged.
- The rendered `Target` pill scrolls to and highlights the captured element when it is still present.

## Discovery model

Plan discovery is filesystem-based. The server scans `DEV_ROOT` with these layout globs:

- `*/ai/plans/*/PLAN.md`
- `*/vidux/*/PLAN.md`
- `*/projects/*/PLAN.md`
- `*/PLAN.md`

Each discovered plan reports task counts, ETA totals for active tasks, sibling-file availability, and any linked or auto-discovered investigations. The topbar uses `/api/plans.summary` so the fleet-wide remaining-hours readout is computed server-side from the same task parser as the plan rows. The sidebar keeps persisted local hot/tasks/ETA filter chips and a sort menu for `mtime`, remaining `ETA`, and freshness status, with filtering still applied before grouping and sorting.

The browser's default pane uses the `/api/plans.dashboard` payload. Server-side extraction keeps each category bounded, includes source path and line metadata, and marks categories with `truncated=true` when the fleet has more rows than the UI payload includes. The ordinary plan list strips the private extractor scratch fields before returning rows to the client.

The per-plan `Ledger` tab loads lazily through `/api/ledger` after a plan is selected. This keeps `/api/plans` small while still exposing proof, handoff status, resume hints, file-claim counts, ledger line numbers, and same-repo fallback rows in the cockpit.

## Related references

- Read [Scripts](/reference/scripts) for the CLI and maintenance helpers that sit alongside the browser.
- Read [Configuration](/reference/config) if you need the repo-level defaults that other vidux tooling consumes.
