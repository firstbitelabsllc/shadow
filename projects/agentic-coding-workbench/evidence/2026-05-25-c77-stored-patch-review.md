# C77 Stored Patch Review Flow

## Summary

Moussey `/coding` now treats stored patch replay as a first-class operator review flow instead of a single hidden run button. The first viewport at `http://127.0.0.1:4321/coding?fresh=c77-stored-patch-review` shows:

- `Stored Patch Review`
- source patch `adb960ae`
- replay proof `9e532045`
- `Inspect Source`
- `Apply+Verify`
- `Inspect Replay`

The flow preserves the C76 safety boundary: source patches are read from guarded local patch artifacts, replay applies only in a disposable Resplit Web worktree, and the primary checkout is not mutated.

## Code Surface

- `/Users/leokwan/Development/moussey/app/coding/page.tsx`
  - added `latestPatchReplayRun` / patch review readiness derived from run history
  - added first-viewport `Stored Patch Review` strip
  - added source patch, replay proof, and inspect/apply controls
  - renamed the lower proof-ladder replay action to `Apply+Verify`

## Verification

- `npx tsc --noEmit --pretty false`
- `node --test --import tsx lib/coding-lanes.test.ts app/api/coding/lanes/run/route.test.ts`
  - 29/29 passing
- `npm run test:brain-dispatcher`
  - 184/184 passing
- `scripts/moussey-server.sh --build && scripts/moussey-server.sh --restart`
  - passed with the known local-CI artifact-route NFT warning
- `scripts/moussey-trigger-doctor --brief`
  - `launchagent=ok listener=ok endpoint=accepting secret=ok selfname=Studio peers_configured=3`
- `curl -fsS --max-time 3 http://127.0.0.1:4321/api/health`
  - ok
- `curl -fsS --max-time 3 http://127.0.0.1:7191/api/health`
  - ok
- Playwright browser proof from Vidux's installed Playwright package:
  - `Stored Patch Review` count: 1
  - `Apply+Verify` count: 2

## Artifacts

- `projects/agentic-coding-workbench/evidence/2026-05-25-c77-stored-patch-review-first-viewport.png`
- `projects/agentic-coding-workbench/evidence/2026-05-25-c77-stored-patch-review.png`

## Remaining Gap

The reviewed replay proof is green, but the larger MVP is not complete until the Resplit Web mission lane's source-state truth can show fresh-main portable proof instead of only local replay proof. Next slice: connect reviewed replay/verifier evidence back into the mission source-state badge and rerun the mission verifier until that first proving lane is portable.
