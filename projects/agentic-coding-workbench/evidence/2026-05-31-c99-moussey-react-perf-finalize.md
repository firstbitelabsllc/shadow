# C99 Moussey React Perf Finalize

Parent plan: `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/PLAN.md`

Source: `/Users/leokwan/Development/vidux/projects/SESSION-HANDOFF-2026-05-31.md`

## Scope

- N6/N7: memoize `/coding` derived Action Shelf items, CI lane lookup, and CI lane count summary without changing the frozen Moussey product UI.
- N8/N9: memoize `/chat` fork routes and message bubbles so completed turns do not re-render on every unrelated stream chunk.
- N10: keep `/chat` stuck to the bottom only while the operator is already near the bottom, so reading older messages is not interrupted by streaming.
- N11: add in-flight guards to consignment visit/payment submit handlers so double-clicks or repeated submits cannot launch duplicate POSTs before React disables the button.

## Boundaries

- This is a perf/logic hardening slice only. It does not resume Moussey `/coding` product UI polish; Litty remains the future cockpit surface.
- No live purchase, external message, or destructive action is in scope.

## Changes

- `/Users/leokwan/Development/moussey/app/coding/page.tsx`
  - Memoized the manifest lane lookup map.
  - Collapsed CI lane repo/readiness/proof-only counts into one memoized summary.
  - Memoized `buildCiConsoleCommandItems(...)` with explicit dependencies.
- `/Users/leokwan/Development/moussey/app/chat/page.tsx`
  - Memoized fork routes.
  - Wrapped `MessageBubble` in `memo(...)` with a comparator keyed on turn identity, action state, route list, disabled/loading states, and handoff error text.
  - Replaced unconditional streaming scroll with a stick-to-bottom ref that only auto-scrolls while the operator is already near the bottom; new chats/session loads/new sends reset to bottom.
- `/Users/leokwan/Development/moussey/app/consignment/page.tsx`
  - Added in-flight submit refs for visit and payment saves before POST.
- `/Users/leokwan/Development/moussey/lib/coding-operating-resume.test.ts`
  - Updated the fixture to the current `LocalCiStatus` shape (`cockpitRuntime`, `diskInventory`) so repo-wide TypeScript can run.

## Verification

- PASS: `npx tsc --noEmit --pretty false`
  - First pass exposed stale generated `.next/dev/types`; cleared only the generated dev type cache.
  - Second pass exposed stale test fixture fields; fixture was updated.
- PASS: `npm run test:coding:contract`
  - 84/84 passing.
- PASS: `npm run test:snowcubes:invoice`
  - 27/27 passing.
- PASS: `npm run test:brain-dispatcher`
  - 272/272 passing.
- PASS: `git diff --check`
  - Checked Moussey touched files and this Vidux plan/evidence file.
- PASS: `npm run build`
  - Build completed.
  - Known warning persisted: local-CI artifact route Turbopack NFT trace warning from `app/api/coding/local-ci/artifact/route.ts`.
- PASS: `bash scripts/moussey-server.sh --restart`
  - Fresh server listening on `http://0.0.0.0:4321`.
- PASS: `curl -fsS http://127.0.0.1:4321/api/health`
  - `ok=true`, Codex/Hermes/Claude Code ready; uptime reset after restart.
- PASS: live `/api/coding/local-ci`
  - `ok=true`, `laneCatalog=43`, `latestLaneProof=43`, `recentRuns=12`.
- PASS: Playwright `/coding?fresh=c99-hydrated-wait`
  - Desktop: `laneRows=43`, `commandActions=6`, `proofOnlyText=true`, `bodyHasPipeline=true`, `overflowX=0`, no console/page errors.
  - Mobile 390px: `laneRows=43`, `commandActions=6`, `proofOnlyText=true`, `bodyHasPipeline=true`, `overflowX=0`, no console/page errors.
- PASS: Playwright `/chat?fresh=c99-react-perf`
  - Desktop/mobile loaded with heading, composer, empty-state message, and no console/page errors.
- PASS with caveat: Playwright `/consignment?fresh=c99-error-state`
  - Desktop/mobile hydrated to the safe error state with no console/page errors.
  - Caveat: this machine reports `{"ok":false,"available":false,"code":"data_unavailable"}` for `/api/consignment?view=all`, so live button-submit proof is not possible here without consignment CSV setup. Route and consignment tests cover the guarded save paths.

## Evidence

- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/evidence/2026-05-31-c99-chat-desktop.png`
- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/evidence/2026-05-31-c99-chat-mobile.png`
- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/evidence/2026-05-31-c99-coding-hydrated-desktop.png`
- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/evidence/2026-05-31-c99-coding-hydrated-mobile.png`
- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/evidence/2026-05-31-c99-consignment-desktop-hydrated.png`
- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/evidence/2026-05-31-c99-consignment-mobile-hydrated.png`

## Resume

- C99 is complete.
- Next aligned agent-doable work remains C98 Litty-CI standalone bootstrap or backend/control-plane contracts, not more Moussey `/coding` product UI polish.
