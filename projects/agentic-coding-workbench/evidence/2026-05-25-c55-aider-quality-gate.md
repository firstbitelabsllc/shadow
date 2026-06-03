# C55 Aider Patch-Quality Gate

## Verdict

C55 closes as a useful negative proof: the Moussey route is now safe enough to judge a local Aider edit attempt, but `ollama_chat/qwen3:8b` through Aider is not yet routine-ready for autonomous Resplit Web fixes.

The guardrails worked:

- Disposable worktree created from historical failing Resplit Web ref `412c49bff1252a26568e98ec3401adcdec9ee120`.
- Isolated server started on `http://127.0.0.1:3110`.
- Route precheck ran `e2e/landing-smoke.spec.ts` first and captured the real failure: stale `#globe` expectation, `1 failed / 4 passed`.
- Aider received the route-captured verifier failure context before edit authority.
- Route postcheck ran the same verifier after Aider exited.
- Worktree, branch, server, and port lock were torn down with `teardownOk:true`.
- Patch artifact stayed guarded under `~/.moussey/coding-patches`.

The local Aider edit did not meet the bar:

- Aider reasoned about the correct target but did not apply the source change to `e2e/landing-smoke.spec.ts`.
- Postcheck still failed on `#globe`: `1 failed / 4 passed`.
- Saved patch only added `.aider*` to `.gitignore`, which is not an acceptable product fix.
- Follow-up hardening added `--no-gitignore` to future Aider runs so tool metadata does not pollute patch artifacts.

## Live Run

- Run id: `57e8067f-9ccb-4218-91fb-26f3a92e8d2d`
- Mode: `aider-editor`
- Base ref: `412c49bff1252a26568e98ec3401adcdec9ee120`
- SSE: `/tmp/moussey-c55-aider-quality-20260524T232432.sse`
- Patch API: `http://127.0.0.1:4321/api/coding/runs/57e8067f-9ccb-4218-91fb-26f3a92e8d2d/patch`
- Patch file: `/Users/leokwan/.moussey/coding-patches/57e8067f-9ccb-4218-91fb-26f3a92e8d2d.patch`
- UI proof: `http://127.0.0.1:4321/coding?fresh=c55-aider-quality`
- Screenshot: `/tmp/moussey-c55-aider-quality-ui.png`

## Commands

```bash
npm run test:brain-dispatcher -- --test-concurrency=1
./scripts/moussey-server.sh --build
./scripts/moussey-server.sh --restart
curl -fsS --max-time 10 http://127.0.0.1:4321/api/health
curl -fsS --max-time 20 http://127.0.0.1:4321/api/coding/jobs
curl -fsS --max-time 30 http://127.0.0.1:4321/api/coding/capabilities
curl -N -sS --max-time 1800 -H 'Content-Type: application/json' \
  -d '{"jobId":"resplit-web-autobot","mode":"aider-editor","label":"C55 Aider Quality Replay","baseRef":"412c49bff1252a26568e98ec3401adcdec9ee120"}' \
  http://127.0.0.1:4321/api/coding/lanes/run | tee /tmp/moussey-c55-aider-quality-20260524T232432.sse
curl -fsS --max-time 10 'http://127.0.0.1:4321/api/coding/runs?limit=3'
curl -fsS --max-time 10 http://127.0.0.1:4321/api/coding/runs/57e8067f-9ccb-4218-91fb-26f3a92e8d2d/patch
```

## Verification

After the route hardening and `--no-gitignore` follow-up:

```bash
node --test --import tsx app/api/coding/lanes/run/route.test.ts lib/coding-lanes.test.ts lib/coding-handoffs.test.ts app/api/coding/local-ci/handoff/route.test.ts app/api/coding/runs/handoff/route.test.ts
npx tsc --noEmit --pretty false
git diff --check -- app/api/coding/lanes/run/route.ts lib/coding-lanes.ts app/api/coding/lanes/run/route.test.ts lib/coding-lanes.test.ts lib/cleaner/visual-batch.ts
npm run test:brain-dispatcher -- --test-concurrency=1
./scripts/moussey-server.sh --build && ./scripts/moussey-server.sh --restart && curl -fsS --max-time 10 http://127.0.0.1:4321/api/health
```

Results:

- Focused route/handoff tests: `36/36` pass.
- TypeScript: pass.
- Diff check: pass.
- Serialized brain/dispatcher/coding suite: `174/174` pass.
- Standalone build/restart: pass with the known local-CI artifact NFT warning.
- Live health: `ok:true`.

## Product Decision

- Keep `Aider Editor` visible as an experimental local-model editor lane.
- Default serious failed-run patch handoff back to `Codex Editor` until a local tool can produce a real source patch and pass postcheck.
- The MVP finish line remains local-CI/autobot/source-state/worker/patch visibility, not proving every open model is already a coding teammate.
