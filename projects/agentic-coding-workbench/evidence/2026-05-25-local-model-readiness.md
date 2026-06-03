# Local Model and Runtime Readiness - 2026-05-25

## Current detected local runtime state

- Host: Mac Studio `Mac14,14`, Apple M2 Ultra, 24 CPU cores, 64 GB unified memory. Data volume has about 169 GiB free, so a few 5-20 GB quantized local models are practical; many 30B+ experiments are feasible but should be staged deliberately.
- Ollama is installed at `/opt/homebrew/bin/ollama` and reachable at `http://127.0.0.1:11434`.
- Installed Ollama inventory: only `qwen2.5:0.5b`, 397 MB, Q4_K_M, family `qwen2`, about 494M parameters, modified `2026-05-23T20:28:46-04:00`.
- Moussey `/api/chat/providers` reports local provider ready with default model `qwen2.5:0.5b`; Claude CLI auth is currently not ready in that API, and Codex CLI is installed.
- Current local model is proof plumbing, not a real coding-agent brain. It is good for latency and local route verification, but it does not support Moussey's Ollama `think` path.
- Moussey local runtime code sends `think` only for names matching `qwen3`, `deepseek-r1`, `gpt-oss`, `magistral`, or `harmony`. For `qwen2.5:0.5b`, Moussey can raise `num_ctx` and `num_predict` in steady/deep modes, but `sendsThinking` remains false.
- `codex-lb` is configured as the default Codex provider in `~/.codex/config.toml`, with `model = "gpt-5.5"`, `model_reasoning_effort = "medium"`, and `base_url = "http://127.0.0.1:2455/backend-api/codex"`.
- `codex-lb` LaunchAgent is installed at `~/Library/LaunchAgents/com.leokwan.codex-lb.plist`, bound to `127.0.0.1:2455`, and health is ok. `/v1/models` returns Codex models with explicit reasoning levels through `xhigh`.
- `codex-lb` account API shows three active authenticated accounts. Do not treat it as hard-pinned per Moussey worker; existing Vidux direction says it is a route hint until a supported next-worker pin is proven.
- HF token boundary: `HF_TOKEN` and `HUGGINGFACE_HUB_TOKEN` are unset in this shell. Moussey's HF dry-run intentionally reports only token presence and does not pass token values or make inference calls.
- Moussey model-route code already exposes Qwen/Gemma/DeepSeek/Kimi candidates and a dry-run gate:
  - local `qwen3:8b`
  - local `gemma3:12b`
  - HF router `Qwen/Qwen3-Coder-30B-A3B-Instruct`
  - HF router `deepseek-ai/DeepSeek-V3.1`
  - HF router `moonshotai/Kimi-K2-Instruct-0905`
- Live `GET /api/coding/capabilities` timed out at 2 seconds during this probe, so I used direct code reads plus `/api/chat/providers`, `/api/health`, Ollama, and codex-lb endpoints for runtime truth.

## Best local coding models to try first, ordered by Mac feasibility

1. `qwen3:8b` via Ollama.
   - Best first real local upgrade. Ollama lists it as 5.2 GB with a 40K context window, and Qwen3 is a supported Ollama thinking family. It should fit easily on this 64 GB M2 Ultra and directly exercises Moussey's `think: true` path for steady/deep local requests.
   - Reality: good local reasoning/general coding candidate, not a frontier repo-scale coding agent.

2. `deepseek-r1:8b` via Ollama.
   - Also 5.2 GB with a 128K context window in Ollama's library. It is a thinking model and a useful contrast against Qwen3 for deliberate reasoning, bug triage, and "explain before acting" local tasks.
   - Reality: likely verbose and slower; use as reasoning fallback, not default chat.

3. `gemma3:12b` via Ollama.
   - 8.1 GB with a 128K context window and text/image support in Ollama. Good generalist and useful for summarization, UI/copy, local multimodal comparison, and non-reasoning chat.
   - Reality: Moussey should not advertise this as explicit thinking; it gets larger context/output budgets only.

