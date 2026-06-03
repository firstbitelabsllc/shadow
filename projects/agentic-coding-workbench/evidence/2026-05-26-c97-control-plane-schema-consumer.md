# C97 Control-Plane Schema And Consumer Smoke

Date: 2026-05-26

## Decision

Leo redirected product UI ownership out of Moussey and into the new Litty-CI / litty-build direction. Moussey remains the LAN/API/data hub. This slice stopped Moussey UI work and made the local-CI producer contract durable enough for a standalone app to consume without scraping `/coding`.

## Changed

- Added saved JSON Schema: `/Users/leokwan/Development/moussey/fixtures/coding/firstbite-local-ci-control-plane-v1.schema.json`.
- Added saved fixture: `/Users/leokwan/Development/moussey/fixtures/coding/firstbite-local-ci-control-plane-v1.fixture.json`.
- Added runtime schema helpers and fixture validation tests: `/Users/leokwan/Development/moussey/lib/local-ci-control-plane-schema.ts`.
- Added read-only schema route: `GET /api/coding/control-plane/schema`.
- Added live consumer smoke: `/Users/leokwan/Development/moussey/scripts/verify-control-plane-consumer.mjs`.
- Added npm script: `npm run test:coding:control-plane-consumer`.

## Live Contract Proof

`GET http://127.0.0.1:4321/api/coding/control-plane/schema` returned:

```json
{
  "id": "https://firstbite.local/schemas/firstbite-local-ci-control-plane-v1.json",
  "title": "FirstBite local CI control-plane snapshot",
  "required": 15,
  "boundaries": [
    "local-no-spend",
    "local-browser",
    "local-simulator",
    "external-live",
    "model-spend",
    "cloud-spend",
    "unknown"
  ]
}
```

`npm run test:coding:control-plane-consumer` returned:

```json
{
  "ok": true,
  "url": "http://127.0.0.1:4321/api/coding/control-plane",
  "schema": "firstbite-local-ci-control-plane-v1",
  "lanes": 38,
  "pipelines": 5,
  "blockers": 9,
  "latestRun": "verify-moussey-cockpit-port-drift-origin-main-pr20-20260526T0640",
  "boundaries": {
    "local-no-spend": 7,
    "local-browser": 13,
    "local-simulator": 16,
    "external-live": 2,
    "model-spend": 0,
    "cloud-spend": 0,
    "unknown": 0
  }
}
```

The consumer smoke now fails if the live route returns a structurally valid but empty catalog. That caught a warm-up race during verification, then passed after `/api/coding/local-ci` had loaded the repo manifest catalog.

## Verification

- `node --test --import tsx lib/local-ci-control-plane-schema.test.ts app/api/coding/control-plane/schema/route.test.ts`: 6/6 pass.
- `npm run test:coding:contract`: 91/91 pass.
- `npm run test:brain-dispatcher`: 234/234 pass.
- `npx tsc --noEmit --pretty false`: pass.
- `git diff --check` scoped to C97 files: pass.
- `scripts/moussey-server.sh --build && scripts/moussey-server.sh --restart`: pass, with the known Turbopack NFT warning from `app/api/coding/local-ci/artifact/route.ts`.
- `/api/health`: `ok=true`.
- FirstBite local CI run `c97-control-plane-schema-consumer-moussey-unit-20260526`: pass.

FirstBite report:

```text
/Users/leokwan/.agent-ledger/firstbite-local-ci-mcp/c97-control-plane-schema-consumer-moussey-unit-20260526/report.json
```

Important caveat: this FirstBite proof intentionally ran against the primary Moussey checkout (`worktree=false`, `source_ref=HEAD`) so it covered the current uncommitted schema/script changes. It is green local proof, not fresh-main portability proof. The report recorded `dirty_count=178`, `sync_status=dirty`, and `behind_origin_main=42`.

## Remaining

- The standalone Litty-CI repo/app does not exist durably on disk yet. Current product UI ownership should resume there, not in Moussey.
- Litty-CI should consume `/api/coding/control-plane` as the primary feed and `/api/coding/local-ci` only for deeper drill-down/debug surfaces.
- Litty-CI should treat empty-catalog payloads as degraded/warming or blocked, not green.
- Next backend slice should add an OpenAPI/client package or generated TypeScript client only after the new app path is settled.
