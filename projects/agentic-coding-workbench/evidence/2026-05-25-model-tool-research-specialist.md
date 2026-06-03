# Model/Tool Research Specialist Note - 2026-05-25

Scope: local/open-weight coding models, local reasoning, coding-agent tools, and verification gates for the Moussey/Vidux `agentic-coding-workbench` MVP.

Write boundary: evidence note only. No Moussey code or PLAN.md files were edited.

## Current Local State

From local toolchain evidence and live checks:

- Installed local models in Ollama: `qwen3:8b`, `deepseek-r1:8b`, `gemma3:12b`, `qwen2.5:0.5b`.
- Installed coding tools: `aider 0.86.2`, `opencode 1.15.10`, `goose 1.35.0`.
- IDE extensions installed per existing evidence: Continue `1.2.22`, Cline `3.84.0`.
- Existing proof: `qwen3:8b` returned `api-thinking-ok` through Ollama with `think:true` and a separate `thinking` field.
- Existing cockpit stance: inventory/routing truth only; no arbitrary shell or edit authority from the browser until an allowlisted disposable-worktree wrapper exists.

## Sources Checked

- Ollama thinking docs: https://docs.ollama.com/capabilities/thinking
- Ollama model catalog/search: https://www.ollama.com/search
- Qwen3-Coder-Next model card: https://huggingface.co/Qwen/Qwen3-Coder-Next
- Gemma 3 model card: https://ai.google.dev/gemma/docs/core/model_card_3
- DeepSeek-R1 paper: https://arxiv.org/abs/2501.12948
- Hugging Face Inference Providers: https://huggingface.co/docs/hub/en/models-inference
- Aider Ollama docs: https://aider.chat/docs/llms/ollama.html
- Aider model guidance: https://aider.chat/docs/llms.html
- OpenCode providers docs: https://opencode.ai/docs/providers/
- Goose local inference post: https://goose-docs.ai/blog/2026/04/24/use-goose-with-built-in-local-inference/
- Cline local models docs: https://docs.cline.bot/running-models-locally/ollama
- Cline provider/local model docs: https://docs.cline.bot/getting-started/authorizing-with-cline
- Continue model-role docs: https://docs.continue.dev/customize/models

## Short Recommendation

For the command-center MVP, use local models to reduce token spend for harness triage and bounded verifier loops, not as the main autonomous coding brain yet.

Recommended order:

1. `qwen3:8b` via Ollama as the first local reasoning/verifier model.
2. `deepseek-r1:8b` via Ollama as the second local reasoning comparator.
3. `gemma3:12b` via Ollama as a generalist/multimodal summarizer, not the first code-edit brain.
4. `qwen2.5:0.5b` only as a fast health/proof fallback.
5. HF Inference Providers only as an optional remote fallback behind explicit `HF_TOKEN` and spend gates.

Recommended tool order:

1. Aider first for a patch-worker experiment because it is terminal-first, git-aware, and has explicit Ollama support.
2. OpenCode second for a richer terminal agent loop once provider config is proven.
3. Goose third for MCP/provider-oriented agent experiments and local inference research, not first patch promotion.
4. Continue and Cline as human-supervised IDE handoff surfaces, not the first browser-launched autonomous worker.

## Model Shortlist

