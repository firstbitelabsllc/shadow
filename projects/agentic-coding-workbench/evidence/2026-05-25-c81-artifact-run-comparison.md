# C81 Artifact Run Comparison

## Result

Moussey `/coding` now promotes local-CI artifact metadata into the visible product surface instead of hiding it in raw console text. The latest FirstBite run inspector shows:

- `Run Comparison`: current run, latest passing baseline when available, and lane/source delta.
- `Artifact Inspector`: typed summary tabs returned by `CodingArtifactSummary` for local-CI reports/logs/patch-style artifacts.
- Explicit raw actions: `Raw` and `Primary` still expose the underlying report text without making raw paths the default UI.

This is product progress toward a Jenkins/Buildkite-style console: the user sees the run/artifact truth inline, while raw MCP envelopes remain available for debugging.

## Touched

- `/Users/leokwan/Development/moussey/app/coding/page.tsx`
- `/Users/leokwan/Development/moussey/lib/coding-operating-resume.test.ts`
- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/PLAN.md`
- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/evidence/2026-05-25-c81-artifact-run-comparison.png`

## Verification

```text
node --test --import tsx lib/coding-operating-resume.test.ts lib/coding-artifacts.test.ts app/api/coding/local-ci/run/route.test.ts app/api/coding/workers/route.test.ts app/api/coding/lanes/run/route.test.ts lib/coding-workbench.test.ts lib/local-ci-status.test.ts app/api/coding/local-ci/route.test.ts
# pass 68/68

npx tsc --noEmit --pretty false
# pass

npm run build
# pass, with known Turbopack NFT warning traced through app/api/coding/local-ci/artifact/route.ts
```

Production browser proof:

```text
http://127.0.0.1:4324/coding?fresh=c81-artifact-run-comparison-fixed

Found:
- RUN COMPARISON
- Latest Passing
- Delta
- ARTIFACT INSPECTOR
- Overview
- Raw JSON
- Latest FirstBite Run
```

Screenshot:

```text
projects/agentic-coding-workbench/evidence/2026-05-25-c81-artifact-run-comparison.png
```

## Remaining

- The page still needs a first-class stop/cancel policy for owned workers and local-CI reservations.
- Source-ref, fresh-main, and remote-main comparison exists in backend/source proof data but still needs a sharper visual product treatment.
- Run history still shows too much raw operational detail by default.
