# C66 Enabled Local-CI Handoff Proof

## Scope

Make the `/coding` first viewport prove the enabled FirstBite failed/stale-lane handoff path, not only the disabled clean-CI state from C65.

## Changed Surface

- `/Users/leokwan/Development/moussey/app/coding/page.tsx`
  - The first-viewport `Handoff` truth tile now switches into handoff-inspector mode when a `?handoff=<id>` record is loaded.
  - Clicking the tile writes the handoff id, source, label, proposed action, source run id, and full prompt into Live Console.
  - `stageLocalCiHandoff` now keeps the created handoff in local React state, updates the URL with `history.replaceState`, and leaves the staged handoff visible in the current tab instead of navigating away.
- `/Users/leokwan/Development/moussey/app/api/coding/local-ci/handoff/route.ts`
  - Existing C65 source-state fields remain in the prompt contract.
- `/Users/leokwan/Development/moussey/app/api/coding/local-ci/handoff/route.test.ts`
  - Existing route test verifies source status, remote-main head, dirty count, and Codex Editor preference.

## Controlled Handoff

- Input: controlled failed `resplit_web_unit` lane payload.
- Run id: `controlled-c66-handoff-proof-20260525`.
- Handoff id: `a26a14af-4d1c-409f-975b-6fd8cfadcf6a`.
- URL: `http://127.0.0.1:4321/coding?handoff=a26a14af-4d1c-409f-975b-6fd8cfadcf6a`.
- Proposed action: `codex-editor`.
- Label: `local-ci-resplit_web_unit`.
- Prompt checks passed:
  - `Source status: dirty`
  - `Remote main head: def456`
  - `Dirty paths: 2`
  - `Preferred action: Codex Editor disposable-worktree patch lane`

This proof uses a controlled fixture instead of intentionally breaking a real FirstBite local-CI lane. It writes only a local handoff record under `~/.moussey/coding-handoffs` and does not mutate CI reports, source repos, Cleaner files, or cross-Mac state.

## Verification

- `node --test --import tsx app/api/coding/local-ci/handoff/route.test.ts lib/local-ci-status.test.ts app/api/coding/local-ci/route.test.ts` passed 12/12.
- `git diff --check -- app/coding/page.tsx app/api/coding/local-ci/handoff/route.ts app/api/coding/local-ci/handoff/route.test.ts lib/local-ci-status.ts app/api/coding/local-ci/route.ts app/api/coding/local-ci/route.test.ts lib/local-ci-status.test.ts` passed.
- `npx tsc --noEmit --pretty false` passed.
- `npm run build` passed with the known Turbopack NFT warning from `app/api/coding/local-ci/artifact/route.ts`.
- `launchctl kickstart -k gui/$UID/com.leokwan.moussey-server` restarted the rebuilt bundle.
- `curl -fsS http://127.0.0.1:4321/api/health` returned `ok:true`, `agent.backend:"off"`, and ready Codex/Claude/Hermes CLIs.
- `GET /api/coding/local-ci` still shows real CI clean: latest run `verify-resplit-web-origin-main-plus-token-fix-20260525`, `17/17` passing, `0` failing, `0` stale.
- Playwright opened the handoff URL on desktop `1440x1100` and mobile `390x1100`.
  - The top `Handoff` tile was fully in the first viewport on both.
  - The tile showed `Codex Editor default patch lane`, `local-ci-resplit_web_unit`, and `a26a14af`.
  - Clicking the tile exposed source-state context in Live Console.
  - Zero console/page errors.

## Screenshots

- `/tmp/moussey-c66-enabled-handoff-desktop.png`
- `/tmp/moussey-c66-enabled-handoff-mobile.png`

## Remaining Gap

The next MVP slice is to turn this staged handoff into a one-click bounded verifier/editor launch from the first viewport and show the resulting worker/run status there, without requiring the older lower handoff panel.
