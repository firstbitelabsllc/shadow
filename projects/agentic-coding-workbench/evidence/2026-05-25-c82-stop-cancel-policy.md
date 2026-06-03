# C82 Stop/Cancel Policy

## Result

Moussey `/coding` now makes queue control explicit instead of leaving long-running work as an invisible lock. The queue strip has a `STOP / CANCEL` card with:

- The current detached-worker stop state.
- A visible `Policy` action that explains what can and cannot be stopped safely.
- A bounded `Stop` action for the first visible running detached Moussey worker.

The backend now exposes `PATCH /api/coding/workers/:workerId` with `{ "action": "stop" }`. It only acts on known detached worker metadata, refuses unsafe server-process kills, marks missing/stale workers failed with stop metadata, sends `SIGTERM` to the owned process group when safe, and records the stop in both worker metadata and coding run history. FirstBite local-CI MCP reservations remain inspect/status only until the MCP has a scoped cancel primitive.

## Touched

- `/Users/leokwan/Development/moussey/lib/coding-workers.ts`
- `/Users/leokwan/Development/moussey/app/api/coding/workers/[workerId]/route.ts`
- `/Users/leokwan/Development/moussey/app/api/coding/workers/route.test.ts`
- `/Users/leokwan/Development/moussey/app/coding/page.tsx`
- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/PLAN.md`
- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/evidence/2026-05-25-c82-stop-cancel-policy.png`

## Verification

```text
node --test --import tsx app/api/coding/workers/route.test.ts
# pass 9/9

node --test --import tsx lib/coding-operating-resume.test.ts lib/coding-artifacts.test.ts app/api/coding/local-ci/run/route.test.ts app/api/coding/workers/route.test.ts app/api/coding/lanes/run/route.test.ts lib/coding-workbench.test.ts lib/local-ci-status.test.ts app/api/coding/local-ci/route.test.ts
# pass 71/71

npx tsc --noEmit --pretty false
# pass

npm run build
# pass, with known Turbopack NFT warning traced through app/api/coding/local-ci/artifact/route.ts

git diff --check -- app/coding/page.tsx lib/coding-workers.ts app/api/coding/workers/[workerId]/route.ts app/api/coding/workers/route.test.ts lib/coding-operating-resume.test.ts
# pass
```

Production browser proof:

```text
http://127.0.0.1:4324/coding?fresh=c82-stop-cancel

Found:
- STOP / CANCEL
- Policy
- No Stop
- Stop policy:
- Detached Moussey workers
- FirstBite local-CI MCP reservations
```

Screenshot:

```text
projects/agentic-coding-workbench/evidence/2026-05-25-c82-stop-cancel-policy.png
```

## Remaining

- Add a real local-CI MCP cancel/resume primitive before exposing stop controls for FirstBite MCP reservations.
- Render source-proof comparison as a first-class product panel so branch/source-ref proof cannot read like fresh-main portability.
- Redact raw run-history args/prompts by default while keeping explicit detail inspection.
