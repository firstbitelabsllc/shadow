# C67 First-Viewport Handoff Launch Proof

Date: 2026-05-25

## Surface

- Local URL: `http://127.0.0.1:4321/coding?handoff=a26a14af-4d1c-409f-975b-6fd8cfadcf6a&fresh=c67-first-viewport-launch`
- Handoff id: `a26a14af-4d1c-409f-975b-6fd8cfadcf6a`
- Proposed action: `codex-editor`
- Label: `local-ci-resplit_web_unit`

## Change

The first-viewport `Handoff` card now launches the staged handoff instead of only inspecting it.

- `codex-editor`, `codex-verifier`, `local-smoke`, `aider-editor`, and `lane-status` map to the existing bounded lane runner.
- `lane-preflight` maps to the existing preflight runner.
- The Live Console keeps a source preface with handoff id, source, label, recommended action, source run, and full source prompt before streamed lane output starts.
- The first viewport reflects the launched handoff state (`running`, `last run green`, or `needs review`) without requiring the lower handoff panel.

## Verification

- `npx tsc --noEmit --pretty false` passed.
- `node --test --import tsx app/api/coding/local-ci/handoff/route.test.ts lib/coding-handoffs.test.ts app/api/coding/lanes/run/route.test.ts` passed 21/21.
- `npm run test:brain-dispatcher` passed 182/182.
- `git diff --check -- app/coding/page.tsx` passed.
- `npm run build` passed with the known `app/api/coding/local-ci/artifact/route.ts` Turbopack NFT warning.
- `launchctl kickstart -k gui/$UID/com.leokwan.moussey-server` restored `http://127.0.0.1:4321/api/health` with `ok:true`.
- `http://127.0.0.1:7191/api/health` returned `ok:true`.
- `/Users/leokwan/Development/moussey/scripts/moussey-trigger-doctor --brief` returned `launchagent=ok listener=ok endpoint=accepting secret=ok`.
- Playwright intercepted the actual `POST /api/coding/lanes/run` request from the first-viewport Handoff tile on desktop and mobile to avoid spending a real Codex editor run during UI verification. Both requests sent:
  - `jobId: "resplit-web-autobot"`
  - `mode: "codex-editor"`
  - `label: "local-ci-resplit_web_unit"`
  - `handoffId: "a26a14af-4d1c-409f-975b-6fd8cfadcf6a"`

## Screenshots

- Desktop before launch: `/tmp/moussey-c67-desktop-before.png`
- Desktop after intercepted launch: `/tmp/moussey-c67-desktop-after.png`
- Mobile before launch: `/tmp/moussey-c67-mobile-before.png`
- Mobile after intercepted launch: `/tmp/moussey-c67-mobile-after.png`

## Boundary

The UI launch path is proven without cloud/token spend. The next proof gap is a real handoff-fired editor/verifier run whose resulting status, patch/verifier artifact, and before/after proof are summarized in the first viewport without relying on the lower handoff panel.
