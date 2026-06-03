# C73 Command Strip Proof

## What Changed

- `/coding` now has a compact first-viewport command strip above the status-card grid.
- The strip exposes the admin-console actions that matter first: mission action, `critical_fast` dry-run, refresh state, and the owning Vidux plan link.
- The mission action uses the same bounded primary action as the operator cards. Current live state labels it `Stage mission verifier` because Resplit Web proof is pass-but-not-fresh-main while the global iOS red remains separate.
- No model-spend, arbitrary shell, cross-Mac write bridge, or primary-checkout mutation was added.

## Live State Verified

- Command strip shows `Mission Action`, `Stage mission verifier`, `Critical Gate`, `Dry-run critical_fast`, `Console State`, and `Open Vidux plan`.
- Global attention still shows `resplit_ios_ui_full` as separate fleet health.
- The command-strip mission action and the `Next Action` card now share the same activation path and label.

## Commands

```bash
git diff --check -- app/coding/page.tsx
npm run build
launchctl kickstart -k gui/$UID/com.leokwan.moussey-server
curl -fsS --max-time 5 http://127.0.0.1:4321/api/health
```

Note: full `npx tsc --noEmit --pretty false` currently fails on neighboring untracked Cleaner tests (`lib/cleaner/cleanup-proposal.test.ts`, `lib/cleaner/review-training.test.ts`). This slice did not edit Cleaner files; `npm run build` still passed the app TypeScript/build path.

Browser proof used the existing Vidux Playwright install:

```bash
node --input-type=module # opened desktop/mobile /coding, asserted the command strip, mission verifier, global attention separation, no console/page errors, and no horizontal overflow.
```

## Proof

- Command-strip UI: `http://127.0.0.1:4321/coding?fresh=c73-command-strip`
- Screenshot: `projects/agentic-coding-workbench/evidence/2026-05-25-c73-command-strip-desktop.png`
- Mobile screenshot: `projects/agentic-coding-workbench/evidence/2026-05-25-c73-command-strip-mobile.png`
- Browser result: zero console/page errors, no horizontal overflow on desktop or `390x844` mobile.

## Remaining Gap

The first viewport is now closer to an internal GUI admin console, but the next product proof is still the same: run a non-intercepted handoff-fired verifier/editor cycle from the real stale Resplit Web mission handoff and render the result/patch/verifier artifact in the first viewport.
