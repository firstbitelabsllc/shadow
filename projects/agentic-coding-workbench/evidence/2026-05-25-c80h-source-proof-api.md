# C80h Source-Proof API Evidence

## Scope

Backend-only Moussey slice. Did not edit `app/coding/page.tsx`; the UX-owned cockpit rendering remains a separate task.

## What Changed

- `/api/coding/local-ci` now exposes `sourceProofComparison`.
- The comparison separates:
  - source-ref green proof
  - fresh-main portability
  - remote-main portability
  - dirty primary checkout state
  - failing proof
  - same-repo mixed source states
- Lane-less metadata reports no longer count as completed source proof.
- Execution source state is classified separately from dirty primary checkout state.
- `remoteMainPortable=true` requires concrete head and remote-main head equality.

## Verification

Commands run from `/Users/leokwan/Development/moussey`:

```bash
node --test --import tsx lib/local-ci-status.test.ts app/api/coding/local-ci/route.test.ts
node --test --import tsx lib/coding-artifacts.test.ts app/api/coding/local-ci/route.test.ts app/api/coding/local-ci/artifact/route.test.ts app/api/coding/runs/patch-route.test.ts lib/local-ci-status.test.ts app/api/coding/tool-actions/run/route.test.ts app/api/coding/workers/route.test.ts
npx tsc --noEmit --pretty false
git diff --check -- app/api/coding/local-ci/route.test.ts app/api/coding/local-ci/artifact/route.ts app/api/coding/local-ci/artifact/route.test.ts app/api/coding/runs/patch-route.test.ts app/api/coding/tool-actions/run/route.ts app/api/coding/tool-actions/run/route.test.ts app/api/coding/workers/route.test.ts app/api/coding/workers/route.ts lib/coding-artifacts.ts lib/coding-artifacts.test.ts lib/coding-workbench.ts lib/coding-workers.ts lib/local-ci-status.ts lib/local-ci-status.test.ts
bash scripts/moussey-server.sh --build
bash scripts/moussey-server.sh --restart
```

Results:

- Local-CI route/status tests: 19/19 pass.
- Expanded coding backend suite: 52/52 pass.
- TypeScript: pass.
- Diff check: pass.
- Build/restart: pass, with the known Turbopack NFT warning on the local-CI artifact route.

Live API proof from `http://127.0.0.1:4321`:

```text
local-ci 200 ok
source-proof fresh_main latest_passing mega-resplit-ios-origin-main-integration-ui-retained-20260525T2050
source-summary Latest compared proof mega-resplit-ios-origin-main-integration-ui-retained-20260525T2050 is clean fresh-main portable.
source-flags {"sourceRefGreen":false,"freshMainPortable":true,"remoteMainPortable":true,"dirtyPrimary":true}
source-repos resplit_ios:fresh_main
latest-run-artifact local-ci-report /api/coding/local-ci/artifact?path=%2FUsers%2Fleokwan%2F.agent-ledger%2Ffirstbite-local-ci-mcp%2Fmega-resplit-ios-origin-main-integration-ui-retained-20260525T2050%2Freport.json
artifact-fetch 200 local-ci-report overview
coding-page 200
```

## Remaining

The UX agent should consume `sourceProofComparison` and render source-ref-green, fresh-main-portable, remote-main-portable, dirty-primary, and mixed repo proof as visible cockpit states. Backend should stay closed unless that rendering pass finds a missing field.
