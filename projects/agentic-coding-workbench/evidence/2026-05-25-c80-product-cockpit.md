# C80 Product Cockpit Slice

## Summary

C80 started the `/coding` internal-tool makeover after C79 proved the Resplit Web promoted source ref could pass the three FirstBite local-CI lanes. This is a UX/product slice, not a new CI authority: FirstBite MCP reports remain the source of lane truth.

The first viewport now moves toward a Jenkins/Buildkite/GCP-style operator console:

- dark left navigation with anchors for Overview, Pipeline, Runners, Queue, Artifacts, Agents, and Console
- `System Overview` block that frames the surface as FirstBite Local CI
- `Recommended Action` deck with one dominant next step
- source/runner/artifact/spend fact panel
- demoted `Action Shelf` for secondary controls
- Source Patch -> Replay -> Promote -> Source CI stage strip
- Runner Recovery cards for stale MCP clients, Xcode slot contention, browser runtimes, and local KV

## Local CI Truth

C79 remains the hard CI proof:

- promoted source ref: `codex/web-promote-reviewed-patch-current-main-20260525T184547Z-tuug6r`
- promoted commit: `65f654f0fbc39ddbdb7e373603ed291d0af3bcd9`
- aggregate MCP run: `/Users/leokwan/.agent-ledger/firstbite-local-ci-mcp/mcp-20260525T185412Z-89241/report.json`
- result: `resplit_web_unit`, `resplit_web_integration`, and `resplit_web_ui` all passed from disposable worktrees

C80 records the dependency lesson in the UI: Playwright browser revisions are branch/source-ref specific enough to install from the executing worktree when missing. It also answers Leo's Docker/KV question directly: current Resplit Web local KV E2E uses the in-process local KV driver and does not need Docker; Docker/Redis remains optional future parity work.

## Verification

Moussey verification:

```text
node --test --import tsx app/api/coding/lanes/run/route.test.ts lib/coding-workbench.test.ts app/api/coding/local-ci/run/route.test.ts
```

Result: 30/30 passing.

```text
npx tsc --noEmit --pretty false
```

Result: passed.

```text
npm run build
```

Result: passed with the known Turbopack NFT warning in `next.config.ts` from the local-CI artifact route import trace.

```text
git diff --check -- app/coding/page.tsx
```

Result: passed.

Vidux verification:

```text
git diff --check -- projects/agentic-coding-workbench/PLAN.md projects/agentic-coding-workbench/evidence/2026-05-25-c80-product-cockpit.md
```

Result: passed after the C80 plan/evidence updates.

Browser verification:

- desktop: `http://127.0.0.1:4322/coding`, viewport `1440x1100`, no horizontal overflow (`1440/1440`)
- mobile: `http://127.0.0.1:4322/coding`, viewport `390x900`, no horizontal overflow (`390/390`)
- required copy present: `Coding operations console`, `RECOMMENDED ACTION`, `SYSTEM OVERVIEW`, `Pipeline`, `RUNNER RECOVERY`, `No Docker needed`, `BROWSER RUNTIMES`, `ACTION SHELF`
- no serious console messages after filtering React DevTools, HMR, and Fast Refresh noise

Screenshots:

- `projects/agentic-coding-workbench/evidence/2026-05-25-c80-product-cockpit-desktop.png`
- `projects/agentic-coding-workbench/evidence/2026-05-25-c80-product-cockpit-mobile.png`

## Remaining Work

C80 is still in progress. This slice addressed or started UX-01, UX-02, UX-06, UX-08, UX-09, UX-10, UX-16, UX-17, and UX-22. The next product slice should make runner/dependency readiness live data, make the pipeline stages clickable, and turn disabled controls/errors into first-class recovery paths.
