# C64 Local-CI Run Hydration Evidence

## Scope

- Moussey `/api/coding/local-ci` now normalizes durable FirstBite MCP `reports` into typed `recentRuns` and `latestRun`.
- Moussey `/coding` hydrates the first-viewport Queue/Rerun strip from `latestRun` on load, before Leo launches a new run in the current browser session.
- The Queue/Rerun strip now names the rerun source: latest MCP run, lane-catalog latest proof, or local CI catalog.

## Changed Files

- `/Users/leokwan/Development/moussey/lib/local-ci-status.ts`
- `/Users/leokwan/Development/moussey/lib/local-ci-status.test.ts`
- `/Users/leokwan/Development/moussey/app/api/coding/local-ci/route.test.ts`
- `/Users/leokwan/Development/moussey/app/coding/page.tsx`

## Live Data

`GET http://127.0.0.1:4321/api/coding/local-ci` returned:

```json
{
  "ok": true,
  "latestRun": {
    "run_id": "verify-resplit-web-origin-main-plus-token-fix-20260525",
    "overall": "pass",
    "created_at": "2026-05-25T02:08:29Z",
    "lanes": 1
  },
  "recentRuns": 2,
  "summary": {
    "totalLanes": 17,
    "passingLanes": 17,
    "failingLanes": 0,
    "staleOrMissingLanes": 0,
    "activeXcodeProcessCount": 1
  }
}
```

## Verification

- `node --test --import tsx lib/local-ci-status.test.ts app/api/coding/local-ci/route.test.ts` passed 10/10.
- `git diff --check -- lib/local-ci-status.ts lib/local-ci-status.test.ts app/api/coding/local-ci/route.test.ts app/coding/page.tsx` passed.
- `npx tsc --noEmit --pretty false` passed.
- `npm run build` passed with the known Turbopack NFT warning from `app/api/coding/local-ci/artifact/route.ts`.
- `launchctl kickstart -k gui/$UID/com.leokwan.moussey-server` restarted Moussey.
- `GET http://127.0.0.1:4321/api/health` returned `ok:true`.
- Playwright opened `http://127.0.0.1:4321/coding?fresh=c64-local-ci-run-hydration` and found:
  - `QUEUE / RERUN`
  - `Latest FirstBite run pass`
  - `verify-resplit-web-origin-main-plus-token-fix-20260525`
  - `hydrated from latest MCP run verify-resplit-web-origin-main-plus-token-fix-20260525; no red lane list`

## Screenshots

- Desktop first viewport: `/tmp/moussey-c64-local-ci-run-hydration-first-viewport.png`
- Mobile first viewport after hydration: `/tmp/moussey-c64-local-ci-run-hydration-mobile-first-viewport-loaded.png`
- Full desktop page: `/tmp/moussey-c64-local-ci-run-hydration-desktop.png`
- Full mobile page: `/tmp/moussey-c64-local-ci-run-hydration-mobile.png`

## Boundaries

- No arbitrary shell was exposed through the browser.
- No cross-Mac ownership bounce or remote plan mutation was added.
- Local-CI green remains source-scoped: current UI says `17/17 pass` while also showing mixed source scope (`1/15 fresh main`) and Xcode contention.
- `Codex Editor` remains the default serious patch route; Aider/Gemma/Qwen remain experimental until they produce a relevant source diff plus passing postcheck.

## Next Gap

The next workbench gap is lane-result-to-handoff polish: failed/stale lane cards should make the verifier/editor follow-up path as obvious as the rerun path, using the hydrated latest MCP run when available.
