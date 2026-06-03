# C72 Mission-Stale Handoff Proof

## What Changed

- `/coding` now derives a Resplit Web mission handoff when the mission lane is pass-but-not-fresh-main or otherwise source-stale.
- The first-viewport `Handoff` tile now prefers the mission-scoped Resplit Web target (`mission verifier`) over unrelated global fleet failures.
- `Global Attention` still shows the fleet red lane (`resplit_ios_ui_full` today), so the console does not hide broader local-CI risk.
- No model-spend, arbitrary shell, cross-Mac write bridge, or primary-checkout mutation was added.

## Live State Verified

- Resplit Web mission: `3/3` pass, but integration/UI proof falls back to current dirty repo state instead of fresh `origin/main`.
- Current source state for the mission handoff: branch `claude/web-FLAKE-e2e-investigation`, `83` dirty paths.
- Global attention: `resplit_ios_ui_full`, kept separate from the mission handoff target.
- Staged handoff: `223131fe-cc49-4b23-a923-0e56d734d610`.

## Commands

```bash
npx tsc --noEmit --pretty false
git diff --check -- app/coding/page.tsx
npm run build
launchctl kickstart -k gui/$UID/com.leokwan.moussey-server
curl -fsS --max-time 5 http://127.0.0.1:4321/api/health
curl -fsS --max-time 5 http://127.0.0.1:4321/api/coding/handoffs/223131fe-cc49-4b23-a923-0e56d734d610
```

Browser proof used the existing Vidux Playwright install:

```bash
node --input-type=module # opened desktop/mobile /coding, asserted Mission Lane, Resplit Web, mission verifier, Global Attention, resplit_ios_ui_full, clicked the mission verifier handoff, asserted the staged prompt, and saved screenshots.
```

## Proof

- Mission handoff UI: `http://127.0.0.1:4321/coding?fresh=c72-mission-handoff`
- Staged mission handoff: `http://127.0.0.1:4321/coding?handoff=223131fe-cc49-4b23-a923-0e56d734d610`
- Handoff API: `http://127.0.0.1:4321/api/coding/handoffs/223131fe-cc49-4b23-a923-0e56d734d610`
- Screenshot: `projects/agentic-coding-workbench/evidence/2026-05-25-c72-mission-handoff-desktop.png`
- Mobile screenshot: `projects/agentic-coding-workbench/evidence/2026-05-25-c72-mission-handoff-mobile.png`
- Browser result: zero console/page errors, no horizontal overflow on desktop or `390x844` mobile.

## Remaining Gap

This completes the mission-scoped handoff UX/control-plane slice. The next proof gap is to run a non-intercepted handoff-fired verifier/editor cycle from this real stale Resplit Web mission handoff, then surface the resulting status, patch/verifier artifact, and before/after evidence in the first viewport.
