# C85 Local-CI Control Surface

## Scope

- FirstBite local-CI cancellation and resume are now visible in Moussey `/coding`, not only available through the MCP/API substrate.
- The `STOP / CANCEL` card now switches to `Cancel CI` when the loaded FirstBite catalog and active reservation advertise scoped MCP cancellation.
- The latest FirstBite run inspector now exposes `Resume Dry` and `Resume Run` when the loaded catalog advertises `resume_run:true`.
- Control copy names the safety boundary: local-CI cancellation writes a cancel request and signals only the MCP-owned active lane process group; resume creates a new report instead of mutating the original run.

## Files Changed

- `/Users/leokwan/Development/moussey/app/coding/page.tsx`
- `/Users/leokwan/Development/moussey/lib/local-ci-status.ts`
- `/Users/leokwan/Development/moussey/app/api/coding/local-ci/cancel/route.ts`
- `/Users/leokwan/Development/moussey/app/api/coding/local-ci/cancel/route.test.ts`
- `/Users/leokwan/Development/moussey/app/api/coding/local-ci/resume/route.ts`
- `/Users/leokwan/Development/moussey/app/api/coding/local-ci/resume/route.test.ts`
- `/Users/leokwan/Development/ai-leo/skills/resplit-watch/mcp/firstbite-local-ci/src/server.mjs`
- `/Users/leokwan/Development/ai-leo/skills/resplit-watch/mcp/firstbite-local-ci/README.md`
- `/Users/leokwan/Development/ai-leo/skills/local-ci/SKILL.md`

## Proof

- FirstBite MCP lint passed: `npm run lint` in `/Users/leokwan/Development/ai-leo/skills/resplit-watch/mcp/firstbite-local-ci`.
- FirstBite MCP cancel smoke passed with a temp run root: `cancelDisposition:"cancel_signal_sent"`, `overall:"canceled"`, lane `status:"canceled"`, and reason `canceled: cancel smoke`.
- FirstBite MCP catalog proof showed control capabilities: `cancel_run:true`, `resume_run:true`, and fresh-report resume semantics.
- Moussey focused tests passed `39/39`:
  - `node --test --import tsx app/api/coding/local-ci/cancel/route.test.ts app/api/coding/local-ci/resume/route.test.ts app/api/coding/local-ci/run/route.test.ts lib/local-ci-status.test.ts`
- Moussey TypeScript passed: `npx tsc --noEmit --pretty false`.
- Moussey production build passed: `npm run build`, with the known Turbopack/NFT warning from the local-CI artifact route.
- Production Playwright desktop proof passed at `http://127.0.0.1:4324/coding?fresh=c85-desktop-rerun` with no console/page errors, no horizontal overflow (`1440/1440`), and visible `STOP / CANCEL`, `Resume Dry`, `Resume Run`, `SOURCE PROOF DECISION`, and local-CI cancel readiness markers.
- Production Playwright mobile proof passed at `http://127.0.0.1:4324/coding?fresh=c85-mobile-rerun` with no console/page errors and no horizontal overflow (`390/390`).
- Policy click proof passed at `http://127.0.0.1:4324/coding?fresh=c85-policy-click`; clicking `Policy` surfaced `cancel_run`, resume policy text, and the read-only refresh boundary.

## Screenshots

- `projects/agentic-coding-workbench/evidence/2026-05-25-c85-local-ci-control-desktop-rerun.png`
- `projects/agentic-coding-workbench/evidence/2026-05-25-c85-local-ci-control-mobile-rerun.png`
- `projects/agentic-coding-workbench/evidence/2026-05-25-c85-local-ci-control-policy.png`

## Remaining

- C85 proves scoped cancel/resume substrate plus visible controls. It did not cancel a real production FirstBite lane; the live process-signal proof used a synthetic MCP-owned run.
- The next UX gap is the disabled-state explanation audit: blocked controls should say why, while safe read-only refresh/inspect/report actions should remain available during foreground streams.
- The completed-run model still needs refinement so terminal runs, resumable runs, active reservations, and replay-only proofs read like one coherent CI pipeline.
