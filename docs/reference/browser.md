# Browser

`shadow browse` binds only to loopback. It exposes four API routes:

- `GET /api/health` — product, version, and a path-safe scan-root identity.
- `GET /api/plans` — bounded Outcome and briefing projections with relative paths.
- `GET /api/gallery` — the same product identity alongside gallery-fixture plan records, for the `/gallery` static page.
- `POST /api/decision` — one typed choice for the current plan revision.

Choice receipts are atomic and idempotent under the selected Git project's
`.shadow/evidence/` directory. The browser never receives a credential,
prompt, transcript, provider payload, or absolute private path.
