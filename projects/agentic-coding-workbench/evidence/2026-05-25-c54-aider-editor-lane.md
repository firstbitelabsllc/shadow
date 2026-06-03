# C54 Aider Editor Lane Proof

Date: 2026-05-25
Host: `Leos-Mac-Studio-10442.local`
Surface: `http://127.0.0.1:4321/coding?fresh=c54-aider-editor`

## Goal

Promote Aider from a readiness probe into a guarded editor lane for the local coding workbench without giving the browser arbitrary shell or primary-checkout mutation power.

## What changed

- Added `aider-editor` lane mode in `/Users/leokwan/Development/moussey/lib/coding-lanes.ts`.
- The Aider lane uses `MOUSSEY_AIDER_BIN || aider`, defaults to `ollama_chat/qwen3:8b`, and sets `OLLAMA_API_BASE=http://127.0.0.1:11434`.
- The child environment is built from the minimal coding env and does not pass `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `HF_TOKEN`.
- The prompt allows edits only inside the disposable Resplit Web worktree, forbids primary-checkout/Cleaner/cross-Mac/production/money/human/public-tunnel mutation, and tells the agent the runner will save a patch artifact and tear down the lane.
- `/Users/leokwan/Development/moussey/app/api/coding/lanes/run/route.ts` now dispatches `aider-agent-editor`, runs it after the same local server prep as Codex Editor, and saves patch artifacts through the existing `git diff --check` / `git diff --stat` / `git diff --binary` path.
- `/Users/leokwan/Development/moussey/lib/coding-handoffs.ts` now accepts `aider-editor`.
- Failed Resplit Web local-CI lane handoffs and failed Resplit Web/autobot run handoffs now recommend `Aider Editor`.
- `/Users/leokwan/Development/moussey/app/coding/page.tsx` now shows `Aider Editor` beside `Codex Editor` in handoff and isolated-agent controls.

## Verification

```bash
node --test --import tsx \
  lib/coding-lanes.test.ts \
  lib/coding-handoffs.test.ts \
  app/api/coding/local-ci/handoff/route.test.ts \
  app/api/coding/runs/handoff/route.test.ts \
  app/api/coding/lanes/run/route.test.ts
# pass: 34/34

git diff --check -- \
  lib/coding-lanes.ts \
  app/api/coding/lanes/run/route.ts \
  lib/coding-handoffs.ts \
  app/api/coding/local-ci/handoff/route.ts \
  app/api/coding/runs/handoff/route.ts \
  app/coding/page.tsx \
  lib/coding-lanes.test.ts \
  lib/coding-handoffs.test.ts \
  app/api/coding/local-ci/handoff/route.test.ts \
  app/api/coding/runs/handoff/route.test.ts \
  app/api/coding/lanes/run/route.test.ts
# pass

npx tsc --noEmit --pretty false
# pass

npm run test:brain-dispatcher
# pass: 171/171

./scripts/moussey-server.sh --build
# pass with the known Turbopack NFT trace warning on app/api/coding/local-ci/artifact/route.ts

./scripts/moussey-server.sh --restart
# kicked. listening on http://0.0.0.0:4321.

curl -fsS --max-time 5 http://127.0.0.1:4321/api/health
# ok:true

curl -fsS --max-time 5 http://127.0.0.1:4321/api/coding/jobs
# ok:true; resplit-web-autobot ready:true

curl -fsS --max-time 30 http://127.0.0.1:4321/api/coding/capabilities
# ok:true; qwen3:8b selected; gemma4:e4b ready; aider installed; Cleaner neighbor warning preserved
```

Browser proof used the Codex app Node REPL Playwright runtime:

- URL: `http://127.0.0.1:4321/coding?fresh=c54-aider-editor`
- Saw: `Aider Editor`, `Codex Editor`, `Local Agent Toolchain`, and `Model Routes`
- Console/page errors: none
- Screenshot: `/tmp/moussey-c54-aider-editor-ui.png`

## Boundary

This proves the route, safety contract, handoff recommendation, patch-artifact machinery, and live UI/API surface. It does not yet prove that Qwen3/Gemma 4 Aider produces a good real-world Resplit Web patch. That is the next C55 quality trial: choose a concrete failing lane, run `Aider Editor`, inspect the saved patch, and decide whether local-model editing is routine-safe or experimental-only.
