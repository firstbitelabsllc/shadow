# C60 Worker Verdicts

## Goal

Make `/coding` feel like a real internal admin console for local coding agents by turning detached worker logs into visible operator verdicts.

## Changed

- Added structured C57 Aider replay verdict parsing in Moussey worker status:
  - `status`: passed, failed, running, or unknown
  - `promotionStatus`: candidate, experimental, blocked, or unknown
  - model name, patch artifact path, patch-empty state, patch byte count
  - per-check rows for build/start, precheck, Aider, postcheck, and diff check
- Rendered worker verdicts directly in `/coding` worker cards.
- Added terminal-summary output that explains the verdict before raw log details.
- Added a regression test for the old Qwen3 C57 worker log where the postcheck was visibly red but the old harness lost the clean exit marker.

## Proof

Commands run in `/Users/leokwan/Development/moussey`:

```bash
node --test --import tsx lib/coding-tool-actions.test.ts lib/capability-catalog.test.ts app/api/coding/workers/route.test.ts app/api/coding/tool-actions/run/route.test.ts app/api/coding/capabilities/route.test.ts
npx tsc --noEmit --pretty false
git diff --check -- lib/coding-workers.ts app/api/coding/workers/route.test.ts app/coding/page.tsx
npm run build
bash scripts/moussey-server.sh --restart
curl -fsS --max-time 5 http://127.0.0.1:4321/api/health
curl -fsS --max-time 5 'http://127.0.0.1:4321/api/coding/workers?limit=12'
```

Results:

- Focused worker/action/capability tests: 39/39 passing.
- TypeScript: passed.
- Diff whitespace check: passed.
- Build: passed with the existing Turbopack NFT warning from `app/api/coding/local-ci/artifact/route.ts`.
- Restart/live health: passed.
- Worker list API: shows the two C57 Qwen3 replay workers with structured failed/experimental verdicts.
- Playwright UI proof: `http://127.0.0.1:4321/coding?fresh=c60-worker-verdicts-settled` renders `Coding command center`, `RESPLIT WEB PROOF LADDER`, `Agent workers`, `C57 Aider Qwen3 Replay`, and the verdict text.
- Screenshot: `/tmp/moussey-c60-worker-verdicts-settled.png`.

## Current Verdicts

- `33556c5f-8853-46c2-9b04-52580a28073f`: failed / experimental. Qwen3 reached Aider, but pre/postcheck stayed red, no passing source fix was produced, and the old harness lacked the fixed postcheck marker.
- `14ab1cbc-5b3e-450f-8916-541de49bb446`: failed / experimental. The no-secret fixture run did not produce a passing source patch.

## Local-CI State

The admin console is honestly red today:

- `/api/coding/local-ci` reports 14/15 passing lanes.
- `resplit_currency_api_integration` is the red lane.
- The C60 UX work is green, but the overall local-CI control plane is not all green.

## Remaining Gap

C57 remains open. Gemma 4 still needs the same no-secret replay, and no local model should be promoted until it changes relevant source and passes the postcheck.
