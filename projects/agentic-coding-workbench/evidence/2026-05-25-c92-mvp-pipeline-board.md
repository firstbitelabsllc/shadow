# C92 MVP Pipeline Board

## Summary

Leo stopped the 30-hour expansion loop and asked for an MVP boundary. This slice moves `/coding` toward that finish line by making the first pipeline surface read like a CI product instead of a hardcoded launcher wall.

Moussey now renders a manifest/report-backed `Pipelines` board near the top of `/coding`:

- rows are built by `buildCiConsolePipelineLaneRows(...)` from repo-owned `.firstbite/local-ci.json` lane catalog data, selected FirstBite run lane data, and latest lane proof
- each row shows lane, repo, kind, status, source state/head, runner, artifact/log state, manifest/proof-only tags, and scoped Inspect/Report/Run actions
- the patch replay stage line is subordinate to lane truth instead of occupying the main `#pipeline` anchor
- long lane ids wrap on mobile instead of causing horizontal overflow

This does not claim all post-MVP UX is done. It closes the most visible MVP confusion: the operator now sees a CI lane board before lower-detail launcher cards and model/debug substrate.

## Verification

Commands:

```bash
node --test --import tsx lib/coding-console-model.test.ts
npx tsc --noEmit --pretty false
scripts/moussey-server.sh --build
scripts/moussey-server.sh --restart
```

Results:

- `lib/coding-console-model.test.ts`: 25/25 passing
- TypeScript: passed
- `scripts/moussey-server.sh --build`: passed with the known Next/Turbopack NFT warning for `app/api/coding/local-ci/artifact/route.ts`
- LaunchAgent restart: `kicked. listening on http://0.0.0.0:4321.`
- Playwright hydrated proof at `http://127.0.0.1:4321/coding?fresh=c92-mvp-pipeline-board-final-3`
  - desktop: `rowCount=38`, `buttonCount=114`, `consoleErrors=[]`, `rootOverflowX=0`, `bodyOverflowX=0`
  - mobile: `rowCount=38`, `buttonCount=114`, `consoleErrors=[]`, `rootOverflowX=0`, `bodyOverflowX=0`

Screenshots:

- `projects/agentic-coding-workbench/evidence/2026-05-25-c92-mvp-pipeline-board-desktop.png`
- `projects/agentic-coding-workbench/evidence/2026-05-25-c92-mvp-pipeline-board-mobile.png`

## MVP Boundary

This is MVP convergence, not a new expansion phase. The remaining work belongs post-MVP unless it blocks comprehension of the current console:

- route-wide button/action audit beyond the highest-risk controls
- unified lifecycle vocabulary across every run source
- persistent selected-object inspector
- mobile bottom action/section switcher
- denser filterable CI tables for repeated lanes/runs/workers
