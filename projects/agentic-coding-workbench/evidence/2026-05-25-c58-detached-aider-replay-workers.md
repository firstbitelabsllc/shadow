# C58 Detached Aider Replay Workers

Date: 2026-05-25

## Verdict

C58 improves the `/coding` MVP by moving the C57 Gemma 4 vs Qwen3 Aider comparison out of fragile browser-bound lane streams and into detached worker actions. The model-quality verdict is blocked, not decided: Qwen3 worker `14ab1cbc-5b3e-450f-8916-541de49bb446` failed before Aider because the historical Resplit Web base now requires Redis/KV credentials during `next build`, and Gemma 4 still needs the same worker run after the build fixture is made safe.

## Why This Exists

C57 live route attempts did not produce a trustworthy model comparison:

- Gemma 4 live replay closed during dependency setup.
- Qwen3 linked-deps replay proved linked dependencies were not safe for the historical base because required Vercel packages were missing.
- Qwen3 isolated replay reached precheck, but the Moussey server was restarted by a neighboring Cleaner apple-photos cache rename failure, orphaning the browser-bound stream.
- Qwen3 detached worker proved the new architecture, then failed on a reproducible pre-Aider build fixture: missing Redis/KV credentials during historical-base `next build`.

The product lesson is clear: long model/editor trials are background work. The admin console should start them, show worker status/logs/artifacts, and let Leo keep using the UI.

## Code Changes

- Moussey `lib/coding-tool-actions.ts` adds allowlisted actions:
  - `aider-c57-gemma4-replay`
  - `aider-c57-qwen3-replay`
- Moussey `scripts/aider-c57-replay.sh` owns the real worker contract:
  - validates local Ollama model tags
  - uses base ref `412c49bff1252a26568e98ec3401adcdec9ee120`
  - creates a disposable `resplit-web` worktree
  - runs isolated `npm ci`, build, local server, precheck, Aider, postcheck, diff check
  - saves patch artifacts under `~/.moussey/coding-patches`
  - tears down server/worktree/branch/port lock
- Moussey `lib/capability-catalog.ts` surfaces both workers as ready tool actions.
- Moussey `/coding` model panel now shows `Gemma 4 Worker` and `Qwen3 Worker` instead of live-route replay buttons.

## Live Proof

- UI: `http://127.0.0.1:4321/coding?fresh=c58-detached-aider-workers`
- Capabilities: `http://127.0.0.1:4321/api/coding/capabilities`
- Qwen3 worker status: `http://127.0.0.1:4321/api/coding/workers/14ab1cbc-5b3e-450f-8916-541de49bb446`
- Screenshot: `/tmp/moussey-c58-detached-aider-workers.png`
- Worker start artifact: `/tmp/moussey-c58-qwen3-worker-start.json`

Qwen3 worker accepted:

```json
{
  "id": "14ab1cbc-5b3e-450f-8916-541de49bb446",
  "actionId": "aider-c57-qwen3-replay",
  "status": "running",
  "statusUrl": "/api/coding/workers/14ab1cbc-5b3e-450f-8916-541de49bb446",
  "command": "bash",
  "args": ["/Users/leokwan/Development/moussey/scripts/aider-c57-replay.sh"]
}
```

Worker log confirmed the intended boundary:

```text
[c57] model: qwen3:8b
[c57] base: 412c49bff1252a26568e98ec3401adcdec9ee120
[c57] repo: /Users/leokwan/Development/resplit-web
[c57] port: 3119
[c57] boundary: detached worker, local model only, no cloud token env, no commit, patch artifact first
```

Final worker state:

```json
{
  "status": "failed",
  "exitCode": 1,
  "signal": null,
  "durationMs": 34400,
  "stale": false
}
```

Failure tail:

```text
Error: Missing Redis credentials. Set UPSTASH_REDIS_REST_URL + UPSTASH_REDIS_REST_TOKEN or KV_REST_API_URL + KV_REST_API_TOKEN in your environment.
> Build error occurred
Error: Failed to collect page data for /api/session/[slug]/emoji-hint
```

Teardown check:

```bash
git -C /Users/leokwan/Development/resplit-web worktree list | rg '14ab1cbc|c57-aider-qwen3' || true
git -C /Users/leokwan/Development/resplit-web branch --list 'codex/web-c57-aider-qwen3-8b-14ab1cbc*'
ls "${TMPDIR:-/tmp}" | rg 'moussey-aider-c57-port-3119' || true
```

All three commands returned no matching worktree, branch, or port lock.

## Verification

```bash
chmod +x scripts/aider-c57-replay.sh
bash -n scripts/aider-c57-replay.sh
node --test --import tsx lib/coding-tool-actions.test.ts lib/capability-catalog.test.ts app/api/coding/workers/route.test.ts app/api/coding/tool-actions/run/route.test.ts
node --test --import tsx lib/coding-lanes.test.ts app/api/coding/lanes/run/route.test.ts lib/coding-workbench.test.ts
npx tsc --noEmit --pretty false
git diff --check -- lib/coding-tool-actions.ts lib/coding-tool-actions.test.ts lib/capability-catalog.ts lib/capability-catalog.test.ts app/coding/page.tsx scripts/aider-c57-replay.sh
./scripts/moussey-server.sh --build && ./scripts/moussey-server.sh --restart
curl -fsS --max-time 5 http://127.0.0.1:4321/api/health
curl -fsS --max-time 20 http://127.0.0.1:4321/api/coding/capabilities
```

Results:

- Focused worker/action/catalog tests: 36/36 passed.
- Focused lane/workbench tests: 34/34 passed.
- TypeScript passed.
- Diff check passed.
- Standalone Moussey build/restart passed with the known local-CI artifact NFT warning.
- Live health returned `ok:true`.
- Live capabilities showed both C57 workers `ready`.
- Playwright opened `/coding?fresh=c58-detached-aider-workers`, found `Gemma 4 Worker`, `Qwen3 Worker`, and the detached-worker boundary copy, with zero console/page errors.
- Live Qwen3 worker failed cleanly with `exitCode:1` on missing Redis/KV credentials before Aider, and teardown removed the generated worktree/branch/lock.

## Remaining Gate

C57 is not complete until the Resplit Web build fixture is safe and both workers finish with an evidence table comparing:

- model
- runtime
- precheck result
- source diff
- patch stat
- postcheck result
- patch artifact path
- teardown result

Do not promote Aider/Gemma/Qwen for serious Resplit Web patching until a local model changes the relevant source and passes the postcheck. `Codex Editor` remains the default serious patch route.

Next implementation slice: give C57 a no-secret Redis/KV mock env for this historical base, or choose a newer equivalent failing ref that can build without secrets, then rerun Qwen3 and Gemma 4 through the detached worker actions.
