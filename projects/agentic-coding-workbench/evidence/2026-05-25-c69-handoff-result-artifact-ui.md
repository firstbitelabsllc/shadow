# C69 Handoff Result Artifact UI

## Summary

C69 makes `/coding` behave more like an internal agent-job console after a handoff launch. A handoff-fired lane now gets a first-viewport `Agent Result` tile plus a `Handoff Result` queue card showing run id, mode, exit state, duration, teardown state, model route, worktree/port, and patch artifact path/bytes when the lane saves a patch.

This is a UI/proof slice only. The browser proof used a controlled local handoff and intercepted the lane SSE stream to avoid spending Codex/model time. The next proof gap remains a non-intercepted handoff-fired verifier/editor run against a real red lane.

## Code

- Moussey `/coding`: `/Users/leokwan/Development/moussey/app/coding/page.tsx`
  - Added `HandoffLaunchResult` state.
  - `runLaneJob` now records handoff-fired `meta`, `patch-saved`, `complete`, and `error` events.
  - First viewport now shows `Agent Result`.
  - Queue/Rerun strip now shows `Handoff Result` with `Inspect` and guarded `Patch` buttons.
- Run history: `/Users/leokwan/Development/moussey/lib/coding-workbench.ts`
  - Preserves `handoffId` from accepted run events so a refreshed page can associate local run history with the staged handoff.

## Verification

- `npx tsc --noEmit --pretty false`
- `node --test --import tsx lib/coding-workbench.test.ts app/api/coding/lanes/run/route.test.ts app/api/coding/runs/route.test.ts app/api/coding/runs/patch-route.test.ts app/api/coding/local-ci/handoff/route.test.ts lib/local-ci-status.test.ts app/api/coding/local-ci/route.test.ts`
  - 37/37 passing.
- `npm run test:brain-dispatcher`
  - 183/183 passing.
- `git diff --check -- app/coding/page.tsx lib/coding-workbench.ts lib/coding-workbench.test.ts`
- `npm run build`
  - Passed with the existing known Turbopack NFT warning from `app/api/coding/local-ci/artifact/route.ts`.
- `launchctl kickstart -k gui/$UID/com.leokwan.moussey-server`
- `curl -fsS --max-time 3 http://127.0.0.1:4321/api/health`
  - `ok:true`
- `/Users/leokwan/Development/moussey/scripts/moussey-trigger-doctor --brief`
  - `launchagent=ok listener=ok endpoint=accepting secret=ok`
- `curl -fsS --max-time 3 http://127.0.0.1:7191/api/health`
  - `ok:true`

## Browser Proof

- URL: `http://127.0.0.1:4321/coding?handoff=c7bece68-7d9f-45ba-9c0e-9738200c1ee6&fresh=c69-handoff-result-v3`
- Screenshot: `projects/agentic-coding-workbench/evidence/2026-05-25-c69-handoff-result-ui.png`
- Proof shape:
  - Created a local Vidux-sourced handoff with `proposedAction:"codex-editor"`.
  - Intercepted only `POST /api/coding/lanes/run`.
  - Asserted the handoff launch posted the expected handoff id and `mode:"codex-editor"`.
  - Returned SSE frames for `meta`, `patch-saved`, and `complete`.
  - Browser found:
    - `Agent Result`: 1
    - `Handoff Result`: 1
    - `patch saved`: 2
    - `2048B patch`: 2
    - `c69-ui-proof-run`: 2

## Remaining Gap

Run a non-intercepted handoff-fired verifier/editor cycle from a real failed/stale lane and prove the same first-viewport result card against the actual run history plus real patch/verifier artifact.
