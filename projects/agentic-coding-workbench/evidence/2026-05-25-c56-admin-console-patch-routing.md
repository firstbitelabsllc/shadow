# C56 Admin Console Patch-Routing Proof

## Summary

C56 makes Moussey `/coding` read more like an internal coding-agent admin console and less like an AI test bed. The first viewport now names the product as `Coding command center`, shows operator-state pills, and separates the serious patch path from the local-model lab:

- Default fixer: `Codex Editor`
- Local lab: `Aider + Gemma/Qwen`
- CI state: surfaced from the local-CI cockpit data
- Ledger state: surfaced as command-center orientation, not source of truth

Failed Resplit Web handoffs now default to `codex-editor` for serious fixes. `Aider Lab` stays available, but it is explicitly experimental until a replay produces both changed source files and a passing postcheck.

## Local Model Truth

- Ollama is listening at `127.0.0.1:11434`.
- Installed local models include `gemma4:e4b`, `qwen3:8b`, `deepseek-r1:8b`, `gemma3:12b`, and `qwen2.5:0.5b`.
- `/api/coding/capabilities` reports `local-gemma4` ready with `gemma4:e4b`.
- The selected local chat/coding model remains `qwen3:8b` because it is the current thinking-capable local route.
- The HF Qwen3-Coder route is present as `Qwen/Qwen3-Coder-30B-A3B-Instruct`, but it remains token/spend-gated.

Gemma 4 is installed and visible. It is not the default coding fixer yet because C55 proved that local edit authority needs source-patch and postcheck proof. A newer or better model is not the same thing as a proven coding-agent lane.

## UX Changes

- Top header changed to `Coding command center`.
- The first viewport now explains the internal console purpose: local CI, agent workers, model routing, patch lanes, logs, and Ledger proof.
- Added an operator rail that makes default patch routing and local-model lab status obvious.
- Added a `Patch Routing` decision panel:
  - serious patch route: `Codex Editor`
  - experimental lane: `Aider Lab`
  - promotion gate: source diff plus passing postcheck
- Renamed action buttons to workbench language:
  - `Check CI Gate`
  - `Run Autobot Matrix`
  - `Delegate Research Agent`
  - `Run System Gate`
- Added model-route cards for Gemma 4, Qwen3-Coder, selected local model, and promotion gate.
- Renamed handoff controls:
  - `Codex Editor (default)`
  - `Aider Lab`

## Code Surfaces

- `/Users/leokwan/Development/moussey/app/coding/page.tsx`
- `/Users/leokwan/Development/moussey/app/api/coding/local-ci/handoff/route.ts`
- `/Users/leokwan/Development/moussey/app/api/coding/runs/handoff/route.ts`
- `/Users/leokwan/Development/moussey/lib/capability-catalog.ts`

## Verification

```bash
node --test --import tsx app/api/coding/local-ci/handoff/route.test.ts app/api/coding/runs/handoff/route.test.ts lib/coding-handoffs.test.ts app/api/coding/lanes/run/route.test.ts lib/coding-lanes.test.ts app/api/coding/capabilities/route.test.ts lib/capability-catalog.test.ts lib/local-model-runtime.test.ts
```

Result: 48/48 tests passed.

```bash
npm run test:brain-dispatcher -- --test-concurrency=1
```

Result: 174/174 tests passed.

```bash
npx tsc --noEmit --pretty false
```

Result: passed.

```bash
git diff --check -- app/coding/page.tsx app/api/coding/local-ci/handoff/route.ts app/api/coding/local-ci/handoff/route.test.ts app/api/coding/runs/handoff/route.ts app/api/coding/runs/handoff/route.test.ts lib/capability-catalog.ts lib/local-model-runtime.ts
```

Result: passed.

```bash
./scripts/moussey-server.sh --build
./scripts/moussey-server.sh --restart
curl -fsS --max-time 10 http://127.0.0.1:4321/api/health
curl -fsS --max-time 30 http://127.0.0.1:4321/api/coding/capabilities
curl -fsS --max-time 5 http://127.0.0.1:11434/api/tags
```

Result: build/restart passed, health returned `ok:true`, capabilities returned `modelRoutePlan.status:"ready"`, and Ollama tags included `gemma4:e4b`.

## Browser Proof

Live target:

- `http://127.0.0.1:4321/coding?fresh=c56-admin-console`

Screenshots:

- `/tmp/moussey-c56-coding-admin-desktop.png`
- `/tmp/moussey-c56-coding-admin-mobile.png`

Playwright proof:

- Desktop viewport saw `Coding command center`, `Codex Editor (default)`, `Aider Lab`, `Gemma 4`, and `Qwen3-Coder`.
- Mobile viewport had no horizontal overflow.
- Console errors: none.

## Localhost Links

- Coding command center: `http://127.0.0.1:4321/coding?fresh=c56-admin-console`
- Coding capabilities: `http://127.0.0.1:4321/api/coding/capabilities`
- Moussey health: `http://127.0.0.1:4321/api/health`
- C55 failed Aider patch preview: `http://127.0.0.1:4321/api/coding/runs/57e8067f-9ccb-4218-91fb-26f3a92e8d2d/patch`

## Residual Gaps

- C57 should run the identical historical patch replay through `Aider Lab` using both `gemma4:e4b` and `qwen3:8b`, then compare source diff, patch stat, postcheck, runtime, and logs.
- Do not promote either local route until it changes the relevant source and passes the verifier.
- Codex LB usage still timed out in the capabilities readout.
- `opencode` and Goose are installed but still need config/wrappers before they become safe workbench actions.
- HF Qwen3-Coder remains token/spend-gated.
