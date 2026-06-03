# C71 Resplit Web Mission-Lane Separation

## What Changed

- `/coding` now has a first-viewport `Mission Lane` card for the actual MVP proving surface: Resplit Web / `/autobot-resplit-web` / FirstBite local-CI.
- `Next Action` now prioritizes the Resplit Web mission when it needs proof. Current live state says `Reprove Resplit Web` because Resplit Web is `3/3 pass` but only `1/3 fresh main`.
- A separate `Global Attention` card keeps fleet-level red proof visible. Current live state shows `resplit_ios_ui_full` as the only global red lane, explicitly outside the Resplit Web first-lane mission.
- No cross-Mac write bridge, arbitrary shell, model-spend, or primary-checkout mutation was added.

## Live State Verified

- Local CI summary: `17/18` pass, `1` red, `0` stale/missing, definition drift present (`18` proof lanes / `15` declared).
- Resplit Web mission: `3/3` pass, `1/3` fresh main, current checkout `local dirty`.
- Global attention: `resplit_ios_ui_full`, source from lane catalog latest proof.

## Commands

```bash
npx tsc --noEmit --pretty false
git diff --check -- app/coding/page.tsx
npm run build
launchctl kickstart -k gui/$UID/com.leokwan.moussey-server
curl -fsS --max-time 5 http://127.0.0.1:4321/api/health
```

Browser proof used the existing Vidux Playwright install:

```bash
node --input-type=module # opened desktop/mobile /coding URLs, asserted Mission Lane, Resplit Web, needs fresh-main proof, Global Attention, resplit_ios_ui_full, no horizontal overflow, and saved screenshots.
```

## Proof

- Desktop: `http://127.0.0.1:4321/coding?fresh=c71-resplit-web-mission-lane`
- Mobile: `http://127.0.0.1:4321/coding?fresh=c71-resplit-web-mission-lane-mobile`
- Screenshot: `projects/agentic-coding-workbench/evidence/2026-05-25-c71-resplit-web-mission-lane.png`
- Mobile screenshot: `projects/agentic-coding-workbench/evidence/2026-05-25-c71-resplit-web-mission-lane-mobile.png`
- Browser result: zero console/page errors, no horizontal overflow on desktop or `390x844` mobile.

## Remaining Gap

The UI is clearer, but this was still a UX/control-plane slice. The next proof gap is unchanged: run a non-intercepted handoff-fired verifier/editor cycle from a real failed/stale lane and surface its resulting status, patch/verifier artifact, and before/after evidence in the first viewport.
