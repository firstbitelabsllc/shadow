# C62 Active Work Strip Proof

## Goal

Make `/coding` feel more like Leo's internal coding-agent admin console by moving Ledger-backed active work into the first operator viewport. The operator should see current repo/agent ownership before firing CI, Codex Editor, or local-model lab actions.

## Change

- Added a compact `Active Work` strip to `/Users/leokwan/Development/moussey/app/coding/page.tsx`.
- The strip sits between CI truth cards and Patch Routing in the top operator workspace.
- It shows active-work status, repo count, priority repo cards, current owner labels, and recent ledger snippets.
- Clicking a repo sends `formatActiveWorkRepo(repo)` into the sticky `Live Console`.
- The lower full `Active Work Map` remains in place as the detailed matrix.

## Verification

- `git diff --check -- app/coding/page.tsx` passed.
- `npx tsc --noEmit --pretty false` passed.
- `bash scripts/moussey-server.sh --build` passed with the known local-CI artifact NFT warning from `app/api/coding/local-ci/artifact/route.ts`.
- `bash scripts/moussey-server.sh --restart` passed and restored `http://0.0.0.0:4321`.
- Playwright opened `http://127.0.0.1:4321/coding?fresh=c62-active-work-strip` and saw:
  - `Coding command center`
  - `Ledger-backed work map`
  - `Live Console`
  - `Patch Routing`
  - `Resplit Web Proof Ladder`
- Desktop overflow: `0`.
- Mobile overflow: `0`.
- Console/page errors: `0`.

## Artifacts

- Desktop screenshot: `/tmp/moussey-c62-active-work-desktop.png`
- Mobile screenshot: `/tmp/moussey-c62-active-work-mobile.png`
- Local URL: `http://127.0.0.1:4321/coding?fresh=c62-active-work-strip`

## Notes

- A quick `curl --max-time 5` capability sample timed out earlier in the turn after `/api/health` succeeded, so the UX should continue to treat capability loading as something that may take longer than a tiny health check.
- Cleaner-owned files were not edited.
- Local-model editor promotion remains unchanged: Gemma 4 and Qwen3 Aider replays are still experimental until a worker produces relevant source diffs plus passing postcheck.
