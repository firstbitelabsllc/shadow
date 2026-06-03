# C94 Selected Object Guts + Moussey UI Pause

Date: 2026-05-26

## Direction

Leo redirected the product UI work out of Moussey. Moussey should remain the LAN/data hub. The clean CI product surface should move into the new Litty-CI / coding-cockpit plan instead of continuing to polish `/coding`.

This slice preserves reusable guts only:

- `buildCiConsolePipelineLaneDetail(...)` turns a manifest/report lane row into selected-object inspector data.
- `buildCiConsolePipelineStageDetail(...)` turns a patch-to-CI stage into the same selected-object shape.
- `/coding` has a small proof implementation so the contract is browser-visible, but further UI product work should move to Litty-CI.

## Verification

- `node --test --import tsx lib/coding-console-model.test.ts`
  - 27/27 passing.
- `npx tsc --noEmit --pretty false`
  - passed.
- `git diff --check -- app/coding/page.tsx lib/coding-console-model.ts lib/coding-console-model.test.ts`
  - passed.
- `scripts/moussey-server.sh --build`
  - passed with the known local-CI artifact NFT warning.
- `scripts/moussey-server.sh --restart`
  - passed; listening on `http://0.0.0.0:4321`.
- `curl -fsS http://127.0.0.1:4321/api/health`
  - passed.
- Browser proof at `http://127.0.0.1:4321/coding?fresh=c94-selected-object-inspector`
  - desktop and mobile: `rowCount=39`, `stageCount=4`, `inspectorCount=1`, no console/page errors, no horizontal overflow.
  - selecting `pipeline-stage-source-ci` changed the inspector to `kind=pipeline-stage`, `stage=source-ci`, `risk=runner-control`.
  - selecting `resplit_currency_api_ui` changed the inspector to `kind=pipeline-lane`, `lane=resplit_currency_api_ui`, `boundary=external/live`, `risk=external`, report button present.
- Live `/api/coding/local-ci` proof after restart:
  - `laneCatalog=38`
  - `catalogVersion=repo-manifest-v2`
  - `latestRun=verify-moussey-self-refresh-landed-source-20260526T0535`
  - `latestRunOverall=pass`
  - `staleMcpCount=20`
- Follow-up hydration diagnostic:
  - `/coding` returned `rows=39`, `inspector=true`, and `/api/coding/local-ci` responded `200`.

## Artifacts

- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/evidence/2026-05-26-c94-selected-object-inspector-desktop.png`
- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/evidence/2026-05-26-c94-selected-object-inspector-mobile.png`
- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/evidence/2026-05-26-c94-diagnostic.png`

## Resume

Do not continue product UI polish in Moussey. Extract the contracts that matter for Litty-CI:

- lane catalog row shape from `/api/coding/local-ci`
- run/report/artifact shape
- selected-object detail shape from `lib/coding-console-model.ts`
- runner/source/spend/blocker vocabulary
- MCP freshness and stale-client signal

Moussey remains the local data/API hub until Litty-CI owns the UI.