| Model | Boundary | Why it fits | Thinking/reasoning control | MVP recommendation |
|---|---|---|---|---|
| `qwen3:8b` | Local Ollama | Already installed locally; Ollama docs list Qwen 3 as thinking-capable; current local smoke proved `think:true` emits `thinking`. | Supported through Ollama `think:true/false`; stream and non-stream paths expose reasoning separately from final answer. | Use as the first local verifier for small coding/test triage and "explain the failed lane" tasks. |
| `deepseek-r1:8b` | Local Ollama | Already installed locally; DeepSeek-R1 is explicitly a reasoning model family and Ollama lists DeepSeek R1 as thinking-capable. | Supported through Ollama `think:true/false`; good second opinion for reasoning-heavy failures. | Use as comparator on selected failures, not every run, because reasoning latency can balloon. |
| `gemma3:12b` | Local Ollama | Already installed locally; Google positions Gemma 3 as lightweight, multimodal, 128K-context, multilingual, and useful for question answering/summarization/reasoning. | No current local proof that Gemma 3 exposes Ollama `think`; treat as generalist, not transparent reasoning. | Use for summarization, visual/text context, and general local chat. Do not make it the first code-edit agent. |
| `qwen3-coder-next` / Qwen3 Coder family | Remote or future local/cloud route | Current Qwen model card says Qwen3-Coder-Next is open-weight, coding-agent oriented, efficient MoE, strong at tool use and recovery from execution failures. Continue also lists Qwen3 Coder 480B/30B among best open models for agent plan/edit roles. | Treat as coding-specialist, not automatically a local thinking-control route. Verify exact runtime behavior before using in Moussey. | Best remote/open-weight coding fallback candidate once routed through HF/provider with a no-spend dry-run and then explicit spend approval. |
| DeepSeek V3/R1 larger variants | Remote fallback, or local only if hardware allows | Strong reasoning/coding lineage; HF docs show OpenAI-compatible router can call DeepSeek models with `HF_TOKEN`. | DeepSeek R1 local supports thinking via Ollama; remote variants need provider-specific proof. | Keep as optional remote fallback behind HF dry-run and spend gate. |
| Kimi/Devstral/other current open coding models | Remote or later local experiment | Continue's model-role docs list Kimi K2 and Devstral among best open candidates for agent planning. Ollama catalog also shows rapidly changing cloud/open model options. | Must be verified per provider. | Do not block MVP on these; add as candidates after Qwen/DeepSeek/Gemma gates are boring. |

## Local Vs Remote Boundary

Local means:

- Ollama on `127.0.0.1:11434`.
- No token spend.
- Suitable for repeated local test summarization, failure clustering, verifier explanations, and small patch proposals.
- Must still run inside disposable-worktree wrappers before source edits.

Remote fallback means:

- Hugging Face Inference Providers or another OpenAI-compatible router.
- Requires explicit env/token gate, e.g. `HF_TOKEN`.
- Current HF docs confirm `https://router.huggingface.co/v1` with `HF_TOKEN` for OpenAI-compatible chat completions.
- Not MVP-default. Only use after a no-token dry-run reports the exact endpoint, model id, expected spend boundary, and the user/operator approves moving beyond dry-run.

## Thinking Controls

Ollama is the cleanest local reasoning control surface right now.

- Ollama supports a `think` field on chat/generate requests.
- Supported thinking-capable model families include Qwen 3, DeepSeek R1, DeepSeek v3.1, and GPT-OSS.
- Most models use boolean `think:true/false`; GPT-OSS uses levels such as `low`, `medium`, and `high`.
- Thinking output is separated from final answer through `thinking` / `message.thinking`, which is good for Moussey UI because the cockpit can store or hide the trace without confusing it with the answer.

MVP policy:

- Require a local API smoke before enabling a model in `/coding`.
- Capture whether `thinking` is present, absent, or unsupported.
- Show that in the model route card.
- Never call a model "reasoning-capable" just because it is large; require a runtime proof.

## Tool Shortlist

| Tool | Boundary | Current fit | Risks | MVP next wrapper |
|---|---|---|---|---|
| Aider | Local CLI; can connect to Ollama or OpenAI-compatible APIs | Best first patch-worker candidate. Aider docs explicitly support `aider --model ollama_chat/<model>` and warn that weak models may fail code-edit formats. | It can edit and commit in a real repo if run carelessly. Local models may produce unusable edit blocks. | Run only in disposable worktree; disable auto-commit or capture patch; require `git diff --check`, targeted tests, and patch artifact. |
| OpenCode | Local terminal agent; provider config supports OpenAI-compatible providers | Good future detached worker because it is agentic and provider-flexible. Docs support configuring OpenAI-compatible provider packages/base URLs. | Provider/model config and tool-calling behavior must be proven; local agents can stall or produce invalid tool calls. | Config-gated detached worker that runs a read-only probe first, then a patch run only after successful tool-call smoke. |
| Goose | Local/desktop/CLI agent; now has built-in local inference via llama.cpp plus extensions/MCP orientation | Good research lane for local inference and MCP-style tool orchestration. Goose docs say local provider can download GGUF models and run in-process without a separate server. | Another agent runtime increases surface area; built-in models are not necessarily best coding patch models. | Use for capability/routing probes first, not patch promotion. |
| Continue | IDE extension and agent workflow | Good human-supervised IDE handoff. Docs model-role table is useful for comparing open models by role: agent plan, chat edit, autocomplete, apply, embed/rerank. | Less appropriate as a browser-launched autonomous worker; state lives in IDE. | Use `/coding` to show handoff instructions/proof packets, not to drive Continue directly yet. |
| Cline | IDE and CLI agent; supports local models via Ollama/LM Studio | Good human-supervised local IDE agent. Docs include local runtime setup and hardware guidance. | Needs context/task scoping; local model quality varies; IDE actions need human supervision. | Treat as supervised IDE route until a CLI dry-run can produce a bounded patch artifact. |
| OpenHands | Heavier sandbox/server surface | Useful later for autonomous tasks, not needed for current MVP. | Too much platform surface before local-CI/source-state gates are boring. | Keep deferred. |

