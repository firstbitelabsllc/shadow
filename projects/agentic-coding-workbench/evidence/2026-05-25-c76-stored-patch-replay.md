# C76 Stored Patch Replay

## What Changed

Moussey `/coding` now has a `patch-replay` lane and a first-viewport `Patch Replay` command. It finds the latest saved source patch from run history, applies it in a disposable Resplit Web worktree, reruns the local smoke verifier, saves a fresh patch artifact, and tears the worktree/server/port lock down.

This is the no-spend fallback after C75: when Codex edit authority is blocked by usage limits but a prior good patch artifact exists, Leo can replay the stored patch and get verifier proof without calling Codex, Aider, Ollama, Hugging Face, or Claude.

## Live Proof

- UI: `http://127.0.0.1:4321/coding?fresh=c55-patch-replay`
- Source patch run: `adb960ae-1805-4695-8c78-6dd1fbed4d2a`
- Source patch path: `/Users/leokwan/.moussey/coding-patches/adb960ae-1805-4695-8c78-6dd1fbed4d2a.patch`
- Replay run: `9e532045-a3fb-487a-bfab-9adf2e969d33`
- Replay patch path: `/Users/leokwan/.moussey/coding-patches/9e532045-a3fb-487a-bfab-9adf2e969d33.patch`
- SSE evidence: `projects/agentic-coding-workbench/evidence/2026-05-25-c76-patch-replay-live.sse`
- Screenshot: `projects/agentic-coding-workbench/evidence/2026-05-25-c76-patch-replay-hydrated.png`

## Verification

```bash
node --test --import tsx lib/coding-lanes.test.ts app/api/coding/lanes/run/route.test.ts
npx tsc --noEmit --pretty false
npm run test:brain-dispatcher
scripts/moussey-server.sh --build
scripts/moussey-server.sh --restart
scripts/moussey-trigger-doctor --brief
curl -fsS -N --max-time 900 -X POST http://127.0.0.1:4321/api/coding/lanes/run \
  -H 'Content-Type: application/json' \
  -d '{"jobId":"resplit-web-autobot","mode":"patch-replay","label":"Stored Patch","patchRunId":"adb960ae-1805-4695-8c78-6dd1fbed4d2a"}'
```

Focused tests passed `29/29`. Brain-dispatcher passed `184/184`. TypeScript passed. Standalone build/restart passed with the known local-CI artifact Turbopack NFT warning. `scripts/moussey-trigger-doctor --brief` returned `launchagent=ok listener=ok endpoint=accepting secret=ok`. Moussey `/api/health` and Vidux `/api/health` returned `ok:true`. The live patch replay finished with `exitCode:0`, `teardownOk:true`, and Playwright `5 passed`.

## Operator Readout

The hydrated `/coding` first viewport shows:

- `Patch Replay`
- `Replay stored patch`
- `adb960ae · 1673B · no model call`
- latest run `ok · patch-replay`

## Remaining Gap

Make stored patch review/apply/replay feel like one obvious operator flow, then rerun the same Resplit Web mission verifier against the target source state until the mission lane is fresh-main portable.
