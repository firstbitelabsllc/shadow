# C59 - C57 Fixture + Admin Console Proof Ladder

Date: 2026-05-25

## Goal

Make the Moussey `/coding` surface feel like a real internal coding-agent admin console and unblock the C57 Gemma 4 vs Qwen3 Aider replay from the historical Resplit Web Redis/KV build crash.

## What Changed

- `moussey/scripts/aider-c57-replay.sh`
  - Added an explicit no-secret Resplit Web fixture for C57 historical replays:
    - `NEXT_PUBLIC_LIVE_SPLIT_API=mock`
    - `LIVE_SPLIT_KV_DRIVER=memory`
    - `LIVE_SPLIT_LOCAL_E2E=1`
    - `LIVE_SPLIT_DISABLE_RATE_LIMITS=1`
    - unique `LIVE_SPLIT_NAMESPACE`
    - loopback inert Upstash/KV placeholder URLs/tokens
  - Runs `next build`, `next start`, Playwright precheck, Aider, and postcheck under the same fixture env.
  - Hardened cleanup so escaped `next start` npm/node children do not leave a listener, worktree, branch, or port lock behind.
  - Hardened verifier exit-code capture so a red postcheck is recorded as a model/verifier verdict instead of an unset shell variable.

- `moussey/app/coding/page.tsx`
  - Added first-viewport `Resplit Web Proof Ladder`.
  - The ladder now shows the intended admin flow:
    - CI proof
    - public matrix
    - Codex patch
    - local-model replay
  - Added direct admin links for `/coding`, `/chat`, `/api/coding/capabilities`, and `/api/coding/workers`.
  - Added direct action buttons for dry/run critical CI, public matrix, preflight/verify/Codex Editor, and Qwen3/Gemma 4 C57 workers.

## Proof

- Fake-Aider fixture proof:
  - Log: `/tmp/moussey-c59-c57-fixture-cleanup.log`
  - Historical Resplit Web base: `412c49bff1252a26568e98ec3401adcdec9ee120`
  - Server: `http://127.0.0.1:3117`
  - Build completed under local memory KV fixture.
  - Precheck reproduced the intended stale landing-smoke failure: `#globe` missing, `1 failed / 4 passed`.
  - Fake editor made no patch.
  - Postcheck reproduced the same verifier failure.
  - Cleanup left no matching worktree, branch, port lock, or listener.

- Loopback/exit-status proof after hardening:
  - Run id: `c59-loopback-pipefix-20260525T043542Z`
  - Aider stand-in: `/usr/bin/true`
  - Port: `3120`
  - Expected script exit: `1`, because the verifier stayed red.
  - Precheck: `#globe` missing, `1 failed / 4 passed`.
  - Postcheck: `#globe` missing, `1 failed / 4 passed`.
  - No unset shell variable occurred.
  - Cleanup verification found no matching worktree, branch, listener on `3120`, or port lock.

- Live worker proof:
  - Worker: `33556c5f-8853-46c2-9b04-52580a28073f`
  - Status: `http://127.0.0.1:4321/api/coding/workers/33556c5f-8853-46c2-9b04-52580a28073f`
  - Log: `/Users/leokwan/.moussey/coding-workers/33556c5f-8853-46c2-9b04-52580a28073f/worker.log`
  - Result when recorded: Qwen3 replay reached Aider and Aider exited `0`, but it did not produce a passing source fix; postcheck still failed on missing `#globe`.
  - Local-model verdict: Qwen3 remains experimental for this lane. The harness is now useful; the model-quality gate is still red.

- UI proof:
  - URL: `http://127.0.0.1:4321/coding?fresh=c59-admin-console-final`
  - Desktop screenshot: `/tmp/moussey-coding-admin-console-final-desktop.png`
  - Mobile screenshot: `/tmp/moussey-coding-admin-console-final-mobile.png`
  - Playwright verified the page included `RESPLIT WEB PROOF LADDER`, `CI proof -> public matrix -> Codex patch -> local-model replay`, and `Qwen3 / Gemma replay`.

- Verification:
  - `bash -n scripts/aider-c57-replay.sh`
  - `node --test --import tsx lib/coding-tool-actions.test.ts lib/capability-catalog.test.ts app/api/coding/workers/route.test.ts app/api/coding/tool-actions/run/route.test.ts app/api/coding/capabilities/route.test.ts`
  - Result: `38/38` passed.
  - `npx tsc --noEmit --pretty false`
  - `git diff --check`
  - `npm run build`
  - `bash scripts/moussey-server.sh --restart`
  - Live `/api/health`
  - Live `/api/coding/capabilities`

## Remaining Gates

- C57 is unblocked at the harness level, but not complete at the model-quality level.
- Qwen3 ran and did not produce changed source plus passing postcheck, so it is not promoted.
- Gemma 4 replay still needs to run through the same worker path.
- Aider remains an experimental local-model lab route; Codex Editor remains the default serious patch path until local models prove source diff plus verifier green.