4. `qwen3:14b` via Ollama.
   - 9.3 GB with 40K context. Still easy on this Mac and likely a better local reasoning/coding model than 8B when latency is acceptable.
   - Reality: test after `qwen3:8b`; it is a second-step quality bump, not the first plumbing proof.

5. `qwen3:30b` via Ollama.
   - 19 GB with 256K context. This Mac can plausibly run it, but it should be a deliberate heavier benchmark because it will contend with browser/test/agent workloads.
   - Reality: promising for local repo-scale summaries and harder coding questions, but do not make it the command-center default until latency and memory are measured.

6. Qwen3-Coder 30B A3B 4-bit via MLX or LM Studio, not Ollama-first.
   - The official Qwen3-Coder-30B-A3B-Instruct card says 30.5B total parameters, 3.3B activated, and 262K native context. That shape is attractive for Apple Silicon, but the practical local route is MLX/LM Studio quantized weights, not the current Moussey Ollama route.
   - Reality: best local coding-specialist experiment after the Ollama route works. It will require separate OpenAI-compatible local server wiring, for example LM Studio on `:1234` or `mlx_lm.server`.

Do not bother with local Kimi K2 or DeepSeek V3.1 on this Mac for normal command-center work. Kimi K2 0905 is a 1T total / 32B active MoE model with 256K context; DeepSeek V3.1 is 671B total / 37B active with 128K context. They belong behind router/cloud overflow gates, not local defaults.

## Best HF/router/cloud open-weight candidates for overflow, with token/spend gates

1. `Qwen/Qwen3-Coder-30B-A3B-Instruct`
   - Best first overflow model for coding-agent tasks too hard for local Ollama. The model card emphasizes agentic coding, 30.5B total / 3.3B active parameters, and 262K native context.
   - Gate: require `HF_TOKEN`, explicit allowlist, provider suffix policy such as `:fastest` or `:cheapest`, request/output budget, and no-secret logging before a single live call.

2. `moonshotai/Kimi-K2-Instruct-0905`
   - Strong overflow candidate for agentic coding and frontend-heavy work. Model card reports 1T total / 32B active parameters and 256K context.
   - Gate: router/cloud only; do not attempt local pull except as a separate MLX research lane with clear disk/time budget.

3. `deepseek-ai/DeepSeek-V3.1`
   - Strong reasoning/coding fallback. Model card says it supports both thinking and non-thinking modes via chat template, 671B total / 37B active parameters, and 128K context.
   - Gate: router/cloud only; confirm the selected HF provider actually exposes the thinking/non-thinking behavior and tool template before relying on it for agent control.

4. `google/gemma-3-12b-it` or Gemma provider route.
   - Good generalist overflow if Leo wants a Google-family comparison, but less compelling for coding-agent overflow than Qwen/Kimi/DeepSeek.
   - Gate: same HF token/spend/no-secret requirements. Prefer local `gemma3:12b` first unless the cloud route provides a clear quality/latency advantage.

HF router control shape:

```bash
# Proposed only; do not run until Leo approves token/spend.
export HF_TOKEN=...
export MOUSSEY_HF_ROUTER_ALLOW_TOKEN_CALL=1
export MOUSSEY_HF_ROUTER_ALLOW_MODEL_LIST=1

curl https://router.huggingface.co/v1/chat/completions \
  -H "Authorization: Bearer $HF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen3-Coder-30B-A3B-Instruct:cheapest","messages":[{"role":"user","content":"Say ok"}],"max_tokens":16}'
```

Use `:cheapest` for exploratory smoke and `:fastest` for latency proof. Do not enable arbitrary model IDs; keep Moussey's allowlist explicit.

## What supports actual thinking/reasoning controls vs only larger context/output budgets

- Actual local Ollama thinking control:
  - Supported by Ollama for Qwen 3 and DeepSeek R1, among others. The API uses a `think` field and emits a separate `thinking` stream/field.
  - Moussey already maps steady/deep local modes to `think: true` for `qwen3:*` and `deepseek-r1:*`.
  - Install candidates: `qwen3:8b`, `qwen3:14b`, `qwen3:30b`, `deepseek-r1:8b`, `deepseek-r1:14b`.

