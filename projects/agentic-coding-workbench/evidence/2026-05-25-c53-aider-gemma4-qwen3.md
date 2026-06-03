# C53 - Aider, Gemma 4, and Qwen3 Local Reasoning Proof

## Scope

Leo asked whether the local command-center workbench can become the real coding-agent finish-line surface: local models, local CI/autobot, agent delegation, and an IDE-like cockpit that is honest about what is ready. This slice keeps ownership on the current Mac Studio base station and advances the local model/tool loop without adding cross-Mac write bridges, arbitrary browser shell, or edit authority.

## What Changed

- Ollama upgraded from `0.18.2` to `0.24.0` because `ollama pull gemma4:e4b` refused the older runtime.
- `gemma4:e4b` installed locally and is now the Gemma target. `gemma3:12b` remains installed but is treated as fallback.
- Moussey's default local chat/coding model moved from `qwen2.5:0.5b` to `qwen3:8b` because Qwen3 can emit Ollama thinking frames.
- `scripts/hf-router-model-dry-run.sh` now lists local `gemma4:e4b` instead of stale Gemma 3 as the Gemma route, while preserving the no-spend/token-needed guard.
- `scripts/aider-local-model-probe.sh` and the `/coding` Aider action default to `qwen3:8b`, strip cloud API env values, and prove readiness only. They do not run an edit loop.
- `/coding` exposes the current state through `http://127.0.0.1:4321/coding?fresh=c53-aider-gemma4-qwen3`.

## Live Proof

- `ollama --version` returns `0.24.0`.
- `GET /api/chat/providers` reports `selectedModel:"qwen3:8b"`, local provider ready, and steady/deep reasoning profiles with `sendsThinking:true`.
- `GET /api/coding/capabilities` reports `selected:"qwen3:8b"`, `local-qwen3` ready, `local-gemma4` ready, and ready actions for HF dry-run, Aider probe, and Resplit Web Autobot public matrix.
- Live deep local chat against `qwen3:8b` emitted `thinking` frames and completed with text after `6707ms`.
- Live worker `5f9e07f8-be45-4443-a657-5906b25efc68` completed `exitCode:0`; it found Aider `0.86.2`, Ollama reachable, selected `qwen3:8b`, and installed models including `gemma4:e4b`, `deepseek-r1:8b`, `gemma3:12b`, `qwen3:8b`, and `qwen2.5:0.5b`.
- Playwright opened `/coding` and saw `Aider Local Model Probe`, `Gemma 4 local agent`, and `qwen3:8b`; screenshot: `/tmp/moussey-c53-coding-gemma4-aider.png`.
- `moussey-trigger-doctor --brief` returned listener and endpoint healthy.
- `vidux-browse health` confirmed Vidux Browser on `http://127.0.0.1:7191`.

## Verification

- `bash -n scripts/aider-local-model-probe.sh scripts/hf-router-model-dry-run.sh`
- Focused tests passed `42/42`, then after the default-model patch passed `35/35`.
- `npm run test:brain-dispatcher` passed `165/165` after rerunning alone. One overlapping worker-test run had a transient worker status race; the isolated rerun passed.
- `npx tsc --noEmit --pretty false` passed.
- `MOUSSEY_AIDER_LOCAL_MODEL=gemma4:e4b scripts/aider-local-model-probe.sh` passed directly.
- `scripts/hf-router-model-dry-run.sh` passed as a no-spend dry-run and ended `status: token-needed`.
- `./scripts/moussey-server.sh --build && ./scripts/moussey-server.sh --restart` passed with the known Turbopack NFT artifact-route warning.

## Finish-Line Amp

Drive the `agentic-coding-workbench` plan to the local coding MVP finish line from this Mac Studio session: keep `/coding` as the single operator cockpit, make FirstBite local-CI/autobot failures flow into allowlisted detached coding agents, and convert Aider from probe-only into a disposable-worktree patch worker that saves previewable patches without touching primary checkouts. Preserve dirty neighboring Cleaner and plan work, keep Gemma 4/Qwen3/local model readiness visible, use Ledger only as activity context, cite real MCP/local-CI reports as proof, and do not claim replacement-level CI until the first viewport shows source state, queue/runs, artifacts, rerun/handoff buttons, executor boundary, and fresh-main versus dirty-local truth.

## Remaining Boundary

- The Aider route is readiness proof only. The next implementation slice is an Aider patch worker in a disposable worktree, wired to a specific failed local-CI/autobot handoff.
- Claude provider auth is still not a local proof point for `/chat`; local Ollama and Codex are ready, and HF routes remain token-gated with no spend.
- Gemma 4 is installed and exposed, but Qwen3 remains the default coding/chat model because it is the smaller thinking-capable model for day-to-day local work.
