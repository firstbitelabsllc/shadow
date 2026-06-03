# Resplit Web Autobot / Local-CI Lane Specialist Report

## Goal

Connect the Moussey `/coding` MVP to Leo's #1 coding proof path: run and support `autobot-resplit-web` plus repo-declared local CI/test frameworks from the local command center.

## What already exists

### `/autobot-resplit-web` proof path

The Resplit Web skill defines the operational contract:

- `~/bin/autobot-resplit-web --public-only` is the auth-free deterministic public matrix. It covers the public surface and `/api/health` GET/HEAD, but does not prove authenticated chaos, seeded sessions, Sentry, staging, CI, FX archive coverage, or iOS/TestFlight entitlement gates.
- Parallel coding agents must use disposable `resplit-web` worktrees, isolated `PW_PORT` values in `3110..3119`, per-worktree `.next`, and mandatory teardown.
- Local server smoke should build/start/test inside the worktree and point Playwright at that lane's `PW_BASE_URL`, never the primary checkout or another agent's port.

Moussey already implements this shape in `lib/coding-lanes.ts`:

- `status`, `dry-run`, and `public` resolve to the base `resplit-web-autobot` harness in a disposable lane.
- `local-smoke` creates a worktree, installs deps or optionally links primary `node_modules`, builds, starts `next start` on the claimed port, runs `e2e/landing-smoke.spec.ts`, stops the server, removes the worktree, deletes the scratch branch, and releases the port lock.
- `codex-skills-probe` runs read-only Codex in the worktree with `/vidux`, `/pilot-leo`, `/captain`, `/nia`, and `/autobot-resplit-web` loaded.
- `codex-capability-probe` runs read-only Codex with live web search enabled, bounded stream output, and `--output-last-message`.
- `codex-verifier` prepares the same local server and delegates a bounded verifier agent to run the exact Playwright smoke and report next action without tracked source edits.
- `codex-editor` is the edit-gated lane: it may patch only the disposable worktree, then runs `git diff --check`, saves `git diff --binary` to `~/.moussey/coding-patches/<run>.patch`, and tears everything down.

### FirstBite local-CI proof path

The local-CI skill defines the product boundary:

- Repo `.firstbite/local-ci.json` files are the lane authority.
- The FirstBite local-CI MCP is the executor/evidence writer, not the product source of truth.
- `list_lanes`, `run_lanes`, and `status` are the control plane.
- The MVP should keep local CI proof local and treat Cursor, GitHub Actions, Buildkite, Slack, and peer machines as wrappers or secondary surfaces until they have their own evidence.

Moussey already implements the bridge:

- `GET /api/coding/local-ci` reads FirstBite MCP `status` and `list_lanes`, normalizes `latest_lane_proof`, `laneCatalog`, `laneGroups`, `repoSourceState`, peer proof, Cursor/Graphite review proof, and M4 fresh-clone packets.
- `POST /api/coding/local-ci/run` runs FirstBite MCP `run_lanes` with exactly one selector: `group`, explicit `lanes`, or `repo` + `kind`. Default mode is `dry_run`; `execute` is explicit.
- The `/coding` page calls `/api/coding/local-ci/run` for lane cards and the `critical_fast` group.
- `GET /api/coding/local-ci/artifact?path=...` reads bounded artifacts from the FirstBite run root, Cursor review root, or M4 fresh-clone packet root.
- `POST /api/coding/local-ci/handoff` turns a FirstBite lane result into a bounded Moussey verifier/editor handoff.

Resplit Web's repo manifest currently declares:

- `resplit_web_unit`: `npm ci && npm run test:run`
- `resplit_web_integration`: `npm ci && npm run lint && npm run test:e2e:live-local`
- `resplit_web_ui`: `npm ci && npm run autobot:web`

## MVP-ready lane

The MVP-ready path is not arbitrary IDE execution. It is:

1. Open `http://127.0.0.1:4321/coding`.
2. Check `GET http://127.0.0.1:4321/api/coding/local-ci` for current local-CI proof, source state, Xcode contention, report/log paths, and repo lane status.
3. Run `critical_fast` as a dry-run or selected Resplit Web lane through `POST /api/coding/local-ci/run`.
4. For Resplit Web public proof, run either:
   - the `/coding` `Run Resplit Autobot` / `Public Matrix` action, or
   - the lane route with `mode: "public"` against `POST http://127.0.0.1:4321/api/coding/lanes/run`.
5. For local browser proof, run `mode: "local-smoke"` through `POST /api/coding/lanes/run`.
6. If a lane fails, inspect the report/log/terminal summary first, then stage a verifier handoff. Only use `codex-editor` after the failing proof is selected and the worktree patch boundary is visible.

This is enough to support Leo's #1 proof path because it connects:

- Resplit Web public matrix and local Playwright smoke.
- FirstBite repo-manifest local CI.
- Evidence artifacts and recent run history.
- Bounded Codex verifier/editor lanes.
- Disposable worktree, port, and teardown safety.

## What is not MVP-ready yet

The system is close, but it is not yet a Claude Code/Codex-like IDE for arbitrary work because:

