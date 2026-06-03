# C93 Pipeline Spend Boundaries

Date: 2026-05-26

## Scope

Moussey `/coding` already had a manifest-backed CI lane board, but the lane rows still did not clearly answer the operator question Leo keeps asking: what is local/no-spend, what touches live/cloud services, what would spend model tokens, and what blocks clean trust.

This slice adds typed spend/boundary and blocker semantics to the pipeline row model, then renders them in the first-viewport `#pipeline` board.

## Code

- `/Users/leokwan/Development/moussey/lib/coding-console-model.ts`
  - Added `CiConsolePipelineSpendBoundaryKind`.
  - Added row fields: `spendBoundaryKind`, `spendBoundaryLabel`, `spendBoundaryDetail`, `spendBoundaryReadiness`, `riskCostClass`, and `blockerSummary`.
  - Classifies local no-spend, local browser, local services, local simulator, external/live, model-spend, and unknown lane boundaries from repo manifest command/note metadata.
  - Avoids false model-spend alarms for negated manifest notes such as "avoids Codex cloud auth".
- `/Users/leokwan/Development/moussey/app/coding/page.tsx`
  - Shows pipeline summary counts for local/no-spend, external/live, model-spend, and blockers.
  - Adds a `Boundary` cell to each CI lane row.
  - Adds data attributes for browser-proofed row semantics:
    - `data-ci-pipeline-spend-boundary`
    - `data-ci-pipeline-spend-label`
    - `data-ci-pipeline-risk`
    - `data-ci-pipeline-blocker`
  - Uses row risk/cost metadata for `Run` action audit attributes.
- `/Users/leokwan/Development/moussey/lib/coding-console-model.test.ts`
  - Covers local no-spend, local simulator, local browser, external/live, dirty-source blockers, and negated model/cloud mentions.

## Mechanical Proof

Commands run from `/Users/leokwan/Development/moussey`:

```bash
node --test --import tsx lib/coding-console-model.test.ts
npx tsc --noEmit --pretty false
git diff --check -- app/coding/page.tsx lib/coding-console-model.ts lib/coding-console-model.test.ts
scripts/moussey-server.sh --build
scripts/moussey-server.sh --restart
```

Results:

- Focused console-model tests: 25/25 passed.
- TypeScript: passed.
- Scoped diff check: passed.
- Build: passed with the known `app/api/coding/local-ci/artifact/route.ts` NFT warning.
- Restart: `kicked. listening on http://0.0.0.0:4321.`

## Real Lane Proof

Executed a real FirstBite local-CI lane from a disposable worktree:

```json
{
  "run_id": "c93-spend-boundary-moussey-unit-20260526",
  "lane": "moussey_unit",
  "mode": "execute",
  "source_ref": "HEAD",
  "worktree": true,
  "overall": "pass",
  "status": "pass",
  "report_path": "/Users/leokwan/.agent-ledger/firstbite-local-ci-mcp/c93-spend-boundary-moussey-unit-20260526/report.json",
  "log_path": "/Users/leokwan/.agent-ledger/firstbite-local-ci-mcp/c93-spend-boundary-moussey-unit-20260526/moussey_unit/run.log",
  "execution_sync_status": "not_origin_main",
  "execution_dirty_count": 0,
  "cleanup_rc": 0
}
```

Meaning: the lane runner proof is green and disposable-worktree clean, but the tested source is `HEAD` behind current `origin/main`, so `/coding` correctly labels it as not fresh-main portable instead of overclaiming.

## Browser Proof

URL:

```text
http://127.0.0.1:4321/coding?fresh=c93-spend-boundary-after-lane-proof
```

Screenshots:

- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/evidence/2026-05-26-c93-spend-boundary-desktop.png`
- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/evidence/2026-05-26-c93-spend-boundary-mobile.png`

Playwright assertions after the real lane proof:

```json
{
  "rowCount": 39,
  "boundaryCounts": {
    "local-no-spend": 7,
    "local-browser": 5,
    "external-live": 3,
    "local-simulator": 16,
    "local-service-stack": 8
  },
  "riskCounts": {
    "local-only": 36,
    "external": 3
  },
  "blockerCount": 33,
  "reportButtons": 39,
  "runButtons": 39,
  "inspectButtons": 39,
  "hasLocalNoSpendCopy": true,
  "hasExternalLiveCopy": true,
  "hasModelSpendCopy": true,
  "hasBoundaryColumn": true,
  "hasBlockerCopy": true,
  "mousseyUnit": {
    "boundary": "local-no-spend",
    "risk": "local-only",
    "blocker": "passing proof is not fresh-main portable",
    "runId": "c93-spend-boundary-moussey-unit-20260526",
    "proof": "source-ref proof only; not fresh-main portable"
  },
  "fxUi": {
    "boundary": "external-live",
    "risk": "external",
    "blocker": "passing proof is not fresh-main portable",
    "runId": "verify-fx-trust-preflight-branch-20260526T0441",
    "proof": "source-ref proof only; not fresh-main portable"
  },
  "consoleErrors": [],
  "rootOverflowX": 0,
  "bodyOverflowX": 0
}
```

The row count is 39 because the UI includes one proof-only lane from latest proof in addition to the 38 repo-declared manifest lanes.

## Remaining Gaps

- Route-wide cost/risk grammar is still not complete. This slice covers the CI pipeline lane board, not every action in the route.
- Model-spend rows are supported by the model and UI copy, but the current manifest-backed lane catalog has no true model-spend lane after the negation fix.
- C94 selected-object inspector remains the next useful product gap if the goal is to make rows clickable like Jenkins/Buildkite run detail objects.
