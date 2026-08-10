# Browser

`shadow browse` is a read-only loopback projection of this computer's board.
It exposes three routes:

- `GET /api/health` — product, version, and a path-safe scan-root identity.
- `GET /api/plans` — total board cards for registered entity plans, with
  path-safe locators and current milestone/checkpoint state.
- `GET /api/gallery` — checked-in representative plan texts rendered through
  that same projection.

The browser never writes plans or choices. The computer board and each
entity's committed `PLAN.md` remain authority. It never receives a credential,
prompt, transcript, provider payload, or absolute private path.