- There is no single "Resplit Web proof ladder" that visually sequences Public Matrix -> Local Smoke -> FirstBite `resplit_web_ui` -> Verifier -> Editor Patch.
- Local-CI lanes and `/autobot-resplit-web` modes appear as separate surfaces. The operator still has to know which button maps to which proof tier.
- The UI has many generic verbs: `Run`, `Dry`, `Public Matrix`, `Run Action`, `Detached`, `Run Local Smoke`, `Codex Verifier`, `Codex Editor`. MVP needs a smaller Resplit-specific command set.
- Source state is present in local-CI status types, but the operator path should make fresh-main/local-branch/dirty proof unavoidable before a green claim.
- The local-CI run path returns JSON after MCP completion; it does not stream lane output like `/api/coding/lanes/run`. That is fine for MVP if artifact links are first-class, but it is not IDE-like yet.
- Edit authority is correctly gated, but the promotion path from saved patch to primary checkout/PR is intentionally missing. Keep it missing for MVP; call it a later apply/review lane.
- Peer/M4 packets are visible, but should stay support-only unless the target Mac has its own execute report.

## Exact next implementation step

Add one Resplit Web proof-ladder panel to the top half of `/coding`, backed by existing APIs only.

Panel label:

> Resplit Web Proof Ladder

Rows:

1. `Public Matrix`
   - Button: `Run Public Matrix`
   - Route: `POST /api/coding/lanes/run` with `{ "jobId": "resplit-web-autobot", "mode": "public", "label": "resplit-web-public-matrix" }`
   - Meaning: auth-free public surface proof only.

2. `Local Smoke`
   - Button: `Run Local Smoke`
   - Route: `POST /api/coding/lanes/run` with `{ "jobId": "resplit-web-autobot", "mode": "local-smoke", "label": "resplit-web-local-smoke" }`
   - Meaning: disposable worktree, isolated port, local build/start, targeted Playwright.

3. `FirstBite UI Lane`
   - Button: `Dry UI Lane` / `Run UI Lane`
   - Route: `POST /api/coding/local-ci/run` with `{ "mode": "dry_run", "lanes": ["resplit_web_ui"], "worktree": true }` or `{ "mode": "execute", "lanes": ["resplit_web_ui"], "worktree": true }`
   - Meaning: repo-manifest CI lane, evidence under `~/.agent-ledger/firstbite-local-ci-mcp`.

4. `Verifier`
   - Button: `Delegate Verifier`
   - Route: `POST /api/coding/lanes/run` with `{ "jobId": "resplit-web-autobot", "mode": "codex-verifier", "label": "resplit-web-verifier" }`
   - Meaning: bounded Codex diagnosis on the prepared local server, no tracked source edits.

5. `Patch Lane`
   - Button: `Open Patch Lane`
   - Route: `POST /api/coding/lanes/run` with `{ "jobId": "resplit-web-autobot", "mode": "codex-editor", "label": "resplit-web-editor" }`
   - Meaning: disposable-worktree edit only, saved patch artifact, no primary checkout mutation.

Each row should show:

- latest run status,
- source state,
- report/log/patch link when present,
- port/worktree/teardown state for lane routes,
- explicit proof scope copy.

This is a UI assembly step, not new runner infrastructure.

## Localhost routes

- Moussey Coding Workbench: `http://127.0.0.1:4321/coding`
- Lane preflight: `POST http://127.0.0.1:4321/api/coding/lanes/preflight`
- Lane runner SSE: `POST http://127.0.0.1:4321/api/coding/lanes/run`
- Local-CI status: `GET http://127.0.0.1:4321/api/coding/local-ci`
- Local-CI run: `POST http://127.0.0.1:4321/api/coding/local-ci/run`
- Local-CI artifact reader: `GET http://127.0.0.1:4321/api/coding/local-ci/artifact?path=<encoded-path>`
- Local-CI handoff: `POST http://127.0.0.1:4321/api/coding/local-ci/handoff`
- Recent coding runs: `GET http://127.0.0.1:4321/api/coding/runs?limit=12`

## Test commands

Focused proof run from this pass:

```bash
cd /Users/leokwan/Development/moussey
node --test --import tsx app/api/coding/lanes/run/route.test.ts app/api/coding/local-ci/route.test.ts app/api/coding/local-ci/run/route.test.ts app/api/coding/local-ci/artifact/route.test.ts lib/local-ci-status.test.ts
```

Result in this pass: `25` tests passed, `0` failed.

Broader Moussey command-center test suite:

```bash
cd /Users/leokwan/Development/moussey
npm run test:brain-dispatcher
```

Manual/local smoke commands:

```bash
cd /Users/leokwan/Development/resplit-web
~/bin/autobot-resplit-web --public-only
```

```bash
cd /Users/leokwan/Development/ai-leo/skills/resplit-watch/mcp/firstbite-local-ci
npm run call -- list_lanes '{}'
npm run call -- status '{"limit":2}'
npm run call -- run_lanes '{"mode":"dry_run","lanes":["resplit_web_ui"],"worktree":true}'
```

Example lane-run API payloads:

```bash
curl -sS -N http://127.0.0.1:4321/api/coding/lanes/run \
  -H 'content-type: application/json' \
  -d '{"jobId":"resplit-web-autobot","mode":"local-smoke","label":"resplit-web-local-smoke"}'
```

```bash
curl -sS http://127.0.0.1:4321/api/coding/local-ci/run \
  -H 'content-type: application/json' \
  -d '{"mode":"dry_run","lanes":["resplit_web_ui"],"worktree":true}'
```

## Bottom line

The backend lane primitives are already MVP-capable for Resplit Web: public matrix, local smoke, local-CI run/status/artifacts, bounded verifier, bounded editor, patch artifact, run history, and teardown proof are all present. The finish-line work is to make them read as one Resplit Web proof ladder in `/coding`, so Leo can run the first coding framework without mentally translating local-CI, autobot, Codex, and artifact vocabulary.
