# C80c Production Cockpit Proof

## Summary

C80c tightened the `/coding` local-CI cockpit after the first responsive pass proved the layout but exposed two product-quality issues:

- stream/lane actions could appear `done` when the SSE stream ended without a terminal event
- live runner-readiness text could overflow on 390px mobile once real M4 peer probe data hydrated

The code now treats lost streams and detached workers as `unknown` instead of green, exposes typed runner readiness from `/api/coding/local-ci`, and wraps long MCP/M4/runtime evidence text in the cockpit cards and proof strips.

## Verification

Browser Use bootstrap:

```text
uv tool install --upgrade browser-use
browser-use install
browser-use doctor
browser-use open http://127.0.0.1:4322/coding
browser-use state
browser-use close
```

Result: Browser Use local control works. `doctor` reports local browser/profile/network ready; cloud API key, `cloudflared`, and `profile-use` remain optional missing pieces for cloud/tunnel/profile-sync flows.

Focused tests:

```text
node --test --import tsx app/api/coding/lanes/run/route.test.ts lib/coding-workbench.test.ts app/api/coding/local-ci/run/route.test.ts lib/local-ci-status.test.ts app/api/coding/local-ci/route.test.ts
```

Result: 47/47 passing.

Type/build:

```text
npx tsc --noEmit --pretty false
npm run build
```

Result: both passed. Build still prints the known Turbopack NFT warning for `next.config.ts` traced through `app/api/coding/local-ci/artifact/route.ts`.

Production browser proof:

```text
npm run start -- --port 4323
Playwright Chromium -> http://127.0.0.1:4323/coding
```

Result:

- desktop `1440x1200`: `scrollWidth=1440`, no overflow offenders, no console errors
- mobile `390x1200`: `scrollWidth=390`, no overflow offenders, no console errors
- live API hydration confirmed: `/api/coding/jobs`, `/api/coding/runs`, `/api/coding/workers`, and `/api/coding/local-ci` loaded
- required live text present: `13/15 declared pass`, `Runner Recovery`, `No Docker needed`

Screenshots:

- `projects/agentic-coding-workbench/evidence/2026-05-25-c80c-production-cockpit-desktop.png`
- `projects/agentic-coding-workbench/evidence/2026-05-25-c80c-production-cockpit-mobile.png`

## Current Truth

The local-CI cockpit is materially more usable, but the product goal remains active. The current live truth is red/yellow rather than done:

- `13/15` declared lanes pass in the hydrated production UI
- M4 remains support-only until it writes its own local `run_lanes execute` proof
- the promoted Resplit Web source ref exists and is visible, but FirstBite source-ref proof remains the recommended next action
- active checkout manifests are still not fully clean/committed even though fresh-clone manifests are present
