# C85 FirstBite MCP Cancel/Resume

## Scope

- FirstBite local-CI MCP now exposes `cancel_run` and `resume_run`.
- Moussey now exposes `POST /api/coding/local-ci/resume`, guarded by the loaded MCP catalog capability `control_capabilities.resume_run === true`.
- No `/Users/leokwan/Development/moussey/app/coding/page.tsx` edits in this slice; the UX agent still owns the first-viewport/admin-console work.

## Files Changed

- `/Users/leokwan/Development/ai-leo/skills/resplit-watch/mcp/firstbite-local-ci/src/server.mjs`
- `/Users/leokwan/Development/ai-leo/skills/resplit-watch/mcp/firstbite-local-ci/README.md`
- `/Users/leokwan/Development/ai-leo/skills/local-ci/SKILL.md`
- `/Users/leokwan/Development/moussey/lib/local-ci-status.ts`
- `/Users/leokwan/Development/moussey/app/api/coding/local-ci/resume/route.ts`
- `/Users/leokwan/Development/moussey/app/api/coding/local-ci/resume/route.test.ts`

## Behavior

- `cancel_run` writes a durable cancel request and control file before signaling.
- Signal delivery is scoped to an MCP-owned active lane process group on the current host. It validates `run_id`, lane key, host, process group ownership, safe child pid, and log path under the run directory before sending a signal.
- Canceled lanes report `status:"canceled"`, `rc:130`, and `exit_classification:"operator_canceled"`. Reports can now finish as `overall:"canceled"`.
- `resume_run` rejects active originals, creates a new run id/report, resumes lanes whose latest result is not `pass` or `warn`, and stores `resumed_from` plus `resume_policy`.
- Moussey delegates resume to the MCP wrapper only after `/api/coding/local-ci` sees `resume_run:true`; the browser does not reconstruct shell commands.

## Proof

- FirstBite MCP lint: `npm run lint` passed in `/Users/leokwan/Development/ai-leo/skills/resplit-watch/mcp/firstbite-local-ci`.
- Moussey focused tests: `node --test --import tsx app/api/coding/local-ci/cancel/route.test.ts app/api/coding/local-ci/resume/route.test.ts app/api/coding/local-ci/run/route.test.ts lib/local-ci-status.test.ts` passed `39/39`.
- Moussey TypeScript: `npx tsc --noEmit --pretty false` passed.
- MCP probe: `npm run probe` passed; the tool list now includes `list_lanes`, `status`, `cancel_run`, `resume_run`, and `run_lanes`.
- Cancel smoke: run `c85-cancel-live-20260525T2045` was canceled through `cancel_run` with disposition `cancel_signal_sent`; report became `overall:"canceled"`, lane `moussey_unit` became `status:"canceled"`, `rc:130`.
- MCP resume smoke: `resume_run` created `c85-resume-dry-20260525T2046` with `disposition:"resumed"`, resumed lane `moussey_unit`, `overall:"planned"`, and `resumed_from:"c85-cancel-live-20260525T2045"`.
- Moussey build: `npm run build` passed with the known Next/Turbopack NFT warning from the local-CI artifact route.
- Moussey restart: `bash scripts/moussey-server.sh --restart` restored `http://127.0.0.1:4321`.
- Live capability proof: `GET http://127.0.0.1:4321/api/coding/local-ci` returned lane count `23`, `control_capabilities.cancel_run:true`, `control_capabilities.resume_run:true`, and a resume rule.
- Live resume API proof: `POST http://127.0.0.1:4321/api/coding/local-ci/resume` created `c85-resume-api-dry-20260525T2047` with `disposition:"resumed"`, `overall:"planned"`, and `resumed_from:"c85-cancel-live-20260525T2045"`.
- Targeted diff checks passed for the touched FirstBite MCP and Moussey files.

## Remaining

- `/coding` still needs visible completed-run resume affordances that are driven by `resume_run:true` and terminal non-passing reports.
- The disabled-state explanation audit remains open: safe read-only actions should stay usable during foreground streams, and blocked actions should explain why.
- The live `activeRunCount:1` observed after restart is not a C85 failure; it reflects current fleet/run state and should stay visible in the queue model rather than being hidden.
