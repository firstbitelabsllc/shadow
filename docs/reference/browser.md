# Browser UI

Vidux ships a local browser surface for inspecting plans across `DEV_ROOT`, reading sibling docs, adding named or anchored comments to the current view, and dropping bounded local notes into a plan's `INBOX.md`.

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
```

Source-grounded defaults from the launcher and server:

- URL: `http://127.0.0.1:7191`
- Bind host: `VIDUX_BROWSER_HOST` defaults to `127.0.0.1`
- Port: `VIDUX_BROWSER_PORT` defaults to `7191`
- Browser-open host: `VIDUX_BROWSER_OPEN_HOST` defaults to `127.0.0.1`
- Repo root for the launcher: `VIDUX_ROOT` defaults to `~/Development/vidux`
- Scan root for the server: `VIDUX_DEV_ROOT` defaults to `~/Development`

In background mode the launcher writes a PID file and log under `${TMPDIR:-/tmp}` and waits for `GET /api/health` before declaring success.

## HTTP surface

The server is stdlib-only and exposes these routes:

- `GET /api/health` returns `ok`, `dev_root`, `port`, and `artifacts_dir`.
- `GET /api/plans` returns discovered plans plus plan metadata.
- `GET /api/artifacts` returns the HTML artifact shelf under `browser/artifacts/`.
- `GET /api/file?path=...` returns an allowed markdown file or HTML artifact.
- `GET /api/comments?path=...` returns named comments attached to an allowed markdown file or HTML artifact.
- `POST /api/artifact` writes a bounded HTML artifact (`slug` + `html` JSON payload).
- `POST /api/comments` appends a bounded named or anchored comment to the separate comments store.
- `POST /api/local-plan-note` appends a bounded local note to a plan directory's `INBOX.md`.

## Read/write safety model

The server is intentionally narrow:

- Reads are limited to `DEV_ROOT` and an allowlist of plan-adjacent files: `PLAN.md`, `PROGRESS.md`, `INBOX.md`, `ASK-LEO.md`, `DOCTRINE.md`, and `README.md`.
- Markdown files under `investigations/` and `evidence/` are also allowed.
- HTML reads are limited to files inside `browser/artifacts/`.
- `node_modules` paths are rejected even if the filename matches the allowlist.
- Artifact writes and local plan-note writes are loopback-only, require `Content-Type: application/json`, and reject cross-origin browser posts.
- Comment writes may come from LAN viewers of the vidux-browse UI, but still require JSON and a same-origin `Origin` or `Referer` header.
- Comments never edit plan files, `INBOX.md`, or artifact HTML. They append JSONL records to the comments store; optional anchors point back to rendered elements only.

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
- For precise placement, use the top-bar `Annotate` control or `Cmd/Ctrl+Shift+C`, then click the browser surface the comment targets. Capture decorates the shared browser chrome plus generic rendered HTML elements, so artifact authors do not need to bake annotation hooks into each file. Annotation/filter shortcuts are ignored while typing in inputs, textareas, selects, or contenteditable fields.
- Anchors store sanitized selector, label, excerpt, tag, kind, and index metadata. They are best-effort display pointers; the source markdown or artifact remains unchanged.
- The rendered `Target` pill scrolls to and highlights the captured element when it is still present.

## Discovery model

Plan discovery is filesystem-based. The server scans `DEV_ROOT` with these layout globs:

- `*/ai/plans/*/PLAN.md`
- `*/vidux/*/PLAN.md`
- `*/projects/*/PLAN.md`
- `*/PLAN.md`

Each discovered plan reports task counts, ETA totals for active tasks, sibling-file availability, and any linked or auto-discovered investigations.

## Related references

- Read [Scripts](/reference/scripts) for the CLI and maintenance helpers that sit alongside the browser.
- Read [Configuration](/reference/config) if you need the repo-level defaults that other vidux tooling consumes.
