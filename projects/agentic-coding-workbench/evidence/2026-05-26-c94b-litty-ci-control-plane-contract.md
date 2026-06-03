# 2026-05-26 C94b Litty-CI Control-Plane Contract

## Direction

Leo redirected the product UI out of Moussey and into Litty-CI / coding-cockpit. Moussey stays the LAN/data/API hub. This slice intentionally does not polish `/coding`; it extracts a stable read-only control-plane payload that Litty-CI can render without scraping the old route.

## Shipped

- Added `lib/local-ci-control-plane.ts`.
- Added `GET /api/coding/control-plane`.
- Added focused tests in `lib/local-ci-control-plane.test.ts` and `app/api/coding/control-plane/route.test.ts`.
- Added the new contract tests to `test:coding:contract` and `test:brain-dispatcher`.

The endpoint returns:

- `schemaVersion: firstbite-local-ci-control-plane-v1`
- authority metadata for repo manifests and FirstBite MCP reports
- pipeline groups by repo
- lane spend boundaries (`local-no-spend`, `local-browser`, `local-simulator`, `external-live`, `model-spend`, `cloud-spend`, `unknown`)
- runner state, Xcode slot, M4 peer state, active reservations
- latest run, recent runs, artifacts/log paths, source proof, gates, blockers

## Live Proof

Command:

```bash
curl -fsS -m 20 http://127.0.0.1:4321/api/coding/control-plane | node -e 'let s="";process.stdin.on("data",d=>s+=d);process.stdin.on("end",()=>{const j=JSON.parse(s); console.log(JSON.stringify({schema:j.schemaVersion,ok:j.ok,lanes:j.totals.lanes,pipelines:j.pipelines.length,blockers:j.blockers.length,latestRun:j.latestRun?.runId,latestOverall:j.latestRun?.overall,localBrowser:j.spendBoundaries["local-browser"],modelSpend:j.spendBoundaries["model-spend"],externalLive:j.spendBoundaries["external-live"]},null,2));})'
```

Result:

```json
{
  "schema": "firstbite-local-ci-control-plane-v1",
  "ok": true,
  "lanes": 38,
  "pipelines": 5,
  "blockers": 7,
  "latestRun": "c95-control-plane-contract-moussey-unit-20260526",
  "latestOverall": "pass",
  "localBrowser": {
    "laneCount": 13,
    "lanes": [
      "moussey_coding_console",
      "moussey_ui",
      "resplit_web_integration",
      "resplit_web_ui",
      "strongyes_web_dsa_chat",
      "strongyes_web_dsa_code_execution",
      "strongyes_web_dsa_code_suggest",
      "strongyes_web_dsa_journey",
      "strongyes_web_dsa_mcp",
      "strongyes_web_dsa_part2",
      "strongyes_web_dsa_tabs",
      "strongyes_web_launch_guest",
      "strongyes_web_ui"
    ]
  },
  "modelSpend": {
    "laneCount": 0,
    "lanes": []
  },
  "externalLive": {
    "laneCount": 2,
    "lanes": [
      "resplit_currency_api_trust_preflight",
      "resplit_currency_api_ui"
    ]
  }
}
```

Health:

```bash
curl -fsS -m 5 http://127.0.0.1:4321/api/health
```

Returned `ok: true`, `agent.backend: off`, Codex/Hermes/Claude bins ready.

## Disposable Worktree Lane Proof

Command:

```bash
cd /Users/leokwan/Development/ai-leo/skills/resplit-watch/mcp/firstbite-local-ci
npm run --silent call -- run_lanes '{"mode":"execute","lanes":["moussey_unit"],"worktree":true,"run_id":"c95-control-plane-contract-moussey-unit-20260526"}'
```

Report:

```text
/Users/leokwan/.agent-ledger/firstbite-local-ci-mcp/c95-control-plane-contract-moussey-unit-20260526/report.json
```

Summary:

```json
{
  "run_id": "c95-control-plane-contract-moussey-unit-20260526",
  "overall": "pass",
  "lane": "moussey_unit",
  "status": "pass",
  "worktree": true,
  "cleanup_rc": 0,
  "cwd": "/tmp/firstbite-local-ci-mcp-c95-control-plane-contract-moussey-unit-20260526/moussey_unit",
  "dirty": 0
}
```

Boundary: this proves the repo-backed FirstBite disposable-worktree runner path. It does not prove the current dirty Moussey checkout's uncommitted route changes, so those remain covered by focused local tests and the live rebuilt API proof.

## Verification

```bash
node --test --import tsx lib/local-ci-control-plane.test.ts app/api/coding/control-plane/route.test.ts
npm run test:coding:contract
npm run test:brain-dispatcher
npx tsc --noEmit --pretty false
git diff --check -- lib/local-ci-control-plane.ts lib/local-ci-control-plane.test.ts app/api/coding/control-plane/route.ts app/api/coding/control-plane/route.test.ts package.json
scripts/moussey-server.sh --build && scripts/moussey-server.sh --restart
```

Results:

- Focused contract tests: 4/4 pass.
- Coding contract suite: 84/84 pass.
- Brain dispatcher suite: 228/228 pass.
- TypeScript: pass.
- Diff check: pass.
- Build/restart: pass, with the known Next NFT warning from `app/api/coding/local-ci/artifact/route.ts`.

## Resume Rule

Do not continue product UI work inside Moussey. Next aligned slices are:

- document the `firstbite-local-ci-control-plane-v1` schema for Litty-CI
- add a saved JSON fixture for local development
- add an API smoke in Litty-CI that reads `/api/coding/control-plane`
- keep Moussey focused on repo-manifest truth, runner APIs, logs, artifacts, and LAN routing
