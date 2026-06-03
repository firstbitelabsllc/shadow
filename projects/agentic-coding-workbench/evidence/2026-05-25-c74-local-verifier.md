# C74 Local Handoff Verifier

Date: 2026-05-25
Surface: Moussey `/coding`

## Goal

Prove the real C72 Resplit Web mission handoff can fire a bounded, non-intercepted verifier cycle from the first viewport without Codex, Aider, HF, or cloud-model spend.

## UI

- Local console: `http://127.0.0.1:4321/coding?handoff=223131fe-cc49-4b23-a923-0e56d734d610&fresh=c74-local-verifier`
- Run history API: `http://127.0.0.1:4321/api/coding/runs?limit=5`
- Handoff API: `http://127.0.0.1:4321/api/coding/handoffs/223131fe-cc49-4b23-a923-0e56d734d610`
- Desktop proof: `projects/agentic-coding-workbench/evidence/2026-05-25-c74-local-verifier-desktop.png`
- Mobile proof: `projects/agentic-coding-workbench/evidence/2026-05-25-c74-local-verifier-mobile.png`

## Implementation

- Added a first-viewport `Local Verifier` command button beside `Mission Action`.
- When a handoff is loaded, `Local Verifier` launches the existing `local-smoke` lane with the handoff id and a no-spend preface.
- When no handoff is loaded but a failed/stale lane exists, the same button stages the handoff first.
- The existing `Agent Result` and `Handoff Result` cards reconnect from run history by `handoffId`, so a refreshed handoff URL shows the latest handoff-fired result in the operator viewport.

## Verification

Moussey checks:

```text
git diff --check -- app/coding/page.tsx
npm run build
launchctl kickstart -k gui/$UID/com.leokwan.moussey-server
curl -fsS --max-time 5 http://127.0.0.1:4321/api/health
```

Result: build passed with the known local-CI artifact Turbopack NFT warning; live health returned `ok:true`.

Real handoff verifier command:

```text
curl -N -X POST \
  -H 'Content-Type: application/json' \
  -d '{"jobId":"resplit-web-autobot","mode":"local-smoke","label":"local-ci-resplit_web_integration","handoffId":"223131fe-cc49-4b23-a923-0e56d734d610"}' \
  http://127.0.0.1:4321/api/coding/lanes/run
```

Run result:

```text
runId: f28f9490-05ca-42c7-ba46-14d6890fbc3a
handoffId: 223131fe-cc49-4b23-a923-0e56d734d610
mode: local-smoke
laneRunKind: local-server-smoke
baseRef: origin/main
worktree: /Users/leokwan/Development/resplit-web-worktrees/web-local-ci-resplit-web-integration-20260525T071752Z-rb6k9d
port: 3110
durationMs: 63771
exitCode: 1
teardownOk: true
```

Target result:

```text
Next build: passed
Next start: http://127.0.0.1:3110 ready
Playwright: 4 passed, 1 failed
Failure: e2e/landing-smoke.spec.ts expects #globe, but section #globe is not found on origin/main landing page.
```

Browser proof:

```text
desktop viewport: 1440x1050, scrollWidth 1440, console errors 0, page errors 0
mobile viewport: 390x1050, scrollWidth 390, console errors 0, page errors 0
visible result: exit 1, run f28f9490, no model call boundary
```

## Verdict

C74 proves the no-spend handoff cycle is real: a staged Resplit Web handoff can launch a disposable-worktree verifier from Moussey, record `handoffId` in run history, show the result in the first viewport, and clean up worktree/branch/server/port state.

This does not make Resplit Web green. The current verifier failure is a product/test truth gap: `#globe` is still expected by `e2e/landing-smoke.spec.ts` on `origin/main`.

## Next

Use the now-visible handoff result to choose the next bounded action:

- If the `#globe` expectation is stale, run `Codex Editor` in a disposable worktree and save a patch that updates the test or restores the anchor.
- If the globe section should return before launch, patch the landing page instead and rerun the same verifier.
- Keep Aider/Gemma/Qwen as experimental until a local-model lane produces changed source plus passing postcheck.
