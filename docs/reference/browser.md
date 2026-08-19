# Browser

`shadow browse` binds only to loopback. It exposes four API routes:

- `GET /api/health` — product, version, and a path-safe scan-root identity.
- `GET /api/plans` — bounded Outcome and briefing projections with relative paths.
- `GET /api/gallery` — the same product identity alongside gallery-fixture plan records, for the `/gallery` static page.
- `POST /api/decision` — one typed choice for the current plan revision.

Choice receipts are atomic and idempotent under the selected Git project's
`.shadow/evidence/` directory. The browser never receives a credential,
prompt, transcript, provider payload, or absolute private path.

## Host header allowance

`shadow browse --allow-host NAME` (repeatable) widens only the accepted
`Host` header, for a self-run proxy such as `tailscale serve` in front of the
loopback server. The bind itself never leaves loopback; no flag changes that.
