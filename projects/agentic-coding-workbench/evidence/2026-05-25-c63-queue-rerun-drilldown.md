# C63 Queue/Rerun Drilldown Proof

## Goal

Make `/coding` more operable as Leo's internal coding-agent admin console. After C62 moved active work into the first viewport, the next gap was queue/rerun/drilldown: the operator should not have to scroll to answer "what just ran, what can I rerun, and where is the report?"

## Change

- Added a `Queue / Rerun` strip to `/Users/leokwan/Development/moussey/app/coding/page.tsx`.
- The strip sits between `Active Work` and `Patch Routing` in the top operator workspace.
- It exposes:
  - latest run inspect/refresh
  - failed/stale lane dry-run and execute controls
  - `critical_fast` dry-run and execute controls
  - primary report and queue-summary drilldown
- Failed/stale lane reruns reuse the bounded `POST /api/coding/local-ci/run` API with explicit lane ids from latest local-CI proof or the current session's `localCiLastRun`.
- The browser still never accepts arbitrary shell or command text.

## Verification

- `git diff --check -- app/coding/page.tsx` passed.
- `npx tsc --noEmit --pretty false` passed.
- `bash scripts/moussey-server.sh --build` passed with the known local-CI artifact NFT warning from `app/api/coding/local-ci/artifact/route.ts`.
- `bash scripts/moussey-server.sh --restart` passed and restored `http://0.0.0.0:4321`.
- `curl -fsS --max-time 5 http://127.0.0.1:4321/api/health` returned `ok:true`.
- Playwright opened `http://127.0.0.1:4321/coding?fresh=c63-queue-rerun-drilldown` and saw:
  - `Coding command center`
  - `Ledger-backed work map`
  - `Queue / Rerun`
  - `Dry Failed`
  - `Run Failed`
  - `Dry Critical`
  - `Run Critical`
  - `Live Console`
- Desktop overflow: `0`.
- Mobile overflow: `0`.
- Console/page errors: `0`.

## Artifacts

- Desktop screenshot: `/tmp/moussey-c63-queue-rerun-desktop.png`
- Mobile screenshot: `/tmp/moussey-c63-queue-rerun-mobile.png`
- Local URL: `http://127.0.0.1:4321/coding?fresh=c63-queue-rerun-drilldown`

## Notes

- Cleaner-owned files were not edited.
- Local-model editor promotion remains unchanged: Gemma 4 and Qwen3 Aider replays are still experimental until a worker produces relevant source diffs plus passing postcheck.
- Next useful slice: hydrate latest local-CI MCP run/report facts on page load so the queue strip does not depend on the current browser session for detailed lane rerun context.
