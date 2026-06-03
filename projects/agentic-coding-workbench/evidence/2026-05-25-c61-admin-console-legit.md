# C61 Admin Console UX Legitimacy Pass

## Goal

Make `http://127.0.0.1:4321/coding` feel like an internal operator console for local coding agents instead of a scattered AI test bed.

## Changed

- Reworked the `/coding` first viewport into a two-pane operator workspace:
  - left: local-CI verdict, source scope, queue, executor, artifact, patch routing, and Resplit Web proof ladder
  - right: sticky `Live Console` with current run output, refresh controls, and latest detached worker verdict cards
- Collapsed the lower Codex/Nia/toolchain substrate behind `Advanced routing map`, so the first screen leads with operational truth instead of implementation inventory.
- Kept the honest model boundary visible: `Codex Editor` remains the default serious patch route; `Aider Lab` plus Gemma/Qwen workers remain experimental until source diff plus passing postcheck.
- Changed the operator workspace shell from a fixed grid to wrapping flex so desktop keeps the console beside the proof board while mobile stacks without horizontal overflow.

## Live Links

- Coding admin console: `http://127.0.0.1:4321/coding?fresh=c61-admin-console-legit`
- Gemma 4 C57 worker verdict API: `http://127.0.0.1:4321/api/coding/workers/a61ada59-813e-4fcc-bd73-19ff9533bc5e`
- Worker list API: `http://127.0.0.1:4321/api/coding/workers?limit=12`
- Local-CI API: `http://127.0.0.1:4321/api/coding/local-ci`

## Proof

Commands run in `/Users/leokwan/Development/moussey`:

```bash
git diff --check -- app/coding/page.tsx lib/coding-tool-actions.ts lib/coding-workers.ts app/api/coding/workers/route.test.ts scripts/aider-local-model-probe.sh
node --test --import tsx app/api/coding/workers/route.test.ts lib/coding-tool-actions.test.ts app/api/coding/capabilities/route.test.ts
npx tsc --noEmit --pretty false
bash scripts/moussey-server.sh --build && bash scripts/moussey-server.sh --restart
curl -fsS --max-time 5 http://127.0.0.1:4321/api/health
curl -fsS --max-time 5 http://127.0.0.1:4321/api/coding/workers/a61ada59-813e-4fcc-bd73-19ff9533bc5e
curl -fsS --max-time 5 http://127.0.0.1:4321/api/coding/local-ci
```

Results:

- Focused worker/action/capability tests: 22/22 passing.
- TypeScript: passed.
- Diff whitespace check: passed.
- Standalone build/restart: passed with the existing Turbopack NFT warning from `app/api/coding/local-ci/artifact/route.ts`.
- Live health: passed.
- Playwright desktop proof: `/tmp/moussey-c61-admin-console-desktop.png`.
- Playwright mobile proof: `/tmp/moussey-c61-admin-console-mobile.png`.
- Browser checks saw `Coding command center`, `Live Console`, `Resplit Web Proof Ladder`, `Codex Editor`, and `Gemma 4 Worker` on both desktop and mobile, with zero console errors and no horizontal overflow.

## Current Operator Truth

- Local CI currently reports 15/15 lanes passing, but source scope is still mixed: the console shows `1/15 fresh main`, plus dirty/branch proof chips. This is local operator proof, not blanket fresh-main portability.
- Latest Gemma 4 replay worker `a61ada59-813e-4fcc-bd73-19ff9533bc5e` is `failed / experimental`. It built and started historical Resplit Web, reproduced the stale `#globe` precheck failure, ran Aider with `gemma4:e4b`, then postcheck still failed and the patch was empty.
- Qwen3 C57 workers remain failed/experimental for the same promotion reason: no relevant source diff plus passing postcheck.

## Remaining Gap

C57 is now answered negatively for the current Gemma 4 and Qwen3 Aider replay attempts: both local-model editor routes stay experimental. The MVP should keep investing in the admin-console/operator loop and Codex Editor patch path while treating local models as a lab until one produces a relevant source patch and passes the verifier.