## What Must Pass Before Calling It MVP

The MVP is not "a model is installed" and not "a tool opened." It is a verified local coding loop with cost and mutation boundaries.

Required gates:

1. Model inventory gate
   - `ollama list` shows the model.
   - `GET /api/coding/capabilities` or the equivalent model route surface reports installed/config-gated/deferred state.
   - The route card says whether `think` is supported and proven.

2. No-token local smoke gate
   - Local model call runs against `127.0.0.1:11434`.
   - No `HF_TOKEN`, OpenAI, Anthropic, or other remote token is passed.
   - Output proves final answer and, for thinking models, separate thinking field behavior.

3. Disposable-worktree gate
   - Agent/tool runs from a generated worktree, not the primary checkout.
   - Source branch/head and remote-main head are logged.
   - Worktree, branch, server process, and port locks tear down cleanly.

4. Patch artifact gate
   - Any code-editing tool saves a patch artifact under a local evidence directory.
   - Primary checkout remains untouched until explicit apply/promotion.
   - Patch preview is available from `/coding`.

5. Verification gate
   - Run `git diff --check`.
   - Run the smallest owning test lane first.
   - For local-CI integration, the lane card must show source-state: `origin_main`, `dirty`, `not_origin_main`, or `unknown`.
   - A dirty/local green result must not be described as fresh-main portable green.

6. Token/spend gate
   - Remote fallback starts with dry-run only.
   - Dry-run prints provider endpoint, model id, env key names, and "no provider call made."
   - Real remote calls require explicit approval and must record spend boundary in run metadata.

7. Ledger/run-history gate
   - Run history captures command, cwd, model/tool, source state, exit code, duration, patch path, report/log path, and final message.
   - Ledger can orient the next agent, but PLAN.md, local-CI reports, tests, and patch artifacts remain authority.

8. UI inspectability gate
   - `/coding` must show the current status without requiring raw log archaeology: model/tool readiness, recent runs, worker final messages, local-CI proof, source-state badges, and exact next action.

## Proposed MVP Sequence

1. Keep C52 inventory as completed.
2. Add one allowlisted local Aider wrapper:
   - Model: `qwen3:8b`.
   - Runtime: Ollama local only.
   - Workdir: disposable worktree.
   - Authority: patch artifact only.
   - Tests: `git diff --check` plus one targeted local-CI or package test.
3. Add a second-model verifier pass:
   - Model: `deepseek-r1:8b`.
   - Purpose: explain or critique Aider patch and failing test output.
   - No edit authority.
4. Keep Gemma route for summarization/context cards.
5. Keep OpenCode/Goose as config-gated research until one read-only tool-call loop succeeds.
6. Keep Continue/Cline as IDE handoff surfaces until their CLI/automation paths can emit patch artifacts and run local-CI proof.
7. Keep HF router as dry-run only until Leo explicitly chooses to spend tokens.

## Bottom Line

The right MVP is not "best model wins." It is "cheap local model plus boring verification loop wins."

Use `qwen3:8b` and `deepseek-r1:8b` to make local failures understandable without burning tokens. Use Aider first for a contained patch-worker experiment. Keep OpenCode, Goose, Continue, and Cline visible as route candidates, but do not promote them to browser-launched edit agents until each can pass the same disposable-worktree, patch-artifact, source-state, and local-CI verification gates.
