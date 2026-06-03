# C65 First-Viewport Handoff Evidence

## Scope

- Moussey `/coding` now makes the FirstBite failed/stale lane handoff path visible in the operator viewport beside the CI verdict.
- The detailed `Queue / Rerun` strip moved ahead of the Ledger Active Work strip so local-CI controls are treated as primary cockpit actions.
- `POST /api/coding/local-ci/handoff` now carries source branch/head/remote-main/dirty/ahead-behind context into the generated verifier/editor follow-up prompt.
- Current live local-CI data has no failed/stale lanes, so the Handoff controls render disabled with `no red lane`; the route test covers the enabled source-state handoff path.

## Changed Files

- `/Users/leokwan/Development/moussey/app/coding/page.tsx`
- `/Users/leokwan/Development/moussey/app/api/coding/local-ci/handoff/route.ts`
- `/Users/leokwan/Development/moussey/app/api/coding/local-ci/handoff/route.test.ts`

## Live Data

`GET http://127.0.0.1:4321/api/coding/local-ci` returned:

```json
{
  "ok": true,
  "latestRun": "verify-resplit-web-origin-main-plus-token-fix-20260525",
  "overall": "pass",
  "recentRuns": 2,
  "total": 17,
  "passing": 17,
  "failing": 0,
  "stale": 0
}
```

## Verification

```bash
node --test --import tsx app/api/coding/local-ci/handoff/route.test.ts lib/local-ci-status.test.ts app/api/coding/local-ci/route.test.ts
git diff --check -- app/coding/page.tsx app/api/coding/local-ci/handoff/route.ts app/api/coding/local-ci/handoff/route.test.ts lib/local-ci-status.ts app/api/coding/local-ci/route.ts app/api/coding/local-ci/route.test.ts lib/local-ci-status.test.ts
npx tsc --noEmit --pretty false
npm run build
launchctl kickstart -k gui/$UID/com.leokwan.moussey-server
curl -fsS http://127.0.0.1:4321/api/health
```

Results:

- Focused local-CI/handoff tests: `12/12` pass.
- `git diff --check`: pass.
- TypeScript: pass.
- `npm run build`: pass with the known Turbopack NFT warning from `app/api/coding/local-ci/artifact/route.ts`.
- Live health: `ok:true`, `agent.backend:"off"`, Codex/Hermes/Claude CLIs ready.

## Browser Proof

URL:

- `http://127.0.0.1:4321/coding?fresh=c65-first-viewport-handoff`

Playwright proof:

- Desktop `1440x1100`: saw `Handoff`, `Queue / Rerun`, `Latest FirstBite Run`, `verify-resplit-web-origin-main-plus-token-fix-20260525`; first handoff tile fully in viewport; zero console/page errors.
- Mobile `390x1100`: saw the same texts; first handoff tile fully in viewport; zero console/page errors.
- Current state shows `HANDOFF / no red lane / no failed/stale handoff target`, matching the all-pass local-CI report.

Screenshots:

- `/tmp/moussey-c65-first-viewport-handoff.png`
- `/tmp/moussey-c65-first-viewport-handoff-mobile.png`

## Remaining Gap

Prove the enabled click path against a real failed/stale FirstBite lane or a controlled fixture: clicking Handoff should create the handoff, open/show its id/status, and make the next verifier/editor action obvious without requiring a hidden console or arbitrary shell.
