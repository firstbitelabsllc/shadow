# Browser

`pilot-puppy browse` binds only to loopback. It exposes three routes:

- `GET /api/health` — product, version, and a path-safe scan-root identity.
- `GET /api/plans` — bounded Outcome and briefing projections with relative paths.
- `POST /api/decision` — one typed choice for the current plan revision.

Choice receipts are atomic and idempotent under the selected Git project's
`.pilot-puppy/evidence/` directory. The browser never receives a credential,
prompt, transcript, provider payload, or absolute private path.