- Not actual thinking in the current Moussey local path:
  - `qwen2.5:0.5b`: installed and fast, but no `think` support.
  - `gemma3:*`: useful context/generalist/vision route, but no explicit Ollama `think` flag in Moussey's support list.

- Cloud/router reasoning controls:
  - `codex-lb`/Codex models expose real reasoning effort levels (`low`, `medium`, `high`, `xhigh`) in the model metadata. This is the strongest current "thinking control" path for coding agents on this Mac.
  - HF router is OpenAI-compatible for chat completions and can route by provider policy, but model-specific thinking controls are not uniform. Treat Qwen/Kimi/DeepSeek thinking behavior as model/provider-template dependent until verified with an allowlisted dry-run.
  - DeepSeek V3.1 explicitly has thinking and non-thinking modes in its model card, but that does not automatically mean every HF provider exposes a clean API toggle.

## Exact safe install commands to propose, but do not run

Smallest useful local reasoning proof:

```bash
ollama pull qwen3:8b
ollama run qwen3:8b --think "Return exactly: local-qwen3-thinking-ok"
curl http://127.0.0.1:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3:8b","prompt":"Return exactly: api-thinking-ok","think":true,"stream":false}'
```

Second local reasoning comparison:

```bash
ollama pull deepseek-r1:8b
ollama run deepseek-r1:8b --think "Return exactly: local-deepseek-thinking-ok"
```

Generalist/local multimodal comparison:

```bash
ollama pull gemma3:12b
ollama run gemma3:12b "Return exactly: local-gemma-ok"
```

Heavier local quality experiments, only after the 8B/12B lanes are measured:

```bash
ollama pull qwen3:14b
ollama pull qwen3:30b
ollama pull deepseek-r1:14b
```

MLX/LM Studio Qwen3-Coder experiment, separate from the current Ollama path:

```bash
# Option A: LM Studio app, then download a Qwen3-Coder-30B-A3B-Instruct MLX 4-bit model in the UI.
brew install --cask lm-studio
# Start LM Studio Developer server, then verify:
curl http://127.0.0.1:1234/v1/models
```

```bash
# Option B: MLX server. This will download a large model if run.
python3 -m pip install --user mlx-lm
python3 -m mlx_lm.server \
  --model mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit \
  --host 127.0.0.1 \
  --port 1234
curl http://127.0.0.1:1234/v1/models
```

HF router no-spend dry-run shape:

```bash
cd /Users/leokwan/Development/moussey
MOUSSEY_HF_TOKEN_CONFIGURED=false ./scripts/hf-router-model-dry-run.sh
```

HF router first spend-gated live smoke, only after Leo provides/approves token use:

```bash
export HF_TOKEN=...
export MOUSSEY_HF_ROUTER_ALLOW_TOKEN_CALL=1
export MOUSSEY_HF_ROUTER_ALLOW_MODEL_LIST=1

curl https://router.huggingface.co/v1/models \
  -H "Authorization: Bearer $HF_TOKEN" \
  | jq '.data[] | select(.id | test("Qwen3-Coder|DeepSeek-V3.1|Kimi-K2|gemma-3-12b")) | {id, owned_by}'
```

## Source URLs checked

- Ollama Qwen3: https://ollama.com/library/qwen3
- Ollama thinking docs: https://docs.ollama.com/capabilities/thinking
- Ollama Gemma3: https://ollama.com/library/gemma3
- Ollama DeepSeek R1: https://www.ollama.com/library/deepseek-r1
- Qwen3-Coder-30B-A3B-Instruct model card: https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct
- Hugging Face Inference Providers / OpenAI-compatible router: https://huggingface.co/docs/inference-providers/main/en/index
- DeepSeek-V3.1 model card: https://huggingface.co/deepseek-ai/DeepSeek-V3.1
- Kimi-K2-Instruct-0905 model card: https://huggingface.co/moonshotai/Kimi-K2-Instruct-0905
